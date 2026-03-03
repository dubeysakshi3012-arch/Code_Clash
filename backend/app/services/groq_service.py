"""Groq-based match question generation (free tier). Same prompt/JSON shape as Gemini; reuse DB creation."""

import json
import logging
import traceback
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import ProgrammingLanguage
from app.services.gemini_service import (
    _create_question_from_gemini,
    _difficulty_from_elo,
)

logger = logging.getLogger(__name__)

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

GROQ_PROMPT_TEMPLATE = """You are a coding assessment question generator. Generate exactly {count} programming questions for a PvP match.
Average player ELO: {elo}. Language: {language}. Difficulty: {difficulty}.

Respond with a JSON object with a single key "questions" whose value is an array of question objects. Each question must have:
- concept_name: string (e.g. "Two Pointers", "Binary Search")
- difficulty_tag: "easy" | "medium" | "hard"
- question_type: "mcq" | "logic_trace" | "coding"
- logic_description: string (short description or question text)
- options: object only for MCQ, e.g. {{"A": "option A", "B": "option B", "C": "option C", "D": "option D"}}
- correct_answer: string (for MCQ the letter e.g. "B", for logic_trace the exact answer)
- problem_statement: string (for coding: full problem description)
- starter_code: string (for coding: template in the given language)
- test_cases: array of {{"input": string, "expected_output": string, "is_hidden": boolean}}
- solution_function_names: array of strings ONLY for coding (e.g. ["sum_numbers", "add"]) — the exact function name(s) the runner should call; must match the function name in starter_code

For coding questions include at least 2 test_cases and solution_function_names. Use the programming language: {language}.
Return ONLY valid JSON with the "questions" key, no markdown or extra text."""


def _safe_parse_groq_response(text: str) -> list:
    """Parse Groq response into a list of question dicts. Accepts JSON array or object with 'questions' key."""
    if not text or not isinstance(text, str):
        return []
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "questions" in data:
        q = data["questions"]
        return q if isinstance(q, list) else []
    return []


def generate_match_questions(
    db: Session,
    elo_avg: int,
    language: ProgrammingLanguage,
    count: int = 3,
    difficulty: Optional[str] = None,
) -> List[int]:
    """
    Try to generate match questions via Groq. On failure or invalid output, return empty list
    so caller can fall back to next option (Gemini or DB). Never raises.
    """
    if not settings.GROQ_API_KEY:
        return []

    try:
        return _generate_match_questions_groq_impl(db, elo_avg, language, count, difficulty)
    except Exception as e:
        logger.warning("Groq generate_match_questions failed: %s", e)
        logger.debug(traceback.format_exc())
        return []


def _generate_match_questions_groq_impl(
    db: Session,
    elo_avg: int,
    language: ProgrammingLanguage,
    count: int,
    difficulty: Optional[str],
) -> List[int]:
    from groq import Groq

    model = (getattr(settings, "GROQ_MODEL", None) or "").strip() or DEFAULT_GROQ_MODEL
    client = Groq(api_key=settings.GROQ_API_KEY)
    difficulty = difficulty or _difficulty_from_elo(elo_avg)
    prompt = GROQ_PROMPT_TEMPLATE.format(
        count=count,
        elo=elo_avg,
        language=language.value,
        difficulty=difficulty,
    )
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_completion_tokens": 8192,
        "response_format": {"type": "json_object"},
    }
    if "gpt-oss" in model.lower():
        kwargs["reasoning_effort"] = "medium"
    response = client.chat.completions.create(**kwargs)
    if not getattr(response, "choices", None) or not response.choices:
        return []
    first = response.choices[0]
    if not first or not getattr(first, "message", None):
        return []
    content = getattr(first.message, "content", None)
    text = (content or "").strip() if content is not None else ""
    if not text:
        return []

    data = _safe_parse_groq_response(text)
    if not data:
        return []

    question_ids: List[int] = []
    for item in data[:count]:
        if not isinstance(item, dict):
            continue
        try:
            q_id = _create_question_from_gemini(db, item, language)
            if q_id:
                question_ids.append(q_id)
        except Exception:
            continue
    return question_ids
