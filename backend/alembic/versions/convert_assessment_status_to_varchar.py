"""convert assessment status to varchar

Revision ID: convert_assessment_status
Revises: add_solution_function_names
Create Date: 2026-02-26

Converts assessments.status from assessmentstatus enum to VARCHAR so we can store
'skipped' (and any future values) without altering the enum.
"""
from alembic import op

revision = 'convert_assessment_status'
down_revision = 'add_solution_function_names'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE assessments
        ALTER COLUMN status TYPE VARCHAR(20)
        USING status::text;
    """)
    op.execute("DROP TYPE IF EXISTS assessmentstatus CASCADE")


def downgrade() -> None:
    op.execute("CREATE TYPE assessmentstatus AS ENUM ('IN_PROGRESS', 'COMPLETED', 'ABANDONED', 'skipped')")
    op.execute("""
        ALTER TABLE assessments
        ALTER COLUMN status TYPE assessmentstatus
        USING status::assessmentstatus
    """)
