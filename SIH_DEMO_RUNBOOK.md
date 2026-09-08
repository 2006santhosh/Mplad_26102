# SIH26102 Demo Runbook

## Core Principle
> **AI FLAGS. OFFICIALS DECIDE.**

This runbook describes the exact sequence for presenting the MPLAD Risk Intelligence platform during the SIH26102 demonstration.

---

## 1. Demo Startup Procedure

### Prerequisites
- Node.js installed
- Python 3.10+ installed
- SQLite included by default

### Start Backend
```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Configure Environment
cp ../.env.example ../.env
# (Ensure JWT_SECRET_KEY is set in .env before proceeding)

# Initialize and seed official government MPLADS data (543 MPs + 2,462 works)
python scripts/seed_official_data.py

# Start the API
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Start Frontend
```powershell
cd frontend
npm install
npm run dev
```

### Demo Login
Open the application at `http://localhost:5173`.
Use the following demo credentials (test-only, not for production):
- **Username:** `admin_demo`
- **Password:** `demo123`

---

## 2. Recommended Demo Sequence

The demo should tell a coherent story highlighting the platform's decision-support capabilities. Avoid claiming that the AI detects "confirmed fraud." The AI provides *risk intelligence*, and humans make the decisions.

### A. Dashboard
- Show the overall project risk, delayed projects, and risk distribution.
- Explain that the dashboard prioritizes projects requiring human attention.

### B. Select an Anomalous Project
- Choose a scenario (e.g., Scenario B: Expenditure/Progress Mismatch).
- Show the project details, sanctioned amount, expenditure, physical progress, and the overall AI risk score.

### C. Explain the Risk (Explainability)
- Show the individual risk indicators (e.g., financial anomaly, delay, duplicate works).
- Wording to use: *"This pattern is flagged for official review."*

### D. History and Trends
- Show the risk history and timeline trends.
- Explain how the system tracks if a project's risk is deteriorating or improving over time.

### E. Early Warning & Projected Completion
- Show the early warning signals (e.g., stagnation, high burn rate).
- Explain the projected completion model based on historical progress velocity.

### F. Comparison & GIS
- Show peer comparison (highlighting statistical outliers, not fraud).
- Show the GIS map (spatial concentration as an analytical signal).

### G. Compliance
- Show the compliance panel (financial discipline, completion consistency).

### H. Human Review Workflow
- Demonstrate a reviewer action (`COMMENT`, `FLAG`).
- Explain: *"AI produces risk intelligence; authorized officials make the final decision."* Show that AI signals do not automatically change official project statuses.

---

## 3. SIH Demo Checklist

### Before Demo
- [ ] Backend environment ready
- [ ] Frontend dependencies ready
- [ ] Database ready
- [ ] Deterministic demo data loaded
- [ ] Demo login verified
- [ ] Backend starts
- [ ] Frontend starts
- [ ] Browser opens
- [ ] Main dashboard loads

### During Demo
- [ ] Dashboard
- [ ] Risk
- [ ] Explainability
- [ ] History/trends
- [ ] Early warning
- [ ] Projected completion
- [ ] Comparison
- [ ] Compliance
- [ ] GIS
- [ ] Human review

### Final Message
> **"AI FLAGS. OFFICIALS DECIDE."**

---

## 4. Limitations & Disclaimers
- **Synthetic Data:** The demo uses strictly synthetic records to demonstrate anomaly scenarios. This is not real official government data.
- **Decision Support:** Risk scores are analytical outputs and anomaly indicators, not fraud verdicts.
- **Production Readiness:** The current deployment is a functional prototype. Production deployment would require authoritative data sources, migration to PostgreSQL, and security hardening (e.g., robust JWT secrets management).
