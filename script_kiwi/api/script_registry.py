"""
Script Registry API Client

Handles all interactions with Supabase scripts table.
"""

import os
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Load .env file - try project root first, then current directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Fallback to default behavior


class ScriptRegistry:
    """Client for Script Kiwi Supabase registry."""
    
    def __init__(self):
        # Reload .env file to ensure we have latest values (important for MCP server)
        project_root = Path(__file__).parent.parent.parent
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)  # override=True ensures MCP env vars take precedence
        
        # Use os.environ.get() like context-kiwi does
        # Try both SUPABASE_SECRET_KEY and SCRIPT_KIWI_API_KEY (for consistency with context-kiwi)
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SCRIPT_KIWI_API_KEY")
        
        if not self.url or not self.key:
            # Log which variable is missing for debugging
            missing = []
            if not self.url:
                missing.append("SUPABASE_URL")
            if not self.key:
                missing.append("SUPABASE_SECRET_KEY or SCRIPT_KIWI_API_KEY")
            # Log to stderr so it's visible in MCP logs
            import sys
            print(f"ScriptRegistry: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
            self.client = None
        else:
            try:
                self.client = create_client(self.url, self.key)
            except Exception as e:
                import sys
                print(f"ScriptRegistry: Failed to create Supabase client: {e}", file=sys.stderr)
                self.client = None
    
    async def search_scripts(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        tech_stack: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search scripts with improved multi-term matching and relevance scoring.
        
        Uses natural language multi-term search that:
        - Parses queries into normalized terms
        - Requires ALL terms to match (AND logic)
        - Intelligent relevance scoring (70% relevance + 30% compatibility)
        - Better results ranking
        
        Args:
            query: Search query (natural language, supports multiple terms)
            category: Optional category filter
            limit: Max results
            tech_stack: Optional tech stack for compatibility scoring
        
        Returns:
            List of matching scripts with relevance scores
        """
        if not self.client:
            return []
        
        # Parse and normalize query
        query_terms = self._parse_search_query(query)
        if not query_terms:
            return []
        
        try:
            # Build search conditions (one per term) for initial filtering
            or_conditions = []
            for term in query_terms:
                or_conditions.extend([
                    f"name.ilike.%{term}%",
                    f"description.ilike.%{term}%"
                ])
            
            # Build query - get more results to filter client-side
            query_builder = self.client.table("scripts").select(
                "id, name, category, subcategory, description, is_official, "
                "download_count, quality_score, tech_stack, created_at, updated_at, "
                "tags, success_rate, estimated_cost_usd, latest_version"
            )
            
            # Apply initial OR filter (any term matches)
            if or_conditions:
                query_builder = query_builder.or_(",".join(or_conditions))
            
            # Apply category filter
            if category:
                query_builder = query_builder.eq("category", category)
            
            # Execute query - get more results to filter client-side
            result = query_builder.limit(limit * 3).execute()
            
            scripts = []
            for row in (result.data or []):
                script = {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "category": row.get("category"),
                    "subcategory": row.get("subcategory"),
                    "description": row.get("description"),
                    "is_official": row.get("is_official", False),
                    "download_count": row.get("download_count", 0),
                    "quality_score": row.get("quality_score", 0),
                    "tech_stack": row.get("tech_stack", []),
                    "tags": row.get("tags", []),
                    "success_rate": row.get("success_rate"),
                    "estimated_cost_usd": row.get("estimated_cost_usd"),
                    "latest_version": row.get("latest_version"),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                }
                
                # CRITICAL: Multi-term matching - ensure ALL terms appear
                name_desc = f"{script['name']} {script.get('description', '')}".lower()
                if not all(term.lower() in name_desc for term in query_terms):
                    continue  # Skip if not all terms match
                
                # Calculate relevance score
                relevance_score = self._calculate_relevance_score(
                    query_terms, script["name"], script.get("description", "")
                )
                script["relevance_score"] = relevance_score
                
                # Apply tech stack compatibility
                if tech_stack and (s_stack := script.get("tech_stack")):
                    overlap = set(t.lower() for t in tech_stack) & set(
                        t.lower() if isinstance(t, str) else str(t).lower() 
                        for t in (s_stack if isinstance(s_stack, list) else [])
                    )
                    if not overlap:
                        continue  # Skip if no tech stack overlap
                    script["compatibility_score"] = len(overlap) / max(len(s_stack), 1)
                else:
                    script["compatibility_score"] = 1.0
                
                scripts.append(script)
            
            # Sort results by combined score: 70% relevance + 30% compatibility
            scripts.sort(
                key=lambda x: (
                    x.get("relevance_score", 0) * 0.7 + 
                    x.get("compatibility_score", 0) * 0.3
                ),
                reverse=True
            )
            
            # Also include quality_score and download_count as tiebreakers
            scripts.sort(
                key=lambda x: (
                    x.get("relevance_score", 0) * 0.7 + 
                    x.get("compatibility_score", 0) * 0.3,
                    x.get("quality_score", 0),
                    x.get("download_count", 0)
                ),
                reverse=True
            )
            
            return scripts[:limit]
        except Exception as e:
            print(f"Error searching scripts: {e}")
            return []
    
    def _parse_search_query(self, query: str) -> List[str]:
        """
        Parse search query into normalized terms.
        
        Handles:
        - Multiple words (split by whitespace)
        - Normalization (lowercase, strip)
        - Filters out single characters
        
        Future: Add support for quoted phrases and operators (| for OR, - for NOT)
        
        Args:
            query: Search query string
        
        Returns:
            List of normalized search terms
        """
        if not query or not query.strip():
            return []
        
        terms = []
        for word in query.split():
            word = word.strip().lower()
            if word and len(word) >= 2:  # Ignore single characters
                terms.append(word)
        
        return terms
    
    def _calculate_relevance_score(
        self,
        query_terms: List[str],
        name: str,
        description: str
    ) -> float:
        """
        Calculate relevance score based on term matches.
        
        Scoring:
        - Exact name match: 100
        - Name contains all terms: 80
        - Name contains some terms: 60 * (matches/terms)
        - Description contains all terms: 40
        - Description contains some terms: 20 * (matches/terms)
        
        Args:
            query_terms: List of normalized search terms
            name: Script name
            description: Script description
        
        Returns:
            Relevance score (0-100)
        """
        name_lower = name.lower()
        desc_lower = (description or "").lower()
        
        # Check exact name match
        name_normalized = name_lower.replace("_", " ").replace("-", " ")
        query_normalized = " ".join(query_terms)
        if name_normalized == query_normalized or name_lower == query_normalized.replace(" ", "_"):
            return 100.0
        
        # Count term matches in name
        name_matches = sum(1 for term in query_terms if term in name_lower)
        desc_matches = sum(1 for term in query_terms if term in desc_lower)
        
        # Calculate score
        score = 0.0
        
        if name_matches == len(query_terms):
            score = 80.0  # All terms in name
        elif name_matches > 0:
            score = 60.0 * (name_matches / len(query_terms))  # Some terms in name
        
        if desc_matches == len(query_terms):
            score = max(score, 40.0)  # All terms in description
        elif desc_matches > 0:
            score = max(score, 20.0 * (desc_matches / len(query_terms)))  # Some terms in description
        
        return score
    
    async def get_script(
        self,
        script_name: str,
        version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get script metadata and code.
        
        Args:
            script_name: Name of script
            version: Optional specific version (default: latest)
        
        Returns:
            Script metadata with code, or None if not found
        """
        if not self.client:
            return None
        
        try:
            # Get script metadata
            script_result = self.client.table("scripts").select(
                "*"
            ).eq("name", script_name).single().execute()
            
            if not script_result.data:
                return None
            
            script = script_result.data
            
            # Parse JSONB fields if they came back as JSON strings (Supabase client issue)
            for field in ["dependencies", "tech_stack", "required_env_vars", "tags"]:
                if field in script:
                    value = script[field]
                    # If whole field is a JSON string, parse it
                    if isinstance(value, str):
                        try:
                            script[field] = json.loads(value)
                            value = script[field]
                        except (json.JSONDecodeError, TypeError):
                            script[field] = []
                            value = []
                    
                    # If field is a list where items are JSON strings, parse each item
                    if isinstance(value, list):
                        parsed_list = []
                        for item in value:
                            if isinstance(item, str) and (item.startswith('{') or item.startswith('[')):
                                try:
                                    parsed_list.append(json.loads(item))
                                except (json.JSONDecodeError, TypeError):
                                    parsed_list.append(item)
                            else:
                                parsed_list.append(item)
                        script[field] = parsed_list
            
            # Get version content
            if version:
                version_result = self.client.table("script_versions").select(
                    "version, content, content_hash, changelog"
                ).eq("script_id", script["id"]).eq("version", version).single().execute()
            else:
                version_result = self.client.rpc(
                    "get_latest_version",
                    {"script_name_param": script_name}
                ).execute()
            
            if version_result.data:
                if isinstance(version_result.data, list) and len(version_result.data) > 0:
                    version_data = version_result.data[0]
                else:
                    version_data = version_result.data
                
                script["version"] = version_data.get("version")
                script["content"] = version_data.get("content")
                script["content_hash"] = version_data.get("content_hash")
                script["changelog"] = version_data.get("changelog")
            
            return script
        except Exception as e:
            print(f"Error getting script: {e}")
            return None
    
    async def publish_script(
        self,
        script_name: str,
        category: str,
        version: str,
        content: str,
        content_hash: str,
        changelog: Optional[str] = None,
        subcategory: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Publish script to registry.
        
        Args:
            script_name: Name of script
            category: Script category
            version: Semver version
            content: Python code
            content_hash: SHA256 hash of content
            changelog: Optional changelog
            subcategory: Optional subcategory (e.g., 'google-maps' for category 'scraping')
            metadata: Optional additional metadata
        
        Returns:
            Publish result with script_id and version_id
        """
        if not self.client:
            return {
                "error": "Supabase client not initialized",
                "details": {
                    "url_set": bool(self.url),
                    "key_set": bool(self.key),
                    "message": "Check SUPABASE_URL and SUPABASE_SECRET_KEY environment variables"
                }
            }
        
        try:
            # Check if script exists
            existing = self.client.table("scripts").select(
                "id"
            ).eq("name", script_name).execute()
            
            if existing.data:
                script_id = existing.data[0]["id"]
                # Update metadata if provided (for existing scripts)
                if metadata:
                    update_data = {}
                    if "description" in metadata:
                        update_data["description"] = metadata["description"]
                    if "dependencies" in metadata:
                        # Ensure dependencies are in correct format before storing
                        deps = metadata["dependencies"]
                        if not isinstance(deps, list):
                            raise ValueError(f"dependencies must be a list, got {type(deps)}")
                        for i, dep in enumerate(deps):
                            if not isinstance(dep, dict):
                                raise ValueError(f"dependency {i} must be a dict, got {type(dep)}")
                            if not isinstance(dep.get("name"), str):
                                raise ValueError(f"dependency {i} 'name' must be a string")
                        update_data["dependencies"] = deps
                    if "required_env_vars" in metadata:
                        update_data["required_env_vars"] = metadata["required_env_vars"]
                    if "tech_stack" in metadata:
                        update_data["tech_stack"] = metadata["tech_stack"]
                    if "tags" in metadata:
                        update_data["tags"] = metadata["tags"]
                    if "cost_per_unit" in metadata:
                        update_data["cost_per_unit"] = metadata["cost_per_unit"]
                    if "cost_unit" in metadata:
                        update_data["cost_unit"] = metadata["cost_unit"]
                    if "module_path" in metadata:
                        update_data["module_path"] = metadata["module_path"]
                    if "category" in metadata:
                        update_data["category"] = metadata["category"]
                    if "subcategory" in metadata:
                        update_data["subcategory"] = metadata["subcategory"]
                    
                    if update_data:
                        self.client.table("scripts").update(update_data).eq("id", script_id).execute()
            else:
                # Create new script
                script_data = {
                    "name": script_name,
                    "category": category,
                    "subcategory": subcategory,
                    "description": metadata.get("description", "") if metadata else "",
                    "module_path": metadata.get("module_path", f"execution.{category}.{script_name}") if metadata else f"execution.{category}.{script_name}",
                    "tech_stack": metadata.get("tech_stack", []) if metadata else [],
                    "dependencies": metadata.get("dependencies", []) if metadata else [],
                    "required_env_vars": metadata.get("required_env_vars", []) if metadata else [],
                    "cost_per_unit": metadata.get("cost_per_unit") if metadata else None,
                    "cost_unit": metadata.get("cost_unit") if metadata else None,
                    "tags": metadata.get("tags", []) if metadata else [],
                }
                
                script_result = self.client.table("scripts").insert(script_data).execute()
                script_id = script_result.data[0]["id"]
            
            self.client.table("script_versions").update(
                {"is_latest": False}
            ).eq("script_id", script_id).execute()
            
            # Insert new version
            version_data = {
                "script_id": script_id,
                "version": version,
                "content": content,
                "content_hash": content_hash,
                "changelog": changelog,
                "is_latest": True
            }
            
            version_result = self.client.table("script_versions").insert(version_data).execute()
            
            self.client.table("scripts").update(
                {"latest_version": version}
            ).eq("id", script_id).execute()
            
            return {
                "script_id": script_id,
                "version_id": version_result.data[0]["id"],
                "version": version,
                "status": "published"
            }
        except Exception as e:
            error_msg = str(e)
            # Provide more helpful error messages
            if "401" in error_msg or "Invalid API key" in error_msg:
                return {
                    "error": "Supabase authentication failed",
                    "details": {
                        "message": "Invalid API key or insufficient permissions",
                        "suggestion": "Verify SUPABASE_SECRET_KEY is the service_role key (not anon key) and has access to 'scripts' and 'script_versions' tables",
                        "original_error": error_msg
                    }
                }
            elif "relation" in error_msg.lower() and "does not exist" in error_msg.lower():
                return {
                    "error": "Database tables not found",
                    "details": {
                        "message": "The 'scripts' or 'script_versions' tables don't exist in this Supabase project",
                        "suggestion": "Run the schema migration from docs/script-kiwi-schema.sql",
                        "original_error": error_msg
                    }
                }
            else:
                return {
                    "error": "Publish failed",
                    "details": {
                        "message": error_msg,
                        "original_error": str(e)
                    }
                }
    
    async def delete_script(
        self,
        script_name: str,
        version: Optional[str] = None,
        cascade: bool = False
    ) -> Dict[str, Any]:
        """
        Delete script or version from registry.
        
        Args:
            script_name: Name of script
            version: Optional specific version (default: all versions)
            cascade: If True, also delete dependent scripts (dangerous)
        
        Returns:
            Deletion result
        """
        if not self.client:
            return {"error": "Supabase client not initialized"}
        
        try:
            # Get script ID
            script_result = self.client.table("scripts").select(
                "id, latest_version"
            ).eq("name", script_name).single().execute()
            
            if not script_result.data:
                return {"error": f"Script '{script_name}' not found"}
            
            script_id = script_result.data["id"]
            latest_version = script_result.data.get("latest_version")
            
            if version:
                # Delete specific version
                version_result = self.client.table("script_versions").delete().eq(
                    "script_id", script_id
                ).eq("version", version).execute()
                
                # If deleted version was latest, update latest_version
                if version == latest_version:
                    # Get new latest version
                    new_latest = self.client.rpc(
                        "get_latest_version",
                        {"script_name_param": script_name}
                    ).execute()
                    
                    if new_latest.data:
                        if isinstance(new_latest.data, list) and len(new_latest.data) > 0:
                            new_version = new_latest.data[0].get("version")
                        else:
                            new_version = new_latest.data.get("version") if isinstance(new_latest.data, dict) else None
                        
                        if new_version:
                            self.client.table("scripts").update({
                                "latest_version": new_version
                            }).eq("id", script_id).execute()
                        else:
                            # No versions left, delete script record
                            self.client.table("scripts").delete().eq("id", script_id).execute()
                            return {
                                "deleted": True,
                                "script_name": script_name,
                                "version": version,
                                "all_versions": True
                            }
                
                return {
                    "deleted": True,
                    "script_name": script_name,
                    "version": version
                }
            else:
                # Delete all versions and script record
                self.client.table("script_versions").delete().eq(
                    "script_id", script_id
                ).execute()
                
                self.client.table("scripts").delete().eq("id", script_id).execute()
                
                return {
                    "deleted": True,
                    "script_name": script_name,
                    "all_versions": True
                }
        except Exception as e:
            return {"error": str(e)}
    
    async def deprecate_script(
        self,
        script_name: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark script as deprecated (safer than deletion).
        
        Args:
            script_name: Name of script
            reason: Optional deprecation reason
        
        Returns:
            Deprecation result
        """
        if not self.client:
            return {"error": "Supabase client not initialized"}
        
        try:
            # Check if deprecated column exists (if not, we'll just return an error)
            script_result = self.client.table("scripts").select(
                "id"
            ).eq("name", script_name).single().execute()
            
            if not script_result.data:
                return {"error": f"Script '{script_name}' not found"}
            
            script_id = script_result.data["id"]
            
            # Try to update with deprecated flag
            # Note: This assumes the column exists. If migration hasn't run, this will fail gracefully.
            update_data = {
                "deprecated": True
            }
            
            if reason:
                update_data["deprecated_reason"] = reason
            
            result = self.client.table("scripts").update(update_data).eq(
                "id", script_id
            ).execute()
            
            return {
                "deprecated": True,
                "script_name": script_name,
                "reason": reason
            }
        except Exception as e:
            # If deprecated column doesn't exist, return helpful error
            if "column" in str(e).lower() and "deprecated" in str(e).lower():
                return {
                    "error": "Deprecated column not found. Run database migration first.",
                    "migration_required": True
                }
            return {"error": str(e)}


