"""
Script Resolution Logic

Implements 3-tier storage system: Project → User → Registry
with lockfile support for version pinning.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import json
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()


class ScriptResolver:
    """Resolve scripts from 3-tier storage system."""
    
    def __init__(
        self,
        project_root: Optional[Path] = None,
        user_home: Optional[Path] = None,
        registry_client=None
    ):
        # Determine project root: explicit > env var > find .ai/scripts > cwd
        if project_root:
            self.project_root = Path(project_root)
        elif os.getenv("SCRIPT_KIWI_HOME"):
            # SCRIPT_KIWI_HOME points to ~/.script-kiwi, but we need project root
            # Try to find project root by looking for .ai/scripts
            potential_root = self._find_project_root()
            self.project_root = potential_root if potential_root else Path.cwd()
        else:
            # Try to find project root by looking for .ai/scripts directory
            potential_root = self._find_project_root()
            self.project_root = potential_root if potential_root else Path.cwd()
        
        self.user_home = user_home or Path.home()
        
        # Get script-kiwi home from env var or default
        script_kiwi_home = os.getenv("SCRIPT_KIWI_HOME")
        if script_kiwi_home:
            self.script_kiwi_home = Path(script_kiwi_home)
        else:
            self.script_kiwi_home = self.user_home / ".script-kiwi"
        
        # Storage tier paths
        self.project_scripts = self.project_root / ".ai" / "scripts"
        self.user_scripts = self.script_kiwi_home / "scripts"
        
        # Registry client (optional, will be created if needed)
        self.registry_client = registry_client
    
    def _find_project_root(self) -> Optional[Path]:
        """
        Find project root by looking for .ai/scripts directory.
        Searches from current directory up to filesystem root.
        """
        current = Path.cwd()
        max_depth = 10  # Prevent infinite loops
        depth = 0
        
        while depth < max_depth:
            ai_scripts = current / ".ai" / "scripts"
            if ai_scripts.exists() and ai_scripts.is_dir():
                return current
            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent
            depth += 1
        
        return None
    
    async def resolve_script(
        self,
        script_name: str,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolve script location in priority order: Project → User → Registry
        
        Returns:
            {
                "location": "project" | "user" | "registry" | None,
                "path": Path | None,
                "version": str | None,
                "lockfile_version": str | None,
                "registry_data": Dict | None
            }
        """
        # Check lockfile first
        lockfile_version = self._get_lockfile_version(script_name)
        
        # 1. Check project space (highest priority)
        project_path = self._check_project_space(script_name, category)
        if project_path and project_path.exists():
            # Extract category and subcategory from path if not provided
            detected_category = category or self._extract_category_from_path(project_path)
            detected_subcategory = self._extract_subcategory_from_path(project_path)
            return {
                "location": "project",
                "path": project_path,
                "category": detected_category,
                "subcategory": detected_subcategory,
                "version": None,  # Local files don't have versions
                "lockfile_version": lockfile_version
            }
        
        # 2. Check user space
        user_path = self._check_user_space(script_name, category)
        if user_path and user_path.exists():
            # Extract category and subcategory from path if not provided
            detected_category = category or self._extract_category_from_path(user_path)
            detected_subcategory = self._extract_subcategory_from_path(user_path)
            return {
                "location": "user",
                "path": user_path,
                "category": detected_category,
                "subcategory": detected_subcategory,
                "version": None,  # Local files don't have versions
                "lockfile_version": lockfile_version
            }
        
        # 3. Check registry (requires Supabase)
        registry_script = await self._check_registry(script_name, lockfile_version)
        if registry_script:
            return {
                "location": "registry",
                "path": None,  # Registry scripts need to be downloaded
                "category": registry_script.get("category"),
                "subcategory": registry_script.get("subcategory"),
                "version": registry_script.get("version"),
                "lockfile_version": lockfile_version,
                "registry_data": registry_script
            }
        
        return {
            "location": None,
            "path": None,
            "version": None,
            "lockfile_version": lockfile_version
        }
    
    def _check_project_space(
        self,
        script_name: str,
        category: Optional[str] = None
    ) -> Optional[Path]:
        """
        Check project space for script.
        Supports nested directories (subcategories).
        
        Examples:
            .ai/scripts/scraping/script.py
            .ai/scripts/scraping/google-maps/script.py
        """
        if category:
            # Try direct path first
            direct_path = self.project_scripts / category / f"{script_name}.py"
            if direct_path.exists():
                return direct_path
            
            # Try nested subdirectories
            cat_dir = self.project_scripts / category
            if cat_dir.exists():
                for subdir in cat_dir.rglob(f"{script_name}.py"):
                    if subdir.is_file():
                        return subdir
        else:
            # Search all categories recursively
            if not self.project_scripts.exists():
                return None
            for script_path in self.project_scripts.rglob(f"{script_name}.py"):
                if script_path.is_file():
                        return script_path
        return None
    
    def _check_user_space(
        self,
        script_name: str,
        category: Optional[str] = None
    ) -> Optional[Path]:
        """
        Check user space for script.
        Supports nested directories (subcategories).
        
        Examples:
            ~/.script-kiwi/scripts/scraping/script.py
            ~/.script-kiwi/scripts/scraping/google-maps/script.py
        """
        if category:
            # Try direct path first
            direct_path = self.user_scripts / category / f"{script_name}.py"
            if direct_path.exists():
                return direct_path
            
            # Try nested subdirectories
            cat_dir = self.user_scripts / category
            if cat_dir.exists():
                for subdir in cat_dir.rglob(f"{script_name}.py"):
                    if subdir.is_file():
                        return subdir
        else:
            # Search all categories recursively
            if not self.user_scripts.exists():
                return None
            for script_path in self.user_scripts.rglob(f"{script_name}.py"):
                if script_path.is_file():
                        return script_path
        return None
    
    def _extract_category_from_path(self, script_path: Path) -> str:
        """
        Extract category from script path.
        Supports nested directories for subcategories.
        
        Examples:
            .ai/scripts/scraping/example.py → "scraping"
            .ai/scripts/scraping/google-maps/example.py → "scraping"
            .ai/scripts/data-processing/api-integration/example.py → "data-processing"
        """
        script_path = Path(script_path)
        
        # Find the scripts directory in the path
        path_str = str(script_path)
        if ".ai/scripts" in path_str:
            # Extract path after .ai/scripts
            scripts_idx = path_str.find(".ai/scripts")
            scripts_path = Path(path_str[:scripts_idx + len(".ai/scripts")])
            try:
                relative = script_path.relative_to(scripts_path)
            except ValueError:
                # Fallback: use parent directory name
                return script_path.parent.name
        elif ".script-kiwi/scripts" in path_str:
            # Extract path after .script-kiwi/scripts
            scripts_idx = path_str.find(".script-kiwi/scripts")
            scripts_path = Path(path_str[:scripts_idx + len(".script-kiwi/scripts")])
            try:
                relative = script_path.relative_to(scripts_path)
            except ValueError:
                # Fallback: use parent directory name
                return script_path.parent.name
        else:
            # Try to find scripts directory by walking up
            current = script_path.parent
            while current != current.parent:
                if current.name == "scripts":
                    try:
                        relative = script_path.relative_to(current)
                        break
                    except ValueError:
                        pass
                current = current.parent
            else:
                # Fallback: use parent directory name
                return script_path.parent.name
        
        # Get category (first directory)
        parts = relative.parts
        if len(parts) > 0:
            # Category is the first directory
            return parts[0]
        else:
            # Fallback to parent directory name
            return script_path.parent.name
    
    def _extract_subcategory_from_path(self, script_path: Path) -> Optional[str]:
        """
        Extract subcategory from script path.
        
        Examples:
            .ai/scripts/scraping/example.py → None
            .ai/scripts/scraping/google-maps/example.py → "google-maps"
            .ai/scripts/data-processing/api-integration/example.py → "api-integration"
        """
        script_path = Path(script_path)
        
        # Find the scripts directory in the path
        path_str = str(script_path)
        if ".ai/scripts" in path_str:
            scripts_idx = path_str.find(".ai/scripts")
            scripts_path = Path(path_str[:scripts_idx + len(".ai/scripts")])
            try:
                relative = script_path.relative_to(scripts_path)
            except ValueError:
                return None
        elif ".script-kiwi/scripts" in path_str:
            scripts_idx = path_str.find(".script-kiwi/scripts")
            scripts_path = Path(path_str[:scripts_idx + len(".script-kiwi/scripts")])
            try:
                relative = script_path.relative_to(scripts_path)
            except ValueError:
                return None
        else:
            current = script_path.parent
            while current != current.parent:
                if current.name == "scripts":
                    try:
                        relative = script_path.relative_to(current)
                        break
                    except ValueError:
                        pass
                current = current.parent
            else:
                return None
        
        # Get subcategory (second directory, if exists)
        # relative.parts structure: (category, subcategory, filename.py) or (category, filename.py)
        parts = relative.parts
        if len(parts) >= 3:
            # Has subcategory: category/subcategory/filename.py
            # parts[0] is category, parts[1] is subcategory, parts[2] is filename
            return parts[1]
        elif len(parts) == 2:
            # Only category/filename.py - no subcategory
            # Check if parts[1] is actually a directory (not .py file)
            if not parts[1].endswith('.py'):
                # It's a directory, so it's a subcategory
                return parts[1]
            # It's a .py file, so no subcategory
            return None
        # Only filename or empty
        return None
    
    async def _check_registry(
        self,
        script_name: str,
        lockfile_version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check registry for script.
        
        Args:
            script_name: Name of script to find
            lockfile_version: Optional version from lockfile (if set, use this version)
        
        Returns:
            Script data from registry, or None if not found
        """
        # Lazy import to avoid circular dependency
        if self.registry_client is None:
            from ..api.script_registry import ScriptRegistry
            self.registry_client = ScriptRegistry()
        
        # If no Supabase client available, return None
        if not self.registry_client.client:
            return None
        
        try:
            # Get script from registry
            script = await self.registry_client.get_script(
                script_name=script_name,
                version=lockfile_version
            )
            
            if script:
                return {
                    "name": script.get("name"),
                    "category": script.get("category"),
                    "subcategory": script.get("subcategory"),
                    "version": script.get("version"),
                    "content": script.get("content"),
                    "content_hash": script.get("content_hash"),
                    "module_path": script.get("module_path"),
                    "description": script.get("description"),
                    "dependencies": script.get("dependencies", []),
                    "required_env_vars": script.get("required_env_vars", []),
                    "required_libs": script.get("required_libs", []),
                    "changelog": script.get("changelog")
                }
            
            return None
        except Exception as e:
            # Log error but don't fail - registry might be unavailable
            print(f"Error checking registry for script '{script_name}': {e}")
            return None
    
    def _get_lockfile_version(self, script_name: str) -> Optional[str]:
        """Get version from lockfile if exists."""
        lockfile_path = self.project_root / ".ai" / "scripts.lock.json"
        
        if not lockfile_path.exists():
            # Check user lockfile
            lockfile_path = self.user_home / ".script-kiwi" / "scripts.lock.json"
            if not lockfile_path.exists():
                return None
        
        try:
            with open(lockfile_path, 'r') as f:
                lockfile = json.load(f)
            
            scripts = lockfile.get("scripts", {})
            return scripts.get(script_name)
        except Exception:
            return None
    
    def download_to_user_space(
        self,
        script_name: str,
        category: str,
        content: str,
        subcategory: Optional[str] = None
    ) -> Path:
        """
        Download script from registry to user space.
        Supports nested directories for subcategories.
        
        Examples:
            category="scraping" → ~/.script-kiwi/scripts/scraping/script.py
            category="scraping", subcategory="google-maps" → ~/.script-kiwi/scripts/scraping/google-maps/script.py
        """
        if subcategory:
            user_path = self.user_scripts / category / subcategory / f"{script_name}.py"
        else:
            user_path = self.user_scripts / category / f"{script_name}.py"
        
        user_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(user_path, 'w') as f:
            f.write(content)
        
        return user_path
    
    def calculate_project_hash(self) -> str:
        """
        Calculate project hash from .ai/directives/custom/ directory.
        Used for grouping lockfiles per project.
        """
        directives_dir = self.project_root / ".ai" / "directives" / "custom"
        
        if not directives_dir.exists():
            return "default"
        
        # Hash of sorted file paths + content hashes
        file_hashes = []
        for file_path in sorted(directives_dir.glob("*.md")):
            with open(file_path, 'rb') as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()
                file_hashes.append(f"{file_path.name}:{content_hash}")
        
        combined = "\n".join(file_hashes)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

