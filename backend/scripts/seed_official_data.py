import sys
import os
import json
from datetime import datetime, date, timedelta
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal, engine
from app.models import (
    Base, DataSource, MP, User, Project, ProjectFinancials, 
    ProjectProgress, Contractor, ProjectContractor, RiskAssessment, 
    RiskIndicator, RiskHistory, ReviewLog, Review, PreSanctionAssessment
)
from app.risk_engine.aggregator import RiskAggregator
import pandas as pd
import bcrypt

def get_hash(password: str):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def parse_date(d_str):
    if not d_str or str(d_str).strip() in ['NA', 'None', '', 'NaN']:
        return None
    d_str = str(d_str).strip()
    for fmt in ['%d-%b-%Y', '%b %d, %Y %I:%M:%S %p', '%Y-%m-%d']:
        try:
            return datetime.strptime(d_str, fmt).date()
        except Exception:
            pass
    return None

def clean_category(act_name, default_cat="General Infrastructure"):
    if not act_name or str(act_name).strip() in ['NA', 'None', '']:
        return default_cat
    parts = str(act_name).split('-')
    if len(parts) > 1:
        cat = parts[-1].strip()
        if len(cat) > 3:
            return cat
    return str(act_name)[:60]

def stage_to_proxy_pct(stage, status):
    if status == 'COMPLETED' or stage == 'Work Completed':
        return 100
    mapping = {
        'Sanction': 0,
        'Time Estimation': 10,
        'Vendor Identification': 20,
        'Physical Inspection': 40,
        'Work partially Completed': 60
    }
    return mapping.get(stage, 15)

def seed_official():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Clear any synthetic / demo records to guarantee 0 synthetic records
        syn_ds = db.query(DataSource).filter(DataSource.source_type == "SYNTHETIC").all()
        for s in syn_ds:
            syn_projects = db.query(Project).filter(Project.data_source_id == s.id).all()
            p_ids = [p.id for p in syn_projects]
            if p_ids:
                db.query(RiskIndicator).filter(RiskIndicator.risk_assessment_id.in_(
                    db.query(RiskAssessment.id).filter(RiskAssessment.project_id.in_(p_ids))
                )).delete(synchronize_session=False)
                db.query(RiskAssessment).filter(RiskAssessment.project_id.in_(p_ids)).delete(synchronize_session=False)
                db.query(ProjectFinancials).filter(ProjectFinancials.project_id.in_(p_ids)).delete(synchronize_session=False)
                db.query(ProjectProgress).filter(ProjectProgress.project_id.in_(p_ids)).delete(synchronize_session=False)
                db.query(ProjectContractor).filter(ProjectContractor.project_id.in_(p_ids)).delete(synchronize_session=False)
                db.query(ReviewLog).filter(ReviewLog.project_id.in_(p_ids)).delete(synchronize_session=False)
                db.query(Review).filter(Review.project_id.in_(p_ids)).delete(synchronize_session=False)
                db.query(Project).filter(Project.id.in_(p_ids)).delete(synchronize_session=False)
            db.delete(s)
        db.commit()

        # 2. Users (Authorized role accounts for demo/evaluation)
        if not db.query(User).first():
            users = [
                User(username="admin_demo", role="Admin", password_hash=get_hash("demo123")),
                User(username="state_demo", role="State", password_hash=get_hash("demo123")),
                User(username="district_demo", role="District", password_hash=get_hash("demo123")),
                User(username="auditor_demo", role="Auditor", password_hash=get_hash("demo123"))
            ]
            db.add_all(users)
            db.commit()
            print("Created authorized role users.")

        # 3. Official Data Source with complete provenance
        ds = db.query(DataSource).filter(DataSource.source_name == "Official Government MPLADS Dataset (MoSPI / eSAKSHI)").first()
        if not ds:
            # Also check previous name
            ds = db.query(DataSource).filter(DataSource.source_name == "Official SIH Dataset").first()
        if not ds:
            ds = DataSource(
                source_name="Official Government MPLADS Dataset (MoSPI / eSAKSHI)",
                source_type="OFFICIAL",
                source_url="https://mplads.mospi.gov.in/",
                description="Official Government MPLADS dataset comprising 543 MP Allocation Limits and 2,462 authentic eSAKSHI work records",
                dataset_version="18th Lok Sabha (2024-2029)"
            )
            db.add(ds)
            db.commit()
            db.refresh(ds)
        else:
            ds.source_name = "Official Government MPLADS Dataset (MoSPI / eSAKSHI)"
            ds.source_type = "OFFICIAL"
            ds.source_url = "https://mplads.mospi.gov.in/"
            ds.description = "Official Government MPLADS dataset comprising 543 MP Allocation Limits and 2,462 authentic eSAKSHI work records"
            ds.dataset_version = "18th Lok Sabha (2024-2029)"
            db.commit()
        print(f"Verified Official DataSource ID {ds.id}")

        # 4. Ingest 543 Official MP Allocations
        csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "Data", "Official", "Allocated Limit for Honble MPs.csv")
        mp_count = 0
        if os.path.exists(csv_path):
            df_mps = pd.read_csv(csv_path)
            for _, row in df_mps.iterrows():
                name = str(row.get("Hon'ble Members of Parliaments", "")).strip()
                if not name or name == "Grand Total" or name == "nan":
                    continue
                state = str(row.get("State", "Unknown State")).strip()
                constituency = str(row.get("Constituency", "")).strip()
                amt_str = str(row.get("Allocated AMOUNT ( ₹ )", "0")).replace(",", "").strip()
                try:
                    amt = float(amt_str)
                except Exception:
                    amt = 0.0

                existing_mp = db.query(MP).filter(MP.name == name, MP.state == state).first()
                if not existing_mp:
                    new_mp = MP(
                        data_source_id=ds.id,
                        name=name,
                        state=state,
                        constituency=constituency,
                        status="Elected",
                        tenure="2024-2029",
                        allocated_amount=amt
                    )
                    db.add(new_mp)
                    mp_count += 1
                else:
                    existing_mp.constituency = constituency
                    existing_mp.allocated_amount = amt
            db.commit()
            print(f"Ingested / updated {mp_count} official MP allocation records from CSV.")

        # Build MP lookup mapping
        all_mps = db.query(MP).all()
        mp_by_name = {mp.name.strip().upper(): mp for mp in all_mps}
        default_mp = all_mps[0] if all_mps else None

        # 5. Ingest 2,462 Official eSAKSHI Work Records
        json_path = os.path.join(os.path.dirname(__file__), "..", "..", "Data", "Official", "eSAKSHI_Official_Works_Sample.json")
        work_count = 0
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                works_data = json.load(f)

            # Check if works are already loaded
            existing_work_ids = set(
                w[0] for w in db.query(Project.work_id).filter(Project.data_source_id == ds.id).all() if w[0]
            )

            new_projects = []
            financials_to_add = []
            progress_to_add = []

            for item in works_data:
                work_id_val = str(item.get("WORK_ID") or item.get("WORK_RECOMMENDATION_DTL_ID") or "").strip()
                if work_id_val and work_id_val in existing_work_ids:
                    continue

                mp_name_raw = str(item.get("MP_NAME") or "").strip().upper()
                matched_mp = mp_by_name.get(mp_name_raw, default_mp)

                s_amt_raw = item.get("SANCTION_AMOUNT") or item.get("RECOMMENDED_AMOUNT") or 0.0
                try:
                    sanctioned_amt = float(s_amt_raw)
                except Exception:
                    sanctioned_amt = 0.0

                s_date = parse_date(item.get("SANCTION_DATE")) or parse_date(item.get("RECOMMENDATION_DATE"))
                c_date = parse_date(item.get("ACTUAL_END_DATE"))
                p_comp = (s_date + timedelta(days=365)) if s_date else None

                rec_type = str(item.get("RECORD_STATUS_TYPE", "")).upper()
                w_stage = str(item.get("WORK_STAGE") or "")
                
                if rec_type == "COMPLETED" or w_stage == "Work Completed":
                    status = "COMPLETED"
                elif w_stage in ["Physical Inspection", "Work partially Completed", "Vendor Identification"]:
                    status = "IN_PROGRESS"
                else:
                    status = "SANCTIONED"

                category = clean_category(item.get("ACTIVITY_NAME"), str(item.get("WORK_CATEGORY") or "Normal/Others"))
                constituency = str(item.get("CONSTITUENCY") or "")
                state = str(item.get("STATE_NAME") or "")
                district = str(item.get("IDA_NAME") or "")
                location = f"{constituency}, {state}".strip(", ")
                description = str(item.get("WORK_DESCRIPTION") or "")

                proj = Project(
                    mp_id=matched_mp.id if matched_mp else 1,
                    data_source_id=ds.id,
                    work_id=work_id_val,
                    work_stage=w_stage or "Sanction",
                    district=district,
                    constituency=constituency,
                    description=description,
                    work_category=str(item.get("WORK_CATEGORY") or "Normal/Others"),
                    category=category,
                    sanctioned_amount=sanctioned_amt,
                    location=location,
                    latitude=None, # Strictly authentic: no fake coordinates
                    longitude=None,
                    planned_start=s_date,
                    planned_completion=p_comp,
                    actual_completion=c_date,
                    status=status
                )
                new_projects.append((proj, item, status, w_stage))

            # Batch insert projects
            for proj, item, status, w_stage in new_projects:
                db.add(proj)
            db.commit()

            # Add financials and progress
            for proj, item, status, w_stage in new_projects:
                act_amt = item.get("ACTUAL_AMOUNT")
                if act_amt is not None:
                    try:
                        exp = float(act_amt)
                        if exp > 0:
                            db.add(ProjectFinancials(project_id=proj.id, expenditure=exp))
                    except Exception:
                        pass

                proxy_pct = stage_to_proxy_pct(w_stage, status)
                db.add(ProjectProgress(project_id=proj.id, percentage=proxy_pct))
                work_count += 1
            db.commit()
            print(f"Ingested {work_count} authentic eSAKSHI project records.")

            # 6. Run Risk Engine on official works
            print("Evaluating risk intelligence across authentic government works...")
            from app.routers.projects import _get_project_context
            context = _get_project_context(db)
            df_p = context['df_projects']
            agg = RiskAggregator()

            assessments = []
            indicators = []

            for proj, _, _, _ in new_projects:
                match_row = df_p[df_p['id'] == proj.id]
                if match_row.empty:
                    continue
                target = match_row.iloc[0].to_dict()
                target['contractors'] = [] # No fake contractors

                res = agg.calculate_risk(target, context)
                ra = RiskAssessment(
                    project_id=proj.id,
                    score=res['score'],
                    overall_risk_level=res['level']
                )
                assessments.append((ra, res['indicators']))

            for ra, inds in assessments:
                db.add(ra)
            db.commit()

            for ra, inds in assessments:
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
                    indicators.append(ri)
            db.add_all(indicators)
            db.commit()
            print(f"Generated risk assessments for {len(assessments)} authentic works.")

        total_mps_db = db.query(MP).count()
        total_proj_db = db.query(Project).count()
        print(f"Seeding Complete! Database has {total_mps_db} Official MPs and {total_proj_db} Official Works.")

    finally:
        db.close()

if __name__ == "__main__":
    seed_official()
