from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import Base, Project, ProjectProgress, ProjectFinancials
from datetime import datetime, date, timedelta

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

def setup_module():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: {'sub': 'test', 'role': 'Admin'}
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    today = date.today()
    
    # 1. HIGH burn-rate case (85% exp, 40% prog)
    p1 = Project(id=1, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")
    f1 = ProjectFinancials(project_id=1, expenditure=8500, updated_at=datetime.now())
    pr1 = ProjectProgress(project_id=1, percentage=40, reported_at=datetime.now())
    
    # 2. MEDIUM burn-rate case (95% exp, 60% prog)
    p2 = Project(id=2, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")
    f2 = ProjectFinancials(project_id=2, expenditure=9500, updated_at=datetime.now())
    pr2 = ProjectProgress(project_id=2, percentage=60, reported_at=datetime.now())
    
    # 3. Overlapping boundary case (95% exp, 85% prog -> no warning)
    p3 = Project(id=3, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")
    f3 = ProjectFinancials(project_id=3, expenditure=9500, updated_at=datetime.now())
    pr3 = ProjectProgress(project_id=3, percentage=85, reported_at=datetime.now())
    
    # 4. Healthy project
    p4 = Project(id=4, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING", planned_completion=today + timedelta(days=365))
    f4 = ProjectFinancials(project_id=4, expenditure=2000, updated_at=datetime.now())
    pr4 = ProjectProgress(project_id=4, percentage=25, reported_at=datetime.now())
    
    # 5. Overdue project
    p5 = Project(id=5, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING", planned_completion=today - timedelta(days=10))
    pr5 = ProjectProgress(project_id=5, percentage=90, reported_at=datetime.now())
    
    # 6. Approaching-deadline project (<90 days, <70% prog)
    p6 = Project(id=6, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING", planned_completion=today + timedelta(days=30))
    pr6 = ProjectProgress(project_id=6, percentage=60, reported_at=datetime.now())
    
    # 7. Stale progress report (>180 days, <100%)
    p7 = Project(id=7, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING", planned_completion=today + timedelta(days=365))
    pr7 = ProjectProgress(project_id=7, percentage=50, reported_at=datetime.now() - timedelta(days=200))
    
    # 8. Missing progress history (no pr8)
    p8 = Project(id=8, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")
    
    # 9. Invalid expenditure (-1000)
    p9 = Project(id=9, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")
    f9 = ProjectFinancials(project_id=9, expenditure=-1000, updated_at=datetime.now())
    
    # 10. Invalid progress (150%)
    p10 = Project(id=10, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="ONGOING")
    pr10 = ProjectProgress(project_id=10, percentage=150, reported_at=datetime.now())
    
    # 13. Completed project, shouldn't trigger deadline even if past planned
    p13 = Project(id=13, mp_id=1, data_source_id=1, sanctioned_amount=10000, status="COMPLETED", planned_completion=today - timedelta(days=10))

    db.add_all([
        p1, f1, pr1,
        p2, f2, pr2,
        p3, f3, pr3,
        p4, f4, pr4,
        p5, pr5,
        p6, pr6,
        p7, pr7,
        p8,
        p9, f9,
        p10, pr10,
        p13
    ])
    db.commit()
    db.close()


def test_early_warning_high_burn_rate():
    response = client.get("/api/projects/1/early-warning")
    assert response.status_code == 200
    data = response.json()
    assert any(w["type"] == "Burn Rate" and w["severity"] == "HIGH" for w in data["warnings"])
    assert not any(w["type"] == "Burn Rate" and w["severity"] == "MEDIUM" for w in data["warnings"])

def test_early_warning_medium_burn_rate():
    response = client.get("/api/projects/2/early-warning")
    assert response.status_code == 200
    data = response.json()
    assert any(w["type"] == "Burn Rate" and w["severity"] == "MEDIUM" for w in data["warnings"])
    assert not any(w["type"] == "Burn Rate" and w["severity"] == "HIGH" for w in data["warnings"])

def test_early_warning_boundary_no_burn_rate():
    response = client.get("/api/projects/3/early-warning")
    assert response.status_code == 200
    data = response.json()
    assert not any(w["type"] == "Burn Rate" for w in data["warnings"])

def test_early_warning_healthy():
    response = client.get("/api/projects/4/early-warning")
    assert response.status_code == 200
    data = response.json()
    assert len(data["warnings"]) == 0

def test_early_warning_overdue():
    response = client.get("/api/projects/5/early-warning")
    assert response.status_code == 200
    data = response.json()
    assert any(w["type"] == "Deadline" and w["severity"] == "HIGH" for w in data["warnings"])

def test_early_warning_approaching_deadline():
    response = client.get("/api/projects/6/early-warning")
    assert response.status_code == 200
    data = response.json()
    assert any(w["type"] == "Deadline" and w["severity"] == "MEDIUM" for w in data["warnings"])

def test_early_warning_stale_progress():
    response = client.get("/api/projects/7/early-warning")
    assert response.status_code == 200
    data = response.json()
    assert any(w["type"] == "Stagnation" and w["severity"] == "MEDIUM" for w in data["warnings"])

def test_early_warning_missing_progress():
    response = client.get("/api/projects/8/early-warning")
    assert response.status_code == 200
    data = response.json()
    # Missing progress means we shouldn't fabricate stagnation or burn rate
    assert len(data["warnings"]) == 0

def test_early_warning_invalid_expenditure():
    response = client.get("/api/projects/9/early-warning")
    assert response.status_code == 200
    data = response.json()
    assert any(w["type"] == "Data Anomaly" and w["severity"] == "LOW" and "negative" in w["message"].lower() for w in data["warnings"])

def test_early_warning_invalid_progress():
    response = client.get("/api/projects/10/early-warning")
    assert response.status_code == 200
    data = response.json()
    assert any(w["type"] == "Data Anomaly" and w["severity"] == "LOW" and "invalid" in w["message"].lower() for w in data["warnings"])

def test_early_warning_nonexistent():
    response = client.get("/api/projects/999/early-warning")
    assert response.status_code == 404
    
def test_early_warning_completed_project_no_deadline():
    response = client.get("/api/projects/13/early-warning")
    assert response.status_code == 200
    data = response.json()
    assert not any(w["type"] == "Deadline" for w in data["warnings"])


def teardown_module():
    app.dependency_overrides.clear()
