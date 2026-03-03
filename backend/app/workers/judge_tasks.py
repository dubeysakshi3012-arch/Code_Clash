"""Celery tasks for judge evaluation."""

import logging
from sqlalchemy.orm import Session
from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models import Submission, SubmissionStatus
from app.services.judge_service import get_judge_service
from app.services.question_service import get_question_by_id

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def evaluate_submission_task(self, submission_id: int):
    """
    Evaluate a submission asynchronously.
    
    Args:
        submission_id: ID of the submission to evaluate
        
    Returns:
        Dictionary with evaluation results
    """
    db: Session = SessionLocal()
    
    try:
        # Load submission
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            raise ValueError(f"Submission {submission_id} not found")
        
        # Update status to PROCESSING
        submission.status = SubmissionStatus.PROCESSING
        db.commit()
        
        # Load problem/question if provided
        question = None
        test_cases = []
        
        if submission.problem_id:
            question = get_question_by_id(db, submission.problem_id)
            if question:
                test_cases = question.test_cases
            else:
                raise ValueError(f"Problem {submission.problem_id} not found")
        else:
            # Generic submission without problem - cannot evaluate fully
            raise ValueError("Problem ID is required for evaluation")
        
        # Get judge service
        judge = get_judge_service(submission.language)
        
        # Evaluate submission
        evaluation_result = judge.evaluate_submission(
            code=submission.source_code,
            language=submission.language,
            question=question,
            all_test_cases=test_cases
        )
        
        # Extract results
        verdict = evaluation_result.get("verdict", "UNKNOWN")
        execution_time = evaluation_result.get("execution_time", 0.0)
        memory_usage = evaluation_result.get("memory_used", 0)
        results = evaluation_result.get("results", [])
        
        # Count passed test cases
        test_cases_passed = sum(1 for r in results if r.get("passed", False))
        total_test_cases = len(results)
        
        # Update submission with results
        submission.status = SubmissionStatus.COMPLETED
        submission.verdict = verdict
        submission.execution_time = execution_time
        submission.memory_usage = memory_usage
        submission.test_cases_passed = test_cases_passed
        submission.total_test_cases = total_test_cases
        submission.execution_result = evaluation_result
        submission.error_message = evaluation_result.get("error")
        
        from datetime import datetime
        submission.completed_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(
            f"Submission {submission_id} evaluated: verdict={verdict}, "
            f"passed={test_cases_passed}/{total_test_cases}"
        )
        
        db.close()
        
        return {
            "submission_id": submission_id,
            "verdict": verdict,
            "test_cases_passed": test_cases_passed,
            "total_test_cases": total_test_cases,
            "execution_time": execution_time,
            "memory_usage": memory_usage
        }
        
    except Exception as e:
        logger.error(f"Error evaluating submission {submission_id}: {e}", exc_info=True)
        
        # Update submission status to FAILED
        try:
            submission = db.query(Submission).filter(Submission.id == submission_id).first()
            if submission:
                submission.status = SubmissionStatus.FAILED
                submission.error_message = str(e)[:500]
                db.commit()
        except Exception as db_error:
            logger.error(f"Error updating submission status: {db_error}")
        finally:
            db.close()
        
        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        else:
            raise
