"""
FTTH Signal Drop Prediction System - Flask Backend
STRICT MANUAL UPLOAD MODE - No auto-loading.
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

# Global Dataframe - Initialized empty
df = pd.DataFrame(columns=COLUMN_DEFAULTS.keys())

def normalize_and_risk(raw_df):
    print(f"DEBUG: Normalizing raw dataframe with {len(raw_df)} rows")
    # Prevent the "arg must be a list, tuple, 1-d array, or Series" error by stripping duplicate columns early
    raw_df = raw_df.loc[:, ~raw_df.columns.duplicated()].copy()
    
    used_targets = set() # Start fresh for rename mapping
    rename_map = {}
    drop_cols = []
    
    for src, tgt in PARQUET_COLUMN_MAP.items():
        if src in raw_df.columns:
            actual_tgt = 'fault_next_2_weeks' if tgt == '_fault_alias_' else tgt
            
            if actual_tgt not in used_targets:
                rename_map[src] = actual_tgt
                used_targets.add(actual_tgt)
            else:
                drop_cols.append(src)
                
    new_df = raw_df.rename(columns=rename_map)
    new_df = new_df.drop(columns=drop_cols, errors='ignore')
    
    # Final safety deduplication
    new_df = new_df.loc[:, ~new_df.columns.duplicated()]

    for col, default in COLUMN_DEFAULTS.items():
        if col not in new_df.columns:
            new_df[col] = default
            
    # Risk calculation
    for col in RULE_WEIGHTS:
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0).astype(int)
    
    weighted = pd.Series(0.0, index=new_df.index)
    for col, weight in RULE_WEIGHTS.items():
        weighted += new_df[col] * weight
    
    # Update score and percentage
    new_df['rule_score_weighted'] = weighted.round(4)
    new_df['calculated_risk_percentage'] = (weighted * 100).clip(0, 100).round(1)
    new_df['flagged_at_risk'] = (new_df['calculated_risk_percentage'] >= RISK_THRESHOLD).astype(int)
    new_df['fault_next_2_weeks'] = pd.to_numeric(new_df['fault_next_2_weeks'], errors='coerce').fillna(0).astype(int)
    
    if 'date_recorded' in new_df.columns:
        new_df['date_recorded'] = pd.to_datetime(new_df['date_recorded'], errors='coerce')
        # Only drop if date is truly unparseable (NaT)
        before_drop = len(new_df)
        new_df = new_df.dropna(subset=['date_recorded'])
        after_drop = len(new_df)
        if before_drop != after_drop:
            print(f"DEBUG: Dropped {before_drop - after_drop} rows due to invalid dates")
    
    # Safety: replace all NaN with None or 0 to prevent JSON error
    # Convert to object to allow None without being turned back into NaN
    new_df = new_df.astype(object).where(pd.notnull(new_df), None)
        
    print(f"DEBUG: Normalization complete. Final rows: {len(new_df)}")
    return new_df

def apply_filters(source_df):
    if source_df.empty:
        return source_df
    
    filtered = source_df.copy()
    search = request.args.get('phone_number', '').strip()
    if search:
        filtered = filtered[filtered['phone_number'].astype(str).str.contains(search, case=False) | 
                            filtered['customer_name'].astype(str).str.contains(search, case=False)]
    
    areas = request.args.getlist('area_codes')
    if areas: filtered = filtered[filtered['area_code'].isin(areas)]
    
    segments = request.args.getlist('segments')
    if segments: filtered = filtered[filtered['business_segment'].isin(segments)]
    
    try:
        min_risk = float(request.args.get('min_risk', 0))
        if min_risk > 0:
            filtered = filtered[filtered['calculated_risk_percentage'] >= min_risk]
    except: pass
    
    date_str = request.args.get('date', '').strip()
    if date_str:
        try:
            date_obj = pd.to_datetime(date_str).date()
            # Convert date_recorded back to datetime for comparison
            filtered = filtered[pd.to_datetime(filtered['date_recorded']).dt.date == date_obj]
        except Exception as e:
            print(f"DEBUG: Date filter error: {e}")
        
    month_str = request.args.get('month', '').strip()
    if month_str:
        try:
            filtered = filtered[pd.to_datetime(filtered['date_recorded']).dt.strftime('%Y-%m') == month_str]
        except Exception as e:
            print(f"DEBUG: Month filter error: {e}")
        
    return filtered

@app.route('/api/stats')
def get_stats():
    global df
    print(f"DEBUG: /api/stats called. Current df size: {len(df)}")
    if df.empty:
        return jsonify({
            'total_records': 0, 'at_risk_count': 0, 'faults_occurred': 0,
            'classifications': {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0},
            'unique_areas': [], 'unique_segments': [], 'status': 'success'
        })
    
    at_risk = int((df['flagged_at_risk'] == 1).sum())
    faults = int((df['fault_next_2_weeks'] == 1).sum())
    
    tp = int(((df['flagged_at_risk'] == 1) & (df['fault_next_2_weeks'] == 1)).sum())
    tn = int(((df['flagged_at_risk'] == 0) & (df['fault_next_2_weeks'] == 0)).sum())
    fp = int(((df['flagged_at_risk'] == 1) & (df['fault_next_2_weeks'] == 0)).sum())
    fn = int(((df['flagged_at_risk'] == 0) & (df['fault_next_2_weeks'] == 1)).sum())
    
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
    print(f"DEBUG: /api/data called. Page: {request.args.get('page')}, Filters: {request.args.to_dict()}")
    if df.empty:
        return jsonify({'data': [], 'total_count': 0, 'status': 'success'})
        
    filtered = apply_filters(df)
    
    # Robust sort - convert to numeric/datetime for sorting then back to object for JSON
    if not filtered.empty and 'date_recorded' in filtered.columns:
        filtered['date_recorded_dt'] = pd.to_datetime(filtered['date_recorded'])
        filtered = filtered.sort_values(['date_recorded_dt', 'calculated_risk_percentage'], ascending=[False, False])
        filtered = filtered.drop(columns=['date_recorded_dt'])
    
    page = int(request.args.get('page', 1))
    size = int(request.args.get('page_size', 500))
    start = (page - 1) * size
    page_df = filtered.iloc[start:start+size].copy()
    
    if not page_df.empty:
        try:
            page_df['date_recorded'] = pd.to_datetime(page_df['date_recorded']).dt.strftime('%Y-%m-%d')
        except:
            page_df['date_recorded'] = page_df['date_recorded'].astype(str)
    
    # Final safety check: ensure no NaN/Inf reach the JSON
    # Converting to object and using where(notnull) is the most robust way to get 'null' in JSON
    clean_df = page_df.astype(object).where(pd.notnull(page_df), None)
    data_list = clean_df.to_dict(orient='records')
        
    print(f"DEBUG: Returning {len(page_df)} records of {len(filtered)} filtered")
    return jsonify({
        'data': data_list,
        'total_count': len(filtered),
        'total_pages': (len(filtered) // size) + 1 if size > 0 else 1,
        'status': 'success'
    })

@app.route('/api/export')
def export_data():
    global df
    filtered = apply_filters(df)
    if filtered.empty:
        return jsonify({'status': 'error', 'message': 'No data to export'}), 400
        
    fmt = request.args.get('format', 'csv').lower()
    filtered = filtered.copy()
    
    # Add clear classifications
    filtered['Final_Result'] = 'Valid Safe'
    filtered.loc[(filtered['flagged_at_risk']==1) & (filtered['fault_next_2_weeks']==1), 'Final_Result'] = 'Valid Alert'
    filtered.loc[(filtered['flagged_at_risk']==1) & (filtered['fault_next_2_weeks']==0), 'Final_Result'] = 'False Alarm'
    filtered.loc[(filtered['flagged_at_risk']==0) & (filtered['fault_next_2_weeks']==1), 'Final_Result'] = 'Missed Fault'
    
    if fmt == 'txt':
        output = io.StringIO()
        output.write("FTTH FAULT PREDICTION REPORT\n")
        output.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        output.write("="*80 + "\n\n")
        
        report_cols = ['phone_number', 'customer_name', 'area_code', 'date_recorded', 'calculated_risk_percentage', 'Final_Result']
        txt_data = filtered[report_cols].copy()
        txt_data['date_recorded'] = pd.to_datetime(txt_data['date_recorded']).dt.strftime('%Y-%m-%d')
        txt_data.columns = ['Phone', 'Name', 'Area', 'Date', 'Risk%', 'Result']
        output.write(txt_data.to_string(index=False))
        
        buf = io.BytesIO(output.getvalue().encode('utf-8'))
        return send_file(buf, mimetype='text/plain', as_attachment=True, download_name=f"fault_report_{datetime.now().strftime('%Y%m%d')}.txt")
    else:
        filtered['date_recorded'] = pd.to_datetime(filtered['date_recorded']).dt.strftime('%Y-%m-%d')
        buf = io.StringIO()
        filtered.to_csv(buf, index=False)
        output = io.BytesIO(buf.getvalue().encode('utf-8'))
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name=f"fault_data_{datetime.now().strftime('%Y%m%d')}.csv")

@app.route('/api/upload', methods=['POST'])
def upload():
    global df
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file'}), 400
    
    f = request.files['file']
    try:
        if f.filename.lower().endswith('.parquet'):
            raw = pd.read_parquet(io.BytesIO(f.read()))
            if isinstance(raw.index, pd.MultiIndex):
                raw = raw.reset_index(drop=True)
        else:
            raw = pd.read_csv(io.BytesIO(f.read()))
        
        df = normalize_and_risk(raw)
        return jsonify({'status': 'success', 'records': len(df)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset():
    global df
    df = pd.DataFrame(columns=COLUMN_DEFAULTS.keys())
    return jsonify({'status': 'success', 'message': 'All data cleared'})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
