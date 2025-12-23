"""Load tool for Script Kiwi."""

from typing import Dict, Any
import json
import logging
from pathlib import Path
from ..api.script_registry import ScriptRegistry
from ..utils.script_resolver import ScriptResolver
from ..utils.script_metadata import extract_script_metadata

logger = logging.getLogger(__name__)


class LoadTool:
    """Load script specification with 3-tier resolution"""
    
    def __init__(self, project_path: str = None):
        self.registry = ScriptRegistry()
        self.project_path = Path(project_path) if project_path else None
        self.resolver = ScriptResolver(
            project_root=self.project_path,
            registry_client=self.registry
        )
    
    async def _download_lib_dependencies(self, lib_names: list[str]):
        """Download library dependencies to user space."""
        import os
        script_kiwi_home = os.getenv("SCRIPT_KIWI_HOME")
        if script_kiwi_home:
            script_kiwi_home = Path(script_kiwi_home)
        else:
            script_kiwi_home = Path.home() / ".script-kiwi"
        lib_dir = script_kiwi_home / "scripts/lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure __init__.py exists
        lib_init = lib_dir / "__init__.py"
        if not lib_init.exists():
            lib_init.write_text("# Script Kiwi library modules\n")
        
        for lib_name in lib_names:
            lib_file = lib_dir / f"{lib_name}.py"
            
            # Don't overwrite if already exists (user may have custom version)
            if lib_file.exists():
                logger.info(f"Library '{lib_name}' already exists, skipping download")
                continue
            
            # Get library from registry
            lib_script = await self.registry.get_script(lib_name)
            if lib_script and lib_script.get("content"):
                # Use existing download_to_user_space with category="lib"
                self.resolver.download_to_user_space(
                    script_name=lib_name,
                    category="lib",
                    content=lib_script["content"],
                    subcategory=None
                )
                logger.info(f"Downloaded library: {lib_name}")
            else:
                logger.warning(f"Library '{lib_name}' not found in registry")
    
    async def execute(self, params: Dict[str, Any]) -> str:
        """
        Load script details and metadata.
        Uses 3-tier resolution: Project → User → Registry
        
        Args:
            script_name: Name of script
            sections: Which sections to load (inputs, dependencies, cost, all)
            download_to_user: If true, download from registry to user space
            version: Optional specific version (default: latest)
        
        Returns:
            JSON with script specification (metadata, inputs, dependencies, cost)
        """
        script_name = params.get("script_name", "")
        sections = params.get("sections", ["all"])
        download_to_user = params.get("download_to_user", False)
        version = params.get("version")
        project_path = params.get("project_path")
        
        # Re-initialize resolver with project_path if provided
        if project_path:
            self.project_path = Path(project_path)
            self.resolver = ScriptResolver(
                project_root=self.project_path,
                registry_client=self.registry
            )
        
        if not script_name:
            return json.dumps({
                "error": "script_name is required"
            })
        
        # Resolve script location (3-tier: Project → User → Registry)
        resolved = await self.resolver.resolve_script(script_name)
        
        script = None
        script_source = None
        
        # If found in project or user space, read from file
        if resolved["location"] in ["project", "user"]:
            script_path = Path(resolved["path"])
            if script_path.exists():
                with open(script_path, 'r') as f:
                    content = f.read()
                
                # Extract metadata from script file
                extracted_metadata = extract_script_metadata(script_path)
                
                # Build script dict with extracted metadata
                script = {
                    "name": script_name,
                    "category": resolved.get("category") or "utility",
                    "content": content,
                    "version": "local",
                    "module_path": f"execution.{resolved.get('category', 'utility')}.{script_name}",
                    "description": extracted_metadata.get("description") or f"Local script: {script_name}",
                    "dependencies": extracted_metadata.get("dependencies", []),
                    "required_env_vars": extracted_metadata.get("required_env_vars", []),
                    "input_schema": extracted_metadata.get("input_schema", {}),
                    "tech_stack": extracted_metadata.get("tech_stack", [])
                }
                script_source = resolved["location"]
        
        # If not found locally, check registry
        if not script and resolved.get("registry_data"):
            script = resolved["registry_data"]
            script_source = "registry"
            
            # Download to user space if requested
            if download_to_user and script.get("content"):
                category = script.get("category", "utility")
                subcategory = script.get("subcategory")
                downloaded_path = self.resolver.download_to_user_space(
                    script_name=script_name,
                    category=category,
                    content=script["content"],
                    subcategory=subcategory
                )
                script["downloaded_to"] = str(downloaded_path)
                
                # Download required_libs dependencies
                required_libs = script.get("required_libs", [])
                if required_libs:
                    await self._download_lib_dependencies(required_libs)
                    script["downloaded_libs"] = required_libs
        
        # If still not found, try direct registry query (fallback)
        if not script:
            script = await self.registry.get_script(script_name, version=version)
            if script:
                script_source = "registry"
                
                # Download to user space if requested
                if download_to_user and script.get("content"):
                    category = script.get("category", "utility")
                    subcategory = script.get("subcategory")
                    downloaded_path = self.resolver.download_to_user_space(
                        script_name=script_name,
                        category=category,
                        content=script["content"],
                        subcategory=subcategory
                    )
                    script["downloaded_to"] = str(downloaded_path)
                    
                    # Download required_libs dependencies
                    required_libs = script.get("required_libs", [])
                    if required_libs:
                        await self._download_lib_dependencies(required_libs)
                        script["downloaded_libs"] = required_libs
        
        if not script:
            return json.dumps({
                "error": f"Script not found: {script_name}",
                "suggestion": "Use search({'query': '...'}) to find available scripts"
            })
        
        # Build response based on requested sections
        response = {
            "script": {
                "name": script.get("name"),
                "category": script.get("category"),
                "description": script.get("description"),
                "module_path": script.get("module_path"),
                "version": script.get("version", "unknown"),
                "quality_score": script.get("quality_score", 0),
                "success_rate": script.get("success_rate"),
                "source": script_source or "unknown",
                "tech_stack": script.get("tech_stack", [])
            }
        }
        
        # Include download info if downloaded
        if script.get("downloaded_to"):
            response["downloaded_to"] = script.get("downloaded_to")
        
        # Extract inputs from script metadata
        if "all" in sections or "inputs" in sections:
            # Use extracted input_schema from script file or registry metadata
            input_schema = script.get("input_schema", {})
            if not input_schema and script.get("content"):
                # Try to extract from script content if not already extracted
                script_path = Path(resolved["path"]) if resolved.get("path") else None
                if script_path and script_path.exists():
                    extracted = extract_script_metadata(script_path)
                    input_schema = extracted.get("input_schema", {})
            response["inputs"] = input_schema
        
        if "all" in sections or "cost" in sections:
            response["cost_estimate"] = {
                "base_cost_usd": script.get("estimated_cost_usd"),
                "cost_per_unit": script.get("cost_per_unit"),
                "cost_unit": script.get("cost_unit"),
            }
        
        if "all" in sections or "dependencies" in sections:
            response["dependencies"] = {
                "packages": script.get("dependencies", []),
                "env_vars": script.get("required_env_vars", []),
                "scripts": script.get("required_scripts", []),
                "libs": script.get("required_libs", []),
            }
        
        # Include downloaded libs info if downloaded
        if script.get("downloaded_libs"):
            response["downloaded_libs"] = script.get("downloaded_libs")
        
        response["next_steps"] = [
            "Review script metadata and dependencies",
            f"Use run({{'script_name': '{script_name}', 'parameters': {{...}}}}) to run",
            "Use dry_run=true to validate without executing"
        ]
        
        return json.dumps(response, indent=2)
