"""Gemini-based match question generation with DB fallback."""

import json
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Question, QuestionTemplate, TestCase, ProgrammingLanguage
from app.db.models.question import DifficultyTag, QuestionType, AssessmentSection

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are a coding assessment question generator. Generate exactly {count} programming questions for a PvP match.
Average player ELO: {elo}. Language: {language}. Difficulty: {difficulty}.

Output a JSON array of questions. Each question must have:
- concept_name: string (e.g. "Two Pointers", "Binary Search")
- difficulty_tag: "easy" | "medium" | "hard"
- question_type: "mcq" | "logic_trace" | "coding"
- logic_description: string (short description or question text)
- options: object only for MCQ, e.g. {"A": "option A", "B": "option B", "C": "option C", "D": "option D"}
- correct_answer: string (for MCQ the letter e.g. "B", for logic_trace the exact answer)
- problem_statement: string (for coding: full problem description)
- starter_code: string (for coding: template in the given language)
- test_cases: array of {"input": string, "expected_output": string, "is_hidden": boolean}
- solution_function_names: array of strings ONLY for coding (e.g. ["sum_numbers", "add"]) — the exact function name(s) the runner should call; must match the function name in starter_code

For coding questions include at least 2 test_cases and solution_function_names. Use the programming language: {language}.
Return ONLY valid JSON array, no markdown or extra text."""


def _difficulty_from_elo(elo: int) -> str:
    if elo < 1000:
        return "easy"
    if elo < 1500:
        return "medium"
    return "hard"


def generate_match_questions(
    db: Session,
    elo_avg: int,
    language: ProgrammingLanguage,
    count: int = 3,
    difficulty: Optional[str] = None,
) -> List[int]:
    """
    Try to generate match questions via Gemini. On failure or invalid output, return empty list
    so caller can fall back to DB question bank.
    """
    if not settings.GEMINI_API_KEY:
        return []

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        difficulty = difficulty or _difficulty_from_elo(elo_avg)
        prompt = PROMPT_TEMPLATE.format(
            count=count,
            elo=elo_avg,
            language=language.value,
            difficulty=difficulty,
        )
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.7, "max_output_tokens": 8192},
        )
        text = (response.text or "").strip()
        if not text:
            return []
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("Gemini returned invalid JSON: %s", e)
            return []
        if not isinstance(data, list) or len(data) == 0:
            return []
        question_ids = []
        for item in data[:count]:
            if not isinstance(item, dict):
                logger.warning("Gemini question item skipped (not a dict)")
                continue
            try:
                q_id = _create_question_from_gemini(db, item, language)
                if q_id:
                    question_ids.append(q_id)
            except Exception as e:
                logger.warning("Gemini question item invalid: %s", e)
                continue
        return question_ids
    except Exception as e:
        logger.warning("Gemini generate_match_questions failed: %s", e)
        return []


def _create_question_from_gemini(db: Session, item: dict, language: ProgrammingLanguage) -> Optional[int]:
    """Create Question, QuestionTemplate, TestCase from one Gemini item. Return question id or None."""
    concept = (item.get("concept_name") or "Generated").strip()[:255]
    diff = (item.get("difficulty_tag") or "medium").lower()
    try:
        difficulty_tag = DifficultyTag(diff)
    except ValueError:
        difficulty_tag = DifficultyTag.MEDIUM
    qtype = (item.get("question_type") or "mcq").lower()
    try:
        question_type = QuestionType(qtype)
    except ValueError:
        question_type = QuestionType.MCQ
    logic_desc = (item.get("logic_description") or "")[:5000]
    options = item.get("options") if isinstance(item.get("options"), dict) else None
    correct_answer = (item.get("correct_answer") or "")[:500] if item.get("correct_answer") else None
    section = AssessmentSection.A if question_type == QuestionType.MCQ else (
        AssessmentSection.B if question_type == QuestionType.LOGIC_TRACE else AssessmentSection.C
    )
    question = Question(
        concept_name=concept,
        difficulty_tag=difficulty_tag,
        logic_description=logic_desc,
        time_limit=30,
        memory_limit=256,
        question_type=question_type,
        section=section,
        points=1.0,
        options=options,
        correct_answer=correct_answer,
    )
    if question_type == QuestionType.CODING:
        names = item.get("solution_function_names")
        if not names and item.get("solution_function_name"):
            names = [item.get("solution_function_name")]
        if names:
            if isinstance(names, list):
                question.solution_function_names = [str(n).strip() for n in names if n]
            else:
                question.solution_function_names = [str(names).strip()]
    db.add(question)
    db.flush()
    problem_statement = (item.get("problem_statement") or logic_desc)[:10000]
    starter_code = (item.get("starter_code") or "")[:10000] if item.get("starter_code") else None
    template = QuestionTemplate(
        question_id=question.id,
        language=language,
        problem_statement=problem_statement,
        starter_code=starter_code,
    )
    db.add(template)

    def _norm(s: str) -> str:
        if s is None:
            return ""
        s = str(s).strip().replace("\r\n", "\n").replace("\r", "\n")
        return s[:5000]

    for i, tc in enumerate(item.get("test_cases") or []):
        if not isinstance(tc, dict):
            continue
        input_val = tc.get("input") or tc.get("input_data")
        expected_val = tc.get("expected_output") or tc.get("expected")
        if input_val is None or expected_val is None:
            continue
        db.add(TestCase(
            question_id=question.id,
            input_data=_norm(input_val),
            expected_output=_norm(expected_val),
            is_hidden=bool(tc.get("is_hidden", True)),
            order=i,
        ))
    db.commit()
    return question.id
