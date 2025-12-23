# Script Kiwi MCP

Script execution MCP server with directive-based architecture.

## Overview

Script Kiwi provides a platform for executing deterministic Python scripts with versioning, cost tracking, and execution logging. It follows the same 3-tier storage pattern as Context Kiwi (Project → User → Registry).

## Features

- **6 Core Tools**: `search`, `load`, `run`, `publish`, `help`, `remove`
- **3-Tier Storage**: Project space → User space → Registry
- **Version Control**: Semver-based script versioning
- **Cost Tracking**: Automatic cost calculation and logging
- **Execution Logging**: Dual logging to user space (`~/.script-kiwi/.runs/history.jsonl`) and Supabase `executions` table
- **Lockfile Support**: Version pinning per project
- **Lib Architecture**: Domain-specific utility libraries in `lib/` directory

## Setup

1. **Create Supabase Project**
   - Create new project at supabase.com
   - Save project URL and API keys

2. **Run Database Schema**
   ```bash
   # Copy SQL from docs/script-kiwi-schema.sql
   # Run in Supabase SQL Editor
   ```

3. **Configure Environment**
   ```bash
   # Set environment variables (or use .env file)
   export SUPABASE_URL="https://your-project.supabase.co"
   export SUPABASE_SECRET_KEY="your-service-role-key"
   ```

4. **Install Dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

5. **Test MCP Server**
   ```bash
   python -m script_kiwi.server
   ```

## Project Structure

**Script Kiwi core:**
```
script-kiwi/
├── script_kiwi/            # Core MCP server
│   ├── api/                # Supabase + external APIs
│   ├── tools/              # 6 core MCP tools
│   ├── utils/              # Shared utilities
│   └── server.py           # MCP server entry point
├── tests/                  # Test suite
├── docs/                   # Documentation
├── migrations/             # Database migrations
└── pyproject.toml          # Package configuration
```

**Script storage (created by users):**
```
User projects create their own script spaces:

project/
├── .ai/
│   └── scripts/            # Project-local scripts (optional)
│       ├── scraping/
│       ├── enrichment/
│       ├── extraction/
│       └── lib/            # Project-specific utility libraries

~/.script-kiwi/
└── scripts/                # User space (auto-created)
    ├── scraping/           # Downloaded/shared scripts
    ├── enrichment/
    ├── extraction/
    └── lib/                # Shared utility libraries
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed storage tier information.

## Tools

### search
Find scripts by describing what you want to do. Use this FIRST when you don't know the exact script name.

### load
Get script details AFTER finding it with 'search'. Returns: what parameters it needs, dependencies, cost estimates, and how to run it.

### run
Execute a script. Use AFTER 'load' to see what parameters are needed. Always use `dry_run=true` first to validate inputs.

### publish
Upload a script to the shared registry so others can use it. Script must exist in project space (`.ai/scripts/`). Requires Supabase connection.

### help
Get guidance on workflows, examples, and how to use Script Kiwi. Use when you're unsure how to accomplish a task or need examples.

### remove
Delete a script from local storage (project/user) or registry. Use `dry_run=true` first to preview. Checks for dependencies before removal.

## The `project_path` Parameter

**Important for MCP usage**: Since the MCP server runs as a separate process (not in your project directory), you must pass `project_path` to find scripts in your project's `.ai/scripts/` folder.

```json
{
  "script_name": "my_script",
  "parameters": {"key": "value"},
  "project_path": "/home/user/my-project"
}
```

- **User space scripts** (`~/.script-kiwi/scripts/`): Work without `project_path`
- **Project space scripts** (`.ai/scripts/`): **Require** `project_path`

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full details on the 3-tier storage system.

## Status

✅ **Fully Operational** - All 6 tools implemented, tested, and ready to use.

## Next Steps

1. ✅ Set up Supabase project and run schema (`docs/script-kiwi-schema.sql`)
2. ✅ Configure environment variables (`SUPABASE_URL` and `SUPABASE_SECRET_KEY`)
3. ✅ Test MCP server connection
4. ✅ All 111 tests passing
5. ⚠️ Add real scripts (example scripts are templates)

See `NEXT_STEPS.md` for detailed setup instructions.
