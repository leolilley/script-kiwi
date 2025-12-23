"""Publish tool for Script Kiwi."""

from typing import Dict, Any
import json
import hashlib
from ..api.script_registry import ScriptRegistry
from ..utils.script_resolver import ScriptResolver


class PublishTool:
    """Publish script to registry with versioning"""
    
    def __init__(self):
        self.registry = ScriptRegistry()
        self.resolver = ScriptResolver(registry_client=self.registry)
    
    async def execute(self, params: Dict[str, Any]) -> str:
        """
        Publish a script to the registry
        
        Args:
            script_name: Name of script to publish
            version: Semver version (e.g., '1.2.0')
            category: Script category
            subcategory: Optional subcategory
            changelog: Optional changelog
            metadata: Optional metadata dict with:
                - description: Script description
                - dependencies: List of pip dependencies [{"name": "...", "version": "..."}]
                - required_env_vars: List of required environment variables
                - tech_stack: List of tech stack items
                - tags: List of tags
                - cost_per_unit: Cost per unit
                - cost_unit: Cost unit name
                - module_path: Module path override
            project_path: Optional project root path
        
        Returns:
            JSON with publish result
        """
        script_name = params.get("script_name", "")
        version = params.get("version", "")
        category = params.get("category")
        project_path = params.get("project_path")
        
        if not script_name or not version:
            return json.dumps({
                "error": "script_name and version are required"
            })
        
        # Validate semver
        import re
        if not re.match(r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$', version):
            return json.dumps({
                "error": f"Invalid semver version: {version}. Must be in format X.Y.Z"
            })
        
        # Initialize resolver with project_path if provided
        if project_path:
            from pathlib import Path
            self.resolver = ScriptResolver(
                project_root=Path(project_path),
                registry_client=self.registry
            )
        
        # Resolve script location
        resolved = await self.resolver.resolve_script(script_name, category=category)
        
        if not resolved["path"]:
            return json.dumps({
                "error": f"Script '{script_name}' not found locally. Cannot publish from registry."
            })
        
        # Auto-detect category and subcategory from resolved path if not provided
        if not category:
            category = resolved.get("category")
        subcategory = params.get("subcategory") or resolved.get("subcategory")
        
        # Read script content
        script_path = resolved["path"]
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Calculate content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        # Extract metadata from params or script file
        metadata = params.get("metadata")
        if metadata and not isinstance(metadata, dict):
            return json.dumps({
                "error": "metadata must be a dictionary/object"
            })
        
        # If no metadata provided, extract from script file
        if not metadata:
            from ..utils.script_metadata import extract_script_metadata
            extracted = extract_script_metadata(script_path)
            metadata = {
                "description": extracted.get("description"),
                "dependencies": extracted.get("dependencies", []),
                "required_env_vars": extracted.get("required_env_vars", []),
                "tech_stack": extracted.get("tech_stack", []),
                "module_path": f"execution.{category}.{script_name}",
            }
        
        # Publish to registry (use resolved category or explicit, fallback to "utility")
        result = await self.registry.publish_script(
            script_name=script_name,
            category=category or "utility",
            version=version,
            content=content,
            content_hash=content_hash,
            changelog=params.get("changelog"),
            subcategory=subcategory,
            metadata=metadata
        )
        
        if "error" in result:
            return json.dumps(result, indent=2)
        
        return json.dumps({
            "status": "published",
            "script_name": script_name,
            "version": version,
            "script_id": result.get("script_id"),
            "version_id": result.get("version_id")
        }, indent=2)
