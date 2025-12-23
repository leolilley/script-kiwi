# Implementation Edge Cases and Verification

## Overview

This document addresses remaining edge cases, verification tasks, and implementation details that need clarification before starting development.

---

## 1. MCP SDK API Verification

**Status:** Needs verification before Week 2

**Question:** Does the MCP SDK v1.0.0+ API match the patterns shown in Pattern-Reuse-Notes.md?

**Verification Steps:**

1. **Install and test the SDK:**
   ```bash
   pip install "mcp>=1.0.0,<2.0.0"
   python -c "from mcp.server import Server; from mcp.server.stdio import stdio_server; print('SDK imports OK')"
   ```

2. **Verify decorator pattern:**
   ```python
   from mcp.server import Server
   from mcp import types
   
   server = Server("test-server")
   
   @server.list_tools()
   async def list_tools() -> list[types.Tool]:
       return [types.Tool(name="test", description="test")]
   
   @server.call_tool()
   async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
       return [types.TextContent(type="text", text="test")]
   ```

3. **Check actual API:**
   - Verify `Server` class exists and accepts name parameter
   - Verify `@server.list_tools()` decorator works
   - Verify `@server.call_tool()` decorator works
   - Verify `types.Tool` and `types.TextContent` exist

**Fallback Plan:**
- If API differs, adapt Pattern-Reuse-Notes.md examples to match actual SDK
- Document any differences in Implementation-Clarifications.md
- Update all code examples to match verified API

**Action:** Verify before Week 2 (Day 7 when implementing tools)

---

## 2. Directive Orchestration Examples

**Status:** Examples exist in Directive-Orchestration-Pattern.md

**Question:** Can you share a concrete example of a directive XML that calls Script Kiwi tools?

**Answer:** See `Directive-Orchestration-Pattern.md` lines 36-139 for complete example.

**Quick Reference Example:**

```xml
<?xml version="1.0"?>
<directive>
  <metadata>
    <name>scrape_and_enrich_leads</name>
    <description>Scrape leads from Google Maps and enrich with emails</description>
    <version>1.0.0</version>
  </metadata>
  
  <progressive_disclosure>
    <initial_questions>
      <question>What industry to target?</question>
      <question>What location?</question>
      <question>How many leads?</question>
    </initial_questions>
  </progressive_disclosure>
  
  <process>
    <step number="1" name="search_script">
      <description>Search Script Kiwi for lead scraping script</description>
      <tool_call>
        <mcp>script-kiwi</mcp>
        <tool>search</tool>
        <params>
          <query>google maps leads</query>
          <category>scraping</category>
        </params>
      </tool_call>
      <expected_output>Script name: "google_maps_leads"</expected_output>
    </step>
    
    <step number="2" name="run_scraping">
      <description>Execute the scraping script</description>
      <tool_call>
        <mcp>script-kiwi</mcp>
        <tool>run</tool>
        <params>
          <script_name>google_maps_leads</script_name>
          <params>
            <search_term>{industry}</search_term>
            <location>{location}</location>
            <max_results>{count}</max_results>
          </params>
        </params>
      </tool_call>
      <expected_output>List of leads with business info</expected_output>
    </step>
  </process>
  
  <outputs>
    <output name="leads">
      <description>List of scraped leads</description>
      <source>{step_2_output}</source>
    </output>
  </outputs>
</directive>
```

**Action:** Use Directive-Orchestration-Pattern.md as reference during implementation

---

## 3. Lockfile Version Pinning Behavior

**Status:** Clarified

**Question:** If a script is updated in registry but lockfile has old version, does `load` respect lockfile or warn?

**Decision:** **Lockfile always respected, with optional warning**

**Behavior:**

```python
def load_script(script_name: str, version: Optional[str] = None) -> dict:
    """Load script, respecting lockfile version."""
    # 1. Check lockfile
    lockfile = load_lockfile()
    pinned_version = lockfile.get("scripts", {}).get(script_name)
    
    if pinned_version:
        # Load specific version from registry
        script = get_script_from_registry(script_name, version=pinned_version)
        
        # Check if newer version exists
        latest_version = get_latest_version(script_name)
        if latest_version != pinned_version:
            # Optional warning (non-blocking)
            return {
                "script": script,
                "version": pinned_version,
                "warning": {
                    "message": f"Using pinned version {pinned_version}, latest is {latest_version}",
                    "suggestion": "Update lockfile to use latest version"
                }
            }
        return {"script": script, "version": pinned_version}
    
    # No lockfile entry, use latest
    return {"script": get_script_from_registry(script_name), "version": "latest"}
```

**Key Points:**
- Lockfile version is **always respected** (no auto-updates)
- Warning is **informational only** (doesn't block execution)
- User must explicitly update lockfile to get new version
- `run` tool also respects lockfile (loads pinned version)

**Action:** Implement lockfile checking in `load` and `run` tools

---

## 4. Knowledge Sync Edge Cases

**Status:** Needs edge case documentation

### 4.1 Large Files (>10MB)

**Decision:** **Skip large files, log warning**

```python
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def sync_file_to_db(file_path: Path) -> dict:
    """Sync file to database, handling large files."""
    file_size = file_path.stat().st_size
    
    if file_size > MAX_FILE_SIZE:
        return {
            "status": "skipped",
            "reason": "file_too_large",
            "file_size": file_size,
            "max_size": MAX_FILE_SIZE,
            "suggestion": "Split large files into smaller entries"
        }
    
    # Normal sync...
```

**Action:** Add size check in sync pipeline

### 4.2 Binary Files

**Decision:** **Skip binary files, only sync text files**

```python
def is_text_file(file_path: Path) -> bool:
    """Check if file is text-based."""
    text_extensions = {'.md', '.txt', '.json', '.yaml', '.yml', '.py', '.js', '.ts'}
    return file_path.suffix.lower() in text_extensions

def sync_file_to_db(file_path: Path) -> dict:
    """Sync file to database, skipping binary files."""
    if not is_text_file(file_path):
        return {
            "status": "skipped",
            "reason": "binary_file",
            "suggestion": "Knowledge Kiwi only syncs text files"
        }
    
    # Normal sync...
```

**Action:** Add file type check in sync pipeline

### 4.3 Deleted Local Files

**Decision:** **Keep in DB, mark as orphaned**

```python
def sync_db_to_files() -> dict:
    """Sync database to files, handling deleted local files."""
    db_entries = get_all_db_entries()
    
    for entry in db_entries:
        file_path = get_file_path(entry.zettel_id)
        
        if not file_path.exists():
            # File was deleted locally
            # Option 1: Keep in DB, mark as orphaned
            mark_entry_orphaned(entry.id)
            
            # Option 2: Delete from DB (if user confirms)
            # delete_entry(entry.id)
            
            log_sync_event({
                "entry_id": entry.id,
                "event": "local_file_deleted",
                "action": "marked_orphaned"
            })
```

**Default Behavior:**
- Keep entry in DB (preserves knowledge)
- Mark as `orphaned: true` in metadata
- User can manually delete via `delete_entry` tool

**Action:** Implement orphaned entry detection in sync

---

## 5. Script Migration Process

**Status:** Needs migration steps documented

**Question:** Is there a migration script, or is it manual? Any breaking changes?

**Decision:** **Semi-automated migration with manual verification**

### Migration Steps

**1. Identify scripts to migrate:**
```bash
# List all execution modules
find src/knowledge_kiwi -name "*.py" -path "*/scraping/*" -o -path "*/enrichment/*" -o -path "*/extraction/*"
```

**2. Create migration script:**
```python
# migration/migrate_scripts.py
import shutil
from pathlib import Path

def migrate_script(source_path: Path, target_category: str):
    """Migrate script from knowledge_kiwi to script_kiwi."""
    target_dir = Path("~/projects/script-kiwi/script_kiwi/execution") / target_category
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy file
    shutil.copy(source_path, target_dir / source_path.name)
    
    # Update imports
    update_imports(target_dir / source_path.name)
    
    # Add execute() function if missing
    ensure_execute_function(target_dir / source_path.name)
```

**3. Update imports:**
```python
# Old: from knowledge_kiwi.lib.api import api_call
# New: from script_kiwi.utils.api import api_call

IMPORT_MAPPING = {
    "knowledge_kiwi.lib.api": "script_kiwi.utils.api",
    "knowledge_kiwi.lib.preflight": "script_kiwi.utils.preflight",
    "knowledge_kiwi.lib.analytics": "script_kiwi.utils.analytics",
    # ... etc
}
```

**4. Verify execute() interface:**
- All scripts must implement `execute(params: dict) -> dict`
- See `Script-Interface-Specification.md` for exact signature
- Scripts with `main()` will be adapted automatically

**5. Test migrated scripts:**
```bash
# Run tests for each migrated script
pytest tests/execution/test_google_maps_leads.py
```

**Breaking Changes:**
- Import paths change: `knowledge_kiwi.lib.*` → `script_kiwi.utils.*`
- Function signature: Must implement `execute(params: dict) -> dict`
- No breaking changes to script logic (deterministic behavior preserved)

**Action:** Create migration script during Week 2, Day 6

---

## 6. Multi-User RLS Testing

**Status:** Needs clarification

**Question:** Should I assume single-user initially, or test multi-user from the start?

**Decision:** **Single-user initially, multi-user ready**

**RLS Policies (Already Defined):**
- Users can view all public scripts/directives
- Users can manage their own entries
- Service role bypasses RLS (for admin operations)

**Initial Approach:**
1. **Week 1-3:** Single-user testing (assume one user)
2. **Week 4:** Add multi-user test scenarios
3. **Production:** RLS policies enforce multi-user security

**Multi-User Test Scenarios (Week 4):**
```python
# tests/integration/test_multi_user.py

async def test_user_a_cannot_modify_user_b_script():
    """Test RLS prevents cross-user modifications."""
    user_a = create_test_user("user_a")
    user_b = create_test_user("user_b")
    
    # User A creates script
    script_id = await create_script(user_a, "test_script")
    
    # User B tries to modify (should fail)
    with pytest.raises(PermissionError):
        await update_script(user_b, script_id, {"name": "hacked"})
```

**Action:** 
- Week 1-3: Focus on single-user functionality
- Week 4: Add multi-user integration tests
- RLS policies are already defined in schema (ready for multi-user)

---

## Summary of Actions

| Item | Priority | Action | Timeline |
|------|----------|--------|----------|
| MCP SDK API verification | Medium | Test SDK before Week 2 | Day 7 (before tool implementation) |
| Directive examples | Low | Use existing Directive-Orchestration-Pattern.md | Reference during implementation |
| Lockfile behavior | Low | Implement lockfile checking in load/run | Week 2, Day 7-8 |
| Knowledge sync edge cases | Low | Add size/binary/orphaned checks | Week 3, Day 11-12 |
| Script migration | Low | Create migration script | Week 2, Day 6 |
| Multi-user RLS | Low | Single-user first, multi-user tests Week 4 | Week 4, Day 16-17 |

---

## Recommended Implementation Order

1. **Week 1:** Supabase schemas (highest confidence, no blockers)
2. **Day 7 (Week 2):** Verify MCP SDK API (quick check, 30 minutes)
3. **Week 2:** Script Kiwi implementation (migration + tools)
4. **Week 3:** Knowledge Kiwi (add edge case handling incrementally)
5. **Week 4:** Integration + multi-user tests

**Bottom Line:** Start with Week 1. The remaining items are edge cases that can be handled incrementally during implementation. The architecture is solid and ready to build.

