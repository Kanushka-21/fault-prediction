# FTTH Fault Prediction System - Quick Start (5 Minutes)

## ⚡ Get Running in 5 Steps

### Step 1: Install Python Dependencies (1 min)
```bash
pip install -r requirements.txt
```

### Step 2: Start the Server (1 min)
```bash
python app.py
```

You should see:
```
✓ Data loaded: 20 records
✓ Server: http://localhost:5000
```

### Step 3: Open Dashboard (1 min)
Visit: **http://localhost:5000**

### Step 4: Explore Data (2 min)

**View Statistics:**
- See top cards showing total records, at-risk count, accuracy
- Statistics auto-load from 20 sample records

**Apply Filters:**
- Search by phone: "077" → shows all matching records
- Filter by risk: Set to 70% → shows at-risk customers only
- Filter by area: Select "CMB_01" → shows that area only
- Combined: Risk=70%, Area=CMB_01, Segment=Retail

**Export Results:**
- Click "Export CSV" → Downloads filtered data

### Step 5: Update Your Data (optional)

Replace `final_df_updated.csv` with your data:
```
phone_number,customer_name,area_code,business_segment,date_recorded,sensor_error,signal_critical,signal_degrading,sudden_drop,rx_instability,low_signal,frequent_fault,rule_score_weighted,calculated_risk_percentage,flagged_at_risk,fault_next_2_weeks
0771234567,John Doe,CMB_01,Retail,2025-07-18,0,0,0,0,1,0,0,0.12,12.0,0,0
0771234568,Jane Smith,MAT_02,SME,2025-07-19,1,0,1,0,0,0,0,0.33,33.0,0,1
```

Restart server and refresh browser.

---

## 🎯 What You Can Do

### Filter Customers
- By phone number or name (partial match)
- By geographic area
- By business segment (Retail, SME, LargeEnterprise)
- By risk level (0-100%)
- By specific date
- By month
- **Combine multiple filters**

### View Risk Metrics
- Risk Score (%): 0-100% probability of fault
- At Risk?: YES if ≥70%, NO if <70%
- Classification: TP/TN/FP/FN (prediction accuracy)
- Fault Occurred?: Did fault happen in next 2 weeks?

### Export Results
- Download filtered data as CSV
- Use in reports, emails, or further analysis

---

## 📊 Understanding Your Data

### Risk Score Calculation
```
risk_score = (sensor_error × 0.18 + signal_critical × 0.22 + ...) × 100

If risk_score >= 70% → Customer flagged as AT RISK
If risk_score < 70% → Customer marked as SAFE
```

### What Each Column Means

| Column | Meaning | Example |
|--------|---------|---------|
| Risk Score (%) | Probability of fault in 2 weeks | 85% = Very likely |
| At Risk? | Exceeds 70% threshold? | YES = needs attention |
| TP (True Positive) | Correctly flagged at-risk | Good! |
| FP (False Positive) | Unnecessary alert | Wasted resources |
| FN (False Negative) | Missed at-risk customer | Customer affected |
| TN (True Negative) | Correctly marked safe | Good! |

---

## 🔧 Common Tasks

### Task 1: Find All At-Risk Retail Customers in CMB_01
1. Set Risk Level: 70%
2. Select Area Code: CMB_01
3. Select Segment: Retail
4. Click "Apply Filters"

### Task 2: Check Predictions for July 2025
1. Set Month: 2025-07
2. Click "Apply Filters"
3. Review results

### Task 3: Export For Analysis
1. Apply desired filters
2. Click "Export CSV"
3. Open in Excel or Python

---

## 🆘 Troubleshooting

### Error: Port 5000 Already in Use
Edit `app.py` line 3 (bottom):
```python
if __name__ == '__main__':
    app.run(debug=True, port=5001)  # Change 5000 to 5001
```
Then: `python app.py`

### Error: Module Not Found
```bash
pip install -r requirements.txt --upgrade
```

### Dashboard Shows No Data
1. Check `final_df_updated.csv` exists
2. Verify CSV has correct columns (16 total)
3. Check Flask console for error messages
4. Restart Flask: `python app.py`

### Table Not Updating After Filters
1. Press F12 (open developer console)
2. Check for error messages
3. Try refreshing page
4. Clear browser cache (Ctrl+Shift+Delete)

---

## 📞 Need Help?

**Full Documentation:**
- README.md - Complete system documentation
- MIGRATION_GUIDE.md - Detailed implementation guide
- IMPLEMENTATION_GUIDE.md - Step-by-step setup instructions

**API Reference:**
- GET /api/stats - Get statistics
- GET /api/data - Get filtered data
- GET /api/export - Export CSV
- GET /api/rules - Get rule weights

---

## ✅ You're Ready!

- ✓ System installed
- ✓ Server running
- ✓ Dashboard open
- ✓ Data loaded
- ✓ Filters working

**Go analyze some customer risk data! 🚀**

---

*Last Updated: May 15, 2025*
