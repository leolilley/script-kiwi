# Script Kiwi Architecture

## Overview

Script Kiwi is an MCP server for executing Python scripts with a 3-tier storage system. It enables:
- **Sharing scripts** via a central registry
- **Local customization** via project-level overrides
- **Portable runtime** via user-space dependencies

## Storage Tiers

Scripts are resolved in priority order:

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. PROJECT SPACE (highest priority)                                │
│     Location: <project>/.ai/scripts/                                │
│     Purpose: Project-specific scripts, local edits/overrides        │
│     Requires: project_path parameter when MCP CWD ≠ project dir     │
├─────────────────────────────────────────────────────────────────────┤
│  2. USER SPACE                                                      │
│     Location: ~/.script-kiwi/scripts/                               │
│     Purpose: Downloaded scripts, shared libs, runtime environment   │
│     Always accessible (uses $HOME)                                  │
├─────────────────────────────────────────────────────────────────────┤
│  3. REGISTRY (lowest priority)                                      │
│     Location: Supabase (remote)                                     │
│     Purpose: Shared scripts, versioning, discovery                  │
│     Requires: Network + Supabase credentials                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Directory Structure

**Project Space** (`.ai/scripts/`):
```
my-project/
└── .ai/
    └── scripts/
        ├── scraping/
        │   ├── __init__.py
        │   └── my_scraper.py
        ├── extraction/
        │   └── extract_youtube_transcript.py
        └── lib/
            ├── __init__.py
            └── my_utils.py          # Project-specific overrides
```

**User Space** (`~/.script-kiwi/`):
```
~/.script-kiwi/
├── scripts/
│   ├── scraping/
│   │   └── google_maps_leads.py    # Downloaded from registry
│   ├── lib/
│   │   ├── __init__.py
│   │   ├── youtube_utils.py        # Shared library
│   │   └── http_session.py         # Shared library
│   └── enrichment/
│       └── email_waterfall.py
└── .runs/
    └── history.jsonl               # Execution history
```

## Script Resolution

When you run `extract_youtube_transcript`:

1. **Check Project Space**: `<project>/.ai/scripts/**/extract_youtube_transcript.py`
2. **Check User Space**: `~/.script-kiwi/scripts/**/extract_youtube_transcript.py`
3. **Check Registry**: Query Supabase for script

First match wins. This allows:
- **Override registry scripts** by copying to project space
- **Edit locally** without affecting shared version
- **Test changes** before publishing back

## Runtime Environment

When a script executes, `PYTHONPATH` includes **both** tiers:

```
PYTHONPATH priority (first = highest):
1. Script's own directory         # Relative imports within category
2. Script's scripts root          # e.g., .ai/scripts/
3. Project scripts root           # .ai/scripts/ (if project_path provided)
4. User scripts root              # ~/.script-kiwi/scripts/ (ALWAYS included)
5. script_kiwi package            # MCP utilities
```

This means:
- A script in **project space** can import libs from **user space**
- Project libs take priority over user libs (local overrides work)
- User space is the "runtime environment" with shared dependencies

### Example: Import Resolution

```python
# In .ai/scripts/extraction/extract_youtube_transcript.py
from lib.youtube_utils import extract_video_id
from lib.http_session import get_session
```

Resolution order:
1. `<project>/.ai/scripts/lib/youtube_utils.py` (if exists)
2. `~/.script-kiwi/scripts/lib/youtube_utils.py` (fallback)

## The `project_path` Parameter

### Why It's Needed

MCP servers run as separate processes. Their current working directory (CWD) is typically:
- The user's home directory
- The MCP installation location
- Some system directory

**Not** your project directory.

The `project_path` parameter tells the MCP where your project lives so it can find `.ai/scripts/`.

### When to Use It

| Scenario | `project_path` needed? |
|----------|------------------------|
| Running scripts from user space (`~/.script-kiwi/`) | No |
| Running scripts from project space (`.ai/scripts/`) | **Yes** |
| Searching for scripts in project | **Yes** |
| Loading script details from project | **Yes** |
| Publishing scripts from project | **Yes** |

### How to Use It

```json
{
  "script_name": "extract_youtube_transcript",
  "parameters": {
    "video_url": "https://youtube.com/watch?v=..."
  },
  "project_path": "/home/user/my-project"
}
```

For Cursor users, you can use the workspace path:
```json
{
  "project_path": "/home/leo/projects/script-kiwi"
}
```

## Workflows

### 1. Run a Script from Registry

```
search("extract youtube transcript")
  → finds: extract_youtube_transcript (registry)

load("extract_youtube_transcript", download_to_user=true)
  → downloads to ~/.script-kiwi/scripts/extraction/
  → downloads lib dependencies to ~/.script-kiwi/scripts/lib/

run("extract_youtube_transcript", {"video_url": "..."})
  → runs from user space (no project_path needed)
```

### 2. Run a Project-Local Script

```
run("my_custom_script", {"param": "value"}, project_path="/home/user/project")
  → finds in .ai/scripts/
  → runs with both project and user libs in PYTHONPATH
```

### 3. Override and Edit a Script

```
# 1. Download to user space first
load("google_maps_leads", download_to_user=true)

# 2. Copy to project for editing
cp ~/.script-kiwi/scripts/scraping/google_maps_leads.py \
   ./ai/scripts/scraping/google_maps_leads.py

# 3. Edit your local copy
# ... make changes ...

# 4. Run - project version takes priority
run("google_maps_leads", {...}, project_path="/home/user/project")

# 5. Publish your improved version
publish("google_maps_leads", "1.1.0", project_path="/home/user/project")
```

### 4. Create Shared Libraries

Libraries in `lib/` are shared across scripts:

```python
# ~/.script-kiwi/scripts/lib/http_session.py
def get_session(domain, proxy=None, cookies=None):
    """Reusable HTTP session with proxy/cookie support."""
    ...

# Any script can use it:
from lib.http_session import get_session
```

## Categories and Subcategories

Scripts are organized by category (directory name):

```
.ai/scripts/
├── scraping/              # category: "scraping"
│   ├── google_maps.py
│   └── google-maps/       # subcategory: "google-maps"
│       └── places_api.py
├── extraction/            # category: "extraction"
├── enrichment/            # category: "enrichment"
├── validation/            # category: "validation"
└── lib/                   # category: "lib" (shared libraries)
```

Categories are **dynamic** - create any directory structure that makes sense for your project.

## Script Types

### 1. Function-Based Scripts (Recommended)

```python
def execute(params: dict) -> dict:
    """Main entry point called by Script Kiwi."""
    video_url = params.get("video_url")
    # ... do work ...
    return {
        "status": "success",
        "data": {"transcript": "..."},
        "metadata": {"duration_sec": 1.5}
    }
```

### 2. Argparse-Based Scripts (CLI)

```python
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-url", required=True)
    args = parser.parse_args()
    # ... do work ...
    print(json.dumps({"status": "success", ...}))

if __name__ == "__main__":
    main()
```

Script Kiwi detects argparse scripts and runs them as subprocesses, converting parameters to CLI arguments.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL` | Registry database URL |
| `SUPABASE_KEY` | Registry API key |
| `SCRIPT_KIWI_HOME` | Override user space location (default: `~/.script-kiwi`) |

## Troubleshooting

### "Script not found"

1. **For project scripts**: Pass `project_path` parameter
2. **For user scripts**: Check `~/.script-kiwi/scripts/` exists
3. **For registry scripts**: Use `load(..., download_to_user=true)` first

### "Module not found" (lib imports)

1. Ensure lib exists in user space: `~/.script-kiwi/scripts/lib/`
2. Ensure `__init__.py` exists in lib directory
3. Check PYTHONPATH includes both project and user space

### Script runs locally but not via MCP

The MCP server has a different CWD. Always pass `project_path` for project-space scripts.

## Best Practices

1. **Keep shared libs in user space** - They're your runtime environment
2. **Use project space for edits** - Override without affecting shared version
3. **Always pass `project_path`** - When working with project-local scripts
4. **Use `dry_run=true` first** - Validate before executing
5. **Semantic versioning** - When publishing to registry
