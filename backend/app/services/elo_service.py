"""ELO rating calculation service.

Enhanced ELO calculation based on comprehensive assessment performance:
- Section-wise performance (MCQ, Logic, Coding)
- Total score percentage
- Coding problem efficiency
- Attempts and time factors
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import User, Assessment, AssessmentResult, AssessmentSection
from app.services.scoring_service import get_section_results


def calculate_initial_elo(
    db: Session,
    user_id: int,
    assessment_id: int
) -> int:
    """
    Calculate initial ELO rating based on comprehensive assessment performance.
    
    Formula:
    - Base ELO: 1000
    - Score-based adjustment: (total_score / 100) * 500
    - Section bonuses:
      - Perfect Section A: +50
      - Perfect Section B: +50
      - Perfect Section C: +100
    - Coding efficiency bonus: up to +50
    - Attempts penalty: -10 per extra attempt (beyond 1)
    
    Args:
        db: Database session
        user_id: User ID
        assessment_id: Assessment ID
        
    Returns:
        Calculated ELO rating
    """
    assessment = db.query(Assessment).filter(
        Assessment.id == assessment_id
    ).first()
    
    if not assessment:
        return 1000  # Default starting ELO
    
    # Base ELO
    base_elo = 1000
    
    # Score-based adjustment (0-100 score maps to 0-500 ELO points)
    total_score = assessment.total_score or 0.0
    score_adjustment = (total_score / 100.0) * 500.0
    
    # Section bonuses
    section_bonus = 0.0
    
    # Section A (MCQ) - perfect score bonus
    if assessment.section_a_score and assessment.section_a_score >= 24.5:  # Near perfect
        section_bonus += 50.0
    
    # Section B (Logic) - perfect score bonus
    if assessment.section_b_score and assessment.section_b_score >= 24.5:
        section_bonus += 50.0
    
    # Section C (Coding) - perfect score bonus
    if assessment.section_c_score and assessment.section_c_score >= 49.0:
        section_bonus += 100.0
    
    # Coding efficiency bonus
    coding_bonus = 0.0
    coding_results = get_section_results(db, assessment_id, AssessmentSection.C)
    if coding_results:
        total_attempts = sum(r.attempts_count for r in coding_results)
        avg_attempts = total_attempts / len(coding_results)
        
        # Bonus for solving with fewer attempts
        if avg_attempts <= 1.5:
            coding_bonus += 50.0
        elif avg_attempts <= 2.0:
            coding_bonus += 25.0
        
        # Bonus for efficient solutions
        total_runtime = sum(
            r.execution_metadata.get("runtime", 0.0) if r.execution_metadata else 0.0
            for r in coding_results
        )
        if total_runtime > 0 and total_runtime < 2.0:  # Fast execution
            coding_bonus += 25.0
    
    # Attempts penalty (for excessive attempts)
    attempts_penalty = 0.0
    all_results = db.query(AssessmentResult).filter(
        AssessmentResult.assessment_id == assessment_id
    ).all()
    total_attempts = sum(r.attempts_count for r in all_results)
    expected_attempts = len(all_results)  # One attempt per question expected
    extra_attempts = max(0, total_attempts - expected_attempts)
    attempts_penalty = extra_attempts * 10.0
    
    # Calculate final ELO
    elo = base_elo + score_adjustment + section_bonus + coding_bonus - attempts_penalty
    
    # Ensure ELO is within reasonable bounds (0-2000)
    elo = max(0, min(2000, elo))
    
    return int(elo)


def update_elo(db: Session, user_id: int, new_elo: int) -> None:
    """
    Update user's ELO rating.
    
    Args:
        db: Database session
        user_id: User ID
        new_elo: New ELO rating to set
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.elo_rating = new_elo
        db.commit()


def update_elo_after_assessment(
    db: Session,
    user_id: int,
    assessment_id: int
) -> int:
    """
    Calculate and update ELO rating after assessment completion.
    
    Args:
        db: Database session
        user_id: User ID
        assessment_id: Assessment ID
        
    Returns:
        New ELO rating
    """
    new_elo = calculate_initial_elo(db, user_id, assessment_id)
    update_elo(db, user_id, new_elo)
    return new_elo


# ELO K-factor for PvP (slightly lower for score-based to avoid big swings)
ELO_K = 32
# Time modifier: max ±5 ELO for fast/slow finish
ELO_TIME_MODIFIER_CAP = 5
logger = logging.getLogger(__name__)


def _expected_score(rating_a: int, rating_b: int) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def _time_modifier(
    time_used_seconds: float,
    time_available_seconds: float,
    normalized_score: float,
) -> float:
    """Return ELO modifier in [-ELO_TIME_MODIFIER_CAP, +ELO_TIME_MODIFIER_CAP]."""
    if not time_available_seconds or time_available_seconds <= 0:
        return 0.0
    ratio = time_used_seconds / time_available_seconds
    # Fast finish and scored well -> small bonus
    if ratio < 0.5 and normalized_score > 0.5:
        return min(ELO_TIME_MODIFIER_CAP, (0.5 - ratio) * 15.0)  # up to +5
    # Slow finish and scored low -> small penalty
    if ratio > 0.9 and normalized_score < 0.5:
        return max(-ELO_TIME_MODIFIER_CAP, (0.9 - ratio) * 25.0)  # down to -5
    return 0.0


def update_elo_after_match_with_scores(
    db: Session,
    id_a: int,
    id_b: int,
    score_a: float,
    score_b: float,
    max_possible_score: float,
    time_used_a: Optional[float] = None,
    time_used_b: Optional[float] = None,
    time_available_seconds: Optional[float] = None,
) -> tuple[int, int]:
    """
    Update both players' ELO after a PvP match using actual points and optional time.
    Normalizes scores to [0,1], applies ELO delta, optional time bonus/penalty, then wins/losses.
    Draws (equal scores) still update ELO; wins/losses only incremented when one player has higher score.
    """
    user_a = db.query(User).filter(User.id == id_a).first()
    user_b = db.query(User).filter(User.id == id_b).first()
    if not user_a or not user_b:
        return (user_a.elo_rating if user_a else 0, user_b.elo_rating if user_b else 0)

    # Normalize scores to [0, 1] (clamp to max)
    if max_possible_score and max_possible_score > 0:
        norm_a = max(0.0, min(1.0, score_a / max_possible_score))
        norm_b = max(0.0, min(1.0, score_b / max_possible_score))
    else:
        total = score_a + score_b
        if total > 0:
            norm_a = score_a / total
            norm_b = score_b / total
        else:
            norm_a = norm_b = 0.5

    r_a = user_a.elo_rating or 1000
    r_b = user_b.elo_rating or 1000
    e_a = _expected_score(r_a, r_b)
    e_b = _expected_score(r_b, r_a)

    delta_a = ELO_K * (norm_a - e_a)
    delta_b = ELO_K * (norm_b - e_b)

    # Time modifier (±5)
    if time_available_seconds and time_available_seconds > 0:
        if time_used_a is not None:
            delta_a += _time_modifier(time_used_a, time_available_seconds, norm_a)
        if time_used_b is not None:
            delta_b += _time_modifier(time_used_b, time_available_seconds, norm_b)

    new_elo_a = max(0, min(2000, int(r_a + delta_a)))
    new_elo_b = max(0, min(2000, int(r_b + delta_b)))
    user_a.elo_rating = new_elo_a
    user_b.elo_rating = new_elo_b

    # Wins/losses only when not draw
    if score_a > score_b:
        user_a.wins = (user_a.wins or 0) + 1
        user_b.losses = (user_b.losses or 0) + 1
    elif score_b > score_a:
        user_b.wins = (user_b.wins or 0) + 1
        user_a.losses = (user_a.losses or 0) + 1

    logger.info(
        "ELO match update id_a=%s id_b=%s score_a=%s score_b=%s max=%s norm_a=%.3f norm_b=%.3f delta_a=%.1f delta_b=%.1f new_elo_a=%s new_elo_b=%s",
        id_a, id_b, score_a, score_b, max_possible_score, norm_a, norm_b, delta_a, delta_b, new_elo_a, new_elo_b,
    )
    db.commit()
    return (new_elo_a, new_elo_b)


def update_elo_after_match(
    db: Session,
    winner_id: int,
    loser_id: int
) -> tuple[int, int]:
    """
    Update both players' ELO and wins/losses after a PvP match (binary win/loss).
    Delegates to score-based update with normalized 1/0 for backward compatibility.
    """
    return update_elo_after_match_with_scores(
        db,
        winner_id,
        loser_id,
        score_a=1.0,
        score_b=0.0,
        max_possible_score=1.0,
    )
