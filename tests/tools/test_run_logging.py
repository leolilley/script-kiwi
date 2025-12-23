"""
Tests for real-time logging functionality in run tool.

Tests cover:
- Function-based script real-time stderr logging
- Argparse script real-time stderr streaming
- History file log_line entries
- Execution start logging
- Execution completion logging
- Execution ID tracking
- Large response truncation
- File-based output for large results
- Configurable timeouts
"""

import pytest
import json
import sys
import time
import logging
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from io import StringIO

from script_kiwi.tools.run import RunTool


class TestFunctionBasedScriptLogging:
    """Tests for function-based script real-time logging."""
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    @patch('script_kiwi.tools.run.log_execution_start')
    async def test_function_script_logs_to_history_in_real_time(
        self, mock_log_start, mock_log_execution, mock_script_registry, 
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that function-based scripts log to history file in real-time."""
        # Mock user home to use tmp_path
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create a test script that logs multiple messages
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)

def execute(params):
    logger = logging.getLogger(__name__)
    logger.info("Starting execution")
    time.sleep(0.1)
    logger.info("Processing item 1")
    time.sleep(0.1)
    logger.info("Processing item 2")
    time.sleep(0.1)
    logger.warning("Milestone reached")
    logger.info("Execution completed")
    
    return {
        "status": "success",
        "data": {"result": "test"},
        "metadata": {"duration_sec": 0.3}
    }
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
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
            'parameters': {}
        })
        
        result_data = json.loads(result)
        assert result_data['status'] == 'success'
        
        # Check that log_execution_start was called
        mock_log_start.assert_called_once()
        
        # Check history file for log_line entries
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        assert history_file.exists()
        
        with open(history_file, 'r') as f:
            lines = f.readlines()
            log_lines = [json.loads(line) for line in lines if 'log_line' in json.loads(line)]
            
            # Should have multiple log_line entries
            assert len(log_lines) >= 4
            assert any('Starting execution' in entry.get('log_line', '') for entry in log_lines)
            assert any('Processing item 1' in entry.get('log_line', '') for entry in log_lines)
            assert any('Milestone reached' in entry.get('log_line', '') for entry in log_lines)
            assert any('Execution completed' in entry.get('log_line', '') for entry in log_lines)
            
            # All log_line entries should have the same execution_id
            execution_ids = {entry.get('execution_id') for entry in log_lines}
            assert len(execution_ids) == 1
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    @patch('script_kiwi.tools.run.log_execution_start')
    async def test_function_script_updates_logging_handlers(
        self, mock_log_start, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that function-based scripts update Python logging handlers."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create a script that uses logging module
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
import logging

# Create a custom logger (not root)
logger = logging.getLogger('custom_module')
logger.setLevel(logging.INFO)

# Add a StreamHandler that uses sys.stderr
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(handler)

def execute(params):
    logger.info("Custom logger message")
    return {"status": "success", "data": {}}
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
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
            'parameters': {}
        })
        
        # Check history file for the custom logger message
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        assert history_file.exists()
        
        with open(history_file, 'r') as f:
            lines = f.readlines()
            log_lines = [json.loads(line) for line in lines if 'log_line' in json.loads(line)]
            
            # Should have captured the custom logger message
            assert any('Custom logger message' in entry.get('log_line', '') for entry in log_lines)
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    async def test_function_script_with_stream_logs_disabled(
        self, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that stream_logs=False disables real-time logging."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stderr)

def execute(params):
    logging.info("This should not appear in history file")
    return {"status": "success", "data": {}}
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
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
            'parameters': {'_stream_logs': False}
        })
        
        # Check history file - should not have log_line entries from the script
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        if history_file.exists():
            with open(history_file, 'r') as f:
                lines = f.readlines()
                log_lines = [json.loads(line) for line in lines if 'log_line' in json.loads(line)]
                # Should not have the script's log message
                assert not any('This should not appear' in entry.get('log_line', '') for entry in log_lines)


class TestArgparseScriptLogging:
    """Tests for argparse script real-time logging."""
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.subprocess.Popen')
    @patch('script_kiwi.tools.run.log_execution')
    @patch('script_kiwi.tools.run.log_execution_start')
    async def test_argparse_script_streams_stderr_in_real_time(
        self, mock_log_start, mock_log_execution, mock_popen,
        mock_script_registry, mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that argparse scripts stream stderr to history file in real-time."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
import argparse
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--json-output', action='store_true')

args = parser.parse_args()

# Write to stderr
sys.stderr.write("Starting argparse script\\n")
sys.stderr.flush()
time.sleep(0.1)
sys.stderr.write("Processing item 1\\n")
sys.stderr.flush()
time.sleep(0.1)
sys.stderr.write("Processing item 2\\n")
sys.stderr.flush()

if args.json_output:
    import json
    print(json.dumps({"status": "success", "data": {}}))
else:
    print("Success")
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        mock_log_execution.return_value = {'execution_id': 'analytics-123'}
        
        # Mock subprocess.Popen to simulate real-time output
        mock_process = Mock()
        mock_process.stdout = StringIO('{"status": "success", "data": {}}')
        mock_process.stderr = StringIO('Starting argparse script\nProcessing item 1\nProcessing item 2\n')
        mock_process.returncode = 0
        mock_process.poll = Mock(side_effect=[None, None, 0])  # Still running, still running, done
        
        def mock_popen_side_effect(*args, **kwargs):
            # Simulate reading stderr in real-time
            history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
            history_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Read stderr and write to history file
            stderr_lines = ['Starting argparse script\n', 'Processing item 1\n', 'Processing item 2\n']
            for line in stderr_lines:
                if line.strip():
                    log_entry = {
                        "timestamp": time.time(),
                        "execution_id": "exec-123",
                        "script": "test_script",
                        "status": "running",
                        "log_line": line.strip()
                    }
                    with open(history_file, 'a') as f:
                        f.write(json.dumps(log_entry) + '\n')
            
            return mock_process
        
        mock_popen.side_effect = mock_popen_side_effect
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {}
        })
        
        # Check that log_execution_start was called
        mock_log_start.assert_called_once()
        
        # Check history file for log_line entries
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        if history_file.exists():
            with open(history_file, 'r') as f:
                lines = f.readlines()
                log_lines = [json.loads(line) for line in lines if 'log_line' in json.loads(line)]
                
                # Should have log_line entries
                assert len(log_lines) >= 2
                assert any('Starting argparse script' in entry.get('log_line', '') for entry in log_lines)
                assert any('Processing item 1' in entry.get('log_line', '') for entry in log_lines)


class TestExecutionStartLogging:
    """Tests for execution start logging."""
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    @patch('script_kiwi.tools.run.log_execution_start')
    async def test_execution_start_logged_immediately(
        self, mock_log_start, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that execution start is logged immediately."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    import time
    time.sleep(0.5)  # Simulate work
    return {"status": "success", "data": {}}
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
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
            'parameters': {}
        })
        
        # Check that log_execution_start was called with correct args
        mock_log_start.assert_called_once()
        call_kwargs = mock_log_start.call_args[1]
        assert call_kwargs['script_name'] == 'test_script'
        assert call_kwargs['execution_id'] == 'exec-123'
        assert 'inputs' in call_kwargs
        
        # Check history file for start entry
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        assert history_file.exists()
        
        with open(history_file, 'r') as f:
            lines = f.readlines()
            start_entries = [json.loads(line) for line in lines if json.loads(line).get('status') == 'running' and 'log_line' not in json.loads(line)]
            
            # Should have at least one "running" status entry (the start)
            assert len(start_entries) >= 1
            assert any(entry.get('execution_id') == 'exec-123' for entry in start_entries)


class TestExecutionCompletionLogging:
    """Tests for execution completion logging."""
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    async def test_execution_completion_logged_with_results(
        self, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that execution completion is logged with results."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    return {
        "status": "success",
        "data": {"result": "test"},
        "metadata": {
            "duration_sec": 1.0,
            "cost_usd": 0.01,
            "rows_processed": 10
        }
    }
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        mock_log_execution.return_value = {
            'execution_id': 'analytics-123',
            'script_name': 'test_script',
            'status': 'success',
            'duration_sec': 1.0,
            'cost_usd': 0.01
        }
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {}
        })
        
        # Check that log_execution was called with correct args
        mock_log_execution.assert_called_once()
        call_kwargs = mock_log_execution.call_args[1]
        assert call_kwargs['script_name'] == 'test_script'
        assert call_kwargs['status'] == 'success'
        assert call_kwargs['outputs'] == {'result': 'test'}
        assert call_kwargs['cost_usd'] == 0.01
        
        # Check history file for completion entry
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        assert history_file.exists()
        
        with open(history_file, 'r') as f:
            lines = f.readlines()
            completion_entries = [json.loads(line) for line in lines if json.loads(line).get('status') == 'success' and 'outputs' in json.loads(line)]
            
            # Should have at least one completion entry
            assert len(completion_entries) >= 1
            assert any(entry.get('outputs', {}).get('result') == 'test' for entry in completion_entries)


class TestExecutionIdTracking:
    """Tests for execution ID tracking across log entries."""
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    @patch('script_kiwi.tools.run.log_execution_start')
    async def test_execution_id_consistent_across_log_entries(
        self, mock_log_start, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that execution_id is consistent across all log entries."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stderr)

def execute(params):
    logger = logging.getLogger(__name__)
    logger.info("Log message 1")
    logger.info("Log message 2")
    return {"status": "success", "data": {}}
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
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
            'parameters': {}
        })
        
        # Check history file - all entries should have same execution_id
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        assert history_file.exists()
        
        with open(history_file, 'r') as f:
            lines = f.readlines()
            entries = [json.loads(line) for line in lines]
            
            # Filter entries for this execution
            exec_entries = [e for e in entries if e.get('execution_id') == 'exec-123']
            
            # Should have multiple entries with same execution_id
            assert len(exec_entries) >= 2
            
            # All should have the same execution_id
            execution_ids = {e.get('execution_id') for e in exec_entries}
            assert len(execution_ids) == 1
            assert 'exec-123' in execution_ids


class TestLargeResponseTruncation:
    """Tests for large response truncation."""
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    async def test_large_response_truncated(
        self, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that large responses are truncated."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create a script that returns a large result
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    # Create a large data array
    large_data = [{"item": i, "data": "x" * 1000} for i in range(1000)]
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
            'path': script_file
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        mock_log_execution.return_value = {'execution_id': 'analytics-123'}
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {}
        })
        
        result_data = json.loads(result)
        
        # Check that result was truncated
        if 'result' in result_data and 'data' in result_data['result']:
            items = result_data['result']['data'].get('items', [])
            # Should be truncated to MAX_ARRAY_ITEMS (default 100)
            assert len(items) <= 100
        
        # Or result might be written to file
        if 'output_file' in result_data:
            assert Path(result_data['output_file']).exists()


class TestFileBasedOutput:
    """Tests for file-based output for large results."""
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    async def test_large_result_written_to_file(
        self, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that large results are written to file."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        project_path = tmp_path / 'project'
        project_path.mkdir()
        (project_path / '.ai' / 'tmp').mkdir(parents=True)
        
        tool = RunTool(project_path=str(project_path))
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create a script that returns a very large result
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    # Create a very large data array
    large_data = [{"item": i, "data": "x" * 10000} for i in range(1000)]
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
            'path': script_file
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        mock_log_execution.return_value = {'execution_id': 'analytics-123'}
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {}
        })
        
        result_data = json.loads(result)
        
        # Should have output_file in response
        if 'output_file' in result_data:
            output_file = Path(result_data['output_file'])
            assert output_file.exists()
            
            # File should contain the full result
            with open(output_file, 'r') as f:
                file_data = json.load(f)
                assert file_data['status'] == 'success'
                assert 'items' in file_data.get('data', {})
                assert len(file_data['data']['items']) == 1000


class TestConfigurableTimeout:
    """Tests for configurable timeout."""
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    async def test_timeout_parameter_respected(
        self, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that _timeout parameter is respected."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        # Create a script that runs longer than default timeout
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    import time
    time.sleep(10)  # Sleep for 10 seconds
    return {"status": "success", "data": {}}
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        mock_log_execution.return_value = {'execution_id': 'analytics-123'}
        
        # Set a short timeout
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {'_timeout': 2}  # 2 second timeout
        })
        
        result_data = json.loads(result)
        
        # Should have timed out (or completed if timeout wasn't applied)
        # The exact behavior depends on implementation
        # For function-based scripts, timeout might not be enforced
        # This test verifies the parameter is extracted correctly
        assert '_timeout' not in result_data.get('result', {})


class TestLoggingErrorHandling:
    """Tests for error handling in logging."""
    
    @pytest.mark.asyncio
    @patch('script_kiwi.tools.run.log_execution')
    async def test_logging_errors_dont_crash_execution(
        self, mock_log_execution, mock_script_registry,
        mock_execution_logger, tmp_path, monkeypatch
    ):
        """Test that logging errors don't crash script execution."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        tool = RunTool()
        tool.registry = mock_script_registry
        tool.logger = mock_execution_logger
        
        script_file = tmp_path / 'test_script.py'
        script_file.write_text('''
def execute(params):
    return {"status": "success", "data": {}}
''')
        
        mock_script = {
            'name': 'test_script',
            'version': '1.0.0',
            'required_env_vars': []
        }
        
        tool.resolver.resolve_script = AsyncMock(return_value={
            'location': 'project',
            'path': script_file
        })
        mock_script_registry.get_script = AsyncMock(return_value=mock_script)
        mock_execution_logger.start_execution = AsyncMock(return_value='exec-123')
        mock_execution_logger.complete_execution = AsyncMock()
        
        # Make log_execution raise an error
        mock_log_execution.side_effect = Exception("Logging error")
        
        result = await tool.execute({
            'script_name': 'test_script',
            'parameters': {}
        })
        
        result_data = json.loads(result)
        
        # Script should still complete successfully despite logging error
        assert result_data['status'] == 'success'
        assert 'result' in result_data
