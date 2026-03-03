"""Script to list all questions/problems in the database."""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from sqlalchemy import text


def list_all_questions():
    """List all questions in the database with details."""
    db = SessionLocal()
    
    try:
        # Get all questions
        result = db.execute(text("""
            SELECT id, concept_name, difficulty_tag, logic_description, 
                   time_limit, memory_limit, question_type, section, 
                   points, options, correct_answer
            FROM questions
            ORDER BY section, id
        """))
        
        question_rows = result.fetchall()
        
        if not question_rows:
            print("No questions found in the database.")
            return
        
        print("=" * 80)
        print(f"Total Questions: {len(question_rows)}")
        print("=" * 80)
        print()
        
        # Group by section
        sections = {"A": [], "B": [], "C": []}
        
        for row in question_rows:
            q_id, concept, difficulty, description, time_limit, memory_limit, \
            q_type, section, points, options, correct_answer = row
            
            q_data = {
                "id": q_id,
                "concept": concept,
                "difficulty": difficulty,
                "description": description,
                "time_limit": time_limit,
                "memory_limit": memory_limit,
                "type": q_type,
                "section": section,
                "points": points,
                "options": options,
                "correct_answer": correct_answer
            }
            
            if section:
                sections[section].append(q_data)
        
        # Section A - MCQ
        if sections["A"]:
            print("=" * 80)
            print("SECTION A: Multiple Choice Questions (MCQ)")
            print("=" * 80)
            for i, q in enumerate(sections["A"], 1):
                print(f"\n[{i}] Question ID: {q['id']}")
                print(f"    Concept: {q['concept']}")
                print(f"    Difficulty: {q['difficulty']}")
                print(f"    Points: {q['points']}")
                desc = q['description'][:100] if q['description'] else "N/A"
                print(f"    Description: {desc}...")
                if q['options']:
                    if isinstance(q['options'], str):
                        options_dict = json.loads(q['options'])
                    else:
                        options_dict = q['options']
                    print(f"    Options: {list(options_dict.keys()) if options_dict else 'N/A'}")
                print(f"    Correct Answer: {q['correct_answer']}")
        
        # Section B - Logic & Trace
        if sections["B"]:
            print("\n" + "=" * 80)
            print("SECTION B: Logic & Trace Questions")
            print("=" * 80)
            for i, q in enumerate(sections["B"], 1):
                print(f"\n[{i}] Question ID: {q['id']}")
                print(f"    Concept: {q['concept']}")
                print(f"    Difficulty: {q['difficulty']}")
                print(f"    Points: {q['points']}")
                desc = q['description'][:100] if q['description'] else "N/A"
                print(f"    Description: {desc}...")
                print(f"    Correct Answer: {q['correct_answer']}")
        
        # Section C - Coding
        if sections["C"]:
            print("\n" + "=" * 80)
            print("SECTION C: Coding Problems")
            print("=" * 80)
            for i, q in enumerate(sections["C"], 1):
                print(f"\n[{i}] Question ID: {q['id']}")
                print(f"    Concept: {q['concept']}")
                print(f"    Difficulty: {q['difficulty']}")
                print(f"    Points: {q['points']}")
                print(f"    Time Limit: {q['time_limit']}s")
                print(f"    Memory Limit: {q['memory_limit']}MB")
                desc = q['description'][:100] if q['description'] else "N/A"
                print(f"    Description: {desc}...")
                
                # Get templates for this question
                template_result = db.execute(text("""
                    SELECT language, problem_statement, starter_code
                    FROM question_templates
                    WHERE question_id = :q_id
                """), {"q_id": q['id']})
                
                templates = template_result.fetchall()
                if templates:
                    print(f"    Templates ({len(templates)} languages):")
                    for lang, problem, starter in templates:
                        problem_preview = problem[:80] + "..." if problem and len(problem) > 80 else (problem or "N/A")
                        print(f"      - {lang}: {problem_preview}")
                
                # Get test cases
                test_result = db.execute(text("""
                    SELECT input_data, expected_output, is_hidden
                    FROM test_cases
                    WHERE question_id = :q_id
                    ORDER BY is_hidden, id
                """), {"q_id": q['id']})
                
                test_cases = test_result.fetchall()
                visible = [tc for tc in test_cases if not tc[2]]
                hidden = [tc for tc in test_cases if tc[2]]
                
                if test_cases:
                    print(f"    Test Cases: {len(visible)} visible, {len(hidden)} hidden")
                    for j, (input_data, expected, _) in enumerate(visible[:3], 1):  # Show first 3 visible
                        input_preview = input_data[:50] + "..." if input_data and len(input_data) > 50 else (input_data or "N/A")
                        expected_preview = expected[:50] + "..." if expected and len(expected) > 50 else (expected or "N/A")
                        print(f"      Visible {j}: Input='{input_preview}', Expected='{expected_preview}'")
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Section A (MCQ): {len(sections['A'])} questions")
        print(f"Section B (Logic & Trace): {len(sections['B'])} questions")
        print(f"Section C (Coding): {len(sections['C'])} questions")
        print(f"Total: {len(question_rows)} questions")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    list_all_questions()
