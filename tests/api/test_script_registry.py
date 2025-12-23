"""
Tests for ScriptRegistry API client.
"""

import pytest
from unittest.mock import Mock

from script_kiwi.api.script_registry import ScriptRegistry


class TestScriptRegistry:
    """Tests for ScriptRegistry"""
    
    def test_registry_initialization_with_credentials(self):
        """Test registry initialization with credentials"""
        with pytest.MonkeyPatch().context() as m:
            m.setenv('SUPABASE_URL', 'https://test.supabase.co')
            m.setenv('SUPABASE_SECRET_KEY', 'test-key')
            
            registry = ScriptRegistry()
            assert registry.client is not None
    
    def test_registry_initialization_without_credentials(self):
        """Test registry initialization without credentials"""
        with pytest.MonkeyPatch().context() as m:
            m.delenv('SUPABASE_URL', raising=False)
            m.delenv('SUPABASE_SECRET_KEY', raising=False)
            
            registry = ScriptRegistry()
            assert registry.client is None
    
    @pytest.mark.asyncio
    async def test_search_scripts(self, mock_supabase):
        """Test searching scripts"""
        registry = ScriptRegistry()
        registry.client = mock_supabase
        
        # Mock RPC call - rpc() returns a query builder, execute() returns response
        mock_rpc_query = Mock()
        mock_response = Mock()
        mock_response.data = [
            {
                'name': 'test_script',
                'category': 'scraping',
                'description': 'Test script',
                'rank': 0.9,
                'quality_score': 0.85,
                'latest_version': '1.0.0'
            }
        ]
        mock_rpc_query.execute = Mock(return_value=mock_response)
        mock_supabase.rpc = Mock(return_value=mock_rpc_query)
        
        result = await registry.search_scripts('test', limit=10)
        
        assert len(result) == 1
        assert result[0]['name'] == 'test_script'
        mock_supabase.rpc.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_scripts_no_client(self):
        """Test searching scripts without client"""
        registry = ScriptRegistry()
        registry.client = None
        
        result = await registry.search_scripts('test')
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_script(self, mock_supabase):
        """Test getting a script"""
        registry = ScriptRegistry()
        registry.client = mock_supabase
        
        # Mock script table query - configure table to return script data
        mock_script = {
            'id': 'script-123',
            'name': 'test_script',
            'category': 'scraping',
            'description': 'Test script',
            'module_path': 'execution.scraping.test_script'
        }
        mock_supabase.configure_table_data('scripts', mock_script)
        
        # Mock RPC for latest version
        mock_rpc_query = Mock()
        mock_version_response = Mock()
        mock_version_response.data = {
            'version': '1.0.0',
            'content': 'def execute(params): pass',
            'content_hash': 'abc123',
            'changelog': 'Initial version'
        }
        mock_rpc_query.execute = Mock(return_value=mock_version_response)
        mock_supabase.rpc = Mock(return_value=mock_rpc_query)
        
        result = await registry.get_script('test_script')
        
        assert result is not None
        assert result['name'] == 'test_script'
        assert result['version'] == '1.0.0'
        assert 'content' in result
    
    @pytest.mark.asyncio
    async def test_publish_script(self, mock_supabase):
        """Test publishing a script"""
        registry = ScriptRegistry()
        registry.client = mock_supabase
        
        # Mock script doesn't exist - configure empty data for select query
        mock_supabase.configure_table_data('scripts', [])
        
        # Mock script insert - patch insert to return mock with execute
        mock_script_table = mock_supabase.table('scripts')
        mock_script_insert_query = Mock()
        mock_script_insert_response = Mock()
        mock_script_insert_response.data = [{'id': 'script-123'}]
        mock_script_insert_query.execute = Mock(return_value=mock_script_insert_response)
        mock_script_table.insert = Mock(return_value=mock_script_insert_query)
        
        # Mock version insert
        mock_version_table = mock_supabase.table('script_versions')
        mock_version_insert_query = Mock()
        mock_version_insert_response = Mock()
        mock_version_insert_response.data = [{'id': 'version-456'}]
        mock_version_insert_query.execute = Mock(return_value=mock_version_insert_response)
        mock_version_table.insert = Mock(return_value=mock_version_insert_query)
        
        # Mock update queries (for is_latest and latest_version updates)
        mock_update_query = Mock()
        mock_update_response = Mock()
        mock_update_response.data = []
        mock_update_query.execute = Mock(return_value=mock_update_response)
        mock_update_query.eq = Mock(return_value=mock_update_query)
        mock_version_table.update = Mock(return_value=mock_update_query)
        mock_script_table.update = Mock(return_value=mock_update_query)
        
        result = await registry.publish_script(
            script_name='test_script',
            category='scraping',
            version='1.0.0',
            content='def execute(params): pass',
            content_hash='abc123'
        )
        
        assert result['status'] == 'published'
        assert result['script_id'] == 'script-123'
        assert 'version_id' in result
    
    @pytest.mark.asyncio
    async def test_publish_script_with_subcategory(self, mock_supabase):
        """Test publishing a script with subcategory"""
        registry = ScriptRegistry()
        registry.client = mock_supabase
        
        # Mock script doesn't exist
        mock_supabase.configure_table_data('scripts', [])
        
        # Mock script insert
        mock_script_table = mock_supabase.table('scripts')
        mock_script_insert_query = Mock()
        mock_script_insert_response = Mock()
        mock_script_insert_response.data = [{'id': 'script-123'}]
        mock_script_insert_query.execute = Mock(return_value=mock_script_insert_response)
        mock_script_table.insert = Mock(return_value=mock_script_insert_query)
        
        # Mock version insert
        mock_version_table = mock_supabase.table('script_versions')
        mock_version_insert_query = Mock()
        mock_version_insert_response = Mock()
        mock_version_insert_response.data = [{'id': 'version-456'}]
        mock_version_insert_query.execute = Mock(return_value=mock_version_insert_response)
        mock_version_table.insert = Mock(return_value=mock_version_insert_query)
        
        # Mock update queries
        mock_update_query = Mock()
        mock_update_response = Mock()
        mock_update_response.data = []
        mock_update_query.execute = Mock(return_value=mock_update_response)
        mock_update_query.eq = Mock(return_value=mock_update_query)
        mock_version_table.update = Mock(return_value=mock_update_query)
        mock_script_table.update = Mock(return_value=mock_update_query)
        
        result = await registry.publish_script(
            script_name='test_script',
            category='scraping',
            subcategory='google-maps',
            version='1.0.0',
            content='def execute(params): pass',
            content_hash='abc123'
        )
        
        assert result['status'] == 'published'
        assert result['script_id'] == 'script-123'
        
        # Verify subcategory was included in insert
        insert_call = mock_script_table.insert.call_args
        script_data = insert_call[0][0]
        assert script_data['subcategory'] == 'google-maps'
        assert script_data['category'] == 'scraping'
    
    @pytest.mark.asyncio
    async def test_publish_script_lib_category(self, mock_supabase):
        """Test publishing a script with lib category"""
        registry = ScriptRegistry()
        registry.client = mock_supabase
        
        mock_supabase.configure_table_data('scripts', [])
        
        mock_script_table = mock_supabase.table('scripts')
        mock_script_insert_query = Mock()
        mock_script_insert_response = Mock()
        mock_script_insert_response.data = [{'id': 'script-123'}]
        mock_script_insert_query.execute = Mock(return_value=mock_script_insert_response)
        mock_script_table.insert = Mock(return_value=mock_script_insert_query)
        
        mock_version_table = mock_supabase.table('script_versions')
        mock_version_insert_query = Mock()
        mock_version_insert_response = Mock()
        mock_version_insert_response.data = [{'id': 'version-456'}]
        mock_version_insert_query.execute = Mock(return_value=mock_version_insert_response)
        mock_version_table.insert = Mock(return_value=mock_version_insert_query)
        
        mock_update_query = Mock()
        mock_update_response = Mock()
        mock_update_response.data = []
        mock_update_query.execute = Mock(return_value=mock_update_response)
        mock_update_query.eq = Mock(return_value=mock_update_query)
        mock_version_table.update = Mock(return_value=mock_update_query)
        mock_script_table.update = Mock(return_value=mock_update_query)
        
        result = await registry.publish_script(
            script_name='youtube_utils',
            category='lib',
            version='1.0.0',
            content='def extract_video_id(url): pass',
            content_hash='abc123'
        )
        
        assert result['status'] == 'published'
        
        # Verify lib category was accepted
        insert_call = mock_script_table.insert.call_args
        script_data = insert_call[0][0]
        assert script_data['category'] == 'lib'
    
    @pytest.mark.asyncio
    async def test_get_script_with_subcategory(self, mock_supabase):
        """Test getting a script that has subcategory"""
        registry = ScriptRegistry()
        registry.client = mock_supabase
        
        # Mock script with subcategory
        mock_script = {
            'id': 'script-123',
            'name': 'test_script',
            'category': 'scraping',
            'subcategory': 'google-maps',
            'description': 'Test script',
            'module_path': 'execution.scraping.test_script'
        }
        mock_supabase.configure_table_data('scripts', mock_script)
        
        # Mock RPC for latest version
        mock_rpc_query = Mock()
        mock_version_response = Mock()
        mock_version_response.data = {
            'version': '1.0.0',
            'content': 'def execute(params): pass',
            'content_hash': 'abc123'
        }
        mock_rpc_query.execute = Mock(return_value=mock_version_response)
        mock_supabase.rpc = Mock(return_value=mock_rpc_query)
        
        result = await registry.get_script('test_script')
        
        assert result is not None
        assert result['name'] == 'test_script'
        assert result['category'] == 'scraping'
        assert result['subcategory'] == 'google-maps'

