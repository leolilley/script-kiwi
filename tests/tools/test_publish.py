"""
Tests for publish tool.
"""

import pytest
import json
from unittest.mock import Mock
from pathlib import Path

from script_kiwi.tools.publish import PublishTool


class TestPublishTool:
    """Tests for PublishTool"""
    
    def test_tool_initialization(self, mock_script_registry):
        """Test tool initialization"""
        tool = PublishTool()
        assert hasattr(tool, 'registry')
        assert hasattr(tool, 'resolver')
    
    @pytest.mark.asyncio
    async def test_publish_script_success(self, mock_script_registry, tmp_path):
        """Test publishing a script successfully"""
        from unittest.mock import AsyncMock
        tool = PublishTool()
        tool.registry = mock_script_registry
        
        # Create a test script file
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('def execute(params): return {"status": "success"}')
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        
        from unittest.mock import AsyncMock as AsyncMock2
        mock_script_registry.publish_script = AsyncMock2(return_value={
            'script_id': 'script-123',
            'version_id': 'version-456',
            'version': '1.0.0',
            'status': 'published'
        })
        
        result = await tool.execute({
            'script_name': 'test_script',
            'version': '1.0.0',
            'category': 'scraping'
        })
        
        result_data = json.loads(result)
        assert result_data['status'] == 'published'
        assert result_data['version'] == '1.0.0'
        assert 'script_id' in result_data
        mock_script_registry.publish_script.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_script_not_found_locally(self, mock_script_registry):
        """Test publishing script that doesn't exist locally"""
        from unittest.mock import AsyncMock
        tool = PublishTool()
        tool.registry = mock_script_registry
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'registry',
            'path': None
        })
        
        result = await tool.execute({
            'script_name': 'remote_script',
            'version': '1.0.0'
        })
        
        result_data = json.loads(result)
        assert 'error' in result_data
        assert 'not found locally' in result_data['error'].lower()
    
    @pytest.mark.asyncio
    async def test_publish_invalid_version(self, mock_script_registry):
        """Test publishing with invalid semver version"""
        tool = PublishTool()
        
        result = await tool.execute({
            'script_name': 'test_script',
            'version': 'invalid-version'
        })
        
        result_data = json.loads(result)
        assert 'error' in result_data
        assert 'Invalid semver' in result_data['error']
    
    @pytest.mark.asyncio
    async def test_publish_dynamic_category(self, mock_script_registry, tmp_path):
        """Test publishing with dynamic category name"""
        from unittest.mock import AsyncMock
        tool = PublishTool()
        tool.registry = mock_script_registry
        
        # Create a test script file
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('def execute(params): return {"status": "success"}')
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        
        from unittest.mock import AsyncMock as AsyncMock2
        mock_script_registry.publish_script = AsyncMock2(return_value={
            'script_id': 'script-123',
            'version_id': 'version-456',
            'version': '1.0.0',
            'status': 'published'
        })
        
        result = await tool.execute({
            'script_name': 'test_script',
            'version': '1.0.0',
            'category': 'data-processing'  # Dynamic category
        })
        
        result_data = json.loads(result)
        assert result_data['status'] == 'published'
        # Verify dynamic category was passed
        call_args = mock_script_registry.publish_script.call_args
        assert call_args[1]['category'] == 'data-processing'
    
    @pytest.mark.asyncio
    async def test_publish_custom_category(self, mock_script_registry, tmp_path):
        """Test publishing with custom category name"""
        from unittest.mock import AsyncMock
        tool = PublishTool()
        tool.registry = mock_script_registry
        
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('def execute(params): pass')
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        
        from unittest.mock import AsyncMock as AsyncMock2
        mock_script_registry.publish_script = AsyncMock2(return_value={
            'script_id': 'script-123',
            'version_id': 'version-456',
            'version': '1.0.0'
        })
        
        result = await tool.execute({
            'script_name': 'test_script',
            'version': '1.0.0',
            'category': 'custom-category'  # Custom category
        })
        
        result_data = json.loads(result)
        assert result_data['status'] == 'published'
        # Verify custom category was accepted
        call_args = mock_script_registry.publish_script.call_args
        assert call_args[1]['category'] == 'custom-category'
    
    @pytest.mark.asyncio
    async def test_publish_defaults_to_utility(self, mock_script_registry, tmp_path):
        """Test publishing without category defaults to utility"""
        from unittest.mock import AsyncMock
        tool = PublishTool()
        tool.registry = mock_script_registry
        
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('def execute(params): pass')
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        
        from unittest.mock import AsyncMock as AsyncMock2
        mock_script_registry.publish_script = AsyncMock2(return_value={
            'script_id': 'script-123',
            'version_id': 'version-456',
            'version': '1.0.0'
        })
        
        result = await tool.execute({
            'script_name': 'test_script',
            'version': '1.0.0'
            # No category specified
        })
        
        result_data = json.loads(result)
        assert result_data['status'] == 'published'
        # Should default to utility
        call_args = mock_script_registry.publish_script.call_args
        assert call_args[1]['category'] == 'utility'
    
    @pytest.mark.asyncio
    async def test_publish_with_subcategory(self, mock_script_registry, tmp_path):
        """Test publishing script with explicit subcategory"""
        from unittest.mock import AsyncMock
        tool = PublishTool()
        tool.registry = mock_script_registry
        
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('def execute(params): pass')
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        
        from unittest.mock import AsyncMock as AsyncMock2
        mock_script_registry.publish_script = AsyncMock2(return_value={
            'script_id': 'script-123',
            'version_id': 'version-456',
            'version': '1.0.0'
        })
        
        result = await tool.execute({
            'script_name': 'test_script',
            'version': '1.0.0',
            'category': 'scraping',
            'subcategory': 'google-maps'
        })
        
        result_data = json.loads(result)
        assert result_data['status'] == 'published'
        # Verify subcategory was passed
        call_args = mock_script_registry.publish_script.call_args
        assert call_args[1]['category'] == 'scraping'
        assert call_args[1]['subcategory'] == 'google-maps'
    
    @pytest.mark.asyncio
    async def test_publish_auto_detect_subcategory(self, mock_script_registry, tmp_path):
        """Test publishing script with auto-detected subcategory from path"""
        from unittest.mock import AsyncMock
        tool = PublishTool()
        tool.registry = mock_script_registry
        
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('def execute(params): pass')
        
        # Resolver returns subcategory from path
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'scraping',
            'subcategory': 'google-maps'  # Auto-detected from path
        })
        
        from unittest.mock import AsyncMock as AsyncMock2
        mock_script_registry.publish_script = AsyncMock2(return_value={
            'script_id': 'script-123',
            'version_id': 'version-456',
            'version': '1.0.0'
        })
        
        result = await tool.execute({
            'script_name': 'test_script',
            'version': '1.0.0'
            # No category/subcategory specified - should auto-detect
        })
        
        result_data = json.loads(result)
        assert result_data['status'] == 'published'
        # Verify auto-detected subcategory was passed
        call_args = mock_script_registry.publish_script.call_args
        assert call_args[1]['category'] == 'scraping'
        assert call_args[1]['subcategory'] == 'google-maps'
    
    @pytest.mark.asyncio
    async def test_publish_lib_category(self, mock_script_registry, tmp_path):
        """Test publishing script with lib category"""
        from unittest.mock import AsyncMock
        tool = PublishTool()
        tool.registry = mock_script_registry
        
        script_file = tmp_path / 'youtube_utils.py'
        script_file.write_text('def extract_video_id(url): pass')
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'lib',
            'subcategory': None
        })
        
        from unittest.mock import AsyncMock as AsyncMock2
        mock_script_registry.publish_script = AsyncMock2(return_value={
            'script_id': 'script-123',
            'version_id': 'version-456',
            'version': '1.0.0'
        })
        
        result = await tool.execute({
            'script_name': 'youtube_utils',
            'version': '1.0.0',
            'category': 'lib'
        })
        
        result_data = json.loads(result)
        assert result_data['status'] == 'published'
        # Verify lib category was accepted
        call_args = mock_script_registry.publish_script.call_args
        assert call_args[1]['category'] == 'lib'
        assert call_args[1].get('subcategory') is None
    
    @pytest.mark.asyncio
    async def test_publish_any_category_name(self, mock_script_registry, tmp_path):
        """Test publishing with any category name (no restrictions)"""
        from unittest.mock import AsyncMock
        tool = PublishTool()
        tool.registry = mock_script_registry
        
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('def execute(params): pass')
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        
        from unittest.mock import AsyncMock as AsyncMock2
        mock_script_registry.publish_script = AsyncMock2(return_value={
            'script_id': 'script-123',
            'version_id': 'version-456',
            'version': '1.0.0'
        })
        
        # Test various category names that should all work
        test_categories = [
            'my-custom-category',
            'api-integration',
            'data-pipeline',
            'ml-models',
            'web-scraping-tools',
            'lib'  # Library category
        ]
        
        for category in test_categories:
            result = await tool.execute({
                'script_name': 'test_script',
                'version': '1.0.0',
                'category': category
            })
            
            result_data = json.loads(result)
            assert result_data['status'] == 'published'
            # Verify category was accepted
            call_args = mock_script_registry.publish_script.call_args
            assert call_args[1]['category'] == category
    
    @pytest.mark.asyncio
    async def test_publish_subcategory_override(self, mock_script_registry, tmp_path):
        """Test that explicit subcategory overrides auto-detected one"""
        from unittest.mock import AsyncMock
        tool = PublishTool()
        tool.registry = mock_script_registry
        
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('def execute(params): pass')
        
        # Resolver returns one subcategory
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'scraping',
            'subcategory': 'google-maps'  # Auto-detected
        })
        
        from unittest.mock import AsyncMock as AsyncMock2
        mock_script_registry.publish_script = AsyncMock2(return_value={
            'script_id': 'script-123',
            'version_id': 'version-456',
            'version': '1.0.0'
        })
        
        result = await tool.execute({
            'script_name': 'test_script',
            'version': '1.0.0',
            'category': 'scraping',
            'subcategory': 'linkedin'  # Explicit override
        })
        
        result_data = json.loads(result)
        assert result_data['status'] == 'published'
        # Verify explicit subcategory was used, not auto-detected
        call_args = mock_script_registry.publish_script.call_args
        assert call_args[1]['category'] == 'scraping'
        assert call_args[1]['subcategory'] == 'linkedin'

