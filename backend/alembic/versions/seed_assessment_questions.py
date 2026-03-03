"""seed_assessment_questions

Revision ID: seed_assessment_questions
Revises: add_question_types_sections
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import json
from sqlalchemy.sql import table, column
from app.services.question_bank import (
    get_mcq_questions,
    get_logic_questions,
    get_coding_problems
)

# revision identifiers, used by Alembic.
revision = 'seed_assessment_questions'
down_revision = 'add_question_types_sections'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get question data
    mcq_questions = get_mcq_questions()
    logic_questions = get_logic_questions()
    coding_problems = get_coding_problems()
    
    # Create table references
    questions_table = table(
        'questions',
        column('id', sa.Integer),
        column('concept_name', sa.String),
        column('difficulty_tag', sa.String),
        column('logic_description', sa.Text),
        column('time_limit', sa.Integer),
        column('memory_limit', sa.Integer),
        column('question_type', sa.String),
        column('section', sa.String),
        column('points', sa.Float),
        column('options', sa.JSON),
        column('correct_answer', sa.Text)
    )
    
    question_templates_table = table(
        'question_templates',
        column('id', sa.Integer),
        column('question_id', sa.Integer),
        column('language', sa.String),
        column('problem_statement', sa.Text),
        column('starter_code', sa.Text),
        column('solution_template', sa.Text)
    )
    
    test_cases_table = table(
        'test_cases',
        column('id', sa.Integer),
        column('question_id', sa.Integer),
        column('input_data', sa.Text),
        column('expected_output', sa.Text),
        column('is_hidden', sa.Boolean),
        column('order', sa.Integer)
    )
    
    # Insert MCQ questions
    for q_data in mcq_questions:
        # Convert difficulty_tag to uppercase (database enum uses EASY, MEDIUM, HARD)
        difficulty_tag = q_data['difficulty_tag'].value.upper()
        op.execute(
            questions_table.insert().values(
                concept_name=q_data['concept_name'],
                difficulty_tag=difficulty_tag,
                logic_description=q_data['logic_description'],
                time_limit=q_data['time_limit'],
                memory_limit=q_data['memory_limit'],
                question_type=q_data['question_type'].value,
                section=q_data['section'].value,
                points=q_data['points'],
                options=json.dumps(q_data['options']) if q_data.get('options') else None,
                correct_answer=q_data.get('correct_answer')
            )
        )
    
    # Insert logic questions
    for q_data in logic_questions:
        difficulty_tag = q_data['difficulty_tag'].value.upper()
        op.execute(
            questions_table.insert().values(
                concept_name=q_data['concept_name'],
                difficulty_tag=difficulty_tag,
                logic_description=q_data['logic_description'],
                time_limit=q_data['time_limit'],
                memory_limit=q_data['memory_limit'],
                question_type=q_data['question_type'].value,
                section=q_data['section'].value,
                points=q_data['points'],
                correct_answer=q_data.get('correct_answer')
            )
        )
    
    # Insert coding problems
    for q_data in coding_problems:
        difficulty_tag = q_data['difficulty_tag'].value.upper()
        op.execute(
            questions_table.insert().values(
                concept_name=q_data['concept_name'],
                difficulty_tag=difficulty_tag,
                logic_description=q_data['logic_description'],
                time_limit=q_data['time_limit'],
                memory_limit=q_data['memory_limit'],
                question_type=q_data['question_type'].value,
                section=q_data['section'].value,
                points=q_data['points']
            )
        )
        # Templates and test cases would be inserted separately
        # This is a simplified version - full implementation would require
        # reading template files and creating proper relationships


def downgrade() -> None:
    # Delete seeded questions
    op.execute("DELETE FROM questions WHERE question_type IN ('mcq', 'logic_trace', 'coding')")
