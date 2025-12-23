# Evaluation Prompt: Cross-Conversation Script Understanding Cache

## Context: The Problem

We have a **Script-Kiwi** system that allows LLM agents to search, load, and execute Python scripts via an MCP (Model Context Protocol) server. The current workflow is:

```
Agent Workflow (Current):
1. search("extract youtube transcript") → Finds script
2. load("extract_youtube_transcript") → Returns script details, inputs, dependencies
3. Agent understands how to use the script
4. run("extract_youtube_transcript", {...}) → Executes script
```

**The Problem**: In Conversation A, the agent does `search → load → understand`. That understanding stays in the conversation context. But when the user starts Conversation B (a new chat session), the agent has to repeat the entire `search → load → understand` cycle again, even though it already learned how to use the script. This is wasteful of:
- API tokens (repeated search/load calls)
- Time (agent has to re-learn)
- User experience (slower responses)

**The Goal**: Enable the agent to remember script understandings across conversations without requiring the user to manually re-inject context.

---

## System Architecture

### Script-Kiwi Overview

**Script-Kiwi** is an MCP server that provides 6 core tools:
- `search`: Find scripts by natural language query
- `load`: Get script details (metadata, inputs, dependencies, cost estimates)
- `run`: Execute scripts with parameters
- `publish`: Upload scripts to shared registry
- `help`: Get usage guidance
- `remove`: Delete scripts

### 3-Tier Storage System

Scripts are resolved in priority order:

```
1. PROJECT SPACE (highest priority)
   Location: <project>/.ai/scripts/
   Purpose: Project-specific scripts, local edits/overrides
   Requires: project_path parameter when MCP CWD ≠ project dir

2. USER SPACE
   Location: ~/.script-kiwi/scripts/
   Purpose: Downloaded scripts, shared libs, runtime environment
   Always accessible (uses $HOME)

3. REGISTRY (lowest priority)
   Location: Supabase (remote)
   Purpose: Shared scripts, versioning, discovery
   Requires: Network + Supabase credentials
```

### The `project_path` Parameter Constraint

**Critical Constraint**: MCP servers run as separate processes. Their current working directory (CWD) is typically:
- The user's home directory
- The MCP installation location
- Some system directory

**NOT** the project directory.

The `project_path` parameter tells the MCP where the project lives so it can find `.ai/scripts/`. However:
- MCP server **always** has access to `~/.script-kiwi/` (user space)
- MCP server **only** has access to project space (`.ai/scripts/`) when `project_path` is explicitly provided by the agent
- The agent must pass `project_path` in tool calls to access project-specific resources

### Current Load Tool Behavior

The `load` tool currently:
1. Resolves script location (Project → User → Registry)
2. Reads script file or queries registry
3. Extracts metadata (description, inputs, dependencies, cost)
4. Returns JSON with script specification
5. **Does NOT cache** the understanding

The agent then uses this information to understand how to call the script, but this understanding is lost when the conversation ends.

---

## Proposed Solutions

### Solution A: User Space Cache (Global Cache)

**Location**: `~/.script-kiwi/.cache/understandings.json`

**Access**: MCP can always read/write (no `project_path` needed)

**Scope**: Works across ALL projects

**Cache Key**: `script_name` (e.g., `"extract_youtube_transcript"`)

**Cache Value Structure**:
```json
{
  "script_name": {
    "understanding": {
      "script_metadata": {...},
      "inputs": {...},
      "key_params": [...],
      "example_usage": "...",
      "common_pitfalls": [...]
    },
    "last_loaded": "2024-01-15T10:30:00",
    "cache_ttl_seconds": 86400,
    "source": "user_cache"
  }
}
```

**Workflow**:
```
Conversation A:
  Agent: load("extract_youtube_transcript")
  → Cache miss → Full load → Saves to ~/.script-kiwi/.cache/

Conversation B:
  Agent: load("extract_youtube_transcript")
  → Cache hit → Returns cached understanding (FAST)
```

**Pros**:
- ✅ Always accessible (MCP can always write to user space)
- ✅ Works across all projects (global knowledge)
- ✅ No `project_path` needed
- ✅ Simple implementation

**Cons**:
- ❌ Cannot differentiate project-specific script customizations
- ❌ Same script might work differently in different projects
- ❌ Cache might become stale if script is updated in project space

---

### Solution B: Project Space Cache (Project-Specific Cache)

**Location**: `.ai/cache/understandings.json` (within project directory)

**Access**: MCP can write **only if** `project_path` is provided

**Scope**: Project-specific customizations

**Cache Key**: `project_hash:script_name` (e.g., `"abc12345:extract_youtube_transcript"`)

**Cache Value Structure**: Same as Solution A, but with `"project_specific": true`

**Workflow**:
```
Conversation A (with project_path):
  Agent: load("extract_youtube_transcript", project_path="/home/user/project")
  → Cache miss → Full load → Saves to .ai/cache/

Conversation B (with project_path):
  Agent: load("extract_youtube_transcript", project_path="/home/user/project")
  → Checks .ai/cache/ first → Cache hit → Returns cached understanding
```

**Pros**:
- ✅ Captures project-specific script customizations
- ✅ Project-specific understanding persists per project
- ✅ Can override global cache for project-specific needs

**Cons**:
- ❌ Requires `project_path` parameter (agent must provide it)
- ❌ MCP cannot access project cache without `project_path`
- ❌ More complex cache resolution logic

---

### Solution C: Hybrid Cache (User + Project)

**Location**: 
- User cache: `~/.script-kiwi/.cache/understandings.json`
- Project cache: `.ai/cache/understandings.json` (when `project_path` provided)

**Access Strategy**:
1. Check project cache first (if `project_path` provided and cache exists)
2. Fall back to user cache (global)
3. If both miss, do full load

**Cache Resolution Logic**:
```python
def get_cached_understanding(script_name, project_path=None):
    # Tier 1: Check project cache (if project_path provided)
    if project_path and project_cache.exists():
        cached = load_project_cache()
        entry = cached.get(f"{project_hash}:{script_name}")
        if entry and is_fresh(entry):
            return entry["understanding"]
    
    # Tier 2: Check user cache (global)
    cached = load_user_cache()
    entry = cached.get(script_name)
    if entry and is_fresh(entry):
        return entry["understanding"]
    
    # Tier 3: Cache miss
    return None
```

**Cache Write Strategy**:
```python
def cache_understanding(script_name, understanding, project_path=None, is_project_script=False):
    if is_project_script and project_path:
        # Script is project-specific → cache in project
        save_to_project_cache(script_name, understanding)
    else:
        # Script is global/shared → cache in user space
        save_to_user_cache(script_name, understanding)
```

**Pros**:
- ✅ Best of both worlds (global + project-specific)
- ✅ User cache always works (no `project_path` needed)
- ✅ Project cache captures customizations when available
- ✅ Graceful fallback (project → user → full load)

**Cons**:
- ❌ More complex implementation
- ❌ Requires cache invalidation logic for script updates
- ❌ Need to decide when to use project vs user cache

---

### Solution D: Kiwiclip Integration (Manual Override)

**Kiwiclip** is a user-controlled 2-bank, 12-slot clipboard system. The user can:
- Save text to slots via Plover steno chords
- Paste from slots into conversation
- Dynamically load/store slots for reuse

**Workflow**:
```
Conversation A:
  Agent: "extract_youtube_transcript extracts full transcript from YouTube videos..."
  User: [save chord] → Saves agent's explanation to Kiwiclip slot P1

Conversation B:
  User: [P1 chord] → Pastes understanding into conversation
  Agent: Sees understanding in context → Uses it directly
```

**Pros**:
- ✅ User has full control over what agent sees
- ✅ Can curate understanding library manually
- ✅ Works across all conversations (user-controlled)
- ✅ No MCP constraints (user-side tool)

**Cons**:
- ❌ Requires manual intervention (user must clip/paste)
- ❌ Not automatic (agent cannot access slots directly)
- ❌ Relies on user remembering to use slots

---

### Solution E: Hybrid Cache + Kiwiclip (Three-Layer System)

**Combines Solutions C and D**:

1. **Layer 1: User Cache (Automatic, Global)**
   - Location: `~/.script-kiwi/.cache/understandings.json`
   - Access: MCP can always read/write
   - Scope: Works across all projects
   - Benefit: Agent remembers scripts globally

2. **Layer 2: Project Cache (Automatic, Project-Specific)**
   - Location: `.ai/cache/understandings.json`
   - Access: MCP writes if `project_path` provided
   - Scope: Project-specific customizations
   - Benefit: Project-specific script understandings

3. **Layer 3: Kiwiclip (Manual, User Control)**
   - Location: `~/.local/share/kiwiclip/`
   - Access: User controls via Plover
   - Scope: User's curated understanding library
   - Benefit: User can inject understanding when needed

**Complete Flow**:
```
Conversation A:
  Agent: load("extract_youtube_transcript")
  → Cache miss → Full load → Saves to user cache
  → Returns understanding
  User: [save] → Clips to Kiwiclip slot P1

Conversation B:
  Option 1: Agent checks cache automatically
    Agent: load("extract_youtube_transcript")
    → Checks cache → Found in user cache! → Returns cached (FAST)
  
  Option 2: User injects via Kiwiclip
    User: [P1] → Pastes understanding
    Agent: Sees understanding in context → Uses it directly
```

**Pros**:
- ✅ Automatic caching (agent remembers)
- ✅ Project-specific caching (when needed)
- ✅ Manual control (Kiwiclip slots)
- ✅ Cross-conversation context (all three layers persist)
- ✅ Solves MCP constraint (user cache always accessible)
- ✅ Flexible (automatic + manual options)

**Cons**:
- ❌ Most complex implementation
- ❌ Requires cache invalidation logic
- ❌ Need to handle cache conflicts (project vs user)

---

## Implementation Details

### Cache Structure

```python
# script_kiwi/utils/script_cache.py

class ScriptCache:
    def __init__(self, project_path: str = None):
        # User cache (always accessible)
        self.user_cache_dir = Path.home() / ".script-kiwi" / ".cache"
        self.user_cache_file = self.user_cache_dir / "understandings.json"
        
        # Project cache (if project_path provided)
        self.project_path = Path(project_path) if project_path else None
        if self.project_path:
            self.project_cache_file = self.project_path / ".ai" / "cache" / "understandings.json"
    
    def get(self, script_name: str, check_project: bool = True) -> dict | None:
        """Get cached understanding. Checks: Project cache → User cache → None"""
        # Check project cache first (if exists)
        if check_project and self.project_cache_file and self.project_cache_file.exists():
            cached = self._load_from_file(self.project_cache_file)
            entry = cached.get(self._get_project_key(script_name))
            if entry and self._is_fresh(entry):
                return entry["understanding"]
        
        # Fall back to user cache
        cached = self._load_from_file(self.user_cache_file)
        entry = cached.get(script_name)
        if entry and self._is_fresh(entry):
            return entry["understanding"]
        
        return None
    
    def set(self, script_name: str, understanding: dict, project_specific: bool = False):
        """Cache understanding. Saves to project cache if project_specific=True, else user cache."""
        if project_specific and self.project_cache_file:
            cache_file = self.project_cache_file
            cache_key = self._get_project_key(script_name)
        else:
            cache_file = self.user_cache_file
            cache_key = script_name
        
        cache = self._load_from_file(cache_file)
        cache[cache_key] = {
            "understanding": understanding,
            "last_loaded": datetime.now().isoformat(),
            "cache_ttl_seconds": 86400,
            "script_name": script_name,
            "project_specific": project_specific
        }
        self._save_to_file(cache_file, cache)
```

### Integration into Load Tool

```python
# script_kiwi/tools/load.py

class LoadTool:
    async def execute(self, params: Dict[str, Any]) -> str:
        script_name = params.get("script_name")
        project_path = params.get("project_path")
        
        # Initialize cache
        cache = ScriptCache(project_path=project_path)
        
        # Check cache first
        cached = cache.get(script_name, check_project=True)
        if cached:
            return json.dumps({
                "script": cached["script_metadata"],
                "inputs": cached["inputs"],
                "understanding": cached["understanding"],
                "cached": True,
                "source": "cache"
            })
        
        # Cache miss: Do full load
        # ... existing load logic ...
        
        # Build understanding
        understanding = {
            "script_metadata": {...},
            "inputs": {...},
            "key_params": [...],
            "example_usage": "..."
        }
        
        # Save to cache
        is_project_script = resolved.get("location") == "project"
        cache.set(script_name, understanding, project_specific=is_project_script)
        
        return json.dumps(response)
```

---

## Evaluation Criteria

Please evaluate the proposed solutions based on:

1. **Feasibility**: Can it be implemented given MCP constraints?
2. **Effectiveness**: Does it solve the cross-conversation context problem?
3. **User Experience**: Is it transparent and easy to use?
4. **Maintainability**: Is the implementation clean and maintainable?
5. **Performance**: Does it reduce token usage and latency?
6. **Flexibility**: Does it handle edge cases (project-specific scripts, script updates, etc.)?

---

## Questions for Evaluation

1. **Which solution (A, B, C, D, or E) is best for this use case?** Why?

2. **How should cache invalidation work?** When a script is updated in project space, how do we invalidate the cache? Should we:
   - Check script file modification time?
   - Use version numbers?
   - Provide manual cache clear command?
   - Use TTL (time-to-live) only?

3. **What should be cached?** Should we cache:
   - Just the understanding (how to use the script)?
   - The full load response (metadata, inputs, dependencies)?
   - Both (understanding + raw data)?

4. **How should project-specific vs global scripts be handled?** If a script exists in both project space and user space, should:
   - Project cache override user cache?
   - User cache be shared across projects?
   - Both be checked (project first, then user)?

5. **What about script versioning?** If a script is updated in the registry, should we:
   - Invalidate cache automatically?
   - Check version numbers?
   - Let TTL handle it?

6. **Should Kiwiclip be integrated into the automatic flow?** Or should it remain purely manual (user-controlled)?

7. **What are the edge cases we should consider?**
   - Script deleted from project but cached
   - Script moved between tiers (project → user → registry)
   - Multiple projects using same script name
   - Cache corruption or invalid JSON

8. **Is there a better architecture we haven't considered?** Any alternative approaches?

---

## Additional Context

### Current Load Tool Response Structure

```json
{
  "script": {
    "name": "extract_youtube_transcript",
    "category": "extraction",
    "description": "Extracts full transcript from YouTube videos",
    "version": "1.0.0",
    "source": "registry"
  },
  "inputs": {
    "video_url": {
      "type": "string",
      "required": true,
      "description": "YouTube video URL"
    },
    "language": {
      "type": "string",
      "required": false,
      "default": "en"
    }
  },
  "dependencies": {
    "packages": ["youtube-transcript-api"],
    "env_vars": []
  },
  "cost_estimate": {
    "base_cost_usd": 0.0
  }
}
```

### What "Understanding" Means

The "understanding" that should be cached is a natural language explanation of:
- What the script does
- Key parameters and their purposes
- Common usage patterns
- Potential pitfalls or gotchas
- Example usage

This is what the agent generates internally after reading the script metadata, but it's not currently persisted.

---

## Your Task

Please provide a comprehensive evaluation that:

1. **Recommends the best solution** (A, B, C, D, or E) with justification
2. **Addresses all evaluation questions** listed above
3. **Identifies potential issues** we haven't considered
4. **Suggests improvements** to the proposed solutions
5. **Provides implementation recommendations** if different from what's proposed

Focus on:
- **Practicality**: What will work best in real-world usage?
- **Simplicity**: What's the simplest solution that solves the problem?
- **Robustness**: What handles edge cases gracefully?

Thank you for your evaluation!
