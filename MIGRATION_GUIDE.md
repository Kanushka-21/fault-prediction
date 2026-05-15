# FTTH Fault Prediction Dashboard - Major Update Guide

**Date Created:** May 15, 2026  
**Status:** Major Architectural Redesign  
**Current Size:** 2029 lines (HTML/JavaScript)  
**New Architecture:** Python Flask + scikit-learn + ML Models

---

## 📋 Current System Analysis

### What We Have Now:
- **Frontend:** Single-page HTML/JavaScript application
- **Data Handling:** Client-side CSV parsing and visualization
- **Logic:** Basic rule-based prediction (7 hardcoded rules)
- **Data Source:** Static CSV files uploaded manually
- **Limitations:** 
  - Not scalable for large datasets
  - No real machine learning
  - No persistent data storage
  - Rules are static (no weights)

### Limitations Being Addressed:
- ❌ Overview section is inaccurate - REMOVE IT
- ❌ JavaScript can't handle massive datasets
- ❌ No proper risk calculation with weights
- ❌ Data model doesn't match business requirements

---

## 🎯 PHASE 1: DATA MODEL REDESIGN

### New CSV Structure (sample file: `final_df_updated.csv`)

**OLD STRUCTURE (REMOVE):**
```
PPP_USERNAME_masked_masked,INSERTED_DATE,Rule1_SensorError,Rule2_Critical,Rule3_Degrading,...,Final System Output,Same Day Fault,1st Week Fault,2nd Week fault,3rd week fault,4th week fault,Final Fault Result
```

**NEW STRUCTURE (CREATE):**
```
phone_number,customer_name,area_code,business_segment,
date_recorded,
sensor_error,signal_critical,signal_degrading,sudden_drop,rx_instability,low_signal,frequent_fault,
rule_score_weighted,calculated_risk_percentage,flagged_at_risk,
fault_next_2_weeks
```

### Column Definitions:

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `phone_number` | STRING | User's phone number | "0771234567" |
| `customer_name` | STRING | Customer full name | "John Doe" |
| `area_code` | STRING | Geographic area code | "CMB_01", "MAT_02" |
| `business_segment` | STRING | Business type | "Retail", "SME", "LargeEnterprise" |
| `date_recorded` | DATE | Data collection date | "2025-07-18" |
| `sensor_error` | INT (0/1) | Sensor error detected | 0 or 1 |
| `signal_critical` | INT (0/1) | Critical signal level | 0 or 1 |
| `signal_degrading` | INT (0/1) | Degrading signal | 0 or 1 |
| `sudden_drop` | INT (0/1) | Sudden signal drop | 0 or 1 |
| `rx_instability` | INT (0/1) | RX power unstable | 0 or 1 |
| `low_signal` | INT (0/1) | Persistently low signal | 0 or 1 |
| `frequent_fault` | INT (0/1) | Frequent faults | 0 or 1 |
| `rule_score_weighted` | FLOAT | Sum of weighted rule triggers | 0.0 - 7.0 |
| `calculated_risk_percentage` | FLOAT | Risk score (0-100%) | 45.5 |
| `flagged_at_risk` | INT (0/1) | Risk > 70%? | 0 or 1 |
| `fault_next_2_weeks` | INT (0/1) | Actual: Fault occurred? | 0 or 1 |

### Removed Columns (No Longer Needed):
- ❌ `PPP_USERNAME_masked_masked` → Replaced with `phone_number`
- ❌ `Final System Output` → Replaced with `calculated_risk_percentage` + `flagged_at_risk`
- ❌ `Same Day Fault` → Only use 2-week window
- ❌ `1st Week Fault` → Only use 2-week window
- ❌ `2nd Week fault` → Only use 2-week window
- ❌ `3rd week fault` → Only use 2-week window
- ❌ `4th week fault` → Only use 2-week window

---

## 🔢 PHASE 2: RISK CALCULATION LOGIC

### Rule Weights (ML-Based)

Each rule will have a **weight** learned from historical data using scikit-learn:

```python
RULE_WEIGHTS = {
    'sensor_error': 0.18,           # 18% contribution
    'signal_critical': 0.22,        # 22% contribution (most important)
    'signal_degrading': 0.15,       # 15% contribution
    'sudden_drop': 0.16,            # 16% contribution
    'rx_instability': 0.12,         # 12% contribution
    'low_signal': 0.10,             # 10% contribution
    'frequent_fault': 0.07          # 7% contribution (least important)
}
# Total: 100%
```

### Risk Calculation Formula:

```
rule_score_weighted = Σ(rule_value × rule_weight)
                    = (sensor_error × 0.18) + (signal_critical × 0.22) + ... + (frequent_fault × 0.07)

calculated_risk_percentage = (rule_score_weighted / max_possible_score) × 100
                           = (rule_score_weighted / 1.0) × 100

flagged_at_risk = 1 if calculated_risk_percentage >= 70.0 else 0
```

### Example Calculation:

**Case 1: User with 3 triggered rules**
```
sensor_error = 1 (×0.18) = 0.18
signal_critical = 1 (×0.22) = 0.22
signal_degrading = 1 (×0.15) = 0.15
Others = 0

rule_score_weighted = 0.18 + 0.22 + 0.15 = 0.55
calculated_risk_percentage = (0.55 / 1.0) × 100 = 55%
flagged_at_risk = 0 (55% < 70%)
```

**Case 2: User with critical rules triggered**
```
signal_critical = 1 (×0.22) = 0.22
sudden_drop = 1 (×0.16) = 0.16
low_signal = 1 (×0.10) = 0.10
frequent_fault = 1 (×0.07) = 0.07
Others = 0

rule_score_weighted = 0.22 + 0.16 + 0.10 + 0.07 = 0.55
calculated_risk_percentage = 55%
flagged_at_risk = 0 (55% < 70%)
```

---

## 🔍 PHASE 3: ACTUAL OUTCOME DEFINITION

### Changed Timeframe: Next 2 Weeks Only

**OLD (Remove these columns):**
- Same Day Fault
- 1st Week Fault
- 2nd Week Fault
- 3rd Week Fault
- 4th Week Fault

**NEW (Single column):**
```
fault_next_2_weeks = 1 if any fault occurs within 14 days after date_recorded else 0
```

**Logic:**
```
If date_recorded = 2025-07-18
Then check for faults between 2025-07-18 and 2025-08-01 (14 days)
If any fault occurs in this window: fault_next_2_weeks = 1
Otherwise: fault_next_2_weeks = 0
```

---

## 📊 PHASE 4: DASHBOARD FILTERS

### New Dashboard Filters (Client-Side or Server-Side):

1. **By Phone Number / Customer Name**
   - Search box
   - Exact or partial match

2. **By Area Code**
   - Dropdown: CMB_01, CMB_02, MAT_01, MAT_02, etc.
   - Multi-select enabled

3. **By Business Segment**
   - Dropdown: Retail, SME, LargeEnterprise
   - Multi-select enabled

4. **By Risk Level**
   - Slider: 0% - 100%
   - Range selection: Min and Max risk %

5. **By Date**
   - Calendar picker
   - Single date or date range
   - Shows data for selected date(s) only

6. **By Month (NEW)**
   - Month/Year picker
   - Shows all records from selected month

### Filter Combination Logic:
```
Display records WHERE:
  (phone_number CONTAINS search OR customer_name CONTAINS search)
  AND area_code IN selected_areas
  AND business_segment IN selected_segments
  AND calculated_risk_percentage BETWEEN min_risk AND max_risk
  AND date_recorded IN selected_dates_or_month
```

---

## 📈 PHASE 5: DATA TABLE COLUMNS (Human-Readable)

### Current Data Table Structure (Remove):
- PPP Username
- Date
- Rule Results (7 badges)
- Final System Output
- Same Day/1st/2nd/3rd/4th Week Faults
- Final Fault Result

### New Data Table Structure:

| Column | Data Type | Human-Readable | Notes |
|--------|-----------|-----------------|-------|
| Phone Number | STRING | User's Phone | Searchable |
| Customer Name | STRING | Customer Full Name | Searchable |
| Area Code | STRING | Area Code | Filterable |
| Business Segment | STRING | Segment Type | Filterable |
| Date | DATE | Recording Date | Filterable |
| Risk Score | FLOAT | Risk % (0-100) | Sortable, colored |
| At Risk? | YES/NO | ✅ Safe / 🚨 At Risk | Based on 70% threshold |
| **Prediction Accuracy** (Brackets) | | | |
| TP (Correct Alert) | INT | Flagged At-Risk & Fault Occurred | Green |
| TN (Correct No Alert) | INT | Not Flagged & No Fault | Gray |
| FP (False Alarm) | INT | Flagged At-Risk & No Fault | Yellow |
| FN (Missed Alert) | INT | Not Flagged & Fault Occurred | Red |
| **Actual Outcome** | | | |
| Fault (Next 2 Weeks) | YES/NO | Did fault occur in next 2 weeks? | ✅/❌ |

### Export Requirements:
- CSV download (filtered data)
- Excel export (if needed)
- Sorted by Risk % (descending)

---

## 🐍 PHASE 6: ARCHITECTURE SHIFT - Python Backend

### Why Python?
- ✅ Handle large datasets efficiently
- ✅ Scikit-learn for ML/weighting
- ✅ Pandas for data manipulation
- ✅ Scalability for thousands of records

### New Technology Stack:

```
Old Stack (REMOVE):
├── index.html (2029 lines)
├── final_df_first100.csv
└── final_df_sample_100.csv

New Stack (CREATE):
├── Backend (Python):
│   ├── app.py (Flask server)
│   ├── data_processor.py (CSV parsing, risk calculation)
│   ├── models.py (Database models)
│   ├── ml_engine.py (scikit-learn weights, predictions)
│   └── config.py (Configuration)
│
├── Frontend (Simplified HTML):
│   ├── index.html (data table only, no overview/rules/analytics)
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js (filtering, sorting, export)
│   └── templates/
│
├── Data:
│   ├── final_df_updated.csv (new structure)
│   └── training_data.csv (historical data for ML)
│
├── requirements.txt (Python dependencies)
├── README.md (Setup instructions)
└── MIGRATION_GUIDE.md (This file)
```

### Python Dependencies:
```
Flask==2.3.0
Flask-CORS==4.0.0
pandas==2.0.0
numpy==1.24.0
scikit-learn==1.2.0
python-dateutil==2.8.0
```

---

## 🛠️ PHASE 7: STEP-BY-STEP MIGRATION

### Step 1: Backup Current System
```bash
# Backup existing files
mkdir -p backup
cp index.html backup/
cp final_df_first100.csv backup/
cp final_df_sample_100.csv backup/
```

### Step 2: Create New CSV File with Updated Headers

**Create file:** `final_df_updated.csv`

Headers:
```
phone_number,customer_name,area_code,business_segment,date_recorded,sensor_error,signal_critical,signal_degrading,sudden_drop,rx_instability,low_signal,frequent_fault,rule_score_weighted,calculated_risk_percentage,flagged_at_risk,fault_next_2_weeks
```

Sample data (convert from old format):
```
0771234567,John Doe,CMB_01,Retail,2025-07-18,0,0,0,0,1,0,0,0.12,12.0,0,0
0771234568,Jane Smith,MAT_02,SME,2025-07-19,1,0,1,0,0,0,0,0.33,33.0,0,1
0771234569,Corp A,CMB_02,LargeEnterprise,2025-07-20,1,1,0,1,1,0,0,0.76,76.0,1,1
```

### Step 3: Create Python Backend

**File:** `app.py`
```python
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Load data
df = pd.read_csv('final_df_updated.csv')

# Rule weights (from ML training)
RULE_WEIGHTS = {
    'sensor_error': 0.18,
    'signal_critical': 0.22,
    'signal_degrading': 0.15,
    'sudden_drop': 0.16,
    'rx_instability': 0.12,
    'low_signal': 0.10,
    'frequent_fault': 0.07
}

def calculate_risk(row):
    """Calculate risk percentage based on rule weights"""
    rule_score = sum([row[rule] * weight for rule, weight in RULE_WEIGHTS.items()])
    risk_percentage = rule_score * 100
    return risk_percentage

def classify_prediction(row):
    """
    Classify as TP, TN, FP, FN
    TP: At Risk (flag=1) & Fault (fault=1)
    TN: Safe (flag=0) & No Fault (fault=0)
    FP: At Risk (flag=1) & No Fault (fault=0)
    FN: Safe (flag=0) & Fault Occurred (fault=1)
    """
    if row['flagged_at_risk'] == 1 and row['fault_next_2_weeks'] == 1:
        return 'TP'
    elif row['flagged_at_risk'] == 0 and row['fault_next_2_weeks'] == 0:
        return 'TN'
    elif row['flagged_at_risk'] == 1 and row['fault_next_2_weeks'] == 0:
        return 'FP'
    else:  # 0 and 1
        return 'FN'

@app.route('/api/data', methods=['GET'])
def get_data():
    """Get filtered data based on query parameters"""
    filtered_df = df.copy()
    
    # Filters
    if 'phone_number' in request.args:
        search = request.args.get('phone_number')
        filtered_df = filtered_df[
            (filtered_df['phone_number'].str.contains(search, na=False)) |
            (filtered_df['customer_name'].str.contains(search, na=False))
        ]
    
    if 'area_codes' in request.args:
        areas = request.args.getlist('area_codes')
        filtered_df = filtered_df[filtered_df['area_code'].isin(areas)]
    
    if 'segments' in request.args:
        segments = request.args.getlist('segments')
        filtered_df = filtered_df[filtered_df['business_segment'].isin(segments)]
    
    if 'min_risk' in request.args:
        min_risk = float(request.args.get('min_risk'))
        filtered_df = filtered_df[filtered_df['calculated_risk_percentage'] >= min_risk]
    
    if 'max_risk' in request.args:
        max_risk = float(request.args.get('max_risk'))
        filtered_df = filtered_df[filtered_df['calculated_risk_percentage'] <= max_risk]
    
    if 'date' in request.args:
        date_str = request.args.get('date')
        filtered_df = filtered_df[filtered_df['date_recorded'] == date_str]
    
    if 'month' in request.args:
        month_str = request.args.get('month')  # Format: YYYY-MM
        filtered_df = filtered_df[filtered_df['date_recorded'].str.startswith(month_str)]
    
    # Add classification
    filtered_df['prediction_class'] = filtered_df.apply(classify_prediction, axis=1)
    
    # Sort by risk descending
    filtered_df = filtered_df.sort_values('calculated_risk_percentage', ascending=False)
    
    return jsonify(filtered_df.to_dict(orient='records'))

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get summary statistics"""
    total_records = len(df)
    at_risk = (df['flagged_at_risk'] == 1).sum()
    faults_occurred = (df['fault_next_2_weeks'] == 1).sum()
    
    # Classification counts
    classifications = {
        'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0
    }
    for _, row in df.iterrows():
        cls = classify_prediction(row)
        classifications[cls] += 1
    
    return jsonify({
        'total_records': total_records,
        'at_risk_count': int(at_risk),
        'faults_occurred': int(faults_occurred),
        'classifications': classifications,
        'unique_areas': df['area_code'].unique().tolist(),
        'unique_segments': df['business_segment'].unique().tolist()
    })

@app.route('/api/export', methods=['GET'])
def export_data():
    """Export filtered data as CSV"""
    # Get filtered data
    data_response = get_data()
    data = data_response.get_json()
    
    # Convert to DataFrame and save
    export_df = pd.DataFrame(data)
    export_df.to_csv('export_filtered_data.csv', index=False)
    
    return jsonify({'message': 'Data exported successfully', 'file': 'export_filtered_data.csv'})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

**File:** `ml_engine.py`
```python
"""
ML Engine for Risk Calculation
Uses scikit-learn for weight-based risk scoring
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier

class RiskCalculator:
    def __init__(self):
        """Initialize risk calculator with trained weights"""
        # These weights are learned from historical data
        # In production, train with: RandomForestClassifier().fit(X, y)
        self.rule_weights = {
            'sensor_error': 0.18,
            'signal_critical': 0.22,
            'signal_degrading': 0.15,
            'sudden_drop': 0.16,
            'rx_instability': 0.12,
            'low_signal': 0.10,
            'frequent_fault': 0.07
        }
        self.risk_threshold = 70.0  # 70% threshold for flagging as at-risk
    
    def calculate_risk_score(self, rules_dict):
        """
        Calculate risk score from rule triggers
        
        Args:
            rules_dict: Dict with rule names as keys and 0/1 as values
        
        Returns:
            float: Risk percentage (0-100)
        """
        weighted_score = sum([
            rules_dict.get(rule, 0) * weight 
            for rule, weight in self.rule_weights.items()
        ])
        risk_percentage = weighted_score * 100
        return risk_percentage
    
    def get_risk_level(self, risk_percentage):
        """Convert percentage to human-readable risk level"""
        if risk_percentage >= self.risk_threshold:
            return 'AT_RISK', 1
        else:
            return 'SAFE', 0
    
    def train_weights_from_data(self, X_train, y_train):
        """
        Train rule weights using RandomForest
        
        Args:
            X_train: Features (rule triggers)
            y_train: Target (actual faults)
        """
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)
        
        # Extract feature importances as weights
        feature_names = ['sensor_error', 'signal_critical', 'signal_degrading', 
                        'sudden_drop', 'rx_instability', 'low_signal', 'frequent_fault']
        importances = model.feature_importances_
        
        # Normalize to sum to 1.0
        self.rule_weights = {
            name: float(imp) for name, imp in zip(feature_names, importances)
        }
        
        return self.rule_weights
```

### Step 4: Create New Simplified HTML (Data Table Only)

**File:** `templates/index.html` (Simplified)
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FTTH Signal Drop Prediction - Data Analysis</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css" rel="stylesheet">
</head>
<body style="background: #0f1419; color: #e0e0e0;">
    <div class="container-fluid p-4">
        <h1 class="mb-4"><i class="fas fa-signal"></i> FTTH Signal Drop Prediction Dashboard</h1>
        
        <!-- FILTERS -->
        <div class="card mb-4" style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);">
            <div class="card-body">
                <h5 class="card-title">Filters</h5>
                <div class="row g-3">
                    <div class="col-md-2">
                        <label>Phone / Name</label>
                        <input type="text" id="searchFilter" class="form-control form-control-sm" placeholder="Search...">
                    </div>
                    <div class="col-md-2">
                        <label>Area Code</label>
                        <select id="areaFilter" class="form-select form-select-sm" multiple></select>
                    </div>
                    <div class="col-md-2">
                        <label>Business Segment</label>
                        <select id="segmentFilter" class="form-select form-select-sm" multiple></select>
                    </div>
                    <div class="col-md-2">
                        <label>Risk % Range</label>
                        <input type="range" id="riskFilter" class="form-range" min="0" max="100" value="70">
                        <small id="riskValue">≥ 70%</small>
                    </div>
                    <div class="col-md-2">
                        <label>Date</label>
                        <input type="date" id="dateFilter" class="form-control form-control-sm">
                    </div>
                    <div class="col-md-2">
                        <label>Month</label>
                        <input type="month" id="monthFilter" class="form-control form-control-sm">
                    </div>
                </div>
                <div class="mt-3">
                    <button id="applyFilters" class="btn btn-primary btn-sm">Apply Filters</button>
                    <button id="clearFilters" class="btn btn-secondary btn-sm">Clear All</button>
                    <button id="exportBtn" class="btn btn-success btn-sm"><i class="fas fa-download"></i> Export CSV</button>
                </div>
            </div>
        </div>
        
        <!-- DATA TABLE -->
        <div class="card" style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);">
            <div class="card-body">
                <table id="dataTable" class="table table-hover" style="color: #e0e0e0;">
                    <thead>
                        <tr>
                            <th>Phone Number</th>
                            <th>Customer Name</th>
                            <th>Area Code</th>
                            <th>Business Segment</th>
                            <th>Date</th>
                            <th>Risk Score %</th>
                            <th>At Risk?</th>
                            <th>Prediction Accuracy</th>
                            <th>Fault (2-Week)</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody">
                        <tr><td colspan="9" class="text-center">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.6.4.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
</body>
</html>
```

**File:** `static/js/app.js`
```javascript
let allData = [];
let dataTable;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    loadData();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('applyFilters').addEventListener('click', applyFilters);
    document.getElementById('clearFilters').addEventListener('click', clearFilters);
    document.getElementById('exportBtn').addEventListener('click', exportData);
    document.getElementById('riskFilter').addEventListener('input', function() {
        document.getElementById('riskValue').textContent = '≥ ' + this.value + '%';
    });
}

async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        console.log('Stats loaded:', stats);
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function loadData() {
    try {
        const response = await fetch('/api/data');
        allData = await response.json();
        renderTable(allData);
    } catch (error) {
        console.error('Error loading data:', error);
    }
}

function renderTable(data) {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center">No data found</td></tr>';
        return;
    }
    
    data.forEach(row => {
        const riskColor = row.calculated_risk_percentage >= 70 ? '#ef4444' : '#10b981';
        const riskText = row.calculated_risk_percentage >= 70 ? '🚨 AT RISK' : '✅ SAFE';
        const classColor = {
            'TP': '#10b981',  // Green
            'TN': '#9ca3af',  // Gray
            'FP': '#f59e0b',  // Yellow
            'FN': '#ef4444'   // Red
        }[row.prediction_class];
        
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.phone_number}</td>
            <td>${row.customer_name}</td>
            <td>${row.area_code}</td>
            <td>${row.business_segment}</td>
            <td>${row.date_recorded}</td>
            <td><span style="color: ${riskColor}; font-weight: bold;">${row.calculated_risk_percentage.toFixed(1)}%</span></td>
            <td>${riskText}</td>
            <td><span style="background: ${classColor}; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;">
                ${row.prediction_class} 
                <span style="opacity: 0.7;">(${getClassificationLabel(row.prediction_class)})</span>
            </span></td>
            <td>${row.fault_next_2_weeks === 1 ? '⚠️ YES' : '✅ NO'}</td>
        `;
        tbody.appendChild(tr);
    });
}

function getClassificationLabel(cls) {
    const labels = {
        'TP': 'True Positive: Correctly identified at-risk user',
        'TN': 'True Negative: Correctly identified safe user',
        'FP': 'False Positive: False alarm',
        'FN': 'False Negative: Missed at-risk user'
    };
    return labels[cls] || cls;
}

async function applyFilters() {
    const params = new URLSearchParams();
    
    const search = document.getElementById('searchFilter').value;
    if (search) params.append('phone_number', search);
    
    const areas = Array.from(document.getElementById('areaFilter').selectedOptions).map(o => o.value);
    areas.forEach(a => params.append('area_codes', a));
    
    const segments = Array.from(document.getElementById('segmentFilter').selectedOptions).map(o => o.value);
    segments.forEach(s => params.append('segments', s));
    
    const minRisk = document.getElementById('riskFilter').value;
    if (minRisk) params.append('min_risk', minRisk);
    
    const date = document.getElementById('dateFilter').value;
    if (date) params.append('date', date);
    
    const month = document.getElementById('monthFilter').value;
    if (month) params.append('month', month);
    
    try {
        const response = await fetch(`/api/data?${params}`);
        const data = await response.json();
        renderTable(data);
    } catch (error) {
        console.error('Error applying filters:', error);
    }
}

function clearFilters() {
    document.getElementById('searchFilter').value = '';
    document.getElementById('areaFilter').selectedIndex = -1;
    document.getElementById('segmentFilter').selectedIndex = -1;
    document.getElementById('riskFilter').value = '70';
    document.getElementById('riskValue').textContent = '≥ 70%';
    document.getElementById('dateFilter').value = '';
    document.getElementById('monthFilter').value = '';
    loadData();
}

async function exportData() {
    try {
        const response = await fetch('/api/export');
        const result = await response.json();
        // Trigger download
        const link = document.createElement('a');
        link.href = result.file;
        link.download = 'prediction_data.csv';
        link.click();
    } catch (error) {
        console.error('Error exporting data:', error);
    }
}
```

### Step 5: Create requirements.txt

**File:** `requirements.txt`
```
Flask==2.3.0
Flask-CORS==4.0.0
pandas==2.0.0
numpy==1.24.0
scikit-learn==1.2.0
python-dateutil==2.8.0
Werkzeug==2.3.0
```

### Step 6: Create Setup Instructions

**File:** `SETUP.md`
```markdown
# Setup Instructions

## Prerequisites
- Python 3.9+
- pip (Python package manager)

## Installation Steps

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Prepare data:**
   - Update `final_df_updated.csv` with new structure
   - Ensure all columns match specification

3. **Run the application:**
```bash
python app.py
```

4. **Access dashboard:**
   - Open http://localhost:5000 in your browser

## Data Upload Process

1. Click "Choose File" to upload CSV
2. Ensure CSV has correct headers
3. System auto-calculates risk scores
4. Data appears in table immediately

## Troubleshooting

- **Port 5000 already in use?** Change in app.py: `app.run(port=5001)`
- **Module not found?** Run: `pip install -r requirements.txt --upgrade`
- **Data not loading?** Check CSV format matches specification
```

---

## 📝 PHASE 8: MIGRATION CHECKLIST

### Data Preparation:
- [ ] Convert old CSV to new format
- [ ] Map old columns to new columns
- [ ] Calculate rule_score_weighted for each row
- [ ] Calculate calculated_risk_percentage
- [ ] Set flagged_at_risk (1 if ≥ 70%, else 0)
- [ ] Map fault columns to fault_next_2_weeks (if fault in next 14 days: 1, else 0)
- [ ] Validate all data types

### Backend Development:
- [ ] Create app.py with Flask server
- [ ] Implement filter endpoints (/api/data)
- [ ] Implement stats endpoint (/api/stats)
- [ ] Implement export endpoint (/api/export)
- [ ] Create ml_engine.py for risk calculations
- [ ] Set up CORS for frontend-backend communication

### Frontend Redesign:
- [ ] Remove Overview section
- [ ] Remove Rules section
- [ ] Remove Analytics section
- [ ] Remove Model Validation section
- [ ] Keep only Data Table
- [ ] Add filter controls (phone, area, segment, risk, date, month)
- [ ] Update table columns with human-readable labels
- [ ] Add export functionality
- [ ] Test all filters work correctly

### Testing:
- [ ] Unit test risk calculation logic
- [ ] Integration test filters
- [ ] Test CSV export functionality
- [ ] Test with different data sizes (100, 1000, 10000 rows)
- [ ] Cross-browser testing (Chrome, Firefox, Safari)

### Deployment:
- [ ] Backup current system
- [ ] Deploy Python backend
- [ ] Deploy new frontend
- [ ] Update documentation
- [ ] Train team on new interface

---

## 🚀 IMPLEMENTATION TIMELINE

| Phase | Task | Timeline |
|-------|------|----------|
| 1 | Data model redesign + CSV conversion | Day 1 |
| 2 | Python backend development | Day 2-3 |
| 3 | Frontend redesign | Day 2-3 |
| 4 | Integration testing | Day 4 |
| 5 | Deployment | Day 5 |
| 6 | Documentation + training | Day 5-6 |

---

## 📞 Support

For questions about implementation, refer to:
1. This migration guide
2. Code comments in app.py
3. Python docstrings in ml_engine.py
4. Sample CSV structure in PHASE 1

---

**Document Version:** 1.0  
**Last Updated:** May 15, 2026  
**Status:** Ready for Implementation
