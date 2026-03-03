"""convert_enums_to_varchar

Revision ID: convert_enums_to_varchar
Revises: seed_assessment_questions
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'convert_enums_to_varchar'
down_revision = 'seed_assessment_questions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert question_type enum column to VARCHAR
    op.execute("""
        ALTER TABLE questions 
        ALTER COLUMN question_type TYPE VARCHAR(50) 
        USING question_type::text;
    """)
    
    # Convert section enum columns to VARCHAR
    op.execute("""
        ALTER TABLE questions 
        ALTER COLUMN section TYPE VARCHAR(10) 
        USING section::text;
    """)
    
    op.execute("""
        ALTER TABLE assessments 
        ALTER COLUMN current_section TYPE VARCHAR(10) 
        USING current_section::text;
    """)
    
    op.execute("""
        ALTER TABLE assessment_sections 
        ALTER COLUMN section TYPE VARCHAR(10) 
        USING section::text;
    """)
    
    op.execute("""
        ALTER TABLE assessment_results 
        ALTER COLUMN section TYPE VARCHAR(10) 
        USING section::text;
    """)
    
    # Drop the enum types (they're no longer needed)
    op.execute("DROP TYPE IF EXISTS questiontype CASCADE")
    op.execute("DROP TYPE IF EXISTS assessmentsection CASCADE")


def downgrade() -> None:
    # Recreate enum types
    op.execute("CREATE TYPE questiontype AS ENUM ('mcq', 'logic_trace', 'coding')")
    op.execute("CREATE TYPE assessmentsection AS ENUM ('A', 'B', 'C')")
    
    # Convert back to enum types
    op.execute("""
        ALTER TABLE questions 
        ALTER COLUMN question_type TYPE questiontype 
        USING question_type::questiontype;
    """)
    
    op.execute("""
        ALTER TABLE questions 
        ALTER COLUMN section TYPE assessmentsection 
        USING section::assessmentsection;
    """)
    
    op.execute("""
        ALTER TABLE assessments 
        ALTER COLUMN current_section TYPE assessmentsection 
        USING current_section::assessmentsection;
    """)
    
    op.execute("""
        ALTER TABLE assessment_sections 
        ALTER COLUMN section TYPE assessmentsection 
        USING section::assessmentsection;
    """)
    
    op.execute("""
        ALTER TABLE assessment_results 
        ALTER COLUMN section TYPE assessmentsection 
        USING section::assessmentsection;
    """)
