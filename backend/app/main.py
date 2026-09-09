from fastapi import FastAPI
from . import models
from .database import engine
from fastapi.middleware.cors import CORSMiddleware
from .routers import projects, pre_sanction, auth, compliance, trends, early_warning, projected_completion, predictive_completion, comparison, gis, review, dashboard, decision_support

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="SIH26102 MPLAD Risk Intelligence API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For demo purposes
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

@app.get("/")
def read_root():
    return {"message": "MPLAD Risk Intelligence API is running"}
