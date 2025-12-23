#!/usr/bin/env python3
"""
Script Kiwi MCP Server

Script execution MCP server with directive-based architecture.
Provides 6 core tools: search, load, run, publish, help, remove
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import tools (will be implemented)
from .tools.search import SearchTool
from .tools.load import LoadTool
from .tools.run import RunTool
from .tools.publish import PublishTool
from .tools.help import HelpTool
from .tools.remove import RemoveTool


class ScriptKiwiMCP:
    """Script execution MCP server with directive-based architecture"""
    
    def __init__(self):
        self.server = Server("script-kiwi")
        self.setup_tools()
    
    def setup_tools(self):
        """
        Register the 6 core Script Kiwi tools.
        
        Typical workflow for LLMs:
        1. search() - Find scripts by describing what you want to do
        2. load() - Get script details and required parameters
        3. run() - Execute script with parameters (use dry_run=true first)
        4. help() - Get guidance when unsure
        5. publish() - Share scripts to registry
        6. remove() - Delete scripts (use dry_run=true first)
        """
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="search",
                    description="Find scripts using natural language search. Use this FIRST when you don't know the exact script name. Searches across project, user, and registry. Supports multi-term queries - all terms must match for best results. Returns script names you can use with 'load' and 'run'.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Natural language search query supporting multiple terms. Examples: 'scrape Google Maps', 'JWT authentication', 'form validation', 'extract YouTube transcripts'. All terms must match for best results. Be specific about the task.",
                                "examples": ["scrape Google Maps leads", "enrich email addresses", "validate emails", "extract YouTube video transcript", "JWT authentication", "form validation"]
                            },
                            "category": {
                                "type": "string",
                                "description": "Filter by category. Use 'all' (default) to search all categories. Any category name is valid (e.g., 'scraping', 'enrichment', 'lib', 'data-processing'). Categories are dynamic - organize scripts however makes sense.",
                                "default": "all",
                                "examples": ["scraping", "enrichment", "extraction", "validation", "lib", "utility", "all"]
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max results to return. Default: 10. Use 5-10 for most cases.",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 50
                            },
                            "project_path": {
                                "type": "string",
                                "description": "CRITICAL: Project root path where .ai/scripts/ lives. Required when MCP server CWD differs from workspace. Example: '/home/user/myproject'."
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="load",
                    description="Get script details AFTER finding it with 'search'. Returns: what parameters it needs, dependencies, cost estimates, and how to run it. Use this to understand a script before running it.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "script_name": {
                                "type": "string",
                                "description": "Script name from 'search' results. Example: 'google_maps_leads', 'email_waterfall'. Do NOT include .py extension.",
                                "examples": ["google_maps_leads", "email_waterfall", "validate_emails"]
                            },
                            "sections": {
                                "type": "array",
                                "items": {"type": "string", "enum": ["inputs", "dependencies", "cost", "all"]},
                                "description": "What to load. Use ['all'] (default) to get everything. Use ['inputs'] to see only required parameters.",
                                "default": ["all"]
                            },
                            "download_to_user": {
                                "type": "boolean",
                                "description": "If true, download script from registry to user space for faster future access. Use true if you'll run it multiple times. Default: false.",
                                "default": False
                            },
                            "version": {
                                "type": "string",
                                "description": "Specific version like '1.2.0'. Leave empty for latest version. Only needed if you want a specific version.",
                                "examples": ["1.0.0", "2.1.3"]
                            },
                            "project_path": {
                                "type": "string",
                                "description": "CRITICAL: Project root path where .ai/scripts/ lives. Required when MCP server CWD differs from workspace. Example: '/home/user/myproject'."
                            }
                        },
                        "required": ["script_name"]
                    }
                ),
                Tool(
                    name="run",
                    description="Execute a script. Use AFTER 'load' to see what parameters are needed. Pass parameters as a dictionary. Returns execution result or error. Always use dry_run=true first to validate inputs.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "script_name": {
                                "type": "string",
                                "description": "Script name from 'search' or 'load'. Example: 'google_maps_leads'. Do NOT include .py extension.",
                                "examples": ["google_maps_leads", "email_waterfall"]
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Script parameters as key-value pairs. Get required parameters from 'load' tool first. Example: {'search_term': 'dentist', 'location': 'Texas', 'max_results': 10}",
                                "examples": [
                                    {"search_term": "dentist", "location": "Texas", "max_results": 10},
                                    {"emails": ["test@example.com"], "validate_format": True}
                                ]
                            },
                            "dry_run": {
                                "type": "boolean",
                                "description": "If true, validate inputs without executing. ALWAYS use true first to check parameters are correct. Then set false to actually run.",
                                "default": False
                            },
                            "project_path": {
                                "type": "string",
                                "description": "CRITICAL: Project root path where .ai/scripts/ lives. Required when MCP server CWD differs from workspace. Example: '/home/user/myproject'."
                            }
                        },
                        "required": ["script_name", "parameters"]
                    }
                ),
                Tool(
                    name="publish",
                    description="Upload a script to the shared registry so others can use it. Script must exist in project space (.ai/scripts/). Requires Supabase connection. Use semantic versioning (1.0.0, 1.1.0, 2.0.0).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "script_name": {
                                "type": "string",
                                "description": "Script name (without .py). Script must exist in .ai/scripts/{category}/. Example: 'my_scraper'.",
                                "examples": ["google_maps_scraper", "email_validator"]
                            },
                            "version": {
                                "type": "string",
                                "description": "Semantic version: MAJOR.MINOR.PATCH. Examples: '1.0.0' (first release), '1.1.0' (new features), '2.0.0' (breaking changes). Must be valid semver.",
                                "pattern": "^\\d+\\.\\d+\\.\\d+$",
                                "examples": ["1.0.0", "1.2.3", "2.0.0"]
                            },
                            "category": {
                                "type": "string",
                                "description": "Script category. Any category name is valid (e.g., 'scraping', 'enrichment', 'lib', 'data-processing'). Should match the folder name in .ai/scripts/ if organized by category. Optional - will be auto-detected from directory structure if not provided.",
                                "examples": ["scraping", "enrichment", "validation", "lib", "utility", "data-processing"]
                            },
                            "subcategory": {
                                "type": "string",
                                "description": "Optional subcategory for nested organization (e.g., 'google-maps' for category 'scraping'). Will be auto-detected from directory structure if script is in a nested folder like .ai/scripts/scraping/google-maps/.",
                                "examples": ["google-maps", "email-finding", "etl", "api-integration"]
                            },
                            "changelog": {
                                "type": "string",
                                "description": "Optional changelog describing what changed in this version."
                            },
                            "metadata": {
                                "type": "object",
                                "description": "Optional metadata dictionary. Can include: description, dependencies (list of {name, version}), required_env_vars (list), tech_stack (list), tags (list), cost_per_unit (number), cost_unit (string), module_path (string).",
                                "properties": {
                                    "description": {"type": "string"},
                                    "dependencies": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "name": {"type": "string"},
                                                "version": {"type": "string"}
                                            },
                                            "required": ["name"]
                                        },
                                        "description": "List of pip package dependencies. Format: [{\"name\": \"package-name\", \"version\": \">=1.0.0\"}]"
                                    },
                                    "required_env_vars": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "List of required environment variable names"
                                    },
                                    "tech_stack": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "List of technologies used"
                                    },
                                    "tags": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "List of tags for categorization"
                                    },
                                    "cost_per_unit": {"type": "number"},
                                    "cost_unit": {"type": "string"},
                                    "module_path": {"type": "string"}
                                }
                            },
                            "project_path": {
                                "type": "string",
                                "description": "CRITICAL: Project root path where .ai/scripts/ lives. Required when MCP server CWD differs from workspace. Example: '/home/user/myproject'."
                            }
                        },
                        "required": ["script_name", "version"]
                    }
                ),
                Tool(
                    name="help",
                    description="Get guidance on workflows, examples, and how to use Script Kiwi. Use when you're unsure how to accomplish a task or need examples. Ask about workflows like 'scrape leads', 'enrich emails', or 'complete campaign workflow'.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "What you need help with. Examples: 'how do I scrape leads', 'email enrichment workflow', 'how to run a script', 'complete campaign workflow'. Be specific about the task.",
                                "examples": ["how do I scrape leads", "email enrichment", "how to run scripts", "complete workflow"]
                            },
                            "context": {
                                "type": "string",
                                "description": "Optional: Additional details about your situation. Example: 'I have 1000 company names and need emails'.",
                                "examples": ["I have company names and need emails", "I want to scrape 500 leads"]
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="remove",
                    description="Delete a script from local storage (project/user) or registry. Use dry_run=true first to preview. Checks for dependencies before removal. For registry, 'deprecate' (default) is safer than 'delete'.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "script_name": {
                                "type": "string",
                                "description": "Script name to remove (without .py). Example: 'old_scraper'.",
                                "examples": ["test_script", "old_scraper"]
                            },
                            "tier": {
                                "type": "string",
                                "enum": ["project", "user", "registry", "all"],
                                "description": "Where to remove from: 'project' (.ai/scripts/), 'user' (~/.script-kiwi/scripts/), 'registry' (Supabase), or 'all' (all locations). Default: 'all'.",
                                "default": "all",
                                "examples": ["project", "user", "all"]
                            },
                            "category": {
                                "type": "string",
                                "description": "Optional: Script category. Auto-detected if not provided. Only needed if script exists in multiple categories.",
                                "examples": ["scraping", "enrichment"]
                            },
                            "dry_run": {
                                "type": "boolean",
                                "description": "If true, show what WOULD be deleted without actually deleting. ALWAYS use true first to preview. Default: false.",
                                "default": False
                            },
                            "force": {
                                "type": "boolean",
                                "description": "If true, remove even if other scripts depend on it. Use with caution. Default: false.",
                                "default": False
                            },
                            "is_lib": {
                                "type": "boolean",
                                "description": "If true, treat as library script (in lib/ folder). Auto-detected if not provided. Default: false.",
                                "default": False
                            },
                            "action": {
                                "type": "string",
                                "enum": ["delete", "deprecate"],
                                "description": "For registry only: 'deprecate' (safer, marks as deprecated) or 'delete' (permanent removal). Default: 'deprecate'.",
                                "default": "deprecate"
                            },
                            "version": {
                                "type": "string",
                                "description": "For registry only: specific version to remove (e.g., '1.0.0'). Leave empty to remove all versions.",
                                "examples": ["1.0.0", "2.1.3"]
                            }
                        },
                        "required": ["script_name"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool execution."""
            try:
                if name == "search":
                    tool = SearchTool()
                    result = await tool.execute(arguments)
                elif name == "load":
                    tool = LoadTool()
                    result = await tool.execute(arguments)
                elif name == "run":
                    # Extract project_path from arguments if provided
                    project_path = arguments.pop("project_path", None)
                    tool = RunTool(project_path=project_path)
                    result = await tool.execute(arguments)
                elif name == "publish":
                    tool = PublishTool()
                    result = await tool.execute(arguments)
                elif name == "help":
                    tool = HelpTool()
                    result = await tool.execute(arguments)
                elif name == "remove":
                    tool = RemoveTool()
                    result = await tool.execute(arguments)
                else:
                    return [TextContent(
                        type="text",
                        text=f'{{"error": "Unknown tool: {name}"}}'
                    )]
                
                return [TextContent(type="text", text=result)]
            except Exception as e:
                import traceback
                error_msg = {
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
                import json
                return [TextContent(
                    type="text",
                    text=json.dumps(error_msg, indent=2)
                )]
    
    async def run(self):
        """Start the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


def main():
    """Entry point for the MCP server"""
    server = ScriptKiwiMCP()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
