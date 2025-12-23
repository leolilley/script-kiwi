"""Run tool for Script Kiwi."""

from typing import Dict, Any, Optional, List
import json
import importlib.util
import os
import sys
import time
import traceback
import logging
import subprocess
import re
from pathlib import Path
from datetime import datetime
from ..api.script_registry import ScriptRegistry
from ..api.execution_logger import ExecutionLogger
from ..utils.script_resolver import ScriptResolver
from ..utils.shared.preflight import run_preflight
from ..utils.analytics import log_execution

logger = logging.getLogger(__name__)

# Response size limits
MAX_RESPONSE_SIZE_BYTES = 1_000_000  # 1MB max response size
MAX_ARRAY_ITEMS = 1000  # Max items in arrays before truncation
MAX_LOG_LINES = 500  # Max log lines to include
MAX_STRING_LENGTH = 10_000  # Max string length before truncation


def truncate_large_response(
    data: Any, max_items: int = MAX_ARRAY_ITEMS, max_string: int = MAX_STRING_LENGTH, path: str = ""
) -> tuple[Any, Dict[str, Any]]:
    """
    Recursively truncate large data structures to fit within MCP message limits.

    Returns:
        (truncated_data, truncation_info) where truncation_info contains details about what was truncated
    """
    truncation_info = {}

    if isinstance(data, dict):
        truncated = {}
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key
            truncated_val, info = truncate_large_response(value, max_items, max_string, new_path)
            truncated[key] = truncated_val
            if info:
                truncation_info.update(info)
        return truncated, truncation_info

    elif isinstance(data, list):
        if len(data) > max_items:
            truncated = data[:max_items]
            truncation_info[path or "root"] = {
                "type": "array",
                "original_count": len(data),
                "truncated_count": max_items,
                "message": f"Array truncated from {len(data)} to {max_items} items. Use --output-file to get full results.",
            }
            return truncated, truncation_info
        else:
            truncated = []
            for i, item in enumerate(data):
                new_path = f"{path}[{i}]" if path else f"[{i}]"
                truncated_item, info = truncate_large_response(
                    item, max_items, max_string, new_path
                )
                truncated.append(truncated_item)
                if info:
                    truncation_info.update(info)
            return truncated, truncation_info

    elif isinstance(data, str):
        if len(data) > max_string:
            truncation_info[path or "root"] = {
                "type": "string",
                "original_length": len(data),
                "truncated_length": max_string,
                "message": f"String truncated from {len(data)} to {max_string} characters.",
            }
            return data[
                :max_string
            ] + f"\n... (truncated {len(data) - max_string} more characters)", truncation_info

    return data, truncation_info


def _create_result_summary(data: Any, max_depth: int = 2, current_depth: int = 0) -> Dict[str, Any]:
    """Create a summary of large result data structures."""
    if current_depth >= max_depth:
        return {"_type": type(data).__name__, "_summary": "Max depth reached"}

    if isinstance(data, dict):
        summary = {}
        for key, value in list(data.items())[:10]:  # First 10 keys
            if isinstance(value, (dict, list)):
                summary[key] = _create_result_summary(value, max_depth, current_depth + 1)
            else:
                summary[key] = str(value)[:100]  # First 100 chars
        if len(data) > 10:
            summary["_other_keys"] = len(data) - 10
        return summary
    elif isinstance(data, list):
        if len(data) == 0:
            return []
        summary = []
        for item in data[:5]:  # First 5 items
            if isinstance(item, (dict, list)):
                summary.append(_create_result_summary(item, max_depth, current_depth + 1))
            else:
                summary.append(str(item)[:100])
        if len(data) > 5:
            summary.append(f"_and_{len(data) - 5}_more_items")
        return summary
    else:
        return str(data)[:200]


class RunTool:
    """Execute scripts with validation and progressive disclosure"""

    def __init__(self, project_path: str = None):
        self.registry = ScriptRegistry()
        self.logger = ExecutionLogger()
        self.project_path = Path(project_path) if project_path else None
        # Pass project_path to resolver - critical for MCP servers running outside project dir
        self.resolver = ScriptResolver(
            project_root=self.project_path, registry_client=self.registry
        )

    def _build_search_paths(self, script_path: Path, storage_location: str) -> list[Path]:
        """
        Build sys.path entries for script execution context.

        Architecture:
        - User space (~/.script-kiwi/scripts/) is the RUNTIME ENVIRONMENT (packages, libs)
        - Project space (.ai/scripts/) has PRIORITY for script resolution (local edits)
        - Both are ALWAYS included in PYTHONPATH for cross-tier lib imports

        Critical: Must add scripts ROOT directory (parent of lib/), not just lib/ itself.
        This makes "from lib.xyz" imports work.
        """
        paths = []

        # User space - ALWAYS included (it's the runtime environment)
        # Get script-kiwi home from env var or default
        import os

        script_kiwi_home = os.getenv("SCRIPT_KIWI_HOME")
        if script_kiwi_home:
            script_kiwi_home = Path(script_kiwi_home)
        else:
            script_kiwi_home = Path.home() / ".script-kiwi"
        user_scripts = script_kiwi_home / "scripts"
        if user_scripts.exists():
            paths.append(user_scripts)

        # Project space - included if we know where it is (ABSOLUTE path required)
        if self.project_path:
            project_scripts = self.project_path / ".ai" / "scripts"
            if project_scripts.exists() and project_scripts not in paths:
                # Project takes priority - insert at front
                paths.insert(0, project_scripts)

        # Script's own directory (for relative imports within category)
        if script_path.parent not in paths:
            paths.insert(0, script_path.parent)

        # Script's scripts root (if different from above)
        # e.g., .ai/scripts/category/script.py -> .ai/scripts/
        scripts_root = script_path.parent.parent
        if scripts_root.exists() and scripts_root not in paths:
            # Insert after script's own directory but maintain priority
            paths.insert(1, scripts_root)

        # MCP shared utilities (always available)
        import script_kiwi

        mcp_root = Path(script_kiwi.__file__).parent
        if mcp_root not in paths:
            paths.append(mcp_root)

        return paths

    def _validate_dependencies(self, dependencies: List[Any]) -> List[Dict[str, str]]:
        """
        Validate dependencies are in correct format.
        
        Dependencies must be a list of dicts with 'name' and optional 'version' keys.
        Raises clear error if dependencies are corrupted.
        
        Args:
            dependencies: List of dependency dicts
            
        Returns:
            List of validated dependency dicts
            
        Raises:
            ValueError: If dependencies are in invalid format
        """
        if not isinstance(dependencies, list):
            raise ValueError(
                f"Dependencies must be a list, got {type(dependencies).__name__}. "
                "Script metadata is corrupted - republish the script."
            )
        
        validated = []
        for i, dep in enumerate(dependencies):
            if not isinstance(dep, dict):
                raise ValueError(
                    f"Dependency {i} must be a dict, got {type(dep).__name__}: {dep}. "
                    "Script metadata is corrupted - republish the script."
                )
            
            name = dep.get("name")
            if not name or not isinstance(name, str):
                raise ValueError(
                    f"Dependency {i} 'name' field must be a string, got {type(name).__name__}: {name}. "
                    "Script metadata is corrupted - republish the script."
                )
            
            # Check for JSON-encoded corruption (name field contains JSON)
            if name.startswith('{') or name.startswith('['):
                raise ValueError(
                    f"Dependency {i} 'name' field appears to be JSON-encoded: {name[:100]}. "
                    "Script metadata is corrupted - republish the script with correct metadata."
                )
            
            version = dep.get("version")
            if version is not None and not isinstance(version, str):
                raise ValueError(
                    f"Dependency {i} 'version' field must be a string or None, got {type(version).__name__}: {version}. "
                    "Script metadata is corrupted - republish the script."
                )
            
            validated.append({"name": name, "version": version})
        
        return validated

    def _check_pip_dependencies(self, dependencies: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Check which pip dependencies are missing.

        Args:
            dependencies: List of dependency dicts with 'name' and optional 'version'

        Returns:
            List of missing dependencies with install commands
        """
        # Import the mapping for package name to module name conversion
        from ..utils.script_metadata import PACKAGE_TO_MODULE

        # Validate dependencies first
        validated_deps = self._validate_dependencies(dependencies)

        # Internal modules to skip (not pip packages)
        internal_prefixes = ("lib", "lib.")

        missing = []
        for dep in validated_deps:
            dep_name = dep.get("name") if isinstance(dep, dict) else str(dep)
            dep_version = dep.get("version") if isinstance(dep, dict) else None

            # Skip internal lib modules (handled by script-kiwi, not pip)
            if dep_name.startswith(internal_prefixes):
                continue

            # Convert package name to module name for import check
            # First check PACKAGE_TO_MODULE mapping (e.g., GitPython -> git)
            # Then fall back to simple hyphen-to-underscore conversion
            module_name = PACKAGE_TO_MODULE.get(dep_name, dep_name.replace("-", "_"))

            try:
                __import__(module_name)
            except ImportError:
                # Also try the original name (some packages use hyphens in module names)
                try:
                    __import__(dep_name)
                except ImportError:
                    install_cmd = (
                        f"pip install '{dep_name}{dep_version}'"
                        if dep_version
                        else f"pip install '{dep_name}'"
                    )
                    missing.append(
                        {
                            "name": dep_name,
                            "version": dep_version,
                            "module": module_name,
                            "install_cmd": install_cmd,
                        }
                    )

        return missing

    def _install_pip_dependencies(self, packages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Install multiple pip packages at once.

        Args:
            packages: List of package dicts with 'name' and optional 'version'

        Returns:
            Dict with installation results
        """
        if not packages:
            return {"status": "success", "installed": [], "failed": []}

        # Validate packages first
        validated_packages = self._validate_dependencies(packages)

        installed = []
        failed = []

        for pkg in validated_packages:
            pkg_name = pkg.get("name")
            pkg_version = pkg.get("version")

            try:
                package_spec = f"{pkg_name}{pkg_version}" if pkg_version else pkg_name
                logger.info(f"Installing: {package_spec}")

                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", package_spec],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if result.returncode == 0:
                    installed.append({"name": pkg_name, "version": pkg_version})
                    logger.info(f"Installed: {package_spec}")
                else:
                    error_msg = result.stderr[:200] if result.stderr else "Unknown error"
                    failed.append({"name": pkg_name, "error": error_msg})
                    logger.warning(f"Failed to install {package_spec}: {error_msg}")

            except subprocess.TimeoutExpired:
                failed.append({"name": pkg_name, "error": "Installation timed out"})
            except Exception as e:
                failed.append({"name": pkg_name, "error": str(e)})

        return {
            "status": "success" if not failed else "partial" if installed else "error",
            "installed": installed,
            "failed": failed,
        }

    async def _verify_lib_dependencies(self, script_name: str, required_libs: list[str]) -> dict:
        """Verify all required libraries are available."""
        missing_libs = []

        # Check in current storage tier's lib/
        for lib_name in required_libs:
            found = False

            # Check project lib/
            if (Path(".ai/scripts/lib") / f"{lib_name}.py").exists():
                found = True

            # Check user lib/
            import os

            script_kiwi_home = os.getenv("SCRIPT_KIWI_HOME")
            if script_kiwi_home:
                script_kiwi_home = Path(script_kiwi_home)
            else:
                script_kiwi_home = Path.home() / ".script-kiwi"
            if not found and (script_kiwi_home / "scripts/lib" / f"{lib_name}.py").exists():
                found = True

            if not found:
                missing_libs.append(lib_name)

        if missing_libs:
            return {
                "error": {
                    "code": "MISSING_DEPENDENCIES",
                    "message": f"Script '{script_name}' requires libraries that are not installed",
                    "details": {
                        "missing_libs": missing_libs,
                        "suggestion": f"Download script with dependencies",
                        "command": f"load({{'script_name': '{script_name}', 'download_to_user': true}})",
                    },
                }
            }

        return {"status": "ok"}

    def _run_function_script(
        self,
        func,
        script_params: Dict[str, Any],
        execution_id: str,
        script_name: str,
        stream_logs: bool = True,
    ) -> Dict[str, Any]:
        """
        Run a function-based script and capture stderr logs in real-time.

        Args:
            func: The execute() or main() function to call
            script_params: Parameters to pass to the function
            execution_id: Execution ID for logging
            script_name: Script name for logging
            stream_logs: Whether to stream logs to history file in real-time

        Returns:
            Function result (should be a dict with status, data, metadata)
        """
        if not stream_logs:
            # If streaming disabled, just call the function normally
            return func(script_params)

        # Set up real-time stderr logging
        from ..utils.analytics import _get_history_file, _ensure_runs_dir
        import io
        from contextlib import redirect_stderr

        history_file = _get_history_file()
        _ensure_runs_dir(history_file)

        # Create a custom stderr handler that writes to both original stderr and history file
        original_stderr = sys.stderr
        log_buffer = io.StringIO()

        class DualStderr:
            """Write to both original stderr and history file."""

            def __init__(self, original, history_file, execution_id, script_name):
                self.original = original
                self.history_file = history_file
                self.execution_id = execution_id
                self.script_name = script_name
                self.buffer = ""

            def write(self, text):
                # Write to original stderr
                self.original.write(text)
                self.original.flush()

                # Also write to history file in real-time
                if text:
                    self.buffer += text
                    # Process line by line
                    while "\n" in self.buffer:
                        line, self.buffer = self.buffer.split("\n", 1)
                        if line.strip():
                            try:
                                log_entry = {
                                    "timestamp": datetime.now().isoformat(),
                                    "execution_id": self.execution_id,
                                    "script": self.script_name,
                                    "status": "running",
                                    "log_line": line.strip(),
                                }
                                with open(self.history_file, "a") as f:
                                    f.write(json.dumps(log_entry) + "\n")
                            except Exception as e:
                                logger.warning(f"Failed to write log line: {e}")

            def flush(self):
                self.original.flush()
                # Write any remaining buffer
                if self.buffer.strip():
                    try:
                        log_entry = {
                            "timestamp": datetime.now().isoformat(),
                            "execution_id": self.execution_id,
                            "script": self.script_name,
                            "status": "running",
                            "log_line": self.buffer.strip(),
                        }
                        with open(self.history_file, "a") as f:
                            f.write(json.dumps(log_entry) + "\n")
                        self.buffer = ""
                    except Exception:
                        pass

        # Replace stderr with our dual handler
        dual_stderr = DualStderr(original_stderr, history_file, execution_id, script_name)
        sys.stderr = dual_stderr

        # Also update any existing logging handlers that use stderr
        # This ensures Python's logging module writes to our handler
        import logging

        updated_handlers = []
        # Update all loggers, not just root
        for logger_name in logging.Logger.manager.loggerDict:
            logger_obj = logging.getLogger(logger_name)
            for handler in logger_obj.handlers[:]:
                if isinstance(handler, logging.StreamHandler):
                    # Check if it's using stderr (either directly or via sys.stderr reference)
                    if handler.stream == original_stderr or handler.stream == sys.stderr:
                        handler.stream = dual_stderr
                        updated_handlers.append((logger_obj, handler, original_stderr))

        # Also check root logger
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler):
                if handler.stream == original_stderr or handler.stream == sys.stderr:
                    handler.stream = dual_stderr
                    updated_handlers.append((root_logger, handler, original_stderr))

        try:
            # Call the function
            result = func(script_params)
        except (ModuleNotFoundError, ImportError) as e:
            # Dependencies should have been checked before execution
            # If we get here, it's an undeclared dependency
            missing_module = str(e).split("'")[1] if "'" in str(e) else str(e)
            error_msg = f"Missing dependency: {missing_module}. Add to script dependencies or install manually."
            raise RuntimeError(error_msg) from e
        finally:
            # Restore original stderr
            sys.stderr = original_stderr
            # Restore logging handlers
            for logger_obj, handler, orig_stream in updated_handlers:
                handler.stream = orig_stream
            # Flush any remaining buffer
            dual_stderr.flush()

        return result

    def _run_argparse_script(
        self,
        script_path: Path,
        script_params: Dict[str, Any],
        search_paths: list[Path],
        project_path: Optional[Path] = None,
        timeout: Optional[int] = None,
        stream_logs: bool = False,
    ) -> Dict[str, Any]:
        """
        Run a script that uses argparse by executing it as a subprocess.

        Converts parameter dict to command-line arguments.
        """
        import shlex

        # Build command
        cmd = [sys.executable, str(script_path.absolute())]

        # Convert params dict to command-line args
        # Handle common patterns: video_url -> --video-url, search_term -> --search-term
        # Skip internal parameters (those starting with _)
        for key, value in script_params.items():
            if value is None:
                continue

            # Skip internal control parameters (should have been removed, but double-check)
            if key.startswith("_"):
                continue

            # Handle keys that already have -- or - prefix
            if key.startswith("--"):
                arg_flag = key
            elif key.startswith("-"):
                arg_flag = key
            else:
                # Convert snake_case to kebab-case for args
                arg_flag = f"--{key.replace('_', '-')}"

            if isinstance(value, bool):
                if value:
                    cmd.append(arg_flag)
                else:
                    # For --no- flags, strip any existing -- and add --no-
                    base_name = arg_flag.lstrip("-")
                    cmd.append(f"--no-{base_name}")
            elif isinstance(value, list):
                # For lists, repeat the argument
                for item in value:
                    cmd.extend([arg_flag, str(item)])
            else:
                cmd.extend([arg_flag, str(value)])

        # Automatically add --json-output for argparse scripts so MCP can parse the output
        # Only add if not already specified (user can override)
        # Check both snake_case and kebab-case variants
        # NOTE: Only add if script actually supports it - many scripts output JSON by default
        has_json_output = (
            "json_output" in script_params
            or "json-output" in script_params
            or any("json-output" in arg or "json_output" in arg for arg in cmd)
        )
        # Don't automatically add --json-output - scripts should output JSON by default
        # If a script needs it, it should be specified explicitly in parameters

        # Debug: Log the command being executed
        logger.debug(f"Executing argparse script with command: {' '.join(cmd)}")
        logger.debug(f"Script params: {script_params}")

        # Set PYTHONPATH to include search paths
        env = dict(os.environ)
        pythonpath = ":".join(str(p.absolute()) for p in search_paths)
        if env.get("PYTHONPATH"):
            env["PYTHONPATH"] = f"{pythonpath}:{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = pythonpath

        # Determine working directory for subprocess
        # Use project_path if provided, otherwise fall back to script's directory
        # This ensures output files (like .tmp/) are saved in the right place
        if project_path:
            subprocess_cwd = project_path
        else:
            # Fall back to script's directory so relative paths work
            subprocess_cwd = script_path.parent

        # Use configurable timeout (default 5 minutes, max 30 minutes)
        if timeout is None:
            timeout = 300  # 5 minutes default
        timeout = min(timeout, 1800)  # Cap at 30 minutes

        # Run subprocess
        try:
            if stream_logs:
                # Use Popen for streaming logs to history file in real-time
                from ..utils.analytics import _get_history_file, _ensure_runs_dir
                import threading

                history_file = _get_history_file()
                _ensure_runs_dir(history_file)

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                    cwd=subprocess_cwd,
                    bufsize=1,  # Line buffered
                )

                stdout_lines = []
                stderr_lines = []

                def log_stderr_line(line: str, execution_id: str, script_name: str):
                    """Write stderr line to history file in real-time."""
                    if line.strip():
                        try:
                            log_entry = {
                                "timestamp": datetime.now().isoformat(),
                                "execution_id": execution_id,
                                "script": script_name,
                                "status": "running",
                                "log_line": line.strip(),
                            }
                            with open(history_file, "a") as f:
                                f.write(json.dumps(log_entry) + "\n")
                        except Exception as e:
                            logger.warning(f"Failed to write log line: {e}")

                # Stream stderr to history file in real-time
                execution_id_for_logging = getattr(self, "_current_execution_id", None)
                script_name_for_logging = getattr(self, "_current_script_name", None)

                def read_stderr():
                    """Read stderr line-by-line and log to history file in real-time."""
                    try:
                        for line in iter(process.stderr.readline, ""):
                            if not line:
                                break
                            stderr_lines.append(line)
                            if execution_id_for_logging and script_name_for_logging:
                                log_stderr_line(
                                    line, execution_id_for_logging, script_name_for_logging
                                )
                    except Exception as e:
                        logger.warning(f"Error reading stderr: {e}")

                def read_stdout():
                    """Read stdout completely - important for JSON output that may be buffered."""
                    try:
                        # Read all available data (handles both line-buffered and full output)
                        # This is important because JSON output from scripts is often printed
                        # all at once and may be buffered
                        while True:
                            chunk = process.stdout.read(8192)  # Read in chunks
                            if not chunk:
                                break
                            stdout_lines.append(chunk if isinstance(chunk, str) else chunk.decode())
                    except Exception as e:
                        logger.warning(f"Error reading stdout: {e}")
                        # Try to read any remaining data
                        try:
                            remaining = process.stdout.read()
                            if remaining:
                                stdout_lines.append(
                                    remaining if isinstance(remaining, str) else remaining.decode()
                                )
                        except Exception:
                            pass

                # Start reader threads
                stderr_thread = threading.Thread(target=read_stderr, daemon=True)
                stdout_thread = threading.Thread(target=read_stdout, daemon=True)
                stderr_thread.start()
                stdout_thread.start()

                # Wait for process to complete
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    raise

                # Wait for threads to finish reading
                # Give more time for stdout since it might contain the JSON result
                stderr_thread.join(timeout=2)
                stdout_thread.join(timeout=10)  # More time for stdout (JSON output may be large)

                # Combine lines into strings
                stdout_text = "".join(stdout_lines) if stdout_lines else ""
                stderr_text = "".join(stderr_lines) if stderr_lines else ""

                # Debug: Log if stdout is empty but stderr has content
                if not stdout_text.strip() and stderr_text:
                    logger.warning(
                        f"Script {script_name_for_logging} produced no stdout but has stderr. "
                        f"Stderr length: {len(stderr_text)}"
                    )
                elif not stdout_text.strip():
                    logger.warning(f"Script {script_name_for_logging} produced no stdout output")

                result = subprocess.CompletedProcess(
                    process.args, process.returncode, stdout=stdout_text, stderr=stderr_text
                )
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=subprocess_cwd,
                    timeout=timeout,
                )

            # Parse JSON output if present (even if returncode != 0, script may output JSON error)
            output = result.stdout.strip()
            stderr_output = result.stderr.strip() if result.stderr else ""

            # Check if stdout or stderr contains JSON output
            # Scripts may output JSON errors to either stdout or stderr
            json_output = None
            json_source = None

            if output:
                try:
                    json_output = json.loads(output)
                    json_source = "stdout"
                except json.JSONDecodeError:
                    pass

            # Also check stderr for JSON (some scripts output errors as JSON to stderr)
            if not json_output and stderr_output:
                try:
                    json_output = json.loads(stderr_output)
                    json_source = "stderr"
                except json.JSONDecodeError:
                    pass

            # If we found JSON output, use it (even if returncode != 0)
            if json_output and isinstance(json_output, dict):
                if json_output.get("status") == "error":
                    # Script returned structured error - use it
                    return {
                        "status": "error",
                        "error": json_output.get("error", "unknown"),
                        "message": json_output.get("message", ""),
                        "data": json_output,
                        "metadata": {"duration_sec": None, "cost_usd": 0},
                    }
                elif json_output.get("status") == "success":
                    # Script succeeded despite non-zero return code - use the success result
                    # This handles edge cases where script exits with code 1 but still returns success JSON
                    # Continue to normal parsing below to extract data properly
                    pass  # Fall through to normal parsing below

            # Check for errors if no valid JSON was found
            if result.returncode != 0 and not json_output:
                error_msg = stderr_output or output or "Unknown error"

                # Check if this is a dependency error (undeclared dependency)
                if (
                    "ModuleNotFoundError" in error_msg
                    or "ImportError" in error_msg
                    or "No module named" in error_msg
                ):
                    missing_module = None
                    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_msg)
                    if match:
                        missing_module = match.group(1)

                    return {
                        "status": "error",
                        "error": f"Missing dependency: {missing_module or 'unknown'}. This dependency was not declared in the script metadata.",
                        "error_type": "dependency_error",
                        "missing_module": missing_module,
                        "suggestion": f"Add '{missing_module}' to script dependencies or install manually: pip install {missing_module.replace('_', '-') if missing_module else 'PACKAGE'}",
                        "data": None,
                        "metadata": {"duration_sec": None, "cost_usd": 0},
                    }

                return {
                    "status": "error",
                    "error": error_msg[:500],
                    "data": None,
                    "metadata": {"duration_sec": None, "cost_usd": 0},
                }

            # Debug: Log output length for troubleshooting
            if not output and json_source != "stderr":
                logger.warning(
                    f"Script produced no stdout output. Return code: {result.returncode}"
                )
                if stderr_output:
                    logger.debug(f"Stderr output (first 500 chars): {stderr_output[:500]}")

            # Build base response
            response = {
                "status": "success",
                "data": {},
                "metadata": {"duration_sec": None, "cost_usd": 0},
            }

            # Include stderr logs if present (scripts log to stderr)
            # Limit log lines to prevent huge responses
            # But exclude stderr if it was the JSON source (to avoid duplicating)
            if stderr_output and json_source != "stderr":
                log_lines = stderr_output.split("\n")
                if len(log_lines) > MAX_LOG_LINES:
                    response["logs"] = log_lines[:MAX_LOG_LINES]
                    response["log_truncated"] = {
                        "original_lines": len(log_lines),
                        "shown_lines": MAX_LOG_LINES,
                        "message": f"Logs truncated from {len(log_lines)} to {MAX_LOG_LINES} lines",
                    }
                else:
                    response["logs"] = log_lines

            # Use the JSON we already parsed, or try to parse output
            if json_output:
                # We already have parsed JSON (from stdout or stderr)
                parsed = json_output
            elif output:
                try:
                    # Try to parse as JSON (scripts output JSON)
                    # The script outputs pure JSON, so parse directly
                    parsed = json.loads(output)

                    # If script returned a dict with status, use it directly
                    if isinstance(parsed, dict) and "status" in parsed:
                        # Extract data from the script's output format
                        # Script outputs: {"status": "success", "video_id": ..., "transcript": ...}
                        # OR: {"status": "success", "businesses": [...], "search_term": ...}
                        # Return in script-kiwi format: {"status": "success", "data": {...}, "metadata": {...}}
                        script_status = parsed.get("status", "success")

                        # Extract metadata if present
                        script_metadata = parsed.get("metadata", {})
                        # Extract all fields except status and metadata into data
                        script_data = {
                            k: v for k, v in parsed.items() if k not in ["status", "metadata"]
                        }

                        response["status"] = script_status
                        # Truncate large data structures before including in response
                        truncated_data, truncation_info = truncate_large_response(script_data)
                        response["data"] = truncated_data
                        if truncation_info:
                            response["truncation_warnings"] = truncation_info

                        # Debug: Log if businesses or other data fields are present
                        if "businesses" in script_data:
                            logger.info(
                                f"Found {len(script_data.get('businesses', []))} businesses in script output"
                            )
                        if "items" in script_data:
                            logger.info(
                                f"Found {len(script_data.get('items', []))} items in script output"
                            )

                        # Extract metadata if present in script output
                        if script_metadata:
                            response["metadata"].update(
                                {
                                    "duration_sec": script_metadata.get("duration_sec"),
                                    "cost_usd": script_metadata.get("cost_usd", 0),
                                    "rows_processed": script_metadata.get("rows_processed"),
                                    "api_calls_made": script_metadata.get("api_calls_made"),
                                }
                            )
                        # Also check if metadata fields are at top level
                        elif "duration_sec" in parsed or "cost_usd" in parsed:
                            response["metadata"].update(
                                {
                                    "duration_sec": parsed.get("duration_sec"),
                                    "cost_usd": parsed.get("cost_usd", 0),
                                    "rows_processed": parsed.get("rows_processed"),
                                    "api_calls_made": parsed.get("api_calls_made"),
                                }
                            )
                    else:
                        # Wrap in standard format
                        response["data"] = parsed
                except json.JSONDecodeError as e:
                    # Not JSON, return as text with error details
                    logger.warning(f"Failed to parse JSON output from script: {str(e)}")
                    logger.debug(f"Output (first 1000 chars): {output[:1000]}")
                    response["data"] = {"output": output[:1000]}
                    response["data"]["parse_error"] = f"Could not parse as JSON: {str(e)}"
                    if stderr_output:
                        response["data"]["stderr"] = stderr_output[:1000]
                    # Also include raw output for debugging
                    response["data"]["_raw_output"] = output[:2000]  # More context for debugging

            # Always include stderr in response for debugging (even if JSON parsed successfully)
            # This helps diagnose issues like empty results from Apify
            if stderr_output:
                if "logs" not in response:
                    response["logs"] = stderr_output.split("\n")
                # Also include raw stderr in data for debugging
                if not response.get("data"):
                    response["data"] = {}
                response["data"]["_stderr"] = stderr_output[:500]  # First 500 chars for debugging

            # Special handling: If script returned status="success" but data is empty,
            # check if the script's output structure has the data at top level
            if response.get("status") == "success" and not response.get("data"):
                if output:
                    try:
                        parsed = json.loads(output)
                        # If parsed has businesses or other data fields, include them
                        if isinstance(parsed, dict):
                            # Check for common data fields
                            data_fields = ["businesses", "items", "results", "data"]
                            for field in data_fields:
                                if field in parsed and parsed[field]:
                                    response["data"] = {field: parsed[field]}
                                    logger.info(f"Found data in field '{field}' from script output")
                                    break
                            # If still no data, include the full parsed output in data
                            if not response.get("data") and parsed:
                                # Include all fields from parsed as data
                                response["data"] = parsed
                                logger.info(f"Including full parsed output as data")
                    except json.JSONDecodeError:
                        pass

            # If no data was extracted and we have stdout, include it for debugging
            if not response.get("data") and output:
                response["data"] = {"_stdout": output[:2000]}  # More context for debugging
                response["data"]["_stdout_length"] = len(output)
                logger.warning(
                    f"Script output was not parsed as expected. Output length: {len(output)}"
                )
                logger.debug(f"Output content (first 2000 chars): {output[:2000]}")
                # Try to show if it's JSON or not
                try:
                    json.loads(output)
                    response["data"]["_is_json"] = True
                except:
                    response["data"]["_is_json"] = False

            return response

        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": "Script execution timed out after 5 minutes",
                "data": None,
                "metadata": {"duration_sec": 300, "cost_usd": 0},
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "data": None,
                "metadata": {"duration_sec": None, "cost_usd": 0},
            }

    async def _download_lib_dependencies(self, lib_names: list[str]):
        """Download library dependencies to user space."""
        lib_dir = Path.home() / ".script-kiwi/scripts/lib"
        lib_dir.mkdir(parents=True, exist_ok=True)

        # Ensure __init__.py exists
        lib_init = lib_dir / "__init__.py"
        if not lib_init.exists():
            lib_init.write_text("# Script Kiwi library modules\n")

        for lib_name in lib_names:
            lib_file = lib_dir / f"{lib_name}.py"

            # Don't overwrite if already exists (user may have custom version)
            if lib_file.exists():
                continue

            # Get library from registry
            lib_script = await self.registry.get_script(lib_name)
            if lib_script and lib_script.get("content"):
                # Use existing download_to_user_space with category="lib"
                self.resolver.download_to_user_space(
                    script_name=lib_name,
                    category="lib",
                    content=lib_script["content"],
                    subcategory=None,
                )
                logger.info(f"Downloaded library: {lib_name}")
            else:
                logger.warning(f"Library '{lib_name}' not found in registry")

    async def _download_script_with_deps(self, script_name: str):
        """Download script and its dependencies from registry."""
        # Get script metadata
        script = await self.registry.get_script(script_name)
        if not script or not script.get("content"):
            raise ValueError(f"Script '{script_name}' not found in registry")

        # Download main script
        category = script.get("category", "utility")
        subcategory = script.get("subcategory")
        self.resolver.download_to_user_space(
            script_name=script_name,
            category=category,
            content=script["content"],
            subcategory=subcategory,
        )

        # Download dependencies
        required_libs = script.get("required_libs", [])
        if required_libs:
            await self._download_lib_dependencies(required_libs)

    async def execute(self, params: Dict[str, Any]) -> str:
        """
        Execute a script with pre-flight checks

        Args:
            script_name: Name of script to run
            parameters: Script parameters
            dry_run: If true, validate only
            project_path: Project root where .ai/scripts/ lives (critical for MCP)

        Returns:
            JSON with execution results or validation errors
        """
        script_name = params.get("script_name", "")
        script_params = params.get("parameters", {})
        dry_run = params.get("dry_run", False)
        auto_download = params.get("auto_download", False)
        # Dependencies are always automatically installed - no parameter needed
        project_path = params.get("project_path")  # CRITICAL for MCP servers

        # Re-initialize with project_path if provided
        # This is necessary because __init__ may have been called without project_path
        if project_path:
            self.project_path = Path(project_path)
            self.resolver = ScriptResolver(
                project_root=self.project_path, registry_client=self.registry
            )

        if not script_name:
            return json.dumps({"error": "script_name is required"})

        resolved = await self.resolver.resolve_script(script_name)

        if not resolved["location"]:
            return json.dumps(
                {
                    "error": {
                        "code": "SCRIPT_NOT_FOUND",
                        "message": f"Script '{script_name}' not found in any location",
                        "details": {
                            "script_name": script_name,
                            "suggestion": "Use search({'query': '...'}) to find available scripts",
                        },
                    }
                }
            )

        if resolved["location"] == "registry" and not resolved["path"]:
            if auto_download:
                logger.info(f"Auto-downloading {script_name} from registry...")
                await self._download_script_with_deps(script_name)
                # Re-resolve to get user space path
                resolved = await self.resolver.resolve_script(script_name)
            else:
                return json.dumps(
                    {
                        "error": {
                            "code": "SCRIPT_NOT_FOUND_LOCALLY",
                            "message": f"Script '{script_name}' not found locally",
                            "details": {
                                "script_name": script_name,
                                "suggestion": f"Use load tool first, or set auto_download=true",
                                "load_command": f"load({{'script_name': '{script_name}', 'download_to_user': true}})",
                                "auto_download_command": f"run({{'script_name': '{script_name}', 'auto_download': true, ...}})",
                            },
                        }
                    }
                )

        script = await self.registry.get_script(script_name)

        if script:
            validation = run_preflight(
                inputs=script_params,
                required_credentials=script.get("required_env_vars", []),
                validation_rules=[],
                cost_formula=f"len(script_params.get('{script.get('cost_unit', 'items')}', [])) * {script.get('cost_per_unit', 0)}"
                if script.get("cost_per_unit")
                else None,
            )

            if not validation.get("pass", True):
                return json.dumps(
                    {
                        "status": "validation_failed",
                        "errors": validation.get("blockers", []),
                        "warnings": validation.get("warnings", []),
                    }
                )

        # Verify lib dependencies are available
        if script:
            required_libs = script.get("required_libs", [])
            if required_libs:
                verification = await self._verify_lib_dependencies(script_name, required_libs)
                if verification.get("error"):
                    return json.dumps(verification)

        # Pre-flight pip dependency check
        # Extract dependencies from script file metadata
        script_path = Path(resolved["path"]) if resolved.get("path") else None
        pip_dependencies = []
        if script_path and script_path.exists():
            from ..utils.script_metadata import (
                extract_script_metadata,
                PACKAGE_TO_MODULE,
                MODULE_TO_PACKAGE,
            )

            metadata = extract_script_metadata(script_path)
            pip_dependencies = metadata.get("dependencies", [])
        else:
            # Import MODULE_TO_PACKAGE mapping for registry deps
            from ..utils.script_metadata import MODULE_TO_PACKAGE

        # Also check registry metadata for dependencies
        if script and script.get("dependencies"):
            # Merge with file-extracted dependencies (registry takes precedence)
            registry_deps = script.get("dependencies", [])
            
            try:
                # Validate registry dependencies have correct format
                validated_registry_deps = self._validate_dependencies(registry_deps)
            except ValueError as e:
                return json.dumps({
                    "status": "error",
                    "error": f"Script has corrupted dependency metadata in registry: {str(e)}",
                    "error_type": "metadata_corruption",
                    "suggestion": f"Republish script '{script_name}' to fix corrupted metadata"
                })
            
            existing_names = {d.get("name") for d in pip_dependencies if isinstance(d, dict)}
            
            for dep in validated_registry_deps:
                dep_name = dep.get("name")
                # Apply MODULE_TO_PACKAGE mapping to registry dependencies
                dep_name = MODULE_TO_PACKAGE.get(dep_name, dep_name)
                if dep_name and dep_name not in existing_names:
                    pip_dependencies.append({"name": dep_name, "version": dep.get("version")})

        # Check for missing dependencies and install automatically
        if pip_dependencies:
            missing_deps = self._check_pip_dependencies(pip_dependencies)
            if missing_deps:
                # Automatically install missing dependencies
                logger.info(f"Installing {len(missing_deps)} missing dependencies...")
                install_result = self._install_pip_dependencies(missing_deps)

                if install_result.get("failed"):
                    # Some installations failed
                    return json.dumps(
                        {
                            "status": "error",
                            "error": "Failed to install some dependencies",
                            "error_type": "dependency_error",
                            "details": {
                                "installed": install_result.get("installed", []),
                                "failed": install_result.get("failed", []),
                                "message": "Some dependencies could not be installed automatically.",
                            },
                        }
                    )
                # All installed successfully - continue with execution
                logger.info(f"Successfully installed {len(missing_deps)} dependencies")

        if dry_run:
            return json.dumps(
                {
                    "status": "validation_passed",
                    "message": "Script is ready to execute",
                    "estimated_cost": script.get("estimated_cost_usd") if script else None,
                    "estimated_time": script.get("estimated_time_seconds") if script else None,
                }
            )

        if not resolved.get("path"):
            return json.dumps(
                {
                    "error": {
                        "code": "SCRIPT_NOT_FOUND_LOCALLY",
                        "message": f"Script '{script_name}' not found locally",
                        "details": {
                            "script_name": script_name,
                            "suggestion": f"Use load tool first: load({{'script_name': '{script_name}', 'download_to_user': true}})",
                            "available_in": resolved.get("location", "unknown"),
                        },
                    }
                }
            )

        # Save original params for logging (includes special params)
        original_script_params = script_params.copy()

        # Extract special control parameters (don't pass to script)
        timeout = script_params.pop("_timeout", None)
        stream_logs = script_params.pop(
            "_stream_logs", True
        )  # Default to True for real-time logging
        output_file = script_params.pop("_output_file", None)
        save_output = script_params.pop(
            "_save_output", True
        )  # Default: always save to ~/.script-kiwi/outputs/{script_name}/

        # script_params now has special params removed - use for script execution
        # original_script_params has all params - use for logging

        start_time = time.time()
        execution_id = None

        try:
            execution_id = await self.logger.start_execution(
                script_name=script_name,
                script_version=script.get("version") if script else None,
                params=original_script_params,  # Log with all params (including special ones for debugging)
            )

            # Store execution_id and script_name for streaming logs
            self._current_execution_id = str(execution_id)
            self._current_script_name = script_name

            # Log execution start to user space immediately (for long-running scripts)
            try:
                from ..utils.analytics import log_execution_start

                log_execution_start(
                    script_name=script_name,
                    execution_id=str(execution_id),
                    inputs=original_script_params,  # Log with all params
                    script_version=script.get("version") if script else None,
                    project=str(self.project_path) if self.project_path else str(Path.cwd()),
                )
            except Exception as log_error:
                # Don't fail execution if logging fails
                logger.warning(f"Failed to log execution start: {log_error}")

            # Build execution context with proper import paths
            script_path = Path(resolved["path"])
            storage_location = resolved["location"]  # ✅ Use "location" not "tier"

            # Build sys.path for this execution
            search_paths = self._build_search_paths(script_path, storage_location)

            # Execute with proper import context
            original_path = sys.path.copy()

            try:
                # Add paths in priority order (first = highest priority)
                for path in reversed(search_paths):
                    if str(path) not in sys.path:
                        sys.path.insert(0, str(path))

                # Dynamic import
                spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[script_path.stem] = module
                spec.loader.exec_module(module)

                if hasattr(module, "execute"):
                    # Function-based script - capture stderr in real-time
                    result = self._run_function_script(
                        module.execute,
                        script_params,
                        execution_id=str(execution_id),
                        script_name=script_name,
                        stream_logs=stream_logs,
                    )
                elif hasattr(module, "main"):
                    # Check if main() accepts parameters (not argparse-based)
                    import inspect

                    main_sig = inspect.signature(module.main)
                    if len(main_sig.parameters) > 0:
                        # main() takes parameters - call it directly, capture stderr
                        result = self._run_function_script(
                            module.main,
                            script_params,
                            execution_id=str(execution_id),
                            script_name=script_name,
                            stream_logs=stream_logs,
                        )
                    else:
                        # main() uses argparse - run as subprocess
                        # stream_logs is already set from parameters (defaults to True)
                        result = self._run_argparse_script(
                            script_path,
                            script_params,
                            search_paths,
                            self.project_path,
                            timeout=timeout,
                            stream_logs=stream_logs,
                        )
                else:
                    raise ValueError(f"Script {script_name} has no execute() or main() function")
            finally:
                # Restore sys.path
                sys.path = original_path
                # Clean up module cache
                if script_path.stem in sys.modules:
                    del sys.modules[script_path.stem]
                # Clean up execution tracking
                if hasattr(self, "_current_execution_id"):
                    delattr(self, "_current_execution_id")
                if hasattr(self, "_current_script_name"):
                    delattr(self, "_current_script_name")

            # Extract script status and data first (needed for logging and response)
            script_status = "success"
            script_error = None
            result_data = None

            if result and isinstance(result, dict):
                script_status = result.get("status", "success")

                # If script returned an error, capture it
                if script_status == "error":
                    script_error = result.get("error") or result.get("message") or "Unknown error"
                    # Include all error details in result_data
                    result_data = {
                        k: v for k, v in result.items() if k not in ["status", "metadata"]
                    }
                else:
                    # Success case - extract data
                    result_data = result.get("data")
                    if result_data is None:
                        # If no "data" field but status is success, use the whole result (minus status/metadata)
                        result_data = {
                            k: v
                            for k, v in result.items()
                            if k not in ["status", "metadata", "logs"]
                        }

                    # Debug: Log if result_data is empty but result has content
                    if not result_data:
                        logger.warning(
                            f"Script returned success but result_data is empty. Result keys: {list(result.keys())}"
                        )
                        # Try to extract any data from result
                        if "businesses" in result:
                            result_data = {"businesses": result["businesses"]}
                            logger.info(
                                f"Found businesses directly in result: {len(result.get('businesses', []))}"
                            )
                        elif any(key in result for key in ["items", "results", "data"]):
                            # Try other common data fields
                            for key in ["items", "results", "data"]:
                                if key in result:
                                    result_data = {key: result[key]}
                                    logger.info(f"Found {key} directly in result")
                                    break
            else:
                if result:
                    logger.warning(f"Result is not a dict: {type(result)}")

            # Calculate duration if not provided
            if result and isinstance(result, dict):
                duration_sec = result.get("metadata", {}).get("duration_sec")
                if duration_sec is None:
                    duration_sec = time.time() - start_time
                cost_usd = result.get("metadata", {}).get("cost_usd", 0) or 0
                rows_processed = result.get("metadata", {}).get("rows_processed")
                api_calls_made = result.get("metadata", {}).get("api_calls_made")
            else:
                # Result is None or not a dict - use defaults
                duration_sec = time.time() - start_time
                cost_usd = 0
                rows_processed = None
                api_calls_made = None

            log_result = None
            try:
                log_result = log_execution(
                    script_name=script_name,
                    status=script_status,
                    duration_sec=duration_sec,
                    inputs=original_script_params,  # Log with all params
                    outputs=result.get("data") if result else None,
                    cost_usd=cost_usd,
                    script_version=script.get("version") if script else None,
                    rows_processed=rows_processed,
                    api_calls_made=api_calls_made,
                    project=str(self.project_path) if self.project_path else str(Path.cwd()),
                    execution_id=str(execution_id),
                )
            except Exception as log_error:
                logger.warning(f"Failed to log execution completion: {log_error}")

            await self.logger.complete_execution(
                execution_id=execution_id,
                status=script_status,
                result={
                    "data": result.get("data") if result else None,
                    "metadata": result.get("metadata", {}) if result else {},
                },
                duration_sec=duration_sec,
                cost_usd=cost_usd,
            )

            # Check if result is too large and should be written to file
            result_size_bytes = len(json.dumps(result_data, default=str))

            # Determine if we should write to file
            # Default: always save to ~/.script-kiwi/outputs/{script_name}/ unless explicitly disabled
            should_write_file = False
            is_auto_save = False  # Track if this is an auto-save due to size

            if output_file:
                # Explicit output_file path provided - always use it
                should_write_file = True
            elif save_output and result_data is not None:
                # Default: save by default (save_output=True by default)
                should_write_file = True
            elif result_size_bytes > MAX_RESPONSE_SIZE_BYTES:
                # Auto-save if result is too large (even if save_output=False)
                should_write_file = True
                is_auto_save = True

            output_path = None  # Track output path for metadata

            if should_write_file:
                # Write full results to file
                if not output_file:
                    # Auto-generate filename in script-specific folder
                    timestamp = int(time.time())
                    if is_auto_save:
                        # Auto-save due to size - use tmp folder in script-kiwi home
                        from ..utils.analytics import _get_script_kiwi_home

                        script_kiwi_home = _get_script_kiwi_home()
                        output_path = (
                            script_kiwi_home / "tmp" / f"{script_name}_{timestamp}_results.json"
                        )
                    else:
                        # Default: ~/.script-kiwi/outputs/{script_name}/{timestamp}_results.json
                        from ..utils.analytics import _get_script_kiwi_home

                        script_kiwi_home = _get_script_kiwi_home()
                        output_path = (
                            script_kiwi_home / "outputs" / script_name / f"{timestamp}_results.json"
                        )
                else:
                    # User provided output_file - resolve it
                    output_path = Path(output_file)
                    if not output_path.is_absolute():
                        # Resolve relative to project_path if available, otherwise use current working directory
                        if self.project_path:
                            output_path = self.project_path / output_path
                        else:
                            # Fall back to current working directory for relative paths
                            output_path = Path.cwd() / output_path
                    else:
                        # Absolute path - use as-is
                        output_path = Path(output_file).expanduser()

                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Keep original data before we replace result_data with summary
                original_data = result_data

                # Write full original data to file
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(original_data, f, indent=2, default=str)

                # Build file info
                file_info = {
                    "_output_file": str(output_path),
                    "_file_size_bytes": result_size_bytes,
                    "_message": f"Results written to file ({result_size_bytes:,} bytes). Full data available at: {output_path}",
                    "_summary": _create_result_summary(original_data),
                }

                # If data is small enough, include data + file info
                # If data is too large, replace with file info only
                if result_size_bytes <= MAX_RESPONSE_SIZE_BYTES:
                    # Keep original data but add file info
                    if isinstance(original_data, dict):
                        result_data = {**original_data, **file_info}
                    else:
                        result_data = {"_data": original_data, **file_info}
                else:
                    # Too large - replace with file info only
                    result_data = file_info
                    # Include a preview
                    if original_data:
                        preview = original_data.copy()
                        if isinstance(preview, dict):
                            for key, value in preview.items():
                                if isinstance(value, list) and len(value) > 5:
                                    preview[key] = value[:5] + [
                                        f"... ({len(value) - 5} more items)"
                                    ]
                                elif isinstance(value, dict) and len(value) > 10:
                                    items = list(value.items())[:10]
                                    preview[key] = dict(items)
                                    preview[key]["_truncated"] = (
                                        f"... ({len(value) - 10} more keys)"
                                    )
                        result_data["_preview"] = preview

            # Build response with always-useful fields
            execution_id_for_response = None
            if log_result and isinstance(log_result, dict):
                execution_id_for_response = log_result.get("execution_id")
            if not execution_id_for_response and execution_id:
                execution_id_for_response = str(execution_id)

            response = {
                "status": script_status,  # Pass through script's actual status
                "execution_id": execution_id_for_response,
                "result": result_data or {},
                "metadata": {
                    "duration_sec": round(duration_sec, 3),
                    "cost_usd": round(cost_usd, 4),
                },
            }

            # Include error details if script returned an error
            if script_error:
                response["error"] = script_error

            # If output was saved to file, include the path in metadata for easy access
            if output_path:
                response["metadata"]["output_file"] = str(output_path)
                response["metadata"]["output_saved"] = True

            # Debug: If result_data is empty, log warning with result structure
            if not result_data and result and isinstance(result, dict):
                logger.warning(f"result_data is empty but result has keys: {list(result.keys())}")
                # Try to include result structure in response for debugging
                response["_debug"] = {
                    "result_keys": list(result.keys()),
                    "result_status": result.get("status"),
                    "result_has_data": "data" in result,
                    "result_data_type": type(result.get("data")).__name__
                    if result.get("data")
                    else None,
                }

            # Add optional metadata fields if present
            if rows_processed is not None:
                response["metadata"]["rows_processed"] = rows_processed
            if api_calls_made is not None:
                response["metadata"]["api_calls_made"] = api_calls_made

            # Include logs if present (from subprocess stderr)
            if result and isinstance(result, dict) and result.get("logs"):
                response["logs"] = result.get("logs")

            # Include debug info if result data is empty (helps diagnose issues)
            if (
                not result_data
                and result
                and isinstance(result, dict)
                and result.get("status") == "success"
            ):
                response["_debug"] = {
                    "message": "Script completed successfully but returned empty data",
                    "raw_result_keys": list(result.keys())
                    if isinstance(result, dict)
                    else "not_a_dict",
                    "has_logs": bool(result.get("logs")),
                    "log_count": len(result.get("logs", [])),
                    "suggestion": "Check logs field for warnings or errors from the script",
                }

            return json.dumps(response, indent=2)

        except (ModuleNotFoundError, ImportError) as e:
            # Dependency error - this means an undeclared dependency
            missing_module = None
            error_str = str(e)
            match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_str)
            if match:
                missing_module = match.group(1)

            duration_sec = time.time() - start_time
            package_guess = missing_module.replace("_", "-") if missing_module else "PACKAGE"

            return json.dumps(
                {
                    "status": "error",
                    "error": f"Missing dependency: {missing_module or 'unknown'}",
                    "error_type": "dependency_error",
                    "missing_module": missing_module,
                    "suggestion": f"This dependency was not declared. Add to script or install: pip install {package_guess}",
                    "data": None,
                    "metadata": {"duration_sec": round(duration_sec, 3), "cost_usd": 0},
                },
                indent=2,
            )
        except Exception as e:
            error_traceback = traceback.format_exc()
            duration_sec = time.time() - start_time

            log_result = log_execution(
                script_name=script_name,
                status="error",
                duration_sec=duration_sec,
                inputs=original_script_params,  # Log with all params
                error=str(e),
                script_version=script.get("version") if script else None,
                project=str(self.project_path) if self.project_path else str(Path.cwd()),
                execution_id=str(execution_id) if execution_id else None,
            )

            await self.logger.complete_execution(
                execution_id=execution_id, status="error", error=str(e), duration_sec=duration_sec
            )

            # Build error response with always-useful information
            execution_id_for_response = None
            if log_result and isinstance(log_result, dict):
                execution_id_for_response = log_result.get("execution_id")
            if not execution_id_for_response and execution_id:
                execution_id_for_response = str(execution_id)

            error_response = {
                "status": "error",
                "execution_id": execution_id_for_response,
                "error": str(e),
                "error_type": type(e).__name__,
                "metadata": {"duration_sec": round(duration_sec, 3), "cost_usd": 0},
                "troubleshooting": [
                    "Check error message above",
                    "Verify all required environment variables are set",
                    "Use help() tool for guidance",
                    f"Script: {script_name}",
                    f"Project: {str(self.project_path) if self.project_path else 'N/A'}",
                ],
            }

            # Include traceback for debugging (but make it optional/truncated for large errors)
            if len(error_traceback) < 2000:
                error_response["traceback"] = error_traceback
            else:
                error_response["traceback"] = error_traceback[:2000] + "\n... (truncated)"

            return json.dumps(error_response, indent=2)
