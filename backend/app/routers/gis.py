from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
import math
from collections import defaultdict
from ..auth_utils import get_current_user

router = APIRouter(prefix="/api/gis", tags=["gis"])

def is_valid_coordinate(lat_str, lng_str):
    if lat_str is None or lng_str is None:
        return False
    try:
        lat = float(lat_str)
        lng = float(lng_str)
    except (ValueError, TypeError):
        return False
        
    if math.isnan(lat) or math.isinf(lat) or math.isnan(lng) or math.isinf(lng):
        return False
        
    if lat < -90 or lat > 90:
        return False
        
    if lng < -180 or lng > 180:
        return False
        
    if lat == 0.0 and lng == 0.0:
        # Reject 0,0 unless explicitly authorized, which we assume is not for generic hackathon data
        return False
        
    return True

@router.get("/clusters", response_model=schemas.GISResponse)
def get_gis_clusters(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    projects = db.query(models.Project).join(models.DataSource).filter(models.DataSource.source_type == "OFFICIAL").all()
    
    valid_projects = []
    
    # 1. Validate and extract genuine coordinates
    for p in projects:
        if is_valid_coordinate(p.latitude, p.longitude):
            valid_projects.append({
                "project": p,
                "lat": float(p.latitude),
                "lng": float(p.longitude)
            })
            
    # 2. Deterministic Grid Bucketing (rounding to 1 decimal place = ~11km grid)
    clusters_map = defaultdict(list)
    for vp in valid_projects:
        grid_lat = round(vp["lat"], 1)
        grid_lng = round(vp["lng"], 1)
        cluster_key = f"{grid_lat}_{grid_lng}"
        clusters_map[cluster_key].append(vp)
        
    clusters_response = []
    
    # 3. Aggregate each cluster safely
    for key, items in clusters_map.items():
        if not items:
            continue
            
        sum_lat = 0.0
        sum_lng = 0.0
        total_amount = 0.0
        project_list = []
        
        for item in items:
            p = item["project"]
            sum_lat += item["lat"]
            sum_lng += item["lng"]
            amt = float(p.sanctioned_amount) if p.sanctioned_amount is not None and p.sanctioned_amount >= 0 else 0.0
            total_amount += amt
            
            project_list.append(schemas.GISProjectItem(
                project_id=p.id,
                location=p.location or "Unknown Location",
                category=p.category or "Unknown Category",
                sanctioned_amount=float(p.sanctioned_amount) if p.sanctioned_amount is not None and p.sanctioned_amount >= 0 else None,
                latitude=item["lat"],
                longitude=item["lng"]
            ))
            
        # Actual geographic center calculated ONLY from actual coordinates
        center_lat = sum_lat / len(items)
        center_lng = sum_lng / len(items)
        
        clusters_response.append(schemas.GISCluster(
            cluster_id=key,
            center_latitude=center_lat,
            center_longitude=center_lng,
            project_count=len(items),
            total_amount=total_amount,
            projects=project_list
        ))
        
    # Sort clusters by size (largest concentration first)
    clusters_response.sort(key=lambda x: x.project_count, reverse=True)
    
    return schemas.GISResponse(
        clusters=clusters_response,
        total_valid_projects=len(valid_projects)
    )
