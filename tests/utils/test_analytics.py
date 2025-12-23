"""
Tests for analytics utilities.
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from script_kiwi.utils.analytics import (
    log_execution,
    log_execution_start,
    get_run_history,
    script_stats,
    _get_history_file,
    _ensure_runs_dir
)


class TestAnalyticsLogging:
    """Tests for log_execution function."""
    
    def test_log_execution_to_user_space(self, tmp_path, monkeypatch):
        """Test logging execution to user space JSONL file."""
        # Mock user home to use tmp_path
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        result = log_execution(
            script_name='test_script',
            status='success',
            duration_sec=1.5,
            inputs={'param1': 'value1', 'param2': 'value2'},
            outputs={'result': 'ok'},
            cost_usd=0.01,
            script_version='1.0.0',
            rows_processed=10
        )
        
        # Check return value
        assert result['script_name'] == 'test_script'
        assert result['status'] == 'success'
        assert result['duration_sec'] == 1.5
        
        # Check file was created
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        assert history_file.exists()
        
        # Check file content
        with open(history_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = json.loads(lines[0])
            assert entry['script'] == 'test_script'
            assert entry['status'] == 'success'
            assert entry['duration_sec'] == 1.5
            assert entry['cost_usd'] == 0.01
            assert entry['script_version'] == '1.0.0'
            assert entry['rows_processed'] == 10
            assert 'timestamp' in entry
            assert 'inputs' in entry
            assert 'outputs' in entry
    
    def test_log_execution_summarizes_inputs_outputs(self, tmp_path, monkeypatch):
        """Test that inputs/outputs are summarized in local log."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        # Create large inputs/outputs
        large_inputs = {f'key{i}': f'value{i}' for i in range(10)}
        large_outputs = {f'result{i}': f'data{i}' for i in range(10)}
        
        log_execution(
            script_name='test_script',
            status='success',
            duration_sec=1.0,
            inputs=large_inputs,
            outputs=large_outputs
        )
        
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        with open(history_file, 'r') as f:
            entry = json.loads(f.readline())
            
            # Should only have first 5 items
            assert len(entry['inputs']) == 5
            assert len(entry['outputs']) == 5
    
    def test_log_execution_with_error(self, tmp_path, monkeypatch):
        """Test logging execution with error."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        result = log_execution(
            script_name='test_script',
            status='error',
            duration_sec=0.5,
            inputs={'param': 'value'},
            error='Test error message'
        )
        
        assert result['status'] == 'error'
        
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        with open(history_file, 'r') as f:
            entry = json.loads(f.readline())
            assert entry['status'] == 'error'
            assert entry['error'] == 'Test error message'
    
    def test_log_execution_with_project(self, tmp_path, monkeypatch):
        """Test logging execution with project path."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        log_execution(
            script_name='test_script',
            status='success',
            duration_sec=1.0,
            inputs={},
            project='/path/to/project'
        )
        
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        with open(history_file, 'r') as f:
            entry = json.loads(f.readline())
            assert entry['project'] == '/path/to/project'
    
    @patch('script_kiwi.utils.analytics._get_supabase_client')
    def test_log_execution_to_supabase(self, mock_get_client, tmp_path, monkeypatch):
        """Test logging execution to Supabase."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        # Mock Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{'id': 'exec-123'}]
        mock_insert.execute.return_value = mock_response
        mock_table.insert.return_value = mock_insert
        mock_client.table.return_value = mock_table
        mock_get_client.return_value = mock_client
        
        # Set env vars
        monkeypatch.setenv('SUPABASE_URL', 'https://test.supabase.co')
        monkeypatch.setenv('SUPABASE_SECRET_KEY', 'test-key')
        
        result = log_execution(
            script_name='test_script',
            status='success',
            duration_sec=1.5,
            inputs={'param': 'value'},
            outputs={'result': 'ok'},
            cost_usd=0.01
        )
        
        # Check Supabase was called
        mock_table.insert.assert_called_once()
        call_args = mock_table.insert.call_args[0][0]
        assert call_args['script_name'] == 'test_script'
        assert call_args['status'] == 'success'
        assert call_args['inputs'] == {'param': 'value'}  # Full inputs for Supabase
        assert call_args['outputs'] == {'result': 'ok'}  # Full outputs for Supabase
        
        # Check execution_id was returned
        assert result['execution_id'] == 'exec-123'
    
    @patch('script_kiwi.utils.analytics._get_supabase_client')
    def test_log_execution_no_supabase(self, mock_get_client, tmp_path, monkeypatch):
        """Test logging when Supabase is not configured."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        mock_get_client.return_value = None
        
        result = log_execution(
            script_name='test_script',
            status='success',
            duration_sec=1.0,
            inputs={}
        )
        
        # Should still log to user space
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        assert history_file.exists()
        
        # execution_id should be None
        assert result['execution_id'] is None
    
    def test_log_execution_removes_none_values(self, tmp_path, monkeypatch):
        """Test that None values are removed from log entry."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        log_execution(
            script_name='test_script',
            status='success',
            duration_sec=1.0,
            inputs={},
            outputs=None,
            error=None,
            cost_usd=None
        )
        
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        with open(history_file, 'r') as f:
            entry = json.loads(f.readline())
            assert 'outputs' not in entry or entry['outputs'] is None
            assert 'error' not in entry
            assert 'cost_usd' not in entry


class TestGetRunHistory:
    """Tests for get_run_history function."""
    
    def test_get_run_history_empty(self, tmp_path, monkeypatch):
        """Test getting history from empty file."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        history = get_run_history(days=30)
        assert history == []
    
    def test_get_run_history_with_entries(self, tmp_path, monkeypatch):
        """Test getting history with entries."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create test entries
        now = datetime.now()
        entries = [
            {
                'timestamp': (now - timedelta(days=1)).isoformat(),
                'script': 'script1',
                'status': 'success',
                'duration_sec': 1.0
            },
            {
                'timestamp': (now - timedelta(days=2)).isoformat(),
                'script': 'script2',
                'status': 'error',
                'duration_sec': 2.0
            },
            {
                'timestamp': (now - timedelta(days=40)).isoformat(),  # Too old
                'script': 'script3',
                'status': 'success',
                'duration_sec': 3.0
            }
        ]
        
        with open(history_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + '\n')
        
        history = get_run_history(days=30)
        
        # Should only return entries from last 30 days
        assert len(history) == 2
        assert history[0]['script'] == 'script1'  # Most recent first
        assert history[1]['script'] == 'script2'
    
    def test_get_run_history_filter_by_script(self, tmp_path, monkeypatch):
        """Test filtering history by script name."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        now = datetime.now()
        entries = [
            {
                'timestamp': (now - timedelta(days=1)).isoformat(),
                'script': 'script1',
                'status': 'success',
                'duration_sec': 1.0
            },
            {
                'timestamp': (now - timedelta(days=2)).isoformat(),
                'script': 'script2',
                'status': 'success',
                'duration_sec': 2.0
            }
        ]
        
        with open(history_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + '\n')
        
        history = get_run_history(days=30, script='script1')
        
        assert len(history) == 1
        assert history[0]['script'] == 'script1'
    
    def test_get_run_history_filter_by_project(self, tmp_path, monkeypatch):
        """Test filtering history by project."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        now = datetime.now()
        entries = [
            {
                'timestamp': (now - timedelta(days=1)).isoformat(),
                'script': 'script1',
                'status': 'success',
                'duration_sec': 1.0,
                'project': '/path/to/project1'
            },
            {
                'timestamp': (now - timedelta(days=2)).isoformat(),
                'script': 'script2',
                'status': 'success',
                'duration_sec': 2.0,
                'project': '/path/to/project2'
            }
        ]
        
        with open(history_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + '\n')
        
        history = get_run_history(days=30, project='/path/to/project1')
        
        assert len(history) == 1
        assert history[0]['project'] == '/path/to/project1'


class TestScriptStats:
    """Tests for script_stats function."""
    
    def test_script_stats_empty(self, tmp_path, monkeypatch):
        """Test stats with no history."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        stats = script_stats(days=30)
        assert stats == {}
    
    def test_script_stats_calculates_rates(self, tmp_path, monkeypatch):
        """Test that stats calculates success/error rates correctly."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        now = datetime.now()
        entries = [
            {
                'timestamp': (now - timedelta(days=1)).isoformat(),
                'script': 'script1',
                'status': 'success',
                'duration_sec': 1.0
            },
            {
                'timestamp': (now - timedelta(days=2)).isoformat(),
                'script': 'script1',
                'status': 'success',
                'duration_sec': 2.0
            },
            {
                'timestamp': (now - timedelta(days=3)).isoformat(),
                'script': 'script1',
                'status': 'error',
                'duration_sec': 0.5,
                'error': 'Test error'
            },
            {
                'timestamp': (now - timedelta(days=4)).isoformat(),
                'script': 'script2',
                'status': 'success',
                'duration_sec': 3.0
            }
        ]
        
        with open(history_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + '\n')
        
        stats = script_stats(days=30)
        
        assert 'script1' in stats
        assert 'script2' in stats
        
        # script1: 2 success, 1 error = 2/3 success rate
        assert stats['script1']['total_runs'] == 3
        assert stats['script1']['success_rate'] == pytest.approx(2/3, 0.01)
        assert stats['script1']['error_rate'] == pytest.approx(1/3, 0.01)
        assert stats['script1']['avg_duration_sec'] == pytest.approx((1.0 + 2.0 + 0.5) / 3, 0.01)
        assert 'Test error' in stats['script1']['common_errors']
        
        # script2: 1 success, 0 error = 1.0 success rate
        assert stats['script2']['total_runs'] == 1
        assert stats['script2']['success_rate'] == 1.0
        assert stats['script2']['error_rate'] == 0.0
    
    def test_script_stats_with_partial_success(self, tmp_path, monkeypatch):
        """Test stats with partial_success status."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        now = datetime.now()
        entries = [
            {
                'timestamp': (now - timedelta(days=1)).isoformat(),
                'script': 'script1',
                'status': 'partial_success',
                'duration_sec': 1.0
            }
        ]
        
        with open(history_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + '\n')
        
        stats = script_stats(days=30)
        
        assert stats['script1']['total_runs'] == 1
        assert stats['script1']['partial_rate'] == 1.0
        assert stats['script1']['success_rate'] == 0.0
        assert stats['script1']['error_rate'] == 0.0


class TestLogExecutionStart:
    """Tests for log_execution_start function."""
    
    def test_log_execution_start_creates_entry(self, tmp_path, monkeypatch):
        """Test that log_execution_start creates a running status entry."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        log_execution_start(
            script_name='test_script',
            execution_id='exec-123',
            inputs={'param1': 'value1', 'param2': 'value2'},
            script_version='1.0.0',
            project='/path/to/project'
        )
        
        # Check file was created
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        assert history_file.exists()
        
        # Check file content
        with open(history_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = json.loads(lines[0])
            assert entry['script'] == 'test_script'
            assert entry['execution_id'] == 'exec-123'
            assert entry['status'] == 'running'
            assert entry['script_version'] == '1.0.0'
            assert entry['project'] == '/path/to/project'
            assert 'timestamp' in entry
            assert 'inputs' in entry
    
    def test_log_execution_start_summarizes_inputs(self, tmp_path, monkeypatch):
        """Test that log_execution_start summarizes large inputs."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        # Create large inputs
        large_inputs = {f'key{i}': f'value{i}' for i in range(10)}
        
        log_execution_start(
            script_name='test_script',
            execution_id='exec-123',
            inputs=large_inputs
        )
        
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        with open(history_file, 'r') as f:
            entry = json.loads(f.readline())
            
            # Should only have first 5 items
            assert len(entry['inputs']) == 5
    
    def test_log_execution_start_without_optional_params(self, tmp_path, monkeypatch):
        """Test that log_execution_start works without optional parameters."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        log_execution_start(
            script_name='test_script',
            execution_id='exec-123',
            inputs={}
        )
        
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        with open(history_file, 'r') as f:
            entry = json.loads(f.readline())
            
            assert entry['script'] == 'test_script'
            assert entry['execution_id'] == 'exec-123'
            assert entry['status'] == 'running'
            # Optional fields should not be present
            assert 'script_version' not in entry
            assert 'project' not in entry
    
    def test_log_execution_start_handles_errors_gracefully(self, tmp_path, monkeypatch):
        """Test that log_execution_start handles file errors gracefully."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        # Make the directory read-only to cause a write error
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        history_file.parent.mkdir(parents=True, exist_ok=True)
        history_file.parent.chmod(0o444)  # Read-only
        
        try:
            # Should not raise an exception
            log_execution_start(
                script_name='test_script',
                execution_id='exec-123',
                inputs={}
            )
        except Exception:
            pytest.fail("log_execution_start should handle errors gracefully")
        finally:
            # Restore permissions
            history_file.parent.chmod(0o755)
    
    def test_log_execution_start_appends_to_existing_file(self, tmp_path, monkeypatch):
        """Test that log_execution_start appends to existing history file."""
        monkeypatch.setattr('script_kiwi.utils.analytics._get_user_home', lambda: tmp_path)
        
        history_file = tmp_path / '.script-kiwi' / '.runs' / 'history.jsonl'
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create existing entry
        with open(history_file, 'w') as f:
            f.write(json.dumps({
                'timestamp': '2024-01-01T00:00:00',
                'script': 'old_script',
                'status': 'success'
            }) + '\n')
        
        # Add new start entry
        log_execution_start(
            script_name='new_script',
            execution_id='exec-456',
            inputs={}
        )
        
        # Check both entries exist
        with open(history_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 2
            
            # First entry
            entry1 = json.loads(lines[0])
            assert entry1['script'] == 'old_script'
            
            # Second entry
            entry2 = json.loads(lines[1])
            assert entry2['script'] == 'new_script'
            assert entry2['status'] == 'running'

