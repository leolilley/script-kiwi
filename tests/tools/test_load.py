"""
Tests for load tool.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from script_kiwi.tools.load import LoadTool


class TestLoadTool:
    """Tests for LoadTool"""
    
    def test_tool_initialization(self, mock_script_registry):
        """Test tool initialization"""
        tool = LoadTool()
        assert hasattr(tool, 'registry')
        assert hasattr(tool, 'resolver')
    
    @pytest.mark.asyncio
    async def test_load_script_from_registry(self, mock_script_registry, mock_supabase):
        """Test loading script from registry"""
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        # Mock script in registry
        mock_script = {
            'name': 'google_maps_leads',
            'category': 'scraping',
            'description': 'Scrape leads from Google Maps',
            'version': '1.0.0',
            'content': 'def execute(params): return {"status": "success"}',
            'module_path': 'execution.scraping.google_maps_leads',
            'dependencies': [],
            'required_env_vars': ['APIFY_API_TOKEN']
        }
        
        mock_script_registry.get_script = Mock(return_value=mock_script)
        
        # Mock resolver to return registry location
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'registry',
            'path': None,
            'registry_data': mock_script
        })
        
        result = await tool.execute({
            'script_name': 'google_maps_leads',
            'sections': ['all']
        })
        
        result_data = json.loads(result)
        assert result_data['script']['name'] == 'google_maps_leads'
        assert result_data['script']['category'] == 'scraping'
        assert result_data['script']['source'] == 'registry'
    
    @pytest.mark.asyncio
    async def test_load_script_not_found(self, mock_script_registry):
        """Test loading non-existent script"""
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': None,
            'path': None
        })
        # get_script is async, so use AsyncMock
        mock_script_registry.get_script = AsyncMock(return_value=None)
        
        result = await tool.execute({
            'script_name': 'nonexistent_script',
            'sections': ['all']
        })
        
        result_data = json.loads(result)
        assert 'error' in result_data
        assert 'not found' in result_data['error'].lower()
    
    @pytest.mark.asyncio
    async def test_load_script_download_to_user(self, mock_script_registry, mock_supabase, tmp_path):
        """Test loading script with download_to_user option"""
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        mock_script = {
            'name': 'test_script',
            'category': 'scraping',
            'content': 'def execute(params): pass',
            'version': '1.0.0'
        }
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'registry',
            'path': None,
            'registry_data': mock_script
        })
        tool.resolver.download_to_user_space = Mock(return_value=tmp_path / 'test_script.py')
        
        result = await tool.execute({
            'script_name': 'test_script',
            'download_to_user': True
        })
        
        result_data = json.loads(result)
        assert 'downloaded_to' in result_data
        tool.resolver.download_to_user_space.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_load_script_dynamic_category(self, mock_script_registry, tmp_path):
        """Test loading script with dynamic category"""
        from unittest.mock import AsyncMock
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        mock_script = {
            'name': 'api_integration',
            'category': 'data-processing',  # Dynamic category
            'description': 'API integration script',
            'version': '1.0.0',
            'content': 'def execute(params): pass',
            'module_path': 'execution.data-processing.api_integration',
            'dependencies': [],
            'required_env_vars': []
        }
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'registry',
            'path': None,
            'registry_data': mock_script
        })
        
        result = await tool.execute({
            'script_name': 'api_integration',
            'sections': ['all']
        })
        
        result_data = json.loads(result)
        assert result_data['script']['name'] == 'api_integration'
        assert result_data['script']['category'] == 'data-processing'
    
    @pytest.mark.asyncio
    async def test_load_script_from_nested_directory(self, mock_script_registry, tmp_path):
        """Test loading script from nested directory structure"""
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        # Create nested directory structure
        script_dir = tmp_path / ".ai" / "scripts" / "scraping" / "google-maps"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_file = script_dir / "example.py"
        script_file.write_text("def execute(params): return {'status': 'success'}")
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'scraping'  # Extracted from path
        })
        
        result = await tool.execute({
            'script_name': 'example',
            'sections': ['all']
        })
        
        result_data = json.loads(result)
        assert result_data['script']['name'] == 'example'
        assert result_data['script']['category'] == 'scraping'
        assert result_data['script']['source'] == 'project'
    
    @pytest.mark.asyncio
    async def test_load_script_with_subcategory(self, mock_script_registry, tmp_path):
        """Test loading script with subcategory from registry"""
        from unittest.mock import AsyncMock
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        mock_script = {
            'name': 'google_maps_scraper',
            'category': 'scraping',
            'subcategory': 'google-maps',  # Subcategory
            'description': 'Google Maps scraper',
            'version': '1.0.0',
            'content': 'def execute(params): pass'
        }
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'registry',
            'path': None,
            'registry_data': mock_script
        })
        tool.resolver.download_to_user_space = Mock(return_value=tmp_path / 'test_script.py')
        
        result = await tool.execute({
            'script_name': 'google_maps_scraper',
            'download_to_user': True
        })
        
        result_data = json.loads(result)
        assert result_data['script']['category'] == 'scraping'
        # Verify subcategory was passed to download
        call_args = tool.resolver.download_to_user_space.call_args
        assert call_args[1]['category'] == 'scraping'
        assert call_args[1]['subcategory'] == 'google-maps'
    
    def test_tool_initialization_with_project_path(self):
        """Test tool initialization with project_path"""
        project_path = "/tmp/test_project"
        tool = LoadTool(project_path=project_path)
        assert tool.project_path == Path(project_path)
        assert tool.resolver.project_root == Path(project_path)
    
    @pytest.mark.asyncio
    async def test_load_with_project_path(self, mock_script_registry, tmp_path):
        """Test loading script with project_path parameter"""
        project_path = tmp_path / "project"
        project_scripts = project_path / ".ai" / "scripts" / "extraction"
        project_scripts.mkdir(parents=True)
        
        script_file = project_scripts / "test_script.py"
        script_file.write_text("def execute(params): return {'status': 'success'}")
        
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'extraction'
        })
        
        result = await tool.execute({
            'script_name': 'test_script',
            'project_path': str(project_path)
        })
        
        # Verify project_path was set
        assert tool.project_path == project_path
        assert tool.resolver.project_root == project_path
        
        result_data = json.loads(result)
        assert result_data['script']['name'] == 'test_script'
        assert result_data['script']['source'] == 'project'
    
    @pytest.mark.asyncio
    async def test_load_extracts_metadata_from_local_script(self, mock_script_registry, tmp_path):
        """Test that load tool extracts metadata from local script files."""
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        # Create a script with metadata
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
"""
This is a test script that scrapes data.

It uses external APIs to fetch information.
"""
import requests
from dotenv import load_dotenv
import os

load_dotenv()

def execute(params):
    """Execute the script."""
    api_key = os.getenv('API_KEY')
    return {"status": "success"}
''')
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'scraping'
        })
        
        result = await tool.execute({
            'script_name': 'test_script',
            'sections': ['all']
        })
        
        result_data = json.loads(result)
        
        # Should extract description from docstring
        assert 'description' in result_data['script']
        description = result_data['script']['description']
        assert description is not None
        assert 'test script' in description.lower()
        
        # Should extract dependencies
        assert 'dependencies' in result_data
        deps = result_data['dependencies']
        assert 'packages' in deps
        # Should include requests and dotenv
        package_names = {p['name'] if isinstance(p, dict) else p for p in deps['packages']}
        assert 'requests' in package_names or any('requests' in str(p) for p in deps['packages'])
        
        # Should extract env vars
        assert 'env_vars' in deps
        assert 'API_KEY' in deps['env_vars']
        
        # Should extract tech stack
        assert 'tech_stack' in result_data['script']
        tech_stack = result_data['script']['tech_stack']
        assert isinstance(tech_stack, list)
    
    @pytest.mark.asyncio
    async def test_load_extracts_input_schema_from_argparse(self, mock_script_registry, tmp_path):
        """Test that load tool extracts input schema from argparse scripts."""
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        # Create a script with argparse
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
"""
Test script with argparse.
"""
import argparse

def main():
    parser = argparse.ArgumentParser(description="Test script")
    parser.add_argument('--search-term', dest='search_term', required=True,
                       help='Search term to use')
    parser.add_argument('--location', required=True,
                       help='Location to search')
    parser.add_argument('--count', type=int, default=100,
                       help='Number of results')
    args = parser.parse_args()
    return {"status": "success"}

if __name__ == '__main__':
    main()
''')
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'scraping'
        })
        
        result = await tool.execute({
            'script_name': 'test_script',
            'sections': ['all']
        })
        
        result_data = json.loads(result)
        
        # Should extract input schema
        assert 'inputs' in result_data
        inputs = result_data['inputs']
        
        # Should have extracted argparse arguments
        assert 'search_term' in inputs or len(inputs) > 0
        
        # If search_term was extracted, check its properties
        if 'search_term' in inputs:
            assert inputs['search_term']['required'] is True
            assert 'description' in inputs['search_term']

