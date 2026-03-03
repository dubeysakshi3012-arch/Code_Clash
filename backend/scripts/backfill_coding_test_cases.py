"""
Backfill test cases for existing coding questions that have none.

Uses test case data from the question bank (by concept_name).
Run from backend directory: python scripts/backfill_coding_test_cases.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.db.models import Question, TestCase
from app.services.question_bank import get_coding_problems
from app.db.models.question import QuestionType


def backfill_coding_test_cases():
    """Insert test cases for coding questions that have none (matched by concept_name)."""
    db = SessionLocal()
    coding_problems = get_coding_problems()

    # Build map: concept_name -> list of test case dicts
    concept_to_cases = {}
    for q_data in coding_problems:
        cases = q_data.get("test_cases", [])
        if cases:
            concept_to_cases[q_data["concept_name"]] = cases

    if not concept_to_cases:
        print("No test cases found in question bank. Add test_cases to CODING_PROBLEMS first.")
        db.close()
        return

    coding_questions = db.query(Question).filter(
        Question.question_type == QuestionType.CODING
    ).all()

    updated = 0
    skipped = 0
    for question in coding_questions:
        cases = concept_to_cases.get(question.concept_name)
        if not cases:
            print(f"  Skip question id={question.id} (concept: {question.concept_name}): no bank data")
            skipped += 1
            continue

        existing_count = len(question.test_cases)
        if existing_count > 0:
            print(f"  Skip question id={question.id} (concept: {question.concept_name}): already has {existing_count} test cases")
            skipped += 1
            continue

        for idx, tc in enumerate(cases):
            test_case = TestCase(
                question_id=question.id,
                input_data=tc["input"],
                expected_output=tc["expected_output"],
                is_hidden=tc.get("is_hidden", False),
                order=idx,
            )
            db.add(test_case)
        print(f"  Backfilled {len(cases)} test cases for question id={question.id} ({question.concept_name})")
        updated += 1

    db.commit()
    db.close()
    print(f"Done. Updated {updated} questions, skipped {skipped}.")


if __name__ == "__main__":
    backfill_coding_test_cases()
