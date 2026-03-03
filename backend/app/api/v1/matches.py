"""Match API routes - list and get match detail for current user."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request, status
from sqlalchemy.orm import Session
from app.core.rate_limit import limiter

from app.db.session import get_db
from app.db.models import User, ProgrammingLanguage
from app.db.models.match import MatchSubmission
from app.api.v1.auth import get_current_user_from_token
from app.services.match_service import get_matches_for_user, create_match, get_match_questions
from app.services.question_service import get_question_ids_for_match
from app.services.gemini_service import generate_match_questions as generate_match_questions_gemini
from app.services.groq_service import generate_match_questions as generate_match_questions_groq
from app.schemas.match import (
    MatchListResponse,
    MatchDetailResponse,
    MatchParticipantSummary,
    MatchQuestionSummary,
    MatchCreateRequest,
    MatchCreateResponse,
    MatchTestRequest,
    MatchSubmitRequest,
    MatchSubmitResponse,
)
from app.schemas.assessment import TestResultResponse, TestCaseResult
from app.services.match_service import submit_match_answer, JudgeError, get_match_by_id
from app.services.judge_service import get_judge_service
from app.services.docker_runner import _sanitize_error_for_client
from app.db.models import Question
from app.db.models.question import QuestionType
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/matches", tags=["matches"])


def require_socket_secret(x_socket_secret: Optional[str] = Header(None)) -> None:
    """Dependency: require valid Socket server secret for internal create-match."""
    if not settings.SOCKET_SERVER_SECRET:
        raise HTTPException(status_code=503, detail="Match creation not configured")
    if x_socket_secret != settings.SOCKET_SERVER_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/create", response_model=MatchCreateResponse)
@limiter.limit("20/hour")
def create_match_endpoint(
    request: Request,
    body: MatchCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_socket_secret),
):
    """Internal: create a match (called by Socket server). Returns match_id and question_ids."""
    lang = ProgrammingLanguage(body.language)
    question_ids = body.question_ids
    if not question_ids:
        users = db.query(User).filter(User.id.in_(body.participant_user_ids)).all()
        elo_avg = int(sum(getattr(u, "elo_rating", 1000) for u in users) / len(users)) if users else 1000
        question_ids = generate_match_questions_gemini(db, elo_avg, lang, count=3)
        if not question_ids:
            question_ids = generate_match_questions_groq(db, elo_avg, lang, count=3)
        if not question_ids:
            question_ids = get_question_ids_for_match(db, lang, count=3)
    if len(question_ids) < 1:
        raise HTTPException(
            status_code=503,
            detail="No questions available for this language. Please try again later or contact support.",
        )
    match = create_match(
        db,
        participant_user_ids=body.participant_user_ids,
        language=lang,
        question_ids=question_ids,
        time_limit_per_question=body.time_limit_per_question,
    )
    return MatchCreateResponse(
        match_id=match.id,
        question_ids=question_ids,
        time_limit_per_question=match.time_limit_per_question,
    )


@router.get("", response_model=List[MatchListResponse])
def list_my_matches(
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filter by status: waiting, in_progress, completed, abandoned"),
):
    """List matches the current user participated in."""
    from app.db.models import MatchStatus
    status_filter = None
    if status is not None:
        try:
            status_filter = MatchStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    matches = get_matches_for_user(db, current_user.id, limit=limit, offset=offset, status=status_filter)
    return [
        MatchListResponse(
            id=m.id,
            status=m.status.value,
            winner_id=m.winner_id,
            language=m.language.value,
            time_limit_per_question=m.time_limit_per_question,
            created_at=m.created_at,
            started_at=m.started_at,
            ended_at=m.ended_at,
        )
        for m in matches
    ]


@router.get("/{match_id}/questions")
def get_match_questions_endpoint(
    match_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """Get full question content for a match (problem statement, starter code, options, etc.). Participants only."""
    questions = get_match_questions(db, match_id, current_user.id)
    if questions == [] and get_match_by_id(db, match_id, current_user.id) is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return questions


@router.post("/{match_id}/submit", response_model=MatchSubmitResponse)
def submit_match_answer_endpoint(
    match_id: int,
    body: MatchSubmitRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """Submit an answer for a question in a match."""
    try:
        score, is_correct, match_completed, winner_id = submit_match_answer(
            db,
            match_id=match_id,
            user_id=current_user.id,
            question_id=body.question_id,
            answer_type=body.answer_type,
            answer_data=body.answer_data,
            mcq_answer=body.mcq_answer,
        )
    except ValueError as e:
        if "No test cases" in str(e):
            raise HTTPException(
                status_code=400,
                detail="This question has no test cases; try again later or contact support.",
            ) from e
        raise
    except JudgeError as e:
        raise HTTPException(
            status_code=503,
            detail=str(e) or "Judging failed; please try again.",
        ) from e
    return MatchSubmitResponse(
        score=score,
        is_correct=is_correct,
        match_completed=match_completed,
        winner_id=winner_id,
    )


@router.post("/{match_id}/test", response_model=TestResultResponse)
@limiter.limit("30/minute")
def test_match_code_endpoint(
    request: Request,
    match_id: int,
    body: MatchTestRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Run/Test code against visible test cases or custom input. Does not submit.
    Only participants can use this; match must be in progress.
    """
    from app.db.models.match import MatchStatus

    match = get_match_by_id(db, match_id, current_user.id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    if match.status != MatchStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Match is not in progress",
        )
    question_ids = [mq.question_id for mq in match.match_questions]
    if body.question_id not in question_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question not part of this match",
        )
    question = db.query(Question).filter(Question.id == body.question_id).first()
    if not question or question.question_type != QuestionType.CODING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or non-coding question",
        )
    judge = get_judge_service(match.language)
    solution_function_names = getattr(question, "solution_function_names", None) or []

    if body.custom_input:
        try:
            result = judge.run_custom_input(
                code=body.code,
                language=match.language,
                custom_input=body.custom_input,
                time_limit=question.time_limit or 30,
                memory_limit=question.memory_limit or 256,
            )
        except Exception as e:
            logger.exception("Match test run_custom_input failed for match_id=%s question_id=%s: %s", match_id, body.question_id, e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Code execution is temporarily unavailable. Please try again.",
            ) from e
        return TestResultResponse(
            passed=0,
            total=1,
            results=[
                TestCaseResult(
                    passed=False,
                    input=body.custom_input,
                    expected_output="",
                    actual_output=result.get("output", ""),
                    error=result.get("error"),
                )
            ],
            execution_time=result.get("execution_time", 0.0),
            error=_sanitize_error_for_client(result.get("error")),
        )

    visible_test_cases = [tc for tc in question.test_cases if not tc.is_hidden]
    if not visible_test_cases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No visible test cases for this question",
        )
    try:
        execution_result = judge.execute_code(
            code=body.code,
            language=match.language,
            test_cases=visible_test_cases,
            time_limit=question.time_limit or 30,
            memory_limit=question.memory_limit or 256,
            solution_function_names=solution_function_names if solution_function_names else None,
        )
    except Exception as e:
        logger.exception("Match test execute_code failed for match_id=%s question_id=%s: %s", match_id, body.question_id, e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Code execution is temporarily unavailable. Please try again.",
        ) from e
    test_results = execution_result.get("results", [])
    passed_count = sum(1 for r in test_results if r.get("passed", False))
    case_results = [
        TestCaseResult(
            passed=r.get("passed", False),
            input=r.get("input", ""),
            expected_output=r.get("expected_output", ""),
            actual_output=r.get("actual_output", ""),
            error=r.get("error"),
        )
        for r in test_results
    ]
    return TestResultResponse(
        passed=passed_count,
        total=len(visible_test_cases),
        results=case_results,
        execution_time=execution_result.get("execution_time", 0.0),
        error=_sanitize_error_for_client(execution_result.get("error")),
    )


@router.get("/{match_id}", response_model=MatchDetailResponse)
def get_match(
    match_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """Get match detail. Only participants can view."""
    match = get_match_by_id(db, match_id, current_user.id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    total_questions = len(match.match_questions)
    submission_counts: dict = {}
    if total_questions > 0:
        from sqlalchemy import func
        rows = (
            db.query(MatchSubmission.user_id, func.count(MatchSubmission.id).label("cnt"))
            .filter(MatchSubmission.match_id == match_id)
            .group_by(MatchSubmission.user_id)
            .all()
        )
        for row in rows:
            submission_counts[int(row[0])] = int(row[1])
    participants = [
        MatchParticipantSummary(
            user_id=p.user_id,
            score=p.score,
            left_at=p.left_at,
            submissions_count=submission_counts.get(p.user_id, 0),
        )
        for p in match.participants
    ]
    return MatchDetailResponse(
        id=match.id,
        status=match.status.value,
        winner_id=match.winner_id,
        language=match.language.value,
        time_limit_per_question=match.time_limit_per_question,
        server_started_at=match.server_started_at,
        created_at=match.created_at,
        started_at=match.started_at,
        ended_at=match.ended_at,
        participants=participants,
        questions=[
            MatchQuestionSummary(question_id=mq.question_id, order=mq.order)
            for mq in match.match_questions
        ],
    )
