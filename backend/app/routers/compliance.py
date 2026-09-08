"""
Phase 4 — Compliance Intelligence Router

POST /api/projects/{project_id}/compliance/assess
    Explicitly runs the compliance engine and persists the assessment.

GET  /api/projects/{project_id}/compliance/
    Retrieves the latest persisted compliance assessment.
    Does NOT create a new assessment on every GET.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user, RoleChecker
from ..compliance_engine.aggregator import ComplianceAggregator

router = APIRouter(prefix="/api/projects/{project_id}/compliance", tags=["compliance"])


def _build_project_context(p: models.Project, db: Session) -> dict:
    """Build a flat project dictionary for the compliance engine."""
    prog = db.query(models.ProjectProgress).filter(
        models.ProjectProgress.project_id == p.id
    ).order_by(models.ProjectProgress.reported_at.desc()).first()
    fin = db.query(models.ProjectFinancials).filter(
        models.ProjectFinancials.project_id == p.id
    ).order_by(models.ProjectFinancials.updated_at.desc()).first()
    pcs = db.query(models.ProjectContractor).filter(
        models.ProjectContractor.project_id == p.id
    ).all()

    return {
        "id": p.id,
        "work_id": p.work_id,
        "mp_id": p.mp_id,
        "mp_name": p.mp.name if p.mp else None,
        "state": p.mp.state if p.mp else None,
        "district": p.district,
        "constituency": p.constituency,
        "category": p.category,
        "work_category": p.work_category,
        "description": p.description,
        "sanctioned_amount": float(p.sanctioned_amount) if p.sanctioned_amount is not None else None,
        "expenditure": float(fin.expenditure) if fin and fin.expenditure is not None else None,
        "work_stage": p.work_stage,
        "planned_start": p.planned_start,
        "planned_completion": p.planned_completion,
        "actual_completion": p.actual_completion,
        "status": p.status,
        "latitude": p.latitude,
        "longitude": p.longitude,
        "progress_pct": prog.percentage if prog else None,
        "contractors": [pc.contractor_id for pc in pcs],
        "source_type": p.data_source.source_type if p.data_source else None,
    }


def _persist_assessment(db: Session, project_id: int, result: dict) -> models.ComplianceAssessment:
    """Persist a compliance assessment and its checks to the database."""
    ca = models.ComplianceAssessment(
        project_id=project_id,
        overall_status=result["overall_status"],
        coverage_percentage=result["coverage_percentage"],
        pass_count=result["pass_count"],
        review_count=result["review_count"],
        not_assessable_count=result["not_assessable_count"],
        fail_count=result["fail_count"],
        engine_version=result["engine_version"],
    )
    db.add(ca)
    db.commit()
    db.refresh(ca)

    for chk in result["checks"]:
        cc = models.ComplianceCheck(
            assessment_id=ca.id,
            check_id=chk["check_id"],
            check_name=chk["check_name"],
            status=chk["status"],
            severity=chk["severity"],
            explanation=chk.get("explanation"),
            evidence=chk.get("evidence"),
            provenance=chk.get("provenance", "UNAVAILABLE"),
            rule_type=chk["rule_type"],
            required_fields=chk.get("required_fields"),
            available_fields=chk.get("available_fields"),
        )
        db.add(cc)
    db.commit()
    return ca


def _format_response(project_id: int, ca: models.ComplianceAssessment,
                      db: Session) -> schemas.ComplianceAssessmentResponse:
    """Convert a persisted ComplianceAssessment into the API response."""
    checks_db = db.query(models.ComplianceCheck).filter(
        models.ComplianceCheck.assessment_id == ca.id
    ).all()
    return schemas.ComplianceAssessmentResponse(
        project_id=project_id,
        overall_status=ca.overall_status,
        coverage_percentage=ca.coverage_percentage,
        pass_count=ca.pass_count,
        review_count=ca.review_count,
        not_assessable_count=ca.not_assessable_count,
        fail_count=ca.fail_count,
        total_checks=ca.pass_count + ca.review_count + ca.not_assessable_count + ca.fail_count,
        checks=[schemas.ComplianceCheckSchema(
            check_id=c.check_id,
            check_name=c.check_name,
            status=c.status,
            severity=c.severity,
            explanation=c.explanation or "",
            evidence=c.evidence or {},
            provenance=c.provenance,
            required_fields=c.required_fields or [],
            available_fields=c.available_fields or [],
            rule_type=c.rule_type,
        ) for c in checks_db],
        engine_version=ca.engine_version,
    )


@router.post("/assess", response_model=schemas.ComplianceAssessmentResponse)
def assess_compliance(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(RoleChecker(["Admin", "Auditor", "State", "District"]))
):
    """Explicitly run the compliance engine and persist a new assessment."""
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    context = _build_project_context(p, db)
    aggregator = ComplianceAggregator()
    result = aggregator.assess(context)

    ca = _persist_assessment(db, project_id, result)
    return _format_response(project_id, ca, db)


@router.get("/", response_model=schemas.ComplianceAssessmentResponse)
@router.get("", response_model=schemas.ComplianceAssessmentResponse)
def get_compliance(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Retrieve the latest persisted compliance assessment.
    Does NOT create a new assessment — use POST /assess for that."""
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    ca = db.query(models.ComplianceAssessment).filter(
        models.ComplianceAssessment.project_id == project_id
    ).order_by(models.ComplianceAssessment.assessed_at.desc()).first()

    if not ca:
        # No persisted assessment; run one on-the-fly but DO persist it
        # so that subsequent GETs and dashboard aggregation work.
        context = _build_project_context(p, db)
        aggregator = ComplianceAggregator()
        result = aggregator.assess(context)
        ca = _persist_assessment(db, project_id, result)

    return _format_response(project_id, ca, db)
