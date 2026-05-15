"""
FTTH Signal Drop Prediction System - Flask Backend
Supports both CSV and Parquet data files.
Implements risk calculation, filtering, pagination, and data serving.
"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import pandas as pd
import numpy as np
from datetime import datetime
import os
import io

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# ============================================================================
# CONFIGURATION
# ============================================================================

RULE_WEIGHTS = {
    'sensor_error': 0.18,
    'signal_critical': 0.22,
    'signal_degrading': 0.15,
    'sudden_drop': 0.16,
    'rx_instability': 0.12,
    'low_signal': 0.10,
    'frequent_fault': 0.07
}

RISK_THRESHOLD = 70.0

# Map parquet column names -> dashboard standard names
PARQUET_COLUMN_MAP = {
    'PPP_USERNAME_masked_masked': 'phone_number',
    'PPP_USERNAME_masked':        'phone_number',
    'INSERTED_DATE':              'date_recorded',
    'Rule1_SensorError':          'sensor_error',
    'Rule2_Critical':             'signal_critical',
    'Rule3_Degrading':            'signal_degrading',
    'Rule4_SuddenDrop':           'sudden_drop',
    'Rule5_RXInstability':        'rx_instability',
    'Rule6_LowSignal':            'low_signal',
    'Rule7_FrequentFault':        'frequent_fault',
    'Final_System_Output':        'rule_score_weighted',
    '2Week_Fault':                'fault_next_2_weeks',
    'FAULT':                      '_fault_alias_',
}

COLUMN_DEFAULTS = {
    'phone_number':               'N/A',
    'customer_name':              'N/A',
    'area_code':                  'UNKNOWN',
    'business_segment':           'Unknown',
    'sensor_error':               0,
    'signal_critical':            0,
    'signal_degrading':           0,
    'sudden_drop':                0,
    'rx_instability':             0,
    'low_signal':                 0,
    'frequent_fault':             0,
    'rule_score_weighted':        0.0,
    'calculated_risk_percentage': 0.0,
    'flagged_at_risk':            0,
    'fault_next_2_weeks':         0,
}

# Initialize with an empty dataframe — strictly waits for upload
df = pd.DataFrame(columns=COLUMN_DEFAULTS.keys())

# ============================================================================
# LOGIC
# ============================================================================

def normalize_columns(df):
    used_targets = set()
    rename_map = {}
    for src, tgt in PARQUET_COLUMN_MAP.items():
        if src in df.columns:
            if tgt == '_fault_alias_':
                if 'fault_next_2_weeks' not in df.columns and 'fault_next_2_weeks' not in used_targets:
                    rename_map[src] = 'fault_next_2_weeks'
                    used_targets.add('fault_next_2_weeks')
                else:
                    rename_map[src] = '_drop_'
            elif tgt not in used_targets:
                rename_map[src] = tgt
                used_targets.add(tgt)
            else:
                rename_map[src] = '_drop_'
    df = df.rename(columns=rename_map)
    df = df.drop(columns=[c for c in df.columns if c == '_drop_'], errors='ignore')
    for col, default in COLUMN_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
    return df

def compute_risk(df):
    rule_cols = list(RULE_WEIGHTS.keys())
    available = [c for c in rule_cols if c in df.columns]
    for col in available:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    if 'rule_score_weighted' in df.columns:
        df['rule_score_weighted'] = pd.to_numeric(df['rule_score_weighted'], errors='coerce').fillna(0.0)
        has_scores = float(df['rule_score_weighted'].max()) > 0.0
    else:
        has_scores = False
    if not has_scores:
        weighted = pd.Series(0.0, index=df.index)
        for col in available:
            weighted += df[col] * RULE_WEIGHTS.get(col, 0)
        df['rule_score_weighted'] = weighted
    df['calculated_risk_percentage'] = (df['rule_score_weighted'] * 100).clip(0, 100)
    df['flagged_at_risk'] = (df['calculated_risk_percentage'] >= RISK_THRESHOLD).astype(int)
    return df

def apply_filters(source_df):
    if source_df.empty:
        return source_df
    mask = pd.Series(True, index=source_df.index)
    search = request.args.get('phone_number', '').strip()
    if search:
        phone_mask = source_df['phone_number'].astype(str).str.contains(search, case=False, na=False)
        name_mask = source_df['customer_name'].astype(str).str.contains(search, case=False, na=False)
        mask &= (phone_mask | name_mask)
    areas = request.args.getlist('area_codes')
    if areas:
        mask &= source_df['area_code'].isin(areas)
    segments = request.args.getlist('segments')
    if segments:
        mask &= source_df['business_segment'].isin(segments)
    try:
        min_risk = float(request.args.get('min_risk', 0))
        if min_risk > 0:
            mask &= (source_df['calculated_risk_percentage'] >= min_risk)
    except: pass
    date_str = request.args.get('date', '').strip()
    if date_str:
        try:
            date_obj = pd.to_datetime(date_str).date()
            mask &= (source_df['date_recorded'].dt.date == date_obj)
        except: pass
    month_str = request.args.get('month', '').strip()
    if month_str:
        try:
            mask &= (source_df['date_recorded'].dt.strftime('%Y-%m') == month_str)
        except: pass
    return source_df[mask]

def format_response(df_slice):
    if df_slice.empty: return []
    out = df_slice.copy()
    if 'date_recorded' in out.columns:
        out['date_recorded'] = out['date_recorded'].dt.strftime('%Y-%m-%d')
    if 'calculated_risk_percentage' in out.columns:
        out['calculated_risk_percentage'] = out['calculated_risk_percentage'].round(1)
    if 'rule_score_weighted' in out.columns:
        out['rule_score_weighted'] = out['rule_score_weighted'].round(4)
    out = out.where(pd.notnull(out), None)
    return out.to_dict(orient='records')

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        total = len(df)
        if total == 0:
            return jsonify({
                'status': 'success', 'total_records': 0, 'at_risk_count': 0,
                'faults_occurred': 0, 'accuracy_percentage': 0,
                'classifications': {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0},
                'unique_areas': [], 'unique_segments': [], 'date_range': {'start': 'N/A', 'end': 'N/A'}
            })
        at_risk = int((df['flagged_at_risk'] == 1).sum())
        faults  = int((df['fault_next_2_weeks'] == 1).sum())
        flagged = (df['flagged_at_risk'] == 1)
        has_fault = (df['fault_next_2_weeks'] == 1)
        tp = int((flagged & has_fault).sum())
        tn = int((~flagged & ~has_fault).sum())
        fp = int((flagged & ~has_fault).sum())
        fn = int((~flagged & has_fault).sum())
        accuracy = round((tp + tn) / total * 100, 2)
        return jsonify({
            'status': 'success', 'total_records': total, 'at_risk_count': at_risk,
            'faults_occurred': faults, 'accuracy_percentage': accuracy,
            'classifications': {'TP': tp, 'TN': tn, 'FP': fp, 'FN': fn},
            'unique_areas': sorted(df['area_code'].dropna().unique().tolist()),
            'unique_segments': sorted(df['business_segment'].dropna().unique().tolist()),
            'date_range': {
                'start': df['date_recorded'].min().strftime('%Y-%m-%d'),
                'end':   df['date_recorded'].max().strftime('%Y-%m-%d'),
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/data', methods=['GET'])
def get_data():
    try:
        filtered = apply_filters(df)

        # Sort logic: Priority 1: Date (Recent first), Priority 2: Risk (Highest first)
        if not filtered.empty:
            # Ensure date is datetime for proper sorting
            filtered['date_recorded'] = pd.to_datetime(filtered['date_recorded'])
            filtered = filtered.sort_values(['date_recorded', 'calculated_risk_percentage'], ascending=[False, False])

        total_count = len(filtered)
        try:
            page = max(1, int(request.args.get('page', 1)))
            page_size = min(2000, max(1, int(request.args.get('page_size', 500))))
        except: page, page_size = 1, 500

        start = (page - 1) * page_size
        page_df = filtered.iloc[start:start + page_size].copy()

        if not page_df.empty:
            page_df['prediction_class'] = 'TN'
            page_df.loc[(page_df['flagged_at_risk']==1) & (page_df['fault_next_2_weeks']==1), 'prediction_class'] = 'TP'
            page_df.loc[(page_df['flagged_at_risk']==1) & (page_df['fault_next_2_weeks']==0), 'prediction_class'] = 'FP'
            page_df.loc[(page_df['flagged_at_risk']==0) & (page_df['fault_next_2_weeks']==1), 'prediction_class'] = 'FN'

        total_pages = max(1, (total_count + page_size - 1) // page_size)

        return jsonify({
            'status':       'success',
            'total_count':  total_count,
            'page':         page,
            'page_size':    page_size,
            'total_pages':  total_pages,
            'count':        len(page_df),
            'data':         format_response(page_df),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    global df
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400
    f = request.files['file']
    if not f.filename:
        df = pd.DataFrame(columns=COLUMN_DEFAULTS.keys())
        return jsonify({'status': 'success', 'message': 'Cleared', 'records': 0})
    try:
        if f.filename.lower().endswith('.parquet'):
            raw = pd.read_parquet(io.BytesIO(f.read()))
        else:
            raw = pd.read_csv(io.BytesIO(f.read()))
        raw = normalize_columns(raw)
        raw['date_recorded'] = pd.to_datetime(raw['date_recorded'], errors='coerce')
        raw = raw.dropna(subset=['date_recorded'])
        raw = compute_risk(raw)
        df = raw
        return jsonify({'status': 'success', 'message': f'Loaded {len(df)} records', 'records': len(df)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
