# EcoPlate AI - Smart Food Waste Reduction & Redistribution Ecosystem
**SIH Problem Statement 26234**: AI-Powered Smart Food Waste Reduction and Sustainable Redistribution Ecosystem for Institutional Kitchens and Food Processing Units.

---

## 📌 Project Overview
EcoPlate AI is a web-based prototype designed for institutional cafeterias, hostels, and food processing units to:
1. **Prevent Overproduction Waste**: Intelligent predictive attendance forecasting and dynamic lean batch sizing.
2. **Track & Audit Kitchen Waste**: Daily waste measurement across Plate Waste, Prep Waste, Spoilage, and Buffet Leftovers with real-time financial loss estimation.
3. **Surplus Redistribution Feed**: Real-time listing of excess edible food with safe-consumption window countdowns and tamper-proof 6-digit OTP verification for NGOs.
4. **Institutional ESG Sustainability Ledger**: Auditable metrics for Landfill CO₂e abatement, embedded water savings, and equivalent meals rescued.

---

## 🤖 AI Demand Forecasting Architecture Note
> **Implementation Detail**:  
> The current demand forecasting and waste pattern analytics engine is implemented as a **lightweight, native statistical and predictive model** in `app/services/ai_engine.py` (incorporating weighted multi-factor regression, day-of-week decay curves, and dynamic safety buffers).  
> Because Python 3.14.5 currently lacks pre-compiled Windows binary wheels on PyPI for heavy C-extensions like Scikit-learn/Pandas, this pure-Python implementation ensures the application runs reliably with zero C-compiler dependencies while delivering accurate, real-time predictions.

---

## 🛠️ Technology Stack
- **Frontend**: HTML5, CSS3, Bootstrap 5.3, JavaScript, Chart.js
- **Backend**: Python, Flask
- **Database**: SQLite (SQLAlchemy)
- **Analytics Engine**: Pure-Python Statistical & Predictive Forecasting

---

## 🚀 Getting Started (Windows)

### 1. Prerequisites
- Windows OS with Python 3.x installed

### 2. Startup Command
Run the application using the local virtual environment:

```powershell
.\.venv\Scripts\python.exe run.py
```
*(If your virtual environment is already activated, you can simply run `python run.py`)*

### 3. Open in Browser
Visit:
```text
http://127.0.0.1:5000
```

---

## 👥 Demo Personas for Evaluation (One-Click Login)
The system includes built-in demo personas for seamless hackathon evaluations:
- **Kitchen Manager**: *Apex University Central Mega-Mess* (Full kitchen controls, waste entry, inventory expiry, AI forecasting)
- **NGO Partner**: *Annapurna Food Rescue Foundation* (Marketplace claims, pickup dispatch, OTP verification)

To reset or re-seed sample cafeteria data at any time, run:
```powershell
.\.venv\Scripts\python.exe seed_data.py
```

---

## 🧪 Running Automated Tests
To run the automated test suite verifying all 12 endpoints:
```powershell
.\.venv\Scripts\python.exe test_app.py
```
