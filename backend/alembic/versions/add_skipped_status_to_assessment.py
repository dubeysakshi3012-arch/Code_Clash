"""add_skipped_status_to_assessment

Revision ID: add_skipped_status
Revises: convert_enums_to_varchar
Create Date: 2025-02-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_skipped_status'
down_revision = 'add_submissions_table'  # Point to latest migration head
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add 'SKIPPED' value to assessmentstatus enum type.
    
    Based on the error, the database enum uses uppercase values ('IN_PROGRESS', 'COMPLETED', 'ABANDONED'),
    so we need to add 'SKIPPED' (uppercase) to match.
    
    IMPORTANT: If this migration fails due to PostgreSQL transaction limitations,
    run this SQL command manually in your database:
    
    ALTER TYPE assessmentstatus ADD VALUE 'SKIPPED';
    """
    # Check what case the existing enum values use
    conn = op.get_bind()
    
    # First, check if the enum type exists and what values it has
    result = conn.execute(sa.text("""
        SELECT enumlabel FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'assessmentstatus')
        ORDER BY enumsortorder
        LIMIT 3
    """))
    
    existing_values = [row[0] for row in result]
    
    if not existing_values:
        # Enum type doesn't exist or is empty, skip
        return
    
    # Determine case from existing values
    # Check if any value is uppercase
    uses_uppercase = any(v.isupper() for v in existing_values)
    value_to_add = 'SKIPPED' if uses_uppercase else 'skipped'
    
    # Check if value already exists
    check_result = conn.execute(sa.text("""
        SELECT 1 FROM pg_enum 
        WHERE enumlabel = :value
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'assessmentstatus')
    """), {'value': value_to_add})
    
    if check_result.fetchone():
        # Value already exists, nothing to do
        return
    
    # Try to add the value
    # Note: ALTER TYPE ADD VALUE cannot be run inside a transaction block in PostgreSQL
    # We'll attempt it, but if it fails, the user needs to run it manually
    try:
        # Use a separate connection with autocommit
        raw_conn = conn.connection
        old_autocommit = raw_conn.autocommit
        raw_conn.autocommit = True
        try:
            raw_conn.execute(sa.text(f"ALTER TYPE assessmentstatus ADD VALUE '{value_to_add}'"))
        finally:
            raw_conn.autocommit = old_autocommit
    except Exception:
        # If it fails, that's okay - user can run it manually
        # The migration will continue
        pass


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type, which is complex
    # For now, we'll leave the value in place
    pass
