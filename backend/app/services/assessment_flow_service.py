"""Assessment flow service for managing section-based assessment progression."""

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime
from typing import List, Dict, Any
from app.db.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentResult,
    AssessmentStatus,
    AssessmentSection,
    Question,
    QuestionType,
    ProgrammingLanguage
)
from app.services.question_service import (
    get_questions_for_section,
    validate_mcq_answer,
    validate_logic_answer,
    get_question_by_id
)
from app.services.judge_service import get_judge_service
from app.services.scoring_service import (
    calculate_total_score,
    get_section_results
)


def initialize_assessment(
    db: Session,
    user_id: int,
    language: ProgrammingLanguage
) -> Assessment:
    """
    Initialize a new assessment or return existing in-progress assessment.
    
    If the user already has an assessment in progress, returns that assessment.
    Otherwise, creates a new assessment with all questions assigned.
    
    Args:
        db: Database session
        user_id: User ID
        language: Selected programming language (used only for new assessments)
        
    Returns:
        Assessment object (existing in-progress or newly created)
    """
    # Check for existing active assessment
    active_assessment = db.query(Assessment).filter(
        Assessment.user_id == user_id,
        Assessment.status == AssessmentStatus.IN_PROGRESS
    ).order_by(Assessment.started_at.desc()).first()
    
    if active_assessment:
        # Return existing assessment - user can continue from where they left off
        return active_assessment
    
    # Create new assessment
    from datetime import datetime
    from sqlalchemy.sql import func
    
    assessment = Assessment(
        user_id=user_id,
        language=language,
        status=AssessmentStatus.IN_PROGRESS,
        current_section=AssessmentSection.A,
        server_start_time=func.now()  # Set server-side start time for timer validation
    )
    
    db.add(assessment)
    db.flush()
    db.refresh(assessment)  # Refresh to get the actual timestamp
    
    # Get all assessment questions
    # With native_enum=False, we can use enum values directly
    all_questions = db.query(Question).filter(
        Question.question_type.in_([QuestionType.MCQ, QuestionType.LOGIC_TRACE, QuestionType.CODING])
    ).all()
    
    # Assign questions to assessment
    order = 0
    for question in all_questions:
        # For coding questions, only assign if template exists for language
        if question.question_type == QuestionType.CODING:
            has_template = any(
                t.language == language for t in question.templates
            )
            if not has_template:
                continue
        
        assessment_question = AssessmentQuestion(
            assessment_id=assessment.id,
            question_id=question.id,
            order=order
        )
        db.add(assessment_question)
        order += 1
    
    db.commit()
    db.refresh(assessment)
    
    return assessment


def get_section_questions(
    db: Session,
    assessment_id: int,
    user_id: int,
    section: AssessmentSection
) -> List[Dict[str, Any]]:
    """
    Get questions for a specific section.
    
    Args:
        db: Database session
        assessment_id: Assessment ID
        user_id: User ID (for authorization)
        section: Section (A, B, or C)
        
    Returns:
        List of questions for the section
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
    
    if assessment.status != AssessmentStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment is not in progress"
        )
    
    return get_questions_for_section(db, section, assessment.language)


def submit_mcq_answer(
    db: Session,
    assessment_id: int,
    user_id: int,
    question_id: int,
    answer: str
) -> AssessmentResult:
    """
    Submit MCQ answer for Section A.
    
    Args:
        db: Database session
        assessment_id: Assessment ID
        user_id: User ID
        question_id: Question ID
        answer: User's answer (A, B, C, or D)
        
    Returns:
        Assessment result object
    """
    assessment = _verify_assessment(db, assessment_id, user_id)
    
    if assessment.current_section != AssessmentSection.A:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not in Section A"
        )
    
    question = get_question_by_id(db, question_id)
    if not question or question.question_type != QuestionType.MCQ:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question"
        )
    
    # Check if answer already submitted
    existing = db.query(AssessmentResult).filter(
        AssessmentResult.assessment_id == assessment_id,
        AssessmentResult.question_id == question_id
    ).first()
    
    if existing:
        # Update existing answer
        existing.mcq_answer = answer
        existing.attempts_count += 1
        existing.is_correct = validate_mcq_answer(question, answer)
        existing.score = question.points if existing.is_correct else 0.0
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new result
    is_correct = validate_mcq_answer(question, answer)
    result = AssessmentResult(
        assessment_id=assessment_id,
        question_id=question_id,
        answer_type="mcq",
        mcq_answer=answer,
        section=AssessmentSection.A,
        is_correct=is_correct,
        score=question.points if is_correct else 0.0,
        attempts_count=1
    )
    
    db.add(result)
    db.commit()
    db.refresh(result)
    
    return result


def submit_logic_answer(
    db: Session,
    assessment_id: int,
    user_id: int,
    question_id: int,
    answer: str
) -> AssessmentResult:
    """
    Submit Logic & Trace answer for Section B.
    
    Args:
        db: Database session
        assessment_id: Assessment ID
        user_id: User ID
        question_id: Question ID
        answer: User's answer string
        
    Returns:
        Assessment result object
    """
    assessment = _verify_assessment(db, assessment_id, user_id)
    
    if assessment.current_section != AssessmentSection.B:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not in Section B"
        )
    
    question = get_question_by_id(db, question_id)
    if not question or question.question_type != QuestionType.LOGIC_TRACE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question"
        )
    
    # Check if answer already submitted
    existing = db.query(AssessmentResult).filter(
        AssessmentResult.assessment_id == assessment_id,
        AssessmentResult.question_id == question_id
    ).first()
    
    if existing:
        existing.logic_answer = answer
        existing.attempts_count += 1
        existing.is_correct = validate_logic_answer(question, answer)
        existing.score = question.points if existing.is_correct else 0.0
        db.commit()
        db.refresh(existing)
        return existing
    
    is_correct = validate_logic_answer(question, answer)
    result = AssessmentResult(
        assessment_id=assessment_id,
        question_id=question_id,
        answer_type="logic_trace",
        logic_answer=answer,
        section=AssessmentSection.B,
        is_correct=is_correct,
        score=question.points if is_correct else 0.0,
        attempts_count=1
    )
    
    db.add(result)
    db.commit()
    db.refresh(result)
    
    return result


def submit_coding_solution(
    db: Session,
    assessment_id: int,
    user_id: int,
    question_id: int,
    code: str
) -> AssessmentResult:
    """
    Submit coding solution for Section C and execute via Docker judge.
    
    Args:
        db: Database session
        assessment_id: Assessment ID
        user_id: User ID
        question_id: Question ID
        code: User's code submission
        
    Returns:
        Assessment result object with execution results
    """
    assessment = _verify_assessment(db, assessment_id, user_id)
    
    if assessment.current_section != AssessmentSection.C:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not in Section C"
        )
    
    question = get_question_by_id(db, question_id)
    if not question or question.question_type != QuestionType.CODING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question"
        )
    
    # Get all test cases (visible + hidden)
    test_cases = question.test_cases
    
    # Use full evaluation with complexity detection and verdict generation
    judge = get_judge_service(assessment.language)
    evaluation_result = judge.evaluate_submission(
        code=code,
        language=assessment.language,
        question=question,
        all_test_cases=test_cases
    )
    
    # Extract verdict and complexity info
    verdict = evaluation_result.get("verdict", "UNKNOWN")
    verdict_message = evaluation_result.get("verdict_message", "")
    complexity = evaluation_result.get("complexity", "unknown")
    efficient = evaluation_result.get("efficient", True)
    
    # Determine if all tests passed
    all_passed = evaluation_result.get("passed", False)
    
    # Check if answer already submitted
    existing = db.query(AssessmentResult).filter(
        AssessmentResult.assessment_id == assessment_id,
        AssessmentResult.question_id == question_id
    ).first()
    
    # Get stress test results from complexity detection
    stress_test_results = None
    if complexity_result := evaluation_result.get("complexity_result"):
        stress_test_results = complexity_result.get("stress_test_results", [])
    
    if existing:
        existing.answer_data = code
        existing.attempts_count += 1
        existing.is_correct = all_passed
        existing.execution_result = evaluation_result
        existing.verdict = verdict
        existing.complexity_detected = complexity
        existing.stress_test_results = stress_test_results
        existing.execution_metadata = {
            "runtime": evaluation_result.get("execution_time", 0.0),
            "memory": evaluation_result.get("memory_used", 0),
            "test_cases_passed": sum(
                1 for r in evaluation_result.get("results", [])
                if r.get("passed", False)
            ),
            "total_test_cases": len(evaluation_result.get("results", [])),
            "verdict": verdict,
            "verdict_message": verdict_message,
            "complexity": complexity,
            "efficient": efficient
        }
        db.commit()
        db.refresh(existing)
        return existing
    
    result = AssessmentResult(
        assessment_id=assessment_id,
        question_id=question_id,
        answer_type="coding",
        answer_data=code,
        section=AssessmentSection.C,
        is_correct=all_passed,
        execution_result=evaluation_result,
        verdict=verdict,
        complexity_detected=complexity,
        stress_test_results=stress_test_results,
        execution_metadata={
            "runtime": evaluation_result.get("execution_time", 0.0),
            "memory": evaluation_result.get("memory_used", 0),
            "test_cases_passed": sum(
                1 for r in evaluation_result.get("results", [])
                if r.get("passed", False)
            ),
            "total_test_cases": len(evaluation_result.get("results", [])),
            "verdict": verdict,
            "verdict_message": verdict_message,
            "complexity": complexity,
            "efficient": efficient
        },
        attempts_count=1
    )
    
    db.add(result)
    db.commit()
    db.refresh(result)
    
    return result


def complete_section(
    db: Session,
    assessment_id: int,
    user_id: int,
    section: AssessmentSection
) -> Dict[str, Any]:
    """
    Complete a section and move to next section or complete assessment.
    
    Args:
        db: Database session
        assessment_id: Assessment ID
        user_id: User ID
        section: Section to complete
        
    Returns:
        Dictionary with completion status and next section
    """
    assessment = _verify_assessment(db, assessment_id, user_id)
    
    if assessment.current_section != section:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Current section is {assessment.current_section}, not {section}"
        )
    
    # Calculate section score
    section_results = get_section_results(db, assessment_id, section)
    
    if section == AssessmentSection.A:
        from app.services.scoring_service import calculate_mcq_score
        score = calculate_mcq_score(section_results)
        assessment.section_a_score = score
        assessment.current_section = AssessmentSection.B
    
    elif section == AssessmentSection.B:
        from app.services.scoring_service import calculate_logic_score
        score = calculate_logic_score(section_results)
        assessment.section_b_score = score
        assessment.current_section = AssessmentSection.C
    
    elif section == AssessmentSection.C:
        from app.services.scoring_service import calculate_coding_score
        # Get total test cases
        coding_questions = db.query(Question).join(AssessmentQuestion).filter(
            AssessmentQuestion.assessment_id == assessment_id,
            Question.question_type == QuestionType.CODING
        ).all()
        total_test_cases = sum(len(q.test_cases) for q in coding_questions)
        
        score = calculate_coding_score(
            section_results,
            assessment.language.value,
            total_test_cases
        )
        assessment.section_c_score = score
        # Assessment complete - calculate total score
        total_score = (assessment.section_a_score or 0.0) + (assessment.section_b_score or 0.0) + score
        assessment.total_score = total_score
        assessment.current_section = None
        assessment.status = AssessmentStatus.COMPLETED
        assessment.completed_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "section": section.value,
        "section_score": score,
        "next_section": assessment.current_section.value if assessment.current_section else None,
        "is_complete": assessment.status == AssessmentStatus.COMPLETED
    }


def complete_assessment(
    db: Session,
    assessment_id: int,
    user_id: int
) -> Dict[str, Any]:
    """
    Complete entire assessment and calculate final scores.
    
    Args:
        db: Database session
        assessment_id: Assessment ID
        user_id: User ID
        
    Returns:
        Dictionary with final scores and ELO update
    """
    assessment = _verify_assessment(db, assessment_id, user_id, allow_completed=True)
    
    # If already completed, return existing results
    if assessment.status == AssessmentStatus.COMPLETED:
        # Calculate total from section scores (in case total_score wasn't set)
        section_a = assessment.section_a_score or 0.0
        section_b = assessment.section_b_score or 0.0
        section_c = assessment.section_c_score or 0.0
        calculated_total = section_a + section_b + section_c
        
        # Update total_score in database if it's missing or incorrect
        if assessment.total_score is None or assessment.total_score == 0.0:
            assessment.total_score = calculated_total
            db.commit()
        
        # Use calculated total to ensure accuracy
        total_score = assessment.total_score if assessment.total_score and assessment.total_score > 0 else calculated_total
        
        return {
            "assessment_id": assessment_id,
            "scores": {
                "section_a_score": section_a,
                "section_b_score": section_b,
                "section_c_score": section_c,
                "total_score": round(total_score, 2),
                "max_score": 100.0
            },
            "completed_at": assessment.completed_at.isoformat() if assessment.completed_at else datetime.utcnow().isoformat()
        }
    
    # Ensure all sections are completed
    if assessment.current_section:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Please complete Section {assessment.current_section.value} first"
        )
    
    # Get all results
    mcq_results = get_section_results(db, assessment_id, AssessmentSection.A)
    logic_results = get_section_results(db, assessment_id, AssessmentSection.B)
    coding_results = get_section_results(db, assessment_id, AssessmentSection.C)
    
    # Get total test cases for coding
    coding_questions = db.query(Question).join(AssessmentQuestion).filter(
        AssessmentQuestion.assessment_id == assessment_id,
        Question.question_type == QuestionType.CODING
    ).all()
    total_test_cases = sum(len(q.test_cases) for q in coding_questions)
    
    # Calculate total score
    scores = calculate_total_score(
        mcq_results,
        logic_results,
        coding_results,
        assessment.language.value,
        total_test_cases
    )
    
    # Update assessment scores if not already set
    if assessment.section_a_score is None:
        assessment.section_a_score = scores["section_a_score"]
    if assessment.section_b_score is None:
        assessment.section_b_score = scores["section_b_score"]
    if assessment.section_c_score is None:
        assessment.section_c_score = scores["section_c_score"]
    
    assessment.total_score = scores["total_score"]
    assessment.status = AssessmentStatus.COMPLETED
    if not assessment.completed_at:
        assessment.completed_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "assessment_id": assessment_id,
        "scores": scores,
        "completed_at": assessment.completed_at.isoformat()
    }


def _verify_assessment(
    db: Session,
    assessment_id: int,
    user_id: int,
    allow_completed: bool = False
) -> Assessment:
    """
    Verify assessment exists and user has access.
    
    Args:
        db: Database session
        assessment_id: Assessment ID
        user_id: User ID
        allow_completed: If True, allow access to completed assessments
        
    Returns:
        Assessment object
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
    
    if not allow_completed and assessment.status != AssessmentStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment is not in progress"
        )
    
    return assessment
