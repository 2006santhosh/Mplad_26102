from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import DataSource, Base, Project, ProjectProgress, ProjectFinancials
from datetime import datetime, date

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    if not db.query(DataSource).filter(DataSource.id == 1).first():
        db.add(DataSource(id=1, source_name="Official Data", source_type="OFFICIAL"))
        db.commit()
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
    
    # Project 1: Both histories
    p1 = Project(id=1, mp_id=1, data_source_id=1, category="Road", sanctioned_amount=10000, status="ONGOING")
    # Project 2: Financial only
    p2 = Project(id=2, mp_id=1, data_source_id=1, category="Road", sanctioned_amount=10000, status="ONGOING")
    # Project 3: Progress only
    p3 = Project(id=3, mp_id=1, data_source_id=1, category="Road", sanctioned_amount=10000, status="ONGOING")
    # Project 4: Empty history
    p4 = Project(id=4, mp_id=1, data_source_id=1, category="Road", sanctioned_amount=10000, status="ONGOING")
    # Project 5: Invalid values and missing values and duplicate timestamps
    p5 = Project(id=5, mp_id=1, data_source_id=1, category="Road", sanctioned_amount=10000, status="ONGOING")
    
    db.add_all([p1, p2, p3, p4, p5])
    
    # Project 1 records (with duplicate timestamp for progress, unordered insertions)
    f1a = ProjectFinancials(project_id=1, expenditure=1000, updated_at=datetime(2023, 2, 1))
    f1b = ProjectFinancials(project_id=1, expenditure=500, updated_at=datetime(2023, 1, 1)) # Earlier
    pr1a = ProjectProgress(project_id=1, percentage=10, reported_at=datetime(2023, 1, 1))
    pr1b = ProjectProgress(project_id=1, percentage=15, reported_at=datetime(2023, 1, 1)) # Duplicate timestamp
    pr1c = ProjectProgress(project_id=1, percentage=50, reported_at=datetime(2023, 3, 1))
    
    # Project 2 records
    f2 = ProjectFinancials(project_id=2, expenditure=2000, updated_at=datetime(2023, 1, 1))
    
    # Project 3 records
    pr3 = ProjectProgress(project_id=3, percentage=30, reported_at=datetime(2023, 1, 1))
    
    # Project 5 records (Invalid, negative, >100, None)
    f5a = ProjectFinancials(project_id=5, expenditure=-500, updated_at=datetime(2023, 1, 1))
    f5b = ProjectFinancials(project_id=5, expenditure=-10, updated_at=datetime(2023, 2, 1))
    pr5a = ProjectProgress(project_id=5, percentage=150, reported_at=datetime(2023, 1, 1))
    pr5b = ProjectProgress(project_id=5, percentage=-10, reported_at=datetime(2023, 2, 1))
    pr5c = ProjectProgress(project_id=5, percentage=-20, reported_at=datetime(2023, 3, 1))

    db.add_all([f1a, f1b, pr1a, pr1b, pr1c, f2, pr3, f5a, f5b, pr5a, pr5b, pr5c])
    db.commit()
    db.close()


def test_get_trends_both_and_chronology():
    response = client.get("/api/trends/1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    exp_trend = next(t for t in data if t["type"] == "expenditure")
    assert len(exp_trend["data"]) == 2
    # Check chronological sort: Jan 1 (500) before Feb 1 (1000)
    assert exp_trend["data"][0]["value"] == 500
    assert exp_trend["data"][1]["value"] == 1000
    
    prog_trend = next(t for t in data if t["type"] == "progress")
    assert len(prog_trend["data"]) == 3
    # Check duplicate timestamp handled and sorted correctly
    assert prog_trend["data"][0]["value"] == 10
    assert prog_trend["data"][1]["value"] == 15
    assert prog_trend["data"][2]["value"] == 50


def test_get_trends_financial_only():
    response = client.get("/api/trends/2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["type"] == "expenditure"


def test_get_trends_progress_only():
    response = client.get("/api/trends/3")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["type"] == "progress"


def test_get_trends_empty_history():
    response = client.get("/api/trends/4")
    assert response.status_code == 200
    assert response.json() == []


def test_get_trends_nonexistent():
    response = client.get("/api/trends/999")
    assert response.status_code == 404


def test_get_trends_invalid_values():
    response = client.get("/api/trends/5")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    exp_trend = next(t for t in data if t["type"] == "expenditure")
    # None value should be skipped, length 1
    assert len(exp_trend["data"]) == 2
    assert exp_trend["data"][0]["is_invalid"] is True

    prog_trend = next(t for t in data if t["type"] == "progress")
    # >100 and negative are invalid, None is skipped, so length 2
    assert len(prog_trend["data"]) == 3
    assert prog_trend["data"][0]["is_invalid"] is True
    assert prog_trend["data"][1]["is_invalid"] is True
    assert "Invalid" in prog_trend["data"][0]["note"]
    assert prog_trend["data"][1]["value"] == -10
    assert prog_trend["data"][1]["is_invalid"] == True


def teardown_module():
    app.dependency_overrides.clear()
