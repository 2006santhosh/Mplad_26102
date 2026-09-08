from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..auth_utils import get_current_user
import pandas as pd
import numpy as np

router = APIRouter(prefix="/api/projects/{project_id}/comparison", tags=["comparison"])

@router.get("/", response_model=schemas.ProjectComparisonResponse)
def get_project_comparison(project_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    if not p.category:
        return schemas.ProjectComparisonResponse(
            project_id=project_id,
            peer_group_name="Unknown Category",
            peer_count=0,
            metrics=[]
        )

    # Find peers (same category, exclude self)
    peers = db.query(models.Project).filter(
        models.Project.category == p.category,
        models.Project.id != project_id
    ).all()

    if not peers:
        return schemas.ProjectComparisonResponse(
            project_id=project_id,
            peer_group_name=f"{p.category} Projects",
            peer_count=0,
            metrics=[]
        )

    metrics = []

    # 1. Cost Comparison
    valid_peer_costs = [
        peer.sanctioned_amount for peer in peers 
        if peer.sanctioned_amount is not None and peer.sanctioned_amount >= 0
    ]
    
    if valid_peer_costs and p.sanctioned_amount is not None and p.sanctioned_amount >= 0:
        peer_avg_cost = sum(valid_peer_costs) / len(valid_peer_costs)
        
        if peer_avg_cost > 0:
            diff_pct = ((p.sanctioned_amount - peer_avg_cost) / peer_avg_cost) * 100
            is_anomaly = abs(diff_pct) > 50.0
            
            metrics.append(schemas.ComparisonMetric(
                metric_name="Sanctioned Amount (₹)",
                project_value=float(p.sanctioned_amount),
                peer_average=float(peer_avg_cost),
                difference_percentage=float(diff_pct),
                is_anomaly=is_anomaly
            ))
        else:
            # peer average is zero, cannot calculate difference percentage safely
            metrics.append(schemas.ComparisonMetric(
                metric_name="Sanctioned Amount (₹)",
                project_value=float(p.sanctioned_amount),
                peer_average=0.0,
                difference_percentage=None,
                is_anomaly=False
            ))

    # 2. Planned Duration Comparison
    def get_duration(proj):
        if proj.planned_start and proj.planned_completion:
            d = (proj.planned_completion - proj.planned_start).days
            return d if d > 0 else None
        return None

    project_duration = get_duration(p)
    valid_peer_durations = [get_duration(peer) for peer in peers if get_duration(peer) is not None]

    if valid_peer_durations and project_duration is not None:
        peer_avg_duration = sum(valid_peer_durations) / len(valid_peer_durations)
        
        if peer_avg_duration > 0:
            diff_pct = ((project_duration - peer_avg_duration) / peer_avg_duration) * 100
            is_anomaly = abs(diff_pct) > 50.0
            
            metrics.append(schemas.ComparisonMetric(
                metric_name="Planned Duration (Days)",
                project_value=float(project_duration),
                peer_average=float(peer_avg_duration),
                difference_percentage=float(diff_pct),
                is_anomaly=is_anomaly
            ))
        else:
            # peer average is zero
            metrics.append(schemas.ComparisonMetric(
                metric_name="Planned Duration (Days)",
                project_value=float(project_duration),
                peer_average=0.0,
                difference_percentage=None,
                is_anomaly=False
            ))

    return schemas.ProjectComparisonResponse(
        project_id=project_id,
        peer_group_name=f"{p.category} Projects",
        peer_count=len(peers),
        metrics=metrics
    )
