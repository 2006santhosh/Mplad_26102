import json
import os

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth_utils import get_current_user
from app.database import get_db
from app.main import app
from app.models import Base, DataSource, EarlyWarning, MP, Project, User

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)


def override_get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
    source = DataSource(id=1, source_name="Official test source", source_type="OFFICIAL")
    mp = MP(id=1, data_source_id=1, name="Test MP", state="Test State")
    project = Project(id=1, mp_id=1, data_source_id=1, work_id="W-12", category="Road", sanctioned_amount=1000, status="ONGOING")
    user = User(id=1, username="phase12_admin", role="Admin", password_hash=bcrypt.hashpw(b"test", bcrypt.gensalt()).decode())
    warning = EarlyWarning(id=1, project_id=1, warning_type="TEST", warning_level="HIGH", status="OPEN", title="Test warning", explanation="Test evidence", trigger_signature="phase12-test", engine_version="test")
    db.add_all([source, mp, project, user, warning])
    db.commit()
    db.close()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: {"sub": "phase12_admin", "role": "Admin"}


def teardown_module():
    app.dependency_overrides.clear()


def test_warning_lifecycle_and_invalid_transition():
    response = client.patch("/api/projects/1/early-warning/1", json={"status": "ACKNOWLEDGED"})
    assert response.status_code == 200
    assert response.json()["status"] == "ACKNOWLEDGED"
    response = client.patch("/api/projects/1/early-warning/1", json={"status": "OPEN"})
    assert response.status_code == 422
    response = client.patch("/api/projects/1/early-warning/1", json={"status": "UNDER_REVIEW"})
    assert response.status_code == 200
    response = client.patch("/api/projects/1/early-warning/1", json={"status": "RESOLVED"})
    assert response.status_code == 200
    db = Session()
    from app.models import AuditLog
    audits = db.query(AuditLog).filter(AuditLog.entity_id == 1, AuditLog.entity_type == "EarlyWarning").all()
    assert len(audits) >= 3
    assert any(a.action == "EARLY_WARNING_STATUS_CHANGED" and "ACKNOWLEDGED" in a.details for a in audits)
    assert any(a.action == "EARLY_WARNING_STATUS_CHANGED" and "RESOLVED" in a.details for a in audits)
    assert db.query(EarlyWarning).filter(EarlyWarning.id == 1).one().status == "RESOLVED"
    db.close()


def test_project_json_export_is_authenticated_and_data_limited():
    response = client.get("/api/reports/projects/1.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["official_project"]["work_id"] == "W-12"
    assert payload["official_project"]["latitude"] is None
    assert payload["provenance"]["latitude"] == "UNAVAILABLE"
    assert any("DATA-LIMITED" in item for item in payload["limitations"])
    
    db = Session()
    from app.models import AuditLog
    audit = db.query(AuditLog).filter(AuditLog.entity_id == 1, AuditLog.entity_type == "Project", AuditLog.action == "PROJECT_REPORT_EXPORTED").first()
    assert audit is not None
    assert audit.user_id == 1
    db.close()


def test_pre_sanction_assessment_is_persisted_and_retrievable():
    response = client.post("/api/pre-sanction/", json={"category": "Road", "sanctioned_amount": 1000, "location": "Test proposal", "planned_duration_days": 180})
    assert response.status_code == 200
    
    db = Session()
    from app.models import AuditLog
    audit = db.query(AuditLog).filter(AuditLog.entity_type == "PreSanctionAssessment", AuditLog.action == "PRE_SANCTION_ASSESSMENT").first()
    assert audit is not None
    assert audit.user_id == 1
    db.close()
    
    history = client.get("/api/pre-sanction/history")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["provenance"] == "AI ASSESSMENT"
