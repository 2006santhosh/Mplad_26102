from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.auth_utils import get_current_user
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.models import Base, Project, RiskAssessment, ReviewLog, ProjectFinancials, ProjectProgress
import datetime

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
    
    p1 = Project(id=1, mp_id=1, data_source_id=1, status="ONGOING", category="Roads", sanctioned_amount=100)
    p2 = Project(id=2, mp_id=1, data_source_id=1, status="DELAYED", category="Roads", sanctioned_amount=200)
    p3 = Project(id=3, mp_id=1, data_source_id=1, status="ONGOING", category="Water", sanctioned_amount=300)
    p4 = Project(id=4, mp_id=1, data_source_id=1, status="COMPLETED", category=None, sanctioned_amount=50) # Unknown
    
    db.add_all([p1, p2, p3, p4])
    db.commit()
    
    # Financials and Progress
    db.add(ProjectFinancials(project_id=1, expenditure=50, updated_at=datetime.datetime.now(datetime.UTC)))
    db.add(ProjectFinancials(project_id=2, expenditure=200, updated_at=datetime.datetime.utcnow()))
    db.add(ProjectFinancials(project_id=4, expenditure=-10, updated_at=datetime.datetime.utcnow())) # Invalid negative
    
    db.add(ProjectProgress(project_id=1, percentage=40, reported_at=datetime.datetime.utcnow()))
    db.add(ProjectProgress(project_id=2, percentage=80, reported_at=datetime.datetime.utcnow()))
    
    # Risk assessments
    db.add(RiskAssessment(project_id=1, score=20, overall_risk_level="LOW", created_at=datetime.datetime(2025, 1, 1)))
    db.add(RiskAssessment(project_id=1, score=80, overall_risk_level="HIGH", created_at=datetime.datetime(2025, 2, 1))) # Latest is HIGH
    
    db.add(RiskAssessment(project_id=2, score=50, overall_risk_level="MEDIUM", created_at=datetime.datetime(2025, 1, 1)))
    
    # Review Logs
    db.add(ReviewLog(project_id=3, action="COMMENT", comment="test", created_at=datetime.datetime(2025, 1, 1)))
    db.add(ReviewLog(project_id=3, action="FLAG", comment="test", created_at=datetime.datetime(2025, 2, 1))) # Latest is FLAG
    db.add(ReviewLog(project_id=1, action="FLAG", comment="test", created_at=datetime.datetime(2025, 1, 1))) # p1 is also FLAG
    
    db.commit()
    db.close()

def test_get_dashboard_stats():
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_projects"] == 4
    
    # Delayed: p2
    assert data["delayed_projects"] == 1 
    
    # AI Risk Projects (HIGH/MEDIUM): p1 (HIGH), p2 (MEDIUM)
    assert data["ai_risk_projects"] == 2
    
    # Human Review Flags: p3, p1
    assert data["human_review_flags"] == 2
    
    # Projects Requiring Attention (Union of p1, p2, p3)
    assert data["projects_requiring_attention"] == 3
    
    # Financials
    assert data["total_sanctioned_amount"] == 650.0
    # exp: p1(50) + p2(200) + p4(ignored negative) = 250
    assert data["total_expenditure"] == 250.0
    assert data["utilization_percentage"] == (250.0 / 650.0) * 100
    
    # Progress
    assert data["projects_with_progress"] == 2
    assert data["average_progress"] == 60.0 # (40+80)/2
    
    # Risk Distribution
    rd = data["risk_distribution"]
    assert rd["LOW"] == 0 # p1 old assessment ignored
    assert rd["MEDIUM"] == 1 # p2
    assert rd["HIGH"] == 1 # p1
    assert rd["CRITICAL"] == 0
    
    # Categories
    categories = data["projects_by_category"]
    assert len(categories) == 3
    assert categories[0]["category"] == "Roads"
    assert categories[0]["count"] == 2


def teardown_module():
    app.dependency_overrides.clear()
