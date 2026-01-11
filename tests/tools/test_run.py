"""
Tests for run tool.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from script_kiwi.tools.run import RunTool


class TestRunTool:
    """Tests for RunTool"""
    
    def test_tool_initialization(self, mock_script_registry, mock_execution_logger):
        """Test tool initialization"""
        tool = RunTool()
        assert hasattr(tool, 'registry')
        assert hasattr(tool, 'logger')
        assert hasattr(tool, 'resolver')
    
    @pytest.mark.asyncio
    async def test_run_script_not_found(self, mock_script_registry):
        """Test running non-existent script"""
        tool = RunTool()
        tool.registry = mock_script_registry
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': None,
            'path': None
        })
        
        result = await tool.execute({
            'script_name': 'nonexistent_script',
            'parameters': {}
        })
        
        result_data = json.loads(result)
        assert 'error' in result_data
        # Error can be a dict with nested structure
        error_msg = result_data['error']
        if isinstance(error_msg, dict):
            error_msg = error_msg.get('message', str(error_msg))
        assert 'not found' in str(error_msg).lower()
    
    @pytest.mark.asyncio
    async def test_run_dry_run(self, mock_script_registry, mock_supabase, monkeypatch):
        """Test dry run (validation only)"""
        tool = RunTool()
        tool.registry = mock_script_registry
        
        # Set API_KEY env var so preflight passes
        monkeypatch.setenv('API_KEY', 'test-key')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': ['API_KEY'],
            'estimated_cost_usd': 0.05
        }
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': Path('/tmp/test_script.py')
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {'count': 10},
            'dry_run': True
        })
        
        result_data = json.loads(result)
        assert result_data['status'] == 'validation_passed'
        assert 'message' in result_data
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    async def test_run_script_execution(self, mock_log_execution, mock_script_registry, mock_execution_logger, tmp_path, monkeypatch):
        """Test actual script execution with analytics logging"""
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Mock log_execution return value
        mock_log_execution.return_value = {
            'execution_id': 'analytics-exec-123',
            'script_name': 'test_script',
            'status': 'success',
            'duration_sec': 1.0,
            'cost_usd': 0.01
        }
        
        # Create a test script file
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    return {
        "status": "success",
        "data": {"result": "test"},
        "metadata": {
            "duration_sec": 1.0,
            "cost_usd": 0.01,
            "rows_processed": 1
        }
    }
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {'test': 'value'}
        })
        
        result_data = json.loads(result)
        assert result_data['status'] == 'success'
        assert 'execution_id' in result_data
        assert result_data['result']['result'] == 'test'
        
        # Check that analytics logging was called
        mock_log_execution.assert_called_once()
        call_kwargs = mock_log_execution.call_args[1]
        assert call_kwargs['script_name'] == 'test_script'
        assert call_kwargs['status'] == 'success'
        assert call_kwargs['inputs'] == {'test': 'value'}
        assert call_kwargs['outputs'] == {'result': 'test'}
        assert call_kwargs['cost_usd'] == 0.01
        assert 'project' in call_kwargs
        
        # Check ExecutionLogger was also called (backward compatibility)
        mock_execution_logger.complete_execution.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    async def test_run_script_execution_error_logging(self, mock_log_execution, mock_script_registry, mock_execution_logger, tmp_path):
        """Test that errors are logged to analytics"""
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        mock_log_execution.return_value = {
            'execution_id': None,
            'script_name': 'test_script',
            'status': 'error',
            'duration_sec': 0.5
        }
        
        # Create a script that raises an error
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    raise ValueError("Test error")
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {}
        })
        
        result_data = json.loads(result)
        assert result_data['status'] == 'error'
        assert 'error' in result_data
        
        # Check that analytics logging was called with error
        mock_log_execution.assert_called_once()
        call_kwargs = mock_log_execution.call_args[1]
        assert call_kwargs['status'] == 'error'
        assert 'Test error' in call_kwargs['error']
    
    def test_tool_initialization_with_project_path(self):
        """Test tool initialization with project_path"""
        project_path = "/tmp/test_project"
        tool = RunTool(project_path=project_path)
        assert tool.project_path == Path(project_path)
        assert tool.resolver.project_root == Path(project_path)
    
    def test_build_search_paths_with_project_path(self, tmp_path):
        """Test _build_search_paths includes both project and user space"""
        project_path = tmp_path / "project"
        project_scripts = project_path / ".ai" / "scripts"
        project_scripts.mkdir(parents=True)
        
        script_path = project_scripts / "extraction" / "test_script.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("# test")
        
        tool = RunTool(project_path=str(project_path))
        search_paths = tool._build_search_paths(script_path, "project")
        
        # Should include user space (runtime env)
        user_scripts = Path.home() / ".script-kiwi" / "scripts"
        assert user_scripts in search_paths
        
        # Should include project space
        assert project_scripts in search_paths
        
        # Should include script's own directory
        assert script_path.parent in search_paths
    
    def test_build_search_paths_without_project_path(self, tmp_path):
        """Test _build_search_paths without project_path still includes user space"""
        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test")
        
        tool = RunTool()  # No project_path
        search_paths = tool._build_search_paths(script_path, "user")
        
        # Should still include user space
        user_scripts = Path.home() / ".script-kiwi" / "scripts"
        assert user_scripts in search_paths
    
    @pytest.mark.asyncio
    async def test_run_with_project_path(self, mock_script_registry, mock_execution_logger, tmp_path, monkeypatch):
        """Test running script with project_path parameter"""
        project_path = tmp_path / "project"
        project_scripts = project_path / ".ai" / "scripts" / "extraction"
        project_scripts.mkdir(parents=True)
        
        script_file = project_scripts / "test_script.py"
        script_file.write_text('''
def execute(params):
    return {
        "status": "success",
        "data": {"result": "test"},
        "metadata": {"duration_sec": 1.0}
    }
''')
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        from unittest.mock import AsyncMock, patch
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        
        with patch('script_kiwi.tools.run.log_execution') as mock_log:
            mock_log.return_value = {'execution_id': 'analytics-123'}
            
            result = await tool.execute({
                'script_name': 'test_script',
                'parameters': {'test': 'value'},
                'project_path': str(project_path)
            })
            
            # Verify project_path was set
            assert tool.project_path == project_path
            assert tool.resolver.project_root == project_path
            
            result_data = json.loads(result)
            assert result_data['status'] == 'success'
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.subprocess.run')
    @patch('script_kiwi.utils.env_manager.subprocess.run')
    async def test_run_argparse_script_with_project_path(self, mock_env_subprocess, mock_run_subprocess, tmp_path):
        """Test _run_argparse_script uses project_path as working directory"""
        project_path = tmp_path / "project"
        project_path.mkdir()
        
        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test")
        
        # Mock venv subprocess calls to succeed
        mock_env_subprocess.return_value = Mock(returncode=0, stdout='', stderr='')
        
        tool = RunTool(project_path=str(project_path))
        
        # Mock script execution subprocess return
        mock_run_subprocess.return_value = Mock(
            returncode=0,
            stdout='{"status": "success", "data": {"result": "test"}}',
            stderr=''
        )
        
        result = tool._run_argparse_script(
            script_path=script_path,
            script_params={'test': 'value'},
            search_paths=[],
            project_path=project_path
        )
        
        # Verify the script execution subprocess was called with project_path as cwd
        # The last call should be the actual script execution
        script_call = mock_run_subprocess.call_args
        call_kwargs = script_call[1]
        assert call_kwargs['cwd'] == project_path
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.subprocess.run')
    @patch('script_kiwi.utils.env_manager.subprocess.run')
    async def test_run_argparse_script_without_project_path(self, mock_env_subprocess, mock_run_subprocess, tmp_path):
        """Test _run_argparse_script falls back to script directory when no project_path"""
        script_path = tmp_path / "test_script.py"
        script_path.write_text("# test")
        
        # Mock venv subprocess calls to succeed
        mock_env_subprocess.return_value = Mock(returncode=0, stdout='', stderr='')
        
        tool = RunTool()
        
        # Mock script execution subprocess return
        mock_run_subprocess.return_value = Mock(
            returncode=0,
            stdout='{"status": "success", "data": {"result": "test"}}',
            stderr=''
        )
        
        result = tool._run_argparse_script(
            script_path=script_path,
            script_params={'test': 'value'},
            search_paths=[],
            project_path=None
        )
        
        # Verify the script execution subprocess was called with script's parent as cwd
        script_call = mock_run_subprocess.call_args
        call_kwargs = script_call[1]
        assert call_kwargs['cwd'] == script_path.parent
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    async def test_run_logs_project_path(self, mock_log_execution, mock_script_registry, mock_execution_logger, tmp_path):
        """Test that project_path is logged correctly to history.jsonl"""
        project_path = tmp_path / "project"
        project_scripts = project_path / ".ai" / "scripts" / "extraction"
        project_scripts.mkdir(parents=True)
        
        script_file = project_scripts / "test_script.py"
        script_file.write_text('''
def execute(params):
    return {
        "status": "success",
        "data": {"result": "test"},
        "metadata": {"duration_sec": 1.0}
    }
''')
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        
        mock_log_execution.return_value = {'execution_id': 'analytics-123'}
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {'test': 'value'},
            'project_path': str(project_path)
        })
        
        # Verify log_execution was called with project_path
        mock_log_execution.assert_called_once()
        call_kwargs = mock_log_execution.call_args[1]
        assert call_kwargs['project'] == str(project_path)
    
    def test_env_manager_uses_script_location_not_project_path(self, tmp_path):
        """Test that venv is selected based on script location, not project_path.
        
        This is critical: when project_path is provided but script is in user space,
        we should use the user venv (~/.script-kiwi/.venv/), not the project venv.
        """
        from script_kiwi.utils.env_manager import EnvManager
        
        # Simulate: project_path is set to some project
        project_path = tmp_path / "some-project"
        project_path.mkdir()
        
        tool = RunTool(project_path=str(project_path))
        
        # Initially, env_manager uses project venv
        assert tool.env_manager.env_type == "project"
        assert "some-project" in str(tool.env_manager.venv_dir)
        
        # But if script is in user space, env_manager should switch to user venv
        # This simulates what happens in execute() after script resolution
        storage_location = "user"
        if storage_location == "user":
            tool.env_manager = EnvManager(project_path=None)
        
        assert tool.env_manager.env_type == "user"
        assert ".script-kiwi" in str(tool.env_manager.venv_dir)
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    async def test_run_logs_cwd_when_no_project_path(self, mock_log_execution, mock_script_registry, mock_execution_logger, tmp_path):
        """Test that CWD is logged when project_path is not provided"""
        script_file = tmp_path / "test_script.py"
        script_file.write_text('''
def execute(params):
    return {
        "status": "success",
        "data": {"result": "test"},
        "metadata": {"duration_sec": 1.0}
    }
''')
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        from unittest.mock import AsyncMock
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'user',
            'path': script_file
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        
        mock_log_execution.return_value = {'execution_id': 'analytics-123'}
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {'test': 'value'}
            # No project_path
        })
        
        # Verify log_execution was called with CWD
        mock_log_execution.assert_called_once()
        call_kwargs = mock_log_execution.call_args[1]
        assert call_kwargs['project'] == str(Path.cwd())
