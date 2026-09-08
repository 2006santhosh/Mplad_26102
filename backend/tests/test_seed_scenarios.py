import os
import pytest
from app.main import app
os.environ["JWT_SECRET_KEY"] = "test_secret_for_pytest"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from scripts.seed_synthetic_data import seed_demo_data
from app.models import Project, ProjectProgress, ProjectFinancials, RiskAssessment, DataSource, MP, User

TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def isolated_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Need at least one MP for seeding to work
    if not db.query(MP).first():
        ds = DataSource(source_name="Test DS", source_type="OFFICIAL")
        db.add(ds)
        db.commit()
        db.add(MP(data_source_id=ds.id, name="Test MP", state="Test", status="Elected"))
        db.commit()

    yield db
    db.close()

def test_seed_is_idempotent(isolated_db):
    seed_demo_data(isolated_db)
    count_first = isolated_db.query(Project).join(DataSource).filter(DataSource.source_type == "SYNTHETIC").count()
    assert count_first > 0
    
    # Run again
    seed_demo_data(isolated_db)
    count_second = isolated_db.query(Project).join(DataSource).filter(DataSource.source_type == "SYNTHETIC").count()
    assert count_second > 0

def test_scenarios_exist(isolated_db):
    seed_demo_data(isolated_db)
    projects = isolated_db.query(Project).join(DataSource).filter(DataSource.source_type == "SYNTHETIC").all()
    names = [p.location for p in projects]
    
    # At least some of these base strings should be present in the generated names
    assert any("Village School" in n for n in names)
    assert any("District Highway" in n for n in names)
    assert any("Rural Clinic" in n for n in names)

def test_no_synthetic_is_official(isolated_db):
    seed_demo_data(isolated_db)
    synthetic_projects = isolated_db.query(Project).join(DataSource).filter(DataSource.source_type == "SYNTHETIC").all()
    assert len(synthetic_projects) > 0
    for p in synthetic_projects:
        assert p.data_source.source_type != "OFFICIAL"

def test_coordinates_are_valid(isolated_db):
    seed_demo_data(isolated_db)
    synthetic_projects = isolated_db.query(Project).join(DataSource).filter(DataSource.source_type == "SYNTHETIC").all()
    for p in synthetic_projects:
        assert p.latitude is not None
        assert p.longitude is not None
        assert -90 <= p.latitude <= 90
        assert -180 <= p.longitude <= 180

def test_scenario_b_mismatch(isolated_db):
    p = isolated_db.query(Project).filter(Project.location.like("%District Highway%")).first()
    assert p is not None
    assert p.sanctioned_amount == 50000000
    assert p.progress[0].percentage == 20
    assert p.financials[0].expenditure == 45000000

def test_scenario_c_delayed(isolated_db):
    p = isolated_db.query(Project).filter(Project.location.like("%Rural Clinic%")).first()
    assert p is not None
    assert p.status == "DELAYED"

def test_risk_engine_generated_assessments(isolated_db):
    seed_demo_data(isolated_db)
    synthetic_projects = isolated_db.query(Project).join(DataSource).filter(DataSource.source_type == "SYNTHETIC").all()
    
    for p in synthetic_projects:
        assert len(p.risk_assessments) == 1
        assert p.risk_assessments[0].overall_risk_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL", "LIMITED"]


def teardown_module():
    app.dependency_overrides.clear()
