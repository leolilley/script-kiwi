# MCP Client Configuration

Script Kiwi MCP can be configured in two ways:

## Option 1: Using the Console Script (Recommended)

The package installs a `script-kiwi` console script that can be used directly:

```json
{
  "mcpServers": {
    "script-kiwi": {
      "command": "/home/leo/projects/script-kiwi/.venv/bin/script-kiwi",
      "cwd": "/home/leo/projects/script-kiwi"
    }
  }
}
```

Or if the venv is in your PATH:

```json
{
  "mcpServers": {
    "script-kiwi": {
      "command": "script-kiwi",
      "cwd": "/home/leo/projects/script-kiwi"
    }
  }
}
```

## Option 2: Using Python Module (More Reliable)

This is the recommended approach as it's more portable:

```json
{
  "mcpServers": {
    "script-kiwi": {
      "command": "python",
      "args": ["-m", "script_kiwi.server"],
      "cwd": "/home/leo/projects/script-kiwi",
      "env": {
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Full Path to Python (Most Reliable)

If you want to be explicit about which Python to use:

```json
{
  "mcpServers": {
    "script-kiwi": {
      "command": "/home/leo/projects/script-kiwi/.venv/bin/python",
      "args": ["-m", "script_kiwi.server"],
      "cwd": "/home/leo/projects/script-kiwi"
    }
  }
}
```

## Verification

After configuring, the MCP client should be able to:
1. Start the server without errors
2. List available tools (search, load, run, publish, help, remove)
3. Execute tool calls

## Environment Variables

The MCP server requires these environment variables:
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_SECRET_KEY` - Your Supabase service role key (or `SCRIPT_KIWI_API_KEY` as fallback)

**These can be set in two ways:**

1. **In the MCP config's `env` section** (recommended for MCP):
```json
{
  "mcpServers": {
    "script-kiwi": {
      "command": "python",
      "args": ["-m", "script_kiwi.server"],
      "cwd": "/home/leo/projects/script-kiwi",
      "env": {
        "SUPABASE_URL": "https://xxx.supabase.co",
        "SUPABASE_SECRET_KEY": "your-secret-key"
      }
    }
  }
}
```

2. **In a `.env` file** in the project root (automatically loaded via `load_dotenv()`):
```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SECRET_KEY=your-secret-key
```

**Note:** The server reads from both sources - MCP env vars take precedence over `.env` file.

## Troubleshooting

If you see `ENOENT` errors:
- Make sure the path to the command is correct
- Make sure the virtual environment is activated or use full path
- Try Option 2 (Python module) instead of Option 1 (console script)

