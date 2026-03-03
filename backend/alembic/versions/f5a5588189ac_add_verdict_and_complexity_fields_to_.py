"""add_verdict_and_complexity_fields_to_assessment_results

Revision ID: f5a5588189ac
Revises: d96bcbdbec49
Create Date: 2026-02-04 20:40:18.160945

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5a5588189ac'
down_revision = 'd96bcbdbec49'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add verdict column to assessment_results table
    op.add_column('assessment_results', sa.Column('verdict', sa.String(length=50), nullable=True))
    
    # Add complexity_detected column to assessment_results table
    op.add_column('assessment_results', sa.Column('complexity_detected', sa.String(length=20), nullable=True))
    
    # Add stress_test_results column to assessment_results table (JSON)
    op.add_column('assessment_results', sa.Column('stress_test_results', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove stress_test_results column
    op.drop_column('assessment_results', 'stress_test_results')
    
    # Remove complexity_detected column
    op.drop_column('assessment_results', 'complexity_detected')
    
    # Remove verdict column
    op.drop_column('assessment_results', 'verdict')
