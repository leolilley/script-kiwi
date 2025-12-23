"""
Tests for help tool.
"""

import pytest
import json

from script_kiwi.tools.help import HelpTool


class TestHelpTool:
    """Tests for HelpTool"""
    
    def test_tool_initialization(self):
        """Test tool initialization"""
        tool = HelpTool()
        assert hasattr(tool, 'execute')
    
    @pytest.mark.asyncio
    async def test_help_scraping(self):
        """Test help for scraping"""
        tool = HelpTool()
        
        result = await tool.execute({
            'query': 'scrape leads'
        })
        
        result_data = json.loads(result)
        assert result_data['topic'] == 'Lead Scraping'
        assert 'workflow' in result_data
        assert 'common_scripts' in result_data
    
    @pytest.mark.asyncio
    async def test_help_enrichment(self):
        """Test help for enrichment"""
        tool = HelpTool()
        
        result = await tool.execute({
            'query': 'enrich emails'
        })
        
        result_data = json.loads(result)
        assert result_data['topic'] == 'Email Enrichment'
        assert 'workflow' in result_data
        assert 'strategies' in result_data
    
    @pytest.mark.asyncio
    async def test_help_workflow(self):
        """Test help for workflow"""
        tool = HelpTool()
        
        result = await tool.execute({
            'query': 'campaign workflow'
        })
        
        result_data = json.loads(result)
        assert result_data['topic'] == 'Complete Outbound Campaign Workflow'
        assert 'steps' in result_data
    
    @pytest.mark.asyncio
    async def test_help_general(self):
        """Test general help"""
        tool = HelpTool()
        
        result = await tool.execute({
            'query': 'how do I use this'
        })
        
        result_data = json.loads(result)
        assert 'available_tools' in result_data
        assert 'script_categories' in result_data
        assert 'getting_started' in result_data

