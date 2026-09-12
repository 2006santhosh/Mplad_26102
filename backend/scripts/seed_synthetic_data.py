import sys
import os
from datetime import date, timedelta
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import DataSource, MP, Project, ProjectFinancials, ProjectProgress, Contractor, ProjectContractor, RiskAssessment, RiskIndicator, RiskHistory
from app.risk_engine.aggregator import RiskAggregator

def clear_synthetic_data(db):
    # Find the Synthetic Data Source
    ds = db.query(DataSource).filter(DataSource.source_type == "SYNTHETIC").first()
    if not ds:
        return
    
    # Find all synthetic projects
    projects = db.query(Project).filter(Project.data_source_id == ds.id).all()
    project_ids = [p.id for p in projects]
    if not project_ids:
        return
        
    # Delete child records
    db.query(ProjectFinancials).filter(ProjectFinancials.project_id.in_(project_ids)).delete(synchronize_session='fetch')
    db.query(ProjectProgress).filter(ProjectProgress.project_id.in_(project_ids)).delete(synchronize_session='fetch')
    db.query(ProjectContractor).filter(ProjectContractor.project_id.in_(project_ids)).delete(synchronize_session='fetch')
    
    # Delete risk data
    assessments = db.query(RiskAssessment).filter(RiskAssessment.project_id.in_(project_ids)).all()
    assessment_ids = [a.id for a in assessments]
    if assessment_ids:
        db.query(RiskIndicator).filter(RiskIndicator.risk_assessment_id.in_(assessment_ids)).delete(synchronize_session='fetch')
        db.query(RiskAssessment).filter(RiskAssessment.project_id.in_(project_ids)).delete(synchronize_session='fetch')
    
    db.query(RiskHistory).filter(RiskHistory.project_id.in_(project_ids)).delete(synchronize_session='fetch')
    
    # Finally delete projects
    db.query(Project).filter(Project.id.in_(project_ids)).delete(synchronize_session='fetch')
    
    # Also delete contractors used just for synthetic
    db.query(Contractor).filter(Contractor.registration_id.in_(["SYN_REG_NORMAL", "SYN_REG_SUSPECT"])).delete(synchronize_session='fetch')
    
    db.commit()

def seed_demo_data(db):
    clear_synthetic_data(db)
    
    ds = db.query(DataSource).filter(DataSource.source_name == "Synthetic Demo Data").first()
    if not ds:
        ds = DataSource(
            source_name="Synthetic Demo Data",
            source_type="SYNTHETIC",
            description="Synthetic project-level data generated for SIH demonstration purposes only.",
            dataset_version="1.0"
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)

    mps = db.query(MP).all()
    if not mps:
        print("Please run seed_official_data.py first to establish MPs.")
        return

    # Contractors
    c_normal = Contractor(name="Reliable Builders Demo", registration_id="SYN_REG_NORMAL")
    c_suspect = Contractor(name="Acme Construction Demo", registration_id="SYN_REG_SUSPECT")
    db.add_all([c_normal, c_suspect])
    db.commit()
    db.refresh(c_normal)
    db.refresh(c_suspect)

    start = date(2025, 1, 1)

    all_projects = []
    import random
    
    print(f"Generating synthetic projects for {len(mps)} MPs...")
    for mp in mps:
        # Base coordinates could be somewhat random but let's just make it simple
        base_lat = 28.6139 + random.uniform(-2, 2)
        base_lon = 77.2090 + random.uniform(-2, 2)
        
        # SCENARIO A: Healthy / Normal Project
        pA = Project(
            mp_id=mp.id, data_source_id=ds.id, category="Education", sanctioned_amount=1500000,
            location=f"Village School, {mp.constituency}", latitude=base_lat + 0.01, longitude=base_lon + 0.01,
            planned_start=start, planned_completion=start + timedelta(days=180), status="IN_PROGRESS"
        )
        
        # SCENARIO B: Financial / Progress Mismatch
        pB = Project(
            mp_id=mp.id, data_source_id=ds.id, category="Road Infrastructure", sanctioned_amount=50000000,
            location=f"District Highway, {mp.constituency}", latitude=base_lat + 0.02, longitude=base_lon + 0.02,
            planned_start=start, planned_completion=start + timedelta(days=90), status="IN_PROGRESS"
        )
        
        # SCENARIO C: Delayed / Stagnating
        pC = Project(
            mp_id=mp.id, data_source_id=ds.id, category="Health", sanctioned_amount=8000000,
            location=f"Rural Clinic, {mp.constituency}", latitude=base_lat + 0.03, longitude=base_lon + 0.03,
            planned_start=start - timedelta(days=365), planned_completion=start - timedelta(days=180), status="DELAYED"
        )

        all_projects.extend([(pA, "A"), (pB, "B"), (pC, "C")])
        
        # Add a few more projects with 50% probability
        if random.random() > 0.5:
            # SCENARIO D: Similar / Potential Duplicate
            pD1 = Project(
                mp_id=mp.id, data_source_id=ds.id, category="Water Supply", sanctioned_amount=5000000,
                location=f"North Block Pipeline, {mp.constituency}", latitude=base_lat + 0.040, longitude=base_lon + 0.040,
                planned_start=start, planned_completion=start + timedelta(days=120), status="COMPLETED"
            )
            pD2 = Project(
                mp_id=mp.id, data_source_id=ds.id, category="Water Supply", sanctioned_amount=4900000,
                location=f"North Block Main Pipeline Ext, {mp.constituency}", latitude=base_lat + 0.041, longitude=base_lon + 0.041,
                planned_start=start + timedelta(days=10), planned_completion=start + timedelta(days=130), status="IN_PROGRESS"
            )
            all_projects.extend([(pD1, "D1"), (pD2, "D2")])

    print(f"Total synthetic projects generated: {len(all_projects)}")
    
    # Save all projects
    projs = [p[0] for p in all_projects]
    db.add_all(projs)
    db.commit()

    # Add specifics
    print("Adding financials and progress data...")
    for p, sc in all_projects:
        if sc == "A":
            db.add(ProjectFinancials(project_id=p.id, expenditure=750000))
            db.add(ProjectProgress(project_id=p.id, percentage=55))
            db.add(ProjectContractor(project_id=p.id, contractor_id=c_normal.id))
        elif sc == "B":
            db.add(ProjectFinancials(project_id=p.id, expenditure=45000000))
            db.add(ProjectProgress(project_id=p.id, percentage=20))
            db.add(ProjectContractor(project_id=p.id, contractor_id=c_normal.id))
        elif sc == "C":
            db.add(ProjectFinancials(project_id=p.id, expenditure=4000000))
            db.add(ProjectProgress(project_id=p.id, percentage=30))
            db.add(ProjectContractor(project_id=p.id, contractor_id=c_normal.id))
        elif sc == "D1":
            db.add(ProjectFinancials(project_id=p.id, expenditure=5000000))
            db.add(ProjectProgress(project_id=p.id, percentage=100))
            db.add(ProjectContractor(project_id=p.id, contractor_id=c_suspect.id))
        elif sc == "D2":
            db.add(ProjectFinancials(project_id=p.id, expenditure=2000000))
            db.add(ProjectProgress(project_id=p.id, percentage=40))
            db.add(ProjectContractor(project_id=p.id, contractor_id=c_suspect.id))

    db.commit()

    print("Running Risk Aggregator on synthetic projects... this might take a few moments.")
    from app.routers.projects import _get_project_context
    context = _get_project_context(db)
    df_p = context['df_projects']
    agg = RiskAggregator()
    
    assessments_to_add = []
    indicators_to_add = []
    
    for i, (p, _) in enumerate(all_projects):
        if not df_p.empty and 'id' in df_p.columns and not df_p[df_p['id'] == p.id].empty:
            target = df_p[df_p['id'] == p.id].iloc[0].to_dict()
        else:
            prog_val = db.query(ProjectProgress).filter(ProjectProgress.project_id == p.id).first()
            fin_val = db.query(ProjectFinancials).filter(ProjectFinancials.project_id == p.id).first()
            target = {
                'id': p.id,
                'category': p.category,
                'sanctioned_amount': float(p.sanctioned_amount) if p.sanctioned_amount else None,
                'location': p.location or "",
                'progress_pct': prog_val.percentage if prog_val else None,
                'expenditure': float(fin_val.expenditure) if fin_val and fin_val.expenditure else None,
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
            }
            
        pcs = db.query(ProjectContractor).filter(ProjectContractor.project_id == p.id).all()
        target['contractors'] = [pc.contractor_id for pc in pcs]
        
        res = agg.calculate_risk(target, context)
        ra = RiskAssessment(
            project_id=p.id,
            score=res['score'],
            overall_risk_level=res['level']
        )
        assessments_to_add.append((ra, res['indicators']))
        
        if (i + 1) % 500 == 0:
            print(f"Processed risk for {i + 1} projects...")

    for ra, _ in assessments_to_add:
        db.add(ra)
    db.commit()

    for ra, inds in assessments_to_add:
        for ind in inds:
            ri = RiskIndicator(
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
            indicators_to_add.append(ri)
            
    db.add_all(indicators_to_add)
    db.commit()

    print(f"Seeded {len(all_projects)} synthetic demo projects successfully.")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()
