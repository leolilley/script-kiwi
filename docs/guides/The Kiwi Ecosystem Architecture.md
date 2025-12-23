# The Kiwi Ecosystem Architecture

Let me crystallize this entire system architecture so you can build it systematically.

---

## The Four Pillars

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE KIWI ECOSYSTEM                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Context Kiwi │  │ Script Kiwi  │  │Campaign Kiwi │         │
│  │              │  │              │  │              │         │
│  │ Directive    │  │ Script       │  │ Email        │         │
│  │ Management   │  │ Execution    │  │ Infrastructure│        │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                  │                  │
│         └─────────────────┼──────────────────┘                  │
│                           │                                     │
│                  ┌────────▼────────┐                           │
│                  │ Knowledge Kiwi  │                           │
│                  │                 │                           │
│                  │ Knowledge Base  │                           │
│                  │ (Zettelkasten)  │                           │
│                  └─────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Context Kiwi (The Orchestrator)

**Purpose:** Directive management system - the "brain" that tells agents HOW to work

**Database:** `context-kiwi` Supabase project
```sql
- users
- directives           # Workflow definitions
- directive_versions   # Versioned content
- runs                 # Execution history
- lockfiles            # Version pinning
```

**Storage Tiers:**
```
Remote (Supabase):     Directive registry (shareable, versioned)
User (~/.context-kiwi/): Cached directives (fast access)
Project (.ai/):        Project-specific directives (local customization)
```

**MCP Interface:** Simple CRUD tools
```
- create_directive
- get_directive
- update_directive
- delete_directive
- list_directives
- pin_version (lockfile)
```

**Key Insight:** Context Kiwi tells the agent WHAT to do, not HOW to do it.

---

## 2. Script Kiwi (The Executor)

**Purpose:** Script execution system - the "hands" that DO the work

**Database:** `script-kiwi` Supabase project (SAME structure as Context Kiwi!)
```sql
- users
- scripts              # Executable code (like directives but for scripts)
- script_versions      # Versioned code
- executions           # Execution history (like runs)
- lockfiles            # Script version pinning
```

**Storage Tiers:**
```
Remote (Supabase):     Script registry (production-ready, tested)
User (~/.script-kiwi/): Personal script library (your custom tools)
Project (.ai/scripts/): Project-specific scripts (one-off tasks)
```

**MCP Interface:** Like Campaign Kiwi (5 core tools)
```
- tool_search          # "Find script for scraping Google Maps"
- load_tool            # Get script spec + directive
- execute              # Run with validation
- help                 # Workflow guidance
```

**Execution Layer:**
```python
script_kiwi/
├── src/
│   ├── execution/           # Core execution modules (deterministic)
│   │   ├── scraping/
│   │   │   ├── google_maps.py
│   │   │   ├── linkedin.py
│   │   │   └── apify_generic.py
│   │   ├── enrichment/
│   │   │   ├── email_waterfall.py
│   │   │   ├── email_validation.py
│   │   │   └── contact_finder.py
│   │   ├── extraction/
│   │   │   ├── youtube.py
│   │   │   ├── website.py
│   │   │   └── github.py
│   │   └── validation/
│   │       ├── email.py
│   │       ├── lead_quality.py
│   │       └── data_completeness.py
│   ├── api/                 # Supabase + external APIs
│   ├── tools/               # MCP tools (5 core tools)
│   └── directives/          # XML directives (cached from Context Kiwi)
```

**Key Insight:** Script Kiwi executes deterministic code. No LLM generation. Just reliable Python.

---

## 3. Knowledge Kiwi (The Memory)

**Purpose:** Knowledge management - the "memory" that stores learnings

**Database:** `knowledge-kiwi` Supabase project
```sql
- knowledge_entries         # Your Zettelkasten notes
- knowledge_relationships   # Links between notes
- knowledge_collections     # Grouped notes
- knowledge_queries         # Search history
```

**Storage Tiers:**
```
Remote (Supabase):       Vector embeddings + relationships (searchable)
Local (knowledge/base/): Plain text Zettelkasten (version controlled)
```

**MCP Interface:** 5 core tools with explicit source selection
```
- search (source: "local" | "registry" | ["local", "registry"])
- get (source: "local" | "registry" | ["local", "registry"])
- manage (action: "create" | "update" | "delete" | "publish")
- link (action: "link" | "create_collection" | "get_relationships")
- help
```

**File Structure:**
```
knowledge/
├── base/                    # Plain text notes (Git tracked)
│   ├── apis/
│   │   ├── 001-apify-basics.md
│   │   └── 002-google-maps-api.md
│   ├── patterns/
│   │   ├── 101-waterfall-enrichment.md
│   │   └── 102-checkpoint-pattern.md
│   ├── concepts/
│   │   └── 201-zettelkasten-method.md
│   └── learnings/
│       └── 301-email-deliverability.md
├── embeddings/              # Generated embeddings (gitignored)
└── index.json               # Fast lookup index
```

**Key Insight:** Knowledge Kiwi stores INFORMATION, not code. It's your second brain.

---

## 4. Campaign Kiwi (The Specialist)

**Purpose:** Email infrastructure - specialized tool for one domain

**Database:** `campaign-kiwi` Supabase project
```sql
- campaigns
- leads
- emails
- templates
- ... (50+ tables)
```

**MCP Interface:** Entity-based (like Script Kiwi)
```
- tool_search
- load_tool
- execute
- help
```

**Key Insight:** Campaign Kiwi is a COMPLETE PRODUCT. Script Kiwi is a PLATFORM.

---

## How They Work Together

### Example: "Find 500 SaaS founders, research them, send personalized emails"

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: Planning (Context Kiwi)                          │
└─────────────────────────────────────────────────────────────┘

Agent → Context Kiwi MCP:
  get_directive("outbound_campaign_workflow")

Context Kiwi returns:
  <directive>
    <step>1. Scrape leads using Script Kiwi</step>
    <step>2. Enrich emails using Script Kiwi</step>
    <step>3. Research companies using web_search</step>
    <step>4. Create campaign using Campaign Kiwi</step>
    <step>5. Monitor replies using Campaign Kiwi</step>
  </directive>

┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: Lead Collection (Script Kiwi)                     │
└─────────────────────────────────────────────────────────────┘

Agent → Script Kiwi MCP:
  tool_search("scrape SaaS companies Austin")

Script Kiwi:
  → Returns: "google_maps_leads"

Agent → Script Kiwi MCP:
  load_tool("google_maps_leads")

Script Kiwi:
  → Returns: Directive with inputs, costs, examples

Agent → Script Kiwi MCP:
  execute("google_maps_leads", {
    search_term: "SaaS company",
    location: "Austin, TX",
    count: 500
  })

Script Kiwi:
  → Runs execution/scraping/google_maps.py
  → Returns: 500 leads with company info
  → Logs to user space (~/.script-kiwi/.runs/history.jsonl) and Supabase executions table

┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: Email Enrichment (Script Kiwi)                    │
└─────────────────────────────────────────────────────────────┘

Agent → Script Kiwi MCP:
  execute("email_waterfall_enrichment", {
    lead_ids: [...]
  })

Script Kiwi:
  → Runs execution/enrichment/email_waterfall.py
  → Returns: 450/500 leads with emails (90% success)

┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: Research (Knowledge Kiwi + Anthropic API)         │
└─────────────────────────────────────────────────────────────┘

Agent → Knowledge Kiwi MCP:
  search({query: "SaaS company pain points", source: ["local", "registry"]})

Knowledge Kiwi:
  → Returns relevant notes from your Zettelkasten

For each company:
  Agent → Anthropic API (web_search):
    Search for company info, recent news, pain points
  
  Agent → Knowledge Kiwi MCP:
    manage({
      action: "create",
      zettel_id: "company-{id}",
      content: research findings,
      entry_type: "learning",
      location: "project"
    })

┌─────────────────────────────────────────────────────────────┐
│ PHASE 5: Campaign Creation (Campaign Kiwi)                 │
└─────────────────────────────────────────────────────────────┘

Agent → Campaign Kiwi MCP:
  execute("create_entity", {
    entity_type: "campaign",
    name: "SaaS Founders Austin",
    leads: [enriched leads from Script Kiwi]
  })

Agent → Campaign Kiwi MCP:
  execute("generate_emails", {
    campaign_id: "...",
    context: [research from Knowledge Kiwi]
  })

Agent → Campaign Kiwi MCP:
  execute("schedule_emails", {
    rate: "10_per_hour"
  })

┌─────────────────────────────────────────────────────────────┐
│ PHASE 6: Monitoring (Campaign Kiwi + Knowledge Kiwi)       │
└─────────────────────────────────────────────────────────────┘

Agent → Campaign Kiwi MCP:
  execute("check_replies")

Campaign Kiwi:
  → Returns: 12 replies, 8 positive, 4 questions

Agent → Knowledge Kiwi MCP:
  manage({
    action: "create",
    zettel_id: "learning-saas-austin-response",
    title: "SaaS Founders Austin Response Pattern",
    content: "SaaS founders in Austin respond well to X approach",
    entry_type: "learning",
    location: "project"
  })

Agent → Context Kiwi MCP:
  update_directive("outbound_campaign_workflow", {
    improvement: "Add step for researching local tech news"
  })
```

---

## Structural Alignment

### Context Kiwi = Script Kiwi (Database Structure)

Both use IDENTICAL table structure:

| Context Kiwi | Script Kiwi | Purpose |
|--------------|-------------|---------|
| `directives` | `scripts` | Registry of items |
| `directive_versions` | `script_versions` | Version control |
| `runs` | `executions` | Execution history |
| `lockfiles` | `lockfiles` | Version pinning |

**Why?** Same problem domain: managing versioned, executable artifacts.

### Campaign Kiwi = Script Kiwi (MCP Interface)

Both use 5 core tools pattern:

| Tool | Purpose |
|------|---------|
| `tool_search` | Find by intent |
| `load_tool` | Get details |
| `execute` | Run with validation |
| `help` | Workflow guidance |

**Why?** Both need dynamic discovery (not static tool lists).

### Knowledge Kiwi = Unique (Content Not Code)

Different because it stores INFORMATION, not EXECUTION.

Simple CRUD tools for knowledge management.

---

## File System Structure

```
~/projects/
├── context-kiwi/              # Directive management
│   ├── src/
│   │   └── context-kiwi-mcp/
│   ├── .context-kiwi/         # User space (cached directives)
│   └── .ai/directives/        # Project directives
│
├── script-kiwi/               # Script execution
│   ├── src/
│   │   ├── script_kiwi/   # MCP server
│   │   │   ├── execution/     # Core scripts (deterministic)
│   │   │   ├── api/           # Supabase + external
│   │   │   ├── tools/         # 5 core tools
│   │   │   └── directives/    # Cached from Context Kiwi
│   ├── .script-kiwi/          # User space (personal scripts)
│   │   └── scripts/
│   └── .ai/scripts/           # Project scripts
│
├── knowledge-kiwi/            # Knowledge base
│   ├── src/
│   │   └── knowledge-kiwi-mcp/  # MCP server
│   ├── knowledge/base/        # Plain text Zettelkasten
│   └── .knowledge-kiwi/       # User space
│       └── cache/
│
└── campaign-kiwi/             # Email infrastructure
    ├── campaign-kiwi-mcp/     # MCP server
    ├── campaign-kiwi-serverless/  # AWS Lambda
    └── campaign-kiwi-dashboard/   # Monitoring
```

---

## Supabase Projects

```
1. context-kiwi (supabase.com/project/mrecfyfjpwzrzxoiooew)
   - directives, directive_versions, runs, lockfiles

2. script-kiwi (supabase.com/project/NEW)
   - scripts, script_versions, executions, lockfiles
   - SAME STRUCTURE as context-kiwi

3. knowledge-kiwi (supabase.com/project/NEW)
   - knowledge_entries, knowledge_relationships, collections
   - DIFFERENT STRUCTURE (content not code)

4. campaign-kiwi (supabase.com/project/EXISTING)
   - campaigns, leads, emails, etc.
   - KEEP AS-IS (working product)
```

---

## Agent Context Loading

The agent in Cursor loads context from multiple sources:

```
Agent starts:
  1. Load system prompt (Claude's base instructions)
  2. Connect to MCPs:
     - Context Kiwi MCP (directive management)
     - Script Kiwi MCP (script execution)
     - Knowledge Kiwi MCP (knowledge base)
     - Campaign Kiwi MCP (email infrastructure)
  3. Load initial directives:
     - get_directive("agent_initialization")
     - get_directive("workflow_patterns")

User: "Find 500 SaaS founders and send them emails"

Agent:
  1. Context Kiwi: get_directive("outbound_campaign_workflow")
  2. Script Kiwi: tool_search("scrape leads")
  3. Script Kiwi: load_tool("google_maps_leads")
  4. Knowledge Kiwi: search({query: "lead generation best practices", source: ["local", "registry"]})
  5. Script Kiwi: execute("google_maps_leads", params)
  6. ... (continue workflow)
```

---

## Implementation Priority

### Phase 1: Foundation (Week 1)
1. **Set up Script Kiwi Supabase** (copy Context Kiwi schema, rename tables)
2. **Set up Knowledge Kiwi Supabase** (new schema for knowledge)
3. **Create MCP skeletons** (copy Campaign Kiwi's tool pattern, use 5 tools)

### Phase 2: Script Kiwi (Week 2)
4. **Move existing scripts** to `execution/` modules
5. **Create script registry** (upload to Supabase)
6. **Test end-to-end**: search → load → execute

### Phase 3: Knowledge Kiwi (Week 3)
7. **Keep local Zettelkasten** as-is
8. **Build sync script** (files → Supabase)
9. **Test semantic search** (with pgvector)

### Phase 4: Integration (Week 4)
10. **Connect all MCPs** to Cursor
11. **Create meta-directive** in Context Kiwi: "outbound_campaign_workflow"
12. **Test full flow**: Plan → Script → Knowledge → Campaign

---

## The Mental Model

```
Context Kiwi:  "Here's HOW to approach this workflow"
Script Kiwi:   "Here's the TOOLS to execute each step"
Knowledge Kiwi: "Here's WHAT I know about this domain"
Campaign Kiwi: "Here's the INFRASTRUCTURE to send emails"
```

**The agent orchestrates across all four to accomplish complex goals.**

---

## Key Architectural Decisions

✅ **Script Kiwi copies Context Kiwi's DB structure** (proven pattern)
✅ **Script Kiwi copies Campaign Kiwi's MCP interface** (5 core tools)
✅ **Knowledge Kiwi has unique structure** (content not code)
✅ **All MCPs expose simple interfaces** (no complex abstractions)
✅ **Directives tell agents HOW to use tools** (not embedded in tools)
✅ **Execution scripts are deterministic** (no LLM code generation)

---

Does this crystallize the architecture? Ready to start building Script Kiwi's Supabase schema?
