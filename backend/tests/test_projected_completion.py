from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import Base, Project, ProjectProgress
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
    
    # 1. On time completion expected
    p1 = Project(id=1, mp_id=1, data_source_id=1, status="ONGOING", planned_start=today - timedelta(days=100), planned_completion=today + timedelta(days=100))
    pr1a = ProjectProgress(project_id=1, percentage=0, reported_at=datetime.now() - timedelta(days=100))
    pr1b = ProjectProgress(project_id=1, percentage=50, reported_at=datetime.now()) # 50% in 100 days -> 0.5/day. Needs 100 days.
    
    # 2. MEDIUM projected delay (> 20%, <= 50%)
    # duration = 200 days. delay > 40, <= 100
    p2 = Project(id=2, mp_id=1, data_source_id=1, status="ONGOING", planned_start=today - timedelta(days=100), planned_completion=today + timedelta(days=100))
    pr2a = ProjectProgress(project_id=2, percentage=0, reported_at=datetime.now() - timedelta(days=100))
    pr2b = ProjectProgress(project_id=2, percentage=40, reported_at=datetime.now()) # 40% in 100 days -> 0.4/day. Needs 150 days. Delay = 150 - 100 = 50. 50/200 = 25%
    
    # 3. HIGH projected delay (> 50%)
    # duration = 200 days. delay > 100
    p3 = Project(id=3, mp_id=1, data_source_id=1, status="ONGOING", planned_start=today - timedelta(days=100), planned_completion=today + timedelta(days=100))
    pr3a = ProjectProgress(project_id=3, percentage=0, reported_at=datetime.now() - timedelta(days=100))
    pr3b = ProjectProgress(project_id=3, percentage=20, reported_at=datetime.now()) # 20% in 100 days -> 0.2/day. Needs 400 days. Delay = 400 - 100 = 300. 300/200 = 150%
    
    # 4. Zero/non-positive velocity (HIGH risk)
    p4 = Project(id=4, mp_id=1, data_source_id=1, status="ONGOING", planned_start=today - timedelta(days=100), planned_completion=today + timedelta(days=100))
    pr4a = ProjectProgress(project_id=4, percentage=20, reported_at=datetime.now() - timedelta(days=100))
    pr4b = ProjectProgress(project_id=4, percentage=20, reported_at=datetime.now()) # 0 progress
    
    # 5. Multiple observations -> uses earliest and latest valid
    p5 = Project(id=5, mp_id=1, data_source_id=1, status="ONGOING", planned_start=today - timedelta(days=100), planned_completion=today + timedelta(days=100))
    pr5a = ProjectProgress(project_id=5, percentage=10, reported_at=datetime.now() - timedelta(days=100))
    pr5b = ProjectProgress(project_id=5, percentage=20, reported_at=datetime.now() - timedelta(days=50))
    pr5c = ProjectProgress(project_id=5, percentage=60, reported_at=datetime.now()) # Total 50% in 100 days -> 0.5/day. Needs 80 days -> Delay = -20 (0). LOW risk.

    # 6. Insufficient history (<2 valid)
    p6 = Project(id=6, mp_id=1, data_source_id=1, status="ONGOING", planned_start=today - timedelta(days=100), planned_completion=today + timedelta(days=100))
    pr6a = ProjectProgress(project_id=6, percentage=50, reported_at=datetime.now())

    # 7. Missing planned dates
    p7 = Project(id=7, mp_id=1, data_source_id=1, status="ONGOING")
    pr7a = ProjectProgress(project_id=7, percentage=0, reported_at=datetime.now() - timedelta(days=100))
    pr7b = ProjectProgress(project_id=7, percentage=50, reported_at=datetime.now())

    # 8. Invalid progress data
    p8 = Project(id=8, mp_id=1, data_source_id=1, status="ONGOING", planned_start=today - timedelta(days=100), planned_completion=today + timedelta(days=100))
    pr8a = ProjectProgress(project_id=8, percentage=-10, reported_at=datetime.now() - timedelta(days=100))
    pr8b = ProjectProgress(project_id=8, percentage=50, reported_at=datetime.now())
    # effectively only 1 valid observation

    # 9. Completed project
    p9 = Project(id=9, mp_id=1, data_source_id=1, status="COMPLETED", planned_start=today - timedelta(days=100), planned_completion=today + timedelta(days=100), actual_completion=today)

    db.add_all([
        p1, pr1a, pr1b,
        p2, pr2a, pr2b,
        p3, pr3a, pr3b,
        p4, pr4a, pr4b,
        p5, pr5a, pr5b, pr5c,
        p6, pr6a,
        p7, pr7a, pr7b,
        p8, pr8a, pr8b,
        p9
    ])
    db.commit()
    db.close()

def test_projected_completion_on_time():
    response = client.get("/api/projected-completion/1")
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "LOW"
    assert data["velocity"] == 0.5
    assert data["delay_days"] == 0

def test_projected_completion_medium_delay():
    response = client.get("/api/projected-completion/2")
    assert response.status_code == 200
    assert response.json()["risk_level"] == "MEDIUM"

def test_projected_completion_high_delay():
    response = client.get("/api/projected-completion/3")
    assert response.status_code == 200
    assert response.json()["risk_level"] == "HIGH"

def test_projected_completion_zero_velocity():
    response = client.get("/api/projected-completion/4")
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "HIGH"
    assert "stalled" in data["explanation"].lower()
    
def test_projected_completion_multiple_observations():
    response = client.get("/api/projected-completion/5")
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "LOW"
    assert data["velocity"] == 0.5
    
def test_projected_completion_insufficient_history():
    response = client.get("/api/projected-completion/6")
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "UNKNOWN"
    assert "insufficient" in data["explanation"].lower()

def test_projected_completion_missing_dates():
    response = client.get("/api/projected-completion/7")
    assert response.status_code == 200
    assert response.json()["risk_level"] == "UNKNOWN"

def test_projected_completion_invalid_progress():
    response = client.get("/api/projected-completion/8")
    assert response.status_code == 200
    assert response.json()["risk_level"] == "UNKNOWN"

def test_projected_completion_completed():
    response = client.get("/api/projected-completion/9")
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "LOW"
    assert "completed" in data["explanation"].lower()
    assert data["delay_days"] == 0
    
def test_projected_completion_nonexistent():
    response = client.get("/api/projected-completion/999")
    assert response.status_code == 404


def teardown_module():
    app.dependency_overrides.clear()
