"""add risk_history table

Revision ID: 144df3b5a80e
Revises: 
Create Date: 2026-08-30 16:06:58.242482

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '144df3b5a80e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema by creating risk_history table."""
    op.create_table(
        "risk_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("risk_score", sa.Integer, nullable=False),
        sa.Column("risk_level", sa.String(length=50), nullable=False),
        sa.Column("indicator_snapshot", sa.JSON, nullable=True),
        sa.Column("recorded_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

def downgrade() -> None:
    """Downgrade schema by dropping risk_history table."""
    op.drop_table("risk_history")
