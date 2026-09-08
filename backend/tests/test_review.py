from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import Base, Project, ReviewLog

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
    
    p1 = Project(id=1, mp_id=1, data_source_id=1, status="ONGOING")
    db.add(p1)
    db.commit()
    db.close()

def test_add_review_log_comment():
    payload = {
        "reviewed_by": "Test User",
        "action": "COMMENT",
        "comment": "This is a comment."
    }
    response = client.post("/api/projects/1/review/", json=payload)
    assert response.status_code == 200
    
    # Check that project status did NOT mutate
    db = TestingSessionLocal()
    p = db.query(Project).filter(Project.id == 1).first()
    assert p.status == "ONGOING"
    db.close()

def test_add_review_log_flag():
    payload = {
        "reviewed_by": "Test User",
        "action": "FLAG",
        "comment": "This requires attention."
    }
    response = client.post("/api/projects/1/review/", json=payload)
    assert response.status_code == 200
    
    # Check that project status did NOT mutate
    db = TestingSessionLocal()
    p = db.query(Project).filter(Project.id == 1).first()
    assert p.status == "ONGOING"
    db.close()

def test_add_review_invalid_action():
    payload = {
        "reviewed_by": "Test User",
        "action": "INVALID_ACTION",
        "comment": "Testing invalid action."
    }
    response = client.post("/api/projects/1/review/", json=payload)
    assert response.status_code == 422 # Pydantic validation error

def test_add_review_empty_comment():
    payload = {
        "reviewed_by": "Test User",
        "action": "FLAG",
        "comment": "   " # Whitespace
    }
    response = client.post("/api/projects/1/review/", json=payload)
    assert response.status_code == 422 # Pydantic validation error

def test_get_review_logs():
    response = client.get("/api/projects/1/review/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["action"] in ["COMMENT", "FLAG"]

def test_add_review_nonexistent_project():
    payload = {
        "reviewed_by": "Test User",
        "action": "COMMENT",
        "comment": "Test."
    }
    response = client.post("/api/projects/999/review/", json=payload)
    assert response.status_code == 404

def test_get_review_nonexistent_project():
    response = client.get("/api/projects/999/review/")
    assert response.status_code == 404


def teardown_module():
    app.dependency_overrides.clear()
