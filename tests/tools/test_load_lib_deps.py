"""
Tests for lib dependency download in load tool.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from script_kiwi.tools.load import LoadTool


class TestLoadToolLibDeps:
    """Tests for lib dependency handling in LoadTool"""
    
    @pytest.mark.asyncio
    async def test_download_lib_dependencies(self, mock_script_registry, tmp_path):
        """Test _download_lib_dependencies downloads libs to user space"""
        tool = LoadTool()
        # Use the real registry but mock its get_script method
        tool.registry = mock_script_registry
        
        # Create user lib directory (but don't create the lib files - they should be downloaded)
        user_lib_dir = tmp_path / ".script-kiwi" / "scripts" / "lib"
        user_lib_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure __init__.py exists (required for Python package)
        (user_lib_dir / "__init__.py").write_text("")
        
        # Mock lib scripts from registry
        mock_lib1 = {
            'name': 'youtube_utils',
            'content': 'def extract_video_id(): pass',
            'category': 'lib'
        }
        mock_lib2 = {
            'name': 'http_session',
            'content': 'def get_session(): pass',
            'category': 'lib'
        }
        
        async def get_script_side_effect(name):
            if name == 'youtube_utils':
                return mock_lib1
            elif name == 'http_session':
                return mock_lib2
            return None
        
        # Mock the registry's get_script method
        from unittest.mock import AsyncMock, patch
        tool.registry.get_script = AsyncMock(side_effect=get_script_side_effect)
        
        # Mock download_to_user_space - need to make it a Mock object
        download_mock = Mock(side_effect=lambda **kwargs: 
            user_lib_dir / f"{kwargs['script_name']}.py")
        tool.resolver.download_to_user_space = download_mock
        
        # Mock Path.home() to return our test tmp_path
        with patch('pathlib.Path.home', return_value=tmp_path):
            # Download lib dependencies
            await tool._download_lib_dependencies(['youtube_utils', 'http_session'])
        
        # Verify get_script was called for each lib
        assert tool.registry.get_script.call_count == 2
        # Verify download_to_user_space was called for each lib
        assert download_mock.call_count == 2
        
        # Verify correct parameters
        calls = tool.resolver.download_to_user_space.call_args_list
        assert calls[0][1]['script_name'] == 'youtube_utils'
        assert calls[0][1]['category'] == 'lib'
        assert calls[1][1]['script_name'] == 'http_session'
        assert calls[1][1]['category'] == 'lib'
    
    @pytest.mark.asyncio
    async def test_download_lib_dependencies_skips_existing(self, mock_script_registry, tmp_path):
        """Test _download_lib_dependencies skips libs that already exist"""
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        # Create user lib directory with existing lib
        user_lib_dir = tmp_path / ".script-kiwi" / "scripts" / "lib"
        user_lib_dir.mkdir(parents=True, exist_ok=True)
        (user_lib_dir / "youtube_utils.py").write_text("existing content")
        
        # Mock Path.home() to return our test home
        download_mock = Mock(side_effect=lambda **kwargs: 
            user_lib_dir / f"{kwargs['script_name']}.py")
        tool.resolver.download_to_user_space = download_mock
        
        with patch('pathlib.Path.home', return_value=tmp_path):
            # Mock get_script to return http_session
            mock_lib = {
                'name': 'http_session',
                'content': 'def get_session(): pass',
                'category': 'lib'
            }
            mock_script_registry.get_script = AsyncMock(return_value=mock_lib)
            
            # Download lib dependencies
            await tool._download_lib_dependencies(['youtube_utils', 'http_session'])
            
            # Should only download http_session (youtube_utils already exists)
            assert download_mock.call_count == 1
            call = download_mock.call_args
            assert call[1]['script_name'] == 'http_session'
    
    @pytest.mark.asyncio
    async def test_load_script_with_lib_dependencies(self, mock_script_registry, tmp_path):
        """Test loading script from registry downloads lib dependencies"""
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        mock_script = {
            'name': 'test_script',
            'category': 'test',
            'description': 'Test script',
            'version': '1.0.0',
            'content': 'def execute(params): pass',
            'module_path': 'execution.test.test_script',
            'required_libs': ['youtube_utils', 'http_session']
        }
        
        mock_lib1 = {
            'name': 'youtube_utils',
            'content': 'def extract_video_id(): pass',
            'category': 'lib'
        }
        mock_lib2 = {
            'name': 'http_session',
            'content': 'def get_session(): pass',
            'category': 'lib'
        }
        
        async def get_script_side_effect(name):
            if name == 'test_script':
                return mock_script
            elif name == 'youtube_utils':
                return mock_lib1
            elif name == 'http_session':
                return mock_lib2
            return None
        
        from unittest.mock import AsyncMock
        mock_script_registry.get_script = AsyncMock(side_effect=get_script_side_effect)
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'registry',
            'path': None,
            'registry_data': mock_script
        })
        download_mock = Mock(side_effect=lambda **kwargs: 
            tmp_path / f"{kwargs['script_name']}.py")
        tool.resolver.download_to_user_space = download_mock
        
        result = await tool.execute({
            'script_name': 'test_script',
            'download_to_user': True
        })
        
        result_data = json.loads(result)
        assert result_data['script']['name'] == 'test_script'
        assert 'downloaded_to' in result_data
        assert 'downloaded_libs' in result_data
        assert set(result_data['downloaded_libs']) == {'youtube_utils', 'http_session'}
        assert result_data['dependencies']['libs'] == ['youtube_utils', 'http_session']
    
    @pytest.mark.asyncio
    async def test_load_script_without_lib_dependencies(self, mock_script_registry):
        """Test loading script without lib dependencies"""
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        mock_script = {
            'name': 'test_script',
            'category': 'test',
            'version': '1.0.0',
            'content': 'def execute(params): pass',
            'required_libs': []
        }
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'registry',
            'path': None,
            'registry_data': mock_script
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        
        result = await tool.execute({
            'script_name': 'test_script',
            'download_to_user': True
        })
        
        result_data = json.loads(result)
        assert result_data['dependencies']['libs'] == []
        # Should not have downloaded_libs if empty
        assert 'downloaded_libs' not in result_data or result_data.get('downloaded_libs') == []
    
    @pytest.mark.asyncio
    async def test_load_script_lib_dependencies_transitive(self, mock_script_registry, tmp_path):
        """Test loading script with transitive lib dependencies (http_session -> proxy_pool)"""
        from unittest.mock import AsyncMock
        tool = LoadTool()
        tool.registry = mock_script_registry
        
        mock_script = {
            'name': 'test_script',
            'category': 'test',
            'version': '1.0.0',
            'content': 'def execute(params): pass',
            'required_libs': ['http_session']
        }
        
        # http_session depends on proxy_pool and cookie_manager
        mock_http_session = {
            'name': 'http_session',
            'content': 'def get_session(): pass',
            'category': 'lib',
            'required_libs': ['proxy_pool', 'cookie_manager']
        }
        
        mock_proxy_pool = {
            'name': 'proxy_pool',
            'content': 'class ProxyPool: pass',
            'category': 'lib'
        }
        
        mock_cookie_manager = {
            'name': 'cookie_manager',
            'content': 'class CookieManager: pass',
            'category': 'lib'
        }
        
        async def get_script_side_effect(name):
            scripts = {
                'test_script': mock_script,
                'http_session': mock_http_session,
                'proxy_pool': mock_proxy_pool,
                'cookie_manager': mock_cookie_manager
            }
            return scripts.get(name)
        
        mock_script_registry.get_script = AsyncMock(side_effect=get_script_side_effect)
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'registry',
            'path': None,
            'registry_data': mock_script
        })
        download_mock = Mock(side_effect=lambda **kwargs: 
            tmp_path / f"{kwargs['script_name']}.py")
        tool.resolver.download_to_user_space = download_mock
        
        result = await tool.execute({
            'script_name': 'test_script',
            'download_to_user': True
        })
        
        result_data = json.loads(result)
        # Should download http_session (direct dependency)
        # Note: Currently we only download direct dependencies, not transitive
        # This test verifies current behavior
        assert 'http_session' in result_data.get('downloaded_libs', [])

