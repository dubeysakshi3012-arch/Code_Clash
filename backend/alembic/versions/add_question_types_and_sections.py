"""add_question_types_and_sections

Revision ID: add_question_types_sections
Revises: a689d8681ac4
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_question_types_sections'
down_revision = '3c66fee58add'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add question type enum (check if exists first)
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'questiontype')"))
    if not result.scalar():
        op.execute("CREATE TYPE questiontype AS ENUM ('mcq', 'logic_trace', 'coding')")
    
    # Add assessment section enum (check if exists first)
    result = conn.execute(sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'assessmentsection')"))
    if not result.scalar():
        op.execute("CREATE TYPE assessmentsection AS ENUM ('A', 'B', 'C')")
    
    # Add columns to questions table (use postgresql.ENUM to avoid auto-creation)
    op.add_column('questions', sa.Column('question_type', postgresql.ENUM('mcq', 'logic_trace', 'coding', name='questiontype', create_type=False), nullable=True))
    op.add_column('questions', sa.Column('section', postgresql.ENUM('A', 'B', 'C', name='assessmentsection', create_type=False), nullable=True))
    op.add_column('questions', sa.Column('points', sa.Float(), nullable=True))
    op.add_column('questions', sa.Column('options', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('questions', sa.Column('correct_answer', sa.Text(), nullable=True))
    
    # Create indexes
    op.create_index(op.f('ix_questions_question_type'), 'questions', ['question_type'], unique=False)
    op.create_index(op.f('ix_questions_section'), 'questions', ['section'], unique=False)
    
    # Add columns to assessments table (use postgresql.ENUM to avoid auto-creation)
    op.add_column('assessments', sa.Column('current_section', postgresql.ENUM('A', 'B', 'C', name='assessmentsection', create_type=False), nullable=True))
    op.add_column('assessments', sa.Column('total_score', sa.Float(), nullable=True))
    op.add_column('assessments', sa.Column('section_a_score', sa.Float(), nullable=True))
    op.add_column('assessments', sa.Column('section_b_score', sa.Float(), nullable=True))
    op.add_column('assessments', sa.Column('section_c_score', sa.Float(), nullable=True))
    
    # Create assessment_sections table (use postgresql.ENUM to avoid auto-creation)
    op.create_table('assessment_sections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('section', postgresql.ENUM('A', 'B', 'C', name='assessmentsection', create_type=False), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('is_completed', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assessment_sections_id'), 'assessment_sections', ['id'], unique=False)
    
    # Add columns to assessment_results table (use postgresql.ENUM to avoid auto-creation)
    op.add_column('assessment_results', sa.Column('section', postgresql.ENUM('A', 'B', 'C', name='assessmentsection', create_type=False), nullable=True))
    op.add_column('assessment_results', sa.Column('logic_answer', sa.Text(), nullable=True))
    op.add_column('assessment_results', sa.Column('execution_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('assessment_results', sa.Column('partial_score', sa.Float(), nullable=True))
    op.alter_column('assessment_results', 'score', type_=sa.Float(), existing_type=sa.Integer())
    op.alter_column('assessment_results', 'answer_type', type_=sa.String(length=50), existing_type=sa.String(length=50))
    
    # Create index
    op.create_index(op.f('ix_assessment_results_section'), 'assessment_results', ['section'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_assessment_results_section'), table_name='assessment_results')
    op.drop_index(op.f('ix_questions_section'), table_name='questions')
    op.drop_index(op.f('ix_questions_question_type'), table_name='questions')
    
    # Drop columns from assessment_results
    op.drop_column('assessment_results', 'partial_score')
    op.drop_column('assessment_results', 'execution_metadata')
    op.drop_column('assessment_results', 'logic_answer')
    op.drop_column('assessment_results', 'section')
    op.alter_column('assessment_results', 'score', type_=sa.Integer(), existing_type=sa.Float())
    
    # Drop assessment_sections table
    op.drop_table('assessment_sections')
    
    # Drop columns from assessments
    op.drop_column('assessments', 'section_c_score')
    op.drop_column('assessments', 'section_b_score')
    op.drop_column('assessments', 'section_a_score')
    op.drop_column('assessments', 'total_score')
    op.drop_column('assessments', 'current_section')
    
    # Drop columns from questions
    op.drop_column('questions', 'correct_answer')
    op.drop_column('questions', 'options')
    op.drop_column('questions', 'points')
    op.drop_column('questions', 'section')
    op.drop_column('questions', 'question_type')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS assessmentsection')
    op.execute('DROP TYPE IF EXISTS questiontype')
