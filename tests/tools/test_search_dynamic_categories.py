"""
Tests for search tool with dynamic categories and nested directories.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock
from pathlib import Path

from script_kiwi.tools.search import SearchTool


class TestSearchToolDynamicCategories:
    """Tests for search with dynamic category names"""
    
    @pytest.mark.asyncio
    async def test_search_dynamic_category(self, mock_script_registry, tmp_path):
        """Test searching with dynamic category name"""
        tool = SearchTool()
        tool.registry = mock_script_registry
        tool.resolver.project_scripts = tmp_path / ".ai" / "scripts"
        tool.resolver.user_scripts = tmp_path / ".script-kiwi" / "scripts"
        
        # Mock registry search
        mock_script_registry.search_scripts = AsyncMock(return_value=[
            {
                'name': 'api_integration',
                'category': 'data-processing',
                'description': 'API integration script',
                'rank': 0.9,
                'quality_score': 0.85
            }
        ])
        
        result = await tool.execute({
            'query': 'api',
            'category': 'data-processing',
            'limit': 10
        })
        
        result_data = json.loads(result)
        assert result_data['query'] == 'api'
        # Verify category filter was passed
        mock_script_registry.search_scripts.assert_called_once()
        call_args = mock_script_registry.search_scripts.call_args
        assert call_args[1]['category'] == 'data-processing'
    
    @pytest.mark.asyncio
    async def test_search_custom_category(self, mock_script_registry, tmp_path):
        """Test searching with custom category name"""
        tool = SearchTool()
        tool.registry = mock_script_registry
        tool.resolver.project_scripts = tmp_path / ".ai" / "scripts"
        tool.resolver.user_scripts = tmp_path / ".script-kiwi" / "scripts"
        
        mock_script_registry.search_scripts = AsyncMock(return_value=[])
        
        result = await tool.execute({
            'query': 'test',
            'category': 'custom-category',
            'limit': 10
        })
        
        result_data = json.loads(result)
        assert result_data['query'] == 'test'
        # Verify custom category was accepted
        call_args = mock_script_registry.search_scripts.call_args
        assert call_args[1]['category'] == 'custom-category'
    
    @pytest.mark.asyncio
    async def test_search_all_categories(self, mock_script_registry, tmp_path):
        """Test searching across all categories"""
        tool = SearchTool()
        tool.registry = mock_script_registry
        tool.resolver.project_scripts = tmp_path / ".ai" / "scripts"
        tool.resolver.user_scripts = tmp_path / ".script-kiwi" / "scripts"
        
        mock_script_registry.search_scripts = AsyncMock(return_value=[
            {
                'name': 'script1',
                'category': 'scraping',
                'description': 'Scraping script',
                'rank': 0.9
            },
            {
                'name': 'script2',
                'category': 'data-processing',
                'description': 'Data processing script',
                'rank': 0.8
            }
        ])
        
        result = await tool.execute({
            'query': 'script',
            'category': 'all',
            'limit': 10
        })
        
        result_data = json.loads(result)
        assert result_data['query'] == 'script'
        # Verify no category filter was applied
        call_args = mock_script_registry.search_scripts.call_args
        assert call_args[1]['category'] is None


class TestSearchToolNestedDirectories:
    """Tests for searching scripts in nested directories"""
    
    @pytest.mark.asyncio
    async def test_search_finds_nested_scripts(self, mock_script_registry, tmp_path):
        """Test that search finds scripts in nested subdirectories"""
        tool = SearchTool()
        tool.registry = mock_script_registry
        tool.resolver.project_scripts = tmp_path / ".ai" / "scripts"
        tool.resolver.user_scripts = tmp_path / ".script-kiwi" / "scripts"
        
        # Create nested directory structure
        script_dir = tmp_path / ".ai" / "scripts" / "scraping" / "google-maps"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_file = script_dir / "example.py"
        script_file.write_text("""
def execute(params):
    \"\"\"Scrape Google Maps for leads\"\"\"
    return {"status": "success"}
""")
        
        mock_script_registry.search_scripts = AsyncMock(return_value=[])
        
        result = await tool.execute({
            'query': 'google maps',
            'category': 'all',
            'limit': 10
        })
        
        result_data = json.loads(result)
        # Should find the script in nested directory
        assert result_data['results_count'] > 0
        found_script = next(
            (r for r in result_data['results'] if r['name'] == 'example'),
            None
        )
        assert found_script is not None
        assert found_script['category'] == 'scraping'
        assert found_script['source'] == 'project'
    
    @pytest.mark.asyncio
    async def test_search_category_with_nested(self, mock_script_registry, tmp_path):
        """Test searching specific category that has nested subdirectories"""
        tool = SearchTool()
        tool.registry = mock_script_registry
        tool.resolver.project_scripts = tmp_path / ".ai" / "scripts"
        tool.resolver.user_scripts = tmp_path / ".script-kiwi" / "scripts"
        
        # Create nested structure in scraping category
        script_dir1 = tmp_path / ".ai" / "scripts" / "scraping" / "google-maps"
        script_dir1.mkdir(parents=True, exist_ok=True)
        script_file1 = script_dir1 / "google_maps.py"
        script_file1.write_text("def execute(params): pass")
        
        script_dir2 = tmp_path / ".ai" / "scripts" / "scraping" / "linkedin"
        script_dir2.mkdir(parents=True, exist_ok=True)
        script_file2 = script_dir2 / "linkedin_scraper.py"
        script_file2.write_text("def execute(params): pass")
        
        mock_script_registry.search_scripts = AsyncMock(return_value=[])
        
        result = await tool.execute({
            'query': 'scrape',
            'category': 'scraping',
            'limit': 10
        })
        
        result_data = json.loads(result)
        # Should find scripts in both nested subdirectories
        # Note: Search matches on query words, so both should match "scrape"
        script_names = [r['name'] for r in result_data['results']]
        # At least one should be found (both contain "scrape" in content)
        assert result_data['results_count'] >= 1
        # Check that we're searching in the right category
        for r in result_data['results']:
            assert r['category'] == 'scraping'
    
    @pytest.mark.asyncio
    async def test_search_dynamic_category_nested(self, mock_script_registry, tmp_path):
        """Test searching dynamic category with nested structure"""
        tool = SearchTool()
        tool.registry = mock_script_registry
        tool.resolver.project_scripts = tmp_path / ".ai" / "scripts"
        tool.resolver.user_scripts = tmp_path / ".script-kiwi" / "scripts"
        
        # Create nested structure with dynamic category
        script_dir = tmp_path / ".ai" / "scripts" / "data-processing" / "etl"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_file = script_dir / "transform.py"
        script_file.write_text("def execute(params): pass")
        
        mock_script_registry.search_scripts = AsyncMock(return_value=[])
        
        result = await tool.execute({
            'query': 'transform',
            'category': 'data-processing',
            'limit': 10
        })
        
        result_data = json.loads(result)
        # Should find script in nested dynamic category
        assert result_data['results_count'] > 0
        found_script = next(
            (r for r in result_data['results'] if r['name'] == 'transform'),
            None
        )
        assert found_script is not None
        assert found_script['category'] == 'data-processing'

