# Handling Long-Running Scripts, Large Responses, and Streaming Logs

## Overview

Script Kiwi now includes comprehensive support for:
1. **Large response handling** - Automatic truncation and file output
2. **Configurable timeouts** - Support for scripts that run longer than 5 minutes
3. **Streaming logs** - Real-time progress updates (foundation laid)
4. **File-based output** - Automatic file writing for very large results

## Large Response Handling

### Automatic Truncation

Script Kiwi automatically truncates large responses to prevent MCP message size limits:

- **Arrays**: Limited to 1,000 items by default (configurable via `MAX_ARRAY_ITEMS`)
- **Strings**: Limited to 10,000 characters by default (configurable via `MAX_STRING_LENGTH`)
- **Logs**: Limited to 500 lines by default (configurable via `MAX_LOG_LINES`)

When truncation occurs, the response includes a `truncation_warnings` field:

```json
{
  "status": "success",
  "result": {
    "businesses": [...1000 items...]
  },
  "truncation_warnings": {
    "businesses": {
      "type": "array",
      "original_count": 5000,
      "truncated_count": 1000,
      "message": "Array truncated from 5000 to 1000 items. Use --output-file to get full results."
    }
  }
}
```

### File-Based Output

**By default, Script Kiwi automatically saves all script outputs to `~/.script-kiwi/outputs/{script_name}/`** (or `$SCRIPT_KIWI_HOME/outputs/{script_name}/` if the env var is set). This ensures you always have a record of script executions.

**Default behavior** (always saves):
```python
run({
    "script_name": "scrape_google_maps",
    "parameters": {
        "search_term": "restaurants",
        "location": "New York",
        "count": 10000
    }
})
# Automatically writes to ~/.script-kiwi/outputs/scrape_google_maps/1234567890_results.json
```

**Custom output path** (overrides default):
```python
run({
    "script_name": "scrape_google_maps",
    "parameters": {
        "search_term": "restaurants",
        "location": "New York",
        "count": 10000,
        "_output_file": "custom/path/results.json"  # Custom file path (overrides default)
    }
})
```

When results are written to a file, the response includes:
- `_output_file`: Path to the file
- `_file_size_bytes`: Size of the file
- `_summary`: Summary of the data structure
- `_message`: Instructions for accessing full results

## Configurable Timeouts

### Default Behavior

- **Default timeout**: 5 minutes (300 seconds)
- **Maximum timeout**: 30 minutes (1800 seconds)

### Custom Timeout

```python
run({
    "script_name": "scrape_apify",
    "parameters": {
        "industry": "dentists",
        "location": "United States",
        "count": 1000,
        "_timeout": 600  # 10 minutes
    }
})
```

**Note**: The `_timeout` parameter is removed from script parameters before execution, so scripts don't see it.

## Streaming Logs (Foundation)

The infrastructure for streaming logs is in place. Currently, logs are captured after script completion. Future enhancements will support:

- Real-time log streaming via MCP progress updates
- Progress callbacks for long-running operations
- Heartbeat messages to prevent connection timeouts

### Current Log Handling

Logs are captured from `stderr` and included in the response:

```json
{
  "status": "success",
  "result": {...},
  "logs": [
    "2025-12-08 - INFO - Starting scrape...",
    "2025-12-08 - INFO - Apify actor started: run_abc123",
    "2025-12-08 - INFO - Waiting for completion...",
    "2025-12-08 - INFO - Scrape completed: 500 businesses found"
  ]
}
```

If logs exceed 500 lines, they're truncated with a warning:

```json
{
  "logs": [...500 lines...],
  "log_truncated": {
    "original_lines": 1200,
    "shown_lines": 500,
    "message": "Logs truncated from 1200 to 500 lines"
  }
}
```

## Best Practices

### For Script Authors

1. **Log to stderr**: Use `print(..., file=sys.stderr)` or Python's `logging` module
2. **Output JSON to stdout**: Always output structured JSON for MCP parsing
3. **Include progress updates**: Log progress for long-running operations
4. **Handle large datasets**: Consider pagination or streaming for very large results

### For Script Users

1. **Outputs are saved by default**: All script results are automatically saved to `~/.script-kiwi/outputs/{script_name}/` (or `$SCRIPT_KIWI_HOME/outputs/{script_name}/`) - no action needed
2. **Disable saving if needed**: Set `_save_output=False` to skip saving (results still returned in response)
3. **Custom output paths**: Use `_output_file` parameter to specify a different path
4. **Increase timeout for long operations**: Use `_timeout` parameter for scripts that take >5 minutes
5. **Check truncation warnings**: Review `truncation_warnings` to see if data was truncated
4. **Monitor logs**: Check the `logs` field for progress and debugging information

## Configuration Constants

These can be adjusted in `script_kiwi/tools/run.py`:

```python
MAX_RESPONSE_SIZE_BYTES = 1_000_000  # 1MB max response size
MAX_ARRAY_ITEMS = 1000  # Max items in arrays before truncation
MAX_LOG_LINES = 500  # Max log lines to include
MAX_STRING_LENGTH = 10_000  # Max string length before truncation
```

## Example: Large Dataset Scraping

```python
# Scrape 10,000 businesses - results will be written to file
result = run({
    "script_name": "scrape_google_maps",
    "parameters": {
        "search_term": "restaurants",
        "location": "New York",
        "count": 10000,
        "_timeout": 900,  # 15 minutes
        "_output_file": "nyc_restaurants.json"
    }
})

# Response includes file location and summary
print(result["result"]["_output_file"])  # ~/.script-kiwi/outputs/scrape_google_maps/1234567890_results.json (or custom path if specified)
print(result["result"]["_file_size_bytes"])  # 2500000 (2.5MB)
print(result["result"]["_summary"])  # Summary of data structure
```

## Dependency Management

Script Kiwi handles pip dependencies **automatically and transparently**:

### How It Works

1. Before execution, dependencies are extracted from script metadata
2. Each dependency is checked for availability (import test)
3. If missing dependencies are found, they are **automatically installed** via pip
4. Script execution proceeds after all dependencies are installed

**No configuration needed** - dependency management is fully automatic. The MCP handles all pip package installation transparently.

### Example

```python
# Dependencies are automatically installed - no parameters needed
result = run({
    "script_name": "scrape_youtube",
    "parameters": {"video_url": "..."}
})

# If dependencies were missing, they're installed automatically before execution
# You'll see log messages like:
# "Installing 2 missing dependencies..."
# "Successfully installed 2 dependencies"
```

### Error Handling

If dependency installation fails, you'll get a clear error:

```json
{
    "status": "error",
    "error": "Failed to install some dependencies",
    "error_type": "dependency_error",
    "details": {
        "installed": [{"name": "requests"}],
        "failed": [{"name": "youtube-transcript-api", "error": "..."}]
    }
}
```

### Best Practices

1. **Declare dependencies in scripts**: Use docstrings or imports that `script_metadata.py` can extract
2. **Use specific versions**: `{"name": "package", "version": ">=1.0.0"}` in metadata
3. **Test locally first**: Run `dry_run=True` to validate before execution
4. **No manual installation needed**: The MCP handles everything automatically

## Future Enhancements

1. **Real-time streaming**: MCP progress updates for live log streaming
2. **Progress callbacks**: Scripts can emit progress updates during execution
3. **Resumable execution**: Save state for long-running scripts that can be resumed
4. **Chunked responses**: Stream large results in chunks via MCP

