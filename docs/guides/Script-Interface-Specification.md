# Script Interface Specification

## Overview

All scripts executed by Script Kiwi must implement a standard interface for consistency and reliability.

## Required Function Signature

**Standard Interface:**
```python
def execute(params: dict) -> dict:
    """
    Execute the script with provided parameters.
    
    Args:
        params: Dictionary of input parameters (validated by MCP)
        
    Returns:
        Dictionary with execution results:
        {
            "status": "success" | "error",
            "data": {...},  # Script-specific output
            "metadata": {
                "duration_sec": float,
                "cost_usd": float,
                "rows_processed": int,  # Optional
                "items_processed": int  # Optional
            },
            "error": str  # Only if status == "error"
        }
    """
    pass
```

## Alternative: Main Function (Legacy Support)

For scripts that use `argparse` or have a `main()` function:

```python
def main(params: dict) -> dict:
    """
    Main entry point (alternative to execute).
    
    Script Kiwi will call main() if execute() is not found.
    """
    pass
```

**Note:** Script Kiwi automatically adapts `main()` to the `execute()` interface.

## Parameter Validation

- Scripts receive **pre-validated** parameters from Script Kiwi MCP
- Parameters match the script's declared `inputs` schema in the registry
- No need for scripts to re-validate (but defensive checks are fine)

## Return Value Requirements

### Success Response

```python
{
    "status": "success",
    "data": {
        # Script-specific output
        "leads": [...],
        "enriched_count": 450,
        # ... other fields
    },
    "metadata": {
        "duration_sec": 12.5,
        "cost_usd": 0.05,
        "rows_processed": 500,  # Optional
        "items_processed": 450   # Optional
    }
}
```

### Error Response

```python
{
    "status": "error",
    "error": "Descriptive error message",
    "data": None,  # or partial results if available
    "metadata": {
        "duration_sec": 2.1,
        "cost_usd": 0.0
    }
}
```

## Execution Context

### Virtual Environment

- Scripts execute in the **same Python process** as the MCP server
- Scripts use the **MCP server's virtual environment** (`.venv/` in Script Kiwi project)
- All dependencies must be installed in Script Kiwi's `.venv/`
- Scripts can import from `script_kiwi.utils.*` (vendored utilities)

### Import Paths

```python
# Scripts can import vendored utilities
from script_kiwi.utils.api import api_call
from script_kiwi.utils.preflight import run_preflight
from script_kiwi.utils.analytics import log_execution

# Scripts can use relative imports within their category
from .helpers import validate_input
```

### Environment Variables

- Scripts access environment variables via `os.environ`
- Required env vars are declared in script registry
- MCP server validates env vars before execution

## Example Script

```python
#!/usr/bin/env python3
"""
Example script showing standard interface.
"""

import os
from typing import Dict, Any
from script_kiwi.utils.api import api_call
from script_kiwi.utils.analytics import log_execution

def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrape leads from Google Maps.
    
    Args:
        params: {
            "search_term": str,
            "location": str,
            "max_results": int
        }
        
    Returns:
        {
            "status": "success",
            "data": {
                "leads": [...],
                "count": 100
            },
            "metadata": {
                "duration_sec": 12.5,
                "cost_usd": 0.05,
                "rows_processed": 100
            }
        }
    """
    import time
    start_time = time.time()
    
    try:
        # Validate inputs (defensive, but MCP already validated)
        search_term = params.get("search_term")
        location = params.get("location")
        max_results = params.get("max_results", 100)
        
        if not search_term or not location:
            return {
                "status": "error",
                "error": "search_term and location are required",
                "metadata": {
                    "duration_sec": time.time() - start_time,
                    "cost_usd": 0.0
                }
            }
        
        # Execute script logic
        leads = []
        # ... scraping logic ...
        
        # Calculate cost
        cost_usd = max_results * 0.0001  # Example: $0.0001 per lead
        
        duration = time.time() - start_time
        
        return {
            "status": "success",
            "data": {
                "leads": leads,
                "count": len(leads)
            },
            "metadata": {
                "duration_sec": duration,
                "cost_usd": cost_usd,
                "rows_processed": len(leads)
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "metadata": {
                "duration_sec": time.time() - start_time,
                "cost_usd": 0.0
            }
        }
```

## Migration from argparse

If you have an existing script with `argparse`:

```python
# Old style
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--search-term', required=True)
    parser.add_argument('--location', required=True)
    args = parser.parse_args()
    # ... do work ...

# New style (for Script Kiwi)
def execute(params: dict) -> dict:
    search_term = params.get("search_term")
    location = params.get("location")
    # ... do work ...
    return {"status": "success", "data": {...}, "metadata": {...}}

# Keep main() for backward compatibility
def main():
    # Adapt argparse to execute() interface
    parser = argparse.ArgumentParser()
    parser.add_argument('--search-term', required=True)
    parser.add_argument('--location', required=True)
    args = parser.parse_args()
    
    params = {
        "search_term": args.search_term,
        "location": args.location
    }
    
    result = execute(params)
    
    # Print result (for CLI usage)
    if result["status"] == "success":
        print(json.dumps(result["data"], indent=2))
    else:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
```

## Best Practices

1. **Always return metadata**: Include `duration_sec` and `cost_usd` in metadata
2. **Handle errors gracefully**: Return error status, don't raise exceptions
3. **Use vendored utilities**: Import from `script_kiwi.utils.*` instead of reimplementing
4. **Log execution**: Use `log_execution()` from `script_kiwi.utils.analytics` (optional, MCP automatically logs to user space and Supabase)
5. **Validate defensively**: Even though MCP validates, add defensive checks for critical paths
6. **Return structured data**: Use consistent data structures in `data` field

## Testing

Scripts should be testable independently:

```python
# test_script.py
def test_execute():
    params = {
        "search_term": "dentist",
        "location": "Texas",
        "max_results": 10
    }
    result = execute(params)
    assert result["status"] == "success"
    assert "data" in result
    assert "metadata" in result
    assert "duration_sec" in result["metadata"]
```

---

**Summary:** All scripts must implement `execute(params: dict) -> dict` (or `main(params: dict) -> dict`). Scripts run in the MCP server's virtual environment, receive pre-validated parameters, and must return structured results with status, data, and metadata.

