"""Match service for PvP: create match, list, get detail, submit answer, complete match."""

import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple

from app.db.models import (
    Match,
    MatchParticipant,
    MatchQuestion,
    MatchSubmission,
    MatchStatus,
    ProgrammingLanguage,
)
from app.db.models.question import Question, QuestionTemplate, TestCase
from app.services.question_service import get_question_by_id, validate_mcq_answer, validate_logic_answer
from app.services.judge_service import JudgeService
from app.services.elo_service import update_elo_after_match_with_scores

logger = logging.getLogger(__name__)
judge_service = JudgeService()


class JudgeError(Exception):
    """Raised when code judging fails (Docker, timeout, etc.). Do not record as user incorrect."""
    pass


def create_match(
    db: Session,
    participant_user_ids: List[int],
    language: ProgrammingLanguage,
    question_ids: List[int],
    time_limit_per_question: int = 300,
) -> Match:
    """
    Create a new PvP match with two participants and ordered questions.
    Caller (e.g. Socket server) is responsible for ensuring exactly two participants.
    """
    match = Match(
        status=MatchStatus.IN_PROGRESS,
        language=language,
        time_limit_per_question=time_limit_per_question,
        server_started_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
    )
    db.add(match)
    db.flush()

    for user_id in participant_user_ids:
        db.add(MatchParticipant(match_id=match.id, user_id=user_id))
    for i, qid in enumerate(question_ids):
        db.add(MatchQuestion(match_id=match.id, question_id=qid, order=i))
    db.commit()
    db.refresh(match)
    return match


def get_matches_for_user(
    db: Session,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    status: Optional[MatchStatus] = None,
) -> List[Match]:
    """List matches the user participated in, newest first."""
    q = (
        db.query(Match)
        .join(MatchParticipant)
        .filter(MatchParticipant.user_id == user_id)
    )
    if status is not None:
        q = q.filter(Match.status == status)
    return q.order_by(Match.created_at.desc()).offset(offset).limit(limit).all()


def get_match_by_id(db: Session, match_id: int, user_id: int) -> Optional[Match]:
    """Get match by id only if the user is a participant."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        return None
    participant = (
        db.query(MatchParticipant)
        .filter(
            MatchParticipant.match_id == match_id,
            MatchParticipant.user_id == user_id,
        )
        .first()
    )
    if not participant:
        return None
    return match


def get_match_questions(db: Session, match_id: int, user_id: int) -> List[dict]:
    """
    Get full question payload for a match (same shape as assessment questions).
    Only participants can access. Returns list of dicts with id, concept_name,
    problem_statement, starter_code, type, options, visible_test_cases, etc.
    """
    match = get_match_by_id(db, match_id, user_id)
    if not match:
        return []
    mqs = (
        db.query(MatchQuestion)
        .filter(MatchQuestion.match_id == match_id)
        .order_by(MatchQuestion.order)
        .all()
    )
    questions_data = []
    for mq in mqs:
        question = db.query(Question).filter(Question.id == mq.question_id).first()
        if not question:
            continue
        template = (
            db.query(QuestionTemplate)
            .filter(
                QuestionTemplate.question_id == question.id,
                QuestionTemplate.language == match.language,
            )
            .first()
        )
        if not template:
            continue
        visible_test_cases = (
            db.query(TestCase)
            .filter(
                TestCase.question_id == question.id,
                TestCase.is_hidden == False,
            )
            .order_by(TestCase.order)
            .all()
            )
        qtype = (question.question_type.value if question.question_type else "coding").lower()
        questions_data.append({
            "id": question.id,
            "concept_name": question.concept_name,
            "difficulty_tag": question.difficulty_tag.value if question.difficulty_tag else "medium",
            "logic_description": question.logic_description,
            "time_limit": question.time_limit or 30,
            "memory_limit": question.memory_limit or 256,
            "problem_statement": template.problem_statement,
            "starter_code": template.starter_code,
            "language": match.language.value,
            "type": qtype,
            "question_type": qtype,
            "options": question.options,
            "points": question.points,
            "solution_function_names": getattr(question, "solution_function_names", None) or [],
            "visible_test_cases": [
                {
                    "id": tc.id,
                    "input_data": tc.input_data,
                    "expected_output": tc.expected_output,
                    "order": tc.order,
                }
                for tc in visible_test_cases
            ],
        })
    return questions_data


def set_match_started(db: Session, match_id: int) -> None:
    """Set match status to in_progress and server_started_at."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if match:
        match.status = MatchStatus.IN_PROGRESS
        match.server_started_at = datetime.now(timezone.utc)
        match.started_at = match.server_started_at
        db.commit()


def set_match_ended(
    db: Session,
    match_id: int,
    winner_id: Optional[int],
    status: MatchStatus = MatchStatus.COMPLETED,
) -> None:
    """Set match ended_at, winner_id, and status."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if match:
        match.ended_at = datetime.now(timezone.utc)
        match.winner_id = winner_id
        match.status = status
        db.commit()


def _score_for_question(question, correct: bool, points: Optional[float] = None) -> float:
    if points is not None:
        return float(points) if correct else 0.0
    return 1.0 if correct else 0.0


def submit_match_answer(
    db: Session,
    match_id: int,
    user_id: int,
    question_id: int,
    answer_type: str,
    answer_data: Optional[str] = None,
    mcq_answer: Optional[str] = None,
) -> Tuple[float, bool, bool, Optional[int]]:
    """
    Submit an answer for a match question. Validates and records; if both players
    have submitted for all questions, computes winner and updates ELO.
    Returns (score, is_correct, match_completed, winner_id).
    """
    match = get_match_by_id(db, match_id, user_id)
    if not match:
        return (0.0, False, False, None)
    if match.status != MatchStatus.IN_PROGRESS and match.status != MatchStatus.WAITING:
        return (0.0, False, False, None)
    mq = next((mq for mq in match.match_questions if mq.question_id == question_id), None)
    if not mq:
        return (0.0, False, False, None)
    existing = (
        db.query(MatchSubmission)
        .filter(
            MatchSubmission.match_id == match_id,
            MatchSubmission.user_id == user_id,
            MatchSubmission.question_id == question_id,
        )
        .first()
    )
    if existing:
        return (existing.score or 0.0, bool(existing.is_correct), False, None)

    question = get_question_by_id(db, question_id)
    if not question:
        return (0.0, False, False, None)

    points = question.points or 1.0
    is_correct = False
    score = 0.0

    if answer_type == "mcq":
        ans = mcq_answer or (answer_data or "").strip()
        is_correct = validate_mcq_answer(question, ans)
        score = _score_for_question(question, is_correct, points)
    elif answer_type == "logic_trace":
        ans = (answer_data or "").strip()
        is_correct = validate_logic_answer(question, ans)
        score = _score_for_question(question, is_correct, points)
    elif answer_type == "coding" and answer_data:
        test_cases = list(question.test_cases) if question.test_cases else []
        if not test_cases:
            raise ValueError("No test cases configured for this question")
        try:
            solution_function_names = getattr(question, "solution_function_names", None) or []
            result = judge_service.execute_code(
                code=answer_data,
                language=match.language,
                test_cases=question.test_cases,
                time_limit=question.time_limit or 30,
                memory_limit=question.memory_limit or 256,
                solution_function_names=solution_function_names if solution_function_names else None,
            )
            passed = result.get("passed", False)
            is_correct = passed
            score = float(points) if passed else 0.0
            # Debug: log each test case so we can see expected vs actual when result is wrong
            for i, tc_result in enumerate(result.get("results") or []):
                logger.info(
                    "Match judge test case match_id=%s question_id=%s case=%s: input=%r expected=%r actual=%r passed=%s error=%s",
                    match_id,
                    question_id,
                    i + 1,
                    tc_result.get("input"),
                    tc_result.get("expected_output"),
                    tc_result.get("actual_output"),
                    tc_result.get("passed"),
                    tc_result.get("error"),
                )
            if not passed and (result.get("results") or []):
                logger.warning(
                    "Match judge FAILED match_id=%s question_id=%s: overall_passed=%s error=%s",
                    match_id,
                    question_id,
                    passed,
                    result.get("error"),
                )
        except Exception as e:
            logger.exception(
                "Match judge failed for match_id=%s question_id=%s: %s",
                match_id,
                question_id,
                e,
            )
            raise JudgeError("Judging failed; please try again.") from e
    else:
        return (0.0, False, False, None)

    db.add(
        MatchSubmission(
            match_id=match_id,
            user_id=user_id,
            question_id=question_id,
            answer_type=answer_type,
            answer_data=answer_data or mcq_answer,
            is_correct=is_correct,
            score=score,
        )
    )
    db.commit()

    completed, winner_id = _try_complete_match(db, match_id)
    return (score, is_correct, completed, winner_id)


def _try_complete_match(db: Session, match_id: int) -> Tuple[bool, Optional[int]]:
    """If both players have submitted for all questions, set winner and ELO. Return (completed, winner_id)."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match or match.status != MatchStatus.IN_PROGRESS:
        return (False, None)
    question_ids = [mq.question_id for mq in match.match_questions]
    participant_ids = [p.user_id for p in match.participants]
    if len(participant_ids) != 2:
        return (False, None)
    for uid in participant_ids:
        subs = (
            db.query(MatchSubmission)
            .filter(
                MatchSubmission.match_id == match_id,
                MatchSubmission.user_id == uid,
            )
            .all()
        )
        submitted_qids = {s.question_id for s in subs}
        if set(question_ids) != submitted_qids:
            return (False, None)
    scores = {}
    time_used_by_user = {}
    for uid in participant_ids:
        subs = (
            db.query(MatchSubmission)
            .filter(
                MatchSubmission.match_id == match_id,
                MatchSubmission.user_id == uid,
            )
            .all()
        )
        scores[uid] = sum(s.score or 0 for s in subs)
        if match.server_started_at and subs:
            last_submit = max(s.submitted_at for s in subs)
            time_used_by_user[uid] = (last_submit - match.server_started_at).total_seconds()
        else:
            time_used_by_user[uid] = None

    max_possible_score = 0.0
    for mq in match.match_questions:
        q = db.query(Question).filter(Question.id == mq.question_id).first()
        max_possible_score += (q.points if q and q.points is not None else 1.0)
    if max_possible_score <= 0:
        max_possible_score = float(len(question_ids))

    time_available_seconds = (match.time_limit_per_question or 300) * len(question_ids)

    a, b = participant_ids[0], participant_ids[1]
    if scores[a] > scores[b]:
        winner_id = a
        loser_id = b
    elif scores[b] > scores[a]:
        winner_id = b
        loser_id = a
    else:
        winner_id = None
        loser_id = None

    update_elo_after_match_with_scores(
        db,
        id_a=a,
        id_b=b,
        score_a=scores[a],
        score_b=scores[b],
        max_possible_score=max_possible_score,
        time_used_a=time_used_by_user.get(a),
        time_used_b=time_used_by_user.get(b),
        time_available_seconds=time_available_seconds,
    )
    set_match_ended(db, match_id, winner_id, MatchStatus.COMPLETED)
    for p in match.participants:
        p.score = scores.get(p.user_id)
    db.commit()
    return (True, winner_id)
