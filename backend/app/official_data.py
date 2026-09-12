"""Guards and query helpers for the official MPLADS application flow."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models


OFFICIAL = "OFFICIAL"


def official_projects_query(db: Session):
    """Return only projects backed by the authoritative official source."""
    return db.query(models.Project).join(models.DataSource).filter(
        models.DataSource.source_type == OFFICIAL
    )


def get_official_project_or_404(db: Session, project_id: int) -> models.Project:
    """Do not expose non-official records through primary-flow APIs."""
    project = official_projects_query(db).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Official project not found")
    return project


def runtime_data_summary(db: Session) -> dict:
    """Safe counts for operators; deliberately excludes credentials and URLs."""
    official_projects = official_projects_query(db).count()
    official_mps = db.query(models.MP).join(models.DataSource).filter(
        models.DataSource.source_type == OFFICIAL
    ).count()
    synthetic_projects = db.query(models.Project).join(models.DataSource).filter(
        models.DataSource.source_type == "SYNTHETIC"
    ).count()
    return {
        "official_projects": official_projects,
        "official_mps": official_mps,
        "synthetic_projects": synthetic_projects,
        "active_source": OFFICIAL,
    }
