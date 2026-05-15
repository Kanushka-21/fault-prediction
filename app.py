"""
FTTH Signal Drop Prediction System - Flask Backend
Implements risk calculation, filtering, and data serving
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

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

RISK_THRESHOLD = 70.0  # 70% threshold for flagging as at-risk

# ============================================================================
# DATA LOADING
# ============================================================================

def load_data():
    """Load and prepare data from CSV"""
    csv_file = 'final_df_updated.csv'
    if not os.path.exists(csv_file):
        print(f"Warning: {csv_file} not found. Using sample data.")
        return create_sample_data()
    
    try:
        df = pd.read_csv(csv_file)
        
        # Ensure data types
        df['date_recorded'] = pd.to_datetime(df['date_recorded'])
        df['flagged_at_risk'] = df['calculated_risk_percentage'] >= RISK_THRESHOLD
        df['flagged_at_risk'] = df['flagged_at_risk'].astype(int)
        
        print(f"✓ Loaded {len(df)} records from {csv_file}")
        return df
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return create_sample_data()

def create_sample_data():
    """Create sample data if CSV not available"""
    print("Creating sample data...")
    np.random.seed(42)
    
    dates = pd.date_range('2025-07-18', periods=20, freq='D')
    areas = ['CMB_01', 'CMB_02', 'CMB_03', 'MAT_01', 'MAT_02', 'COL_01', 'COL_02']
    segments = ['Retail', 'SME', 'LargeEnterprise']
    
    data = []
    for i in range(20):
        phone = f"077{1234567 + i}"
        name = f"Customer {i+1}"
        
        # Generate random rule triggers
        rules = {
            'sensor_error': np.random.randint(0, 2),
            'signal_critical': np.random.randint(0, 2),
            'signal_degrading': np.random.randint(0, 2),
            'sudden_drop': np.random.randint(0, 2),
            'rx_instability': np.random.randint(0, 2),
            'low_signal': np.random.randint(0, 2),
            'frequent_fault': np.random.randint(0, 2),
        }
        
        # Calculate risk
        rule_score = sum([rules[k] * RULE_WEIGHTS[k] for k in rules])
        risk_pct = rule_score * 100
        flagged = 1 if risk_pct >= RISK_THRESHOLD else 0
        
        data.append({
            'phone_number': phone,
            'customer_name': name,
            'area_code': np.random.choice(areas),
            'business_segment': np.random.choice(segments),
            'date_recorded': dates[i],
            'sensor_error': rules['sensor_error'],
            'signal_critical': rules['signal_critical'],
            'signal_degrading': rules['signal_degrading'],
            'sudden_drop': rules['sudden_drop'],
            'rx_instability': rules['rx_instability'],
            'low_signal': rules['low_signal'],
            'frequent_fault': rules['frequent_fault'],
            'rule_score_weighted': rule_score,
            'calculated_risk_percentage': risk_pct,
            'flagged_at_risk': flagged,
            'fault_next_2_weeks': np.random.randint(0, 2)
        })
    
    return pd.DataFrame(data)

# Load data at startup
df = load_data()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def classify_prediction(row):
    """
    Classify prediction as TP, TN, FP, or FN
    
    TP (True Positive): Flagged at-risk AND fault occurred
    TN (True Negative): Not flagged AND no fault
    FP (False Positive): Flagged at-risk BUT no fault (false alarm)
    FN (False Negative): Not flagged BUT fault occurred (missed alert)
    """
    flagged = row['flagged_at_risk']
    fault = row['fault_next_2_weeks']
    
    if flagged == 1 and fault == 1:
        return 'TP'
    elif flagged == 0 and fault == 0:
        return 'TN'
    elif flagged == 1 and fault == 0:
        return 'FP'
    else:  # flagged == 0 and fault == 1
        return 'FN'

def format_response(df):
    """Format dataframe for JSON response"""
    df_copy = df.copy()
    df_copy['date_recorded'] = df_copy['date_recorded'].dt.strftime('%Y-%m-%d')
    df_copy['calculated_risk_percentage'] = df_copy['calculated_risk_percentage'].round(1)
    df_copy['rule_score_weighted'] = df_copy['rule_score_weighted'].round(4)
    return df_copy.to_dict(orient='records')

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    Get summary statistics
    
    Returns:
    - total_records: Total number of records
    - at_risk_count: Records flagged as at-risk (risk >= 70%)
    - faults_occurred: Records where fault actually occurred
    - classifications: Counts of TP, TN, FP, FN
    - unique_areas: List of unique area codes
    - unique_segments: List of unique business segments
    """
    try:
        total = len(df)
        at_risk = int((df['flagged_at_risk'] == 1).sum())
        faults = int((df['fault_next_2_weeks'] == 1).sum())
        
        # Calculate confusion matrix
        classifications = {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0}
        for _, row in df.iterrows():
            cls = classify_prediction(row)
            classifications[cls] += 1
        
        # Accuracy metrics
        total_correct = classifications['TP'] + classifications['TN']
        accuracy = (total_correct / total * 100) if total > 0 else 0
        
        return jsonify({
            'status': 'success',
            'total_records': total,
            'at_risk_count': at_risk,
            'faults_occurred': faults,
            'accuracy_percentage': round(accuracy, 2),
            'classifications': {
                'TP': classifications['TP'],
                'TN': classifications['TN'],
                'FP': classifications['FP'],
                'FN': classifications['FN']
            },
            'unique_areas': sorted(df['area_code'].unique().tolist()),
            'unique_segments': sorted(df['business_segment'].unique().tolist()),
            'date_range': {
                'start': df['date_recorded'].min().strftime('%Y-%m-%d'),
                'end': df['date_recorded'].max().strftime('%Y-%m-%d')
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/data', methods=['GET'])
def get_data():
    """
    Get filtered data based on query parameters
    
    Query Parameters:
    - phone_number: Search phone or customer name (partial match)
    - area_codes: List of area codes to filter (comma-separated or multiple params)
    - segments: List of business segments (comma-separated or multiple params)
    - min_risk: Minimum risk percentage
    - max_risk: Maximum risk percentage
    - date: Single date (YYYY-MM-DD)
    - month: Month filter (YYYY-MM)
    
    Returns: Sorted list of records (by risk descending)
    """
    try:
        filtered_df = df.copy()
        
        # Phone/Name search
        if 'phone_number' in request.args:
            search = request.args.get('phone_number', '').strip()
            if search:
                filtered_df = filtered_df[
                    (filtered_df['phone_number'].str.contains(search, case=False, na=False)) |
                    (filtered_df['customer_name'].str.contains(search, case=False, na=False))
                ]
        
        # Area code filter
        if 'area_codes' in request.args:
            areas = request.args.getlist('area_codes')
            if areas:
                filtered_df = filtered_df[filtered_df['area_code'].isin(areas)]
        
        # Business segment filter
        if 'segments' in request.args:
            segments = request.args.getlist('segments')
            if segments:
                filtered_df = filtered_df[filtered_df['business_segment'].isin(segments)]
        
        # Risk range filter
        if 'min_risk' in request.args:
            try:
                min_risk = float(request.args.get('min_risk'))
                filtered_df = filtered_df[filtered_df['calculated_risk_percentage'] >= min_risk]
            except ValueError:
                pass
        
        if 'max_risk' in request.args:
            try:
                max_risk = float(request.args.get('max_risk'))
                filtered_df = filtered_df[filtered_df['calculated_risk_percentage'] <= max_risk]
            except ValueError:
                pass
        
        # Date filter
        if 'date' in request.args:
            date_str = request.args.get('date')
            try:
                date_obj = pd.to_datetime(date_str)
                filtered_df = filtered_df[filtered_df['date_recorded'].dt.date == date_obj.date()]
            except:
                pass
        
        # Month filter
        if 'month' in request.args:
            month_str = request.args.get('month')  # Format: YYYY-MM
            try:
                filtered_df = filtered_df[
                    filtered_df['date_recorded'].dt.strftime('%Y-%m') == month_str
                ]
            except:
                pass
        
        # Add classification column
        filtered_df['prediction_class'] = filtered_df.apply(classify_prediction, axis=1)
        
        # Sort by risk descending
        filtered_df = filtered_df.sort_values('calculated_risk_percentage', ascending=False)
        
        return jsonify({
            'status': 'success',
            'count': len(filtered_df),
            'data': format_response(filtered_df)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/export', methods=['GET'])
def export_data():
    """
    Export filtered data as CSV file
    
    Query parameters: Same as /api/data
    Returns: CSV file download
    """
    try:
        # Get filtered data using same logic as /api/data
        # Reconstruct the filtered dataframe
        filtered_df = df.copy()
        
        # Apply same filters
        if 'phone_number' in request.args:
            search = request.args.get('phone_number', '').strip()
            if search:
                filtered_df = filtered_df[
                    (filtered_df['phone_number'].str.contains(search, case=False, na=False)) |
                    (filtered_df['customer_name'].str.contains(search, case=False, na=False))
                ]
        
        if 'area_codes' in request.args:
            areas = request.args.getlist('area_codes')
            if areas:
                filtered_df = filtered_df[filtered_df['area_code'].isin(areas)]
        
        if 'segments' in request.args:
            segments = request.args.getlist('segments')
            if segments:
                filtered_df = filtered_df[filtered_df['business_segment'].isin(segments)]
        
        if 'min_risk' in request.args:
            try:
                min_risk = float(request.args.get('min_risk'))
                filtered_df = filtered_df[filtered_df['calculated_risk_percentage'] >= min_risk]
            except ValueError:
                pass
        
        if 'max_risk' in request.args:
            try:
                max_risk = float(request.args.get('max_risk'))
                filtered_df = filtered_df[filtered_df['calculated_risk_percentage'] <= max_risk]
            except ValueError:
                pass
        
        if 'date' in request.args:
            date_str = request.args.get('date')
            try:
                date_obj = pd.to_datetime(date_str)
                filtered_df = filtered_df[filtered_df['date_recorded'].dt.date == date_obj.date()]
            except:
                pass
        
        if 'month' in request.args:
            month_str = request.args.get('month')
            try:
                filtered_df = filtered_df[
                    filtered_df['date_recorded'].dt.strftime('%Y-%m') == month_str
                ]
            except:
                pass
        
        # Add classification
        filtered_df['prediction_class'] = filtered_df.apply(classify_prediction, axis=1)
        
        # Format date for export
        filtered_df['date_recorded'] = filtered_df['date_recorded'].dt.strftime('%Y-%m-%d')
        
        # Save to CSV
        export_file = 'export_filtered_data.csv'
        filtered_df.to_csv(export_file, index=False)
        
        return jsonify({
            'status': 'success',
            'message': f'Exported {len(filtered_df)} records',
            'file': export_file
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/rules', methods=['GET'])
def get_rules():
    """
    Get current rule weights
    
    Returns: Dictionary of rule names and their weights
    """
    return jsonify({
        'status': 'success',
        'risk_threshold_percentage': RISK_THRESHOLD,
        'rules': RULE_WEIGHTS,
        'total_weight': sum(RULE_WEIGHTS.values())
    })

# ============================================================================
# HTML ROUTES
# ============================================================================

@app.route('/')
def index():
    """Render main dashboard page"""
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
    print("\n" + "="*70)
    print(" FTTH Signal Drop Prediction System - Flask Backend")
    print("="*70)
    print(f"✓ Data loaded: {len(df)} records")
    print(f"✓ Risk threshold: {RISK_THRESHOLD}%")
    print(f"✓ Rules: {len(RULE_WEIGHTS)} rules with weights")
    print(f"✓ Server: http://localhost:5000")
    print("="*70 + "\n")
    
    app.run(debug=True, port=5000, host='0.0.0.0')
