# Implementation Plan: Legacy Script Maintenance Tools

**Priority:** High  
**Impact:** High - Addresses real pain point  
**Effort:** Medium  
**Status:** Planning

---

## Overview

Add explicit "legacy maintenance" features to Script-Kiwi to help developers maintain, track, and migrate legacy scripts. This addresses the video insight that "the highest paid engineers forever throughout history were the people who are actually maintaining legacy systems."

---

## Goals

1. **Mark scripts as legacy** with maintenance notes
2. **Find legacy dependencies** across projects
3. **Suggest migration paths** from legacy to modern scripts
4. **Track legacy script health** and usage patterns
5. **Document maintenance requirements** in Knowledge-Kiwi

---

## Technical Specifications

### 1. Database Schema Changes

#### New Table: `script_legacy_metadata`

```sql
CREATE TABLE script_legacy_metadata (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    script_id uuid NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
    
    -- Legacy status
    is_legacy boolean DEFAULT false,
    marked_legacy_at timestamptz,
    marked_legacy_by uuid REFERENCES users(id),
    legacy_reason text,  -- Why is this legacy?
    
    -- Maintenance info
    maintenance_notes text,
    maintenance_priority text CHECK (maintenance_priority IN ('low', 'medium', 'high', 'critical')),
    last_maintained_at timestamptz,
    maintained_by uuid REFERENCES users(id),
    
    -- Migration info
    replacement_script_id uuid REFERENCES scripts(id),
    migration_guide_url text,
    migration_effort text CHECK (migration_effort IN ('low', 'medium', 'high')),
    migration_status text CHECK (migration_status IN ('not_started', 'in_progress', 'completed', 'deprecated')),
    
    -- Health tracking
    health_status text CHECK (health_status IN ('thriving', 'stable', 'declining', 'critical', 'dead')),
    last_health_check timestamptz,
    health_check_interval_days integer DEFAULT 365,
    
    -- Metadata
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(script_id)
);

-- Indexes
CREATE INDEX idx_script_legacy_metadata_is_legacy ON script_legacy_metadata(is_legacy);
CREATE INDEX idx_script_legacy_metadata_health_status ON script_legacy_metadata(health_status);
CREATE INDEX idx_script_legacy_metadata_migration_status ON script_legacy_metadata(migration_status);
```

#### Update `scripts` Table

```sql
-- Add legacy flag for quick filtering
ALTER TABLE scripts ADD COLUMN is_legacy boolean DEFAULT false;
CREATE INDEX idx_scripts_is_legacy ON scripts(is_legacy);
```

### 2. New MCP Tool: `maintain`

**Location:** `script_kiwi/tools/maintain.py`

**Tool Definition:**
```python
{
    "name": "maintain",
    "description": "Tools for maintaining legacy scripts",
    "inputSchema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["mark_legacy", "unmark_legacy", "update_maintenance", 
                        "check_health", "find_dependencies", "suggest_migration", 
                        "schedule_health_check", "get_legacy_report"],
                "description": "Action to perform"
            },
            "script_name": {
                "type": "string",
                "description": "Name of script to maintain"
            },
            "reason": {
                "type": "string",
                "description": "Reason for marking as legacy (required for mark_legacy)"
            },
            "maintenance_notes": {
                "type": "string",
                "description": "Maintenance notes (for update_maintenance)"
            },
            "maintenance_priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Maintenance priority"
            },
            "replacement_script": {
                "type": "string",
                "description": "Name of replacement script (for suggest_migration)"
            },
            "migration_effort": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Estimated migration effort"
            },
            "project_path": {
                "type": "string",
                "description": "Project root path (for project-specific analysis)"
            }
        },
        "required": ["action", "script_name"]
    }
}
```

### 3. Tool Implementation

#### `mark_legacy`
```python
async def mark_legacy(script_name: str, reason: str, 
                     maintenance_priority: str = "medium",
                     replacement_script: str = None,
                     project_path: str = None) -> dict:
    """
    Mark a script as legacy.
    
    Steps:
    1. Resolve script location (Project → User → Registry)
    2. Check if already marked as legacy
    3. Create/update script_legacy_metadata entry
    4. Update scripts.is_legacy flag
    5. Store maintenance notes in Knowledge-Kiwi
    6. Find all dependent scripts
    7. Return legacy metadata + dependencies
    """
```

#### `find_dependencies`
```python
async def find_dependencies(script_name: str, 
                           project_path: str = None) -> dict:
    """
    Find all scripts that depend on this legacy script.
    
    Steps:
    1. Query executions table for scripts that import/call this script
    2. Check lockfiles for pinned versions
    3. Search script content for imports/references
    4. Check Knowledge-Kiwi for documented dependencies
    5. Return list of dependent scripts with usage stats
    """
```

#### `suggest_migration`
```python
async def suggest_migration(script_name: str,
                           project_path: str = None) -> dict:
    """
    Suggest how to migrate from legacy script.
    
    Steps:
    1. Check if replacement_script_id exists in legacy_metadata
    2. Search Knowledge-Kiwi for migration patterns
    3. Search registry for similar/alternative scripts
    4. Compare API differences between legacy and alternatives
    5. Generate migration guide
    6. Store migration guide in Knowledge-Kiwi
    7. Return migration path with effort estimate
    """
```

#### `check_health`
```python
async def check_health(script_name: str,
                      project_path: str = None) -> dict:
    """
    Check legacy script health metrics.
    
    Steps:
    1. Query executions table for recent usage
    2. Calculate error rate (failed executions / total)
    3. Check last execution date
    4. Compare with replacement script (if exists)
    5. Determine health status (thriving/stable/declining/critical/dead)
    6. Update health_status in legacy_metadata
    7. Return health report
    """
```

#### `schedule_health_check`
```python
async def schedule_health_check(script_name: str,
                               interval_days: int = 365,
                               project_path: str = None) -> dict:
    """
    Schedule periodic health checks for legacy script.
    
    Steps:
    1. Update health_check_interval_days in legacy_metadata
    2. Calculate next_health_check date
    3. Create calendar reminder (or cron job entry)
    4. Store schedule in Knowledge-Kiwi
    5. Return schedule confirmation
    """
```

#### `get_legacy_report`
```python
async def get_legacy_report(project_path: str = None,
                          include_health: bool = True) -> dict:
    """
    Get comprehensive report of all legacy scripts.
    
    Steps:
    1. Query all scripts with is_legacy=true
    2. For each, get legacy_metadata
    3. If include_health, check health for each
    4. Group by maintenance_priority
    5. Calculate statistics (total legacy, by status, by health)
    6. Return comprehensive report
    """
```

---

## Implementation Steps

### Phase 1: Database & Schema (Week 1)

1. **Create migration script**
   ```bash
   # scripts/migrations/001_add_legacy_metadata.sql
   ```

2. **Run migration**
   - Create `script_legacy_metadata` table
   - Add `is_legacy` column to `scripts` table
   - Create indexes

3. **Update Supabase schema**
   - Apply migration to production
   - Update schema documentation

### Phase 2: Core Tool Implementation (Week 2)

1. **Create `maintain.py` tool**
   ```python
   # script_kiwi/tools/maintain.py
   class MaintainTool:
       def __init__(self, project_path: str = None):
           self.registry = ScriptRegistry()
           self.resolver = ScriptResolver(project_path)
           self.knowledge_client = KnowledgeKiwiClient()  # If available
   ```

2. **Implement core actions**
   - `mark_legacy`
   - `find_dependencies`
   - `check_health`
   - `suggest_migration`

3. **Add to MCP server**
   ```python
   # script_kiwi/server.py
   from .tools.maintain import MaintainTool
   
   @self.server.list_tools()
   async def list_tools():
       # ... existing tools ...
       tools.append(Tool(
           name="maintain",
           description="Tools for maintaining legacy scripts",
           inputSchema={...}
       ))
   ```

### Phase 3: Knowledge-Kiwi Integration (Week 2-3)

1. **Create Knowledge-Kiwi entry types**
   - `legacy_maintenance_notes`
   - `migration_guide`
   - `dependency_map`

2. **Integrate with maintain tool**
   - Store maintenance notes in Knowledge-Kiwi
   - Store migration guides
   - Link related entries

3. **Create Knowledge-Kiwi collections**
   - "Legacy Scripts" collection
   - "Migration Guides" collection

### Phase 4: Health Monitoring (Week 3)

1. **Implement health check logic**
   - Query executions table
   - Calculate metrics (error rate, usage, etc.)
   - Determine health status

2. **Add scheduling**
   - Calendar integration (or cron job)
   - Automated health checks
   - Alert system (optional)

3. **Create health dashboard**
   - CLI command or tool output
   - Visual health status

### Phase 5: Testing & Documentation (Week 4)

1. **Unit tests**
   ```python
   # tests/tools/test_maintain.py
   - test_mark_legacy
   - test_find_dependencies
   - test_check_health
   - test_suggest_migration
   ```

2. **Integration tests**
   - End-to-end legacy workflow
   - Knowledge-Kiwi integration
   - Health check scheduling

3. **Documentation**
   - Update README with maintain tool
   - Create usage examples
   - Document legacy workflow

---

## Usage Examples

### Example 1: Mark Script as Legacy

```python
# Mark a script as legacy
result = await maintain_tool.execute({
    "action": "mark_legacy",
    "script_name": "old_scraping_script",
    "reason": "Uses deprecated API, replaced by new_scraping_script",
    "maintenance_priority": "high",
    "replacement_script": "new_scraping_script"
})

# Returns:
{
    "status": "success",
    "script_name": "old_scraping_script",
    "legacy_metadata": {
        "is_legacy": true,
        "marked_legacy_at": "2025-01-15T10:00:00Z",
        "legacy_reason": "Uses deprecated API...",
        "replacement_script": "new_scraping_script",
        "maintenance_priority": "high"
    },
    "dependencies": [
        {
            "script_name": "dependent_script_1",
            "usage_count": 45,
            "last_used": "2025-01-10T15:30:00Z"
        }
    ],
    "knowledge_entry": {
        "zettel_id": "legacy-old-scraping-script",
        "location": "project"
    }
}
```

### Example 2: Check Legacy Script Health

```python
# Check health of legacy script
result = await maintain_tool.execute({
    "action": "check_health",
    "script_name": "old_scraping_script"
})

# Returns:
{
    "status": "success",
    "script_name": "old_scraping_script",
    "health_status": "declining",
    "metrics": {
        "last_executed": "2024-12-01T10:00:00Z",
        "execution_count_30d": 5,
        "execution_count_90d": 12,
        "error_rate": 0.2,
        "avg_duration_sec": 3.5,
        "trend": "decreasing"
    },
    "recommendation": "Consider migrating to new_scraping_script. Usage is declining and error rate is high."
}
```

### Example 3: Find Dependencies

```python
# Find all scripts that depend on legacy script
result = await maintain_tool.execute({
    "action": "find_dependencies",
    "script_name": "old_scraping_script",
    "project_path": "/home/user/my-project"
})

# Returns:
{
    "status": "success",
    "script_name": "old_scraping_script",
    "dependencies": [
        {
            "script_name": "dependent_script_1",
            "location": "project",
            "usage_count": 45,
            "last_used": "2025-01-10T15:30:00Z",
            "import_type": "direct_import",
            "lockfile_version": "1.0.0"
        },
        {
            "script_name": "dependent_script_2",
            "location": "user",
            "usage_count": 12,
            "last_used": "2024-11-20T08:00:00Z",
            "import_type": "indirect"
        }
    ],
    "total_dependencies": 2,
    "recommendation": "2 scripts depend on this legacy script. Update them before deprecating."
}
```

### Example 4: Get Legacy Report

```python
# Get comprehensive legacy script report
result = await maintain_tool.execute({
    "action": "get_legacy_report",
    "project_path": "/home/user/my-project",
    "include_health": true
})

# Returns:
{
    "status": "success",
    "summary": {
        "total_legacy_scripts": 5,
        "by_priority": {
            "critical": 1,
            "high": 2,
            "medium": 1,
            "low": 1
        },
        "by_health": {
            "thriving": 0,
            "stable": 2,
            "declining": 2,
            "critical": 1,
            "dead": 0
        }
    },
    "legacy_scripts": [
        {
            "script_name": "old_scraping_script",
            "health_status": "declining",
            "maintenance_priority": "high",
            "dependencies_count": 2,
            "replacement_available": true
        },
        # ... more scripts
    ],
    "recommendations": [
        "Migrate old_scraping_script to new_scraping_script (high priority, declining health)",
        "Schedule health check for legacy_script_2 (no recent checks)"
    ]
}
```

---

## Testing Requirements

### Unit Tests

```python
# tests/tools/test_maintain.py

class TestMaintainTool:
    def test_mark_legacy(self):
        """Test marking script as legacy"""
        
    def test_unmark_legacy(self):
        """Test unmarking legacy script"""
        
    def test_find_dependencies(self):
        """Test finding dependent scripts"""
        
    def test_check_health_thriving(self):
        """Test health check for thriving script"""
        
    def test_check_health_dead(self):
        """Test health check for dead script"""
        
    def test_suggest_migration(self):
        """Test migration path suggestion"""
        
    def test_schedule_health_check(self):
        """Test scheduling health checks"""
        
    def test_get_legacy_report(self):
        """Test comprehensive legacy report"""
```

### Integration Tests

```python
# tests/integration/test_legacy_workflow.py

class TestLegacyWorkflow:
    def test_full_legacy_lifecycle(self):
        """Test: mark → check health → find deps → suggest migration → migrate"""
        
    def test_legacy_with_knowledge_kiwi(self):
        """Test Knowledge-Kiwi integration for legacy scripts"""
        
    def test_legacy_health_monitoring(self):
        """Test automated health check scheduling"""
```

---

## Migration Considerations

### Existing Scripts

- **No breaking changes** - All existing scripts continue to work
- **Opt-in feature** - Scripts are not marked as legacy by default
- **Backward compatible** - Old tools/APIs still function

### Data Migration

- **No data migration needed** - New tables, no existing data to migrate
- **Optional migration** - Can retroactively mark existing scripts as legacy

---

## Success Metrics

1. **Adoption Rate:** % of legacy scripts properly marked and maintained
2. **Migration Success:** % of legacy scripts successfully migrated
3. **Health Monitoring:** % of legacy scripts with scheduled health checks
4. **Dependency Resolution:** % of legacy dependencies identified and updated

---

## Future Enhancements

1. **Automated Migration Tools:** Scripts to help migrate from legacy to new
2. **Legacy Script Deprecation Warnings:** Alert users when using legacy scripts
3. **Migration Cost Calculator:** Estimate effort/cost of migration
4. **Legacy Script Archive:** Archive deprecated scripts with full history
5. **Community Legacy Scripts:** Share legacy maintenance knowledge

---

## Dependencies

- **Script-Kiwi:** Core script registry and execution
- **Knowledge-Kiwi:** Storage for maintenance notes and migration guides (optional)
- **Supabase:** Database for legacy metadata

---

## Timeline

- **Week 1:** Database schema and migration
- **Week 2:** Core tool implementation
- **Week 3:** Knowledge-Kiwi integration and health monitoring
- **Week 4:** Testing and documentation

**Total:** 4 weeks

---

## Open Questions

1. Should legacy scripts be blocked from new executions? (Probably not - opt-in warnings)
2. How to handle legacy scripts in lockfiles? (Keep as-is, add warning)
3. Should we auto-detect legacy scripts? (Maybe based on age + low usage)
4. Integration with Context-Kiwi directives? (Mark directives that use legacy scripts)

---

## Related Documents

- [Script Alternative Recommendations Plan](./02-script-alternatives.md)
- [Script Lifecycle Management Plan](./04-script-lifecycle.md)
- [Knowledge-Kiwi Integration Guide](../guides/Knowledge-Kiwi-Integration.md)
