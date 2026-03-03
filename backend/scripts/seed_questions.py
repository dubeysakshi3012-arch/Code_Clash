"""
Script to seed assessment questions into the database.
Run this after migrations to populate questions.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.db.models import Question, QuestionTemplate, TestCase
from app.services.question_bank import (
    get_mcq_questions,
    get_logic_questions,
    get_coding_problems
)
from app.db.models.question import QuestionType, AssessmentSection, DifficultyTag, ProgrammingLanguage
import json
import os

def seed_questions():
    """Seed all assessment questions into the database."""
    db = SessionLocal()
    
    try:
        # Check if questions already exist
        existing_count = db.query(Question).filter(
            Question.question_type.in_([QuestionType.MCQ, QuestionType.LOGIC_TRACE, QuestionType.CODING])
        ).count()
        
        if existing_count > 0:
            print(f"Found {existing_count} existing questions. Deleting old questions...")
            db.query(Question).filter(
                Question.question_type.in_([QuestionType.MCQ, QuestionType.LOGIC_TRACE, QuestionType.CODING])
            ).delete(synchronize_session=False)
            db.commit()
        
        # Get question data
        mcq_questions = get_mcq_questions()
        logic_questions = get_logic_questions()
        coding_problems = get_coding_problems()
        
        print(f"Seeding {len(mcq_questions)} MCQ questions...")
        # Insert MCQ questions
        for q_data in mcq_questions:
            question = Question(
                concept_name=q_data['concept_name'],
                difficulty_tag=q_data['difficulty_tag'],
                logic_description=q_data['logic_description'],
                time_limit=q_data['time_limit'],
                memory_limit=q_data['memory_limit'],
                question_type=QuestionType.MCQ,
                section=AssessmentSection.A,
                points=q_data['points'],
                options=q_data.get('options'),
                correct_answer=q_data.get('correct_answer')
            )
            db.add(question)
        
        print(f"Seeding {len(logic_questions)} Logic questions...")
        # Insert logic questions
        for q_data in logic_questions:
            question = Question(
                concept_name=q_data['concept_name'],
                difficulty_tag=q_data['difficulty_tag'],
                logic_description=q_data['logic_description'],
                time_limit=q_data['time_limit'],
                memory_limit=q_data['memory_limit'],
                question_type=QuestionType.LOGIC_TRACE,
                section=AssessmentSection.B,
                points=q_data['points'],
                correct_answer=q_data.get('correct_answer')
            )
            db.add(question)
        
        print(f"Seeding {len(coding_problems)} Coding problems...")
        # Insert coding problems
        for q_data in coding_problems:
            question = Question(
                concept_name=q_data['concept_name'],
                difficulty_tag=q_data['difficulty_tag'],
                logic_description=q_data['logic_description'],
                time_limit=q_data['time_limit'],
                memory_limit=q_data['memory_limit'],
                question_type=QuestionType.CODING,
                section=AssessmentSection.C,
                points=q_data['points']
            )
            db.add(question)
            db.flush()  # Get the question ID
            
            # Add templates for all languages
            for lang in [ProgrammingLanguage.PYTHON, ProgrammingLanguage.JAVA, ProgrammingLanguage.CPP]:
                template_path = None
                if q_data['concept_name'] == 'Maximum Consecutive Ones':
                    if lang == ProgrammingLanguage.PYTHON:
                        template_path = Path(__file__).parent.parent / 'app' / 'templates' / 'python' / 'max_consecutive_ones.py'
                    elif lang == ProgrammingLanguage.JAVA:
                        template_path = Path(__file__).parent.parent / 'app' / 'templates' / 'java' / 'MaxConsecutiveOnes.java'
                    elif lang == ProgrammingLanguage.CPP:
                        template_path = Path(__file__).parent.parent / 'app' / 'templates' / 'cpp' / 'max_consecutive_ones.cpp'
                elif q_data['concept_name'] == 'Smallest Subarray with Sum ≥ K':
                    if lang == ProgrammingLanguage.PYTHON:
                        template_path = Path(__file__).parent.parent / 'app' / 'templates' / 'python' / 'smallest_subarray.py'
                    elif lang == ProgrammingLanguage.JAVA:
                        template_path = Path(__file__).parent.parent / 'app' / 'templates' / 'java' / 'SmallestSubarray.java'
                    elif lang == ProgrammingLanguage.CPP:
                        template_path = Path(__file__).parent.parent / 'app' / 'templates' / 'cpp' / 'smallest_subarray.cpp'
                
                starter_code = ""
                problem_statement = q_data['logic_description']
                
                if template_path and template_path.exists():
                    starter_code = template_path.read_text(encoding='utf-8')
                
                template = QuestionTemplate(
                    question_id=question.id,
                    language=lang,
                    problem_statement=problem_statement,
                    starter_code=starter_code,
                    solution_template=""  # Not needed for assessment
                )
                db.add(template)
            
            # Add test cases
            test_cases = q_data.get('test_cases', [])
            for idx, tc in enumerate(test_cases):
                test_case = TestCase(
                    question_id=question.id,
                    input_data=tc['input'],
                    expected_output=tc['expected_output'],
                    is_hidden=tc.get('is_hidden', False),
                    order=idx
                )
                db.add(test_case)
        
        db.commit()
        print("Questions seeded successfully!")
        
        # Verify
        total = db.query(Question).filter(
            Question.question_type.in_([QuestionType.MCQ, QuestionType.LOGIC_TRACE, QuestionType.CODING])
        ).count()
        print(f"Total questions in database: {total}")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding questions: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == '__main__':
    seed_questions()
