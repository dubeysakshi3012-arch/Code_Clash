"""Docker-based code execution runner with security constraints.

Provides isolated execution environment for user-submitted code.
"""

import sys
import docker
import json
import time
import os
import tempfile
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.core.config import settings

# Windows Docker Desktop uses a named pipe; Linux/Mac use Unix socket
DOCKER_NPIPE_WIN = "npipe:////./pipe/docker_engine"


def _strip_jvm_stderr(logs: str) -> str:
    """Remove JVM stderr lines (e.g. Picked up JAVA_TOOL_OPTIONS) so JSON can be parsed."""
    if not logs:
        return logs
    lines = logs.split("\n")
    kept = [
        line
        for line in lines
        if not line.strip().startswith("Picked up JAVA_TOOL_OPTIONS")
    ]
    return "\n".join(kept)


def _sanitize_error_for_client(error: Optional[str], max_len: int = 2000) -> Optional[str]:
    """Remove JVM noise from error message shown to the user."""
    if not error:
        return error
    text = _strip_jvm_stderr(error)
    if len(text) > max_len:
        text = text[:max_len] + "\n..."
    return text.strip() or error.strip()[:max_len]


def _normalize_runner_output(s: str) -> str:
    """Normalize output for comparison: newlines and trim. Safe for None."""
    if s is None:
        return ""
    s = str(s).strip().replace("\r\n", "\n").replace("\r", "\n")
    return s


def _normalize_test_cases_for_runner(test_cases: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Ensure every test case has string input and expected_output. No None."""
    return [
        {
            "input": _normalize_runner_output(tc.get("input")),
            "expected_output": _normalize_runner_output(tc.get("expected_output")),
        }
        for tc in test_cases
    ]


def _make_docker_client():
    """Create Docker client, trying from_env then configured URL then Windows npipe."""
    try:
        return docker.from_env()
    except Exception:
        pass
    try:
        return docker.DockerClient(base_url=settings.DOCKER_SOCKET_URL)
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            return docker.DockerClient(base_url=DOCKER_NPIPE_WIN)
        except Exception:
            pass
    return None


class DockerRunner:
    """Docker-based code execution runner."""
    
    def __init__(self):
        """Initialize Docker client."""
        self.client = _make_docker_client()
    
    def _create_files_command(self, files: Dict[str, str]) -> str:
        """
        Create a shell command that writes multiple files using base64 encoding.
        Avoids put_archive which doesn't work with read-only filesystems.
        
        Args:
            files: Dictionary mapping file paths to file contents
            
        Returns:
            Shell command string that creates all files
        """
        import base64
        commands = []
        for filepath, content in files.items():
            # Base64 encode content and create file
            content_b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')
            # Ensure directory exists
            dirpath = filepath.rsplit('/', 1)[0] if '/' in filepath else '/tmp'
            commands.append(f"mkdir -p {dirpath}")
            commands.append(f"echo {content_b64} | base64 -d > {filepath}")
        return " && ".join(commands)
    
    def run_code(
        self,
        code: str,
        language: str,
        test_cases: List[Dict[str, str]],
        time_limit: int = 30,
        memory_limit: int = 256,
        solution_function_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute code in isolated Docker container.

        Args:
            code: User's code to execute
            language: Programming language (python, java, cpp)
            test_cases: List of test cases with 'input' and 'expected_output'
            time_limit: Time limit in seconds
            memory_limit: Memory limit in MB
            solution_function_names: Optional list of function names to try first (from question template).

        Returns:
            Dictionary with execution results:
            - passed: bool
            - results: List of test case results
            - execution_time: float
            - memory_used: int
            - error: Optional[str]
        """
        if not self.client:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": "Docker not available"
            }

        test_cases = _normalize_test_cases_for_runner(test_cases)

        # Pre-check: detect language from code first (most reliable)
        code_upper = code.strip()[:200].upper()
        detected_language = None
        
        # C++ detection: #include, using namespace, int main(), vector<, etc.
        if any(marker in code_upper for marker in ['#INCLUDE', '#include', 'USING NAMESPACE', 'using namespace', 
                                                   'INT MAIN()', 'int main()', 'VECTOR<', 'vector<', 
                                                   'STD::', 'std::', 'COUT', 'cout', 'CIN', 'cin']):
            detected_language = "cpp"
        # Java detection: import java, public class, package, etc.
        elif any(marker in code_upper for marker in ['IMPORT JAVA', 'import java', 'PUBLIC CLASS', 'public class',
                                                      'PACKAGE ', 'package ', 'PUBLIC STATIC', 'public static']):
            detected_language = "java"
        # Python detection: def, import (but not #include), print(, etc.
        elif any(marker in code_upper for marker in ['DEF ', 'def ', 'IMPORT ', 'import ', 'PRINT(', 'print(',
                                                      'IF __NAME__', 'if __name__']) and '#INCLUDE' not in code_upper:
            detected_language = "python"
        
        # Normalize language string (handle case variations and common aliases)
        # Handle enum objects by extracting their value
        if hasattr(language, 'value'):
            language_str = language.value
        elif hasattr(language, 'name'):
            language_str = language.name.lower()
        else:
            language_str = str(language)
        
        language_normalized = language_str.lower().strip()
        
        # Normalize common variations
        if language_normalized in ["c++", "cplusplus", "cpp"]:
            language_normalized = "cpp"
        elif language_normalized in ["py", "python3", "python"]:
            language_normalized = "python"
        elif language_normalized in ["java"]:
            language_normalized = "java"
        
        # Use detected language if normalization failed or if there's a mismatch
        if language_normalized not in ["python", "java", "cpp"]:
            if detected_language:
                language_normalized = detected_language
        elif detected_language and detected_language != language_normalized:
            # Language parameter doesn't match code - trust the code detection
            language_normalized = detected_language
        
        # Select appropriate executor based on language
        if language_normalized == "python":
            return self._run_python(code, test_cases, time_limit, memory_limit, solution_function_names)
        elif language_normalized == "java":
            return self._run_java(code, test_cases, time_limit, memory_limit)
        elif language_normalized == "cpp":
            return self._run_cpp(code, test_cases, time_limit, memory_limit)
        else:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": f"Unsupported language: {language} (normalized: {language_normalized}). Supported: python, java, cpp"
            }
    
    def run_custom_input(
        self,
        code: str,
        language: str,
        custom_input: str,
        time_limit: int = 30,
        memory_limit: int = 256
    ) -> Dict[str, Any]:
        """
        Execute code with custom user input (for "Run Code" feature).
        
        Args:
            code: User's code to execute
            language: Programming language (python, java, cpp)
            custom_input: User-provided input (flexible format: multi-line, JSON, space-separated)
            time_limit: Time limit in seconds
            memory_limit: Memory limit in MB
            
        Returns:
            Dictionary with execution results:
            - output: Raw output from code execution
            - execution_time: float
            - memory_used: int
            - error: Optional[str]
        """
        if not self.client:
            return {
                "output": "",
                "execution_time": 0.0,
                "memory_used": 0,
                "error": "Docker not available"
            }
        
        # Create a single test case with custom input (no expected output for custom runs)
        test_case = {
            "input": custom_input,
            "expected_output": ""  # Not used for custom input
        }
        
        # Execute using language-specific custom input handler
        if language == "python":
            return self._run_python_custom_input(code, custom_input, time_limit, memory_limit)
        elif language == "java":
            return self._run_java_custom_input(code, custom_input, time_limit, memory_limit)
        elif language == "cpp":
            return self._run_cpp_custom_input(code, custom_input, time_limit, memory_limit)
        else:
            return {
                "output": "",
                "execution_time": 0.0,
                "memory_used": 0,
                "error": f"Unsupported language: {language}"
            }
    
    def _run_python(
        self,
        code: str,
        test_cases: List[Dict[str, str]],
        time_limit: int,
        memory_limit: int,
        solution_function_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute Python code using Docker.
        
        Uses python:3.10-slim image with security constraints.
        """
        # Safety check: detect if C++ or Java code was accidentally passed
        # This should never happen if language detection works correctly
        code_start = code.strip()[:100].upper()
        if '#INCLUDE' in code_start or '#include' in code_start or 'USING NAMESPACE' in code_start:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": "C++ code was routed to Python runner. The backend should auto-detect C++ code - this may indicate a language parameter issue."
            }
        if 'IMPORT JAVA' in code_start or 'PUBLIC CLASS' in code_start or 'PACKAGE ' in code_start:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": "Java code was routed to Python runner. The backend should auto-detect Java code - this may indicate a language parameter issue."
            }
        
        if not test_cases:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": "No test cases provided"
            }
        
        try:
            # Create test runner script (prefer AI-provided function names for this question)
            test_runner = self._create_python_test_runner(code, test_cases, solution_function_names)
            
            # Create files command (avoids put_archive on read-only fs)
            files_cmd = self._create_files_command({
                "/tmp/runner.py": test_runner
            })
            
            # Create container with security constraints
            container = self.client.containers.create(
                image="python:3.10-slim",
                command=["sh", "-c", f"{files_cmd} && python /tmp/runner.py"],
                mem_limit=f"{memory_limit}m",
                memswap_limit=f"{memory_limit}m",
                network_disabled=True,
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=100m"},
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],
                pids_limit=10,
                ulimits=[docker.types.Ulimit(name="nofile", soft=64, hard=64)],
                stdin_open=False,
                tty=False
            )
            
            # Start container and measure time
            start_time = time.time()
            container.start()
            
            # Wait for container with timeout
            try:
                exit_code = container.wait(timeout=time_limit + 5)
            except Exception as e:
                container.kill()
                container.remove()
                return {
                    "passed": False,
                    "results": [],
                    "execution_time": time_limit,
                    "memory_used": 0,
                    "error": f"Execution timeout exceeded ({time_limit}s)"
                }
            
            execution_time = time.time() - start_time
            
            # Get output
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            
            # Get memory stats
            stats = container.stats(stream=False)
            memory_used = stats.get('memory_stats', {}).get('usage', 0) // (1024 * 1024)  # MB
            
            # Remove container
            container.remove()
            
            # Parse results
            try:
                results_data = json.loads(logs.strip())
                test_results = results_data.get("results", [])
                passed_count = sum(1 for r in test_results if r.get("passed", False))
                
                return {
                    "passed": passed_count == len(test_cases),
                    "results": test_results,
                    "execution_time": execution_time,
                    "memory_used": memory_used,
                    "error": results_data.get("error")
                }
            except json.JSONDecodeError:
                # If output is not JSON, it's likely an error
                return {
                    "passed": False,
                    "results": [],
                    "execution_time": execution_time,
                    "memory_used": memory_used,
                    "error": logs[:500] if logs else "Unknown error"
                }
                
        except docker.errors.ImageNotFound:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": "Python Docker image not found. Please pull python:3.10-slim"
            }
        except Exception as e:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": f"Execution error: {str(e)}"
            }
    
    def _create_python_test_runner(
        self,
        code: str,
        test_cases: List[Dict[str, str]],
        solution_function_names: Optional[List[str]] = None,
    ) -> str:
        """Create Python test runner script. Tries solution_function_names first, then fallback list."""
        test_cases_json = json.dumps(test_cases)
        default_func_names = [
            'sum_numbers', 'add', 'sum', 'add_numbers', 'get_sum',
            'find_max', 'find_maximum', 'max_of_two', 'maximum', 'max',
            'max_consecutive_ones', 'findMaxConsecutiveOnes', 'maxConsecutiveOnes',
            'smallest_subarray_sum', 'smallestSubarray', 'minSubArrayLen', 'min_subarray_len',
            'solution', 'solve', 'main'
        ]
        func_names_list = (solution_function_names or []) + default_func_names
        func_names_literal = repr(func_names_list)
        return f"""import json
import sys
from io import StringIO

# User's code
user_code = {repr(code)}

# Test cases
test_cases = {test_cases_json}

results = []
error_occurred = None

def normalize(s):
    if s is None: return ""
    s = str(s).strip().replace("\\r\\n", "\\n").replace("\\r", "\\n")
    return s

def output_matches(actual, expected):
    an, en = normalize(actual), normalize(expected)
    if an == en: return True
    try:
        fa, fe = float(an), float(en)
        return fa == fe
    except (ValueError, TypeError):
        pass
    return False

try:
    # Execute user code in a namespace
    # Wrap in try-except to handle code that reads input at module level
    namespace = {{}}
    try:
        # First, try executing with empty stdin to avoid EOF errors
        old_stdin = sys.stdin
        sys.stdin = StringIO("")
        exec(user_code, namespace)
        sys.stdin = old_stdin
    except EOFError:
        # Code tried to read input - that's OK, we'll handle it per test case
        sys.stdin = old_stdin
        pass
    except Exception:
        # Re-raise other exceptions
        sys.stdin = old_stdin
        raise
    
    # Try to find solution function (prefer question's solution_function_names, then fallback list)
    solution_func = None
    func_names = {func_names_literal}

    for name in func_names:
        if name in namespace and callable(namespace[name]):
            solution_func = namespace[name]
            break
    
    # If no named function found, try to find any function that takes arguments
    if solution_func is None:
        for name, obj in namespace.items():
            if callable(obj) and not name.startswith('_') and name not in ['print', 'input', 'range', 'len', 'str', 'int']:
                # Check if it's likely a solution function (has parameters)
                import inspect
                try:
                    sig = inspect.signature(obj)
                    if len(sig.parameters) > 0:
                        solution_func = obj
                        break
                except:
                    pass
    
    # Run test cases
    for i, test_case in enumerate(test_cases):
        input_data = test_case.get('input', '').strip()
        expected_output = test_case.get('expected_output', '').strip()
        
        try:
            actual_output = ""
            
            if solution_func:
                # Parse input
                try:
                    # Try JSON first
                    parsed_input = json.loads(input_data) if input_data else None
                except:
                    # Try space-separated integers
                    if input_data:
                        parts = input_data.split()
                        if len(parts) == 1:
                            try:
                                parsed_input = int(parts[0])
                            except:
                                parsed_input = input_data
                        else:
                            try:
                                parsed_input = [int(x) for x in parts]
                            except:
                                parsed_input = parts
                    else:
                        parsed_input = None
                
                # Call function (capture stdout so print()-based solutions work)
                import inspect
                sig = inspect.signature(solution_func)
                param_count = len(sig.parameters)
                old_stdout = sys.stdout
                sys.stdout = StringIO()
                try:
                    ret = None
                    if param_count == 0:
                        ret = solution_func()
                    elif param_count == 1:
                        ret = solution_func(parsed_input)
                    elif param_count == 2 and isinstance(parsed_input, list) and len(parsed_input) >= 2:
                        if len(parsed_input) == 2:
                            try:
                                ret = solution_func(parsed_input[0], parsed_input[1])
                            except TypeError:
                                pass
                        if ret is None and len(parsed_input) >= 2:
                            try:
                                ret = solution_func(parsed_input[0], parsed_input[1:])
                            except TypeError:
                                try:
                                    ret = solution_func(parsed_input[:-1], parsed_input[-1])
                                except TypeError:
                                    pass
                    else:
                        if isinstance(parsed_input, list):
                            ret = solution_func(*parsed_input)
                        else:
                            ret = solution_func(parsed_input)
                    captured = sys.stdout.getvalue().strip()
                    sys.stdout = old_stdout
                    # Use printed output if present, else return value (so print(i) works)
                    if captured:
                        actual_output = captured
                    elif ret is not None:
                        actual_output = str(ret)
                    else:
                        actual_output = ""
                except Exception:
                    sys.stdout = old_stdout
                    raise
            else:
                # Try to run code with stdin input (for main block code)
                old_stdin = sys.stdin
                try:
                    sys.stdin = StringIO(input_data)
                    old_stdout = sys.stdout
                    sys.stdout = StringIO()
                    exec(user_code, namespace)
                    actual_output = sys.stdout.getvalue().strip()
                    sys.stdout = old_stdout
                except Exception as e:
                    actual_output = ""
                    raise e
                finally:
                    sys.stdin = old_stdin
            
            actual_output = str(actual_output).strip()
            expected_output = str(expected_output).strip()
            
            # Compare: normalize newlines/trim, and if both numeric compare as float
            passed = output_matches(actual_output, expected_output)
            
            results.append({{
                "passed": passed,
                "input": input_data,
                "expected_output": expected_output,
                "actual_output": actual_output,
                "error": None
            }})
        except Exception as e:
            import traceback
            error_msg = str(e)
            results.append({{
                "passed": False,
                "input": input_data,
                "expected_output": expected_output,
                "actual_output": "",
                "error": error_msg
            }})
                
except Exception as e:
    import traceback
    error_occurred = str(e) + "\\n" + traceback.format_exc()

output = {{
    "results": results,
    "error": error_occurred
}}

print(json.dumps(output))
sys.stdout.flush()
"""
    
    def _run_java(
        self,
        code: str,
        test_cases: List[Dict[str, str]],
        time_limit: int,
        memory_limit: int
    ) -> Dict[str, Any]:
        """
        Execute Java code using Docker.
        
        Uses eclipse-temurin:17-alpine image with security constraints.
        """
        if not test_cases:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": "No test cases provided"
            }
        
        try:
            # Extract class name from code
            import re
            class_match = re.search(r'public\s+class\s+(\w+)', code)
            if not class_match:
                return {
                    "passed": False,
                    "results": [],
                    "execution_time": 0.0,
                    "memory_used": 0,
                    "error": "No public class found in Java code"
                }
            class_name = class_match.group(1)
            
            # Create test runner script
            test_runner = self._create_java_test_runner(code, test_cases, class_name)
            
            # Create files command (avoids put_archive on read-only fs)
            files_cmd = self._create_files_command({
                f"/tmp/{class_name}.java": code,
                "/tmp/run.sh": test_runner
            })
            
            # JVM options for 256MB container: limit heap, stack, use serial GC, single CPU
            java_opts = "-Xmx128m -Xss256k -XX:+UseSerialGC -XX:ActiveProcessorCount=1"
            
            # Create container
            container = self.client.containers.create(
                image="eclipse-temurin:17-alpine",
                command=["sh", "-c", f"export JAVA_TOOL_OPTIONS='{java_opts}' && {files_cmd} && sh /tmp/run.sh"],
                mem_limit=f"{memory_limit}m",
                memswap_limit=f"{memory_limit}m",
                network_disabled=True,
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=100m"},
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],
                pids_limit=50,
                ulimits=[docker.types.Ulimit(name="nofile", soft=64, hard=64)],
                stdin_open=False,
                tty=False
            )
            
            # Start container
            start_time = time.time()
            container.start()
            
            # Wait for container
            try:
                exit_code = container.wait(timeout=time_limit + 10)
            except Exception as e:
                container.kill()
                container.remove()
                return {
                    "passed": False,
                    "results": [],
                    "execution_time": time_limit,
                    "memory_used": 0,
                    "error": f"Execution timeout exceeded ({time_limit}s)"
                }
            
            execution_time = time.time() - start_time
            
            # Get output
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            logs = _strip_jvm_stderr(logs)
            
            # Get memory stats
            stats = container.stats(stream=False)
            memory_used = stats.get('memory_stats', {}).get('usage', 0) // (1024 * 1024)
            
            # Remove container
            container.remove()
            
            # Parse results
            try:
                # Check for detailed compilation error output
                comp_err_start = logs.find("___COMPILATION_ERROR_START___")
                comp_err_end = logs.find("___COMPILATION_ERROR_END___")
                if comp_err_start != -1 and comp_err_end != -1:
                    comp_msg = logs[comp_err_start + len("___COMPILATION_ERROR_START___"):comp_err_end].strip()
                    return {
                        "passed": False,
                        "results": [],
                        "execution_time": execution_time,
                        "memory_used": memory_used,
                        "error": "Compilation failed:\n" + comp_msg[:3000]
                    }
                # Extract JSON from logs (might have compilation errors before)
                json_start = logs.find('{"results"')
                if json_start == -1:
                    json_start = logs.find('{')
                if json_start == -1:
                    return {
                        "passed": False,
                        "results": [],
                        "execution_time": execution_time,
                        "memory_used": memory_used,
                        "error": _sanitize_error_for_client(logs[:500])
                    }
                
                # Find the end of the JSON object (look for closing brace after results array)
                json_str = logs[json_start:]
                # Try to find complete JSON by matching braces
                brace_count = 0
                json_end = -1
                for i, char in enumerate(json_str):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if json_end == -1:
                    # Fallback: try parsing the whole remaining string
                    json_to_parse = json_str.strip()
                else:
                    json_to_parse = json_str[:json_end].strip()
                
                results_data = json.loads(json_to_parse)
                test_results = results_data.get("results", [])
                # Ensure test_results is a list of dicts
                if not isinstance(test_results, list):
                    test_results = []
                passed_count = sum(1 for r in test_results if isinstance(r, dict) and r.get("passed", False))
                
                return {
                    "passed": passed_count == len(test_cases),
                    "results": test_results,
                    "execution_time": execution_time,
                    "memory_used": memory_used,
                    "error": results_data.get("error")
                }
            except json.JSONDecodeError as e:
                # Log the problematic JSON for debugging (first 1000 chars)
                error_preview = json_to_parse[:1000] if 'json_to_parse' in locals() else logs[:500]
                return {
                    "passed": False,
                    "results": [],
                    "execution_time": execution_time,
                    "memory_used": memory_used,
                    "error": f"Failed to parse test results JSON: {str(e)[:200]}. Output preview: {_sanitize_error_for_client(error_preview)}"
                }
                
        except docker.errors.ImageNotFound:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": "Java Docker image not found. Please pull eclipse-temurin:17-alpine"
            }
        except Exception as e:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": f"Execution error: {str(e)}"
            }
    
    def _create_java_test_runner(self, code: str, test_cases: List[Dict[str, str]], class_name: str) -> str:
        """Create Java test runner shell script with proper test harness."""
        # Escape JSON for embedding in shell script
        test_cases_json = json.dumps(test_cases).replace('\\', '\\\\').replace('"', '\\"')
        
        # Extract strings with backslashes to avoid f-string issues
        # Use raw strings for patterns with backslashes
        split_pattern = r"}},\\s*\\{\\{"
        input_quote = r'\"input\":'
        expected_quote = r'\"expected_output\":'
        quote_char = r'\"'
        whitespace_pattern = r"\\s+"
        # Java line to print one result as JSON. Each segment must be a proper Java string
        # literal (starts/ends with ") so the generated line compiles.
        java_result_line = (
            '"\\"passed\\": " + r.get("passed") + ", " + '
            '"\\"input\\": \\"" + r.get("input") + "\\", " + '
            '"\\"expected_output\\": \\"" + r.get("expected_output") + "\\", " + '
            '"\\"actual_output\\": \\"" + r.get("actual_output") + "\\", " + '
            '"\\"error\\": " + (r.get("error") == null ? "null" : "\\"" + r.get("error").toString().replace("\\\\", "\\\\\\\\").replace("\\"", "\\\\\\"") + "\\"")'
        )
        
        # Use .format() instead of f-string to avoid backslash issues
        template = """#!/bin/sh
cd /tmp

# Write user's Java code
cat > {class_name}.java << 'JAVACODE'
{code}
JAVACODE

# Compile user code and capture output
JAVAC_OUT=$(javac {class_name}.java 2>&1)
if [ $? -ne 0 ]; then
    echo "___COMPILATION_ERROR_START___"
    printf '%s' "$JAVAC_OUT" | head -c 3000
    echo ""
    echo "___COMPILATION_ERROR_END___"
    echo '{{"results": [], "error": "Compilation failed (see compiler output above)"}}'
    exit 1
fi

# Create test runner Java file
cat > TestRunner.java << 'TESTRUNNER'
import java.util.*;
import java.io.*;

public class TestRunner {{
    private static String normalize(String s) {{
        if (s == null) return "";
        return s.trim().replace("\\r\\n", "\\n").replace("\\r", "\\n");
    }}

    // Simple JSON-like parser for test cases
    private static List<Map<String, String>> parseTestCases(String json) {{
        List<Map<String, String>> testCases = new ArrayList<>();
        // Remove outer brackets and split by test case
        json = json.trim();
        if (json.startsWith("[")) json = json.substring(1);
        if (json.endsWith("]")) json = json.substring(0, json.length() - 1);
        
        // Split by "}},{{" to get individual test cases
        String[] cases = json.split("{split_pattern}");
        for (String testCase : cases) {{
            testCase = testCase.replace("{{", "").replace("}}", "");
            Map<String, String> tc = new HashMap<>();
            
            // Extract input
            int inputIdx = testCase.indexOf("{input_quote}");
            int expectedIdx = testCase.indexOf("{expected_quote}");
            
            if (inputIdx != -1 && expectedIdx != -1) {{
                String inputPart = testCase.substring(inputIdx + 9, expectedIdx);
                String expectedPart = testCase.substring(expectedIdx + 18);
                
                // Extract values (remove quotes)
                if (inputPart.contains("{quote_char}")) {{
                    int start = inputPart.indexOf("{quote_char}") + 1;
                    int end = inputPart.lastIndexOf("{quote_char}");
                    if (end > start) {{
                        tc.put("input", inputPart.substring(start, end));
                    }}
                }}
                
                if (expectedPart.contains("{quote_char}")) {{
                    int start = expectedPart.indexOf("{quote_char}") + 1;
                    int end = expectedPart.indexOf("{quote_char}", start);
                    if (end > start) {{
                        tc.put("expected_output", expectedPart.substring(start, end));
                    }}
                }}
            }}
            
            if (!tc.isEmpty()) {{
                testCases.add(tc);
            }}
        }}
        return testCases;
    }}
    
    public static void main(String[] args) {{
        String testCasesJson = "{test_cases_json}";
        
        List<Map<String, String>> testCases = parseTestCases(testCasesJson);
        List<Map<String, Object>> results = new ArrayList<>();
        
        try {{
            // Try to find solution method using reflection
            Class<?> solutionClass = Class.forName("{class_name}");
            java.lang.reflect.Method solutionMethod = null;
            
            // Look for common method names
            String[] methodNames = {{"maxConsecutiveOnes", "findMaxConsecutiveOnes", 
                                    "smallestSubarraySum", "minSubArrayLen", 
                                    "solution", "solve"}};
            
            for (String methodName : methodNames) {{
                try {{
                    solutionMethod = solutionClass.getMethod(methodName, int[].class);
                    break;
                }} catch (NoSuchMethodException e) {{
                    try {{
                        // Try (int[] arr, int k)
                        solutionMethod = solutionClass.getMethod(methodName, int[].class, int.class);
                        break;
                    }} catch (NoSuchMethodException e2) {{
                        try {{
                            // Try (int k, int[] arr)
                            solutionMethod = solutionClass.getMethod(methodName, int.class, int[].class);
                            break;
                        }} catch (NoSuchMethodException e3) {{
                            // Try next method
                        }}
                    }}
                }}
            }}
            
            // If no method found, try to find main method or any public method
            if (solutionMethod == null) {{
                java.lang.reflect.Method[] methods = solutionClass.getMethods();
                for (java.lang.reflect.Method m : methods) {{
                    if (m.getParameterCount() == 1 || m.getParameterCount() == 2) {{
                        Class<?>[] params = m.getParameterTypes();
                        // Accept methods with (int[]), (int[], int), or (int, int[])
                        if (params.length == 1 && params[0] == int[].class) {{
                            solutionMethod = m;
                            break;
                        }} else if (params.length == 2 && 
                                   ((params[0] == int[].class && params[1] == int.class) ||
                                    (params[0] == int.class && params[1] == int[].class))) {{
                            solutionMethod = m;
                            break;
                        }}
                    }}
                }}
            }}
            
            // Run test cases
            for (Map<String, String> testCase : testCases) {{
                String input = testCase.get("input");
                String expected = testCase.get("expected_output");
                
                try {{
                    // Parse input (space-separated integers)
                    String[] parts = input.trim().split("{whitespace_pattern}");
                    int[] nums = new int[parts.length];
                    for (int i = 0; i < parts.length; i++) {{
                        nums[i] = Integer.parseInt(parts[i]);
                    }}
                    
                    String actualOutput = "";
                    
                    if (solutionMethod != null) {{
                        Object result;
                        if (solutionMethod.getParameterCount() == 1) {{
                            result = solutionMethod.invoke(null, (Object) nums);
                        }} else {{
                            // Two parameters: detect order (int[], int) vs (int, int[])
                            Class<?>[] paramTypes = solutionMethod.getParameterTypes();
                            
                            // Try both interpretations: K first vs K last
                            // For (int k, int[] arr): K is first element
                            // For (int[] arr, int k): K is last element
                            int kFirst = nums[0];
                            int[] arrKFirst = Arrays.copyOfRange(nums, 1, nums.length);
                            int kLast = nums[nums.length - 1];
                            int[] arrKLast = Arrays.copyOf(nums, nums.length - 1);
                            
                            if (paramTypes[0] == int[].class && paramTypes[1] == int.class) {{
                                // Method signature: (int[] arr, int k) - K is last
                                result = solutionMethod.invoke(null, (Object) arrKLast, kLast);
                            }} else if (paramTypes[0] == int.class && paramTypes[1] == int[].class) {{
                                // Method signature: (int k, int[] arr) - K is first
                                result = solutionMethod.invoke(null, kFirst, (Object) arrKFirst);
                            }} else {{
                                // Fallback: try both orders
                                try {{
                                    // Try (arr, k) with K last
                                    result = solutionMethod.invoke(null, (Object) arrKLast, kLast);
                                }} catch (Exception e) {{
                                    // If that fails, try (k, arr) with K first
                                    result = solutionMethod.invoke(null, kFirst, (Object) arrKFirst);
                                }}
                            }}
                        }}
                        actualOutput = String.valueOf(result);
                    }} else {{
                        // Try to call main method
                        try {{
                            java.lang.reflect.Method mainMethod = solutionClass.getMethod("main", String[].class);
                            // Redirect stdin/stdout
                            System.setIn(new java.io.ByteArrayInputStream(input.getBytes()));
                            java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream();
                            PrintStream oldOut = System.out;
                            System.setOut(new PrintStream(baos));
                            mainMethod.invoke(null, (Object) new String[0]);
                            System.setOut(oldOut);
                            actualOutput = baos.toString().trim();
                        }} catch (Exception e) {{
                            throw new RuntimeException("No suitable method found", e);
                        }}
                    }}
                    
                    boolean passed = normalize(actualOutput).equals(normalize(expected));
                    
                    Map<String, Object> result = new HashMap<>();
                    result.put("passed", passed);
                    result.put("input", input);
                    result.put("expected_output", expected);
                    result.put("actual_output", actualOutput);
                    result.put("error", null);
                    results.add(result);
                    
                }} catch (Exception e) {{
                    Map<String, Object> result = new HashMap<>();
                    result.put("passed", false);
                    result.put("input", input);
                    result.put("expected_output", expected);
                    result.put("actual_output", "");
                    result.put("error", e.getMessage());
                    results.add(result);
                }}
            }}
            
        }} catch (Exception e) {{
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("results", new ArrayList<>());
            errorResult.put("error", e.getMessage());
            System.out.println(errorResult);
            return;
        }}
        
        // Output JSON results (escaped: {{ -> {{, \\\" -> \" in Java)
        // java_result_line must be valid Java: every concatenated part must be a string literal (opening " before each segment).
        System.out.print("{{\\\"results\\\": [");
        for (int i = 0; i < results.size(); i++) {{
            if (i > 0) System.out.print(",");
            Map<String, Object> r = results.get(i);
            System.out.print("{{" + {java_result_line} + "}}");
        }}
        System.out.println("]}");
    }}
}}
TESTRUNNER

# Compile test runner and capture output
JAVAC_OUT=$(javac TestRunner.java 2>&1)
if [ $? -ne 0 ]; then
    echo "___COMPILATION_ERROR_START___"
    printf '%s' "$JAVAC_OUT" | head -c 3000
    echo ""
    echo "___COMPILATION_ERROR_END___"
    echo '{{"results": [], "error": "Test runner compilation failed (see compiler output above)"}}'
    exit 1
fi

# Run test runner
java TestRunner 2>&1
"""
        
        # Use string replacement instead of .format() to avoid brace escaping issues entirely
        # Replace all placeholders directly without using Python's format() which has strict brace matching
        # Order matters: replace placeholders first, then convert {{ to { and }} to }
        result = template
        result = result.replace('{class_name}', class_name)
        result = result.replace('{code}', code)
        result = result.replace('{split_pattern}', split_pattern)
        result = result.replace('{input_quote}', input_quote)
        result = result.replace('{expected_quote}', expected_quote)
        result = result.replace('{quote_char}', quote_char)
        result = result.replace('{whitespace_pattern}', whitespace_pattern)
        result = result.replace('{test_cases_json}', test_cases_json)
        result = result.replace('{java_result_line}', java_result_line)
        # Now convert double braces to single braces ({{ -> {, }} -> })
        result = result.replace('{{', '{')
        result = result.replace('}}', '}')
        return result
    
    def _run_cpp(
        self,
        code: str,
        test_cases: List[Dict[str, str]],
        time_limit: int,
        memory_limit: int
    ) -> Dict[str, Any]:
        """
        Execute C++ code using Docker.
        
        Uses gcc:latest image with security constraints.
        """
        if not test_cases:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": "No test cases provided"
            }
        
        try:
            # Create test runner script
            test_runner = self._create_cpp_test_runner(code, test_cases)
            
            # Create files command (avoids put_archive on read-only fs)
            files_cmd = self._create_files_command({
                "/tmp/solution.cpp": code,
                "/tmp/run.sh": test_runner
            })
            
            # Create container
            # Note: tmpfs with explicit 'exec' is needed for C++ to execute compiled binaries
            # Security is maintained through read_only rootfs, network_disabled, and dropped capabilities
            container = self.client.containers.create(
                image="gcc:latest",
                command=["sh", "-c", f"{files_cmd} && sh /tmp/run.sh"],
                mem_limit=f"{memory_limit}m",
                memswap_limit=f"{memory_limit}m",
                network_disabled=True,
                read_only=True,
                tmpfs={"/tmp": "rw,exec,nosuid,size=100m"},  # Explicit exec option for C++ binary execution
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],
                pids_limit=10,
                ulimits=[docker.types.Ulimit(name="nofile", soft=64, hard=64)],
                stdin_open=False,
                tty=False
            )
            
            # Start container
            start_time = time.time()
            container.start()
            
            # Wait for container
            try:
                exit_code = container.wait(timeout=time_limit + 10)
            except Exception as e:
                container.kill()
                container.remove()
                return {
                    "passed": False,
                    "results": [],
                    "execution_time": time_limit,
                    "memory_used": 0,
                    "error": f"Execution timeout exceeded ({time_limit}s)"
                }
            
            execution_time = time.time() - start_time
            
            # Get output
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            
            # Get memory stats
            stats = container.stats(stream=False)
            memory_used = stats.get('memory_stats', {}).get('usage', 0) // (1024 * 1024)
            
            # Remove container
            container.remove()
            
            # Parse results
            try:
                # Check for detailed compilation error output
                comp_err_start = logs.find("___COMPILATION_ERROR_START___")
                comp_err_end = logs.find("___COMPILATION_ERROR_END___")
                if comp_err_start != -1 and comp_err_end != -1:
                    comp_msg = logs[comp_err_start + len("___COMPILATION_ERROR_START___"):comp_err_end].strip()
                    return {
                        "passed": False,
                        "results": [],
                        "execution_time": execution_time,
                        "memory_used": memory_used,
                        "error": "Compilation failed:\n" + comp_msg[:3000]
                    }
                json_start = logs.find('{')
                if json_start == -1:
                    return {
                        "passed": False,
                        "results": [],
                        "execution_time": execution_time,
                        "memory_used": memory_used,
                        "error": logs[:500]
                    }
                
                results_data = json.loads(logs[json_start:].strip())
                test_results = results_data.get("results", [])
                passed_count = sum(1 for r in test_results if r.get("passed", False))
                
                return {
                    "passed": passed_count == len(test_cases),
                    "results": test_results,
                    "execution_time": execution_time,
                    "memory_used": memory_used,
                    "error": results_data.get("error")
                }
            except json.JSONDecodeError:
                return {
                    "passed": False,
                    "results": [],
                    "execution_time": execution_time,
                    "memory_used": memory_used,
                    "error": logs[:500] if logs else "Unknown error"
                }
                
        except docker.errors.ImageNotFound:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": "C++ Docker image not found. Please pull gcc:latest"
            }
        except Exception as e:
            return {
                "passed": False,
                "results": [],
                "execution_time": 0.0,
                "memory_used": 0,
                "error": f"Execution error: {str(e)}"
            }
    
    def _create_cpp_test_runner(self, code: str, test_cases: List[Dict[str, str]]) -> str:
        """Create C++ test runner shell script with proper test harness."""
        # Use Python if available (gcc:latest typically includes Python)
        # Otherwise fall back to a simpler shell-based approach
        test_cases_json = json.dumps(test_cases)
        
        # Use regular string template instead of f-string to avoid brace conflicts
        # Use a raw string to avoid issues with triple quotes in embedded Python code
        template = r"""#!/bin/sh
cd /tmp

# Write C++ code
cat > solution.cpp << 'CPPCODE'
{code}
CPPCODE

# Compile solution with improved flags for better compatibility
GPP_OUT=$(g++ -std=c++17 -O2 -static-libgcc -static-libstdc++ -o solution solution.cpp 2>&1)
if [ $? -ne 0 ]; then
    echo "___COMPILATION_ERROR_START___"
    printf '%s' "$GPP_OUT" | head -c 3000
    echo ""
    echo "___COMPILATION_ERROR_END___"
    echo '{{"results": [], "error": "Compilation failed (see compiler output above)"}}'
    exit 1
fi

# Verify binary is valid ELF executable
if ! file solution 2>/dev/null | grep -q "ELF.*executable"; then
    echo '{{"results": [], "error": "Compilation produced invalid or non-executable binary"}}'
    exit 1
fi

# Make executable with multiple methods (robust permission setting)
chmod 755 solution 2>/dev/null || true
chmod u+x solution 2>/dev/null || true
chmod +x solution 2>/dev/null || true

        # Use Python to run test cases (gcc:latest includes Python)
        python3 << 'PYTHONRUNNER'
import json
import subprocess
import sys
import os

# Ensure we're in /tmp directory
os.chdir('/tmp')

# Verify solution binary exists
if not os.path.exists('/tmp/solution'):
    print('{{"results": [], "error": "Compiled binary not found at /tmp/solution"}}')
    sys.exit(1)

# Try to ensure executable permissions (may fail on some filesystems, but we'll try to run anyway)
try:
    import stat
    os.chmod('/tmp/solution', stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
except:
    pass  # Continue even if chmod fails - we'll try to execute anyway

test_cases = {test_cases_json}

results = []

def normalize(s):
    if s is None: return ""
    s = str(s).strip().replace("\\r\\n", "\\n").replace("\\r", "\\n")
    return s

def output_matches(actual, expected):
    an, en = normalize(actual), normalize(expected)
    if an == en: return True
    try:
        fa, fe = float(an), float(en)
        return fa == fe
    except (ValueError, TypeError):
        pass
    return False

# Define multiple execution methods to try (robust fallback approach)
def try_execute_binary(input_data, timeout=5):
    '''Try multiple execution methods until one works.'''
    exec_methods = [
        ['/tmp/solution'],  # Direct execution
        ['/lib64/ld-linux-x86-64.so.2', '/tmp/solution'],  # Dynamic linker (x86_64)
        ['/lib/ld-linux.so.2', '/tmp/solution'],  # Dynamic linker (i386)
        ['sh', '-c', 'exec /tmp/solution'],  # Shell exec
        ['sh', '-c', '/tmp/solution'],  # Shell wrapper
    ]
    
    last_error = None
    for method in exec_methods:
        try:
            process = subprocess.Popen(
                method,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=input_data, timeout=timeout)
            # If process exited successfully (returncode 0), consider it successful execution
            # Even if stdout is empty, that's valid output for some programs
            if process.returncode == 0:
                return stdout.strip(), stderr.strip() if stderr else None
            # If returncode != 0, try next method (might be permission issue)
            last_error = stderr.strip() if stderr else "Process exited with code " + str(process.returncode)
        except (PermissionError, FileNotFoundError, OSError) as e:
            last_error = str(e)
            continue  # Try next method
        except subprocess.TimeoutExpired:
            process.kill()
            raise  # Timeout is fatal, don't retry
    
    # All methods failed
    raise RuntimeError("All execution methods failed. Last error: " + str(last_error))

for test_case in test_cases:
    input_data = test_case.get('input', '').strip()
    expected_output = test_case.get('expected_output', '').strip()
    
    try:
        # Run solution with input via stdin using robust multi-method execution
        actual_output, error_msg = try_execute_binary(input_data, timeout=5)
        
        # Compare: normalize newlines/trim, and if both numeric compare as float
        passed = output_matches(actual_output, expected_output)
        
        results.append({{
            'passed': passed,
            'input': input_data,
            'expected_output': expected_output,
            'actual_output': actual_output,
            'error': error_msg
        }})
    except Exception as e:
        results.append({{
            'passed': False,
            'input': input_data,
            'expected_output': expected_output,
            'actual_output': '',
            'error': str(e)
        }})

output = {{'results': results}}
print(json.dumps(output))
sys.stdout.flush()
PYTHONRUNNER
"""
        
        # Replace placeholders using string replacement (avoid f-string brace issues)
        result = template
        result = result.replace('{code}', code)
        result = result.replace('{test_cases_json}', test_cases_json)
        # Convert double braces to single braces ({{ -> {, }} -> })
        result = result.replace('{{', '{')
        result = result.replace('}}', '}')
        return result
    
    def _run_python_custom_input(
        self,
        code: str,
        custom_input: str,
        time_limit: int,
        memory_limit: int
    ) -> Dict[str, Any]:
        """Execute Python code with custom input."""
        try:
            # Create a simple runner that executes code with custom input
            runner_script = f"""import sys
from io import StringIO

# User's code
user_code = {repr(code)}

# Custom input
custom_input = {repr(custom_input)}

try:
    # Redirect stdin
    old_stdin = sys.stdin
    sys.stdin = StringIO(custom_input)
    
    # Redirect stdout to capture output
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    
    # Execute user code
    exec(user_code, {{}})
    
    # Get output
    output = sys.stdout.getvalue()
    
    # Restore stdout
    sys.stdout = old_stdout
    sys.stdin = old_stdin
    
    print(output, end='')
    
except Exception as e:
    import traceback
    sys.stdout = old_stdout
    sys.stdin = old_stdin
    print(f"Error: {{e}}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
"""
            
            # Create files command (avoids put_archive on read-only fs)
            files_cmd = self._create_files_command({
                "/tmp/runner.py": runner_script
            })
            
            container = self.client.containers.create(
                image="python:3.10-slim",
                command=["sh", "-c", f"{files_cmd} && python /tmp/runner.py"],
                mem_limit=f"{memory_limit}m",
                memswap_limit=f"{memory_limit}m",
                network_disabled=True,
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=100m"},
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],
                pids_limit=10,
                ulimits=[docker.types.Ulimit(name="nofile", soft=64, hard=64)],
                stdin_open=False,
                tty=False
            )
            
            start_time = time.time()
            container.start()
            
            try:
                exit_code = container.wait(timeout=time_limit + 5)
            except Exception as e:
                container.kill()
                container.remove()
                return {
                    "output": "",
                    "execution_time": time_limit,
                    "memory_used": 0,
                    "error": f"Execution timeout exceeded ({time_limit}s)"
                }
            
            execution_time = time.time() - start_time
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            
            stats = container.stats(stream=False)
            memory_used = stats.get('memory_stats', {}).get('usage', 0) // (1024 * 1024)
            
            container.remove()
            
            # Split stdout and stderr
            lines = logs.split('\n')
            stdout_lines = []
            stderr_lines = []
            in_stderr = False
            
            for line in lines:
                if "Error:" in line or "Traceback" in line:
                    in_stderr = True
                if in_stderr:
                    stderr_lines.append(line)
                else:
                    stdout_lines.append(line)
            
            output = '\n'.join(stdout_lines).strip()
            error = '\n'.join(stderr_lines).strip() if stderr_lines else None
            
            return {
                "output": output,
                "execution_time": execution_time,
                "memory_used": memory_used,
                "error": error
            }
            
        except Exception as e:
            return {
                "output": "",
                "execution_time": 0.0,
                "memory_used": 0,
                "error": f"Execution error: {str(e)}"
            }
    
    def _run_java_custom_input(
        self,
        code: str,
        custom_input: str,
        time_limit: int,
        memory_limit: int
    ) -> Dict[str, Any]:
        """Execute Java code with custom input."""
        try:
            import re
            class_match = re.search(r'public\s+class\s+(\w+)', code)
            if not class_match:
                return {
                    "output": "",
                    "execution_time": 0.0,
                    "memory_used": 0,
                    "error": "No public class found in Java code"
                }
            class_name = class_match.group(1)
            
            # Create runner script
            runner_script = f"""#!/bin/sh
cd /tmp

cat > {class_name}.java << 'JAVACODE'
{code}
JAVACODE

JAVAC_OUT=$(javac {class_name}.java 2>&1)
if [ $? -ne 0 ]; then
    echo "___COMPILATION_ERROR___"
    printf '%s' "$JAVAC_OUT" | head -c 3000
    exit 1
fi

echo '{custom_input}' | java {class_name} 2>&1
"""
            
            # Create files command (avoids put_archive on read-only fs)
            files_cmd = self._create_files_command({
                "/tmp/run.sh": runner_script
            })
            
            # JVM options for 256MB container
            java_opts = "-Xmx128m -Xss256k -XX:+UseSerialGC -XX:ActiveProcessorCount=1"
            
            container = self.client.containers.create(
                image="eclipse-temurin:17-alpine",
                command=["sh", "-c", f"export JAVA_TOOL_OPTIONS='{java_opts}' && {files_cmd} && sh /tmp/run.sh"],
                mem_limit=f"{memory_limit}m",
                memswap_limit=f"{memory_limit}m",
                network_disabled=True,
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=100m"},
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],
                pids_limit=50,
                ulimits=[docker.types.Ulimit(name="nofile", soft=64, hard=64)],
                stdin_open=False,
                tty=False
            )
            
            start_time = time.time()
            container.start()
            
            try:
                exit_code = container.wait(timeout=time_limit + 10)
            except Exception as e:
                container.kill()
                container.remove()
                return {
                    "output": "",
                    "execution_time": time_limit,
                    "memory_used": 0,
                    "error": f"Execution timeout exceeded ({time_limit}s)"
                }
            
            execution_time = time.time() - start_time
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            
            stats = container.stats(stream=False)
            memory_used = stats.get('memory_stats', {}).get('usage', 0) // (1024 * 1024)
            
            container.remove()
            
            # Check for detailed compilation error (custom input Run Code)
            if "___COMPILATION_ERROR___" in logs:
                comp_msg = logs.split("___COMPILATION_ERROR___", 1)[-1].strip()[:3000]
                return {
                    "output": "",
                    "execution_time": execution_time,
                    "memory_used": memory_used,
                    "error": "Compilation failed:\n" + comp_msg
                }
            
            return {
                "output": logs.strip(),
                "execution_time": execution_time,
                "memory_used": memory_used,
                "error": None
            }
            
        except Exception as e:
            return {
                "output": "",
                "execution_time": 0.0,
                "memory_used": 0,
                "error": f"Execution error: {str(e)}"
            }
    
    def _run_cpp_custom_input(
        self,
        code: str,
        custom_input: str,
        time_limit: int,
        memory_limit: int
    ) -> Dict[str, Any]:
        """Execute C++ code with custom input."""
        try:
            runner_script = f"""#!/bin/sh
cd /tmp

cat > solution.cpp << 'CPPCODE'
{code}
CPPCODE

# Compile solution with improved flags for better compatibility
GPP_OUT=$(g++ -std=c++17 -O2 -static-libgcc -static-libstdc++ -o solution solution.cpp 2>&1)
if [ $? -ne 0 ]; then
    echo "___COMPILATION_ERROR___"
    printf '%s' "$GPP_OUT" | head -c 3000
    exit 1
fi

# Verify binary is valid ELF executable
if ! file solution 2>/dev/null | grep -q "ELF.*executable"; then
    echo "___COMPILATION_ERROR___"
    echo "Compilation produced invalid or non-executable binary"
    exit 1
fi

# Make executable with multiple methods (robust permission setting)
chmod 755 solution 2>/dev/null || true
chmod u+x solution 2>/dev/null || true
chmod +x solution 2>/dev/null || true

# Try multiple execution methods as fallback
if ! echo '{custom_input}' | ./solution 2>&1; then
    # Fallback: use sh to execute
    echo '{custom_input}' | sh -c './solution' 2>&1 || echo '{custom_input}' | sh -c 'exec ./solution' 2>&1
fi
"""
            
            # Create files command (avoids put_archive on read-only fs)
            files_cmd = self._create_files_command({
                "/tmp/run.sh": runner_script
            })
            
            # Note: tmpfs without 'noexec' is needed for C++ to execute compiled binaries
            container = self.client.containers.create(
                image="gcc:latest",
                command=["sh", "-c", f"{files_cmd} && sh /tmp/run.sh"],
                mem_limit=f"{memory_limit}m",
                memswap_limit=f"{memory_limit}m",
                network_disabled=True,
                read_only=True,
                tmpfs={"/tmp": "rw,exec,nosuid,size=100m"},  # Explicit exec option for C++ binary execution
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],
                pids_limit=10,
                ulimits=[docker.types.Ulimit(name="nofile", soft=64, hard=64)],
                stdin_open=False,
                tty=False
            )
            
            start_time = time.time()
            container.start()
            
            try:
                exit_code = container.wait(timeout=time_limit + 10)
            except Exception as e:
                container.kill()
                container.remove()
                return {
                    "output": "",
                    "execution_time": time_limit,
                    "memory_used": 0,
                    "error": f"Execution timeout exceeded ({time_limit}s)"
                }
            
            execution_time = time.time() - start_time
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            
            stats = container.stats(stream=False)
            memory_used = stats.get('memory_stats', {}).get('usage', 0) // (1024 * 1024)
            
            container.remove()
            
            # Check for detailed compilation error (custom input Run Code)
            if "___COMPILATION_ERROR___" in logs:
                comp_msg = logs.split("___COMPILATION_ERROR___", 1)[-1].strip()[:3000]
                return {
                    "output": "",
                    "execution_time": execution_time,
                    "memory_used": memory_used,
                    "error": "Compilation failed:\n" + comp_msg
                }
            
            return {
                "output": logs.strip(),
                "execution_time": execution_time,
                "memory_used": memory_used,
                "error": None
            }
            
        except Exception as e:
            return {
                "output": "",
                "execution_time": 0.0,
                "memory_used": 0,
                "error": f"Execution error: {str(e)}"
            }
    
    def _create_container_config(
        self,
        image: str,
        command: List[str],
        time_limit: int,
        memory_limit: int
    ) -> Dict[str, Any]:
        """
        Create Docker container configuration with security constraints.
        
        Args:
            image: Docker image name
            command: Command to execute
            time_limit: Time limit in seconds
            memory_limit: Memory limit in MB
            
        Returns:
            Container configuration dictionary
        """
        return {
            "image": image,
            "command": command,
            "mem_limit": f"{memory_limit}m",
            "memswap_limit": f"{memory_limit}m",
            "cpu_period": 100000,
            "cpu_quota": int(time_limit * 100000),  # CPU time limit
            "network_disabled": True,  # No network access
            "read_only": True,  # Read-only filesystem
            "tmpfs": {
                "/tmp": "rw,noexec,nosuid,size=100m"  # Temporary writable space
            },
            "security_opt": ["no-new-privileges:true"],
            "cap_drop": ["ALL"],  # Drop all capabilities
            "cap_add": [],  # No additional capabilities
            "pids_limit": 10,  # Limit number of processes
            "ulimits": [
                docker.types.Ulimit(name="nofile", soft=64, hard=64)
            ]
        }


# Global instance
docker_runner = DockerRunner()
