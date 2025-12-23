"""
Tests for search tool.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

from script_kiwi.tools.search import SearchTool


class TestSearchTool:
    """Tests for SearchTool"""
    
    def test_tool_initialization(self, mock_script_registry):
        """Test tool initialization"""
        tool = SearchTool()
        assert hasattr(tool, 'registry')
        assert hasattr(tool, 'resolver')
    
    @pytest.mark.asyncio
    async def test_search_with_query(self, mock_script_registry, mock_supabase):
        """Test search with a query"""
        tool = SearchTool()
        tool.registry = mock_script_registry
        
        # Mock registry search
        mock_script_registry.search_scripts = AsyncMock(return_value=[
            {
                'name': 'google_maps_leads',
                'category': 'scraping',
                'description': 'Scrape leads from Google Maps',
                'rank': 0.9,
                'quality_score': 0.85,
                'latest_version': '1.0.0'
            }
        ])
        
        # Mock resolver for local search
        tool.resolver.project_scripts = Path('/tmp/test/.ai/scripts')
        tool.resolver.user_scripts = Path('/tmp/test/.script-kiwi/scripts')
        
        result = await tool.execute({
            'query': 'google maps',
            'category': 'scraping',
            'limit': 10
        })
        
        result_data = json.loads(result)
        assert result_data['query'] == 'google maps'
        assert result_data['results_count'] > 0
        assert 'results' in result_data
    
    @pytest.mark.asyncio
    async def test_search_empty_query(self, mock_script_registry):
        """Test search with empty query"""
        tool = SearchTool()
        tool.registry = mock_script_registry
        
        result = await tool.execute({'query': ''})
        result_data = json.loads(result)
        
        assert 'error' in result_data
        assert 'Query is required' in result_data['error']
    
    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, mock_script_registry, mock_supabase):
        """Test search with category filter"""
        tool = SearchTool()
        tool.registry = mock_script_registry
        
        mock_script_registry.search_scripts = AsyncMock(return_value=[])
        tool.resolver.project_scripts = Path('/tmp/test/.ai/scripts')
        tool.resolver.user_scripts = Path('/tmp/test/.script-kiwi/scripts')
        
        result = await tool.execute({
            'query': 'email',
            'category': 'enrichment',
            'limit': 5
        })
        
        result_data = json.loads(result)
        assert result_data['query'] == 'email'
        # Verify category filter was passed
        mock_script_registry.search_scripts.assert_called_once()
        call_args = mock_script_registry.search_scripts.call_args
        assert call_args[1]['category'] == 'enrichment'
    
    def test_tool_initialization_with_project_path(self):
        """Test tool initialization with project_path"""
        project_path = "/tmp/test_project"
        tool = SearchTool(project_path=project_path)
        assert tool.project_path == Path(project_path)
        assert tool.resolver.project_root == Path(project_path)
    
    @pytest.mark.asyncio
    async def test_search_with_project_path(self, mock_script_registry, mock_supabase, tmp_path):
        """Test search with project_path parameter"""
        project_path = tmp_path / "project"
        project_scripts = project_path / ".ai" / "scripts" / "extraction"
        project_scripts.mkdir(parents=True)
        
        script_file = project_scripts / "test_script.py"
        script_file.write_text("# Test script for extraction")
        
        tool = SearchTool()
        tool.registry = mock_script_registry
        
        # Mock registry search
        mock_script_registry.search_scripts = AsyncMock(return_value=[])
        
        result = await tool.execute({
            'query': 'extraction',
            'project_path': str(project_path)
        })
        
        # Verify project_path was set
        assert tool.project_path == project_path
        assert tool.resolver.project_root == project_path
        
        result_data = json.loads(result)
        assert result_data['query'] == 'extraction'
        assert 'results' in result_data

