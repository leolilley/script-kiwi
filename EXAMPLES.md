# Script Examples

Example scripts showing the standard `execute()` interface for each category.

## Interface Pattern

All scripts must implement:

```python
def execute(params: dict) -> dict:
    """
    Execute the script.
    
    Returns:
        {
            "status": "success" | "error",
            "data": {...},  # Script-specific output
            "metadata": {
                "duration_sec": float,
                "cost_usd": float,
                "rows_processed": int  # Optional
            },
            "error": str  # Only if status == "error"
        }
    """
```

## Examples

### Scraping
- `execution/scraping/example_google_maps.py` - Google Maps lead scraping

### Enrichment
- `execution/enrichment/example_email_waterfall.py` - Email enrichment with waterfall strategy

### Extraction
- `execution/extraction/example_youtube.py` - YouTube transcript extraction

### Validation
- `execution/validation/example_email_validation.py` - Email validation

## Key Patterns

1. **Pre-flight Checks**: Always run `run_preflight()` before expensive operations
2. **Cost Tracking**: Calculate and return `cost_usd` in metadata
3. **Execution Logging**: Call `log_execution()` after completion
4. **Error Handling**: Return error status, don't raise exceptions
5. **Time Tracking**: Track `duration_sec` from start to finish

## Migration from argparse

If you have existing scripts with `argparse`, see `Script-Interface-Specification.md` for migration patterns.

