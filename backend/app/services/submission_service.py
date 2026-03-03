"""Submission service for managing code submissions."""

from sqlalchemy.orm import Session
from typing import Optional, List
from app.db.models import Submission, SubmissionStatus, ProgrammingLanguage
from app.workers.judge_tasks import evaluate_submission_task


def create_submission(
    db: Session,
    user_id: int,
    source_code: str,
    language: ProgrammingLanguage,
    problem_id: Optional[int] = None
) -> Submission:
    """
    Create a new submission record.
    
    Args:
        db: Database session
        user_id: User ID
        source_code: Source code to evaluate
        language: Programming language
        problem_id: Optional problem/question ID
        
    Returns:
        Created Submission object
    """
    submission = Submission(
        user_id=user_id,
        problem_id=problem_id,
        language=language,
        source_code=source_code,
        status=SubmissionStatus.QUEUED
    )
    
    db.add(submission)
    db.commit()
    db.refresh(submission)
    
    return submission


def get_submission(
    db: Session,
    submission_id: int,
    user_id: Optional[int] = None
) -> Optional[Submission]:
    """
    Get submission by ID.
    
    Args:
        db: Database session
        submission_id: Submission ID
        user_id: Optional user ID to filter by (for authorization)
        
    Returns:
        Submission object or None
    """
    query = db.query(Submission).filter(Submission.id == submission_id)
    
    if user_id:
        query = query.filter(Submission.user_id == user_id)
    
    return query.first()


def queue_submission_evaluation(submission_id: int) -> str:
    """
    Queue submission for evaluation.
    
    Args:
        submission_id: Submission ID to evaluate
        
    Returns:
        Celery task ID for tracking
    """
    task = evaluate_submission_task.delay(submission_id)
    return task.id


def get_submission_status(db: Session, submission_id: int) -> Optional[dict]:
    """
    Get submission status information.
    
    Args:
        db: Database session
        submission_id: Submission ID
        
    Returns:
        Dictionary with status information or None
    """
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    
    if not submission:
        return None
    
    return {
        "id": submission.id,
        "status": submission.status.value if hasattr(submission.status, 'value') else str(submission.status),
        "verdict": submission.verdict,
        "test_cases_passed": submission.test_cases_passed,
        "total_test_cases": submission.total_test_cases,
        "execution_time": submission.execution_time,
        "memory_usage": submission.memory_usage,
        "error_message": submission.error_message
    }


def list_user_submissions(
    db: Session,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    status: Optional[SubmissionStatus] = None,
    verdict: Optional[str] = None
) -> tuple[List[Submission], int]:
    """
    List user's submissions with pagination and filtering.
    
    Args:
        db: Database session
        user_id: User ID
        limit: Maximum number of results
        offset: Number of results to skip
        status: Optional status filter
        verdict: Optional verdict filter
        
    Returns:
        Tuple of (list of submissions, total count)
    """
    query = db.query(Submission).filter(Submission.user_id == user_id)
    
    if status:
        query = query.filter(Submission.status == status)
    
    if verdict:
        query = query.filter(Submission.verdict == verdict)
    
    total = query.count()
    
    submissions = query.order_by(Submission.created_at.desc()).offset(offset).limit(limit).all()
    
    return submissions, total
