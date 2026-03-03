"""add_attempts_count_to_assessment_results

Revision ID: d96bcbdbec49
Revises: convert_enums_to_varchar
Create Date: 2026-02-04 16:12:35.785617

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd96bcbdbec49'
down_revision = 'convert_enums_to_varchar'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add attempts_count column to assessment_results table
    op.add_column('assessment_results', sa.Column('attempts_count', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    # Remove attempts_count column from assessment_results table
    op.drop_column('assessment_results', 'attempts_count')
