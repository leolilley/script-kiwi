"""
Tests for remove tool.
"""

import pytest
import json

from script_kiwi.tools.remove import RemoveTool


class TestRemoveTool:
    """Tests for RemoveTool"""
    
    def test_tool_initialization(self, mock_script_registry):
        """Test tool initialization"""
        tool = RemoveTool()
        assert hasattr(tool, 'registry')
        assert hasattr(tool, 'resolver')
    
    @pytest.mark.asyncio
    async def test_remove_from_project(self, mock_script_registry, tmp_path):
        """Test removing script from project space"""
        tool = RemoveTool()
        tool.registry = mock_script_registry
        
        # Create test script in project space
        project_root = tmp_path / "project"
        scripts_dir = project_root / ".ai" / "scripts" / "test"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        script_file = scripts_dir / "test_script.py"
        script_file.write_text("def execute(params): pass")
        
        # Mock project root
        tool.resolver.project_root = project_root
        tool.resolver.project_scripts = project_root / ".ai" / "scripts"
        
        result = await tool.execute({
            'script_name': 'test_script',
            'tier': 'project',
            'category': 'test'
        })
        
        result_data = json.loads(result)
        assert result_data['removals']['project']['removed'] is True
        assert not script_file.exists()
    
    @pytest.mark.asyncio
    async def test_remove_from_user(self, mock_script_registry, tmp_path):
        """Test removing script from user space"""
        tool = RemoveTool()
        tool.registry = mock_script_registry
        
        # Create test script in user space
        user_home = tmp_path / "home" / "user"
        scripts_dir = user_home / ".script-kiwi" / "scripts" / "test"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        script_file = scripts_dir / "test_script.py"
        script_file.write_text("def execute(params): pass")
        
        # Mock user home
        tool.resolver.user_home = user_home
        tool.resolver.user_scripts = user_home / ".script-kiwi" / "scripts"
        
        result = await tool.execute({
            'script_name': 'test_script',
            'tier': 'user',
            'category': 'test'
        })
        
        result_data = json.loads(result)
        assert result_data['removals']['user']['removed'] is True
        assert not script_file.exists()
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent(self, mock_script_registry):
        """Test removing non-existent script"""
        tool = RemoveTool()
        tool.registry = mock_script_registry
        
        result = await tool.execute({
            'script_name': 'nonexistent_script',
            'tier': 'project'
        })
        
        result_data = json.loads(result)
        assert result_data['removals']['project']['removed'] is False
        assert 'not found' in result_data['removals']['project']['reason'].lower()
    
    @pytest.mark.asyncio
    async def test_remove_dry_run(self, mock_script_registry, tmp_path):
        """Test dry run mode"""
        tool = RemoveTool()
        tool.registry = mock_script_registry
        
        # Create test script
        project_root = tmp_path / "project"
        scripts_dir = project_root / ".ai" / "scripts" / "test"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        script_file = scripts_dir / "test_script.py"
        script_file.write_text("def execute(params): pass")
        
        tool.resolver.project_root = project_root
        tool.resolver.project_scripts = project_root / ".ai" / "scripts"
        
        result = await tool.execute({
            'script_name': 'test_script',
            'tier': 'project',
            'category': 'test',
            'dry_run': True
        })
        
        result_data = json.loads(result)
        assert result_data['dry_run'] is True
        assert result_data['removals']['project']['dry_run'] is True
        assert result_data['removals']['project']['would_remove'] is True
        # Script should still exist
        assert script_file.exists()
    
    @pytest.mark.asyncio
    async def test_remove_all_tiers(self, mock_script_registry, tmp_path):
        """Test removing from all tiers"""
        tool = RemoveTool()
        tool.registry = mock_script_registry
        
        # Create scripts in both project and user space
        project_root = tmp_path / "project"
        project_scripts_dir = project_root / ".ai" / "scripts" / "test"
        project_scripts_dir.mkdir(parents=True, exist_ok=True)
        project_script = project_scripts_dir / "test_script.py"
        project_script.write_text("def execute(params): pass")
        
        user_home = tmp_path / "home" / "user"
        user_scripts_dir = user_home / ".script-kiwi" / "scripts" / "test"
        user_scripts_dir.mkdir(parents=True, exist_ok=True)
        user_script = user_scripts_dir / "test_script.py"
        user_script.write_text("def execute(params): pass")
        
        tool.resolver.project_root = project_root
        tool.resolver.project_scripts = project_root / ".ai" / "scripts"
        tool.resolver.user_home = user_home
        tool.resolver.user_scripts = user_home / ".script-kiwi" / "scripts"
        
        result = await tool.execute({
            'script_name': 'test_script',
            'tier': 'all',
            'category': 'test'
        })
        
        result_data = json.loads(result)
        assert result_data['removals']['project']['removed'] is True
        assert result_data['removals']['user']['removed'] is True
        assert result_data['summary']['successful'] == 2
        assert not project_script.exists()
        assert not user_script.exists()
    
    @pytest.mark.asyncio
    async def test_remove_lib_script(self, mock_script_registry, tmp_path):
        """Test removing lib script"""
        tool = RemoveTool()
        tool.registry = mock_script_registry
        
        # Create lib script in project space
        project_root = tmp_path / "project"
        lib_dir = project_root / ".ai" / "scripts" / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        
        lib_file = lib_dir / "test_lib.py"
        lib_file.write_text("def helper(): pass")
        
        tool.resolver.project_root = project_root
        tool.resolver.project_scripts = project_root / ".ai" / "scripts"
        
        result = await tool.execute({
            'script_name': 'test_lib',
            'tier': 'project',
            'is_lib': True
        })
        
        result_data = json.loads(result)
        assert result_data['removals']['project']['removed'] is True
        assert not lib_file.exists()
    
    @pytest.mark.asyncio
    async def test_remove_missing_script_name(self, mock_script_registry):
        """Test error when script_name is missing"""
        tool = RemoveTool()
        tool.registry = mock_script_registry
        
        result = await tool.execute({})
        
        result_data = json.loads(result)
        assert 'error' in result_data
        assert 'script_name' in result_data['error'].lower()

