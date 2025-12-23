# Script Logging and Output

## Overview

Script Kiwi handles logging and output in two ways:
1. **Script-level logging** (stderr) - Debug/info logs from the script itself
2. **Execution logging** (history.jsonl) - Script Kiwi's execution history

## Script Output Format

Scripts should return structured data that Script Kiwi can parse and present usefully.

### Function-Based Scripts (Recommended)

```python
def execute(params: dict) -> dict:
    """Main entry point."""
    # Your script logic here
    
    return {
        "status": "success",  # or "error"
        "data": {
            # Your actual results here
            "result": "some value",
            "items_processed": 100
        },
        "metadata": {
            "duration_sec": 1.5,      # Optional: script-measured duration
            "cost_usd": 0.05,          # Optional: estimated cost
            "rows_processed": 100,      # Optional: items processed
            "api_calls_made": 5        # Optional: API calls made
        }
    }
```

### Argparse-Based Scripts

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    
    # Your script logic here
    
    # Output JSON to stdout (MCP captures this)
    result = {
        "status": "success",
        "data": {"result": "..."},
        "metadata": {"duration_sec": 1.0}
    }
    print(json.dumps(result, indent=2))
```

## Logging to stderr

Scripts can log to stderr for debugging/info without interfering with JSON output:

```python
import logging
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stderr)  # Important: use stderr
handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(handler)

def execute(params):
    logger.info("Starting execution...")
    # ... do work ...
    logger.info("Execution completed")
    return {"status": "success", "data": {...}}
```

**Note**: For argparse scripts (subprocess), stderr logs are captured and included in the MCP response under `"logs"`. For function-based scripts (direct call), stderr logs go to the console but aren't captured in the response.

## MCP Response Format

The MCP tool always returns a useful, structured response:

### Success Response

```json
{
  "status": "success",
  "execution_id": "uuid-here",
  "result": {
    // Your script's data field
    "message": "...",
    "items": [...]
  },
  "metadata": {
    "duration_sec": 1.234,
    "cost_usd": 0.05,
    "rows_processed": 100,      // if provided
    "api_calls_made": 5         // if provided
  },
  "logs": [                     // Only for subprocess scripts
    "2025-12-08 - INFO - Starting...",
    "2025-12-08 - INFO - Completed"
  ]
}
```

### Error Response

```json
{
  "status": "error",
  "execution_id": "uuid-here",
  "error": "Error message here",
  "error_type": "ValueError",
  "metadata": {
    "duration_sec": 0.5,
    "cost_usd": 0
  },
  "traceback": "Full traceback...",  // Truncated if > 2000 chars
  "troubleshooting": [
    "Check error message above",
    "Verify all required environment variables are set",
    "Use help() tool for guidance",
    "Script: script_name",
    "Project: /path/to/project"
  ]
}
```

## Execution History Logging

Every script execution is automatically logged to:
- **User space**: `~/.script-kiwi/.runs/history.jsonl`
- **Supabase**: `executions` table (if configured)

Each entry includes:
- `timestamp`: ISO format timestamp
- `script`: Script name
- `status`: "success" or "error"
- `duration_sec`: Execution duration
- `project`: Project path (if `project_path` provided)
- `inputs`: Summarized input parameters
- `outputs`: Summarized output data
- `error`: Error message (if failed)
- `cost_usd`: Estimated/actual cost
- `script_version`: Version used
- `rows_processed`: Items processed
- `api_calls_made`: API calls made

## Best Practices

1. **Always return structured data**: Use the `{"status": "...", "data": {...}, "metadata": {...}}` format
2. **Log to stderr**: Use `logging` with `sys.stderr` for debug/info logs
3. **Include metadata**: Provide `duration_sec`, `cost_usd`, etc. when available
4. **Handle errors gracefully**: Return error status with useful error messages
5. **Output JSON to stdout**: For argparse scripts, always output JSON to stdout

## Example: Complete Test Script

See `.ai/scripts/validation/test_mcp_script.py` for a complete example that demonstrates:
- Function-based execution
- Structured output
- Logging to stderr
- Error handling
- Metadata reporting
