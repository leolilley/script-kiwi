"""
Tests for default output saving behavior in run tool.

Tests cover:
- Default behavior: always saves to ~/.script-kiwi/outputs/{script_name}/ (or $SCRIPT_KIWI_HOME/outputs/{script_name}/)
- Override with _save_output=False
- Override with _output_file custom path
- File organization in script-specific folders
- Auto-save to ~/.script-kiwi/tmp/ when result is too large and save_output=False
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from script_kiwi.tools.run import RunTool


class TestDefaultOutputSaving:
    """Tests for default output saving behavior."""
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    @patch('script_kiwi.tools.run.log_execution_start')
    async def test_default_saves_to_script_folder(
        self, mock_log_start, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that outputs are saved to ~/.script-kiwi/outputs/{script_name}/ by default."""
        # Set SCRIPT_KIWI_HOME to tmp_path
        monkeypatch.setenv('SCRIPT_KIWI_HOME', str(tmp_path / '.script-kiwi'))
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        project_path = tmp_path / 'project'
        project_path.mkdir()
        script_kiwi_home = tmp_path / '.script-kiwi'
        (script_kiwi_home / 'outputs').mkdir(parents=True)
        
        tool = RunTool(project_path=str(project_path))
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create a test script
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    return {
        "status": "success",
        "data": {"result": "test data", "count": 5},
        "metadata": {"duration_sec": 0.5}
    }
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'utility'
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        mock_log_execution.return_value = {'execution_id': 'analytics-123'}
        mock_log_start.return_value = 'start-123'
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {}
        })
        
        result_data = json.loads(result)
        
        # Should have output file in response
        assert '_output_file' in result_data.get('result', {})
        output_file = Path(result_data['result']['_output_file'])
        
        # Should be in ~/.script-kiwi/outputs/test_script/ folder
        assert 'outputs' in str(output_file)
        assert 'test_script' in str(output_file)
        assert '.script-kiwi' in str(output_file) or str(script_kiwi_home) in str(output_file)
        assert output_file.exists()
        
        # File should contain the result data
        with open(output_file, 'r') as f:
            file_data = json.load(f)
            assert file_data['result'] == 'test data'
            assert file_data['count'] == 5
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    @patch('script_kiwi.tools.run.log_execution_start')
    async def test_save_output_false_disables_saving(
        self, mock_log_start, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that _save_output=False disables saving."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        project_path = tmp_path / 'project'
        project_path.mkdir()
        
        tool = RunTool(project_path=str(project_path))
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create a test script with small result
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    return {
        "status": "success",
        "data": {"result": "small data"},
        "metadata": {"duration_sec": 0.5}
    }
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'utility'
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        mock_log_execution.return_value = {'execution_id': 'analytics-123'}
        mock_log_start.return_value = 'start-123'
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {
                '_save_output': False
            }
        })
        
        result_data = json.loads(result)
        
        # Should NOT have output file for small results when save_output=False
        result_obj = result_data.get('result', {})
        assert '_output_file' not in result_obj or result_obj.get('_output_file') is None
        
        # Result should still be in response
        assert 'result' in result_obj or 'data' in result_obj
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    @patch('script_kiwi.tools.run.log_execution_start')
    async def test_save_output_false_auto_saves_large_results(
        self, mock_log_start, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that large results are auto-saved to ~/.script-kiwi/tmp/ even when _save_output=False."""
        # Set SCRIPT_KIWI_HOME to tmp_path
        monkeypatch.setenv('SCRIPT_KIWI_HOME', str(tmp_path / '.script-kiwi'))
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        project_path = tmp_path / 'project'
        project_path.mkdir()
        script_kiwi_home = tmp_path / '.script-kiwi'
        (script_kiwi_home / 'tmp').mkdir(parents=True)
        
        tool = RunTool(project_path=str(project_path))
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create a script that returns a very large result (>1MB)
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    # Create a very large data array (>1MB)
    large_data = [{"item": i, "data": "x" * 10000} for i in range(200)]
    return {
        "status": "success",
        "data": {"items": large_data},
        "metadata": {"duration_sec": 1.0}
    }
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'utility'
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        mock_log_execution.return_value = {'execution_id': 'analytics-123'}
        mock_log_start.return_value = 'start-123'
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {
                '_save_output': False
            }
        })
        
        result_data = json.loads(result)
        
        # Should have output file (auto-saved due to size)
        result_obj = result_data.get('result', {})
        assert '_output_file' in result_obj
        output_file = Path(result_obj['_output_file'])
        
        # Should be in ~/.script-kiwi/tmp/ (not outputs/)
        assert 'tmp' in str(output_file)
        assert '.script-kiwi' in str(output_file) or str(script_kiwi_home) in str(output_file)
        assert output_file.exists()
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    @patch('script_kiwi.tools.run.log_execution_start')
    async def test_custom_output_file_path(
        self, mock_log_start, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that _output_file parameter overrides default path."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        project_path = tmp_path / 'project'
        project_path.mkdir()
        (project_path / 'custom' / 'output').mkdir(parents=True)
        
        tool = RunTool(project_path=str(project_path))
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create a test script
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    return {
        "status": "success",
        "data": {"result": "test data"},
        "metadata": {"duration_sec": 0.5}
    }
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'utility'
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        mock_log_execution.return_value = {'execution_id': 'analytics-123'}
        mock_log_start.return_value = 'start-123'
        
        custom_path = 'custom/output/my_results.json'
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {
                '_output_file': custom_path
            }
        })
        
        result_data = json.loads(result)
        
        # Should have output file at custom path
        assert '_output_file' in result_data.get('result', {})
        output_file = Path(result_data['result']['_output_file'])
        
        # Should be at the custom path (relative to project)
        assert 'custom' in str(output_file)
        assert 'output' in str(output_file)
        assert 'my_results.json' in str(output_file)
        assert output_file.exists()
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    @patch('script_kiwi.tools.run.log_execution_start')
    async def test_script_folder_created_automatically(
        self, mock_log_start, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that script-specific folder is created automatically."""
        # Set SCRIPT_KIWI_HOME to tmp_path
        monkeypatch.setenv('SCRIPT_KIWI_HOME', str(tmp_path / '.script-kiwi'))
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        project_path = tmp_path / 'project'
        project_path.mkdir()
        # Don't create outputs folder - should be created automatically
        
        tool = RunTool(project_path=str(project_path))
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create a test script
        script_file = tmp_path / 'my_custom_script.py'
        script_file.write_text('''
def execute(params):
    return {
        "status": "success",
        "data": {"result": "test"},
        "metadata": {"duration_sec": 0.5}
    }
''')
        
        mock_script = {
            'name': 'my_custom_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'utility'
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        mock_log_execution.return_value = {'execution_id': 'analytics-123'}
        mock_log_start.return_value = 'start-123'
        
        result = await tool.execute({
            'script_name': 'my_custom_script',
            'parameters': {}
        })
        
        result_data = json.loads(result)
        
        # Should have output file
        assert '_output_file' in result_data.get('result', {})
        output_file = Path(result_data['result']['_output_file'])
        
        # Script folder should exist
        script_folder = output_file.parent
        assert script_folder.exists()
        assert script_folder.name == 'my_custom_script'
        assert 'outputs' in str(script_folder)
        assert '.script-kiwi' in str(script_folder) or str(tmp_path / '.script-kiwi') in str(script_folder)
        
        # File should exist
        assert output_file.exists()
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    @patch('script_kiwi.tools.run.log_execution_start')
    async def test_output_includes_file_metadata(
        self, mock_log_start, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that output includes file metadata (_output_file, _file_size_bytes, etc.)."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        project_path = tmp_path / 'project'
        project_path.mkdir()
        
        tool = RunTool(project_path=str(project_path))
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create a test script
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    return {
        "status": "success",
        "data": {"result": "test data", "items": [1, 2, 3]},
        "metadata": {"duration_sec": 0.5}
    }
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file,
            'category': 'utility'
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        mock_log_execution.return_value = {'execution_id': 'analytics-123'}
        mock_log_start.return_value = 'start-123'
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {}
        })
        
        result_data = json.loads(result)
        result_obj = result_data.get('result', {})
        
        # Should include file metadata
        assert '_output_file' in result_obj
        assert '_file_size_bytes' in result_obj
        assert '_message' in result_obj
        assert '_summary' in result_obj
        
        # Should also include the actual data (since it's small)
        assert 'result' in result_obj or 'data' in result_obj
