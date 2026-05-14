# FTTH Fault Prediction Dashboard

A comprehensive, single-file web application for monitoring and predicting fiber optic network faults in FTTH (Fiber To The Home) infrastructure. Built with vanilla JavaScript, Bootstrap 5, and Chart.js.

## Features

### 📊 Dashboard Overview
- **Real-time KPI Cards**: Display total records, predicted faults, critical/marginal/good power levels, and active rules
- **Fault Prediction Trend**: Full-width line chart showing RX Power trends and fault detection over time
- **Power Distribution**: Doughnut chart showing percentage breakdown of signal strength levels
- **Weekly Fault Analysis**: Bar chart displaying fault count by week
- **Frequency Analysis**: Horizontal bar chart showing most affected categories

### 🔧 Rule Engine
- **4 Default Rules** (Always Enabled):
  1. **RX Power Outside Physical Valid Range**: Detects power levels outside transceiver limits (<-37 or >3 dBm)
  2. **Critical Power Threshold**: Triggers when RX Power drops to critical level (≤-32 dBm)
  3. **Continuous Daily Drop (5+ Days)**: Detects sustained power degradation trends
  4. **Single Day Drop > 3 dBm**: Identifies sudden power drops

- **Custom Rules** (Create up to 15):
  - Add, enable/disable, and delete custom rules
  - Customizable rule names and conditions
  - Real-time evaluation against all data

### 📅 Date Range Filtering
- **Interactive Date Slider**: Filter data by selecting a date range
- **Dynamic Updates**: All charts, tables, and KPIs automatically update based on selected date range
- **Date Display**: Shows start and end dates of current filter
- **Full Data Reset**: Slider automatically resets when new data is uploaded

### 📤 Data Management
- **CSV Upload**: Upload your FTTH network data with Date and RX Power columns
- **Sample Data**: Automatic sample data generation (100 records) for demo purposes
- **Data Table**: 
  - Search, sort, and filter functionality
  - CSV export capability
  - Pagination support
  - Shows all rule evaluation results per record
- **Clear Data**: Reset dashboard and upload new files

### 📋 Analytics Page
- **Summary Statistics**: 
  - Total records analyzed
  - Fault count and fault rate
  - Power level distribution (Critical, Marginal, Good)
  - Active rules count

### 🎨 Design
- **Dark Minimal Color Scheme**: Professional glassmorphism UI with dark background (#0f1419)
- **Responsive Layout**: Works on desktop, tablet, and mobile devices
- **Real-time Updates**: All visualizations update instantly as you interact with the dashboard
- **Accessibility**: Font Awesome icons and clear visual hierarchy

## Getting Started

### Requirements
- Modern web browser (Chrome, Firefox, Safari, Edge)
- No installation or dependencies required
- Works entirely in the browser

### Usage
1. Open `index.html` in your web browser
2. Dashboard loads with sample data automatically
3. **To use your own data**:
   - Click the cloud upload icon in the top-right
   - Select a CSV file with "Date" and "RX Power" columns
   - Data will be processed and dashboard will update instantly
4. **To filter by date**:
   - Use the date range slider in the topbar
   - Drag to select start date
   - All results update in real-time
5. **To manage rules**:
   - Navigate to "Rules Engine" section
   - View default rules (always active)
   - Create custom rules (up to 15)
   - Toggle rules on/off to see impact on predictions

## CSV Data Format

Your CSV file should contain at minimum these columns (case-insensitive):

```
Date,RX Power
2024-01-01,-20.5
2024-01-02,-21.3
2024-01-03,-22.1
...
```

## Technical Stack

- **Frontend Framework**: Vanilla JavaScript (No dependencies)
- **UI Framework**: Bootstrap 5.3.0 (CDN)
- **Charting**: Chart.js 4.4.0 (CDN)
- **Data Tables**: DataTables 1.13.6 (CDN)
- **Icons**: Font Awesome 6.4.0 (CDN)
- **Architecture**: Single HTML file with embedded CSS and JavaScript

## File Structure

```
fault-prediction/
├── index.html          # Complete dashboard application (all features in one file)
├── initial.csv         # Sample CSV file for testing
└── README.md           # This file
```

## Key Functions

| Function | Purpose |
|----------|---------|
| `parseCSV()` | Reads and parses uploaded CSV files |
| `evaluateRules()` | Evaluates all enabled rules against data |
| `processData()` | Main orchestrator for data processing and updates |
| `initializeDateRangeSlider()` | Sets up date filtering functionality |
| `updateKPIs()`, `updateCharts()`, `updateDataTable()` | Real-time UI updates |
| `calculateFinalFault()` | Determines final fault status based on rules |
| `getPowerStatus()` | Classifies RX Power into status levels |

## Power Status Classification

- **Critical** (Red): RX Power ≤ -32 dBm
- **Marginal** (Orange): -32 dBm < RX Power < -27 dBm
- **Good** (Green): -8 dBm to 0 dBm
- **Fair** (Gray): All other values

## Features Highlights

✅ Single-file deployment (no build process)
✅ Real-time data processing and visualization
✅ Advanced rule engine with custom rule creation
✅ Date range filtering with dynamic updates
✅ Export data to CSV
✅ Responsive design
✅ Dark mode optimized interface
✅ Sample data for immediate testing
✅ Professional telecommunications UI/UX

## License

This project is provided as-is for network monitoring and fault prediction purposes.