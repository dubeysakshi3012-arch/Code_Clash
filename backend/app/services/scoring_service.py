"""Scoring service for assessment evaluation.

Implements multi-factor scoring system:
- MCQ: (correct/total) * 25
- Logic: (correct/total) * 25
- Coding: Multi-factor scoring (correctness, time, algorithm, attempts, structure)
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.db.models import AssessmentResult, Question, QuestionType, AssessmentSection


# Language runtime normalization factors
RUNTIME_NORMALIZATION = {
    "python": 1.0,   # Baseline
    "java": 1.2,     # Compilation overhead
    "cpp": 0.8       # Faster execution
}


def calculate_mcq_score(results: List[AssessmentResult]) -> float:
    """
    Calculate MCQ section score (Section A).
    
    Formula: (correct / total) * 25
    
    Args:
        results: List of assessment results for MCQ questions
        
    Returns:
        Score out of 25
    """
    if not results:
        return 0.0
    
    total = len(results)
    correct = sum(1 for r in results if r.is_correct is True)
    
    return (correct / total) * 25.0


def calculate_logic_score(results: List[AssessmentResult]) -> float:
    """
    Calculate Logic & Trace section score (Section B).
    
    Formula: (correct / total) * 25
    
    Args:
        results: List of assessment results for logic questions
        
    Returns:
        Score out of 25
    """
    if not results:
        return 0.0
    
    total = len(results)
    correct = sum(1 for r in results if r.is_correct is True)
    
    return (correct / total) * 25.0


def normalize_runtime(runtime: float, language: str) -> float:
    """
    Normalize runtime based on language.
    
    Args:
        runtime: Actual runtime in seconds
        language: Programming language
        
    Returns:
        Normalized runtime
    """
    factor = RUNTIME_NORMALIZATION.get(language.lower(), 1.0)
    return runtime * factor


def calculate_coding_score(
    results: List[AssessmentResult],
    language: str,
    total_test_cases: int
) -> float:
    """
    Calculate coding section score (Section C) with multi-factor scoring.
    
    Scoring breakdown:
    - Correctness: 40% (all test cases pass)
    - Time efficiency: 15% (normalized runtime)
    - Algorithm efficiency: 15% (based on time complexity)
    - Attempts/errors: 15% (fewer attempts = better)
    - Code structure: 15% (basic quality check)
    
    Args:
        results: List of assessment results for coding problems
        language: Programming language used
        total_test_cases: Total number of test cases across all problems
        
    Returns:
        Score out of 50
    """
    if not results:
        return 0.0
    
    total_score = 0.0
    
    for result in results:
        if not result.execution_result:
            continue
        
        execution = result.execution_result
        test_results = execution.get("results", [])
        
        # Correctness (40%)
        passed_tests = sum(1 for tr in test_results if tr.get("passed", False))
        total_tests = len(test_results)
        correctness_score = (passed_tests / total_tests) * 40.0 if total_tests > 0 else 0.0
        
        # Time efficiency (15%)
        execution_time = execution.get("execution_time", 0.0)
        normalized_time = normalize_runtime(execution_time, language)
        # Score based on how close to optimal time
        # For problems with time_limit, score decreases if approaching limit
        # Optimal: < 10% of time limit, Good: < 50%, Acceptable: < 80%
        time_limit = 30  # Default, could be from question
        if normalized_time < time_limit * 0.1:
            time_score = 15.0
        elif normalized_time < time_limit * 0.5:
            time_score = 12.0
        elif normalized_time < time_limit * 0.8:
            time_score = 8.0
        else:
            time_score = max(0, 15.0 * (1.0 - (normalized_time / time_limit)))
        
        # Algorithm efficiency (15%) - Use complexity detection results
        complexity = execution.get("complexity", "unknown")
        efficient = execution.get("efficient", True)
        verdict = execution.get("verdict", "")
        
        if verdict == "CORRECT_BUT_SLOW":
            # Correct but inefficient algorithm
            algo_score = 7.5  # Half points
        elif not efficient:
            # Inefficient algorithm detected
            algo_score = 5.0  # Low score
        elif complexity == "unknown":
            # Can't determine complexity, assume efficient if all tests pass
            algo_score = 15.0 if correctness_score >= 35.0 else 7.5
        else:
            # Efficient algorithm
            algo_score = 15.0
        
        # Attempts/errors (15%)
        attempts = result.attempts_count
        # Fewer attempts = better
        # 1 attempt: 15 points, 2 attempts: 12 points, 3 attempts: 9 points, 4+: 6 points
        if attempts == 1:
            attempts_score = 15.0
        elif attempts == 2:
            attempts_score = 12.0
        elif attempts == 3:
            attempts_score = 9.0
        else:
            attempts_score = max(0, 15.0 - (attempts - 1) * 2.0)
        
        # Code structure (15%)
        # Check for compilation errors, runtime errors, code quality
        error = execution.get("error")
        verdict_type = execution.get("verdict", "")
        
        if verdict_type == "COMPILATION_ERROR":
            structure_score = 0.0
        elif error and "runtime" in error.lower():
            structure_score = 5.0
        elif error:
            structure_score = 10.0
        else:
            # No errors - check code length and complexity (basic heuristic)
            # This is a placeholder - could be enhanced with AST analysis
            code_length = len(result.answer_data or "")
            if 50 <= code_length <= 500:  # Reasonable length
                structure_score = 15.0
            elif code_length < 50:  # Too short, might be incomplete
                structure_score = 10.0
            else:  # Too long, might be inefficient
                structure_score = 12.0
        
        problem_score = (
            correctness_score +
            time_score +
            algo_score +
            attempts_score +
            structure_score
        )
        
        total_score += problem_score
    
    # Cap at 50 points total
    return min(total_score, 50.0)


def calculate_total_score(
    mcq_results: List[AssessmentResult],
    logic_results: List[AssessmentResult],
    coding_results: List[AssessmentResult],
    language: str,
    total_coding_test_cases: int
) -> Dict[str, Any]:
    """
    Calculate total assessment score across all sections.
    
    Args:
        mcq_results: Section A results
        logic_results: Section B results
        coding_results: Section C results
        language: Programming language used
        total_coding_test_cases: Total test cases for coding problems
        
    Returns:
        Dictionary with section scores and total score
    """
    section_a_score = calculate_mcq_score(mcq_results)
    section_b_score = calculate_logic_score(logic_results)
    section_c_score = calculate_coding_score(
        coding_results,
        language,
        total_coding_test_cases
    )
    
    total_score = section_a_score + section_b_score + section_c_score
    
    return {
        "section_a_score": round(section_a_score, 2),
        "section_b_score": round(section_b_score, 2),
        "section_c_score": round(section_c_score, 2),
        "total_score": round(total_score, 2),
        "max_score": 100.0
    }


def get_section_results(
    db: Session,
    assessment_id: int,
    section: AssessmentSection
) -> List[AssessmentResult]:
    """
    Get assessment results for a specific section.
    
    Args:
        db: Database session
        assessment_id: Assessment ID
        section: Section (A, B, or C)
        
    Returns:
        List of assessment results for the section
    """
    return db.query(AssessmentResult).filter(
        AssessmentResult.assessment_id == assessment_id,
        AssessmentResult.section == section
    ).all()
