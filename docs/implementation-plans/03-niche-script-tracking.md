# Implementation Plan: Niche Script Value Tracking

**Priority:** High  
**Impact:** Medium - Preserves valuable niche tools  
**Effort:** Low - Enhance existing metrics  
**Status:** Planning

---

## Overview

Track value metrics for niche scripts even with low usage. This addresses the video insight that "developer-focused tools don't need mass adoption to be valuable" and "specialized tools serve specific needs" - preventing deletion of valuable niche scripts just because they're rarely used.

---

## Goals

1. **Track niche script value** beyond usage count
2. **Calculate value score** based on success rate, time saved, etc.
3. **Identify niche indicators** (low usage but high value)
4. **Prevent deletion** of valuable niche scripts
5. **Promote niche scripts** in discovery

---

## Technical Specifications

### 1. Database Schema Changes

#### Update `scripts` Table

```sql
-- Add niche/value tracking columns
ALTER TABLE scripts ADD COLUMN is_niche boolean DEFAULT false;
ALTER TABLE scripts ADD COLUMN value_score numeric(3,2);  -- 0.00 to 1.00
ALTER TABLE scripts ADD COLUMN niche_indicator boolean DEFAULT false;
ALTER TABLE scripts ADD COLUMN last_value_calculation timestamptz;

-- Indexes
CREATE INDEX idx_scripts_is_niche ON scripts(is_niche);
CREATE INDEX idx_scripts_value_score ON scripts(value_score);
CREATE INDEX idx_scripts_niche_indicator ON scripts(niche_indicator);
```

#### New Table: `script_value_metrics`

```sql
CREATE TABLE script_value_metrics (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    script_id uuid NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
    
    -- Usage metrics
    usage_count integer DEFAULT 0,
    unique_users integer DEFAULT 0,
    execution_count_30d integer DEFAULT 0,
    execution_count_90d integer DEFAULT 0,
    
    -- Value metrics
    success_rate numeric(5,4) DEFAULT 0,  -- 0.0000 to 1.0000
    avg_duration_sec numeric(10,2),
    time_saved_hours numeric(10,2),  -- Estimated time saved
    cost_saved_usd numeric(10,2),  -- Estimated cost savings
    
    -- Value score calculation
    value_score numeric(3,2) DEFAULT 0,  -- 0.00 to 1.00
    value_score_components jsonb,  -- Breakdown of score calculation
    
    -- Niche indicators
    is_niche boolean DEFAULT false,
    niche_reason text,  -- Why is this niche?
    niche_value text,  -- What makes it valuable despite low usage?
    
    -- Metadata
    calculated_at timestamptz DEFAULT now(),
    calculation_method text,  -- How was value calculated?
    
    UNIQUE(script_id)
);

-- Indexes
CREATE INDEX idx_script_value_metrics_value_score ON script_value_metrics(value_score);
CREATE INDEX idx_script_value_metrics_is_niche ON script_value_metrics(is_niche);
CREATE INDEX idx_script_value_metrics_calculated_at ON script_value_metrics(calculated_at);
```

### 2. Value Score Calculation

**Formula:**
```python
def calculate_value_score(script_id: str) -> float:
    """
    Calculate value score (0.00 to 1.00) based on:
    - Success rate (40% weight)
    - Time saved (30% weight)
    - Cost saved (20% weight)
    - User satisfaction (10% weight) - if available
    """
    metrics = get_script_metrics(script_id)
    
    # Normalize each component to 0-1 scale
    success_rate_score = metrics.success_rate  # Already 0-1
    
    # Time saved: normalize (assume max 100 hours saved = 1.0)
    time_saved_score = min(metrics.time_saved_hours / 100, 1.0)
    
    # Cost saved: normalize (assume max $1000 saved = 1.0)
    cost_saved_score = min(metrics.cost_saved_usd / 1000, 1.0)
    
    # User satisfaction: if available (from feedback)
    user_satisfaction_score = metrics.user_satisfaction or 0.5  # Default 0.5
    
    # Weighted average
    value_score = (
        success_rate_score * 0.4 +
        time_saved_score * 0.3 +
        cost_saved_score * 0.2 +
        user_satisfaction_score * 0.1
    )
    
    return round(value_score, 2)
```

**Niche Indicator:**
```python
def is_niche_script(usage_count: int, value_score: float) -> bool:
    """
    Script is niche if:
    - Usage count < 10 AND value_score > 0.8
    - OR usage_count < 50 AND value_score > 0.9
    """
    if usage_count < 10 and value_score > 0.8:
        return True
    if usage_count < 50 and value_score > 0.9:
        return True
    return False
```

### 3. Enhance Existing Tools

#### Update `search` Tool

**Location:** `script_kiwi/tools/search.py`

**Enhancement:**
```python
# Don't filter by usage count
# Rank by relevance AND value_score
# Tag results: "Niche but valuable" if niche_indicator=True

def search_with_value_ranking(query: str, include_niche: bool = True):
    """Search including niche scripts, ranked by value"""
    results = search_scripts(query)
    
    # Rank by: relevance_score * (0.7) + value_score * (0.3)
    for result in results:
        result["relevance_score"] = calculate_relevance(query, result)
        result["combined_score"] = (
            result["relevance_score"] * 0.7 +
            result.get("value_score", 0.5) * 0.3
        )
        
        if result.get("niche_indicator"):
            result["tags"].append("Niche but valuable")
    
    # Sort by combined_score, not just usage
    results.sort(key=lambda x: x["combined_score"], reverse=True)
    return results
```

#### Update `remove` Tool

**Location:** `script_kiwi/tools/remove.py`

**Enhancement:**
```python
# Check value_score before allowing deletion
# Warn if niche_indicator=True

async def remove_with_value_check(script_name: str, force: bool = False):
    """Remove script with value check"""
    script = await load_script(script_name)
    metrics = get_value_metrics(script.id)
    
    if metrics.niche_indicator and not force:
        return {
            "status": "error",
            "error": "NICHE_SCRIPT_PROTECTED",
            "message": f"This script is marked as niche but valuable (value_score: {metrics.value_score}). Use force=true to delete.",
            "value_metrics": {
                "value_score": metrics.value_score,
                "usage_count": metrics.usage_count,
                "success_rate": metrics.success_rate,
                "niche_reason": metrics.niche_reason
            }
        }
    
    # Proceed with deletion
    return await remove_script(script_name, force)
```

### 4. New Tool: `value`

**Location:** `script_kiwi/tools/value.py`

**Tool Definition:**
```python
{
    "name": "value",
    "description": "Track and analyze script value metrics",
    "inputSchema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["calculate", "get_metrics", "mark_niche", 
                        "get_niche_scripts", "update_value"],
                "description": "Action to perform"
            },
            "script_name": {
                "type": "string",
                "description": "Script name (for calculate, get_metrics, mark_niche)"
            },
            "niche_reason": {
                "type": "string",
                "description": "Reason why script is niche (for mark_niche)"
            },
            "niche_value": {
                "type": "string",
                "description": "What makes it valuable (for mark_niche)"
            },
            "project_path": {
                "type": "string",
                "description": "Project root path"
            }
        },
        "required": ["action"]
    }
}
```

---

## Implementation Steps

### Phase 1: Database Schema (Week 1)

1. **Create migration script**
   ```sql
   -- scripts/migrations/003_add_value_tracking.sql
   ALTER TABLE scripts ADD COLUMN is_niche boolean DEFAULT false;
   ALTER TABLE scripts ADD COLUMN value_score numeric(3,2);
   -- ... etc
   CREATE TABLE script_value_metrics (...);
   ```

2. **Run migration**
   - Add columns to scripts table
   - Create script_value_metrics table
   - Create indexes

### Phase 2: Value Calculation Logic (Week 1)

1. **Implement value score calculation**
   ```python
   # script_kiwi/utils/value_calculator.py
   
   class ValueCalculator:
       def calculate_value_score(self, script_id: str) -> float:
           """Calculate value score for script"""
           
       def calculate_time_saved(self, script_id: str) -> float:
           """Estimate time saved by script"""
           
       def calculate_cost_saved(self, script_id: str) -> float:
           """Estimate cost saved by script"""
   ```

2. **Implement niche detection**
   ```python
   def is_niche_script(self, usage_count: int, value_score: float) -> bool:
       """Determine if script is niche but valuable"""
   ```

### Phase 3: Enhance Existing Tools (Week 2)

1. **Update search tool**
   - Add value_score to ranking
   - Don't filter niche scripts
   - Tag niche scripts

2. **Update remove tool**
   - Check niche_indicator
   - Warn before deleting valuable scripts
   - Require force flag for niche scripts

3. **Update load tool**
   - Show value_score in response
   - Show niche_indicator if true
   - Include value metrics

### Phase 4: Value Tool Implementation (Week 2)

1. **Create value tool**
   ```python
   # script_kiwi/tools/value.py
   
   class ValueTool:
       async def calculate(self, script_name: str) -> dict:
           """Calculate value metrics for script"""
           
       async def get_metrics(self, script_name: str) -> dict:
           """Get value metrics for script"""
           
       async def mark_niche(self, script_name: str, 
                           niche_reason: str, niche_value: str) -> dict:
           """Manually mark script as niche"""
           
       async def get_niche_scripts(self, project_path: str = None) -> dict:
           """Get all niche scripts"""
   ```

2. **Add to MCP server**
   ```python
   # script_kiwi/server.py
   from .tools.value import ValueTool
   
   tools.append(Tool(
       name="value",
       description="Track and analyze script value metrics",
       inputSchema={...}
   ))
   ```

### Phase 5: Automated Value Calculation (Week 3)

1. **Background job for value calculation**
   ```python
   # script_kiwi/utils/value_scheduler.py
   
   async def calculate_all_script_values():
       """Calculate value scores for all scripts"""
       scripts = get_all_scripts()
       for script in scripts:
           value_score = calculate_value_score(script.id)
           update_value_metrics(script.id, value_score)
   ```

2. **Schedule periodic calculation**
   - Daily/weekly job to recalculate values
   - Update niche indicators
   - Store in script_value_metrics

### Phase 6: Testing & Documentation (Week 3)

1. **Unit tests**
   ```python
   # tests/tools/test_value.py
   - test_calculate_value_score
   - test_is_niche_script
   - test_mark_niche
   - test_get_niche_scripts
   ```

2. **Integration tests**
   - End-to-end value tracking
   - Search with value ranking
   - Remove protection for niche scripts

3. **Documentation**
   - Update README
   - Value calculation explanation
   - Niche script best practices

---

## Usage Examples

### Example 1: Calculate Value Score

```python
# Calculate value metrics for script
result = await value_tool.execute({
    "action": "calculate",
    "script_name": "niche_data_processor"
})

# Returns:
{
    "status": "success",
    "script_name": "niche_data_processor",
    "value_metrics": {
        "usage_count": 8,
        "unique_users": 3,
        "execution_count_30d": 2,
        "execution_count_90d": 5,
        "success_rate": 1.0,  # 100% success
        "avg_duration_sec": 0.5,
        "time_saved_hours": 50,  # Estimated
        "cost_saved_usd": 200,  # Estimated
        "value_score": 0.92,  # High value despite low usage
        "value_score_components": {
            "success_rate": 1.0,
            "time_saved": 0.5,
            "cost_saved": 0.2,
            "user_satisfaction": 0.5
        },
        "is_niche": true,
        "niche_indicator": true,
        "niche_reason": "Specialized data processing for specific use case",
        "recommendation": "Keep: High value despite low usage"
    }
}
```

### Example 2: Mark Script as Niche

```python
# Manually mark script as niche
result = await value_tool.execute({
    "action": "mark_niche",
    "script_name": "specialized_validator",
    "niche_reason": "Validates specific data format used by only 3 teams",
    "niche_value": "Critical for those teams, saves hours of manual validation"
})

# Returns:
{
    "status": "success",
    "script_name": "specialized_validator",
    "marked_as_niche": true,
    "niche_reason": "Validates specific data format...",
    "niche_value": "Critical for those teams...",
    "protection": "Script is now protected from accidental deletion"
}
```

### Example 3: Get All Niche Scripts

```python
# Get all niche scripts
result = await value_tool.execute({
    "action": "get_niche_scripts",
    "project_path": "/home/user/my-project"
})

# Returns:
{
    "status": "success",
    "niche_scripts": [
        {
            "script_name": "niche_data_processor",
            "value_score": 0.92,
            "usage_count": 8,
            "niche_reason": "Specialized data processing",
            "niche_value": "Saves 50 hours per month for 3 teams"
        },
        {
            "script_name": "specialized_validator",
            "value_score": 0.88,
            "usage_count": 5,
            "niche_reason": "Validates specific data format",
            "niche_value": "Critical for data integrity"
        }
    ],
    "total_niche_scripts": 2,
    "summary": "2 niche scripts with high value despite low usage"
}
```

### Example 4: Search with Value Ranking

```python
# Search - niche scripts included and ranked by value
result = await search_tool.execute({
    "query": "data processing",
    "include_niche": true
})

# Returns:
{
    "results": [
        {
            "script_name": "niche_data_processor",
            "relevance_score": 0.9,
            "value_score": 0.92,
            "combined_score": 0.906,
            "tags": ["Niche but valuable", "high-value"],
            "usage_count": 8,
            "note": "Low usage but high value - specialized tool"
        },
        {
            "script_name": "generic_data_processor",
            "relevance_score": 0.85,
            "value_score": 0.65,
            "combined_score": 0.78,
            "tags": ["popular"],
            "usage_count": 150
        }
    ]
}
# Note: niche_data_processor ranks higher due to value_score
```

### Example 5: Remove Protection

```python
# Try to remove niche script
result = await remove_tool.execute({
    "script_name": "niche_data_processor"
})

# Returns:
{
    "status": "error",
    "error": "NICHE_SCRIPT_PROTECTED",
    "message": "This script is marked as niche but valuable (value_score: 0.92). Use force=true to delete.",
    "value_metrics": {
        "value_score": 0.92,
        "usage_count": 8,
        "success_rate": 1.0,
        "niche_reason": "Specialized data processing for specific use case",
        "time_saved_hours": 50
    },
    "recommendation": "Consider keeping this script - it has high value despite low usage"
}

# Force removal (if really needed)
result = await remove_tool.execute({
    "script_name": "niche_data_processor",
    "force": true
})
# Proceeds with deletion after confirmation
```

---

## Testing Requirements

### Unit Tests

```python
# tests/tools/test_value.py

class TestValueTool:
    def test_calculate_value_score(self):
        """Test value score calculation"""
        
    def test_is_niche_script(self):
        """Test niche detection logic"""
        
    def test_mark_niche(self):
        """Test marking script as niche"""
        
    def test_get_niche_scripts(self):
        """Test retrieving niche scripts"""
        
    def test_value_score_components(self):
        """Test value score component breakdown"""
```

### Integration Tests

```python
# tests/integration/test_niche_tracking.py

class TestNicheTracking:
    def test_search_includes_niche(self):
        """Test search includes niche scripts"""
        
    def test_remove_protects_niche(self):
        """Test remove tool protects niche scripts"""
        
    def test_value_calculation_workflow(self):
        """Test end-to-end value calculation"""
```

---

## Success Metrics

1. **Niche Script Preservation:** % of niche scripts protected from deletion
2. **Value Score Accuracy:** Correlation between value_score and actual value
3. **Discovery Improvement:** % increase in niche script usage after value ranking
4. **User Satisfaction:** Feedback on niche script recommendations

---

## Future Enhancements

1. **ML-Based Value Prediction:** Predict value for new scripts
2. **Community Value Ratings:** Allow users to rate script value
3. **Value-Based Recommendations:** Recommend scripts based on value, not just popularity
4. **Niche Script Showcase:** Dedicated page for valuable niche scripts
5. **Value Analytics Dashboard:** Visualize value metrics across all scripts

---

## Dependencies

- **Script-Kiwi:** Core script registry and execution tracking
- **Supabase:** Database for value metrics

---

## Timeline

- **Week 1:** Database schema and value calculation logic
- **Week 2:** Enhance existing tools and create value tool
- **Week 3:** Automated calculation and testing

**Total:** 3 weeks

---

## Related Documents

- [Legacy Script Maintenance Plan](./01-legacy-script-maintenance.md)
- [Script Alternative Recommendations Plan](./02-script-alternatives.md)
- [Script Lifecycle Management Plan](./04-script-lifecycle.md)
