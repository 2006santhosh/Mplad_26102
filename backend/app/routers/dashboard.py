from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user
from collections import defaultdict

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/stats", response_model=schemas.DashboardStatsResponse)
def get_dashboard_stats(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # 1. MP Allocations (Official Government CSV)
    mps = db.query(models.MP).all()
    total_mps = len(mps)
    total_allocated_amount = sum((float(mp.allocated_amount) if mp.allocated_amount else 0.0) for mp in mps)

    # 2. Official Government Projects (eSAKSHI Work Dataset)
    projects = db.query(models.Project).outerjoin(models.DataSource).filter(
        (models.DataSource.source_type == "OFFICIAL") | (models.DataSource.id.is_(None))
    ).all()
    total_projects = len(projects)
    
    # Financials
    total_sanctioned = 0.0
    total_expenditure = 0.0
    
    for p in projects:
        s_amt = float(p.sanctioned_amount) if p.sanctioned_amount is not None and p.sanctioned_amount > 0 else 0.0
        total_sanctioned += s_amt
        
        exp_records = [float(f.expenditure) for f in p.financials if f.expenditure is not None and f.expenditure >= 0]
        if exp_records:
            total_expenditure += max(exp_records)
            
    utilization_pct = (total_expenditure / total_sanctioned * 100) if total_sanctioned > 0 else None
    
    # Portfolio Progress
    progress_sum = 0.0
    progress_count = 0
    for p in projects:
        prog_records = [pr.percentage for pr in p.progress if pr.percentage is not None and pr.percentage >= 0]
        if prog_records:
            progress_sum += max(prog_records)
            progress_count += 1
            
    average_progress = (progress_sum / progress_count) if progress_count > 0 else None
    
    # Risk Distribution & AI Risk Projects
    risk_distribution = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0, "LIMITED": 0}
    ai_risk_projects = set()
    
    for p in projects:
        if p.risk_assessments:
            latest_assessment = sorted(p.risk_assessments, key=lambda x: x.created_at, reverse=True)[0]
            level = latest_assessment.overall_risk_level.upper() if latest_assessment.overall_risk_level else "LOW"
            if level in risk_distribution:
                risk_distribution[level] += 1
            if level in ["MEDIUM", "HIGH", "CRITICAL"]:
                ai_risk_projects.add(p.id)
                
    # Human Review Flags
    human_flags = set()
    for p in projects:
        if p.review_logs:
            latest_review = sorted(p.review_logs, key=lambda x: x.created_at, reverse=True)[0]
            if latest_review.action == "FLAG":
                human_flags.add(p.id)
                
    # Delayed Projects
    delayed_projects = set(p.id for p in projects if p.status == "DELAYED")
    
    # Union: Projects Requiring Attention
    attention_projects = ai_risk_projects.union(human_flags).union(delayed_projects)
    
    # Category Breakdown
    categories = defaultdict(lambda: {"count": 0, "amount": 0.0})
    for p in projects:
        cat = p.category or "Unknown"
        amt = float(p.sanctioned_amount) if p.sanctioned_amount is not None and p.sanctioned_amount > 0 else 0.0
        categories[cat]["count"] += 1
        categories[cat]["amount"] += amt
        
    category_stats = []
    for cat, data in categories.items():
        category_stats.append(schemas.DashboardCategoryStat(
            category=cat,
            count=data["count"],
            total_amount=data["amount"]
        ))
    category_stats.sort(key=lambda x: x.count, reverse=True)

    # Compliance Intelligence Summary — from persisted assessments
    compliance_pass = 0
    compliance_review = 0
    compliance_na = 0
    compliance_assessed = 0
    
    for p in projects:
        if p.compliance_assessments:
            latest_ca = sorted(p.compliance_assessments, key=lambda x: x.assessed_at, reverse=True)[0]
            compliance_assessed += 1
            if latest_ca.overall_status == "PASS":
                compliance_pass += 1
            elif latest_ca.overall_status in ("REVIEW", "PASS WITH LIMITED COVERAGE"):
                compliance_review += 1
            elif latest_ca.overall_status == "NOT_ASSESSABLE":
                compliance_na += 1
            else:
                compliance_review += 1  # FAIL also routes to review

    return schemas.DashboardStatsResponse(
        total_projects=total_projects,
        total_sanctioned_amount=total_sanctioned,
        total_expenditure=total_expenditure,
        utilization_percentage=utilization_pct,
        total_mps=total_mps,
        total_allocated_amount=total_allocated_amount,
        projects_with_progress=progress_count,
        average_progress=average_progress,
        ai_risk_projects=len(ai_risk_projects),
        human_review_flags=len(human_flags),
        delayed_projects=len(delayed_projects),
        projects_requiring_attention=len(attention_projects),
        risk_distribution=schemas.RiskDistribution(**risk_distribution),
        projects_by_category=category_stats,
        compliance_pass_count=compliance_pass if compliance_assessed > 0 else None,
        compliance_review_count=compliance_review if compliance_assessed > 0 else None,
        compliance_not_assessable_count=compliance_na if compliance_assessed > 0 else None,
        compliance_assessed_projects=compliance_assessed if compliance_assessed > 0 else None,
    )
