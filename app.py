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
import json

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# Default Configuration
DEFAULT_RULE_WEIGHTS = {
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
    'Final_System_Output': 'rule_score_weighted', 
    'FAULT': 'fault_next_2_weeks',
    '2Week_Fault': '_fallback_prediction_'
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

def calculate_risk_dynamic(target_df, weights=None, enabled_rules=None):
    if weights is None: weights = DEFAULT_RULE_WEIGHTS
    if enabled_rules is None: enabled_rules = list(weights.keys())
    
    # Ensure rule columns are numeric
    for col in weights:
        if col in target_df.columns:
            target_df[col] = pd.to_numeric(target_df[col], errors='coerce').fillna(0).astype(int)
    
    weighted = pd.Series(0.0, index=target_df.index)
    total_enabled_weight = 0.0
    
    for col, weight in weights.items():
        if col in enabled_rules and col in target_df.columns:
            weighted += target_df[col] * weight
            total_enabled_weight += weight
    
    if total_enabled_weight > 0:
        target_df['rule_score_weighted'] = (weighted / total_enabled_weight).round(4)
    else:
        target_df['rule_score_weighted'] = 0.0
        
    return target_df

def finalize_df(new_df):
    new_df['calculated_risk_percentage'] = (new_df['rule_score_weighted'] * 100).clip(0, 100).round(1)
    new_df['flagged_at_risk'] = (new_df['calculated_risk_percentage'] >= RISK_THRESHOLD).astype(int)
    new_df['fault_next_2_weeks'] = pd.to_numeric(new_df['fault_next_2_weeks'], errors='coerce').fillna(0).astype(int)
    if 'date_recorded' in new_df.columns:
        new_df['date_recorded'] = pd.to_datetime(new_df['date_recorded'], errors='coerce')
        new_df = new_df.dropna(subset=['date_recorded'])
    return new_df.astype(object).where(pd.notnull(new_df), None)

def get_dynamic_df():
    global df
    if df.empty: return df
    
    custom_weights = request.args.get('weights')
    enabled_rules = request.args.getlist('enabled_rules')
    
    if not custom_weights and not enabled_rules:
        # If no dynamic params, we still want to ensure it's finalized (though global df usually is)
        return df
    
    temp_df = df.copy()
    weights = DEFAULT_RULE_WEIGHTS.copy()
    if custom_weights:
        try:
            input_weights = json.loads(custom_weights)
            for k, v in input_weights.items():
                if k in weights: weights[k] = float(v)
        except: pass
        
    if not enabled_rules:
        enabled_rules = list(weights.keys())
        
    temp_df = calculate_risk_dynamic(temp_df, weights, enabled_rules)
    return finalize_df(temp_df)

def normalize_and_risk(raw_df):
    raw_df = raw_df.loc[:, ~raw_df.columns.duplicated()].copy()
    
    used_targets = set()
    rename_map = {}
    
    for src, tgt in PARQUET_COLUMN_MAP.items():
        if src in raw_df.columns:
            if tgt not in used_targets:
                rename_map[src] = tgt
                used_targets.add(tgt)
                
    new_df = raw_df.rename(columns=rename_map)
    
    if 'fault_next_2_weeks' not in new_df.columns and '_fallback_prediction_' in new_df.columns:
        new_df['fault_next_2_weeks'] = new_df['_fallback_prediction_']
        
    for col, default in COLUMN_DEFAULTS.items():
        if col not in new_df.columns:
            new_df[col] = default
            
    # Initial calculation using defaults
    new_df = calculate_risk_dynamic(new_df)
    return finalize_df(new_df)

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
            filtered = filtered[pd.to_datetime(filtered['date_recorded']).dt.date == date_obj]
        except: pass
        
    month_str = request.args.get('month', '').strip()
    if month_str:
        try:
            filtered = filtered[pd.to_datetime(filtered['date_recorded']).dt.strftime('%Y-%m') == month_str]
        except: pass
        
    return filtered

@app.route('/api/stats')
def get_stats():
    working_df = get_dynamic_df()
    if working_df.empty:
        return jsonify({
            'total_records': 0, 'at_risk_count': 0, 'faults_occurred': 0,
            'classifications': {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0},
            'unique_areas': [], 'unique_segments': [], 'status': 'success'
        })
    
    at_risk = int((working_df['flagged_at_risk'] == 1).sum())
    faults = int((working_df['fault_next_2_weeks'] == 1).sum())
    
    tp = int(((working_df['flagged_at_risk'] == 1) & (working_df['fault_next_2_weeks'] == 1)).sum())
    tn = int(((working_df['flagged_at_risk'] == 0) & (working_df['fault_next_2_weeks'] == 0)).sum())
    fp = int(((working_df['flagged_at_risk'] == 1) & (working_df['fault_next_2_weeks'] == 0)).sum())
    fn = int(((working_df['flagged_at_risk'] == 0) & (working_df['fault_next_2_weeks'] == 1)).sum())
    
    return jsonify({
        'total_records': len(working_df), 'at_risk_count': at_risk, 'faults_occurred': faults,
        'classifications': {'TP': tp, 'TN': tn, 'FP': fp, 'FN': fn},
        'unique_areas': sorted(working_df['area_code'].dropna().unique().tolist()),
        'unique_segments': sorted(working_df['business_segment'].dropna().unique().tolist()),
        'status': 'success'
    })

@app.route('/api/data')
def get_data():
    working_df = get_dynamic_df()
    if working_df.empty:
        return jsonify({'data': [], 'total_count': 0, 'status': 'success'})
        
    filtered = apply_filters(working_df)
    
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
    
    clean_df = page_df.astype(object).where(pd.notnull(page_df), None)
    data_list = clean_df.to_dict(orient='records')
        
    return jsonify({
        'data': data_list,
        'total_count': len(filtered),
        'total_pages': (len(filtered) // size) + 1 if size > 0 else 1,
        'status': 'success'
    })

@app.route('/api/export')
def export_data():
    working_df = get_dynamic_df()
    filtered = apply_filters(working_df)
    if filtered.empty:
        return jsonify({'status': 'error', 'message': 'No data to export'}), 400
        
    fmt = request.args.get('format', 'csv').lower()
    filtered = filtered.copy()
    
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
