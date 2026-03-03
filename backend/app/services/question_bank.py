"""Fixed question bank for CodeClash assessment module.

Contains all 13 questions:
- Section A: 8 MCQ questions (25% weight)
- Section B: 3 Logic & Trace questions (25% weight)
- Section C: 2 Coding problems (50% weight)
"""

from typing import Dict, List, Any
from app.db.models.question import QuestionType, AssessmentSection, DifficultyTag


# Section A: MCQ Questions (8 questions)
MCQ_QUESTIONS: List[Dict[str, Any]] = [
    {
        "concept_name": "Time Complexity - Binary Search",
        "difficulty_tag": DifficultyTag.EASY,
        "question_type": QuestionType.MCQ,
        "section": AssessmentSection.A,
        "logic_description": "What is the time complexity of binary search on a sorted array?",
        "points": 3.125,  # 25/8 points per question
        "options": {
            "A": "O(n)",
            "B": "O(log n)",
            "C": "O(n log n)",
            "D": "O(1)"
        },
        "correct_answer": "B",
        "time_limit": 60,
        "memory_limit": 64
    },
    {
        "concept_name": "Data Structures - Balanced Parentheses",
        "difficulty_tag": DifficultyTag.EASY,
        "question_type": QuestionType.MCQ,
        "section": AssessmentSection.A,
        "logic_description": "Which data structure is best for checking balanced parentheses?",
        "points": 3.125,
        "options": {
            "A": "Queue",
            "B": "Stack",
            "C": "Tree",
            "D": "Array"
        },
        "correct_answer": "B",
        "time_limit": 60,
        "memory_limit": 64
    },
    {
        "concept_name": "Hashing - Hash Collision",
        "difficulty_tag": DifficultyTag.EASY,
        "question_type": QuestionType.MCQ,
        "section": AssessmentSection.A,
        "logic_description": "What is a hash collision?",
        "points": 3.125,
        "options": {
            "A": "Hash table is full",
            "B": "Two keys map to the same index",
            "C": "Hashing fails",
            "D": "Key not found"
        },
        "correct_answer": "B",
        "time_limit": 60,
        "memory_limit": 64
    },
    {
        "concept_name": "Time Complexity - Nested Loops",
        "difficulty_tag": DifficultyTag.MEDIUM,
        "question_type": QuestionType.MCQ,
        "section": AssessmentSection.A,
        "logic_description": "What is the time complexity of:\nfor i = 1 to n:\n  for j = 1 to i:\n    print(i, j)",
        "points": 3.125,
        "options": {
            "A": "O(n)",
            "B": "O(n²)",
            "C": "O(n log n)",
            "D": "O(2ⁿ)"
        },
        "correct_answer": "B",
        "time_limit": 60,
        "memory_limit": 64
    },
    {
        "concept_name": "Algorithms - Sliding Window",
        "difficulty_tag": DifficultyTag.MEDIUM,
        "question_type": QuestionType.MCQ,
        "section": AssessmentSection.A,
        "logic_description": "What is the best technique for solving contiguous subarray problems?",
        "points": 3.125,
        "options": {
            "A": "Brute Force",
            "B": "Sliding Window",
            "C": "Dynamic Programming",
            "D": "Greedy Algorithm"
        },
        "correct_answer": "B",
        "time_limit": 60,
        "memory_limit": 64
    },
    {
        "concept_name": "Space Complexity - Two Pointers",
        "difficulty_tag": DifficultyTag.EASY,
        "question_type": QuestionType.MCQ,
        "section": AssessmentSection.A,
        "logic_description": "Which technique uses constant extra space for array traversal?",
        "points": 3.125,
        "options": {
            "A": "Hash Set",
            "B": "Two-pointer technique",
            "C": "Sorting",
            "D": "Nested loops"
        },
        "correct_answer": "B",
        "time_limit": 60,
        "memory_limit": 64
    },
    {
        "concept_name": "Amortized Analysis - Dynamic Arrays",
        "difficulty_tag": DifficultyTag.MEDIUM,
        "question_type": QuestionType.MCQ,
        "section": AssessmentSection.A,
        "logic_description": "What is the amortized time complexity of append operation in a dynamic array?",
        "points": 3.125,
        "options": {
            "A": "O(n)",
            "B": "O(log n)",
            "C": "O(1) amortized",
            "D": "O(n²)"
        },
        "correct_answer": "C",
        "time_limit": 60,
        "memory_limit": 64
    },
    {
        "concept_name": "Sorting - Stable Algorithms",
        "difficulty_tag": DifficultyTag.EASY,
        "question_type": QuestionType.MCQ,
        "section": AssessmentSection.A,
        "logic_description": "Which sorting algorithm is stable?",
        "points": 3.125,
        "options": {
            "A": "Quick Sort",
            "B": "Heap Sort",
            "C": "Merge Sort",
            "D": "Selection Sort"
        },
        "correct_answer": "C",
        "time_limit": 60,
        "memory_limit": 64
    }
]

# Section B: Logic & Trace Questions (3 questions)
LOGIC_QUESTIONS: List[Dict[str, Any]] = [
    {
        "concept_name": "Loop Output Calculation",
        "difficulty_tag": DifficultyTag.EASY,
        "question_type": QuestionType.LOGIC_TRACE,
        "section": AssessmentSection.B,
        "logic_description": "What is the output of:\nx = 0\nfor i = 1 to 5:\n  if i % 2 == 0:\n    x += i\nprint(x)",
        "points": 8.33,  # 25/3 points per question
        "correct_answer": "6",
        "time_limit": 120,
        "memory_limit": 64
    },
    {
        "concept_name": "Nested Loop Count",
        "difficulty_tag": DifficultyTag.MEDIUM,
        "question_type": QuestionType.LOGIC_TRACE,
        "section": AssessmentSection.B,
        "logic_description": "How many times does the inner loop execute?\nfor i = 1 to n:\n  for j = i to n:\n    print('*')\nExpress answer as a formula.",
        "points": 8.33,
        "correct_answer": "n(n+1)/2",
        "time_limit": 120,
        "memory_limit": 64
    },
    {
        "concept_name": "Space Complexity Analysis",
        "difficulty_tag": DifficultyTag.MEDIUM,
        "question_type": QuestionType.LOGIC_TRACE,
        "section": AssessmentSection.B,
        "logic_description": "What is the extra space complexity when removing duplicates from an unsorted array using a set?",
        "points": 8.33,
        "correct_answer": "O(n)",
        "time_limit": 120,
        "memory_limit": 64
    }
]

# Section C: Coding Problems (2 problems)
CODING_PROBLEMS: List[Dict[str, Any]] = [
    {
        "concept_name": "Maximum Consecutive Ones",
        "difficulty_tag": DifficultyTag.EASY,
        "question_type": QuestionType.CODING,
        "section": AssessmentSection.C,
        "logic_description": "Given a binary array, find the maximum number of consecutive 1s.\n\nExample:\nInput: [1, 1, 0, 1, 1, 1]\nOutput: 3",
        "points": 25.0,  # Mandatory problem - 25 points
        "time_limit": 300,  # 5 minutes
        "memory_limit": 256,
        "is_mandatory": True,
        "test_cases": [
            # Visible
            {"input": "1 1 0 1 1 1", "expected_output": "3", "is_hidden": False},
            {"input": "1 1 1 1 1", "expected_output": "5", "is_hidden": False},
            {"input": "0 0 0 0", "expected_output": "0", "is_hidden": False},
            # Hidden: single element, edge cases, stress
            {"input": "1", "expected_output": "1", "is_hidden": True},
            {"input": "0", "expected_output": "0", "is_hidden": True},
            {"input": " ".join(["1"] * 1000), "expected_output": "1000", "is_hidden": True},
        ],
    },
    {
        "concept_name": "Smallest Subarray with Sum >= K",
        "difficulty_tag": DifficultyTag.MEDIUM,
        "question_type": QuestionType.CODING,
        "section": AssessmentSection.C,
        "logic_description": "Given an array of positive integers and integer K, return the length of the smallest contiguous subarray with sum >= K. If no such subarray exists, return 0.\n\nExample:\nInput: nums = [2, 1, 5, 2, 3, 2], K = 7\nOutput: 2\nExplanation: The smallest subarray with sum >= 7 is [5, 2].",
        "points": 25.0,  # Optional problem - 25 points
        "time_limit": 600,  # 10 minutes
        "memory_limit": 256,
        "is_mandatory": False,
        "test_cases": [
            # Visible
            {"input": "7 2 3 1 2 4 3", "expected_output": "2", "is_hidden": False},
            {"input": "4 1 4 4", "expected_output": "1", "is_hidden": False},
            {"input": "11 1 1 1 1 1 1 1", "expected_output": "0", "is_hidden": False},
            # Hidden: single element >= K, edge, stress
            {"input": "5 5", "expected_output": "1", "is_hidden": True},
            {"input": "10 1 2 3 4", "expected_output": "4", "is_hidden": True},
            {"input": "100 " + " ".join(["1"] * 100), "expected_output": "100", "is_hidden": True},
        ],
    },
]


def get_all_assessment_questions() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all assessment questions organized by section.
    
    Returns:
        Dictionary with keys: 'mcq', 'logic', 'coding'
    """
    return {
        "mcq": MCQ_QUESTIONS,
        "logic": LOGIC_QUESTIONS,
        "coding": CODING_PROBLEMS
    }


def get_mcq_questions() -> List[Dict[str, Any]]:
    """Get all MCQ questions for Section A."""
    return MCQ_QUESTIONS


def get_logic_questions() -> List[Dict[str, Any]]:
    """Get all Logic & Trace questions for Section B."""
    return LOGIC_QUESTIONS


def get_coding_problems() -> List[Dict[str, Any]]:
    """Get all coding problems for Section C."""
    return CODING_PROBLEMS
