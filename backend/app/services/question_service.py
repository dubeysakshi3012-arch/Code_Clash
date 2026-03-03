"""Question service for retrieving and validating assessment questions."""

from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.db.models import Question, QuestionType, AssessmentSection, ProgrammingLanguage
from app.services.question_bank import (
    get_mcq_questions,
    get_logic_questions,
    get_coding_problems
)


def get_mcq_questions_for_assessment(db: Session) -> List[Question]:
    """
    Get all MCQ questions for Section A.
    
    Args:
        db: Database session
        
    Returns:
        List of MCQ questions
    """
    return db.query(Question).filter(
        Question.question_type == QuestionType.MCQ,
        Question.section == AssessmentSection.A
    ).order_by(Question.id).all()


def get_logic_questions_for_assessment(db: Session) -> List[Question]:
    """
    Get all Logic & Trace questions for Section B.
    
    Args:
        db: Database session
        
    Returns:
        List of logic questions
    """
    return db.query(Question).filter(
        Question.question_type == QuestionType.LOGIC_TRACE,
        Question.section == AssessmentSection.B
    ).order_by(Question.id).all()


def get_coding_problems_for_assessment(
    db: Session,
    language: ProgrammingLanguage
) -> List[Dict[str, Any]]:
    """
    Get coding problems for Section C with language-specific templates.
    
    Args:
        db: Database session
        language: Selected programming language
        
    Returns:
        List of coding problems with templates
    """
    questions = db.query(Question).filter(
        Question.question_type == QuestionType.CODING,
        Question.section == AssessmentSection.C
    ).order_by(Question.id).all()
    
    result = []
    for question in questions:
        # Get template for the selected language
        template = None
        for t in question.templates:
            if t.language == language:
                template = t
                break
        
        if template:
            result.append({
                "question": question,
                "template": template,
                "test_cases": [
                    tc for tc in question.test_cases
                    if not tc.is_hidden  # Only visible test cases
                ]
            })
    
    return result


def validate_mcq_answer(question: Question, answer: str) -> bool:
    """
    Validate MCQ answer.
    
    Args:
        question: Question object
        answer: User's answer (A, B, C, or D)
        
    Returns:
        True if correct, False otherwise
    """
    if question.question_type != QuestionType.MCQ:
        return False
    
    correct_answer = question.correct_answer
    return answer.upper().strip() == correct_answer.upper().strip()


def validate_logic_answer(question: Question, answer: str) -> bool:
    """
    Validate Logic & Trace answer with exact match.
    
    Args:
        question: Question object
        answer: User's answer string
        
    Returns:
        True if exact match, False otherwise
    """
    if question.question_type != QuestionType.LOGIC_TRACE:
        return False
    
    correct_answer = question.correct_answer
    # Exact match (case-insensitive, whitespace trimmed)
    return answer.strip().lower() == correct_answer.strip().lower()


def get_question_ids_for_match(
    db: Session,
    language: ProgrammingLanguage,
    count: int = 3,
) -> List[int]:
    """
    Get question IDs that have a template for the given language (for PvP match).
    Returns up to `count` IDs, mixing types if available.
    """
    from sqlalchemy import and_
    from app.db.models.question import QuestionTemplate
    subq = (
        db.query(QuestionTemplate.question_id)
        .filter(QuestionTemplate.language == language)
        .distinct()
    )
    questions = (
        db.query(Question.id)
        .filter(Question.id.in_(subq))
        .limit(count)
        .all()
    )
    return [q.id for q in questions]


def get_question_by_id(db: Session, question_id: int) -> Optional[Question]:
    """
    Get question by ID.
    
    Args:
        db: Database session
        question_id: Question ID
        
    Returns:
        Question object or None
    """
    return db.query(Question).filter(Question.id == question_id).first()


def get_questions_for_section(
    db: Session,
    section: AssessmentSection,
    language: Optional[ProgrammingLanguage] = None
) -> List[Dict[str, Any]]:
    """
    Get all questions for a specific section.
    
    Args:
        db: Database session
        section: Section (A, B, or C)
        language: Programming language (required for Section C)
        
    Returns:
        List of questions with appropriate formatting
    """
    if section == AssessmentSection.A:
        questions = get_mcq_questions_for_assessment(db)
        return [
            {
                "id": q.id,
                "concept_name": q.concept_name,
                "logic_description": q.logic_description,
                "options": q.options,
                "points": q.points,
                "type": "mcq"
            }
            for q in questions
        ]
    
    elif section == AssessmentSection.B:
        questions = get_logic_questions_for_assessment(db)
        return [
            {
                "id": q.id,
                "concept_name": q.concept_name,
                "logic_description": q.logic_description,
                "points": q.points,
                "type": "logic_trace"
            }
            for q in questions
        ]
    
    elif section == AssessmentSection.C:
        if not language:
            raise ValueError("Language required for Section C")
        problems = get_coding_problems_for_assessment(db, language)
        return [
            {
                "id": item["question"].id,
                "concept_name": item["question"].concept_name,
                "logic_description": item["question"].logic_description,
                "problem_statement": item["template"].problem_statement,
                "starter_code": item["template"].starter_code,
                "time_limit": item["question"].time_limit,
                "memory_limit": item["question"].memory_limit,
                "visible_test_cases": [
                    {
                        "input": tc.input_data,
                        "expected_output": tc.expected_output
                    }
                    for tc in item["test_cases"]
                ],
                "points": item["question"].points,
                "type": "coding"
            }
            for item in problems
        ]
    
    return []
