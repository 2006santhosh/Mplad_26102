"""phase_5_patch

Revision ID: 42a54cbdf4f0
Revises: 5f563d161682
Create Date: 2026-09-08 15:20:12.208295

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42a54cbdf4f0'
down_revision: Union[str, Sequence[str], None] = '5f563d161682'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Modify the column to be nullable=True and remove default
    with op.batch_alter_table('risk_assessments', schema=None) as batch_op:
        batch_op.alter_column('engine_version',
               existing_type=sa.VARCHAR(),
               nullable=True,
               server_default=None)

    # 2. Correct historical records where assessment_status IS NULL
    # Using raw SQL
    op.execute("UPDATE risk_assessments SET engine_version = NULL WHERE assessment_status IS NULL")


def downgrade() -> None:
    # 1. Revert historical records (Optional/Best-Effort fallback)
    # We set them back to '5.0.0' to satisfy NOT NULL constraint
    op.execute("UPDATE risk_assessments SET engine_version = '5.0.0' WHERE engine_version IS NULL")

    # 2. Re-apply NOT NULL constraint and default
    with op.batch_alter_table('risk_assessments', schema=None) as batch_op:
        batch_op.alter_column('engine_version',
               existing_type=sa.VARCHAR(),
               nullable=False,
               server_default='5.0.0')
