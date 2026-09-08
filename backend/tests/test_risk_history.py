from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import Base, Project, RiskAssessment, RiskIndicator
from datetime import datetime

# Use an in-memory SQLite database for fast testing
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
    
    # Project
    p1 = Project(id=1, mp_id=1, data_source_id=1, category="Road", sanctioned_amount=10000, status="ONGOING")
    db.add(p1)
    
    # Risk Assessments
    ra1 = RiskAssessment(project_id=1, score=50, overall_risk_level="MEDIUM", created_at=datetime(2023, 1, 1))
    ra2 = RiskAssessment(project_id=1, score=80, overall_risk_level="HIGH", created_at=datetime(2023, 2, 1))
    db.add_all([ra1, ra2])
    db.commit()
    
    # Indicators
    ri1 = RiskIndicator(risk_assessment_id=ra1.id, indicator="Cost", status="ASSESSABLE", severity="MEDIUM", explanation="Test1")
    ri2 = RiskIndicator(risk_assessment_id=ra2.id, indicator="Delay", status="ASSESSABLE", severity="HIGH", explanation="Test2")
    db.add_all([ri1, ri2])
    db.commit()
    db.close()

def test_get_risk_history():
    response = client.get("/api/projects/1/risk/history")
    assert response.status_code == 200
    data = response.json()
    
    # Should be sorted descending by created_at, so ra2 then ra1
    assert "assessments" in data
    assessments = data["assessments"]
    assert len(assessments) == 2
    assert assessments[0]["risk_score"] == 80
    assert assessments[0]["risk_level"] == "HIGH"
    
    assert assessments[1]["risk_score"] == 50
    assert assessments[1]["risk_level"] == "MEDIUM"
    
    assert data["risk_trend_status"] == "INCREASING"
    assert data["score_change_absolute"] == 30

def test_get_risk_history_nonexistent():
    # Since the project doesn't exist, we added a 404 handler
    response = client.get("/api/projects/999/risk/history")
    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def teardown_module():
    app.dependency_overrides.clear()
