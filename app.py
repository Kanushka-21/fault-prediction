"""
FTTH Signal Drop Prediction System - Flask Backend
ULTRA-PERFORMANCE MODE (Optimized for 8M+ Records)
"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import pandas as pd
import numpy as np
from datetime import datetime
import io

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# Configuration
RULE_WEIGHTS = {
    'sensor_error': 0.18, 'signal_critical': 0.22, 'signal_degrading': 0.15,
    'sudden_drop': 0.16, 'rx_instability': 0.12, 'low_signal': 0.10, 'frequent_fault': 0.07
}
RISK_THRESHOLD = 70.0

PARQUET_COLUMN_MAP = {
    'PPP_USERNAME_masked_masked': 'phone_number', 'PPP_USERNAME_masked': 'phone_number',
    'INSERTED_DATE': 'date_recorded', 'Rule1_SensorError': 'sensor_error',
    'Rule2_Critical': 'signal_critical', 'Rule3_Degrading': 'signal_degrading',
    'Rule4_SuddenDrop': 'sudden_drop', 'Rule5_RXInstability': 'rx_instability',
    'Rule6_LowSignal': 'low_signal', 'Rule7_FrequentFault': 'frequent_fault',
    'Final_System_Output': 'rule_score_weighted', '2Week_Fault': 'fault_next_2_weeks', 'FAULT': '_fault_alias_'
}

COLUMN_DEFAULTS = {
    'phone_number': 'N/A', 'customer_name': 'N/A', 'area_code': 'UNKNOWN',
    'business_segment': 'Unknown', 'date_recorded': pd.Timestamp.now(),
    'sensor_error': 0, 'signal_critical': 0, 'signal_degrading': 0, 'sudden_drop': 0,
    'rx_instability': 0, 'low_signal': 0, 'frequent_fault': 0,
    'rule_score_weighted': 0.0, 'calculated_risk_percentage': 0.0,
    'flagged_at_risk': 0, 'fault_next_2_weeks': 0
}

# Global Dataframe
df = pd.DataFrame()

def normalize_and_risk(raw_df):
    print(f"DEBUG: Processing {len(raw_df):,} records...")
    start_time = datetime.now()
    
    # 1. Deduplicate columns and subset only what we need to save memory
    new_df = raw_df.loc[:, ~raw_df.columns.duplicated()].copy()
    
    # 2. Map columns
    rename_map = {}
    for src, tgt in PARQUET_COLUMN_MAP.items():
        if src in new_df.columns:
            actual_tgt = 'fault_next_2_weeks' if tgt == '_fault_alias_' else tgt
            if actual_tgt not in rename_map.values():
                rename_map[src] = actual_tgt
    new_df = new_df.rename(columns=rename_map)
    
    # 3. Fill missing essential columns
    for col, default in COLUMN_DEFAULTS.items():
        if col not in new_df.columns:
            new_df[col] = default
            
    # 4. Use CATEGORICAL types for strings to save massive memory
    cat_cols = ['area_code', 'business_segment']
    for col in cat_cols:
        new_df[col] = new_df[col].astype('category')
            
    # 5. Optimized Numeric conversions
    for col in RULE_WEIGHTS:
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0).astype(np.int8)
    
    # 6. Faster Risk Calculation
    weighted = pd.Series(0.0, index=new_df.index)
    for col, weight in RULE_WEIGHTS.items():
        weighted += new_df[col].values * weight
        
    new_df['rule_score_weighted'] = weighted.astype(np.float32).round(4)
    new_df['calculated_risk_percentage'] = (weighted * 100).clip(0, 100).astype(np.float32).round(1)
    new_df['flagged_at_risk'] = (new_df['calculated_risk_percentage'] >= RISK_THRESHOLD).astype(np.int8)
    new_df['fault_next_2_weeks'] = pd.to_numeric(new_df['fault_next_2_weeks'], errors='coerce').fillna(0).astype(np.int8)
    
    # 7. Date Handling
    new_df['date_recorded'] = pd.to_datetime(new_df['date_recorded'], errors='coerce')
    new_df = new_df.dropna(subset=['date_recorded'])
    
    print(f"DEBUG: Processing complete in {datetime.now() - start_time}. Final rows: {len(new_df):,}")
    return new_df

def apply_filters(source_df):
    if source_df.empty:
        return source_df
    
    filtered = source_df
    
    # Text Search (Most expensive operation, only run if needed)
    search = request.args.get('phone_number', '').strip()
    if search:
        # Use str.contains only on the required subset to save CPU
        mask = (filtered['phone_number'].astype(str).str.contains(search, case=False) | 
                filtered['customer_name'].astype(str).str.contains(search, case=False))
        filtered = filtered[mask]
    
    # Category filters (EXTREMELY FAST)
    areas = request.args.getlist('area_codes')
    if areas:
        filtered = filtered[filtered['area_code'].isin(areas)]
    
    segments = request.args.getlist('segments')
    if segments:
        filtered = filtered[filtered['business_segment'].isin(segments)]
    
    # Risk Level
    try:
        min_risk = float(request.args.get('min_risk', 0))
        if min_risk > 0:
            filtered = filtered[filtered['calculated_risk_percentage'] >= min_risk]
    except: pass
    
    # Time Filters
    date_str = request.args.get('date', '').strip()
    if date_str:
        try:
            date_val = pd.to_datetime(date_str).date()
            filtered = filtered[filtered['date_recorded'].dt.date == date_val]
        except: pass
        
    month_str = request.args.get('month', '').strip()
    if month_str:
        try:
            filtered = filtered[filtered['date_recorded'].dt.strftime('%Y-%m') == month_str]
        except: pass
        
    return filtered

@app.route('/api/stats')
def get_stats():
    global df
    if df.empty:
        return jsonify({'total_records': 0, 'status': 'success'})
    
    # Use vectorized sums for speed
    at_risk = int((df['flagged_at_risk'] == 1).sum())
    faults = int((df['fault_next_2_weeks'] == 1).sum())
    
    # Efficiency: use numpy logic for confusion matrix
    risk_arr = df['flagged_at_risk'].values
    fault_arr = df['fault_next_2_weeks'].values
    
    tp = int(((risk_arr == 1) & (fault_arr == 1)).sum())
    tn = int(((risk_arr == 0) & (fault_arr == 0)).sum())
    fp = int(((risk_arr == 1) & (fault_arr == 0)).sum())
    fn = int(((risk_arr == 0) & (fault_arr == 1)).sum())
    
    return jsonify({
        'total_records': len(df), 'at_risk_count': at_risk, 'faults_occurred': faults,
        'classifications': {'TP': tp, 'TN': tn, 'FP': fp, 'FN': fn},
        'unique_areas': sorted(df['area_code'].dropna().unique().tolist()),
        'unique_segments': sorted(df['business_segment'].dropna().unique().tolist()),
        'status': 'success'
    })

@app.route('/api/data')
def get_data():
    global df
    if df.empty:
        return jsonify({'data': [], 'total_count': 0, 'status': 'success'})
        
    # 1. Filter
    filtered = apply_filters(df)
    total_found = len(filtered)
    
    # 2. Sort (Only if results are manageable)
    if 0 < total_found < 50000:
        filtered = filtered.sort_values(['date_recorded', 'calculated_risk_percentage'], ascending=[False, False])
    
    # 3. Paginate
    page = int(request.args.get('page', 1))
    size = int(request.args.get('page_size', 500))
    start = (page - 1) * size
    page_df = filtered.iloc[start:start+size].copy()
    
    if not page_df.empty:
        # 4. JSON-Friendly Cleaning (ONLY ON 500 ROWS)
        page_df['date_recorded'] = page_df['date_recorded'].dt.strftime('%Y-%m-%d')
        # Explicit conversion to native Python types for JSON
        data_list = page_df.replace({np.nan: None}).to_dict(orient='records')
    else:
        data_list = []
        
    return jsonify({
        'data': data_list,
        'total_count': total_found,
        'total_pages': (total_found // size) + 1 if size > 0 else 1,
        'status': 'success'
    })

@app.route('/api/export')
def export_data():
    global df
    if df.empty:
        return jsonify({'status': 'error', 'message': 'No data loaded'}), 400
        
    filtered = apply_filters(df)
    if filtered.empty:
        return jsonify({'status': 'error', 'message': 'No data matching filters'}), 400
        
    fmt = request.args.get('format', 'csv').lower()
    
    # Fast vectorized classification for export
    export_df = filtered.copy()
    risk_arr = export_df['flagged_at_risk'].values
    fault_arr = export_df['fault_next_2_weeks'].values
    
    conditions = [
        (risk_arr == 1) & (fault_arr == 1),
        (risk_arr == 1) & (fault_arr == 0),
        (risk_arr == 0) & (fault_arr == 1)
    ]
    choices = ['Valid Alert', 'False Alarm', 'Missed Fault']
    export_df['Final_Result'] = np.select(conditions, choices, default='Valid Safe')
    
    # Format dates efficiently
    export_df['date_recorded'] = export_df['date_recorded'].dt.strftime('%Y-%m-%d')
    
    if fmt == 'txt':
        output = io.StringIO()
        output.write(f"FTTH FAULT PREDICTION REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        output.write('='*80 + '\n\n')
        
        report_cols = ['phone_number', 'customer_name', 'area_code', 'date_recorded', 'calculated_risk_percentage', 'Final_Result']
        txt_data = export_df[report_cols].head(10000)
        output.write(txt_data.to_string(index=False))
        
        buf = io.BytesIO(output.getvalue().encode('utf-8'))
        return send_file(buf, mimetype='text/plain', as_attachment=True, download_name='fault_report.txt')
    else:
        buf = io.StringIO()
        export_df.to_csv(buf, index=False)
        output = io.BytesIO(buf.getvalue().encode('utf-8'))
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='fault_data.csv')

@app.route('/api/upload', methods=['POST'])
def upload():
    global df
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file'}), 400
    
    f = request.files['file']
    try:
        # Efficient parquet reading
        if f.filename.lower().endswith('.parquet'):
            raw = pd.read_parquet(io.BytesIO(f.read()))
        else:
            raw = pd.read_csv(io.BytesIO(f.read()))
        
        df = normalize_and_risk(raw)
        return jsonify({'status': 'success', 'records': len(df)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset():
    global df
    df = pd.DataFrame()
    return jsonify({'status': 'success', 'message': 'All data cleared'})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # Increase timeout for large uploads if needed
    app.run(debug=True, port=5000, host='0.0.0.0')
