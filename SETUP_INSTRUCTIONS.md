# MPLAD Risk Intelligence System - Setup Instructions

Welcome to the MPLAD Risk Intelligence System. Follow these steps to set up and run the project on a fresh Windows machine.

### Prerequisites
* **Node.js** installed
* **Python 3.10+** installed

---

## 1. Setup the Backend API

Open a terminal inside the `backend` folder and run the following commands in order:

```powershell
# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate

# Install the required dependencies
pip install -r requirements.txt

# Configure the environment variables
Copy-Item ../.env.example ../.env

# Seed the database with official government MPLADS data (543 MPs + 2,462 eSAKSHI works)
python scripts/seed_official_data.py

# Start the Backend Server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
*(Leave this terminal window open and running!)*

---

## 2. Setup the Frontend Interface

Open a **second** terminal inside the `frontend` folder and run:

```powershell
# Install node modules
npm install

# Start the frontend development server
npm run dev
```
*(Leave this terminal window open and running!)*

---

## 3. Access the Application

Once both the backend and frontend servers are running:
1. Open your browser and go to `http://localhost:5173`
2. Log in using the seeded demo credentials:
   * **Username:** `admin_demo`
   * **Password:** `demo123`

Enjoy exploring the MPLAD Risk Intelligence System!
