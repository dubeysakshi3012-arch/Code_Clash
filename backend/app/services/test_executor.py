"""Test case execution orchestration service.

Handles execution of visible and hidden test cases,
batch processing, and result aggregation.
"""

from typing import Dict, Any, List, Optional
from app.services.docker_runner import docker_runner
from app.db.models.question import ProgrammingLanguage, TestCase


class TestExecutor:
    """Orchestrates test case execution."""
    
    def execute_test_cases(
        self,
        code: str,
        language: ProgrammingLanguage,
        test_cases: List[TestCase],
        time_limit: int = 30,
        memory_limit: int = 256
    ) -> Dict[str, Any]:
        """
        Execute code against test cases.
        
        Args:
            code: User's code
            language: Programming language
            test_cases: List of TestCase objects
            time_limit: Time limit in seconds
            memory_limit: Memory limit in MB
            
        Returns:
            Dictionary with execution results
        """
        # Convert TestCase objects to dict format
        test_cases_dict = [
            {
                "input": tc.input_data,
                "expected_output": tc.expected_output
            }
            for tc in test_cases
        ]
        
        lang_str = language.value if hasattr(language, 'value') else str(language)
        
        # Execute using Docker runner
        result = docker_runner.run_code(
            code=code,
            language=lang_str,
            test_cases=test_cases_dict,
            time_limit=time_limit,
            memory_limit=memory_limit
        )
        
        # Enhance result with test case metadata
        enhanced_results = []
        for i, tc in enumerate(test_cases):
            if i < len(result.get("results", [])):
                tc_result = result["results"][i]
                enhanced_results.append({
                    **tc_result,
                    "test_case_id": tc.id,
                    "is_hidden": tc.is_hidden,
                    "order": tc.order
                })
            else:
                # Missing result for this test case
                enhanced_results.append({
                    "passed": False,
                    "input": tc.input_data,
                    "expected_output": tc.expected_output,
                    "actual_output": "",
                    "error": "Test case not executed",
                    "test_case_id": tc.id,
                    "is_hidden": tc.is_hidden,
                    "order": tc.order
                })
        
        return {
            **result,
            "results": enhanced_results
        }
    
    def execute_visible_test_cases(
        self,
        code: str,
        language: ProgrammingLanguage,
        test_cases: List[TestCase],
        time_limit: int = 30,
        memory_limit: int = 256
    ) -> Dict[str, Any]:
        """
        Execute code against visible test cases only.
        
        Args:
            code: User's code
            language: Programming language
            test_cases: List of TestCase objects (will filter for visible)
            time_limit: Time limit in seconds
            memory_limit: Memory limit in MB
            
        Returns:
            Dictionary with execution results
        """
        visible_cases = [tc for tc in test_cases if not tc.is_hidden]
        return self.execute_test_cases(
            code=code,
            language=language,
            test_cases=visible_cases,
            time_limit=time_limit,
            memory_limit=memory_limit
        )
    
    def execute_all_test_cases(
        self,
        code: str,
        language: ProgrammingLanguage,
        visible_cases: List[TestCase],
        hidden_cases: List[TestCase],
        time_limit: int = 30,
        memory_limit: int = 256
    ) -> Dict[str, Any]:
        """
        Execute code against both visible and hidden test cases.
        
        Args:
            code: User's code
            language: Programming language
            visible_cases: Visible test cases
            hidden_cases: Hidden test cases
            time_limit: Time limit in seconds
            memory_limit: Memory limit in MB
            
        Returns:
            Dictionary with execution results for all test cases
        """
        all_cases = visible_cases + hidden_cases
        return self.execute_test_cases(
            code=code,
            language=language,
            test_cases=all_cases,
            time_limit=time_limit,
            memory_limit=memory_limit
        )


# Global instance
test_executor = TestExecutor()
