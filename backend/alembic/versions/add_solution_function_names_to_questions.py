"""add solution_function_names to questions

Revision ID: add_solution_function_names
Revises: add_match_submissions
Create Date: 2025-02-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_solution_function_names'
down_revision = 'add_match_submissions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'questions',
        sa.Column('solution_function_names', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('questions', 'solution_function_names')
