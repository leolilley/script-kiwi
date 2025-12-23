"""Remove tool for Script Kiwi."""

from typing import Dict, Any, List, Optional
import json
import logging
from pathlib import Path
from ..api.script_registry import ScriptRegistry
from ..utils.script_resolver import ScriptResolver

logger = logging.getLogger(__name__)


class RemoveTool:
    """Remove scripts from project, user, or registry storage"""
    
    def __init__(self):
        self.registry = ScriptRegistry()
        self.resolver = ScriptResolver(registry_client=self.registry)
    
    async def _remove_from_project(
        self,
        script_name: str,
        category: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Remove script from project space."""
        project_scripts = self.resolver.project_scripts
        
        # Try to find script in project space
        if category:
            script_path = project_scripts / category / f"{script_name}.py"
        else:
            # Search all categories
            script_path = None
            for cat_dir in project_scripts.iterdir():
                if cat_dir.is_dir():
                    potential_path = cat_dir / f"{script_name}.py"
                    if potential_path.exists():
                        script_path = potential_path
                        category = cat_dir.name
                        break
        
        if not script_path or not script_path.exists():
            return {
                "removed": False,
                "reason": "Script not found in project space"
            }
        
        if dry_run:
            return {
                "removed": False,
                "dry_run": True,
                "would_remove": True,
                "path": str(script_path),
                "category": category
            }
        
        try:
            script_path.unlink()
            logger.info(f"Removed script from project: {script_path}")
            
            return {
                "removed": True,
                "path": str(script_path),
                "category": category
            }
        except Exception as e:
            logger.error(f"Failed to remove script from project: {e}")
            return {
                "removed": False,
                "error": str(e)
            }
    
    async def _remove_from_user(
        self,
        script_name: str,
        category: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Remove script from user space."""
        user_scripts = self.resolver.user_scripts
        
        # Try to find script in user space
        if category:
            script_path = user_scripts / category / f"{script_name}.py"
        else:
            # Search all categories
            script_path = None
            for cat_dir in user_scripts.iterdir():
                if cat_dir.is_dir():
                    potential_path = cat_dir / f"{script_name}.py"
                    if potential_path.exists():
                        script_path = potential_path
                        category = cat_dir.name
                        break
        
        if not script_path or not script_path.exists():
            return {
                "removed": False,
                "reason": "Script not found in user space"
            }
        
        if dry_run:
            return {
                "removed": False,
                "dry_run": True,
                "would_remove": True,
                "path": str(script_path),
                "category": category
            }
        
        try:
            script_path.unlink()
            logger.info(f"Removed script from user space: {script_path}")
            
            return {
                "removed": True,
                "path": str(script_path),
                "category": category
            }
        except Exception as e:
            logger.error(f"Failed to remove script from user space: {e}")
            return {
                "removed": False,
                "error": str(e)
            }
    
    async def _remove_lib_from_project(self, lib_name: str) -> Dict[str, Any]:
        """Remove lib script from project space."""
        lib_path = self.resolver.project_scripts / "lib" / f"{lib_name}.py"
        
        if not lib_path.exists():
            return {
                "removed": False,
                "reason": "Lib not found in project space"
            }
        
        try:
            lib_path.unlink()
            logger.info(f"Removed lib from project: {lib_path}")
            return {
                "removed": True,
                "path": str(lib_path)
            }
        except Exception as e:
            logger.error(f"Failed to remove lib from project: {e}")
            return {
                "removed": False,
                "error": str(e)
            }
    
    async def _remove_lib_from_user(self, lib_name: str) -> Dict[str, Any]:
        """Remove lib script from user space."""
        lib_path = self.resolver.user_scripts / "lib" / f"{lib_name}.py"
        
        if not lib_path.exists():
            return {
                "removed": False,
                "reason": "Lib not found in user space"
            }
        
        try:
            lib_path.unlink()
            logger.info(f"Removed lib from user space: {lib_path}")
            return {
                "removed": True,
                "path": str(lib_path)
            }
        except Exception as e:
            logger.error(f"Failed to remove lib from user space: {e}")
            return {
                "removed": False,
                "error": str(e)
            }
    
    async def _check_dependencies(
        self,
        script_name: str,
        tier: str
    ) -> Dict[str, Any]:
        """Check if any scripts depend on the target script."""
        dependent_scripts = []
        
        # Check registry for dependencies
        if self.registry.client:
            try:
                # Search for scripts that have this script in required_scripts or required_libs
                scripts_result = self.registry.client.table("scripts").select(
                    "name, required_scripts, required_libs"
                ).execute()
                
                for script in scripts_result.data or []:
                    required_scripts = script.get("required_scripts", []) or []
                    required_libs = script.get("required_libs", []) or []
                    
                    if script_name in required_scripts:
                        dependent_scripts.append({
                            "name": script["name"],
                            "tier": "registry",
                            "type": "script",
                            "dependency_type": "required_scripts"
                        })
                    if script_name in required_libs:
                        dependent_scripts.append({
                            "name": script["name"],
                            "tier": "registry",
                            "type": "lib",
                            "dependency_type": "required_libs"
                        })
            except Exception as e:
                logger.warning(f"Error checking registry dependencies: {e}")
        
        # Check project space
        project_scripts = self.resolver.project_scripts
        if project_scripts.exists():
            for cat_dir in project_scripts.iterdir():
                if cat_dir.is_dir() and cat_dir.name != "lib":
                    for script_file in cat_dir.glob("*.py"):
                        try:
                            content = script_file.read_text()
                            # Simple heuristic: check if script_name is imported
                            if f"from lib.{script_name}" in content or f"import {script_name}" in content:
                                dependent_scripts.append({
                                    "name": script_file.stem,
                                    "tier": "project",
                                    "type": "script",
                                    "dependency_type": "import"
                                })
                        except Exception:
                            pass
        
        # Check user space
        user_scripts = self.resolver.user_scripts
        if user_scripts.exists():
            for cat_dir in user_scripts.iterdir():
                if cat_dir.is_dir() and cat_dir.name != "lib":
                    for script_file in cat_dir.glob("*.py"):
                        try:
                            content = script_file.read_text()
                            if f"from lib.{script_name}" in content or f"import {script_name}" in content:
                                dependent_scripts.append({
                                    "name": script_file.stem,
                                    "tier": "user",
                                    "type": "script",
                                    "dependency_type": "import"
                                })
                        except Exception:
                            pass
        
        return {
            "has_dependencies": len(dependent_scripts) > 0,
            "dependent_scripts": dependent_scripts,
            "count": len(dependent_scripts)
        }
    
    async def execute(self, params: Dict[str, Any]) -> str:
        """
        Remove script from specified tier(s).
        
        Args:
            script_name: Name of script to remove
            tier: 'project' | 'user' | 'registry' | 'all' (default: 'all')
            category: Optional category (auto-detected if not provided)
            confirm: Require confirmation (default: true for registry, false for local)
            dry_run: Preview what would be deleted (default: false)
            force: Remove even if dependencies exist (default: false)
            remove_libs: Also remove lib dependencies if unused (default: false)
            is_lib: Whether this is a lib script (default: false, auto-detected)
        
        Returns:
            JSON with removal results
        """
        script_name = params.get("script_name", "")
        tier = params.get("tier", "all")
        category = params.get("category")
        dry_run = params.get("dry_run", False)
        force = params.get("force", False)
        remove_libs = params.get("remove_libs", False)
        is_lib = params.get("is_lib", False)
        
        if not script_name:
            return json.dumps({
                "error": "script_name is required",
                "suggestion": "Try: remove({'script_name': 'script_name', 'tier': 'user'})"
            }, indent=2)
        
        results = {
            "script_name": script_name,
            "tier": tier,
            "dry_run": dry_run,
            "removals": {},
            "warnings": []
        }
        
        # Check dependencies if not forcing
        if not force and not dry_run:
            dep_check = await self._check_dependencies(script_name, tier)
            if dep_check["has_dependencies"]:
                results["warnings"].append({
                    "type": "dependencies",
                    "message": f"Script is used by {dep_check['count']} other script(s)",
                    "dependent_scripts": dep_check["dependent_scripts"]
                })
                if not force:
                    return json.dumps({
                        "error": "Script has dependencies",
                        "details": dep_check,
                        "suggestion": "Use force=true to remove anyway, or remove dependent scripts first"
                    }, indent=2)
        
        # Determine if this is a lib script
        if not is_lib:
            # Check if it exists in lib/ directory
            project_lib = self.resolver.project_scripts / "lib" / f"{script_name}.py"
            user_lib = self.resolver.user_scripts / "lib" / f"{script_name}.py"
            is_lib = project_lib.exists() or user_lib.exists()
        
        # Remove from project space
        if tier in ["project", "all"]:
            if is_lib:
                result = await self._remove_lib_from_project(script_name)
            else:
                result = await self._remove_from_project(script_name, category, dry_run)
            
            results["removals"]["project"] = result
        
        # Remove from user space
        if tier in ["user", "all"]:
            if is_lib:
                result = await self._remove_lib_from_user(script_name)
            else:
                result = await self._remove_from_user(script_name, category, dry_run)
            
            results["removals"]["user"] = result
        
        # Remove from registry
        if tier in ["registry", "all"]:
            action = params.get("action", "deprecate")  # Default to deprecate for safety
            version = params.get("version")
            
            if action == "delete":
                result = await self.registry.delete_script(script_name, version)
            else:
                # Default to deprecate
                reason = params.get("reason", "Removed by user")
                result = await self.registry.deprecate_script(script_name, reason)
            
            if dry_run:
                result["dry_run"] = True
                result["would_remove"] = result.get("deleted", False) or result.get("deprecated", False)
                result["deleted"] = False
                result["deprecated"] = False
            
            results["removals"]["registry"] = result
        
        # Count successful removals (or would_remove in dry_run)
        if dry_run:
            successful = sum(
                1 for r in results["removals"].values()
                if r.get("would_remove", False)
            )
        else:
            successful = sum(
                1 for r in results["removals"].values()
                if r.get("removed", False)
            )
        
        results["summary"] = {
            "successful": successful,
            "total_attempted": len(results["removals"]),
            "dry_run": dry_run
        }
        
        if dry_run:
            results["message"] = f"Would remove '{script_name}' from {successful} location(s)"
        else:
            results["message"] = f"Removed '{script_name}' from {successful} location(s)"
        
        return json.dumps(results, indent=2)

