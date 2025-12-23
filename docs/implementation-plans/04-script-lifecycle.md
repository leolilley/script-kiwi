# Implementation Plan: Script Lifecycle Management

**Priority:** Medium  
**Impact:** Medium - Proactive monitoring  
**Effort:** Medium  
**Status:** Planning

---

## Overview

Track script lifecycle (active, deprecated, archived) and automate health monitoring. This addresses the video insight about checking if tools are "dead" - "I set up like a calendar event to check if it's dead every year. It hasn't been dead yet."

---

## Goals

1. **Track script lifecycle status** (active, deprecated, archived, experimental)
2. **Automated health checks** with scheduling
3. **Lifecycle transitions** with proper workflows
4. **Health status monitoring** (thriving, stable, declining, critical, dead)
5. **Lifecycle analytics** and reporting

---

## Technical Specifications

### 1. Database Schema Changes

#### Update `scripts` Table

```sql
-- Add lifecycle fields
ALTER TABLE scripts ADD COLUMN lifecycle_status text 
    CHECK (lifecycle_status IN ('active', 'deprecated', 'archived', 'experimental', 'sunset'))
    DEFAULT 'active';
ALTER TABLE scripts ADD COLUMN deprecation_date timestamptz;
ALTER TABLE scripts ADD COLUMN replacement_script_id uuid REFERENCES scripts(id);
ALTER TABLE scripts ADD COLUMN sunset_date timestamptz;  -- When script will be removed

-- Indexes
CREATE INDEX idx_scripts_lifecycle_status ON scripts(lifecycle_status);
CREATE INDEX idx_scripts_deprecation_date ON scripts(deprecation_date);
```

#### New Table: `script_lifecycle_events`

```sql
CREATE TABLE script_lifecycle_events (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    script_id uuid NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
    
    -- Event details
    event_type text NOT NULL CHECK (event_type IN (
        'created', 'activated', 'deprecated', 'archived', 
        'experimental', 'sunset', 'health_check', 'status_change'
    )),
    from_status text,
    to_status text,
    event_date timestamptz DEFAULT now(),
    
    -- Event metadata
    reason text,  -- Why did this event happen?
    performed_by uuid REFERENCES users(id),
    metadata jsonb,  -- Additional event data
    
    -- Health check specific
    health_status text CHECK (health_status IN ('thriving', 'stable', 'declining', 'critical', 'dead')),
    health_metrics jsonb,  -- Metrics at time of check
    
    created_at timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX idx_script_lifecycle_events_script_id ON script_lifecycle_events(script_id);
CREATE INDEX idx_script_lifecycle_events_event_type ON script_lifecycle_events(event_type);
CREATE INDEX idx_script_lifecycle_events_event_date ON script_lifecycle_events(event_date);
```

#### New Table: `script_health_schedules`

```sql
CREATE TABLE script_health_schedules (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    script_id uuid NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
    
    -- Schedule details
    interval_days integer NOT NULL DEFAULT 365,
    next_check_date timestamptz NOT NULL,
    last_check_date timestamptz,
    
    -- Notification settings
    notify_on_decline boolean DEFAULT true,
    notify_on_critical boolean DEFAULT true,
    notify_on_dead boolean DEFAULT true,
    notification_channels text[],  -- ['email', 'slack', 'webhook']
    
    -- Status
    is_active boolean DEFAULT true,
    
    -- Metadata
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    created_by uuid REFERENCES users(id),
    
    UNIQUE(script_id)
);

-- Index for finding scripts due for health check
CREATE INDEX idx_script_health_schedules_next_check ON script_health_schedules(next_check_date) 
    WHERE is_active = true;
```

### 2. Lifecycle Status Definitions

**Active:** Script is actively maintained and recommended for use
**Deprecated:** Script still works but not recommended for new projects
**Archived:** Script is kept for historical reference but not maintained
**Experimental:** Script is in testing/development phase
**Sunset:** Script is scheduled for removal

### 3. Health Status Definitions

**Thriving:** High usage, low errors, recent updates, growing adoption
**Stable:** Consistent usage, low errors, maintained
**Declining:** Decreasing usage, increasing errors, less maintenance
**Critical:** High error rate, low usage, needs immediate attention
**Dead:** No usage, no maintenance, should be deprecated/archived

### 4. New MCP Tool: `lifecycle`

**Location:** `script_kiwi/tools/lifecycle.py`

**Tool Definition:**
```python
{
    "name": "lifecycle",
    "description": "Manage script lifecycle and health monitoring",
    "inputSchema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_status", "deprecate", "archive", "activate", 
                        "set_experimental", "schedule_health_check", 
                        "check_health", "get_health_schedule", "get_lifecycle_history",
                        "get_lifecycle_report"],
                "description": "Action to perform"
            },
            "script_name": {
                "type": "string",
                "description": "Script name"
            },
            "reason": {
                "type": "string",
                "description": "Reason for status change"
            },
            "replacement_script": {
                "type": "string",
                "description": "Replacement script name (for deprecate)"
            },
            "sunset_date": {
                "type": "string",
                "format": "date",
                "description": "Date when script will be removed (ISO 8601)"
            },
            "interval_days": {
                "type": "integer",
                "description": "Health check interval in days (default: 365)"
            },
            "project_path": {
                "type": "string",
                "description": "Project root path"
            }
        },
        "required": ["action", "script_name"]
    }
}
```

---

## Implementation Steps

### Phase 1: Database Schema (Week 1)

1. **Create migration script**
   ```sql
   -- scripts/migrations/004_add_lifecycle_tracking.sql
   ALTER TABLE scripts ADD COLUMN lifecycle_status text DEFAULT 'active';
   -- ... etc
   CREATE TABLE script_lifecycle_events (...);
   CREATE TABLE script_health_schedules (...);
   ```

2. **Run migration**
   - Add lifecycle fields to scripts
   - Create lifecycle events table
   - Create health schedules table

### Phase 2: Core Lifecycle Tool (Week 2)

1. **Create lifecycle tool**
   ```python
   # script_kiwi/tools/lifecycle.py
   
   class LifecycleTool:
       async def get_status(self, script_name: str) -> dict:
           """Get current lifecycle status"""
           
       async def deprecate(self, script_name: str, reason: str,
                          replacement_script: str = None,
                          sunset_date: str = None) -> dict:
           """Deprecate a script"""
           
       async def archive(self, script_name: str, reason: str) -> dict:
           """Archive a script"""
           
       async def activate(self, script_name: str, reason: str) -> dict:
           """Activate a script (remove deprecation)"""
   ```

2. **Implement status transitions**
   - Validate transitions (can't go from archived to active)
   - Create lifecycle events
   - Update script status
   - Store in Knowledge-Kiwi

### Phase 3: Health Check Logic (Week 2)

1. **Implement health check**
   ```python
   # script_kiwi/utils/health_checker.py
   
   class HealthChecker:
       async def check_health(self, script_id: str) -> dict:
           """Check script health and determine status"""
           # 1. Query executions for recent usage
           # 2. Calculate error rate
           # 3. Check last update date
           # 4. Compare with replacement (if exists)
           # 5. Determine health status
           # 6. Create lifecycle event
           # 7. Return health report
   ```

2. **Health status calculation**
   ```python
   def calculate_health_status(metrics: dict) -> str:
       """Calculate health status from metrics"""
       if metrics.error_rate > 0.5 or metrics.usage_30d == 0:
           return "dead"
       elif metrics.error_rate > 0.2 or metrics.usage_trend == "decreasing":
           return "critical"
       elif metrics.usage_trend == "decreasing":
           return "declining"
       elif metrics.usage_trend == "increasing" and metrics.error_rate < 0.05:
           return "thriving"
       else:
           return "stable"
   ```

### Phase 4: Health Check Scheduling (Week 3)

1. **Implement scheduling**
   ```python
   # script_kiwi/utils/health_scheduler.py
   
   class HealthScheduler:
       async def schedule_health_check(self, script_id: str, 
                                      interval_days: int = 365) -> dict:
           """Schedule periodic health checks"""
           
       async def get_due_checks(self) -> list:
           """Get scripts due for health check"""
           
       async def run_scheduled_checks(self) -> dict:
           """Run all due health checks"""
   ```

2. **Background job**
   - Daily job to check for due health checks
   - Run health checks automatically
   - Send notifications if configured

### Phase 5: Lifecycle Analytics (Week 3)

1. **Lifecycle reporting**
   ```python
   async def get_lifecycle_report(project_path: str = None) -> dict:
       """Get comprehensive lifecycle report"""
       # 1. Count scripts by status
       # 2. Count scripts by health
       # 3. List deprecated scripts
       # 4. List scripts due for health check
       # 5. List scripts approaching sunset
       # 6. Return comprehensive report
   ```

2. **Lifecycle history**
   ```python
   async def get_lifecycle_history(script_name: str) -> dict:
       """Get lifecycle event history for script"""
       # Query script_lifecycle_events
       # Return timeline of events
   ```

### Phase 6: Testing & Documentation (Week 4)

1. **Unit tests**
   ```python
   # tests/tools/test_lifecycle.py
   - test_deprecate_script
   - test_archive_script
   - test_check_health
   - test_schedule_health_check
   - test_lifecycle_transitions
   ```

2. **Integration tests**
   - End-to-end lifecycle workflow
   - Automated health checks
   - Lifecycle reporting

3. **Documentation**
   - Update README
   - Lifecycle best practices
   - Health check guide

---

## Usage Examples

### Example 1: Deprecate Script

```python
# Deprecate a script
result = await lifecycle_tool.execute({
    "action": "deprecate",
    "script_name": "old_scraping_script",
    "reason": "Replaced by new_scraping_script with better API",
    "replacement_script": "new_scraping_script",
    "sunset_date": "2025-12-31"  # Remove after this date
})

# Returns:
{
    "status": "success",
    "script_name": "old_scraping_script",
    "lifecycle_status": "deprecated",
    "deprecation_date": "2025-01-15T10:00:00Z",
    "replacement_script": "new_scraping_script",
    "sunset_date": "2025-12-31T00:00:00Z",
    "lifecycle_event": {
        "event_type": "deprecated",
        "from_status": "active",
        "to_status": "deprecated",
        "reason": "Replaced by new_scraping_script..."
    },
    "warning": "This script is deprecated. Use new_scraping_script instead."
}
```

### Example 2: Check Health

```python
# Check script health
result = await lifecycle_tool.execute({
    "action": "check_health",
    "script_name": "old_scraping_script"
})

# Returns:
{
    "status": "success",
    "script_name": "old_scraping_script",
    "health_status": "declining",
    "health_metrics": {
        "last_executed": "2024-12-01T10:00:00Z",
        "execution_count_30d": 5,
        "execution_count_90d": 12,
        "execution_trend": "decreasing",
        "error_rate": 0.2,
        "avg_duration_sec": 3.5,
        "last_updated": "2024-06-01T00:00:00Z",
        "days_since_update": 228
    },
    "recommendation": "Script health is declining. Consider migrating to replacement or updating script.",
    "lifecycle_event": {
        "event_type": "health_check",
        "health_status": "declining",
        "health_metrics": {...}
    }
}
```

### Example 3: Schedule Health Check

```python
# Schedule periodic health checks
result = await lifecycle_tool.execute({
    "action": "schedule_health_check",
    "script_name": "old_scraping_script",
    "interval_days": 365
})

# Returns:
{
    "status": "success",
    "script_name": "old_scraping_script",
    "health_schedule": {
        "interval_days": 365,
        "next_check_date": "2026-01-15T10:00:00Z",
        "is_active": true,
        "notify_on_decline": true,
        "notify_on_critical": true,
        "notify_on_dead": true
    },
    "message": "Health check scheduled. Next check: 2026-01-15"
}
```

### Example 4: Get Lifecycle Report

```python
# Get comprehensive lifecycle report
result = await lifecycle_tool.execute({
    "action": "get_lifecycle_report",
    "project_path": "/home/user/my-project"
})

# Returns:
{
    "status": "success",
    "summary": {
        "total_scripts": 50,
        "by_status": {
            "active": 35,
            "deprecated": 10,
            "archived": 3,
            "experimental": 2
        },
        "by_health": {
            "thriving": 20,
            "stable": 15,
            "declining": 8,
            "critical": 5,
            "dead": 2
        },
        "deprecated_count": 10,
        "due_for_health_check": 5,
        "approaching_sunset": 2
    },
    "deprecated_scripts": [
        {
            "script_name": "old_scraping_script",
            "deprecation_date": "2025-01-15",
            "replacement_script": "new_scraping_script",
            "sunset_date": "2025-12-31",
            "health_status": "declining"
        }
    ],
    "due_for_health_check": [
        {
            "script_name": "script_a",
            "next_check_date": "2025-01-20",
            "days_overdue": 5
        }
    ],
    "approaching_sunset": [
        {
            "script_name": "old_script",
            "sunset_date": "2025-12-31",
            "days_remaining": 350
        }
    ],
    "recommendations": [
        "5 scripts are due for health check",
        "2 scripts are approaching sunset - plan migration",
        "5 scripts have critical health - investigate immediately"
    ]
}
```

### Example 5: Get Lifecycle History

```python
# Get lifecycle event history
result = await lifecycle_tool.execute({
    "action": "get_lifecycle_history",
    "script_name": "old_scraping_script"
})

# Returns:
{
    "status": "success",
    "script_name": "old_scraping_script",
    "current_status": "deprecated",
    "lifecycle_history": [
        {
            "event_type": "created",
            "event_date": "2020-01-15T10:00:00Z",
            "to_status": "active"
        },
        {
            "event_type": "health_check",
            "event_date": "2023-01-15T10:00:00Z",
            "health_status": "stable",
            "health_metrics": {...}
        },
        {
            "event_type": "health_check",
            "event_date": "2024-01-15T10:00:00Z",
            "health_status": "declining",
            "health_metrics": {...}
        },
        {
            "event_type": "deprecated",
            "event_date": "2025-01-15T10:00:00Z",
            "from_status": "active",
            "to_status": "deprecated",
            "reason": "Replaced by new_scraping_script"
        }
    ],
    "timeline_summary": "Script was active for 5 years, health declined in 2024, deprecated in 2025"
}
```

---

## Testing Requirements

### Unit Tests

```python
# tests/tools/test_lifecycle.py

class TestLifecycleTool:
    def test_deprecate_script(self):
        """Test deprecating a script"""
        
    def test_archive_script(self):
        """Test archiving a script"""
        
    def test_check_health(self):
        """Test health check"""
        
    def test_schedule_health_check(self):
        """Test scheduling health checks"""
        
    def test_lifecycle_transitions(self):
        """Test valid/invalid lifecycle transitions"""
        
    def test_get_lifecycle_report(self):
        """Test lifecycle reporting"""
```

### Integration Tests

```python
# tests/integration/test_lifecycle_workflow.py

class TestLifecycleWorkflow:
    def test_full_lifecycle(self):
        """Test: create → active → health check → deprecate → archive"""
        
    def test_automated_health_checks(self):
        """Test automated health check scheduling"""
        
    def test_lifecycle_with_knowledge_kiwi(self):
        """Test Knowledge-Kiwi integration"""
```

---

## Success Metrics

1. **Lifecycle Coverage:** % of scripts with lifecycle status
2. **Health Check Coverage:** % of scripts with scheduled health checks
3. **Proactive Deprecation:** % of scripts deprecated before becoming dead
4. **Migration Success:** % of deprecated scripts successfully migrated

---

## Future Enhancements

1. **Automated Deprecation:** Auto-deprecate scripts based on health metrics
2. **Migration Assistant:** Automated migration tools for deprecated scripts
3. **Lifecycle Dashboard:** Visual dashboard for lifecycle management
4. **Notification System:** Email/Slack notifications for lifecycle events
5. **Lifecycle Analytics:** Advanced analytics on script lifecycle patterns

---

## Dependencies

- **Script-Kiwi:** Core script registry and execution tracking
- **Knowledge-Kiwi:** Storage for lifecycle documentation (optional)
- **Supabase:** Database for lifecycle events and schedules

---

## Timeline

- **Week 1:** Database schema
- **Week 2:** Core lifecycle tool and health check logic
- **Week 3:** Health check scheduling and lifecycle analytics
- **Week 4:** Testing and documentation

**Total:** 4 weeks

---

## Related Documents

- [Legacy Script Maintenance Plan](./01-legacy-script-maintenance.md)
- [Script Alternative Recommendations Plan](./02-script-alternatives.md)
- [Niche Script Value Tracking Plan](./03-niche-script-tracking.md)
