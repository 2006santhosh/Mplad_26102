"""phase_9_review_cases

Revision ID: a1b2c3d4e5f6
Revises: 16cf8924411d
Create Date: 2026-09-09 23:00:00.000000

Phase 9 — Investigation Workflow, Audit Trail & Case Management
Creates:
  - review_cases  (central case entity)
  - case_notes    (immutable official notes, append-only)
  - case_audit_events  (append-only audit trail)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '16cf8924411d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # review_cases
    op.create_table(
        'review_cases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('case_reference', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='OPEN'),
        sa.Column('priority', sa.String(), nullable=False, server_default='MEDIUM'),
        sa.Column('opened_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('assigned_to_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('initial_note', sa.Text(), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('triggering_signals', sa.JSON(), nullable=True),
        sa.Column('opened_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('case_reference'),
    )
    op.create_index('ix_review_cases_id', 'review_cases', ['id'])
    op.create_index('ix_review_cases_project_id', 'review_cases', ['project_id'])
    op.create_index('ix_review_cases_status', 'review_cases', ['status'])
    op.create_index('ix_review_cases_case_reference', 'review_cases', ['case_reference'])

    # case_notes (immutable — no DELETE endpoint)
    op.create_table(
        'case_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('review_cases.id'), nullable=False),
        sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('provenance', sa.String(), nullable=False, server_default='OFFICIAL ACTION'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_case_notes_id', 'case_notes', ['id'])
    op.create_index('ix_case_notes_case_id', 'case_notes', ['case_id'])

    # case_audit_events (append-only — no DELETE endpoint)
    op.create_table(
        'case_audit_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('review_cases.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('previous_status', sa.String(), nullable=True),
        sa.Column('new_status', sa.String(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('provenance', sa.String(), nullable=False, server_default='OFFICIAL ACTION'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_case_audit_events_id', 'case_audit_events', ['id'])
    op.create_index('ix_case_audit_events_case_id', 'case_audit_events', ['case_id'])
    op.create_index('ix_case_audit_events_project_id', 'case_audit_events', ['project_id'])


def downgrade() -> None:
    op.drop_table('case_audit_events')
    op.drop_table('case_notes')
    op.drop_table('review_cases')
