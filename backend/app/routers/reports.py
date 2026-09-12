from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from ..auth_utils import get_current_user
from ..official_data import get_official_project_or_404
import csv
import io
import json
import datetime

router = APIRouter(prefix='/api/reports', tags=['reports'])

@router.get('/projects/{project_id}.json')
def export_project(project_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    project = get_official_project_or_404(db, project_id)
    risk = db.query(models.RiskAssessment).filter(models.RiskAssessment.project_id == project_id).order_by(models.RiskAssessment.created_at.desc(), models.RiskAssessment.id.desc()).first()
    compliance = db.query(models.ComplianceAssessment).filter(models.ComplianceAssessment.project_id == project_id).order_by(models.ComplianceAssessment.assessed_at.desc(), models.ComplianceAssessment.id.desc()).first()
    warnings = db.query(models.EarlyWarning).filter(models.EarlyWarning.project_id == project_id).all()
    predictive = db.query(models.PredictiveCompletionAssessment).filter(models.PredictiveCompletionAssessment.project_id == project_id).order_by(models.PredictiveCompletionAssessment.created_at.desc(), models.PredictiveCompletionAssessment.id.desc()).first()
    official_user = db.query(models.User).filter(models.User.username == user.get('sub')).first()
    if official_user:
        db.add(models.AuditLog(user_id=official_user.id, action='PROJECT_REPORT_EXPORTED', entity_type='Project', entity_id=project_id, details='Structured JSON project report exported'))
        db.commit()
    payload = {
        'report_type': 'MPLAD_PROJECT_INTELLIGENCE',
        'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'official_project': {'id': project.id, 'work_id': project.work_id, 'category': project.category, 'description': project.description, 'district': project.district, 'constituency': project.constituency, 'status': project.status, 'sanctioned_amount': float(project.sanctioned_amount) if project.sanctioned_amount is not None else None, 'latitude': project.latitude, 'longitude': project.longitude},
        'analytical_progress_proxy': {'value': project.progress[-1].percentage if project.progress else None, 'provenance': 'DERIVED'},
        'risk_assessment': {'score': risk.score, 'level': risk.overall_risk_level, 'reasons': risk.risk_reasons, 'coverage': risk.assessment_coverage_pct, 'engine_version': risk.engine_version, 'created_at': risk.created_at.isoformat() if risk else None} if risk else None,
        'compliance': {'status': compliance.overall_status, 'coverage': compliance.coverage_percentage, 'engine_version': compliance.engine_version} if compliance else None,
        'early_warnings': [{'type': w.warning_type, 'level': w.warning_level, 'status': w.status, 'explanation': w.explanation, 'provenance': w.provenance, 'engine_version': w.engine_version} for w in warnings],
        'predictive_completion': {'status': predictive.status, 'risk_level': predictive.risk_level, 'risk_score': predictive.risk_score, 'confidence': predictive.confidence, 'missing_data': predictive.missing_data, 'engine_version': predictive.engine_version} if predictive else None,
        'provenance': project.provenance,
        'limitations': ['Analytical progress is a proxy derived from official work-stage data.', 'GPS, contractor, and payment history are DATA-LIMITED when absent from the official record.'],
    }
    return StreamingResponse(io.BytesIO(json.dumps(payload, default=str, indent=2).encode()), media_type='application/json', headers={'Content-Disposition': f'attachment; filename=mplad-project-{project_id}.json'})

@router.get('/projects/{project_id}.csv')
def export_project_csv(project_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    project = get_official_project_or_404(db, project_id)
    official_user = db.query(models.User).filter(models.User.username == user.get('sub')).first()
    if official_user:
        db.add(models.AuditLog(user_id=official_user.id, action='PROJECT_REPORT_EXPORTED', entity_type='Project', entity_id=project_id, details='Structured CSV project report exported'))
        db.commit()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['field', 'value', 'provenance'])
    for field, value, provenance in [('id', project.id, 'OFFICIAL'), ('work_id', project.work_id, 'OFFICIAL'), ('category', project.category, 'OFFICIAL'), ('description', project.description, 'OFFICIAL'), ('district', project.district, 'OFFICIAL'), ('sanctioned_amount', project.sanctioned_amount, 'OFFICIAL'), ('latitude', project.latitude, project.gps_provenance), ('longitude', project.longitude, project.gps_provenance), ('progress_proxy', project.progress[-1].percentage if project.progress else None, 'DERIVED')]:
        writer.writerow([field, value, provenance])
    return StreamingResponse(io.BytesIO(output.getvalue().encode()), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename=mplad-project-{project_id}.csv'})
