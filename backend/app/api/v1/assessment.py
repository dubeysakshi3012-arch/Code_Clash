"""Assessment API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import text as sa_text
from typing import List
from app.db.session import get_db
from app.db.models import User, ProgrammingLanguage, AssessmentSection, Assessment
from app.schemas.assessment import (
    AssessmentStart,
    AssessmentResponse,
    AnswerSubmission,
    AssessmentResultResponse,
    AssessmentCompleteResponse,
    MCQAnswer,
    LogicAnswer,
    CodingSubmission,
    CustomRunRequest,
    SectionProgress,
    SectionCompleteResponse,
    TestResultResponse,
    TestCaseResult,
    AssessmentSkip,
    AssessmentSkipResponse,
    ViolationLogRequest,
    ViolationLogResponse,
    TimerValidationRequest,
    TimerValidationResponse
)
from app.schemas.question import SectionQuestionsResponse
from app.services.docker_runner import _sanitize_error_for_client
from app.services.assessment_flow_service import (
    initialize_assessment,
    get_section_questions,
    submit_mcq_answer,
    submit_logic_answer,
    submit_coding_solution,
    complete_section,
    complete_assessment as complete_assessment_flow
)
from app.services.elo_service import update_elo_after_assessment
from app.api.v1.auth import get_current_user_from_token

router = APIRouter(prefix="/assessment", tags=["assessment"])


@router.post("/start", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def start_new_assessment(
    assessment_data: AssessmentStart,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Start a new assessment session or continue an existing one.
    
    If the user already has an assessment in progress, returns that assessment.
    Otherwise, creates a new assessment with all questions initialized.
    
    Args:
        assessment_data: Assessment start data (language selection)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Assessment object (existing in-progress or newly created)
    """
    assessment = initialize_assessment(db, current_user.id, assessment_data.language)
    return assessment


@router.post("/skip", response_model=AssessmentSkipResponse, status_code=status.HTTP_200_OK)
def skip_assessment(
    skip_data: AssessmentSkip,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Skip assessment and assign beginner ELO rating (800).
    
    This endpoint allows complete beginners to skip the assessment and get
    a default beginner ELO rating. Users who already have an ELO > 0 cannot skip.
    
    Args:
        skip_data: Skip request data (optional language preference)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success response with new ELO rating
        
    Raises:
        HTTPException: If user already has ELO > 0 or assessment already completed
    """
    from app.db.models.assessment import AssessmentStatus
    
    # Check if user already has ELO > 0
    if current_user.elo_rating > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot skip assessment: User already has an ELO rating. Assessment can only be skipped for new users."
        )
    
    # Check if user has any completed assessments
    from app.db.models import Assessment
    completed_assessment = db.query(Assessment).filter(
        Assessment.user_id == current_user.id,
        Assessment.status == AssessmentStatus.COMPLETED
    ).first()
    
    if completed_assessment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot skip assessment: User has already completed an assessment."
        )
    
    # Set ELO to beginner level (800)
    BEGINNER_ELO = 800
    current_user.elo_rating = BEGINNER_ELO
    
    # Save selected language if provided
    if skip_data.selected_language:
        current_user.selected_language = skip_data.selected_language.value
    
    # Create a skipped assessment record for tracking
    # Use SQLAlchemy ORM (same approach as other assessment creation)
    # SQLAlchemy Enum column will automatically convert AssessmentStatus.SKIPPED 
    # to its string value 'skipped' when inserting
    from app.db.models import Assessment
    
    language_value = (skip_data.selected_language or ProgrammingLanguage.PYTHON).value
    
    # Try ORM approach first - SQLAlchemy will convert AssessmentStatus.SKIPPED to 'skipped'
    # If that fails due to enum caching, fallback to raw SQL with both cases
    assessment_id = None
    
    try:
        skipped_assessment = Assessment(
            user_id=current_user.id,
            language=skip_data.selected_language or ProgrammingLanguage.PYTHON,
            status=AssessmentStatus.SKIPPED,  # SQLAlchemy converts to enum value 'skipped'
            completed_at=func.now(),
            current_section=AssessmentSection.A,
            total_score=0.0,
            section_a_score=0.0,
            section_b_score=0.0,
            section_c_score=0.0
        )
        db.add(skipped_assessment)
        db.flush()
        assessment_id = skipped_assessment.id
    except Exception as e:
        # If ORM fails, try raw SQL fallback (handles enum caching issues)
        db.rollback()
        error_msg = str(e).lower()
        
        # Check if it's an enum-related error
        is_enum_error = (
            'skipped' in error_msg or 
            'SKIPPED' in str(e) or
            'enum' in error_msg or 
            ('invalid' in error_msg and 'assessmentstatus' in error_msg)
        )
        
        if is_enum_error:
            # Try raw SQL with both lowercase and uppercase
            # This bypasses SQLAlchemy's enum validation which may be cached
            try:
                # Try lowercase first (what SQLAlchemy enum value would be)
                result = db.execute(
                    sa_text("""
                        INSERT INTO assessments 
                        (user_id, language, status, completed_at, current_section, total_score, section_a_score, section_b_score, section_c_score)
                        VALUES 
                        (:user_id, :language, 'skipped'::assessmentstatus, now(), 'A', 0.0, 0.0, 0.0, 0.0)
                        RETURNING id
                    """),
                    {'user_id': current_user.id, 'language': language_value}
                )
                assessment_id = result.scalar()
            except Exception:
                # Try uppercase as fallback
                try:
                    db.rollback()
                    result = db.execute(
                        sa_text("""
                            INSERT INTO assessments 
                            (user_id, language, status, completed_at, current_section, total_score, section_a_score, section_b_score, section_c_score)
                            VALUES 
                            (:user_id, :language, 'SKIPPED'::assessmentstatus, now(), 'A', 0.0, 0.0, 0.0, 0.0)
                            RETURNING id
                        """),
                        {'user_id': current_user.id, 'language': language_value}
                    )
                    assessment_id = result.scalar()
                except Exception as sql_error:
                    # Both SQL attempts failed
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=(
                            f"Database enum issue: Could not insert 'skipped' status.\n\n"
                            f"ORM Error: {str(e)}\n"
                            f"SQL Fallback Error: {str(sql_error)}\n\n"
                            f"SOLUTION: Restart your backend server.\n"
                            f"PostgreSQL connection pools cache enum definitions. "
                            f"Even though the enum values exist, the server needs a restart to see them.\n\n"
                            f"To verify enum values, run:\n"
                            f"SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'assessmentstatus');"
                        )
                    )
        else:
            # Not an enum error, re-raise as generic error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create skipped assessment: {str(e)}"
            )
    
    db.commit()
    db.refresh(current_user)
    
    return AssessmentSkipResponse(
        status="success",
        elo_rating=current_user.elo_rating,
        message="Assessment skipped. Beginner ELO rating assigned."
    )


@router.get("/{assessment_id}/questions", response_model=SectionQuestionsResponse)
def get_assessment_questions(
    assessment_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Get questions for the current section of an assessment.
    Convenience endpoint that automatically gets questions for the current section.
    
    Args:
        assessment_id: Assessment ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Questions for the current section
    """
    from app.db.models import Assessment
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id,
        Assessment.user_id == current_user.id
    ).first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    if not assessment.current_section:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment has no current section"
        )
    
    # Convert current_section to enum if it's a string
    section_enum = assessment.current_section
    if isinstance(section_enum, str):
        try:
            section_enum = AssessmentSection(section_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid section: {section_enum}"
            )
    
    try:
        questions = get_section_questions(db, assessment_id, current_user.id, section_enum)
    except Exception as e:
        import traceback
        print(f"Error getting section questions: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load questions: {str(e)}"
        )
    
    # Get section value as string
    section_value = section_enum.value if hasattr(section_enum, 'value') else str(section_enum)
    
    return {
        "section": section_value,
        "questions": questions,
        "total": len(questions),
        "language": assessment.language.value if hasattr(assessment.language, 'value') else str(assessment.language)
    }


@router.get("/{assessment_id}/section/{section}", response_model=SectionQuestionsResponse)
def get_section_questions_endpoint(
    assessment_id: int,
    section: str,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Get questions for a specific section.
    
    Args:
        assessment_id: Assessment ID
        section: Section (A, B, or C)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Questions for the specified section
    """
    try:
        section_enum = AssessmentSection(section.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid section: {section}. Must be A, B, or C"
        )
    
    questions = get_section_questions(db, assessment_id, current_user.id, section_enum)
    return {
        "section": section.upper(),
        "questions": questions,
        "total": len(questions)
    }


@router.get("/{assessment_id}/progress", response_model=SectionProgress)
def get_assessment_progress(
    assessment_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Get assessment progress and current section.
    
    Args:
        assessment_id: Assessment ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Assessment progress information
    """
    from app.db.models import Assessment
    
    try:
        assessment = db.query(Assessment).filter(
            Assessment.id == assessment_id,
            Assessment.user_id == current_user.id
        ).first()
        
        if not assessment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assessment not found"
            )
        
        # Get current section value safely
        current_section_value = None
        if assessment.current_section:
            if hasattr(assessment.current_section, 'value'):
                current_section_value = assessment.current_section.value
            else:
                current_section_value = str(assessment.current_section)
        
        return {
            "section": current_section_value,
            "current_section": current_section_value,
            "section_a_completed": assessment.section_a_score is not None,
            "section_b_completed": assessment.section_b_score is not None,
            "section_c_completed": assessment.section_c_score is not None,
            "section_a_score": float(assessment.section_a_score) if assessment.section_a_score is not None else None,
            "section_b_score": float(assessment.section_b_score) if assessment.section_b_score is not None else None,
            "section_c_score": float(assessment.section_c_score) if assessment.section_c_score is not None else None
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching assessment progress: {str(e)}"
        )


@router.post("/{assessment_id}/section/A/submit", response_model=AssessmentResultResponse, status_code=status.HTTP_201_CREATED)
def submit_mcq_answer_endpoint(
    assessment_id: int,
    answer: MCQAnswer,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Submit MCQ answer for Section A.
    
    Args:
        assessment_id: Assessment ID
        answer: MCQ answer submission
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Assessment result object
    """
    result = submit_mcq_answer(
        db,
        assessment_id,
        current_user.id,
        answer.question_id,
        answer.answer
    )
    return result


@router.post("/{assessment_id}/section/B/submit", response_model=AssessmentResultResponse, status_code=status.HTTP_201_CREATED)
def submit_logic_answer_endpoint(
    assessment_id: int,
    answer: LogicAnswer,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Submit Logic & Trace answer for Section B.
    
    Args:
        assessment_id: Assessment ID
        answer: Logic answer submission
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Assessment result object
    """
    result = submit_logic_answer(
        db,
        assessment_id,
        current_user.id,
        answer.question_id,
        answer.answer
    )
    return result


@router.post("/{assessment_id}/test", response_model=TestResultResponse)
def test_code_endpoint(
    assessment_id: int,
    submission: CodingSubmission,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Test code against visible test cases or custom input (does not save to database).
    
    If custom_input is provided, runs code with that input only.
    Otherwise, runs against visible test cases.
    
    Args:
        assessment_id: Assessment ID
        submission: Coding solution with question_id, code, and optional custom_input
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Test execution results
    """
    from app.db.models import Assessment
    from app.services.question_service import get_question_by_id
    from app.services.judge_service import get_judge_service
    from app.db.models.assessment import AssessmentStatus
    from app.db.models.question import QuestionType
    
    # Verify assessment belongs to user
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id,
        Assessment.user_id == current_user.id
    ).first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    if assessment.status != AssessmentStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment is not in progress"
        )
    
    # Get question
    question = get_question_by_id(db, submission.question_id)
    if not question or question.question_type != QuestionType.CODING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid question"
        )
    
    judge = get_judge_service(assessment.language)
    
    # If custom input provided, run with custom input
    if submission.custom_input:
        result = judge.run_custom_input(
            code=submission.code,
            language=assessment.language,
            custom_input=submission.custom_input,
            time_limit=question.time_limit,
            memory_limit=question.memory_limit
        )
        
        # Return custom input result
        return TestResultResponse(
            passed=0,  # Not applicable for custom input
            total=1,
            results=[
                TestCaseResult(
                    passed=False,  # Not evaluated
                    input=submission.custom_input,
                    expected_output="",
                    actual_output=result.get("output", ""),
                    error=result.get("error")
                )
            ],
            execution_time=result.get("execution_time", 0.0),
            error=_sanitize_error_for_client(result.get("error"))
        )
    
    # Otherwise, run against visible test cases
    visible_test_cases = [tc for tc in question.test_cases if not tc.is_hidden]
    
    if not visible_test_cases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No visible test cases available for this question"
        )
    
    execution_result = judge.execute_code(
        code=submission.code,
        language=assessment.language,
        test_cases=visible_test_cases,
        time_limit=question.time_limit,
        memory_limit=question.memory_limit
    )
    
    # Format response
    test_results = execution_result.get("results", [])
    passed_count = sum(1 for r in test_results if r.get("passed", False))
    
    # Convert to TestCaseResult objects
    case_results = [
        TestCaseResult(
            passed=r.get("passed", False),
            input=r.get("input", ""),
            expected_output=r.get("expected_output", ""),
            actual_output=r.get("actual_output", ""),
            error=r.get("error")
        )
        for r in test_results
    ]
    
    return TestResultResponse(
        passed=passed_count,
        total=len(visible_test_cases),
        results=case_results,
        execution_time=execution_result.get("execution_time", 0.0),
        error=_sanitize_error_for_client(execution_result.get("error"))
    )


@router.post("/{assessment_id}/section/C/submit", response_model=AssessmentResultResponse, status_code=status.HTTP_201_CREATED)
def submit_coding_solution_endpoint(
    assessment_id: int,
    submission: CodingSubmission,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Submit coding solution for Section C.
    
    Runs code against ALL test cases (visible + hidden), performs complexity detection,
    generates verdict, and saves result to database.
    
    Args:
        assessment_id: Assessment ID
        submission: Coding solution submission
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Assessment result object with execution results, verdict, and complexity info
    """
    result = submit_coding_solution(
        db,
        assessment_id,
        current_user.id,
        submission.question_id,
        submission.code
    )
    return result


@router.post("/{assessment_id}/custom-run")
def custom_run_endpoint(
    assessment_id: int,
    request: CustomRunRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Run code with custom input (for "Run Code" button).
    
    Does not save results to database. Returns raw output.
    
    Args:
        assessment_id: Assessment ID
        request: Custom run request with code and custom_input
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Execution result with output, execution_time, error
    """
    from app.db.models import Assessment
    from app.services.judge_service import get_judge_service
    from app.db.models.assessment import AssessmentStatus
    
    # Verify assessment belongs to user
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id,
        Assessment.user_id == current_user.id
    ).first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    if assessment.status != AssessmentStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment is not in progress"
        )
    
    judge = get_judge_service(assessment.language)
    result = judge.run_custom_input(
        code=request.code,
        language=assessment.language,
        custom_input=request.custom_input,
        time_limit=30,  # Default time limit for custom runs
        memory_limit=256  # Default memory limit
    )
    
    return {
        "output": result.get("output", ""),
        "execution_time": result.get("execution_time", 0.0),
        "memory_used": result.get("memory_used", 0),
        "error": result.get("error")
    }


@router.post("/{assessment_id}/section/{section}/complete", response_model=SectionCompleteResponse)
def complete_section_endpoint(
    assessment_id: int,
    section: str,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Complete a section and move to next section.
    
    Args:
        assessment_id: Assessment ID
        section: Section to complete (A, B, or C)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Section completion status
    """
    try:
        section_enum = AssessmentSection(section.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid section: {section}. Must be A, B, or C"
        )
    
    result = complete_section(db, assessment_id, current_user.id, section_enum)
    return result


@router.post("/{assessment_id}/log-violation", response_model=ViolationLogResponse, status_code=status.HTTP_200_OK)
def log_violation(
    assessment_id: int,
    violation_data: ViolationLogRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Log an assessment violation (fullscreen exit, tab switch, etc.).
    
    Args:
        assessment_id: Assessment ID
        violation_data: Violation details
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Updated violation count
    """
    from app.db.models.assessment import AssessmentStatus
    from app.db.models.assessment_violation import AssessmentViolation
    from datetime import datetime
    
    # Validate assessment belongs to user and is in progress
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id,
        Assessment.user_id == current_user.id
    ).first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    if assessment.status != AssessmentStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot log violations for completed or abandoned assessments"
        )
    
    # Validate violation type
    valid_types = ['fullscreen_exit', 'tab_switch', 'window_blur']
    if violation_data.violation_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid violation type. Must be one of: {', '.join(valid_types)}"
        )
    
    # Create violation record
    violation = AssessmentViolation(
        assessment_id=assessment_id,
        user_id=current_user.id,
        violation_type=violation_data.violation_type,
        timestamp=violation_data.timestamp or datetime.utcnow()
    )
    db.add(violation)
    
    # Increment violation count
    assessment.violation_count += 1
    
    # Auto-submit if violation count reaches threshold (3 violations): run completion and ELO so frontend can show results
    if assessment.violation_count >= 3:
        assessment.auto_submitted = True
        db.flush()
        try:
            complete_assessment_flow(db, assessment_id, current_user.id)
            update_elo_after_assessment(db, current_user.id, assessment_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Auto-submit completion/ELO failed: %s", e)
    
    db.commit()
    db.refresh(assessment)
    
    return ViolationLogResponse(
        violation_count=assessment.violation_count,
        message="Violation logged successfully" if assessment.violation_count < 3 else "Assessment auto-submitted due to violations"
    )


@router.post("/{assessment_id}/validate-timer", response_model=TimerValidationResponse, status_code=status.HTTP_200_OK)
def validate_timer(
    assessment_id: int,
    timer_data: TimerValidationRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Validate client-reported timer against server-side timer.
    
    Args:
        assessment_id: Assessment ID
        timer_data: Client-reported time remaining
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Timer validation result
    """
    from datetime import datetime
    
    ASSESSMENT_DURATION_SECONDS = 2400  # 40 minutes
    TOLERANCE_SECONDS = 30  # Allow ±30 seconds difference
    
    # Get assessment
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id,
        Assessment.user_id == current_user.id
    ).first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    # Use server_start_time if available, otherwise fall back to started_at
    start_time = assessment.server_start_time or assessment.started_at
    if not start_time:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assessment start time not found"
        )
    
    # Calculate server-side time remaining (use timezone-aware for comparison)
    from datetime import timezone
    now = datetime.now(timezone.utc)
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    
    elapsed_seconds = int((now - start_time).total_seconds())
    server_time_remaining = max(0, ASSESSMENT_DURATION_SECONDS - elapsed_seconds)
    
    # Compare with client-reported time
    difference = abs(server_time_remaining - timer_data.client_time_remaining)
    is_valid = difference <= TOLERANCE_SECONDS and server_time_remaining >= 0
    
    return TimerValidationResponse(
        is_valid=is_valid,
        server_time_remaining=server_time_remaining,
        difference=difference,
        message=None if is_valid else f"Timer mismatch detected. Server: {server_time_remaining}s, Client: {timer_data.client_time_remaining}s"
    )


@router.post("/{assessment_id}/complete", response_model=AssessmentCompleteResponse)
def complete_assessment_session(
    assessment_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Complete entire assessment and get final results with ELO update.
    Includes server-side timer validation and violation checks.
    
    Args:
        assessment_id: Assessment ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Assessment completion details with new ELO rating
    """
    from datetime import datetime
    
    ASSESSMENT_DURATION_SECONDS = 2400  # 40 minutes
    
    # Get assessment
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id,
        Assessment.user_id == current_user.id
    ).first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    # Server-side timer validation (use timezone-aware for comparison)
    start_time = assessment.server_start_time or assessment.started_at
    if start_time:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        
        elapsed_seconds = int((now - start_time).total_seconds())
        server_time_remaining = ASSESSMENT_DURATION_SECONDS - elapsed_seconds
        
        if server_time_remaining < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Assessment time has expired. Server time remaining: {server_time_remaining} seconds"
            )
    
    from app.db.models import User
    user = db.query(User).filter(User.id == current_user.id).first()

    # If already auto-submitted due to violations, return existing results and ELO so frontend can show them
    if assessment.auto_submitted:
        from datetime import timezone
        completed_at_value = assessment.completed_at
        if completed_at_value is None:
            completed_at_value = datetime.now(timezone.utc)
        sa = assessment.section_a_score or 0.0
        sb = assessment.section_b_score or 0.0
        sc = assessment.section_c_score or 0.0
        total = assessment.total_score or 0.0
        if total == 0.0 and (sa or sb or sc):
            total = round(sa + sb + sc, 2)
        return {
            "assessment_id": assessment_id,
            "total_score": total,
            "section_a_score": round(sa, 2),
            "section_b_score": round(sb, 2),
            "section_c_score": round(sc, 2),
            "new_elo_rating": user.elo_rating if user else 0,
            "completed_at": completed_at_value,
            "detailed_scores": None,
            "auto_submitted": True,
        }

    result = complete_assessment_flow(db, assessment_id, current_user.id)
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    new_elo = update_elo_after_assessment(db, current_user.id, assessment_id)

    if not assessment.completed_at:
        assessment.completed_at = datetime.utcnow()
        db.commit()

    completed_at_value = assessment.completed_at
    if hasattr(completed_at_value, 'isoformat'):
        completed_at_value = completed_at_value.isoformat()

    return {
        "assessment_id": assessment_id,
        "total_score": result["scores"]["total_score"],
        "section_a_score": result["scores"]["section_a_score"],
        "section_b_score": result["scores"]["section_b_score"],
        "section_c_score": result["scores"]["section_c_score"],
        "new_elo_rating": new_elo,
        "completed_at": completed_at_value,
        "detailed_scores": None,
    }


@router.get("/{assessment_id}/results")
def get_assessment_results(
    assessment_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Get detailed assessment results.
    
    Args:
        assessment_id: Assessment ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Detailed assessment results
    """
    from app.db.models import Assessment
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id,
        Assessment.user_id == current_user.id
    ).first()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    
    if assessment.status != AssessmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment not completed yet"
        )
    
    # Get all results
    from app.services.scoring_service import get_section_results
    mcq_results = get_section_results(db, assessment_id, AssessmentSection.A)
    logic_results = get_section_results(db, assessment_id, AssessmentSection.B)
    coding_results = get_section_results(db, assessment_id, AssessmentSection.C)
    
    return {
        "assessment_id": assessment_id,
        "total_score": assessment.total_score,
        "section_a_score": assessment.section_a_score,
        "section_b_score": assessment.section_b_score,
        "section_c_score": assessment.section_c_score,
        "section_a_results": [
            {
                "question_id": r.question_id,
                "is_correct": r.is_correct,
                "score": r.score,
                "attempts": r.attempts_count
            }
            for r in mcq_results
        ],
        "section_b_results": [
            {
                "question_id": r.question_id,
                "is_correct": r.is_correct,
                "score": r.score,
                "attempts": r.attempts_count
            }
            for r in logic_results
        ],
        "section_c_results": [
            {
                "question_id": r.question_id,
                "is_correct": r.is_correct,
                "score": r.score,
                "attempts": r.attempts_count,
                "execution_metadata": r.execution_metadata
            }
            for r in coding_results
        ],
        "completed_at": assessment.completed_at.isoformat()
    }
