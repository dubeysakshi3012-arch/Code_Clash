"""Quick script to check question count by section."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from sqlalchemy import text


def quick_check():
    """Quick check of questions in database."""
    db = SessionLocal()
    
    try:
        # Count by section
        result = db.execute(text("""
            SELECT section, question_type, COUNT(*) as count
            FROM questions
            GROUP BY section, question_type
            ORDER BY section, question_type
        """))
        
        rows = result.fetchall()
        
        print("Questions by Section and Type:")
        print("-" * 50)
        for section, q_type, count in rows:
            print(f"Section {section} ({q_type}): {count} questions")
        
        # Total count
        total_result = db.execute(text("SELECT COUNT(*) FROM questions"))
        total = total_result.scalar()
        print("-" * 50)
        print(f"Total: {total} questions")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    quick_check()
