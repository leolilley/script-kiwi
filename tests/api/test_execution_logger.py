"""
Tests for ExecutionLogger.
"""

import pytest
from unittest.mock import Mock

from script_kiwi.api.execution_logger import ExecutionLogger


class TestExecutionLogger:
    """Tests for ExecutionLogger"""
    
    def test_logger_initialization_with_credentials(self):
        """Test logger initialization with credentials"""
        with pytest.MonkeyPatch().context() as m:
            m.setenv('SUPABASE_URL', 'https://test.supabase.co')
            m.setenv('SUPABASE_SECRET_KEY', 'test-key')
            
            logger = ExecutionLogger()
            assert logger.client is not None
    
    def test_logger_initialization_without_credentials(self):
        """Test logger initialization without credentials"""
        with pytest.MonkeyPatch().context() as m:
            m.delenv('SUPABASE_URL', raising=False)
            m.delenv('SUPABASE_SECRET_KEY', raising=False)
            
            logger = ExecutionLogger()
            assert logger.client is None
    
    @pytest.mark.asyncio
    async def test_start_execution(self):
        """Test starting execution"""
        logger = ExecutionLogger()
        
        execution_id = await logger.start_execution(
            script_name='test_script',
            script_version='1.0.0',
            params={'test': 'value'}
        )
        
        assert execution_id is not None
        assert isinstance(execution_id, str)
    
    @pytest.mark.asyncio
    async def test_complete_execution_success(self, mock_supabase):
        """Test completing execution with success"""
        logger = ExecutionLogger()
        logger.client = mock_supabase
        
        # Patch insert to return a mock query with execute
        mock_table = mock_supabase.table('executions')
        mock_insert_query = Mock()
        mock_response = Mock()
        mock_response.data = [{'id': 'exec-123'}]
        mock_insert_query.execute = Mock(return_value=mock_response)
        mock_table.insert = Mock(return_value=mock_insert_query)
        
        await logger.complete_execution(
            execution_id='exec-123',
            status='success',
            result={'data': 'test'},
            duration_sec=1.5,
            cost_usd=0.01
        )
        
        # Verify insert was called and execute was called
        mock_table.insert.assert_called_once()
        mock_insert_query.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_complete_execution_error(self, mock_supabase):
        """Test completing execution with error"""
        logger = ExecutionLogger()
        logger.client = mock_supabase
        
        # Patch insert to capture call args and return mock query
        mock_table = mock_supabase.table('executions')
        captured_insert_args = []
        
        def insert_side_effect(*args, **kwargs):
            # Capture the data being inserted
            if args:
                captured_insert_args.append(args[0])
            elif kwargs:
                captured_insert_args.append(kwargs)
            # Return a mock query with execute
            mock_insert_query = Mock()
            mock_response = Mock()
            mock_response.data = [{'id': 'exec-123'}]
            mock_insert_query.execute = Mock(return_value=mock_response)
            return mock_insert_query
        
        mock_table.insert = Mock(side_effect=insert_side_effect)
        
        await logger.complete_execution(
            execution_id='exec-123',
            status='error',
            error='Test error',
            duration_sec=0.5
        )
        
        mock_table.insert.assert_called_once()
        call_args = captured_insert_args[0]
        assert call_args['status'] == 'error'
        assert call_args['error'] == 'Test error'
    
    @pytest.mark.asyncio
    async def test_complete_execution_no_client(self):
        """Test completing execution without client"""
        logger = ExecutionLogger()
        logger.client = None
        
        # Should not raise error, just print
        await logger.complete_execution(
            execution_id='exec-123',
            status='success',
            duration_sec=1.0
        )

