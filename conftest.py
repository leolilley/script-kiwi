"""
Shared pytest fixtures for Script Kiwi MCP tests

Centralized mocking infrastructure to eliminate duplication across test files.
Provides reusable fixtures and helper classes for mocking Supabase and API clients.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import Mock
from typing import Dict, Any, Optional

# Package is at root level, no need to add to path


# ============================================================================
# Mock Helper Classes
# ============================================================================

class SupabaseQueryBuilder:
    """
    Builder pattern for creating Supabase query mocks.
    
    Creates a fluent query chain that supports methods like:
    .select().eq().in_().limit().execute().data
    
    Usage:
        builder = SupabaseQueryBuilder([{'id': '123'}])
        query = builder.build()
        result = query.select().eq('id', '123').execute()
        assert result.data == [{'id': '123'}]
    """
    
    def __init__(self, data: Any = None):
        """
        Initialize query builder with optional default data.
        
        Args:
            data: Default data to return when execute() is called.
                  Can be a list, dict, or None. Defaults to [].
        """
        self.data = data if data is not None else []
        self._count = None
        self._query = Mock()
        self._setup_chain()
    
    def _setup_chain(self):
        """Setup the fluent query chain - all methods return self to allow chaining."""
        # Track if single() or maybe_single() was called
        self._is_single = False
        self._is_maybe_single = False
        
        # All query builder methods return self to allow chaining
        self._query.eq = Mock(return_value=self._query)
        self._query.in_ = Mock(return_value=self._query)
        self._query.limit = Mock(return_value=self._query)
        self._query.offset = Mock(return_value=self._query)
        self._query.order = Mock(return_value=self._query)
        self._query.gte = Mock(return_value=self._query)
        self._query.lte = Mock(return_value=self._query)
        self._query.gt = Mock(return_value=self._query)
        self._query.lt = Mock(return_value=self._query)
        
        # Setup not_ as a special mock that has is_() method
        not_mock = Mock()
        not_mock.is_ = Mock(return_value=self._query)
        self._query.not_ = not_mock
        
        # Track single() and maybe_single() calls
        def single_side_effect():
            self._is_single = True
            return self._query
        self._query.single = Mock(side_effect=single_side_effect)
        
        def maybe_single_side_effect():
            self._is_maybe_single = True
            return self._query
        self._query.maybe_single = Mock(side_effect=maybe_single_side_effect)
        
        # Track count parameter in select()
        def select_side_effect(*args, **kwargs):
            # Check if count='exact' is passed
            if 'count' in kwargs:
                self._count = kwargs['count']
            return self._query
        self._query.select = Mock(side_effect=select_side_effect)
        
        # Execute returns a response object with data attribute
        # If single() was called, return dict (first item if list), otherwise return list
        def execute_side_effect():
            mock_response = Mock()
            if self._is_single or self._is_maybe_single:
                # For single(), return dict (first item if list, or the data itself if dict)
                if isinstance(self.data, list) and len(self.data) > 0:
                    mock_response.data = self.data[0]
                elif isinstance(self.data, dict):
                    mock_response.data = self.data
                else:
                    mock_response.data = self.data
            else:
                # For regular queries, return list
                if isinstance(self.data, dict):
                    mock_response.data = [self.data]
                else:
                    mock_response.data = self.data if self.data is not None else []
            
            # Add count attribute if count='exact' was used
            if self._count == 'exact':
                if isinstance(mock_response.data, list):
                    count_value = len(mock_response.data)
                else:
                    count_value = 1 if mock_response.data else 0
                mock_response.count = count_value
            
            return mock_response
        
        self._query.execute = Mock(side_effect=execute_side_effect)
    
    def build(self):
        """Return the configured query mock."""
        return self._query


class SupabaseTableMock:
    """
    Mock for a Supabase table with query builder support.
    
    Provides select(), insert(), update(), delete() methods that return
    query builders configured with default data.
    
    Usage:
        table = SupabaseTableMock([{'id': '123'}])
        query = table.select()
        result = query.eq('id', '123').execute()
        assert result.data == [{'id': '123'}]
    """
    
    def __init__(self, default_data: Any = None):
        """
        Initialize table mock with optional default data.
        
        Args:
            default_data: Default data returned by queries. Defaults to [].
        """
        self.default_data = default_data if default_data is not None else []
    
    def select(self, *args, **kwargs):
        """Mock select() - returns a query builder with current default_data."""
        builder = SupabaseQueryBuilder(self.default_data)
        if 'count' in kwargs:
            builder._count = kwargs['count']
        query = builder.build()
        return query
    
    def insert(self, *args, **kwargs):
        """Mock insert() - returns a query builder."""
        builder = SupabaseQueryBuilder()
        return builder.build()
    
    def update(self, *args, **kwargs):
        """Mock update() - returns a query builder."""
        builder = SupabaseQueryBuilder()
        return builder.build()
    
    def upsert(self, *args, **kwargs):
        """Mock upsert() - returns a query builder."""
        builder = SupabaseQueryBuilder()
        return builder.build()
    
    def delete(self, *args, **kwargs):
        """Mock delete() - returns a query builder."""
        builder = SupabaseQueryBuilder()
        return builder.build()


class MockSupabaseClient:
    """
    Centralized Supabase client mock with all common tables pre-configured.
    
    Provides a complete mock of SupabaseClient with:
    - All common tables pre-configured with sensible defaults
    - table() method for direct table access
    - RPC support
    
    Usage:
        mock_supabase = MockSupabaseClient()
        mock_supabase.configure_table_data('scripts', [{'id': '123'}])
        table = mock_supabase.table('scripts')
    """
    
    def __init__(self):
        """Initialize mock Supabase client with all common tables."""
        # Create table mocks with sensible defaults
        self._tables = {
            'scripts': SupabaseTableMock(),
            'script_versions': SupabaseTableMock(),
            'executions': SupabaseTableMock(),
            'lockfiles': SupabaseTableMock(),
            'script_feedback': SupabaseTableMock(),
            'users': SupabaseTableMock(),
        }
        
        # Setup table() method for direct table access
        def table_side_effect(table_name: str):
            """Return table mock for given table name."""
            if table_name in self._tables:
                return self._tables[table_name]
            # Create new table mock if not found
            new_table = SupabaseTableMock()
            self._tables[table_name] = new_table
            return new_table
        
        self.table = Mock(side_effect=table_side_effect)
        
        # Setup RPC
        self.rpc = Mock(return_value=SupabaseQueryBuilder().build())
    
    def configure_table_data(self, table_name: str, data: Any):
        """
        Configure default data for a table.
        
        Args:
            table_name: Name of the table to configure
            data: Default data to return (list, dict, or None)
        
        Usage:
            mock_supabase.configure_table_data('scripts', [{'id': '123'}])
        """
        if table_name in self._tables:
            self._tables[table_name].default_data = data
        else:
            self._tables[table_name] = SupabaseTableMock(data)


# ============================================================================
# Base Fixtures
# ============================================================================

@pytest.fixture
def mock_supabase():
    """
    Standard Supabase client mock.
    
    Returns a MockSupabaseClient instance with all common tables pre-configured.
    Use configure_table_data() to set test-specific data.
    
    Usage:
        def test_something(mock_supabase):
            mock_supabase.configure_table_data('scripts', [{'id': '123'}])
            # ... test code
    """
    return MockSupabaseClient()


@pytest.fixture
def mock_script_registry(mock_supabase):
    """
    Mock ScriptRegistry with Supabase client.
    
    Usage:
        def test_something(mock_script_registry, mock_supabase):
            mock_supabase.configure_table_data('scripts', [{'name': 'test_script'}])
            # ... test code
    """
    from script_kiwi.api.script_registry import ScriptRegistry
    
    registry = ScriptRegistry()
    registry.client = mock_supabase
    return registry


@pytest.fixture
def mock_execution_logger(mock_supabase):
    """
    Mock ExecutionLogger with Supabase client.
    
    Usage:
        def test_something(mock_execution_logger):
            # ... test code
    """
    from script_kiwi.api.execution_logger import ExecutionLogger
    
    logger = ExecutionLogger()
    logger.client = mock_supabase
    return logger


@pytest.fixture
def mock_script_resolver(mock_script_registry):
    """
    Mock ScriptResolver with registry client.
    
    Usage:
        def test_something(mock_script_resolver):
            # ... test code
    """
    from script_kiwi.utils.script_resolver import ScriptResolver
    
    resolver = ScriptResolver(registry_client=mock_script_registry)
    return resolver


# ============================================================================
# Context Manager Fixtures
# ============================================================================

@pytest.fixture
def supabase_patch(mock_supabase):
    """
    Context manager for patching Supabase clients across all API modules.
    
    Automatically patches ScriptRegistry and ExecutionLogger.
    Returns the mock_supabase instance for configuration.
    
    Usage:
        def test_something(supabase_patch):
            with supabase_patch as mock_supabase:
                mock_supabase.configure_table_data('scripts', [{'id': '123'}])
                # ... test code
    """
    from contextlib import contextmanager
    
    @contextmanager
    def _patch():
        with pytest.MonkeyPatch().context() as m:
            # Patch ScriptRegistry
            m.setattr('script_kiwi.api.script_registry.create_client', lambda url, key: mock_supabase)
            # Patch ExecutionLogger
            m.setattr('script_kiwi.api.execution_logger.create_client', lambda url, key: mock_supabase)
            yield mock_supabase
    
    return _patch

