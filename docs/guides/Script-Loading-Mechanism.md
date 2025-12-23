# Script Loading & Running Mechanism

## Overview

Script Kiwi uses a 3-tier storage system (same pattern as Context Kiwi) with resolution priority: **Project → User → Registry**.

## Storage Tiers

### 1. Project Space (`.ai/scripts/`)
- **Purpose**: Project-specific scripts, one-off tasks
- **Priority**: Highest (checked first)
- **Location**: `{project_root}/.ai/scripts/{category}/`
- **Example**: `.ai/scripts/scraping/custom_google_maps.py`
- **Use case**: Scripts specific to this project, not shared

### 2. User Space (`~/.script-kiwi/scripts/`)
- **Purpose**: Personal script library, downloaded from registry
- **Priority**: Second (checked if not in project)
- **Location**: `~/.script-kiwi/scripts/{category}/`
- **Example**: `~/.script-kiwi/scripts/scraping/google_maps_leads.py`
- **Use case**: Scripts you've downloaded from registry, available across all projects

### 3. Registry (Supabase `scripts` table)
- **Purpose**: Production-ready, tested scripts (shareable)
- **Priority**: Last (checked if not in project or user space)
- **Location**: Remote Supabase database
- **Example**: Script "google_maps_leads" version "1.2.0
- **Use case**: Official scripts, community scripts, versioned releases

## Tool Behaviors

### `search` Tool
- Searches **all three tiers** (Project + User + Registry)
- Returns matches with source indicator: `{"source": "project" | "user" | "registry"}`
- Registry search uses full-text search (tsvector)
- Local search uses file system glob

### `load` Tool
- **Resolution order**: Project → User → Registry
- **Behavior**:
  1. Check `.ai/scripts/` first → if found, return local version
  2. Check `~/.script-kiwi/scripts/` second → if found, return cached version
  3. Check Supabase registry last → if found:
     - Return script spec + code
     - **Optionally download to user space** (for faster future access)
- **Parameters**:
  - `script_name`: Name of script to load
  - `download_to_user`: Boolean, if true downloads from registry to `~/.script-kiwi/scripts/`
  - `version`: Optional specific version (default: latest)

**Example:**
```python
# Load script from registry, download to user space
load({
  "script_name": "google_maps_leads",
  "download_to_user": true  # Caches in ~/.script-kiwi/scripts/scraping/
})

# Load script from project space (if exists)
load({
  "script_name": "custom_scraper",
  # Will find in .ai/scripts/ first, never checks registry
})
```

### `run` Tool
- **Resolution order**: Project → User → Registry (same as `load`)
- **Behavior**:
  1. Resolve script location using same priority
  2. If in Project/User: Import Python module directly and execute
  3. If only in Registry: **Return error suggesting to load first** (do not auto-download)
  4. Execute Python module (deterministic, no LLM code generation)
  5. Log to `executions` table in Supabase
- **No caching**: Each run resolves fresh (respects lockfiles)
- **Error handling**: If script only exists in registry, suggests using `load` tool first

**Example:**
```python
# Run script (automatically resolves location)
run({
  "script_name": "google_maps_leads",
  "params": {
    "search_term": "dentist",
    "location": "Texas",
    "max_results": 500
  }
})
# Resolution: .ai/scripts/ → ~/.script-kiwi/scripts/ → (if not found) error with suggestion to load
```

**Error Response:**
```python
# If script only in registry:
{
  "error": "script_not_found_locally",
  "message": "Script 'google_maps_leads' not found in project or user space",
  "suggestion": "Use load tool first: load({'script_name': 'google_maps_leads', 'download_to_user': true})",
  "available_in": "registry"
}
```

### `publish` Tool
- **Source**: Can publish from Project or User space
- **Destination**: Supabase `scripts` table
- **Behavior**:
  1. Read script file from `.ai/scripts/` or `~/.script-kiwi/scripts/`
  2. Validate semver version
  3. Compute content hash
  4. Upload to Supabase `script_versions` table
  5. Update `scripts` table (mark as latest version)
- **Parameters**:
  - `script_name`: Name of script to publish
  - `version`: Semver version (e.g., "1.0.0")
  - `source`: "project" or "user" (where to read script from)
  - `changelog`: Optional changelog text

**Example:**
```python
# Publish project-specific script to registry
publish({
  "script_name": "custom_scraper",
  "version": "1.0.0",
  "source": "project",  # Read from .ai/scripts/
  "changelog": "Initial release"
})
# Now available in registry for others to download
```

### `help` Tool
- Provides guidance on script usage
- Can reference scripts from any tier
- Shows examples of search/load/run/publish workflows

## Complete Workflow Examples

### Workflow 1: Create & Publish New Script
```python
# 1. Create script in project space
# File: .ai/scripts/scraping/my_custom_scraper.py
# ... write script code ...

# 2. Publish to registry
publish({
  "script_name": "my_custom_scraper",
  "version": "1.0.0",
  "source": "project",
  "changelog": "Custom scraper for specific use case"
})

# 3. Script now in registry, can be loaded by others
```

### Workflow 2: Download & Use Registry Script
```python
# 1. Search for script
search({"query": "google maps leads"})
# Returns: [{"name": "google_maps_leads", "source": "registry", ...}]

# 2. Load script (download to user space)
load({
  "script_name": "google_maps_leads",
  "download_to_user": true
})
# Downloads to: ~/.script-kiwi/scripts/scraping/google_maps_leads.py

# 3. Run script (uses cached user space version)
run({
  "script_name": "google_maps_leads",
  "params": {"search_term": "dentist", "location": "Texas"}
})
# Resolution: .ai/scripts/ (not found) → ~/.script-kiwi/scripts/ (found!) → execute

# If step 2 was skipped and script only in registry:
# run() would return error suggesting to use load() first
```

### Workflow 3: Override Registry Script with Project Version
```python
# 1. Copy registry script to project space
# File: .ai/scripts/scraping/google_maps_leads.py
# ... modify for project-specific needs ...

# 2. Run script (project version takes precedence)
run({
  "script_name": "google_maps_leads",
  "params": {"search_term": "dentist", "location": "Texas"}
})
# Resolution: .ai/scripts/ (found! uses project version) → never checks user/registry
```

## Lockfile Integration

Lockfiles pin script versions per project:
- **Location**: `.ai/scripts.lock.json` (project) or `~/.script-kiwi/scripts.lock.json` (user)
- **Format**: 
  ```json
  {
    "version": "1.0.0",
    "project_hash": "abc123...",
    "scripts": {
      "google_maps_leads": "1.2.0",
      "email_waterfall": "2.0.0"
    },
    "directives": {
      "scrape_leads": "2.1.0"
    },
    "created_at": "2025-12-05T00:00:00Z",
    "updated_at": "2025-12-05T00:00:00Z"
  }
  ```
- **Project Hash**: SHA256 of `.ai/directives/custom/` directory contents (groups lockfiles per project)
- **Behavior**: `load` and `run` respect lockfile versions (always use pinned version)
  - If script version in lockfile, load that specific version from registry
  - If newer version exists but lockfile has old version, load pinned version (with optional warning)
  - User must update lockfile to get new version
- See Implementation-Clarifications.md for complete format specification
- See Implementation-Edge-Cases-and-Verification.md for detailed behavior examples

## Implementation Details

### Script Resolution Logic
```python
def resolve_script(script_name: str, category: str = None) -> Path | None:
    """Resolve script location in priority order."""
    # 1. Check project space
    project_path = Path(".ai/scripts") / category / f"{script_name}.py"
    if project_path.exists():
        return project_path
    
    # 2. Check user space
    user_path = Path.home() / ".script-kiwi/scripts" / category / f"{script_name}.py"
    if user_path.exists():
        return user_path
    
    # 3. Check registry (Supabase)
    # Query scripts table, return None if not found
    return None
```

### Script Execution Logic
```python
import importlib.util
import sys
from pathlib import Path

async def run_script(script_name: str, params: dict):
    """Execute script from resolved location."""
    # 1. Resolve location
    script_path = resolve_script(script_name)
    
    # 2. If not found locally, check registry and suggest loading
    if script_path is None:
        registry_script = check_registry(script_name)
        if registry_script:
            raise ScriptNotFoundError(
                code="SCRIPT_NOT_FOUND",
                message=f"Script '{script_name}' not found locally",
                details={
                    "script_name": script_name,
                    "suggestion": f"Use 'load' tool first: load({{'script_name': '{script_name}', 'download_to_user': true}})",
                    "available_in": "registry"
                }
            )
        else:
            raise ScriptNotFoundError(
                code="SCRIPT_NOT_FOUND",
                message=f"Script '{script_name}' not found in any location"
            )
    
    # 3. Dynamic import and execute Python module
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[script_path.stem] = module
    spec.loader.exec_module(module)
    
    # 4. Call execute() or main() function
    if hasattr(module, 'execute'):
    result = await module.execute(params)
    elif hasattr(module, 'main'):
        result = await module.main(params)  # Adapt argparse-style
    else:
        raise ValueError(f"Script {script_path} has no execute() or main() function")
    
    # 5. Calculate cost (if script declares cost_per_unit)
    cost_usd = calculate_cost(script_name, params, result)
    
    # 6. Log execution (dual logging: user space + Supabase)
    log_execution(
        script_name=script_name,
        status=result.get("status", "success"),
        duration_sec=duration_sec,
        inputs=params,
        outputs=result.get("data"),
        cost_usd=cost_usd,
        rows_processed=result.get("metadata", {}).get("rows_processed")
    )
    
    return result
```

## Alignment with Context Kiwi

This mechanism **exactly mirrors** Context Kiwi's directive resolution:
- Same 3-tier system (Project → User → Registry)
- Same priority order
- Same `get`/`load` behavior (download from registry to user space)
- Same `publish` behavior (upload local to registry)
- Same lockfile support

**Key difference**: Scripts are Python modules (executed directly), directives are XML (loaded for LLM to follow).
