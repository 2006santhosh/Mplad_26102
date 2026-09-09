from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user
from ..risk_engine.predictive_completion import PredictiveCompletionRiskEngine

router = APIRouter(prefix="/api/projects/{project_id}/predictive-completion", tags=["predictive-completion"])

@router.get("", response_model=schemas.PredictiveCompletionResponse)
@router.get("/", response_model=schemas.PredictiveCompletionResponse)
def get_predictive_completion(project_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    assessment = db.query(models.PredictiveCompletionAssessment).filter(
        models.PredictiveCompletionAssessment.project_id == project_id
    ).order_by(models.PredictiveCompletionAssessment.created_at.desc()).first()

    if not assessment:
        return schemas.PredictiveCompletionResponse(
            status="NOT_ASSESSABLE",
            risk_level=None,
            risk_score=None,
            confidence=None,
            coverage_pct=35.0,
            drivers=["No predictive assessment has been explicitly generated for this project yet."],
            evidence={},
            missing_data=["Predictive assessment never run"],
            provenance="AI ASSESSMENT",
            engine_version="7.0.0"
        )

    return schemas.PredictiveCompletionResponse(
        status=assessment.status,
        risk_level=assessment.risk_level,
        risk_score=assessment.risk_score,
        confidence=assessment.confidence,
        coverage_pct=assessment.coverage_pct,
        drivers=assessment.drivers or [],
        evidence=assessment.evidence or {},
        missing_data=assessment.missing_data or [],
        provenance=assessment.provenance,
        engine_version=assessment.engine_version
    )

@router.post("/assess", response_model=schemas.PredictiveCompletionResponse)
def run_predictive_completion(project_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    engine = PredictiveCompletionRiskEngine(db)
    result = engine.assess(project_id)

    db_assessment = models.PredictiveCompletionAssessment(
        project_id=project_id,
        status=result["status"],
        risk_level=result["risk_level"],
        risk_score=result["risk_score"],
        confidence=result["confidence"],
        coverage_pct=result["coverage_pct"],
        drivers=result["drivers"],
        evidence=result["evidence"],
        missing_data=result["missing_data"],
        provenance=result["provenance"],
        engine_version=result["engine_version"]
    )
    db.add(db_assessment)
    db.commit()
    db.refresh(db_assessment)

    return schemas.PredictiveCompletionResponse(
        status=db_assessment.status,
        risk_level=db_assessment.risk_level,
        risk_score=db_assessment.risk_score,
        confidence=db_assessment.confidence,
        coverage_pct=db_assessment.coverage_pct,
        drivers=db_assessment.drivers or [],
        evidence=db_assessment.evidence or {},
        missing_data=db_assessment.missing_data or [],
        provenance=db_assessment.provenance,
        engine_version=db_assessment.engine_version
    )
