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
    'business_segment': 'Unknown', 'sensor_error': 0, 'signal_critical': 0,
    'signal_degrading': 0, 'sudden_drop': 0, 'rx_instability': 0, 'low_signal': 0,
    'frequent_fault': 0, 'rule_score_weighted': 0.0, 'calculated_risk_percentage': 0.0,
    'flagged_at_risk': 0, 'fault_next_2_weeks': 0
}

# Global Dataframe - Initialized empty
df = pd.DataFrame(columns=COLUMN_DEFAULTS.keys())

def normalize_and_risk(raw_df):
    used_targets = set()
    rename_map = {}
    for src, tgt in PARQUET_COLUMN_MAP.items():
        if src in raw_df.columns:
            if tgt == '_fault_alias_':
                if 'fault_next_2_weeks' not in raw_df.columns:
                    rename_map[src] = 'fault_next_2_weeks'
            elif tgt not in used_targets:
                rename_map[src] = tgt
                used_targets.add(tgt)
    
    new_df = raw_df.rename(columns=rename_map)
    for col, default in COLUMN_DEFAULTS.items():
        if col not in new_df.columns:
            new_df[col] = default
            
    # Risk calculation
    for col in RULE_WEIGHTS:
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0).astype(int)
    
    weighted = pd.Series(0.0, index=new_df.index)
    for col, weight in RULE_WEIGHTS.items():
        weighted += new_df[col] * weight
        
    new_df['calculated_risk_percentage'] = (weighted * 100).clip(0, 100).round(1)
    new_df['flagged_at_risk'] = (new_df['calculated_risk_percentage'] >= RISK_THRESHOLD).astype(int)
    new_df['fault_next_2_weeks'] = pd.to_numeric(new_df['fault_next_2_weeks'], errors='coerce').fillna(0).astype(int)
    
    if 'date_recorded' in new_df.columns:
        new_df['date_recorded'] = pd.to_datetime(new_df['date_recorded'], errors='coerce')
        new_df = new_df.dropna(subset=['date_recorded'])
        
    return new_df

@app.route('/api/stats')
def get_stats():
    global df
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
    if df.empty:
        return jsonify({'data': [], 'total_count': 0, 'status': 'success'})
        
    # Simple filtering
    filtered = df.copy()
    search = request.args.get('phone_number', '').strip()
    if search:
        filtered = filtered[filtered['phone_number'].astype(str).str.contains(search, case=False) | 
                            filtered['customer_name'].astype(str).str.contains(search, case=False)]
    
    areas = request.args.getlist('area_codes')
    if areas: filtered = filtered[filtered['area_code'].isin(areas)]
    
    # Sort
    filtered = filtered.sort_values(['date_recorded', 'calculated_risk_percentage'], ascending=[False, False])
    
    # Paginate
    page = int(request.args.get('page', 1))
    size = int(request.args.get('page_size', 500))
    start = (page - 1) * size
    page_df = filtered.iloc[start:start+size].copy()
    
    # Format dates for JSON
    if not page_df.empty:
        page_df['date_recorded'] = page_df['date_recorded'].dt.strftime('%Y-%m-%d')
        
    return jsonify({
        'data': page_df.to_dict(orient='records'),
        'total_count': len(filtered),
        'total_pages': (len(filtered) // size) + 1,
        'status': 'success'
    })

@app.route('/api/upload', methods=['POST'])
def upload():
    global df
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file'}), 400
    
    f = request.files['file']
    try:
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
    df = pd.DataFrame(columns=COLUMN_DEFAULTS.keys())
    return jsonify({'status': 'success', 'message': 'All data cleared'})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
