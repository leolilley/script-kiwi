"""
Tests for script resolver with dynamic categorization and subfolder support.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from script_kiwi.utils.script_resolver import ScriptResolver


class TestScriptResolverCategoryExtraction:
    """Tests for category extraction from paths"""
    
    def test_extract_category_simple(self):
        """Test extracting category from simple path"""
        resolver = ScriptResolver()
        
        # Simple category
        path = Path("/project/.ai/scripts/scraping/example.py")
        category = resolver._extract_category_from_path(path)
        assert category == "scraping"
    
    def test_extract_category_nested(self):
        """Test extracting category from nested path"""
        resolver = ScriptResolver()
        
        # Nested subcategory - should still return top-level category
        path = Path("/project/.ai/scripts/scraping/google-maps/example.py")
        category = resolver._extract_category_from_path(path)
        assert category == "scraping"
    
    def test_extract_category_dynamic(self):
        """Test extracting dynamic category names"""
        resolver = ScriptResolver()
        
        # Dynamic category
        path = Path("/project/.ai/scripts/data-processing/api-integration/script.py")
        category = resolver._extract_category_from_path(path)
        assert category == "data-processing"
    
    def test_extract_category_user_space(self):
        """Test extracting category from user space path"""
        resolver = ScriptResolver()
        
        path = Path("/home/user/.script-kiwi/scripts/enrichment/email_finder.py")
        category = resolver._extract_category_from_path(path)
        assert category == "enrichment"
    
    def test_extract_category_custom(self):
        """Test extracting custom category names"""
        resolver = ScriptResolver()
        
        # Custom category
        path = Path("/project/.ai/scripts/custom-category/my-script.py")
        category = resolver._extract_category_from_path(path)
        assert category == "custom-category"


class TestScriptResolverNestedDirectories:
    """Tests for resolving scripts in nested directories"""
    
    @pytest.mark.asyncio
    async def test_resolve_script_simple_category(self, tmp_path):
        """Test resolving script in simple category directory"""
        resolver = ScriptResolver(project_root=tmp_path)
        
        # Create script in simple category
        script_dir = tmp_path / ".ai" / "scripts" / "scraping"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_file = script_dir / "example.py"
        script_file.write_text("def execute(params): pass")
        
        resolved = await resolver.resolve_script("example")
        
        assert resolved["location"] == "project"
        assert resolved["path"] == script_file
        assert resolved["category"] == "scraping"
    
    @pytest.mark.asyncio
    async def test_resolve_script_nested_category(self, tmp_path):
        """Test resolving script in nested subcategory directory"""
        resolver = ScriptResolver(project_root=tmp_path)
        
        # Create script in nested category
        script_dir = tmp_path / ".ai" / "scripts" / "scraping" / "google-maps"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_file = script_dir / "example.py"
        script_file.write_text("def execute(params): pass")
        
        resolved = await resolver.resolve_script("example")
        
        assert resolved["location"] == "project"
        assert resolved["path"] == script_file
        assert resolved["category"] == "scraping"  # Top-level category
    
    @pytest.mark.asyncio
    async def test_resolve_script_dynamic_category(self, tmp_path):
        """Test resolving script with dynamic category name"""
        resolver = ScriptResolver(project_root=tmp_path)
        
        # Create script in dynamic category
        script_dir = tmp_path / ".ai" / "scripts" / "data-processing" / "etl"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_file = script_dir / "transform.py"
        script_file.write_text("def execute(params): pass")
        
        resolved = await resolver.resolve_script("transform")
        
        assert resolved["location"] == "project"
        assert resolved["path"] == script_file
        assert resolved["category"] == "data-processing"
    
    @pytest.mark.asyncio
    async def test_resolve_script_with_category_param(self, tmp_path):
        """Test resolving script with explicit category parameter"""
        resolver = ScriptResolver(project_root=tmp_path)
        
        # Create script in specific category
        script_dir = tmp_path / ".ai" / "scripts" / "scraping"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_file = script_dir / "example.py"
        script_file.write_text("def execute(params): pass")
        
        resolved = await resolver.resolve_script("example", category="scraping")
        
        assert resolved["location"] == "project"
        assert resolved["path"] == script_file
        assert resolved["category"] == "scraping"
    
    @pytest.mark.asyncio
    async def test_resolve_script_nested_with_category_param(self, tmp_path):
        """Test resolving script in nested directory with category param"""
        resolver = ScriptResolver(project_root=tmp_path)
        
        # Create script in nested category
        script_dir = tmp_path / ".ai" / "scripts" / "scraping" / "google-maps"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_file = script_dir / "example.py"
        script_file.write_text("def execute(params): pass")
        
        # Should find it even with just category param (searches recursively)
        resolved = await resolver.resolve_script("example", category="scraping")
        
        assert resolved["location"] == "project"
        assert resolved["path"] == script_file
        assert resolved["category"] == "scraping"


class TestScriptResolverUserSpace:
    """Tests for resolving scripts in user space with nested directories"""
    
    @pytest.mark.asyncio
    async def test_resolve_script_user_space_nested(self, tmp_path, monkeypatch):
        """Test resolving script from user space with nested directory"""
        # Mock user home
        user_scripts = tmp_path / ".script-kiwi" / "scripts"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        
        resolver = ScriptResolver(project_root=Path("/tmp/project"))
        
        # Create script in user space nested category
        script_dir = user_scripts / "enrichment" / "email-finding"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_file = script_dir / "email_finder.py"
        script_file.write_text("def execute(params): pass")
        
        resolved = await resolver.resolve_script("email_finder")
        
        assert resolved["location"] == "user"
        assert resolved["path"] == script_file
        assert resolved["category"] == "enrichment"


class TestScriptResolverSubcategoryExtraction:
    """Tests for subcategory extraction from paths"""
    
    def test_extract_subcategory_simple_path(self):
        """Test extracting subcategory from nested path"""
        resolver = ScriptResolver()
        
        # Nested subcategory
        path = Path("/project/.ai/scripts/scraping/google-maps/example.py")
        subcategory = resolver._extract_subcategory_from_path(path)
        assert subcategory == "google-maps"
    
    def test_extract_subcategory_no_subcategory(self):
        """Test extracting subcategory from simple path (no subcategory)"""
        resolver = ScriptResolver()
        
        # Simple category, no subcategory
        path = Path("/project/.ai/scripts/scraping/example.py")
        subcategory = resolver._extract_subcategory_from_path(path)
        assert subcategory is None
    
    def test_extract_subcategory_user_space(self):
        """Test extracting subcategory from user space path"""
        resolver = ScriptResolver()
        
        path = Path("/home/user/.script-kiwi/scripts/enrichment/email-finding/email_finder.py")
        subcategory = resolver._extract_subcategory_from_path(path)
        assert subcategory == "email-finding"
    
    def test_extract_subcategory_dynamic(self):
        """Test extracting subcategory with dynamic category names"""
        resolver = ScriptResolver()
        
        path = Path("/project/.ai/scripts/data-processing/api-integration/stripe_webhook.py")
        subcategory = resolver._extract_subcategory_from_path(path)
        assert subcategory == "api-integration"
    
    def test_extract_subcategory_lib_category(self):
        """Test extracting subcategory from lib category (should be None)"""
        resolver = ScriptResolver()
        
        # Lib category doesn't have subcategories typically
        path = Path("/project/.ai/scripts/lib/youtube_utils.py")
        subcategory = resolver._extract_subcategory_from_path(path)
        assert subcategory is None


class TestScriptResolverSubcategoryResolution:
    """Tests for resolving scripts with subcategory detection"""
    
    @pytest.mark.asyncio
    async def test_resolve_script_with_subcategory(self, tmp_path):
        """Test resolving script in nested subcategory directory"""
        resolver = ScriptResolver(project_root=tmp_path)
        
        # Create script in nested category
        script_dir = tmp_path / ".ai" / "scripts" / "scraping" / "google-maps"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_file = script_dir / "example.py"
        script_file.write_text("def execute(params): pass")
        
        resolved = await resolver.resolve_script("example")
        
        assert resolved["location"] == "project"
        assert resolved["path"] == script_file
        assert resolved["category"] == "scraping"
        assert resolved["subcategory"] == "google-maps"
    
    @pytest.mark.asyncio
    async def test_resolve_script_without_subcategory(self, tmp_path):
        """Test resolving script without subcategory"""
        resolver = ScriptResolver(project_root=tmp_path)
        
        # Create script in simple category
        script_dir = tmp_path / ".ai" / "scripts" / "scraping"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_file = script_dir / "example.py"
        script_file.write_text("def execute(params): pass")
        
        resolved = await resolver.resolve_script("example")
        
        assert resolved["location"] == "project"
        assert resolved["path"] == script_file
        assert resolved["category"] == "scraping"
        assert resolved["subcategory"] is None
    
    @pytest.mark.asyncio
    async def test_resolve_script_lib_category(self, tmp_path):
        """Test resolving script in lib category"""
        resolver = ScriptResolver(project_root=tmp_path)
        
        # Create script in lib category
        script_dir = tmp_path / ".ai" / "scripts" / "lib"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_file = script_dir / "youtube_utils.py"
        script_file.write_text("def extract_video_id(url): pass")
        
        resolved = await resolver.resolve_script("youtube_utils")
        
        assert resolved["location"] == "project"
        assert resolved["path"] == script_file
        assert resolved["category"] == "lib"
        assert resolved["subcategory"] is None
    
    @pytest.mark.asyncio
    async def test_resolve_script_registry_with_subcategory(self, mock_script_registry):
        """Test resolving script from registry with subcategory"""
        resolver = ScriptResolver(registry_client=mock_script_registry)
        
        from unittest.mock import AsyncMock
        mock_script_registry.get_script = AsyncMock(return_value={
            "name": "example",
            "category": "scraping",
            "subcategory": "google-maps",
            "version": "1.0.0",
            "content": "def execute(params): pass"
        })
        
        resolved = await resolver.resolve_script("example")
        
        assert resolved["location"] == "registry"
        assert resolved["category"] == "scraping"
        assert resolved["subcategory"] == "google-maps"


class TestScriptResolverDownloadWithSubcategory:
    """Tests for downloading scripts with subcategories"""
    
    def test_download_to_user_space_simple(self, tmp_path, monkeypatch):
        """Test downloading script to user space with simple category"""
        user_scripts = tmp_path / ".script-kiwi" / "scripts"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        
        resolver = ScriptResolver(project_root=Path("/tmp/project"))
        
        script_path = resolver.download_to_user_space(
            script_name="test_script",
            category="scraping",
            content="def execute(params): pass"
        )
        
        assert script_path.exists()
        assert script_path.parent.name == "scraping"
        assert script_path.name == "test_script.py"
    
    def test_download_to_user_space_with_subcategory(self, tmp_path, monkeypatch):
        """Test downloading script to user space with subcategory"""
        user_scripts = tmp_path / ".script-kiwi" / "scripts"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        
        resolver = ScriptResolver(project_root=Path("/tmp/project"))
        
        script_path = resolver.download_to_user_space(
            script_name="test_script",
            category="scraping",
            subcategory="google-maps",
            content="def execute(params): pass"
        )
        
        assert script_path.exists()
        assert script_path.parent.name == "google-maps"
        assert script_path.parent.parent.name == "scraping"
        assert script_path.name == "test_script.py"
        
        # Verify content
        assert script_path.read_text() == "def execute(params): pass"
    
    async def test_resolve_script_with_explicit_project_path(self, tmp_path):
        """Test resolving script with explicit project_path"""
        project_path = tmp_path / "project"
        project_scripts = project_path / ".ai" / "scripts" / "extraction"
        project_scripts.mkdir(parents=True)
        
        script_file = project_scripts / "test_script.py"
        script_file.write_text("# test script")
        
        # Create resolver with explicit project_path
        resolver = ScriptResolver(project_root=project_path)
        
        # Verify project_root is set correctly
        assert resolver.project_root == project_path
        assert resolver.project_scripts == project_scripts.parent
        
        # Resolve script
        result = await resolver.resolve_script("test_script")
        
        assert result['location'] == 'project'
        assert result['path'] == script_file
        assert result['category'] == 'extraction'
    
    async def test_resolve_script_project_path_priority(self, tmp_path, monkeypatch):
        """Test that explicit project_path takes priority over CWD"""
        # Create project structure
        project_path = tmp_path / "project"
        project_scripts = project_path / ".ai" / "scripts" / "extraction"
        project_scripts.mkdir(parents=True)
        
        script_file = project_scripts / "test_script.py"
        script_file.write_text("# test script")
        
        # Create another directory that would be CWD
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        
        # Mock Path.cwd() to return other_dir
        original_cwd = Path.cwd
        monkeypatch.setattr(Path, "cwd", lambda: other_dir)
        
        # Create resolver with explicit project_path
        resolver = ScriptResolver(project_root=project_path)
        
        # Should still find script in project_path, not CWD
        result = await resolver.resolve_script("test_script")
        
        assert result['location'] == 'project'
        assert result['path'] == script_file

