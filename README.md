# MPLAD Risk Intelligence Platform
**Problem Statement:** SIH26102

This is a functional prototype of a project monitoring and early-warning platform for the MPLAD Scheme. It uses an explainable risk engine to help authorized officials identify projects requiring closer attention.

## Architecture
- **Frontend**: React (Vite) + Tailwind CSS + Leaflet (Map)
- **Backend**: FastAPI (Python)
- **Database**: SQLite (converted from PostgreSQL for easy local demo running) + SQLAlchemy ORM

## Core Philosophy
**"AI FLAGS. OFFICIALS DECIDE."**
This system does not predict fraud. It detects anomalous behaviors, validates rules, and flags projects with transparent reasoning.

## How to Run
1. Start the Backend API:
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
*(The SQLite database `mplad.db` can be safely seeded with 6 synthetic demo scenarios using `backend/scripts/seed_synthetic_data.py`)*

2. Start the Frontend UI:
```bash
cd frontend
npm install
npm run dev
```

## Demo Dataset
The system uses **Synthetic Demo Data** for demonstration purposes. This dataset is strictly labeled, completely synthetic, and **does not represent official government project data, fraud cases, or real MP allocations.** The coordinates provided are explicitly synthetic for demonstration of GIS capabilities.

The demo includes 6 distinct scenarios:
- **Scenario A (Healthy)**: Normal expenditure/progress and no major anomaly. (LOW RISK)
- **Scenario B (Mismatch)**: High expenditure with substantially lower physical progress. (PAYMENT MISMATCH)
- **Scenario C (Delayed)**: Incomplete project with overdue/deteriorating timeline. (DELAY/STAGNATING)
- **Scenario D (Similar)**: Two deliberately similar projects testing the Duplicate Detector. (POTENTIAL DUPLICATE)
- **Scenario E (Vendor Concentration)**: Multiple projects associated with the same vendor to trigger concentration rules. (VENDOR RISK)
- **Scenario F (Invalid Data)**: Explicitly invalid progress value (105%) to demonstrate data-quality handling without crashing.

## Demo Flow
We recommend the following sequential flow for a demonstration:
1. Login to the application.
2. Open the **Dashboard** and show the AI risk overview metrics.
3. Open **Scenario A (Healthy)** to show a baseline normal project.
4. Open **Scenario B (Mismatch)** and show the risk explanation and AI Risk Signal.
5. Show **Trend Analytics** and **Early Warning** for the stagnant project (Scenario C).
6. View the **Projected Completion** model's predictions.
7. Open **Scenario D (Similar)** to show the duplicate detector's "potentially similar project" warning.
8. View the map (GIS) to show the vendor concentration clustering for **Scenario E**.
9. Demonstrate the human review workflow by logging an official `COMMENT` or `FLAG` action.
10. Show the Review History log.
