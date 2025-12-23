# Script Kiwi Migration Plan

Purpose: move execution code from this repo into the Script Kiwi project with a clean registry + MCP surface, mirroring Context Kiwi's DB structure and Campaign Kiwi's tool patterns.

## Outcomes
- Script Kiwi Supabase live with `scripts`, `script_versions`, `executions`, `lockfiles`, `script_feedback`.
- Core tools (`search`, `load`, `run`, `publish`, `help`) callable; search → load → run flows green; publish for semver releases.
- Execution modules relocated and namespaced; existing functionality preserved (scraping, enrichment, extraction, validation, maintenance).
- Cost tracking, checkpointing, proxy/cookie flows intact.
- Clear separation: agent/LLM orchestrates; Script Kiwi MCP executes deterministically (no LLM-side code execution).

## Inputs
- Current modules: `src/knowledge_kiwi/{scraping,enrichment,extraction,validation,maintenance,lib}`.
- v2 Implementation Guide Part 4 (Script Kiwi MCP) and schema section 2.1.
- Context Kiwi directive patterns and lockfile semantics.
- Campaign Kiwi tool behavior (for parity tests).

## Target Repository Layout (script-kiwi)
- `script_kiwi/execution/{scraping,enrichment,extraction,validation,maintenance,utility}`
- `script_kiwi/api` (Supabase + external APIs)
- `script_kiwi/tools` (6 core tools: search, load, run, publish, help, remove)
- `script_kiwi/directives` (cached from Context Kiwi)
- `pyproject.toml` (dependencies, package config)
- `.venv/` (virtual environment)
- `.script-kiwi/scripts/...` (user space), `.ai/scripts` (project space)
- Tests: `tests/{execution,api,tools}`

## Workstreams
1) **Schema & infra**: create Script Kiwi Supabase (copy Context Kiwi schema); set env contracts.
2) **Code move**: relocate execution modules; adjust imports to `script_kiwi` namespace; keep deterministic behavior.
   - Create migration script to automate import path updates
   - Verify all scripts implement `execute(params: dict) -> dict` interface
   - See Implementation-Edge-Cases-and-Verification.md for migration steps and breaking changes
3) **Registry + tools**: implement core tools backed by Supabase; align with Campaign Kiwi semantics.
4) **Packaging**: `pyproject.toml` (dependencies), `.venv/` virtual environment, env.example, Makefile/tasks; release process.
5) **Testing**: unit + integration (search→load→execute); cost/proxy/cookie coverage.
6) **Cutover**: lockfile versions, directive updates, deprecation notices in this repo.

## Storage Tier Resolution & Script Loading Mechanism

Script Kiwi resolves scripts in this order (same as Context Kiwi):
1. **Project space**: `.ai/scripts/` (project-specific, one-off tasks, highest priority)
2. **User space**: `~/.script-kiwi/scripts/` (personal script library, downloaded from registry)
3. **Registry**: Supabase `scripts` table (production-ready, tested, remote source)

### Script Lifecycle Flow

**Creating a new script:**
1. Create script in `.ai/scripts/` (project-specific) or `~/.script-kiwi/scripts/` (personal)
2. Use `publish` tool to upload to Supabase registry with semver version
3. Script now available in remote registry for others

**Loading a script:**
1. `load` tool checks locations in priority order: Project → User → Registry
2. If found in Project or User space, use local version
3. If only in Registry, `load` can optionally download to User space (`~/.script-kiwi/scripts/`) for faster future access
4. Returns script spec + code for execution

**Running a script:**
1. `run` tool uses same resolution order (Project → User → Registry)
2. Executes Python module directly (no LLM code generation)
3. Logs execution to Supabase `executions` table
4. Script code can come from any tier (local takes precedence)

**Implementation:** 
- `load` tool: Resolves script location, optionally downloads from registry to user space
- `run` tool: Resolves script location, imports and executes Python module
- `publish` tool: Uploads local script to Supabase registry with versioning

**See `Script-Loading-Mechanism.md` for complete workflow examples and implementation details.**

## Database Schema Requirements

### Required SQL Functions (from Implementation Guide §2.1)
- `search_scripts(search_query, search_category, limit_count)` - Full-text search with tsvector
- `get_latest_version(script_name_param)` - Get latest script version
- `update_script_quality()` - Trigger to update quality_score from feedback
- `update_script_metrics()` - Trigger to update success_rate, avg_execution_time from executions

### Required Indexes
- `idx_scripts_tsv` - GIN index on tsvector for full-text search
- `idx_scripts_tags` - GIN index on tags array
- `idx_script_versions_latest` - Partial index for latest versions
- `idx_executions_script_name` - For execution history queries

### Required RLS Policies
- Public scripts viewable by all (is_official = true)
- Users can view/manage their own scripts
- Executions private to user
- Lockfiles private to user

## Environment Variables

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=your-service-role-key
APIFY_API_TOKEN=your-apify-token
ANYMAILFINDER_API_KEY=your-anymailfinder-key
LEAD_MAGIC_API_KEY=your-leadmagic-key
OPENAI_API_KEY=your-openai-key  # Optional
SERVER_NAME=script-kiwi
LOG_LEVEL=INFO
```

**Note:** Script Kiwi does NOT connect to Context Kiwi's database. Directives are loaded via Context Kiwi MCP server, not direct database access.

**Supabase Client:**
- Use `supabase-py` with connection pooling (automatic via httpx)
- Retry logic via vendored `api.py` utilities (`@with_retry` decorator)
- Anon key for read operations, service role key for admin operations
- See Implementation-Clarifications.md for exact patterns

## Migration Steps
1. Stand up Script Kiwi Supabase (schema from v2 guide §2.1, including functions, indexes, triggers, RLS).
2. Scaffold repo structure (v2 guide §3, Script Kiwi section):
   ```bash
   mkdir -p script_kiwi/{execution/{scraping,enrichment,extraction,validation,maintenance,utility},api,tools,directives,config,utils}
   mkdir -p tests/{execution,api,tools}
   mkdir -p docs/{guides,examples}
   mkdir -p .ai/{directives/custom,scripts,patterns}
   mkdir -p .script-kiwi/scripts/{scraping,enrichment,extraction,validation,maintenance,utility}
   
   # Create virtual environment
   python -m venv .venv
   source .venv/bin/activate
   
   # Create pyproject.toml with dependencies
   # Install in editable mode
   pip install -e .
   ```
3. Copy execution modules; refactor imports:
   - Replace `knowledge_kiwi.lib.*` with `script_kiwi.utils.*` (vendored utilities).
   - Vendor shared utilities: `api.py`, `preflight.py`, `checkpoint.py`, `analytics.py`, `cost_tracker.py`, `proxy_pool.py`, `cookie_manager.py` → `script_kiwi/utils/`
   - Keep proxy/cookie/cost/checkpoint patterns intact.
   - Adapt `analytics.py` to dual logging: user space (`~/.script-kiwi/.runs/history.jsonl`) and Supabase `executions` table
4. Create script registry records per module (name, category, module_path, required_env_vars).
5. Implement core tools against registry:
   - `search` (full-text/tsvector search of scripts)
   - `load` (code/spec retrieval from Supabase, optional download to user space)
   - `run` (parameter validation, execute Python module via `importlib`, log to `executions` with cost_usd)
   - `publish` (upload script version with semver to Supabase)
   - `help` (usage + examples)
   - **Error handling**: Standardized JSON error responses with error codes (see Implementation-Clarifications.md)
   - **Script execution**: Dynamic import via `importlib.util`, calls `execute()` or `main()` function
6. Add lockfile support (pinning script versions per project hash):
   - Format: JSON with `project_hash`, `scripts` object mapping names to versions
   - Location: `.ai/scripts.lock.json` (project) or `~/.script-kiwi/scripts.lock.json` (user)
   - Behavior: `load` and `run` respect lockfile versions (load specific version from registry)
   - See Implementation-Clarifications.md for exact format
7. Tests:
   - **Coverage target**: 80% overall (90% unit, 70% integration)
   - **Unit tests**: API client, registry queries, parameter validation, script execution, cost calculation
   - **Integration tests**: search → load → run flow, publish workflow, lockfile behavior
   - **Mocking**: Mock Supabase client, external APIs (Apify, Anymailfinder), file system
   - **Test data**: Use test Supabase projects, `pytest.fixture` for setup/teardown
   - **Parity**: Compare outputs with current repo for golden samples
   - See Implementation-Clarifications.md for detailed testing strategy
8. Documentation: README, MCP config example, env.example, tool docs.
9. Deprecate in this repo:
   - Mark execution modules as moved.
   - Update directives to use Script Kiwi MCP.
   - Provide migration notes for users.

## Dependencies
- **Context Kiwi** for directives and lockfiles:
  - Directives define workflows that call Script Kiwi tools (`search`, `load`, `run`)
  - Script Kiwi loads directives from Context Kiwi Supabase, caches in `.ai/directives/custom/`
  - Directives contain step-by-step instructions referencing Script Kiwi tools
  - See `Directive-Orchestration-Pattern.md` for how directives orchestrate Script Kiwi
- Campaign Kiwi for interface parity checks and data handoff (direct Supabase writes or CSV export).
- External APIs: Supabase, Apify, Anymailfinder, Lead Magic, OpenAI (if embeddings).
- Python packages: Scripts declare dependencies in `dependencies` JSONB field; managed via `pyproject.toml`.

## Shared Utilities (Vendored)
- `api.py`, `preflight.py`, `checkpoint.py`, `analytics.py`, `cost_tracker.py`, `proxy_pool.py`, `cookie_manager.py`
- Copied to `script_kiwi/utils/` with namespace change: `knowledge_kiwi.lib.*` → `script_kiwi.utils.*`
- No shared package dependency (Script Kiwi is self-contained)

## Risks & Mitigations
- Import drift after move → add shim layer or clear refactors; run integration tests.
- Registry integrity → enforce semver, content hash, and lockfile validation.
- Cost tracking gaps → ensure `analytics.log_execution` equivalent in Script Kiwi (dual logging: user space + Supabase).
- Tool discovery mismatch → mirror Campaign Kiwi tool interaction pattern (search→load→run); add contract tests.

## Acceptance Tests (high level)
- `search("google maps leads")` returns expected script.
- `load` returns module path + parameters.
- `run` executes sample script with real env keys; writes `executions` row; emits cost metrics.
- `publish` uploads script version to Supabase with semver validation.
- Directive flow: Context Kiwi directive invokes Script Kiwi tools and succeeds end-to-end.
