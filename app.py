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
# Priority order matters when multiple source cols map to same target
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
    # FAULT is a secondary alias - only used if 2Week_Fault is absent
    'FAULT':                      '_fault_alias_',
}

# Default values for columns that may not exist in every file
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

# ============================================================================
# DATA LOADING
# ============================================================================

def normalize_columns(df):
    """
    Rename any known parquet/alternate column names to the dashboard standard.
    Handles cases where two source columns would produce duplicate target names.
    Then fills in any missing required columns with safe defaults.
    """
    # Rename known alternates — avoid creating duplicate columns
    used_targets = set()
    rename_map = {}
    for src, tgt in PARQUET_COLUMN_MAP.items():
        if src in df.columns:
            if tgt == '_fault_alias_':
                # Only use FAULT if 2Week_Fault / fault_next_2_weeks not already present
                if 'fault_next_2_weeks' not in df.columns and 'fault_next_2_weeks' not in used_targets:
                    rename_map[src] = 'fault_next_2_weeks'
                    used_targets.add('fault_next_2_weeks')
                else:
                    rename_map[src] = '_drop_'
            elif tgt not in used_targets:
                rename_map[src] = tgt
                used_targets.add(tgt)
            else:
                # Duplicate target — drop the source column
                rename_map[src] = '_drop_'

    df = df.rename(columns=rename_map)
    # Remove columns renamed to _drop_
    df = df.drop(columns=[c for c in df.columns if c == '_drop_'], errors='ignore')

    # Fill missing columns with defaults
    for col, default in COLUMN_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default

    return df


def compute_risk(df):
    """
    Recalculate risk scores from raw rule columns using RULE_WEIGHTS.
    Uses rule_score_weighted directly if the column has non-zero values;
    otherwise computes it from individual rule columns.
    """
    rule_cols = list(RULE_WEIGHTS.keys())
    available = [c for c in rule_cols if c in df.columns]

    # Convert rule columns to numeric safely
    for col in available:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    # Check if rule_score_weighted column already has real values
    if 'rule_score_weighted' in df.columns:
        df['rule_score_weighted'] = pd.to_numeric(df['rule_score_weighted'], errors='coerce').fillna(0.0)
        # Consider it valid only if max value > 0 (not all-zero placeholder)
        has_scores = float(df['rule_score_weighted'].max()) > 0.0
    else:
        has_scores = False

    if not has_scores:
        # Compute weighted score from individual rule columns
        weighted = pd.Series(0.0, index=df.index)
        for col in available:
            weighted += df[col] * RULE_WEIGHTS.get(col, 0)
        df['rule_score_weighted'] = weighted

    # Derive risk % and at-risk flag
    df['calculated_risk_percentage'] = (df['rule_score_weighted'] * 100).clip(0, 100)
    df['flagged_at_risk'] = (df['calculated_risk_percentage'] >= RISK_THRESHOLD).astype(int)

    return df


def load_data():
    """
    Load data in priority order: parquet → CSV → sample data.
    Handles column mismatches gracefully.
    """
    # 1. Try parquet
    parquet_file = 'final_fault_results.parquet'
    if os.path.exists(parquet_file):
        try:
            print(f"Loading parquet: {parquet_file} ...")
            df = pd.read_parquet(parquet_file)
            # Flatten any MultiIndex that pyarrow may produce
            if isinstance(df.index, pd.MultiIndex):
                df = df.reset_index(drop=True)
            df = df.reset_index(drop=True)
            df = normalize_columns(df)
            df['date_recorded'] = pd.to_datetime(df['date_recorded'], errors='coerce')
            df = df[df['date_recorded'].notna()].copy()   # drop rows with bad dates
            df = compute_risk(df)
            df['fault_next_2_weeks'] = pd.to_numeric(df['fault_next_2_weeks'], errors='coerce').fillna(0).astype(int)
            print(f"[OK] Parquet loaded: {len(df):,} records")
            return df
        except Exception as e:
            print(f"Warning: Could not load parquet ({e}). Trying CSV .")

    # 2. Try CSV
    csv_file = 'final_df_updated.csv'
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file, encoding='utf-8')
            df = normalize_columns(df)
            df['date_recorded'] = pd.to_datetime(df['date_recorded'], errors='coerce')
            df = df[df['date_recorded'].notna()].copy()
            df = compute_risk(df)
            df['fault_next_2_weeks'] = pd.to_numeric(df['fault_next_2_weeks'], errors='coerce').fillna(0).astype(int)
            print(f"[OK] CSV loaded: {len(df):,} records")
            return df
        except Exception as e:
            print(f"Warning: Could not load CSV ({e}). Using sample data.")

    # 3. Fallback sample
    return create_sample_data()


def create_sample_data():
    """Create minimal sample data when no file is available."""
    print("Creating sample data (no data file found) ...")
    np.random.seed(42)
    dates = pd.date_range('2025-07-18', periods=20, freq='D')
    areas = ['CMB_01', 'CMB_02', 'MAT_01', 'MAT_02', 'COL_01']
    segments = ['Retail', 'SME', 'LargeEnterprise']

    rows = []
    for i in range(20):
        rules = {k: np.random.randint(0, 2) for k in RULE_WEIGHTS}
        score = sum(rules[k] * RULE_WEIGHTS[k] for k in rules)
        risk_pct = score * 100
        rows.append({
            'phone_number':               f'077{1234567 + i}',
            'customer_name':              f'Customer {i+1}',
            'area_code':                  np.random.choice(areas),
            'business_segment':           np.random.choice(segments),
            'date_recorded':              dates[i],
            **rules,
            'rule_score_weighted':        round(score, 4),
            'calculated_risk_percentage': round(risk_pct, 1),
            'flagged_at_risk':            1 if risk_pct >= RISK_THRESHOLD else 0,
            'fault_next_2_weeks':         np.random.randint(0, 2),
        })
    return pd.DataFrame(rows)


# Load data at startup
df = load_data()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def classify_vectorized(flagged: pd.Series, fault: pd.Series) -> pd.Series:
    """Vectorized TP/TN/FP/FN classification — fast even on millions of rows."""
    result = pd.Series('TN', index=flagged.index)
    result[(flagged == 1) & (fault == 1)] = 'TP'
    result[(flagged == 1) & (fault == 0)] = 'FP'
    result[(flagged == 0) & (fault == 1)] = 'FN'
    return result


def apply_filters(source_df):
    """
    Apply all request query-param filters to a dataframe.
    Shared by /api/data and /api/export to avoid duplication.
    """
    filtered = source_df.copy()

    # Phone / name search
    search = request.args.get('phone_number', '').strip()
    if search:
        mask = (
            filtered['phone_number'].astype(str).str.contains(search, case=False, na=False) |
            filtered['customer_name'].astype(str).str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    # Area codes
    areas = request.args.getlist('area_codes')
    if areas:
        filtered = filtered[filtered['area_code'].isin(areas)]

    # Business segments
    segments = request.args.getlist('segments')
    if segments:
        filtered = filtered[filtered['business_segment'].isin(segments)]

    # Risk range
    try:
        min_risk = float(request.args.get('min_risk', 0))
        filtered = filtered[filtered['calculated_risk_percentage'] >= min_risk]
    except (ValueError, TypeError):
        pass

    try:
        max_risk = float(request.args.get('max_risk', 100))
        filtered = filtered[filtered['calculated_risk_percentage'] <= max_risk]
    except (ValueError, TypeError):
        pass

    # Exact date
    date_str = request.args.get('date', '').strip()
    if date_str:
        try:
            date_obj = pd.to_datetime(date_str)
            filtered = filtered[filtered['date_recorded'].dt.date == date_obj.date()]
        except Exception:
            pass

    # Month
    month_str = request.args.get('month', '').strip()
    if month_str:
        try:
            filtered = filtered[filtered['date_recorded'].dt.strftime('%Y-%m') == month_str]
        except Exception:
            pass

    return filtered


def format_response(df_slice):
    """Serialize a dataframe slice for JSON. Converts dates and rounds floats."""
    out = df_slice.copy()
    out['date_recorded'] = out['date_recorded'].dt.strftime('%Y-%m-%d')
    out['calculated_risk_percentage'] = out['calculated_risk_percentage'].round(1)
    out['rule_score_weighted'] = out['rule_score_weighted'].round(4)
    # Replace NaN with None (JSON null)
    out = out.where(pd.notnull(out), None)
    return out.to_dict(orient='records')


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    Summary statistics — fully vectorized, no iterrows.
    Fast even on 8M+ rows.
    """
    try:
        total = len(df)
        at_risk = int((df['flagged_at_risk'] == 1).sum())
        faults  = int((df['fault_next_2_weeks'] == 1).sum())

        # Vectorized confusion matrix
        classes = classify_vectorized(df['flagged_at_risk'], df['fault_next_2_weeks'])
        counts  = classes.value_counts()
        tp = int(counts.get('TP', 0))
        tn = int(counts.get('TN', 0))
        fp = int(counts.get('FP', 0))
        fn = int(counts.get('FN', 0))

        accuracy = round((tp + tn) / total * 100, 2) if total > 0 else 0.0

        return jsonify({
            'status':               'success',
            'total_records':        total,
            'at_risk_count':        at_risk,
            'faults_occurred':      faults,
            'accuracy_percentage':  accuracy,
            'classifications':      {'TP': tp, 'TN': tn, 'FP': fp, 'FN': fn},
            'unique_areas':         sorted(df['area_code'].dropna().unique().tolist()),
            'unique_segments':      sorted(df['business_segment'].dropna().unique().tolist()),
            'date_range': {
                'start': df['date_recorded'].min().strftime('%Y-%m-%d'),
                'end':   df['date_recorded'].max().strftime('%Y-%m-%d'),
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/data', methods=['GET'])
def get_data():
    """
    Paginated, filtered customer data.

    Query Parameters (filters same as before, plus):
      page      : int, 1-based (default 1)
      page_size : int (default 500, max 2000)
    """
    try:
        filtered = apply_filters(df)

        # Add classification column (vectorized)
        filtered = filtered.copy()
        filtered['prediction_class'] = classify_vectorized(
            filtered['flagged_at_risk'], filtered['fault_next_2_weeks']
        )

        # Sort by risk descending
        filtered = filtered.sort_values('calculated_risk_percentage', ascending=False)

        total_count = len(filtered)

        # Pagination
        try:
            page      = max(1, int(request.args.get('page', 1)))
            page_size = min(2000, max(1, int(request.args.get('page_size', 500))))
        except (ValueError, TypeError):
            page, page_size = 1, 500

        start = (page - 1) * page_size
        end   = start + page_size
        page_df = filtered.iloc[start:end]

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


@app.route('/api/export', methods=['GET'])
def export_data():
    """Export filtered data as a downloadable CSV."""
    try:
        filtered = apply_filters(df)
        filtered = filtered.copy()
        filtered['prediction_class'] = classify_vectorized(
            filtered['flagged_at_risk'], filtered['fault_next_2_weeks']
        )
        filtered['date_recorded'] = filtered['date_recorded'].dt.strftime('%Y-%m-%d')

        # Stream directly — don't touch disk
        buf = io.StringIO()
        filtered.to_csv(buf, index=False)
        buf.seek(0)

        return send_file(
            io.BytesIO(buf.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='export_filtered_data.csv'
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """
    Accept a CSV or Parquet file upload and reload the global dataframe.
    This lets the UI upload a .parquet without the browser needing to parse it.
    """
    global df

    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400

    f = request.files['file']
    filename = f.filename.lower()

    try:
        if filename.endswith('.parquet'):
            raw = pd.read_parquet(io.BytesIO(f.read()))
        elif filename.endswith('.csv'):
            raw = pd.read_csv(io.BytesIO(f.read()))
        else:
            return jsonify({'status': 'error', 'message': 'Only .csv and .parquet files are supported'}), 400

        raw = normalize_columns(raw)
        raw['date_recorded'] = pd.to_datetime(raw['date_recorded'], errors='coerce')
        raw = raw.dropna(subset=['date_recorded'])
        raw = compute_risk(raw)
        raw['fault_next_2_weeks'] = pd.to_numeric(raw['fault_next_2_weeks'], errors='coerce').fillna(0).astype(int)

        df = raw
        print(f"✓ Upload accepted: {len(df):,} records from {f.filename}")

        return jsonify({
            'status':   'success',
            'message':  f'Loaded {len(df):,} records',
            'records':  len(df),
            'columns':  df.columns.tolist(),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to load file: {str(e)}'}), 500


@app.route('/api/rules', methods=['GET'])
def get_rules():
    """Return current rule weights."""
    return jsonify({
        'status':                    'success',
        'risk_threshold_percentage': RISK_THRESHOLD,
        'rules':                     RULE_WEIGHTS,
        'total_weight':              round(sum(RULE_WEIGHTS.values()), 4),
    })


# ============================================================================
# HTML ROUTES
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'status': 'error', 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print(" FTTH Signal Drop Prediction System - Flask Backend")
    print("=" * 70)
    print(f"[OK] Data loaded:    {len(df):,} records")
    print(f"[OK] Risk threshold: {RISK_THRESHOLD}%")
    print(f"[OK] Rules:          {len(RULE_WEIGHTS)} rules with weights")
    print(f"[OK] Server:         http://localhost:5000")
    print("=" * 70 + "\n")

    app.run(debug=True, port=5000, host='0.0.0.0')
