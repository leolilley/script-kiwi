# Dependency Metadata Corruption Issue

## Issue Summary

The `extract_youtube_transcript` script (and potentially other scripts) have corrupted dependency metadata in the Supabase registry. Dependencies are being stored/retrieved as JSON-encoded strings instead of proper Python dict objects.

## Symptoms

When running the script:
```bash
script-kiwi_run(extract_youtube_transcript, dry_run=true)
```

Error received:
```
"error": "Script has corrupted dependency metadata in registry: Dependency 0 must be a dict, got str: {\"name\":\"youtube-transcript-api\",\"version\":\">=0.6.0\"}. Script metadata is corrupted - republish the script."
```

## Root Cause Analysis

### Expected Format
Dependencies should be stored as a JSONB array of objects:
```json
[
  {"name": "youtube-transcript-api", "version": ">=0.6.0"},
  {"name": "requests", "version": ">=2.31.0"}
]
```

### Actual Format in Database
Dependencies are being stored as an array of JSON strings:
```json
[
  "{\"name\":\"youtube-transcript-api\",\"version\":\">=0.6.0\"}",
  "{\"name\":\"requests\",\"version\":\">=2.31.0\"}"
]
```

This is double-encoding: the dict is serialized to JSON, then that JSON string is stored as an array element.

## Investigation Path

### 1. Checked Metadata Extraction (`script_metadata.py`)
- ✅ CORRECT: Extracts dependencies as `List[Dict[str, str]]`
- ✅ Returns: `[{"name": "youtube_transcript_api", "version": None}, ...]`
- ⚠️ ISSUE FOUND: Was incorrectly detecting `concurrent` as external dependency (it's stdlib)

### 2. Checked Publish Flow (`publish.py`)
- ❌ BUG FOUND: **Publish tool does NOT extract metadata from script files**
- It only uses metadata if explicitly provided in `params.get("metadata")`
- When sync_scripts directive publishes, it doesn't pass metadata parameter
- This means dependencies are never sent to the registry during publish

### 3. Checked Registry Client (`script_registry.py`)
- The `publish_script()` method correctly handles JSONB fields
- Supabase Python client should automatically serialize list/dict to JSONB
- ❌ BUG FOUND: `get_script()` method doesn't handle case where Supabase returns JSONB as strings

### 4. Checked Run Tool (`run.py`)
- Had extensive defensive code trying to parse JSON-encoded dependencies
- This was treating symptoms, not the root cause
- Multiple layers of "normalization" that hid the real issue

## Attempted Fixes

### Fix 1: Added Defensive Parsing (WRONG APPROACH)
- Added `_normalize_dependencies()` method to parse JSON strings
- Added special handling for corrupted metadata
- **PROBLEM**: This treats symptoms, doesn't fix root cause

### Fix 2: Added Metadata Extraction to Publish
```python
# If no metadata provided, extract from script file
if not metadata:
    from ..utils.script_metadata import extract_script_metadata
    extracted = extract_script_metadata(script_path)
    metadata = {
        "description": extracted.get("description"),
        "dependencies": extracted.get("dependencies", []),
        ...
    }
```
- **PROBLEM**: Still didn't fix existing corrupted data

### Fix 3: Added JSONB Parsing in get_script()
```python
# Parse JSONB fields if they came back as JSON strings
for field in ["dependencies", "tech_stack", ...]:
    if isinstance(value, str):
        script[field] = json.loads(value)
    if isinstance(value, list):
        # Parse each item if it's a JSON string
        parsed_list = []
        for item in value:
            if isinstance(item, str) and item.startswith('{'):
                parsed_list.append(json.loads(item))
```
- **PROBLEM**: This should work but didn't - corruption persists

### Fix 4: Added Validation Instead of Normalization
```python
def _validate_dependencies(self, dependencies: List[Any]) -> List[Dict[str, str]]:
    """Validate dependencies are in correct format, raise clear error if corrupted."""
    # Check for JSON-encoded corruption
    if name.startswith('{') or name.startswith('['):
        raise ValueError(
            f"Dependency {i} 'name' field appears to be JSON-encoded: {name[:100]}. "
            "Script metadata is corrupted - republish the script with correct metadata."
        )
```
- **RESULT**: Now fails fast with clear error message instead of silently handling corruption

## Current State

### Code Changes Made
1. ✅ `script_metadata.py`: Added stdlib modules (`concurrent`, `threading`, etc.) to skip list
2. ✅ `publish.py`: Auto-extracts metadata from script file if not provided
3. ✅ `run.py`: Replaced `_normalize_dependencies()` with `_validate_dependencies()` - fails fast on corruption
4. ✅ `script_registry.py`: Added JSONB string parsing in `get_script()` 
5. ✅ `script_registry.py`: Added validation in `publish_script()` to prevent storing corrupted data

### What Still Doesn't Work
- **Old corrupted data persists in database**
- Publishing new versions doesn't fix the corruption in the `scripts` table
- The UPDATE query in `publish_script()` should work but corruption persists

## Proper Solution

### Option 1: Manual Database Fix (RECOMMENDED)
Run SQL directly against Supabase to fix corrupted records:

```sql
-- Check current state
SELECT id, name, dependencies 
FROM scripts 
WHERE name = 'extract_youtube_transcript';

-- Fix corrupted dependencies
UPDATE scripts 
SET dependencies = '[
  {"name": "youtube-transcript-api", "version": ">=0.6.0"},
  {"name": "requests", "version": ">=2.31.0"}
]'::jsonb
WHERE name = 'extract_youtube_transcript';
```

### Option 2: Migration Script
Create `migrations/002_fix_dependency_encoding.py`:
- Query all scripts with dependencies
- For each, parse the corrupted JSON strings
- Update with properly formatted JSONB

### Option 3: Delete and Republish
```python
# Delete script entirely from registry
script-kiwi_remove(extract_youtube_transcript, from_registry=true)

# Republish with auto-extracted metadata (fix now in place)
script-kiwi_publish(extract_youtube_transcript, version="2.1.0")
```

## Prevention

### Changes to Prevent Future Corruption

1. **Always extract metadata when publishing** (✅ DONE)
   - `publish.py` now auto-extracts if not provided

2. **Validate before storing** (✅ DONE)
   - `publish_script()` validates format before UPDATE/INSERT

3. **Parse JSONB strings on retrieval** (✅ DONE)
   - `get_script()` handles case where Supabase returns strings

4. **Fail fast with clear errors** (✅ DONE)
   - `_validate_dependencies()` raises descriptive errors
   - No silent corruption handling

## Why This Happened

1. **Sync scripts directive** was publishing without metadata parameter
2. **Publish tool** wasn't extracting metadata from files
3. **Registry** was only updating if metadata provided
4. **Old data** had corrupted format from previous sync
5. **Supabase client** may have serialization quirks with nested JSONB

## Testing After Fix

```bash
# 1. Fix existing corrupted data (manual SQL or delete/republish)

# 2. Republish script with new code
script-kiwi_publish(extract_youtube_transcript, version="2.1.0")

# 3. Verify dependencies are correct
script-kiwi_load(extract_youtube_transcript, sections=["dependencies"])

# 4. Test execution
script-kiwi_run(extract_youtube_transcript, parameters={...}, dry_run=true)
```

## Resolution - FIXED ✅

### Database Migration Applied
Successfully ran `migrations/002_fix_dependency_encoding.sql`:
1. ✅ Converted `dependencies`, `tech_stack`, `required_env_vars`, `tags` from `text[]` to `jsonb`
2. ✅ Parsed double-encoded JSON strings back into proper objects
3. ✅ Script validation now passes

### Files Modified
- `script_kiwi/utils/script_metadata.py`: Fixed stdlib detection (added `concurrent`, `threading`, etc.)
- `script_kiwi/tools/publish.py`: Auto-extract metadata from script files if not provided
- `script_kiwi/tools/run.py`: Replaced normalization with strict validation (fails fast on corruption)
- `script_kiwi/api/script_registry.py`: Added JSONB string parsing in `get_script()`, validation in `publish_script()`
- `migrations/002_fix_dependency_encoding.sql`: Schema fix and data cleanup migration

