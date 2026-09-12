import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import projects, pre_sanction, auth, compliance, trends, early_warning, projected_completion, predictive_completion, comparison, gis, review, dashboard, decision_support, review_cases, reports
from .database import SessionLocal, database_diagnostic
from .official_data import runtime_data_summary

app = FastAPI(title="SIH26102 MPLAD Risk Intelligence API", version="1.0.0")

cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(pre_sanction.router)
app.include_router(compliance.router)
app.include_router(trends.router)
app.include_router(early_warning.router)
app.include_router(projected_completion.router)
app.include_router(predictive_completion.router)
app.include_router(comparison.router)
app.include_router(gis.router)
app.include_router(review.router)
app.include_router(dashboard.router)
app.include_router(decision_support.router)
app.include_router(review_cases.router)
app.include_router(reports.router)

@app.on_event("startup")
def log_runtime_data_source():
    """Safe local diagnostic for operators; no secret-bearing connection string is logged."""
    db = SessionLocal()
    try:
        print(f"MPLAD runtime diagnostic: {database_diagnostic()} {runtime_data_summary(db)}")
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "MPLAD Risk Intelligence API is running"}
