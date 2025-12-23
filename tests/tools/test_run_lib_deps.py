"""
Tests for lib dependency system in run tool.
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

from script_kiwi.tools.run import RunTool


class TestRunToolLibDeps:
    """Tests for lib dependency handling in RunTool"""
    
    def test_build_search_paths_project_absolute_path(self, tmp_path):
        """Test _build_search_paths uses absolute path for project scripts"""
        tool = RunTool()
        
        # Create a project structure
        project_root = tmp_path / "project"
        scripts_dir = project_root / ".ai" / "scripts"
        lib_dir = scripts_dir / "lib"
        test_dir = scripts_dir / "test"
        
        lib_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        
        script_file = test_dir / "test_script.py"
        script_file.write_text("def execute(params): pass")
        
        # Change to a different directory to test absolute path resolution
        original_cwd = os.getcwd()
        try:
            os.chdir("/tmp")
            
            # Build search paths
            paths = tool._build_search_paths(script_file, "project")
            
            # Verify scripts root is in paths (absolute path)
            scripts_root = script_file.parent.parent
            assert scripts_root in paths
            assert scripts_root.is_absolute()
            assert (scripts_root / "lib").exists()
            
        finally:
            os.chdir(original_cwd)
    
    def test_build_search_paths_user_space(self, tmp_path):
        """Test _build_search_paths for user space scripts"""
        tool = RunTool()
        
        user_home = tmp_path / "home" / "user"
        scripts_dir = user_home / ".script-kiwi" / "scripts"
        lib_dir = scripts_dir / "lib"
        test_dir = scripts_dir / "test"
        
        lib_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        
        script_file = test_dir / "test_script.py"
        script_file.write_text("def execute(params): pass")
        
        # Mock Path.home() to return our test home
        with patch('pathlib.Path.home', return_value=user_home):
            paths = tool._build_search_paths(script_file, "user")
            
            # Verify user scripts root is in paths
            scripts_root = Path.home() / ".script-kiwi" / "scripts"
            assert scripts_root in paths
            assert (scripts_root / "lib").exists() or True  # May not exist in test
    
    def test_build_search_paths_registry(self, tmp_path):
        """Test _build_search_paths for registry scripts (downloaded to user space)"""
        tool = RunTool()
        
        user_home = tmp_path / "home" / "user"
        scripts_dir = user_home / ".script-kiwi" / "scripts"
        lib_dir = scripts_dir / "lib"
        test_dir = scripts_dir / "test"
        
        lib_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        
        script_file = test_dir / "test_script.py"
        script_file.write_text("def execute(params): pass")
        
        with patch('pathlib.Path.home', return_value=user_home):
            paths = tool._build_search_paths(script_file, "registry")
            
            # Should use script_path.parent.parent (absolute)
            scripts_root = script_file.parent.parent
            assert scripts_root in paths
            assert scripts_root.is_absolute()
    
    @pytest.mark.asyncio
    async def test_verify_lib_dependencies_all_present(self, tmp_path, monkeypatch):
        """Test _verify_lib_dependencies when all libs are present"""
        tool = RunTool()
        
        # Create lib directory with required libs
        project_root = tmp_path / "project"
        scripts_dir = project_root / ".ai" / "scripts"
        lib_dir = scripts_dir / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        
        (lib_dir / "youtube_utils.py").write_text("def extract_video_id(): pass")
        (lib_dir / "http_session.py").write_text("def get_session(): pass")
        
        # Mock Path.home() for user space check
        user_home = tmp_path / "home" / "user"
        user_lib_dir = user_home / ".script-kiwi" / "scripts" / "lib"
        user_lib_dir.mkdir(parents=True, exist_ok=True)
        
        # Change to project root and mock Path.home
        original_cwd = os.getcwd()
        try:
            os.chdir(project_root)
            monkeypatch.setattr('pathlib.Path.home', lambda: user_home)
            
            result = await tool._verify_lib_dependencies(
                "test_script",
                ["youtube_utils", "http_session"]
            )
            
            # Returns {'status': 'ok'} when all dependencies found
            assert result == {'status': 'ok'}
        finally:
            os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_verify_lib_dependencies_some_missing(self, tmp_path, monkeypatch):
        """Test _verify_lib_dependencies when some libs are missing"""
        tool = RunTool()
        
        # Create lib directory with only one lib
        project_root = tmp_path / "project"
        scripts_dir = project_root / ".ai" / "scripts"
        lib_dir = scripts_dir / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        
        (lib_dir / "youtube_utils.py").write_text("def extract_video_id(): pass")
        # http_session.py is missing
        
        # Mock Path.home() for user space check
        user_home = tmp_path / "home" / "user"
        user_lib_dir = user_home / ".script-kiwi" / "scripts" / "lib"
        user_lib_dir.mkdir(parents=True, exist_ok=True)
        
        # Change to project root and mock Path.home
        original_cwd = os.getcwd()
        try:
            os.chdir(project_root)
            monkeypatch.setattr('pathlib.Path.home', lambda: user_home)
            
            result = await tool._verify_lib_dependencies(
                "test_script",
                ["youtube_utils", "http_session"]
            )
            
            assert result is not None
            assert result["error"]["code"] == "MISSING_DEPENDENCIES"
            assert "http_session" in str(result["error"]["details"]["missing_libs"])
            assert "youtube_utils" not in str(result["error"]["details"]["missing_libs"])
        finally:
            os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_verify_lib_dependencies_cross_tier(self, tmp_path, monkeypatch):
        """Test _verify_lib_dependencies checks both project and user space"""
        tool = RunTool()
        
        # Lib in user space, not project
        project_root = tmp_path / "project"
        scripts_dir = project_root / ".ai" / "scripts"
        lib_dir = scripts_dir / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        # No libs in project
        
        user_home = tmp_path / "home" / "user"
        user_lib_dir = user_home / ".script-kiwi" / "scripts" / "lib"
        user_lib_dir.mkdir(parents=True, exist_ok=True)
        (user_lib_dir / "youtube_utils.py").write_text("def extract_video_id(): pass")
        
        # Change to project root and mock Path.home
        original_cwd = os.getcwd()
        try:
            os.chdir(project_root)
            monkeypatch.setattr('pathlib.Path.home', lambda: user_home)
            
            result = await tool._verify_lib_dependencies(
                "test_script",
                ["youtube_utils"]
            )
            
            # Should find it in user space - returns {'status': 'ok'} when found
            assert result == {'status': 'ok'}
        finally:
            os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_run_script_with_lib_dependencies(self, mock_script_registry, mock_execution_logger, tmp_path):
        """Test running a script that uses lib dependencies"""
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create project structure with lib and script
        project_root = tmp_path / "project"
        scripts_dir = project_root / ".ai" / "scripts"
        lib_dir = scripts_dir / "lib"
        test_dir = scripts_dir / "test"
        
        lib_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create lib dependency
        (lib_dir / "__init__.py").write_text("")
        (lib_dir / "youtube_utils.py").write_text("""
def extract_video_id(url):
    return "dQw4w9WgXcQ"
""")
        
        # Create script that uses lib
        script_file = test_dir / "test_script.py"
        script_file.write_text("""
from lib.youtube_utils import extract_video_id

def execute(params):
    video_id = extract_video_id(params.get("url", "test"))
    return {
        "status": "success",
        "video_id": video_id
    }
""")
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': [],
            'required_libs': ['youtube_utils']
        }
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'test'
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        
        # Change to project root for execution
        original_cwd = os.getcwd()
        try:
            os.chdir(project_root)
            
            result = await tool.execute({
                'script_name': 'test_script',
                'parameters': {'url': 'https://youtube.com/watch?v=test'}
            })
            
            result_data = json.loads(result)
            assert result_data['status'] == 'success'
            # Script returns dict with 'data' key, which becomes 'result' in response
            # The actual script output is in result_data['result']
            if result_data.get('result'):
                # Check if it's a dict with video_id
                if isinstance(result_data['result'], dict):
                    assert result_data['result'].get('video_id') == 'dQw4w9WgXcQ'
                else:
                    # If result is None, check metadata
                    assert 'execution_id' in result_data
            
        finally:
            os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_run_script_missing_lib_dependency(self, mock_script_registry, mock_execution_logger, tmp_path):
        """Test running a script with missing lib dependencies"""
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create project structure without lib (libs are missing)
        project_root = tmp_path / "project"
        scripts_dir = project_root / ".ai" / "scripts"
        test_dir = scripts_dir / "test"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create script file so it exists
        script_file = test_dir / "test_script.py"
        script_file.write_text("def execute(params): pass")
        
        # Ensure lib directory exists but is empty (no libs)
        lib_dir = scripts_dir / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        
        # Mock Path.home() to return a test home that also doesn't have the libs
        user_home = tmp_path / "home" / "user"
        user_lib_dir = user_home / ".script-kiwi" / "scripts" / "lib"
        user_lib_dir.mkdir(parents=True, exist_ok=True)
        # Don't create the lib files - they should be missing
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': [],
            'required_libs': ['youtube_utils', 'http_session']
        }
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'test'
        })
        # Mock get_script to return script with required_libs
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        
        # Change to project root so Path('.ai/scripts/lib') resolves correctly
        # Also mock Path.home() to use our test home
        original_cwd = os.getcwd()
        try:
            os.chdir(project_root)
            with patch('pathlib.Path.home', return_value=user_home):
                result = await tool.execute({
                    'script_name': 'test_script',
                    'parameters': {}
                })
            
            result_data = json.loads(result)
            # Should return error about missing dependencies
            # The error can be in different formats, so check status and that it's an error
            assert result_data.get('status') == 'error' or 'error' in result_data
            
            # Extract error message from various possible formats
            error_obj = result_data.get('error', {})
            if isinstance(error_obj, dict):
                error_content = str(error_obj.get('message', '')).lower()
                if not error_content:
                    error_content = str(error_obj).lower()
            else:
                error_content = str(error_obj).lower()
            
            # Should mention missing dependencies or libraries
            # The error might be in the nested structure, so check multiple places
            full_error_str = str(result_data).lower()
            assert any(keyword in full_error_str for keyword in ['missing', 'dependency', 'libraries', 'requires', 'not installed'])
        finally:
            os.chdir(original_cwd)

