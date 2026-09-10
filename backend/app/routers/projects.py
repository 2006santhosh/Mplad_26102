from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
import pandas as pd
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user, RoleChecker
from ..risk_engine.aggregator import RiskAggregator
from ..risk_engine.trend_analyzer import TrendAnalyzer
from ..services.review_priority import calculate_review_priority
from datetime import date, datetime

CURRENT_RISK_ENGINE_VERSION = "5.0.0"

router = APIRouter(prefix="/api/projects", tags=["projects"])

def _get_project_context(db: Session):
    projects = db.query(models.Project).options(joinedload(models.Project.mp)).all()

    progress_rows = db.query(
        models.ProjectProgress.project_id,
        models.ProjectProgress.percentage,
    ).order_by(
        models.ProjectProgress.reported_at.desc(),
        models.ProjectProgress.id.desc(),
    ).all()
    progress_map = {}
    for row in progress_rows:
        if row.project_id not in progress_map:
            progress_map[row.project_id] = row.percentage

    financial_rows = db.query(
        models.ProjectFinancials.project_id,
        models.ProjectFinancials.expenditure,
    ).order_by(
        models.ProjectFinancials.updated_at.desc(),
        models.ProjectFinancials.id.desc(),
    ).all()
    financial_map = {}
    for row in financial_rows:
        if row.project_id not in financial_map:
            financial_map[row.project_id] = row.expenditure
    
    data = []
    for p in projects:
        prog_pct = progress_map.get(p.id)
        exp = financial_map.get(p.id)
        
        data.append({
            'id': p.id,
            'category': p.category,
            'sanctioned_amount': float(p.sanctioned_amount) if p.sanctioned_amount is not None else None,
            'location': p.location or "",
            'progress_pct': prog_pct,
            'expenditure': float(exp) if exp is not None else None,
            'planned_completion': p.planned_completion,
            'actual_completion': p.actual_completion,
            'status': p.status,
            'description': p.description,
            'district': p.district,
            'constituency': p.constituency,
            'work_category': p.work_category,
            'latitude': p.latitude,
            'longitude': p.longitude,
            'mp_name': p.mp.name if p.mp else None,
            'expenditure_pct': (float(exp) / float(p.sanctioned_amount) * 100) if exp is not None and p.sanctioned_amount else None,
            'delay_days': (date.today() - p.planned_completion).days if p.planned_completion and p.status != 'COMPLETED' else None
        })
    df_projects = pd.DataFrame(data)
    
    # Contract mappings
    c_data = []
    pcs = db.query(models.ProjectContractor).all()
    for pc in pcs:
        c_data.append({'project_id': pc.project_id, 'contractor_id': pc.contractor_id})
    df_contractor_projects = pd.DataFrame(c_data)
    
    return {'df_projects': df_projects, 'df_contractor_projects': df_contractor_projects}

@router.get("", response_model=list[schemas.ProjectResponse])
@router.get("/", response_model=list[schemas.ProjectResponse])
def get_projects(include_demo: bool = False, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    query = db.query(models.Project).options(
        joinedload(models.Project.mp),
        joinedload(models.Project.data_source),
    )
    if not include_demo:
        query = query.join(models.DataSource).filter(models.DataSource.source_type == "OFFICIAL")
    
    projects = query.all()
    
    # Fast bulk maps for 1-query performance across thousands of official works
    progress_rows = db.query(
        models.ProjectProgress.project_id,
        models.ProjectProgress.percentage,
    ).order_by(
        models.ProjectProgress.reported_at.desc(),
        models.ProjectProgress.id.desc(),
    ).all()
    prog_map = {}
    for row in progress_rows:
        if row[0] not in prog_map:
            prog_map[row[0]] = row[1]
    
    risk_rows = db.query(models.RiskAssessment.project_id, models.RiskAssessment.score, models.RiskAssessment.overall_risk_level, models.RiskAssessment.assessment_coverage_pct).order_by(
        models.RiskAssessment.created_at.desc(), models.RiskAssessment.id.desc()
    ).all()
    risk_map = {}
    for row in risk_rows:
        if row[0] not in risk_map:
            risk_map[row[0]] = (row[1], row[2], row[3])

    ew_rows = db.query(models.EarlyWarning.project_id).filter(
        models.EarlyWarning.status.in_(["OPEN", "ACKNOWLEDGED", "UNDER_REVIEW"])
    ).all()
    ew_map = {}
    for row in ew_rows:
        ew_map[row[0]] = ew_map.get(row[0], 0) + 1

    # Predictive Completion Map
    pred_rows = db.query(
        models.PredictiveCompletionAssessment.project_id,
        models.PredictiveCompletionAssessment.risk_level
    ).order_by(
        models.PredictiveCompletionAssessment.created_at.desc(),
        models.PredictiveCompletionAssessment.id.desc(),
    ).all()
    
    pred_map = {}
    for row in pred_rows:
        if row[0] not in pred_map:
            pred_map[row[0]] = row[1]

    # Compliance Map
    comp_rows = db.query(
        models.ComplianceAssessment.project_id,
        models.ComplianceAssessment.overall_status
    ).order_by(
        models.ComplianceAssessment.assessed_at.desc(),
        models.ComplianceAssessment.id.desc(),
    ).all()
    
    comp_map = {}
    for row in comp_rows:
        if row[0] not in comp_map:
            comp_map[row[0]] = row[1]

    results = []
    for p in projects:
        risk_info = risk_map.get(p.id, (None, None, None))
        resp = schemas.ProjectResponse(
            id=p.id,
            mp_id=p.mp_id,
            data_source_id=p.data_source_id,
            category=p.category,
            sanctioned_amount=float(p.sanctioned_amount) if p.sanctioned_amount is not None else None,
            location=p.location,
            planned_start=p.planned_start,
            planned_completion=p.planned_completion,
            actual_completion=p.actual_completion,
            status=p.status,
            work_id=p.work_id,
            work_stage=p.work_stage,
            district=p.district,
            constituency=p.constituency,
            latitude=p.latitude,
            longitude=p.longitude,
            gps_provenance=p.gps_provenance,
            description=p.description,
            source_type=p.data_source.source_type if p.data_source else None,
            mp_name=p.mp.name if p.mp else None,
            progress_pct=prog_map.get(p.id),
            progress_proxy_label="Analytical Progress Proxy — derived from official WORK_STAGE",
            latest_risk_score=risk_info[0],
            latest_risk_level=risk_info[1],
            early_warning_count=ew_map.get(p.id, 0),
            predictive_risk_level=pred_map.get(p.id),
            provenance={
                "sanctioned_amount": p.data_source.source_type if p.sanctioned_amount is not None and p.data_source else "UNAVAILABLE",
                "work_stage": p.data_source.source_type if p.work_stage and p.data_source else "UNAVAILABLE",
                "physical_progress": "DERIVED" if prog_map.get(p.id) is not None and p.source_type == "OFFICIAL" else ("SYNTHETIC" if prog_map.get(p.id) is not None else "UNAVAILABLE"),
                "risk_score": "AI ASSESSMENT" if risk_info[0] is not None else "UNAVAILABLE",
            }
        )
        
        comp_status = comp_map.get(p.id, "NOT_ASSESSABLE")
        ew_count = ew_map.get(p.id, 0)
        pred_lvl = pred_map.get(p.id)

        priority = calculate_review_priority(
            overall_risk={"level": risk_info[1], "score": risk_info[0], "coverage": risk_info[2]},
            risk_trend={"trend": "STABLE", "explanation": "Risk levels have remained stable."},
            compliance={"status": comp_status},
            open_warnings=[{"level": "LOW"}] * ew_count,
            completion_risk={"level": pred_lvl, "confidence": None},
        )
        resp.review_priority_level = priority["level"]
        results.append(resp)
    return results

@router.get("/map", response_model=schemas.MapResponse)
def get_map_data(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    projects = db.query(models.Project).join(models.DataSource).filter(
        models.DataSource.source_type == "OFFICIAL"
    ).all()
    
    # Fast bulk maps
    risk_rows = db.query(models.RiskAssessment.project_id, models.RiskAssessment.score, models.RiskAssessment.overall_risk_level).order_by(
        models.RiskAssessment.created_at.desc(), models.RiskAssessment.id.desc()
    ).all()
    risk_map = {}
    for row in risk_rows:
        if row[0] not in risk_map:
            risk_map[row[0]] = (row[1], row[2])
    
    # Since we do not have a dedicated warnings table yet, we can mock warning count to 0 or derive it if needed.
    # In Phase 6, early warnings are usually evaluated on the fly. 
    # For now we'll just return 0 for map view to avoid N+1 queries.
    
    valid_projects = []
    total_projects = len(projects)
    valid_gps_count = 0
    unavailable_gps_count = 0
    
    from ..risk_engine.geo_utils import validate_coordinates
    
    for p in projects:
        if validate_coordinates(p.latitude, p.longitude) == 'VALID':
            valid_gps_count += 1
            risk_info = risk_map.get(p.id, (None, None))
            valid_projects.append(schemas.ProjectMapItem(
                project_id=p.id,
                latitude=float(p.latitude),
                longitude=float(p.longitude),
                gps_provenance=p.gps_provenance,
                risk_score=risk_info[0],
                risk_level=risk_info[1],
                warning_count=0
            ))
        else:
            unavailable_gps_count += 1
            
    coverage = (valid_gps_count / total_projects * 100) if total_projects > 0 else 0.0
    
    return schemas.MapResponse(
        projects=valid_projects,
        gps_coverage_percentage=coverage,
        total_projects=total_projects,
        valid_gps_count=valid_gps_count,
        unavailable_gps_count=unavailable_gps_count
    )

@router.get("/{project_id}", response_model=schemas.ProjectDetailResponse)
def get_project(project_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
        
    prog = db.query(models.ProjectProgress).filter(models.ProjectProgress.project_id == project_id).order_by(models.ProjectProgress.reported_at.desc(), models.ProjectProgress.id.desc()).first()
    fin = db.query(models.ProjectFinancials).filter(models.ProjectFinancials.project_id == project_id).order_by(models.ProjectFinancials.updated_at.desc(), models.ProjectFinancials.id.desc()).first()
    risk = db.query(models.RiskAssessment).filter(models.RiskAssessment.project_id == project_id).order_by(models.RiskAssessment.created_at.desc(), models.RiskAssessment.id.desc()).first()

    return schemas.ProjectDetailResponse(
        id=p.id, mp_id=p.mp_id, data_source_id=p.data_source_id,
        category=p.category, sanctioned_amount=p.sanctioned_amount,
        location=p.location, planned_start=p.planned_start, 
        planned_completion=p.planned_completion, actual_completion=p.actual_completion,
        status=p.status,
        work_id=p.work_id,
        work_stage=p.work_stage,
        district=p.district,
        constituency=p.constituency,
        description=p.description,
        work_category=p.work_category,
        mp_name=p.mp.name if p.mp else None,
        progress_pct=prog.percentage if prog else None,
        progress_proxy_label="Analytical Progress Proxy — derived from official WORK_STAGE",
        expenditure=float(fin.expenditure) if fin and fin.expenditure is not None else None,
        latest_risk_score=risk.score if risk else None,
        latest_risk_level=risk.overall_risk_level if risk else None,
        source_type=p.data_source.source_type if p.data_source else None
    )

def _calculate_and_persist_risk(project_id: int, db: Session) -> schemas.RiskAssessmentResponse:
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
        
    context = _get_project_context(db)
    df_p = context['df_projects']
    target = df_p[df_p['id'] == project_id].iloc[0].to_dict()
    
    # get contractors
    pcs = db.query(models.ProjectContractor).filter(models.ProjectContractor.project_id == project_id).all()
    target['contractors'] = [pc.contractor_id for pc in pcs]
    
    agg = RiskAggregator()
    res = agg.calculate_risk(target, context)
    
    # Save assessment to DB
    ra = models.RiskAssessment(
        project_id=project_id,
        score=res['score'],
        overall_risk_level=res['level'],
        assessment_status=res.get('assessment_status'),
        assessment_coverage_pct=res.get('assessment_coverage', {}).get('percentage'),
        assessable_indicator_count=res.get('assessable_indicator_count'),
        total_indicator_count=res.get('total_indicator_count'),
        risk_reasons=res.get('risk_reasons'),
        engine_version=CURRENT_RISK_ENGINE_VERSION
    )
    db.add(ra)
    db.flush()
    
    for ind in res['indicators']:
        ri = models.RiskIndicator(
            risk_assessment_id=ra.id,
            indicator=ind['indicator'],
            status=ind['status'],
            severity=ind['severity'],
            score=ind.get('score'),
            confidence=ind.get('confidence'),
            explanation=ind.get('explanation'),
            evidence=ind.get('evidence'),
            data_provenance=ind.get('data_provenance', 'UNAVAILABLE')
        )
        db.add(ri)

    db.add(models.RiskHistory(
        project_id=project_id,
        risk_score=res['score'],
        risk_level=res['level'],
        indicator_snapshot=res['indicators'],
    ))
    db.commit()
    db.refresh(ra)

    return schemas.RiskAssessmentResponse(
        score=res['score'],
        level=res['level'],
        assessment_status=res['assessment_status'],
        assessment_coverage=schemas.AssessmentCoverage(**res['assessment_coverage']),
        assessable_indicator_count=res['assessable_indicator_count'],
        total_indicator_count=res['total_indicator_count'],
        risk_reasons=res['risk_reasons'],
        indicators=[schemas.RiskIndicatorSchema(**i) for i in res['indicators']]
    )


@router.get("/{project_id}/risk", response_model=schemas.RiskAssessmentResponse)
def run_project_risk(project_id: int, db: Session = Depends(get_db), user: dict = Depends(RoleChecker(['Admin', 'Auditor', 'State', 'District']))):
    assessment = db.query(models.RiskAssessment).filter(
        models.RiskAssessment.project_id == project_id
    ).order_by(
        models.RiskAssessment.created_at.desc(),
        models.RiskAssessment.id.desc(),
    ).first()
    if not assessment:
        if not db.query(models.Project).filter(models.Project.id == project_id).first():
            raise HTTPException(status_code=404, detail="Project not found")
        return schemas.RiskAssessmentResponse(
            level="LIMITED",
            assessment_status="NOT_ASSESSABLE",
            risk_reasons=[],
            indicators=[],
        )
    indicators = db.query(models.RiskIndicator).filter(
        models.RiskIndicator.risk_assessment_id == assessment.id
    ).all()
    return schemas.RiskAssessmentResponse(
        score=assessment.score,
        level=assessment.overall_risk_level,
        assessment_status=assessment.assessment_status or "NOT_ASSESSABLE",
        assessment_coverage=schemas.AssessmentCoverage(
            assessable=assessment.assessable_indicator_count,
            total=assessment.total_indicator_count,
            percentage=assessment.assessment_coverage_pct,
        ) if assessment.assessment_coverage_pct is not None else None,
        assessable_indicator_count=assessment.assessable_indicator_count,
        total_indicator_count=assessment.total_indicator_count,
        risk_reasons=assessment.risk_reasons or [],
        indicators=[schemas.RiskIndicatorSchema(
            indicator=i.indicator,
            status=i.status,
            severity=i.severity,
            score=i.score,
            confidence=i.confidence,
            explanation=i.explanation or "",
            evidence=i.evidence or {},
            data_provenance=i.data_provenance,
        ) for i in indicators],
    )


@router.post("/{project_id}/risk", response_model=schemas.RiskAssessmentResponse)
def create_project_risk_assessment(project_id: int, db: Session = Depends(get_db), user: dict = Depends(RoleChecker(['Admin', 'Auditor', 'State', 'District']))):
    return _calculate_and_persist_risk(project_id, db)

@router.get("/{project_id}/risk/history", response_model=schemas.RiskHistoryResponse)
def get_risk_history(project_id: int, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    # Order oldest to newest for trend analysis, but return newest to oldest
    assessments = db.query(models.RiskAssessment).filter(
        models.RiskAssessment.project_id == project_id
    ).order_by(
        models.RiskAssessment.created_at.desc(),
        models.RiskAssessment.id.desc(),
    ).limit(limit).all()
    assessments.reverse()
    
    if not assessments:
        return schemas.RiskHistoryResponse(
            project_id=project_id,
            assessments=[],
            indicator_trends=[],
            risk_trend_status="INSUFFICIENT_HISTORY",
            risk_trend_explanation="No historical data available.",
            score_change_absolute=None
        )

    assessment_ids = [assessment.id for assessment in assessments]
    indicator_rows = db.query(models.RiskIndicator).filter(
        models.RiskIndicator.risk_assessment_id.in_(assessment_ids)
    ).all()
    indicators_by_assessment = {}
    for indicator in indicator_rows:
        indicators_by_assessment.setdefault(indicator.risk_assessment_id, []).append(indicator)

    # Convert to dictionaries for TrendAnalyzer
    assessments_data = []
    for a in assessments:
        assessments_data.append({
            'risk_score': a.score,
            'assessment_coverage_pct': a.assessment_coverage_pct or 0.0
        })
        
    analyzer = TrendAnalyzer()
    trend_result = analyzer.analyze_risk_trend(assessments_data)
    
    # Collect indicator history
    indicator_dict = {}
    
    # Build RiskHistoryAssessment objects
    history_assessments = []
    for a in reversed(assessments): # Newest first for response
        inds = indicators_by_assessment.get(a.id, [])
        for i in inds:
            if i.indicator not in indicator_dict:
                indicator_dict[i.indicator] = []
            indicator_dict[i.indicator].append({
                'assessment_id': a.id,
                'assessed_at': a.created_at,
                'status': i.status,
                'score': i.score,
                'confidence': i.confidence,
                'severity': i.severity,
                'explanation': i.explanation or ""
            })
            
        history_assessments.append(schemas.RiskHistoryAssessment(
            assessment_id=a.id,
            assessed_at=a.created_at,
            risk_score=a.score,
            risk_level=a.overall_risk_level,
            assessment_status=a.assessment_status,
            assessment_coverage=schemas.AssessmentCoverage(
                assessable=a.assessable_indicator_count,
                total=a.total_indicator_count,
                percentage=a.assessment_coverage_pct,
            ) if a.assessment_coverage_pct is not None else None,
            risk_reasons=a.risk_reasons or [],
            engine_version=a.engine_version
        ))
        
    indicator_trends = []
    for indicator_name, points in indicator_dict.items():
        # points are newest first, need oldest first for trend analysis
        chronological_points = list(reversed(points))
        ind_trend = analyzer.analyze_indicator_trend(chronological_points)
        
        history_points = [schemas.IndicatorHistoryPoint(**p) for p in points]
        indicator_trends.append(schemas.IndicatorTrendResponse(
            indicator=indicator_name,
            history=history_points,
            trend=ind_trend["trend"],
            explanation=ind_trend["explanation"]
        ))
    
    return schemas.RiskHistoryResponse(
        project_id=project_id,
        assessments=history_assessments,
        indicator_trends=indicator_trends,
        risk_trend_status=trend_result["status"],
        risk_trend_explanation=trend_result["explanation"],
        score_change_absolute=trend_result["score_change"]
    )

@router.get("/{project_id}/compliance/history", response_model=schemas.ComplianceHistoryResponse)
def get_compliance_history(project_id: int, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    assessments = db.query(models.ComplianceAssessment).filter(
        models.ComplianceAssessment.project_id == project_id
    ).order_by(
        models.ComplianceAssessment.assessed_at.desc(),
        models.ComplianceAssessment.id.desc(),
    ).limit(limit).all()
    
    if not assessments:
         return schemas.ComplianceHistoryResponse(
             project_id=project_id,
             assessments=[],
             trend_status="INSUFFICIENT_HISTORY",
             trend_explanation="No compliance history available."
         )
         
    history = []
    for a in assessments:
        history.append(schemas.ComplianceHistoryAssessment(
            assessment_id=a.id,
            assessed_at=a.assessed_at,
            overall_status=a.overall_status,
            coverage_percentage=a.coverage_percentage,
            pass_count=a.pass_count,
            review_count=a.review_count,
            not_assessable_count=a.not_assessable_count,
            fail_count=a.fail_count,
            engine_version=a.engine_version
        ))
        
    if len(assessments) >= 2:
        recent = assessments[:3] # already descending, so newest first
        oldest_of_recent = recent[-1]
        newest = recent[0]
        
        if newest.fail_count > oldest_of_recent.fail_count:
            trend_status = "DEGRADING"
            trend_explanation = f"Failures increased from {oldest_of_recent.fail_count} to {newest.fail_count} over the last {len(recent)} assessments."
        elif newest.pass_count > oldest_of_recent.pass_count and newest.fail_count <= oldest_of_recent.fail_count:
            trend_status = "IMPROVING"
            trend_explanation = f"Passes increased from {oldest_of_recent.pass_count} to {newest.pass_count} over the last {len(recent)} assessments."
        else:
            trend_status = "STABLE"
            trend_explanation = "Compliance posture remained stable."
    else:
        trend_status = "INSUFFICIENT_HISTORY"
        trend_explanation = "Only one compliance assessment recorded."

    return schemas.ComplianceHistoryResponse(
        project_id=project_id,
        assessments=history,
        trend_status=trend_status,
        trend_explanation=trend_explanation
    )
