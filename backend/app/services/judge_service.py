"""Code execution and judging service.

Implements Docker-based code execution for:
- Python code execution
- Java code execution
- C++ code execution
- Test case validation
- Time and memory limit enforcement
- Complexity detection
- Verdict generation
"""

from typing import Optional, Dict, Any, List
from app.db.models.question import ProgrammingLanguage, TestCase, Question
from app.core.config import settings
from app.services.docker_runner import docker_runner
from app.services.complexity_detector import complexity_detector
from app.services.verdict_generator import verdict_generator
from app.services.test_executor import test_executor


def _normalize_output(s: str) -> str:
    """Normalize string for comparison: newlines and trim. Handles None."""
    if s is None:
        return ""
    s = str(s).strip()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s


def _convert_test_cases(test_cases):
    """Convert TestCase objects to dict format for Docker runner. Coerce to strings, no None."""
    return [
        {
            "input": _normalize_output(getattr(tc, "input_data", None)),
            "expected_output": _normalize_output(getattr(tc, "expected_output", None)),
        }
        for tc in test_cases
    ]


def _concept_name_to_problem_type(concept_name: str) -> str:
    """Map question concept_name to complexity detector problem_type key."""
    mapping = {
        "maximum consecutive ones": "max_consecutive_ones",
        "smallest subarray with sum >= k": "smallest_subarray_sum",
    }
    normalized = concept_name.lower().strip()
    return mapping.get(normalized, normalized.replace(" ", "_"))


class JudgeService:
    """Base judge service interface."""
    
    def execute_code(
        self,
        code: str,
        language: ProgrammingLanguage,
        test_cases: list[TestCase],
        time_limit: int,
        memory_limit: int,
        solution_function_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute code and validate against test cases.

        Args:
            code: User's code submission
            language: Programming language
            test_cases: List of test cases to validate
            time_limit: Time limit in seconds
            memory_limit: Memory limit in MB
            solution_function_names: Optional list of function names to try when running code (from question template).

        Returns:
            Dictionary containing:
            - passed: bool
            - results: List of test case results
            - execution_time: float
            - memory_used: int
            - error: Optional[str]
        """
        return docker_runner.run_code(
            code=code,
            language=language.value if hasattr(language, 'value') else str(language),
            test_cases=_convert_test_cases(test_cases),
            time_limit=time_limit,
            memory_limit=memory_limit,
            solution_function_names=solution_function_names,
        )
    
    def run_custom_input(
        self,
        code: str,
        language: ProgrammingLanguage,
        custom_input: str,
        time_limit: int = 30,
        memory_limit: int = 256
    ) -> Dict[str, Any]:
        """
        Run code with custom user input (for "Run Code" button).
        
        Args:
            code: User's code
            language: Programming language
            custom_input: User-provided input
            time_limit: Time limit in seconds
            memory_limit: Memory limit in MB
            
        Returns:
            Dictionary with output, execution_time, memory_used, error
        """
        return docker_runner.run_custom_input(
            code=code,
            language=language.value if hasattr(language, 'value') else str(language),
            custom_input=custom_input,
            time_limit=time_limit,
            memory_limit=memory_limit
        )
    
    def evaluate_submission(
        self,
        code: str,
        language: ProgrammingLanguage,
        question: Question,
        all_test_cases: List[TestCase]
    ) -> Dict[str, Any]:
        """
        Full evaluation of code submission with visible and hidden test cases.
        
        Args:
            code: User's code submission
            language: Programming language
            question: Question object
            all_test_cases: All test cases (visible + hidden)
            
        Returns:
            Comprehensive evaluation results with verdict
        """
        # Execute all test cases
        execution_result = test_executor.execute_test_cases(
            code=code,
            language=language,
            test_cases=all_test_cases,
            time_limit=question.time_limit,
            memory_limit=question.memory_limit
        )
        
        # Detect complexity
        visible_cases = [tc for tc in all_test_cases if not tc.is_hidden]
        complexity_result = None
        if visible_cases:
            try:
                complexity_result = complexity_detector.detect_complexity(
                    code=code,
                    language=language,
                    problem_type=_concept_name_to_problem_type(question.concept_name),
                    base_test_cases=_convert_test_cases(visible_cases[:3])  # Use first 3 visible cases
                )
            except Exception as e:
                # If complexity detection fails, continue without it
                pass
        
        # Generate verdict
        verdict = verdict_generator.generate_verdict(
            execution_result=execution_result,
            complexity_result=complexity_result,
            time_limit=question.time_limit,
            memory_limit=question.memory_limit
        )
        
        return {
            **execution_result,
            "verdict": verdict["verdict"],
            "verdict_message": verdict["message"],
            "verdict_details": verdict["details"],
            "complexity": complexity_result.get("complexity", "unknown") if complexity_result else None,
            "efficient": complexity_result.get("efficient", True) if complexity_result else True,
            "complexity_result": complexity_result  # Include full complexity result for stress test data
        }
    
    def check_complexity(
        self,
        code: str,
        language: ProgrammingLanguage,
        question: Question,
        test_cases: List[TestCase]
    ) -> Dict[str, Any]:
        """
        Check algorithm complexity for a question.
        
        Args:
            code: User's code
            language: Programming language
            question: Question object
            test_cases: Test cases to use for complexity detection
            
        Returns:
            Complexity detection results
        """
        return complexity_detector.detect_complexity(
            code=code,
            language=language,
            problem_type=_concept_name_to_problem_type(question.concept_name),
            base_test_cases=_convert_test_cases(test_cases)
        )


class PythonJudge(JudgeService):
    """Python code execution judge."""
    pass  # Inherits all methods from JudgeService


class JavaJudge(JudgeService):
    """Java code execution judge."""
    pass  # Inherits all methods from JudgeService


class CppJudge(JudgeService):
    """C++ code execution judge."""
    pass  # Inherits all methods from JudgeService


def get_judge_service(language: ProgrammingLanguage) -> JudgeService:
    """
    Get appropriate judge service for language.
    
    Args:
        language: Programming language
        
    Returns:
        Judge service instance
    """
    # All judges use the same base implementation now
    return JudgeService()
