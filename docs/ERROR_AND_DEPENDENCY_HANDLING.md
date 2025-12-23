# Error and Dependency Handling in Script Kiwi

## Overview

This document explains how Script Kiwi handles:
1. **Dependencies** - Python package dependencies
2. **Errors** - Error handling and response formats
3. **Messaging** - How information is passed back to the LLM/user

---

## 1. Dependencies

### Declaration

Dependencies are declared in the `scripts` table:

```sql
dependencies jsonb DEFAULT '[]'  -- [{"name": "apify-client", "version": ">=0.1.0"}]
required_env_vars text[] DEFAULT '{}'  -- ['APIFY_API_TOKEN']
required_scripts uuid[] DEFAULT '{}'  -- Other scripts this depends on
```

### Loading Dependencies Info

The `load` tool returns dependency information:

```json
{
  "script": {
    "name": "scrape_google_maps",
    "dependencies": {
      "packages": [
        {"name": "apify-client", "version": ">=1.7.0"},
        {"name": "beautifulsoup4", "version": ">=4.12.0"}
      ],
      "env_vars": ["APIFY_API_TOKEN"],
      "scripts": []
    }
  }
}
```

### Declaring Dependencies in Scripts

When creating a script, declare pip dependencies in two places:

1. **In the script docstring** (for documentation):
```python
"""
Script description here.

Dependencies:
  - youtube-transcript-api>=0.6.0  # pip install youtube-transcript-api>=0.6.0
  - requests>=2.31.0
"""
```

2. **When publishing** (for registry storage):
```python
publish(
    script_name="my_script",
    version="1.0.0",
    metadata={
        "dependencies": [
            {"name": "youtube-transcript-api", "version": ">=0.6.0"},
            {"name": "requests", "version": ">=2.31.0"}
        ]
    }
)
```

**Format**: `[{"name": "package-name", "version": ">=1.0.0"}]`
- `version` is optional (defaults to latest if omitted)
- Use standard version specifiers: `>=`, `==`, `~=`, etc.

### Automatic Dependency Installation

**✅ Dependencies are now automatically installed.**

- The system checks for missing dependencies before execution.
- If dependencies are missing, it attempts to install them using `pip install`.
- It uses a library mapping mechanism (`MODULE_TO_PACKAGE` and `PACKAGE_TO_MODULE`) to handle cases where the import name differs from the package name (e.g., `import git` requires `pip install GitPython`).
- This mapping is defined in `script_kiwi/utils/script_metadata.py`.

---

## 2. Error Handling

### Error Response Format

All errors are returned as JSON strings with structured formats:

#### Tool-Level Errors (Script Not Found, etc.)

```json
{
  "error": {
    "code": "SCRIPT_NOT_FOUND",
    "message": "Script 'example_script' not found in any location",
    "details": {
      "script_name": "example_script",
      "suggestion": "Use search({'query': '...'}) to find available scripts"
    }
  }
}
```

#### Validation Errors (Pre-flight Checks)

```json
{
  "status": "validation_failed",
  "errors": [
    "Missing credentials: ['APIFY_API_TOKEN']",
    "'count' must be >= 1, got 0"
  ],
  "warnings": [
    "Estimated cost $15.00 exceeds warning threshold $10.00"
  ]
}
```

#### Execution Errors (Runtime Failures)

```json
{
  "status": "error",
  "execution_id": "exec-123",
  "error": "ModuleNotFoundError: No module named 'apify_client'",
  "traceback": "Traceback (most recent call last):\n  ...",
  "troubleshooting": [
    "Check error message above",
    "Verify all required environment variables are set",
    "Use help() tool for guidance"
  ]
}
```

### Error Codes

Common error codes:
- `SCRIPT_NOT_FOUND` - Script doesn't exist in any tier
- `SCRIPT_NOT_FOUND_LOCALLY` - Script only in registry, needs to be loaded
- `VALIDATION_FAILED` - Pre-flight checks failed
- `EXECUTION_ERROR` - Script execution failed (runtime error)

### Error Flow

1. **Pre-flight Validation** (`run_preflight`)
   - Checks credentials (env vars)
   - Validates inputs
   - Estimates cost/time
   - Returns `validation_failed` if blockers exist

2. **Execution**
   - Try/except around script execution
   - Catches all exceptions
   - Returns structured error with traceback

3. **Logging**
   - All errors logged to user space and Supabase
   - Includes error message, traceback, duration

---

## 3. Messaging and Response Format

### Success Response

```json
{
  "status": "success",
  "execution_id": "exec-123",
  "result": {
    "leads": [...],
    "count": 500
  },
  "metadata": {
    "duration_sec": 12.5,
    "cost_usd": 0.05,
    "rows_processed": 500
  }
}
```

### Dry Run Response

```json
{
  "status": "validation_passed",
  "message": "Script is ready to execute",
  "estimated_cost": 0.05,
  "estimated_time": 12
}
```

### Load Response

```json
{
  "script": {
    "name": "scrape_google_maps",
    "category": "scraping",
    "description": "Scrape leads from Google Maps",
    "version": "1.0.0",
    "module_path": "execution.scraping.scrape_google_maps"
  },
  "dependencies": {
    "packages": [...],
    "env_vars": [...],
    "scripts": [...]
  },
  "inputs": {...},
  "cost": {...},
  "next_steps": [
    "Review script metadata and dependencies",
    "Use run({'script_name': '...', 'parameters': {...}}) to run",
    "Use dry_run=true to validate without executing"
  ]
}
```

### Response Format Standards

- **All responses are JSON strings** (not Python dicts)
- **Consistent structure**: `status`, `error` (if failed), `result` (if success)
- **Metadata included**: duration, cost, execution_id
- **Helpful context**: suggestions, troubleshooting hints, next_steps

---

## 4. Pre-flight Validation

The `run_preflight` function checks:

1. **Credentials** (`required_env_vars`)
   - Checks if environment variables exist
   - Returns blockers if missing

2. **Input Validation** (`validation_rules`)
   - Type checking (string, integer, float, boolean)
   - Min/max values
   - Pattern matching (regex)
   - Enum values
   - Required fields

3. **Cost Estimation** (`cost_formula`)
   - Calculates estimated cost
   - Warns if exceeds `cost_warn_threshold`
   - Blocks if exceeds `cost_block_threshold`

4. **Time Estimation** (`time_formula`)
   - Calculates estimated duration
   - Returns human-readable format

### Pre-flight Response

```json
{
  "pass": false,
  "checks": {
    "credentials": {"status": "fail", "missing": ["APIFY_API_TOKEN"]},
    "inputs": {"status": "pass"},
    "cost": {"estimated_cost_usd": 15.0}
  },
  "warnings": ["Estimated cost $15.00 exceeds warning threshold $10.00"],
  "blockers": ["Missing credentials: ['APIFY_API_TOKEN']"]
}
```

---

## 5. Current Gaps and Future Improvements

### Dependencies

**Current:** Declared but not installed/validated

**Potential Improvements:**
- Pre-execution dependency check
- Automatic installation (with user confirmation)
- Isolated virtual environments per script
- Dependency version conflict detection

### Error Messages

**Current:** Good structure, includes traceback and troubleshooting

**Potential Improvements:**
- More specific error codes (e.g., `DEPENDENCY_MISSING`, `TIMEOUT`, `RATE_LIMIT`)
- Error recovery suggestions (e.g., "Install missing package: pip install apify-client")
- Partial result return on partial failures

### Messaging

**Current:** JSON responses with helpful context

**Potential Improvements:**
- Progress updates for long-running scripts
- Streaming results for large outputs
- Structured logging levels (info, warning, error)

---

## 6. Example Error Scenarios

### Missing Dependency

```python
# Script tries to import missing package
from apify_client import ApifyClient  # ModuleNotFoundError

# Response:
{
  "status": "error",
  "error": "ModuleNotFoundError: No module named 'apify_client'",
  "traceback": "...",
  "troubleshooting": [
    "Check error message above",
    "Verify all required environment variables are set",
    "Use help() tool for guidance"
  ]
}
```

### Missing Credential

```python
# Pre-flight check fails
{
  "status": "validation_failed",
  "errors": ["Missing credentials: ['APIFY_API_TOKEN']"],
  "warnings": []
}
```

### Invalid Input

```python
# Input validation fails
{
  "status": "validation_failed",
  "errors": ["'count' must be >= 1, got 0"],
  "warnings": []
}
```

---

## Summary

- **Dependencies**: Declared in DB, returned by `load`, but NOT automatically installed
- **Errors**: Structured JSON with codes, messages, traceback, and troubleshooting
- **Messaging**: Consistent JSON format with status, result/error, metadata, and helpful context
- **Pre-flight**: Validates credentials, inputs, cost, and time before execution

