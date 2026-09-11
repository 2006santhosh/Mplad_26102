"""phase 12 completion metadata"""
from alembic import op
import sqlalchemy as sa

revision = 'c12_phase12_completion'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('pre_sanction_assessments', sa.Column('assessment_status', sa.String(), nullable=True))
    op.add_column('pre_sanction_assessments', sa.Column('assessment_coverage_pct', sa.Float(), nullable=True))
    op.add_column('pre_sanction_assessments', sa.Column('risk_reasons', sa.JSON(), nullable=True))
    op.add_column('pre_sanction_assessments', sa.Column('indicators', sa.JSON(), nullable=True))
    op.add_column('pre_sanction_assessments', sa.Column('provenance', sa.String(), server_default='AI ASSESSMENT', nullable=False))
    op.add_column('pre_sanction_assessments', sa.Column('engine_version', sa.String(), nullable=True))

def downgrade():
    for column in ['engine_version', 'provenance', 'indicators', 'risk_reasons', 'assessment_coverage_pct', 'assessment_status']:
        op.drop_column('pre_sanction_assessments', column)