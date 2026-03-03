"""Assessment service for managing assessment sessions and submissions."""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime
from typing import List
from app.db.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentResult,
    Question,
    QuestionTemplate,
    TestCase,
    AssessmentStatus,
    AssessmentLanguage as ProgrammingLanguage
)
from app.schemas.assessment import AnswerSubmission
from app.services.elo_service import update_elo_after_assessment
from app.services.judge_service import get_judge_service


def start_assessment(
    db: Session,
    user_id: int,
    language: ProgrammingLanguage
) -> Assessment:
    """
    Start a new assessment session for a user.
    
    Args:
        db: Database session
        user_id: User ID
        language: Selected programming language
        
    Returns:
        Created assessment object
        
    Raises:
        HTTPException: If user has an active assessment
    """
    # Check for existing active assessment
    active_assessment = db.query(Assessment).filter(
        Assessment.user_id == user_id,
        Assessment.status == AssessmentStatus.IN_PROGRESS
    ).first()
    
    if active_assessment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has an active assessment"
        )
    
    # Create new assessment
    assessment = Assessment(
        user_id=user_id,
        language=language,
        status=AssessmentStatus.IN_PROGRESS
    )
    
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    
    # Select questions for assessment
    # TODO: Replace with AI-driven question selection
    select_questions_for_assessment(db, assessment.id, language)
    
    return assessment


def select_questions_for_assessment(
    db: Session,
    assessment_id: int,
    language: ProgrammingLanguage,
    count: int = 5
) -> None:
    """
    Select questions for an assessment.
    
    TODO: Implement AI-driven question selection
    - Use AI service to generate personalized questions
    - Balance difficulty based on user ELO
    - Ensure concept diversity
    
    Currently: Selects random questions with templates for the language
    
    Args:
        db: Database session
        assessment_id: Assessment ID
        language: Programming language
        count: Number of questions to select
    """
    # Get questions that have templates for the selected language
    questions = db.query(Question).join(QuestionTemplate).filter(
        QuestionTemplate.language == language
    ).limit(count).all()
    
    if not questions:
        # If no questions exist, assessment will have no questions
        # In production, this should trigger question generation
        return
    
    # Link questions to assessment
    for idx, question in enumerate(questions):
        assessment_question = AssessmentQuestion(
            assessment_id=assessment_id,
            question_id=question.id,
            order=idx
        )
        db.add(assessment_question)
    
    db.commit()


def get_assessment_questions(
    db: Session,
    assessment_id: int,
    user_id: int
) -> List[dict]:
    """
    Get questions for an assessment.
    
    Args:
        db: Database session
        assessment_id: Assessment ID
        user_id: User ID (for authorization)
        
    Returns:
        List of question dictionaries with templates and visible test cases
        
    Raises:
        HTTPException: If assessment not found or unauthorized
    """
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id
    ).first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    if assessment.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this assessment"
        )
    
    if assessment.status != AssessmentStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment is not in progress"
        )
    
    # Get assessment questions
    assessment_questions = db.query(AssessmentQuestion).filter(
        AssessmentQuestion.assessment_id == assessment_id
    ).order_by(AssessmentQuestion.order).all()
    
    questions_data = []
    
    for aq in assessment_questions:
        question = db.query(Question).filter(Question.id == aq.question_id).first()
        if not question:
            continue
        
        # Get template for assessment language
        template = db.query(QuestionTemplate).filter(
            QuestionTemplate.question_id == question.id,
            QuestionTemplate.language == assessment.language
        ).first()
        
        if not template:
            continue
        
        # Get visible test cases only
        visible_test_cases = db.query(TestCase).filter(
            TestCase.question_id == question.id,
            TestCase.is_hidden == False
        ).order_by(TestCase.order).all()
        
        questions_data.append({
            "id": question.id,
            "concept_name": question.concept_name,
            "difficulty_tag": question.difficulty_tag.value,
            "logic_description": question.logic_description,
            "time_limit": question.time_limit,
            "memory_limit": question.memory_limit,
            "problem_statement": template.problem_statement,
            "starter_code": template.starter_code,
            "language": assessment.language.value,
            "visible_test_cases": [
                {
                    "id": tc.id,
                    "input_data": tc.input_data,
                    "expected_output": tc.expected_output,
                    "order": tc.order
                }
                for tc in visible_test_cases
            ]
        })
    
    return questions_data


def submit_answer(
    db: Session,
    assessment_id: int,
    user_id: int,
    answer_data: AnswerSubmission
) -> AssessmentResult:
    """
    Submit an answer for a question in an assessment.
    
    Args:
        db: Database session
        assessment_id: Assessment ID
        user_id: User ID
        answer_data: Answer submission data
        
    Returns:
        Created assessment result object
        
    Raises:
        HTTPException: If assessment not found or invalid
    """
    # Verify assessment
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id
    ).first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    if assessment.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    if assessment.status != AssessmentStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment is not in progress"
        )
    
    # Verify question belongs to assessment
    assessment_question = db.query(AssessmentQuestion).filter(
        AssessmentQuestion.assessment_id == assessment_id,
        AssessmentQuestion.question_id == answer_data.question_id
    ).first()
    
    if not assessment_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question not part of this assessment"
        )
    
    # Check if answer already submitted
    existing_result = db.query(AssessmentResult).filter(
        AssessmentResult.assessment_id == assessment_id,
        AssessmentResult.question_id == answer_data.question_id
    ).first()
    
    if existing_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Answer already submitted for this question"
        )
    
    # Evaluate answer (placeholder for now)
    is_correct = None
    execution_result = None
    score = 0
    
    if answer_data.answer_type == "coding" and answer_data.answer_data:
        # TODO: Execute code using judge service
        question = db.query(Question).filter(Question.id == answer_data.question_id).first()
        test_cases = db.query(TestCase).filter(
            TestCase.question_id == answer_data.question_id
        ).all()
        
        if question and test_cases:
            judge = get_judge_service(assessment.language)
            execution_result = judge.execute_code(
                code=answer_data.answer_data,
                language=assessment.language,
                test_cases=test_cases,
                time_limit=question.time_limit,
                memory_limit=question.memory_limit
            )
            is_correct = execution_result.get("passed", False)
            score = 100 if is_correct else 0
    
    # Create assessment result
    result = AssessmentResult(
        assessment_id=assessment_id,
        question_id=answer_data.question_id,
        answer_type=answer_data.answer_type,
        answer_data=answer_data.answer_data,
        mcq_answer=answer_data.mcq_answer,
        is_correct=is_correct,
        execution_result=execution_result,
        score=score
    )
    
    db.add(result)
    db.commit()
    db.refresh(result)
    
    return result


def complete_assessment(
    db: Session,
    assessment_id: int,
    user_id: int
) -> dict:
    """
    Complete an assessment and calculate ELO.
    
    Args:
        db: Database session
        assessment_id: Assessment ID
        user_id: User ID
        
    Returns:
        Dictionary with assessment completion details
        
    Raises:
        HTTPException: If assessment not found or invalid
    """
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id
    ).first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    if assessment.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    if assessment.status == AssessmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment already completed"
        )
    
    # Get results
    results = db.query(AssessmentResult).filter(
        AssessmentResult.assessment_id == assessment_id
    ).all()
    
    total_questions = len(results)
    correct_answers = sum(1 for r in results if r.is_correct is True)
    total_score = sum(r.score or 0 for r in results)
    
    # Update assessment status
    assessment.status = AssessmentStatus.COMPLETED
    assessment.completed_at = datetime.utcnow()
    
    # Calculate and update ELO
    new_elo = update_elo_after_assessment(db, user_id, assessment_id)
    
    db.commit()
    
    return {
        "assessment_id": assessment_id,
        "total_questions": total_questions,
        "correct_answers": correct_answers,
        "score": total_score,
        "new_elo_rating": new_elo,
        "completed_at": assessment.completed_at
    }
