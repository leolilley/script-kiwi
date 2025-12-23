"""Search tool for Script Kiwi."""

from typing import Dict, Any, List, Optional
import json
from pathlib import Path
from ..api.script_registry import ScriptRegistry
from ..utils.script_resolver import ScriptResolver


class SearchTool:
    """Search for scripts by intent or keywords across all tiers"""
    
    def __init__(self, project_path: str = None):
        self.registry = ScriptRegistry()
        self.project_path = Path(project_path) if project_path else None
        self.resolver = ScriptResolver(
            project_root=self.project_path,
            registry_client=self.registry
        )
    
    async def execute(self, params: Dict[str, Any]) -> str:
        """
        Search scripts across all tiers (Project + User + Registry)
        
        Args:
            query: Search query
            category: Optional category filter
            limit: Max results
        
        Returns:
            JSON string with matching scripts and confidence scores
        """
        query = params.get("query", "")
        category = params.get("category", "all")
        limit = params.get("limit", 10)
        project_path = params.get("project_path")
        
        # Re-initialize resolver with project_path if provided
        if project_path:
            self.project_path = Path(project_path)
            self.resolver = ScriptResolver(
                project_root=self.project_path,
                registry_client=self.registry
            )
        
        if not query:
            return json.dumps({
                "error": "Query is required",
                "suggestion": "Try: search({'query': 'scrape Google Maps'})"
            })
        
        results = []
        query_lower = query.lower()
        query_words = query_lower.split()
        
        # 1. Search project space
        project_results = self._search_local_space(
            self.resolver.project_scripts,
            query_words,
            category if category != "all" else None,
            "project"
        )
        results.extend(project_results)
        
        # 2. Search user space (avoid duplicates)
        existing_names = {r["name"] for r in project_results}
        user_results = self._search_local_space(
            self.resolver.user_scripts,
            query_words,
            category if category != "all" else None,
            "user"
        )
        results.extend([
            r for r in user_results
            if r["name"] not in existing_names
        ])
        
        # 3. Search registry (with improved multi-term matching)
        registry_results = await self.registry.search_scripts(
            query=query,
            category=None if category == "all" else category,
            limit=limit
        )
        
        # Format registry results
        for script in registry_results:
            # Skip if already found locally
            if script.get("name") not in existing_names:
                # Calculate combined score: 70% relevance + 30% compatibility
                relevance = script.get("relevance_score", 0)
                compatibility = script.get("compatibility_score", 1.0)
                combined_score = (relevance * 0.7 + compatibility * 0.3) / 100.0  # Normalize to 0-1
                
                results.append({
                    "name": script.get("name"),
                    "category": script.get("category"),
                    "subcategory": script.get("subcategory"),
                    "description": script.get("description"),
                    "source": "registry",
                    "confidence": combined_score,
                    "relevance_score": relevance,
                    "compatibility_score": compatibility,
                    "quality_score": script.get("quality_score", 0),
                    "success_rate": script.get("success_rate"),
                    "estimated_cost": script.get("estimated_cost_usd"),
                    "version": script.get("latest_version"),
                    "tags": script.get("tags", [])
                })
        
        # Sort by confidence (which includes relevance + compatibility for registry, or local score)
        # Use quality_score and download_count as tiebreakers
        results.sort(
            key=lambda x: (
                x.get("confidence", 0),
                x.get("quality_score", 0),
                x.get("download_count", 0) if x.get("source") == "registry" else 0
            ),
            reverse=True
        )
        results = results[:limit]
        
        return json.dumps({
            "query": query,
            "results_count": len(results),
            "results": results,
            "next_steps": [
                "Use load({'script_name': '...'}) to see details",
                "Use run({'script_name': '...', 'parameters': {...}}) to run"
            ]
        }, indent=2)
    
    def _search_local_space(
        self,
        base_dir: Path,
        query_words: List[str],
        category: Optional[str],
        source: str
    ) -> List[Dict[str, Any]]:
        """
        Search local directory for matching scripts with improved multi-term matching.
        
        Uses enhanced scoring that:
        - Requires ALL query terms to match
        - Calculates relevance based on name/description matches
        - Provides better ranking
        """
        results = []
        
        if not base_dir.exists():
            return results
        
        # Normalize query terms (filter single characters)
        query_terms = [w.strip().lower() for w in query_words if w.strip() and len(w.strip()) >= 2]
        if not query_terms:
            # Fallback to original words if all filtered out
            query_terms = [w.strip().lower() for w in query_words if w.strip()]
        
        # Search recursively - supports any category and subfolders
        if category and category != "all":
            # Search specific category (and subcategories)
            cat_dir = base_dir / category
            if cat_dir.exists():
                # Search recursively in category directory
                for script_file in cat_dir.rglob("*.py"):
                    if script_file.is_file() and script_file.name != "__init__.py":
                        result = self._evaluate_script_match(
                            script_file, base_dir, query_terms, category, source
                        )
                        if result:
                            results.append(result)
        else:
            # Search all categories recursively
            if base_dir.exists():
                for script_file in base_dir.rglob("*.py"):
                    if script_file.is_file() and script_file.name != "__init__.py":
                        result = self._evaluate_script_match(
                            script_file, base_dir, query_terms, None, source
                        )
                        if result:
                            results.append(result)
        
        return results
    
    def _evaluate_script_match(
        self,
        script_file: Path,
        base_dir: Path,
        query_terms: List[str],
        category: Optional[str],
        source: str
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate if a script matches the query and calculate relevance score.
        
        Returns:
            Script match dict with confidence score, or None if no match
        """
        # Extract category from path
        relative = script_file.relative_to(base_dir)
        script_category = relative.parts[0] if len(relative.parts) > 0 else (category or "unknown")
        
        script_name = script_file.stem
        script_content = script_file.read_text()
        
        # Try to extract description from docstring
        try:
            description = self._extract_description(script_content)
        except Exception:
            description = None
        
        # Calculate relevance score
        score = self._calculate_score(
            query_terms, script_name, description or "", script_category
        )
        
        # Require ALL terms to match (score > 0 means at least some match)
        # For multi-term queries, we want all terms to appear
        if not query_terms:
            return None
        
        name_desc = f"{script_name} {description or ''}".lower()
        if not all(term in name_desc for term in query_terms):
            return None  # Skip if not all terms match
        
        return {
            "name": script_name,
            "category": script_category,
            "description": description or f"Local script: {script_name}",
            "source": source,
            "confidence": score / 100.0,  # Convert to 0-1 range
            "path": str(script_file),
            "version": "local"
        }
    
    def _calculate_score(
        self,
        query_terms: List[str],
        name: str,
        description: str,
        category: str
    ) -> float:
        """
        Calculate match score with improved multi-term support.
        
        Scoring:
        - Exact name match: 100
        - Name contains all query terms: 80
        - Name contains some query terms: 60 * ratio
        - Description contains all terms: 40
        - Description contains some terms: 20 * ratio
        - Category match: +15
        
        Args:
            query_terms: List of normalized search terms
            name: Script name
            description: Script description
            category: Script category
        
        Returns:
            Score (0-100)
        """
        name_lower = name.lower()
        desc_lower = (description or "").lower()
        category_lower = (category or "").lower()
        
        if not query_terms:
            # Fallback to simple matching
            return 0
        
        # Exact name match
        name_normalized = name_lower.replace("_", " ").replace("-", " ")
        query_normalized = " ".join(query_terms)
        if name_lower == query_normalized or name_normalized == query_normalized:
            return 100.0
        
        score = 0.0
        
        # Count term matches in name
        name_matches = sum(1 for term in query_terms if term in name_lower)
        if name_matches == len(query_terms):
            score = 80.0  # All terms in name
        elif name_matches > 0:
            score = 60.0 * (name_matches / len(query_terms))  # Partial match
        
        # Count term matches in description
        desc_matches = sum(1 for term in query_terms if term in desc_lower)
        if desc_matches == len(query_terms):
            score = max(score, 40.0)  # All terms in description
        elif desc_matches > 0:
            score = max(score, 20.0 * (desc_matches / len(query_terms)))  # Partial match
        
        # Category match (bonus)
        if category_lower:
            category_matches = sum(1 for term in query_terms if term in category_lower)
            if category_matches > 0:
                score += 15.0 * (category_matches / len(query_terms))
        
        return min(score, 100.0)  # Cap at 100
    
    def _extract_description(self, content: str) -> Optional[str]:
        """Extract description from docstring."""
        # Look for module docstring
        if '"""' in content:
            parts = content.split('"""')
            if len(parts) >= 2:
                docstring = parts[1].strip()
                # Take first line or first 100 chars
                return docstring.split('\n')[0][:100]
        return None
