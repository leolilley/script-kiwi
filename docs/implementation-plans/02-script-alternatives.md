# Implementation Plan: Script Alternative Recommendations

**Priority:** High  
**Impact:** High - Reduces fragmentation confusion  
**Effort:** Low - Enhance existing load tool  
**Status:** Planning

---

## Overview

Enhance the `load` tool to suggest alternative scripts when loading a script. This addresses the video insight about framework fragmentation - "Cannot agree on how to increase a counter" (Remix v2/3/4 example) and helps developers choose the right tool for their context.

---

## Goals

1. **Suggest alternatives** when loading a script
2. **Compare alternatives** with pros/cons
3. **Recommend best fit** based on context
4. **Store comparisons** in Knowledge-Kiwi
5. **Track alternative usage** patterns

---

## Technical Specifications

### 1. Database Schema Changes

#### New Table: `script_alternatives`

```sql
CREATE TABLE script_alternatives (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    script_id uuid NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
    alternative_script_id uuid NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
    
    -- Comparison metadata
    comparison_type text CHECK (comparison_type IN ('version', 'alternative', 'replacement', 'similar')),
    pros text[],  -- Array of advantages
    cons text[],  -- Array of disadvantages
    migration_effort text CHECK (migration_effort IN ('low', 'medium', 'high')),
    use_case text,  -- When to use this alternative
    
    -- Usage tracking
    recommendation_count integer DEFAULT 0,
    migration_count integer DEFAULT 0,
    
    -- Metadata
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    created_by uuid REFERENCES users(id),
    
    UNIQUE(script_id, alternative_script_id)
);

-- Indexes
CREATE INDEX idx_script_alternatives_script_id ON script_alternatives(script_id);
CREATE INDEX idx_script_alternatives_alternative_id ON script_alternatives(alternative_script_id);
CREATE INDEX idx_script_alternatives_comparison_type ON script_alternatives(comparison_type);
```

#### New Table: `script_comparisons`

```sql
CREATE TABLE script_comparisons (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Comparison group
    comparison_name text NOT NULL,  -- e.g., "counter-increment-approaches"
    problem_description text,  -- What problem are we solving?
    
    -- Scripts being compared
    script_ids uuid[] NOT NULL,  -- Array of script IDs in comparison
    
    -- Comparison metadata
    comparison_type text CHECK (comparison_type IN ('version_comparison', 'approach_comparison', 'tool_comparison')),
    recommendation text,  -- Overall recommendation
    context_notes text,  -- When to use which approach
    
    -- Usage tracking
    view_count integer DEFAULT 0,
    recommendation_count integer DEFAULT 0,
    
    -- Metadata
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    created_by uuid REFERENCES users(id)
);

-- Index for searching comparisons
CREATE INDEX idx_script_comparisons_name ON script_comparisons(comparison_name);
CREATE INDEX idx_script_comparisons_type ON script_comparisons(comparison_type);
```

### 2. Enhance `load` Tool

**Location:** `script_kiwi/tools/load.py`

**New Response Field:**
```python
{
    "script": {...},  # Existing script data
    "alternatives": [  # NEW FIELD
        {
            "script_name": "alternative_script",
            "comparison_type": "alternative",
            "pros": ["faster", "better error handling"],
            "cons": ["newer API", "less tested"],
            "migration_effort": "low",
            "use_case": "Use when you need better error handling",
            "recommendation": "Consider if error handling is critical"
        }
    ],
    "recommendation": "Use alternative_script if you need better error handling"  # NEW FIELD
}
```

### 3. New MCP Tool: `compare`

**Location:** `script_kiwi/tools/compare.py`

**Tool Definition:**
```python
{
    "name": "compare",
    "description": "Compare scripts and manage alternatives",
    "inputSchema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["compare_scripts", "add_alternative", "get_comparison", 
                        "list_comparisons", "update_comparison"],
                "description": "Action to perform"
            },
            "script_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Script names to compare (for compare_scripts)"
            },
            "script_name": {
                "type": "string",
                "description": "Script name (for add_alternative, get_comparison)"
            },
            "alternative_script": {
                "type": "string",
                "description": "Alternative script name (for add_alternative)"
            },
            "pros": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Advantages of alternative"
            },
            "cons": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Disadvantages of alternative"
            },
            "migration_effort": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Migration effort"
            },
            "comparison_name": {
                "type": "string",
                "description": "Name of comparison (for get_comparison)"
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
   -- scripts/migrations/002_add_script_alternatives.sql
   CREATE TABLE script_alternatives (...);
   CREATE TABLE script_comparisons (...);
   ```

2. **Run migration**
   - Create tables
   - Create indexes
   - Update Supabase schema

### Phase 2: Enhance Load Tool (Week 1)

1. **Add alternative detection logic**
   ```python
   # script_kiwi/tools/load.py
   
   async def _find_alternatives(self, script_name: str, script_data: dict) -> list:
       """Find alternative scripts"""
       # 1. Query script_alternatives table
       # 2. Search for similar scripts (same category, similar description)
       # 3. Check Knowledge-Kiwi for documented alternatives
       # 4. Return alternatives with comparison data
   ```

2. **Add recommendation logic**
   ```python
   async def _recommend_alternative(self, script_name: str, 
                                    alternatives: list,
                                    context: dict = None) -> dict:
       """Recommend best alternative based on context"""
       # 1. Analyze script metadata
       # 2. Compare with alternatives
       # 3. Consider context (project type, requirements)
       # 4. Return recommendation
   ```

3. **Update load response**
   ```python
   # Add alternatives and recommendation to response
   response["alternatives"] = await self._find_alternatives(script_name, script)
   response["recommendation"] = await self._recommend_alternative(
       script_name, response["alternatives"], context
   )
   ```

### Phase 3: Compare Tool Implementation (Week 2)

1. **Create compare tool**
   ```python
   # script_kiwi/tools/compare.py
   
   class CompareTool:
       async def compare_scripts(self, script_names: list) -> dict:
           """Compare multiple scripts side-by-side"""
           
       async def add_alternative(self, script_name: str, 
                                alternative_script: str,
                                pros: list, cons: list,
                                migration_effort: str) -> dict:
           """Add alternative relationship"""
           
       async def get_comparison(self, comparison_name: str) -> dict:
           """Get stored comparison"""
   ```

2. **Add to MCP server**
   ```python
   # script_kiwi/server.py
   from .tools.compare import CompareTool
   
   tools.append(Tool(
       name="compare",
       description="Compare scripts and manage alternatives",
       inputSchema={...}
   ))
   ```

### Phase 4: Knowledge-Kiwi Integration (Week 2)

1. **Store comparisons in Knowledge-Kiwi**
   ```python
   # When comparison is created, store in Knowledge-Kiwi
   knowledge_kiwi.manage({
       "action": "create",
       "zettel_id": f"comparison-{comparison_name}",
       "entry_type": "pattern",
       "category": "patterns/comparisons",
       "content": {
           "problem": problem_description,
           "solutions": [
               {"name": script1, "pros": [...], "cons": [...]},
               {"name": script2, "pros": [...], "cons": [...]}
           ],
           "recommendation": recommendation
       }
   })
   ```

2. **Link related comparisons**
   ```python
   # Link comparisons to scripts
   knowledge_kiwi.link({
       "action": "link",
       "from_zettel_id": f"script-{script_name}",
       "to_zettel_id": f"comparison-{comparison_name}",
       "relationship_type": "related"
   })
   ```

### Phase 5: Context-Aware Recommendations (Week 3)

1. **Add context analysis**
   ```python
   async def _analyze_context(self, project_path: str = None) -> dict:
       """Analyze project context for recommendations"""
       # 1. Check project type (from .ai/ structure)
       # 2. Check existing scripts (what's already used)
       # 3. Check requirements (performance, error handling, etc.)
       # 4. Return context dict
   ```

2. **Enhance recommendation logic**
   ```python
   async def _recommend_with_context(self, script_name: str,
                                    alternatives: list,
                                    context: dict) -> dict:
       """Recommend based on context"""
       # 1. Score alternatives based on context fit
       # 2. Consider project requirements
       # 3. Check compatibility with existing scripts
       # 4. Return context-aware recommendation
   ```

### Phase 6: Testing & Documentation (Week 3)

1. **Unit tests**
   ```python
   # tests/tools/test_compare.py
   - test_find_alternatives
   - test_compare_scripts
   - test_add_alternative
   - test_context_aware_recommendation
   ```

2. **Integration tests**
   - End-to-end alternative workflow
   - Knowledge-Kiwi integration
   - Context-aware recommendations

3. **Documentation**
   - Update README
   - Usage examples
   - Comparison best practices

---

## Usage Examples

### Example 1: Load Script with Alternatives

```python
# Load script - automatically gets alternatives
result = await load_tool.execute({
    "script_name": "extract_youtube_transcript",
    "sections": ["all"]
})

# Response includes:
{
    "script": {
        "name": "extract_youtube_transcript",
        "description": "Extracts transcript from YouTube videos",
        # ... existing fields
    },
    "alternatives": [
        {
            "script_name": "extract_youtube_transcript_v2",
            "comparison_type": "version",
            "pros": [
                "Better error handling",
                "Supports more languages",
                "Faster execution"
            ],
            "cons": [
                "Newer API (breaking changes)",
                "Less tested in production"
            ],
            "migration_effort": "medium",
            "use_case": "Use v2 if you need better error handling or more languages"
        },
        {
            "script_name": "extract_video_transcript_generic",
            "comparison_type": "alternative",
            "pros": [
                "Works with multiple platforms (YouTube, Vimeo, etc.)",
                "More flexible"
            ],
            "cons": [
                "More complex API",
                "Slower for YouTube-specific use"
            ],
            "migration_effort": "high",
            "use_case": "Use if you need multi-platform support"
        }
    ],
    "recommendation": "Consider extract_youtube_transcript_v2 if you need better error handling. The migration effort is medium and the benefits are significant."
}
```

### Example 2: Compare Scripts Explicitly

```python
# Compare multiple scripts
result = await compare_tool.execute({
    "action": "compare_scripts",
    "script_names": [
        "extract_youtube_transcript",
        "extract_youtube_transcript_v2",
        "extract_video_transcript_generic"
    ]
})

# Returns:
{
    "status": "success",
    "comparison": {
        "problem": "Extract transcript from video platforms",
        "scripts": [
            {
                "name": "extract_youtube_transcript",
                "pros": ["Simple API", "Well tested", "Fast"],
                "cons": ["YouTube only", "Limited error handling"],
                "best_for": "Simple YouTube transcript extraction"
            },
            {
                "name": "extract_youtube_transcript_v2",
                "pros": ["Better error handling", "More languages", "Faster"],
                "cons": ["Breaking changes", "Less tested"],
                "best_for": "Production YouTube extraction with error handling"
            },
            {
                "name": "extract_video_transcript_generic",
                "pros": ["Multi-platform", "Flexible"],
                "cons": ["Complex API", "Slower"],
                "best_for": "Multi-platform video transcript extraction"
            }
        ],
        "recommendation": "Use extract_youtube_transcript_v2 for new projects, extract_youtube_transcript for legacy projects, extract_video_transcript_generic for multi-platform needs"
    }
}
```

### Example 3: Add Alternative Relationship

```python
# Add alternative relationship
result = await compare_tool.execute({
    "action": "add_alternative",
    "script_name": "extract_youtube_transcript",
    "alternative_script": "extract_youtube_transcript_v2",
    "pros": [
        "Better error handling",
        "More language support",
        "Faster execution"
    ],
    "cons": [
        "Breaking API changes",
        "Less production testing"
    ],
    "migration_effort": "medium"
})

# Returns:
{
    "status": "success",
    "alternative_added": {
        "script_name": "extract_youtube_transcript",
        "alternative_script": "extract_youtube_transcript_v2",
        "comparison_type": "version",
        "stored_in": ["database", "knowledge_kiwi"]
    }
}
```

### Example 4: Context-Aware Recommendation

```python
# Load with context
result = await load_tool.execute({
    "script_name": "extract_youtube_transcript",
    "project_path": "/home/user/my-project",
    "context": {
        "project_type": "production",
        "requirements": ["error_handling", "performance"],
        "existing_scripts": ["script_a", "script_b"]
    }
})

# Recommendation considers context:
{
    "recommendation": "Use extract_youtube_transcript_v2. Your project requires error handling and performance, and v2 provides both. Migration effort is medium but worth it for production use."
}
```

---

## Testing Requirements

### Unit Tests

```python
# tests/tools/test_compare.py

class TestCompareTool:
    def test_find_alternatives(self):
        """Test finding alternatives for a script"""
        
    def test_compare_scripts(self):
        """Test comparing multiple scripts"""
        
    def test_add_alternative(self):
        """Test adding alternative relationship"""
        
    def test_get_comparison(self):
        """Test retrieving stored comparison"""
        
    def test_context_aware_recommendation(self):
        """Test context-aware recommendations"""
```

### Integration Tests

```python
# tests/integration/test_alternatives_workflow.py

class TestAlternativesWorkflow:
    def test_load_with_alternatives(self):
        """Test load tool returning alternatives"""
        
    def test_alternatives_with_knowledge_kiwi(self):
        """Test Knowledge-Kiwi integration"""
        
    def test_comparison_storage(self):
        """Test storing comparisons in Knowledge-Kiwi"""
```

---

## Success Metrics

1. **Alternative Discovery:** % of scripts with documented alternatives
2. **Recommendation Accuracy:** % of users who follow recommendations
3. **Migration Success:** % of successful migrations to alternatives
4. **Comparison Usage:** Number of comparisons viewed/used

---

## Future Enhancements

1. **Auto-detect Alternatives:** Use ML/similarity to find alternatives automatically
2. **Community Comparisons:** Allow users to contribute comparison data
3. **Version Comparison UI:** Visual diff between script versions
4. **Migration Assistant:** Automated migration tools based on comparisons
5. **Alternative Analytics:** Track which alternatives are most popular

---

## Dependencies

- **Script-Kiwi:** Core script registry
- **Knowledge-Kiwi:** Storage for comparisons (optional but recommended)
- **Supabase:** Database for alternatives and comparisons

---

## Timeline

- **Week 1:** Database schema and enhance load tool
- **Week 2:** Compare tool implementation and Knowledge-Kiwi integration
- **Week 3:** Context-aware recommendations and testing

**Total:** 3 weeks

---

## Related Documents

- [Legacy Script Maintenance Plan](./01-legacy-script-maintenance.md)
- [Script Lifecycle Management Plan](./04-script-lifecycle.md)
- [Knowledge-Kiwi Integration Guide](../guides/Knowledge-Kiwi-Integration.md)
