"""add_anti_cheat_tables

Revision ID: add_anti_cheat_tables
Revises: add_skipped_status
Create Date: 2025-02-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_anti_cheat_tables'
down_revision = 'add_skipped_status'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create assessment_violations table
    op.create_table(
        'assessment_violations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('violation_type', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assessment_violations_id'), 'assessment_violations', ['id'], unique=False)
    
    # Add anti-cheating fields to assessments table
    op.add_column('assessments', sa.Column('violation_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('assessments', sa.Column('auto_submitted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('assessments', sa.Column('server_start_time', sa.DateTime(timezone=True), nullable=True))
    
    # Set server_start_time to started_at for existing assessments
    op.execute("UPDATE assessments SET server_start_time = started_at WHERE server_start_time IS NULL")


def downgrade() -> None:
    # Remove anti-cheating fields from assessments table
    op.drop_column('assessments', 'server_start_time')
    op.drop_column('assessments', 'auto_submitted')
    op.drop_column('assessments', 'violation_count')
    
    # Drop assessment_violations table
    op.drop_index(op.f('ix_assessment_violations_id'), table_name='assessment_violations')
    op.drop_table('assessment_violations')
