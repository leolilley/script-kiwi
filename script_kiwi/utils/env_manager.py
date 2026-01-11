"""
Environment Manager for Script Kiwi

Manages virtual environments for script execution:
- Project-level: .ai/scripts/.venv/ (when project_path provided)
- User-level: ~/.script-kiwi/.venv/ (default fallback)

This ensures scripts run in isolated environments with their own dependencies,
similar to how Context Kiwi handles project vs user directives.
"""

import os
import sys
import subprocess
import logging
import fcntl
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class EnvManager:
    """Manages virtual environments for script execution."""

    def __init__(self, project_path: Optional[Path] = None):
        """
        Initialize environment manager.

        Args:
            project_path: If provided, use project-level venv at .ai/scripts/.venv/
                         Otherwise, use user-level venv at ~/.script-kiwi/.venv/
        """
        self.project_path = Path(project_path) if project_path else None

        # Determine script-kiwi home
        script_kiwi_home_env = os.getenv("SCRIPT_KIWI_HOME")
        if script_kiwi_home_env:
            self.script_kiwi_home = Path(script_kiwi_home_env)
        else:
            self.script_kiwi_home = Path.home() / ".script-kiwi"

        # Determine environment root based on project_path
        if self.project_path:
            # Project-level env at .ai/scripts/.venv
            self.env_root = self.project_path / ".ai" / "scripts"
            self.env_type = "project"
        else:
            # User-level env at ~/.script-kiwi/.venv
            self.env_root = self.script_kiwi_home
            self.env_type = "user"

        self.venv_dir = self.env_root / ".venv"
        self._lock_file: Optional[int] = None

    def _acquire_lock(self) -> bool:
        """
        Acquire a file lock to prevent concurrent venv operations.

        Returns:
            True if lock acquired, False otherwise
        """
        lock_path = self.venv_dir.parent / ".venv.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._lock_file = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, BlockingIOError):
            if self._lock_file is not None:
                os.close(self._lock_file)
                self._lock_file = None
            return False

    def _release_lock(self) -> None:
        """Release the file lock."""
        if self._lock_file is not None:
            try:
                fcntl.flock(self._lock_file, fcntl.LOCK_UN)
                os.close(self._lock_file)
            except OSError:
                pass
            finally:
                self._lock_file = None

    def ensure_venv(self) -> Path:
        """
        Create venv lazily if it doesn't exist.

        Returns:
            Path to the venv directory
        """
        if self.venv_dir.exists() and (self.venv_dir / "bin" / "python").exists():
            return self.venv_dir

        # Try to acquire lock for venv creation
        lock_acquired = self._acquire_lock()
        try:
            # Double-check after acquiring lock (another process may have created it)
            if self.venv_dir.exists() and (self.venv_dir / "bin" / "python").exists():
                return self.venv_dir

            logger.info(f"Creating {self.env_type} venv at {self.venv_dir}")
            self.venv_dir.parent.mkdir(parents=True, exist_ok=True)

            # Create venv using current Python
            result = subprocess.run(
                [sys.executable, "-m", "venv", str(self.venv_dir)],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"Failed to create venv: {result.stderr or result.stdout}"
                )

            # Upgrade pip in the new venv (helps avoid issues with old pip)
            # Use _get_python_path directly to avoid recursion
            venv_python = self._get_python_path()
            pip_upgrade = subprocess.run(
                [venv_python, "-m", "pip", "install", "--upgrade", "pip"],
                capture_output=True,
                text=True,
            )
            if pip_upgrade.returncode != 0:
                logger.warning(f"Failed to upgrade pip: {pip_upgrade.stderr}")

            logger.info(f"Created {self.env_type} venv at {self.venv_dir}")
            return self.venv_dir
        finally:
            if lock_acquired:
                self._release_lock()

    def _get_python_path(self) -> str:
        """
        Get path to the venv's Python executable without ensuring venv exists.
        Internal helper to avoid recursion in ensure_venv.
        """
        if os.name == "nt":
            return str(self.venv_dir / "Scripts" / "python.exe")
        else:
            return str(self.venv_dir / "bin" / "python")

    def get_python(self) -> str:
        """
        Get path to the venv's Python executable.
        Ensures the venv exists first.

        Returns:
            Absolute path to python executable in the venv
        """
        self.ensure_venv()
        return self._get_python_path()

    def get_pip(self) -> str:
        """
        Get path to the venv's pip executable.

        Returns:
            Absolute path to pip executable in the venv
        """
        venv = self.ensure_venv()
        if os.name == "nt":
            return str(venv / "Scripts" / "pip.exe")
        else:
            return str(venv / "bin" / "pip")

    def build_subprocess_env(self, search_paths: list[Path]) -> dict[str, str]:
        """
        Build environment variables for subprocess execution.

        Sets up PYTHONPATH, PATH, and VIRTUAL_ENV so scripts run in the venv
        with access to lib/ directories from both project and user space.

        Args:
            search_paths: List of paths to add to PYTHONPATH (from _build_search_paths)

        Returns:
            Environment dict for subprocess.run()
        """
        env = dict(os.environ)

        # Build PYTHONPATH from search paths
        pythonpath_parts = [str(p.absolute()) for p in search_paths if p.exists()]
        if env.get("PYTHONPATH"):
            pythonpath_parts.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

        # Activate venv for subprocess
        venv = self.ensure_venv()
        bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
        env["VIRTUAL_ENV"] = str(venv)

        # Remove PYTHONHOME if set (can interfere with venv)
        env.pop("PYTHONHOME", None)

        return env

    def install_packages(
        self, packages: list[dict[str, str]], timeout: int = 300
    ) -> dict[str, any]:
        """
        Install pip packages into the venv.

        Args:
            packages: List of dicts with 'name' and optional 'version' keys
            timeout: Timeout in seconds for each install

        Returns:
            Dict with 'installed', 'failed', and 'status' keys
        """
        if not packages:
            return {"status": "success", "installed": [], "failed": []}

        python = self.get_python()
        installed = []
        failed = []

        for pkg in packages:
            pkg_name = pkg.get("name")
            pkg_version = pkg.get("version")

            if not pkg_name:
                continue

            try:
                # Build package spec
                if pkg_version:
                    # Handle version specs like ">=1.0.0" or "==2.0"
                    if pkg_version.startswith((">=", "<=", "==", "~=", "!=")):
                        package_spec = f"{pkg_name}{pkg_version}"
                    else:
                        package_spec = f"{pkg_name}=={pkg_version}"
                else:
                    package_spec = pkg_name

                logger.info(f"Installing {package_spec} into {self.env_type} venv")

                result = subprocess.run(
                    [python, "-m", "pip", "install", package_spec],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if result.returncode == 0:
                    installed.append({"name": pkg_name, "version": pkg_version})
                    logger.info(f"Installed: {package_spec}")
                else:
                    error_msg = result.stderr[:500] if result.stderr else "Unknown error"
                    failed.append({"name": pkg_name, "error": error_msg})
                    logger.warning(f"Failed to install {package_spec}: {error_msg}")

            except subprocess.TimeoutExpired:
                failed.append({"name": pkg_name, "error": "Installation timed out"})
                logger.warning(f"Timeout installing {pkg_name}")
            except Exception as e:
                failed.append({"name": pkg_name, "error": str(e)})
                logger.warning(f"Error installing {pkg_name}: {e}")

        if failed:
            status = "partial" if installed else "error"
        else:
            status = "success"

        return {"status": status, "installed": installed, "failed": failed}

    def check_packages(self, packages: list[dict[str, str]]) -> list[dict[str, any]]:
        """
        Check which packages are missing from the venv.

        Runs import checks in the venv's Python to get accurate results.

        Args:
            packages: List of dicts with 'name' and optional 'version' keys

        Returns:
            List of missing packages with install commands
        """
        if not packages:
            return []

        # Import the package-to-module mapping
        from .script_metadata import PACKAGE_TO_MODULE

        # Internal modules to skip
        internal_prefixes = ("lib", "lib.")

        # Build a script to check imports in the venv
        check_script = """
import sys
import json

packages = json.loads(sys.argv[1])
missing = []

for pkg in packages:
    name = pkg.get('name', '')
    module = pkg.get('module', name.replace('-', '_'))
    try:
        __import__(module)
    except ImportError:
        # Also try original name
        try:
            __import__(name)
        except ImportError:
            missing.append(name)

print(json.dumps(missing))
"""

        # Prepare package list with module names
        packages_with_modules = []
        for pkg in packages:
            pkg_name = pkg.get("name") if isinstance(pkg, dict) else str(pkg)

            # Skip internal lib modules
            if pkg_name.startswith(internal_prefixes):
                continue

            module_name = PACKAGE_TO_MODULE.get(pkg_name, pkg_name.replace("-", "_"))
            packages_with_modules.append({"name": pkg_name, "module": module_name})

        if not packages_with_modules:
            return []

        import json

        python = self.get_python()

        try:
            result = subprocess.run(
                [python, "-c", check_script, json.dumps(packages_with_modules)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                missing_names = json.loads(result.stdout.strip())
            else:
                # Fallback: assume all are missing if check fails
                logger.warning(f"Import check failed: {result.stderr}")
                missing_names = [p["name"] for p in packages_with_modules]
        except Exception as e:
            logger.warning(f"Error checking packages: {e}")
            missing_names = [p["name"] for p in packages_with_modules]

        # Build missing packages list with install commands
        missing = []
        pkg_lookup = {p.get("name"): p for p in packages if isinstance(p, dict)}

        for name in missing_names:
            pkg = pkg_lookup.get(name, {"name": name})
            version = pkg.get("version")
            install_cmd = (
                f"pip install '{name}{version}'" if version else f"pip install '{name}'"
            )
            missing.append(
                {
                    "name": name,
                    "version": version,
                    "install_cmd": install_cmd,
                }
            )

        return missing

    def get_info(self) -> dict[str, any]:
        """
        Get information about the current environment.

        Returns:
            Dict with env_type, venv_dir, exists, python_path
        """
        exists = self.venv_dir.exists() and (self.venv_dir / "bin" / "python").exists()
        return {
            "env_type": self.env_type,
            "venv_dir": str(self.venv_dir),
            "exists": exists,
            "python_path": self.get_python() if exists else None,
            "project_path": str(self.project_path) if self.project_path else None,
        }
