"""Verdict generation service for code submissions.

Generates human-readable verdicts based on execution results,
complexity analysis, and resource usage.
"""

from typing import Dict, Any, Optional
from enum import Enum


class VerdictType(str, Enum):
    """Verdict types for code submissions."""
    ACCEPTED = "ACCEPTED"
    CORRECT_BUT_SLOW = "CORRECT_BUT_SLOW"
    WRONG_ANSWER = "WRONG_ANSWER"
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    COMPILATION_ERROR = "COMPILATION_ERROR"
    MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED"


class VerdictGenerator:
    """Generates verdicts for code submissions."""
    
    def generate_verdict(
        self,
        execution_result: Dict[str, Any],
        complexity_result: Optional[Dict[str, Any]] = None,
        time_limit: int = 30,
        memory_limit: int = 256
    ) -> Dict[str, Any]:
        """
        Generate verdict based on execution and complexity results.
        
        Args:
            execution_result: Result from Docker runner
            complexity_result: Result from complexity detector (optional)
            time_limit: Time limit in seconds
            memory_limit: Memory limit in MB
            
        Returns:
            Dictionary with:
            - verdict: VerdictType enum value
            - message: Human-readable message
            - details: Additional details
        """
        # Check for compilation errors first
        error = execution_result.get("error", "")
        if error:
            if "compilation" in error.lower() or "compile" in error.lower():
                return {
                    "verdict": VerdictType.COMPILATION_ERROR.value,
                    "message": "Compilation Error",
                    "details": f"Your code failed to compile: {error[:200]}"
                }
        
        # Check for runtime errors
        results = execution_result.get("results", [])
        has_runtime_error = any(
            r.get("error") for r in results
        ) or (error and "runtime" in error.lower())
        
        if has_runtime_error:
            error_msg = error or next((r.get("error") for r in results if r.get("error")), "Unknown error")
            return {
                "verdict": VerdictType.RUNTIME_ERROR.value,
                "message": "Runtime Error",
                "details": f"Your code encountered a runtime error: {error_msg[:200]}"
            }
        
        # Check for time limit exceeded
        execution_time = execution_result.get("execution_time", 0.0)
        if execution_time >= time_limit * 0.95:  # 95% of time limit
            return {
                "verdict": VerdictType.TIME_LIMIT_EXCEEDED.value,
                "message": "Time Limit Exceeded",
                "details": f"Your code exceeded the time limit of {time_limit}s"
            }
        
        # Check for memory limit exceeded
        memory_used = execution_result.get("memory_used", 0)
        if memory_used >= memory_limit * 0.95:  # 95% of memory limit
            return {
                "verdict": VerdictType.MEMORY_LIMIT_EXCEEDED.value,
                "message": "Memory Limit Exceeded",
                "details": f"Your code exceeded the memory limit of {memory_limit}MB"
            }
        
        # Check if all test cases passed
        passed_count = sum(1 for r in results if r.get("passed", False))
        total_count = len(results)
        
        if passed_count < total_count:
            failed_tests = total_count - passed_count
            return {
                "verdict": VerdictType.WRONG_ANSWER.value,
                "message": "Wrong Answer",
                "details": f"Failed {failed_tests} out of {total_count} test cases"
            }
        
        # All test cases passed - check complexity
        if complexity_result:
            efficient = complexity_result.get("efficient", True)
            detected_complexity = complexity_result.get("complexity", "unknown")
            expected_complexity = complexity_result.get("expected_complexity", "O(N)")
            
            if not efficient and detected_complexity != expected_complexity:
                return {
                    "verdict": VerdictType.CORRECT_BUT_SLOW.value,
                    "message": "Correct but Slow",
                    "details": f"Your solution is correct but uses {detected_complexity} algorithm. Expected {expected_complexity}."
                }
        
        # All checks passed - accepted
        return {
            "verdict": VerdictType.ACCEPTED.value,
            "message": "Accepted",
            "details": f"All {total_count} test cases passed successfully"
        }


# Global instance
verdict_generator = VerdictGenerator()
