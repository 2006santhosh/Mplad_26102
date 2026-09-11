from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from .. import schemas, models
from .projects import _get_project_context
from ..risk_engine.aggregator import RiskAggregator
from datetime import date, timedelta
from ..auth_utils import get_current_user

router = APIRouter(prefix="/api/pre-sanction", tags=["pre-sanction"])

@router.post("/", response_model=schemas.RiskAssessmentResponse)
def analyze_pre_sanction(req: schemas.PreSanctionRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    context = _get_project_context(db)
    
    # We construct a hypothetical target
    target = {
        'id': -1, # Does not exist
        'category': req.category,
        'sanctioned_amount': req.sanctioned_amount,
        'location': req.location,
        'progress_pct': 0, # Not started
        'expenditure': 0.0,
        'planned_completion': date.today() + timedelta(days=req.planned_duration_days),
        'actual_completion': None,
        'status': 'PROPOSED',
        'contractors': [req.contractor_id] if req.contractor_id else []
    }
    
    agg = RiskAggregator()
    res = agg.calculate_risk(target, context)

    assessment = models.PreSanctionAssessment(
        proposed_category=req.category,
        proposed_amount=req.sanctioned_amount,
        description=req.location,
        risk_score=res.get('score'),
        risk_level=res.get('level', 'LIMITED'),
        assessment_status=res.get('assessment_status'),
        assessment_coverage_pct=res.get('assessment_coverage', {}).get('percentage'),
        risk_reasons=res.get('risk_reasons', []),
        indicators=res.get('indicators', []),
        provenance='AI ASSESSMENT',
        engine_version='5.0.0',
    )
    db.add(assessment)
    db.flush()
    official_user = db.query(models.User).filter(models.User.username == current_user.get('sub')).first()
    if official_user:
        db.add(models.AuditLog(user_id=official_user.id, action='PRE_SANCTION_ASSESSMENT', entity_type='PreSanctionAssessment', entity_id=assessment.id, details='Persisted analytical pre-sanction assessment'))
    db.commit()
    
    return schemas.RiskAssessmentResponse(
        score=res['score'],
        level=res['level'],
        assessment_status=res.get('assessment_status', 'COMPLETED'),
        assessment_coverage=schemas.AssessmentCoverage(**res.get('assessment_coverage', {'assessable': 0, 'total': 0, 'percentage': 0.0})),
        assessable_indicator_count=res.get('assessable_indicator_count', 0),
        total_indicator_count=res.get('total_indicator_count', 0),
        risk_reasons=res.get('risk_reasons', []),
        indicators=[schemas.RiskIndicatorSchema(
            indicator=i['indicator'],
            status=i['status'],
            severity=i['severity'],
            score=i.get('score'),
            confidence=i.get('confidence'),
            explanation=i.get('explanation', ''),
            evidence=i.get('evidence', {}),
            data_provenance=i.get('data_provenance', 'UNAVAILABLE')
        ) for i in res['indicators']]
    )

@router.get('/history', response_model=list[schemas.PreSanctionAssessmentResponse])
def pre_sanction_history(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    return db.query(models.PreSanctionAssessment).order_by(
        models.PreSanctionAssessment.assessed_at.desc(), models.PreSanctionAssessment.id.desc()
    ).limit(limit).all()
