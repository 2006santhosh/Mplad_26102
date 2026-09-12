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
The authoritative runtime database is `backend/mplad.db` unless `DATABASE_URL` is explicitly configured. Seed it from the bundled official data before starting the API:
```bash
python scripts/seed_official_data.py
```

2. Start the Frontend UI:
```bash
cd frontend
npm install
npm run dev
```

## Official data and provenance

The primary flow uses the bundled MoSPI MP allocation export (543 MPs) and eSAKSHI work export (2,462 works). `OFFICIAL` fields are source values; the work-stage progress proxy is `DERIVED`; missing source fields such as GPS, contractor, payment history, and planned completion remain `UNAVAILABLE`/null. Synthetic fixtures are test-only and are excluded by backend provenance guards.

## Demo Flow
We recommend the following sequential flow for a demonstration:
1. Login to the application.
2. Open the **Dashboard** to review official portfolio metrics and their data limitations.
3. Open an official eSAKSHI work and inspect provenance-labelled analytical signals.
4. Demonstrate the human review workflow by logging an official `COMMENT` or `FLAG` action.
