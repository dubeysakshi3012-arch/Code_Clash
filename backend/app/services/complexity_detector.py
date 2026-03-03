"""Behavior-based complexity detection service.

Detects algorithm complexity by analyzing execution time growth patterns
with progressively larger inputs (stress testing).
"""

from typing import Dict, Any, List, Optional
from app.services.docker_runner import docker_runner
from app.db.models.question import ProgrammingLanguage


class ComplexityDetector:
    """Detects algorithm complexity through behavior-based stress testing."""
    
    # Expected complexity for problems
    PROBLEM_COMPLEXITY = {
        "max_consecutive_ones": "O(N)",
        "smallest_subarray_sum": "O(N)"
    }
    
    # Time thresholds (in seconds) for different input sizes
    # These are normalized by language
    TIME_THRESHOLDS = {
        "O(N)": {
            100: 0.01,      # Should complete in 0.01s for N=100
            1000: 0.1,      # Should complete in 0.1s for N=1000
            10000: 1.0,     # Should complete in 1s for N=10000
            100000: 10.0    # Should complete in 10s for N=100000
        },
        "O(N²)": {
            100: 0.1,       # O(N²) might take longer
            1000: 10.0,     # O(N²) will be much slower
            10000: 1000.0   # O(N²) will timeout or be very slow
        }
    }
    
    # Language normalization factors (for time comparison)
    LANGUAGE_NORMALIZATION = {
        "python": 1.0,
        "java": 0.8,  # Account for compilation overhead
        "cpp": 0.5    # Faster execution
    }
    
    def detect_complexity(
        self,
        code: str,
        language: ProgrammingLanguage,
        problem_type: str,
        base_test_cases: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Detect algorithm complexity through stress testing.
        
        Args:
            code: User's code
            language: Programming language
            problem_type: Problem identifier (e.g., "max_consecutive_ones")
            base_test_cases: Base test cases to understand input format
            
        Returns:
            Dictionary with:
            - complexity: Detected complexity ("O(N)", "O(N²)", "unknown")
            - efficient: Whether the algorithm meets expected complexity
            - stress_test_results: List of test results for different input sizes
        """
        expected_complexity = self.PROBLEM_COMPLEXITY.get(problem_type, "O(N)")
        lang_str = language.value if hasattr(language, 'value') else str(language)
        
        # Generate stress test cases with progressively larger inputs
        stress_test_cases = self._generate_stress_test_cases(
            problem_type,
            base_test_cases,
            [100, 1000, 10000]  # Skip 100000 for speed, use 10000 as max
        )
        
        if not stress_test_cases:
            return {
                "complexity": "unknown",
                "efficient": True,  # Assume efficient if we can't test
                "stress_test_results": []
            }
        
        # Run stress tests
        stress_results = []
        execution_times = []
        
        for size, test_cases in stress_test_cases.items():
            try:
                # Run code with stress test cases
                result = docker_runner.run_code(
                    code=code,
                    language=lang_str,
                    test_cases=test_cases,
                    time_limit=30,  # Generous time limit for stress tests
                    memory_limit=256
                )
                
                execution_time = result.get("execution_time", 0.0)
                normalized_time = execution_time * self.LANGUAGE_NORMALIZATION.get(lang_str, 1.0)
                execution_times.append((size, normalized_time))
                
                # Check if it passed all test cases
                passed = result.get("passed", False)
                error = result.get("error")
                
                stress_results.append({
                    "input_size": size,
                    "execution_time": execution_time,
                    "normalized_time": normalized_time,
                    "passed": passed,
                    "error": error
                })
                
                # If timeout or error, likely inefficient
                if error and "timeout" in error.lower():
                    break
                    
            except Exception as e:
                stress_results.append({
                    "input_size": size,
                    "execution_time": 0.0,
                    "normalized_time": 0.0,
                    "passed": False,
                    "error": str(e)
                })
                break
        
        # Analyze time growth pattern
        complexity, efficient = self._analyze_complexity(
            execution_times,
            expected_complexity,
            lang_str
        )
        
        return {
            "complexity": complexity,
            "efficient": efficient,
            "stress_test_results": stress_results,
            "expected_complexity": expected_complexity
        }
    
    def _generate_stress_test_cases(
        self,
        problem_type: str,
        base_test_cases: List[Dict[str, str]],
        sizes: List[int]
    ) -> Dict[int, List[Dict[str, str]]]:
        """
        Generate stress test cases with progressively larger inputs.
        
        Args:
            problem_type: Problem identifier
            base_test_cases: Base test cases to understand format
            sizes: List of input sizes to test
            
        Returns:
            Dictionary mapping size to list of test cases
        """
        stress_cases = {}
        
        if not base_test_cases:
            return stress_cases
        
        # Understand input format from base test case
        sample_input = base_test_cases[0].get("input", "")
        sample_output = base_test_cases[0].get("expected_output", "")
        
        for size in sizes:
            test_cases = []
            
            if problem_type == "max_consecutive_ones":
                # Generate binary array of given size
                # Mix of patterns: all ones, all zeros, alternating, etc.
                test_cases.append({
                    "input": " ".join(["1"] * size),  # All ones
                    "expected_output": str(size)
                })
                test_cases.append({
                    "input": " ".join(["0"] * size),  # All zeros
                    "expected_output": "0"
                })
                # Alternating pattern
                alt_input = " ".join(["1" if i % 2 == 0 else "0" for i in range(size)])
                test_cases.append({
                    "input": alt_input,
                    "expected_output": "1"  # Max consecutive is 1
                })
                
            elif problem_type == "smallest_subarray_sum":
                # Generate array with sum pattern
                # First test: array where sum of all elements equals K
                k = size // 2
                arr = [1] * size
                test_cases.append({
                    "input": f"{k} {' '.join(map(str, arr))}",
                    "expected_output": str(min(size, k))  # Approximate
                })
                # Second test: array where we need all elements
                k2 = sum(arr)
                test_cases.append({
                    "input": f"{k2} {' '.join(map(str, arr))}",
                    "expected_output": str(size)
                })
            
            if test_cases:
                stress_cases[size] = test_cases
        
        return stress_cases
    
    def _analyze_complexity(
        self,
        execution_times: List[tuple],
        expected_complexity: str,
        language: str
    ) -> tuple:
        """
        Analyze execution time growth to determine complexity.
        
        Args:
            execution_times: List of (size, time) tuples
            expected_complexity: Expected complexity ("O(N)", "O(N²)")
            language: Programming language
            
        Returns:
            Tuple of (detected_complexity, is_efficient)
        """
        if len(execution_times) < 2:
            return "unknown", True
        
        # Sort by size
        execution_times.sort(key=lambda x: x[0])
        
        # Calculate time growth ratios
        ratios = []
        for i in range(1, len(execution_times)):
            prev_size, prev_time = execution_times[i-1]
            curr_size, curr_time = execution_times[i]
            
            if prev_time == 0:
                continue
            
            size_ratio = curr_size / prev_size
            time_ratio = curr_time / prev_time
            
            ratios.append((size_ratio, time_ratio))
        
        if not ratios:
            return "unknown", True
        
        # Analyze growth pattern
        # For O(N): time should grow roughly linearly with size
        # For O(N²): time should grow quadratically (time_ratio ~ size_ratio²)
        
        avg_time_ratio = sum(r[1] for r in ratios) / len(ratios)
        avg_size_ratio = sum(r[0] for r in ratios) / len(ratios)
        
        # Check thresholds
        threshold = self.TIME_THRESHOLDS.get(expected_complexity, {})
        max_time = max(t[1] for _, t in execution_times) if execution_times else 0
        
        # Check if times exceed thresholds
        efficient = True
        for size, time in execution_times:
            threshold_time = threshold.get(size, float('inf'))
            if time > threshold_time * 2:  # Allow 2x margin
                efficient = False
                break
        
        # Determine complexity based on growth
        if avg_time_ratio > avg_size_ratio * 1.5:
            # Time growing faster than size - likely O(N²) or worse
            detected = "O(N²)"
            if expected_complexity == "O(N)":
                efficient = False
        elif avg_time_ratio <= avg_size_ratio * 1.2:
            # Time growing roughly linearly - likely O(N)
            detected = "O(N)"
            if expected_complexity == "O(N)":
                efficient = True
            else:
                efficient = False
        else:
            detected = "O(N)"  # Default assumption
            efficient = True
        
        return detected, efficient


# Global instance
complexity_detector = ComplexityDetector()
