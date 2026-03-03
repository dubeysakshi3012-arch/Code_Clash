"""Submission API routes for Online Judge."""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import Optional
from app.db.session import get_db
from app.core.rate_limit import limiter
from app.db.models import User, SubmissionStatus
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionResponse,
    SubmissionStatusResponse,
    SubmissionListResponse
)
from app.services.submission_service import (
    create_submission,
    get_submission,
    queue_submission_evaluation,
    get_submission_status,
    list_user_submissions
)
from app.api.v1.auth import get_current_user_from_token

router = APIRouter(prefix="/submission", tags=["submission"])


@router.post("/submit", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def submit_code(
    request: Request,
    submission_data: SubmissionCreate,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Submit code for evaluation.
    
    Creates a submission record and queues it for evaluation.
    Returns submission_id immediately (non-blocking).
    
    Args:
        submission_data: Submission data (code, language, problem_id)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Submission object with submission_id
    """
    # Validate problem_id if provided
    if submission_data.problem_id:
        from app.services.question_service import get_question_by_id
        question = get_question_by_id(db, submission_data.problem_id)
        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Problem {submission_data.problem_id} not found"
            )
    
    # Create submission
    submission = create_submission(
        db=db,
        user_id=current_user.id,
        source_code=submission_data.source_code,
        language=submission_data.language,
        problem_id=submission_data.problem_id
    )
    
    # Queue evaluation (only if problem_id is provided)
    if submission_data.problem_id:
        try:
            task_id = queue_submission_evaluation(submission.id)
            # Store task_id in execution_result for tracking (optional)
            submission.execution_result = {"celery_task_id": task_id}
            db.commit()
        except Exception as e:
            # If queueing fails, mark submission as failed
            submission.status = SubmissionStatus.FAILED
            submission.error_message = f"Failed to queue evaluation: {str(e)}"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to queue submission for evaluation"
            )
    else:
        # No problem_id - cannot evaluate, just store submission
        submission.status = SubmissionStatus.COMPLETED
        submission.verdict = "SKIPPED"
        submission.error_message = "No problem_id provided - submission stored but not evaluated"
        db.commit()
    
    return submission


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission_details(
    submission_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Get full submission details.
    
    Args:
        submission_id: Submission ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Submission object
    """
    submission = get_submission(db, submission_id, user_id=current_user.id)
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )
    
    return submission


@router.get("/{submission_id}/status", response_model=SubmissionStatusResponse)
def get_submission_status_endpoint(
    submission_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Get lightweight submission status.
    
    Args:
        submission_id: Submission ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Submission status information
    """
    submission = get_submission(db, submission_id, user_id=current_user.id)
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )
    
    return SubmissionStatusResponse(
        id=submission.id,
        status=submission.status,
        verdict=submission.verdict,
        test_cases_passed=submission.test_cases_passed,
        total_test_cases=submission.total_test_cases,
        execution_time=submission.execution_time,
        memory_usage=submission.memory_usage
    )


@router.get("/user/{user_id}", response_model=SubmissionListResponse)
def list_user_submissions_endpoint(
    user_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    verdict: Optional[str] = Query(default=None)
):
    """
    List user's submissions with pagination and filtering.
    
    Args:
        user_id: User ID (must match current_user.id)
        current_user: Current authenticated user
        db: Database session
        limit: Maximum number of results (1-100)
        offset: Number of results to skip
        status_filter: Optional status filter (queued, processing, completed, failed)
        verdict: Optional verdict filter
        
    Returns:
        Paginated list of submissions
    """
    # Authorization check
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's submissions"
        )
    
    # Parse status filter
    status_enum = None
    if status_filter:
        try:
            status_enum = SubmissionStatus(status_filter.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}. Must be one of: queued, processing, completed, failed"
            )
    
    submissions, total = list_user_submissions(
        db=db,
        user_id=user_id,
        limit=limit,
        offset=offset,
        status=status_enum,
        verdict=verdict
    )
    
    return SubmissionListResponse(
        submissions=submissions,
        total=total,
        limit=limit,
        offset=offset
    )
