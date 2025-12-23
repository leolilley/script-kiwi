# Directive Orchestration Pattern

## Overview

**Context Kiwi directives** are XML-structured workflows that tell the agent HOW to accomplish tasks by orchestrating **Script Kiwi** (execution) and **Knowledge Kiwi** (knowledge base) tools.

**Key Principle:** Directives contain the "what" and "how", while Script/Knowledge Kiwi provide the "tools" to execute.

## The Orchestration Flow

```
User Request
    ↓
Agent reads Context Kiwi directive
    ↓
Directive contains step-by-step instructions
    ↓
Each step calls Script Kiwi or Knowledge Kiwi tools
    ↓
Agent executes steps in order
    ↓
Results flow between tools as needed
```

## How Directives Reference MCP Tools

### Directive Structure

Directives are XML files that contain:

1. **Progressive Disclosure** - Questions to ask before starting
2. **Process Steps** - Step-by-step instructions
3. **Tool References** - Which Script/Knowledge Kiwi tools to call
4. **Input/Output Mapping** - How data flows between steps

### Example Directive Pattern

```xml
<directive>
  <metadata>
    <name>scrape_and_enrich_leads</name>
    <description>Scrape leads from Google Maps and enrich with emails</description>
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
    
    <step number="2" name="load_script">
      <description>Load the script from Script Kiwi registry</description>
      <tool_call>
        <mcp>script-kiwi</mcp>
        <tool>load</tool>
        <params>
          <script_name>google_maps_leads</script_name>
          <download_to_user>true</download_to_user>
        </params>
      </tool_call>
      <expected_output>Script loaded, ready to execute</expected_output>
    </step>
    
    <step number="3" name="run_scraping">
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
    
    <step number="4" name="enrich_emails">
      <description>Enrich leads with email addresses</description>
      <tool_call>
        <mcp>script-kiwi</mcp>
        <tool>run</tool>
        <params>
          <script_name>email_waterfall_enrichment</script_name>
          <params>
            <input_leads>{step_3_output}</input_leads>
            <strategy>cost_effective</strategy>
          </params>
        </params>
      </tool_call>
      <expected_output>Leads with email addresses</expected_output>
    </step>
    
    <step number="5" name="store_knowledge">
      <description>Store learnings in Knowledge Kiwi</description>
      <tool_call>
        <mcp>knowledge-kiwi</mcp>
        <tool>manage</tool>
        <params>
          <action>create</action>
          <zettel_id>045-lead-generation-{industry}-{location}</zettel_id>
          <title>Lead generation for {industry} in {location}</title>
          <content>Successfully scraped {count} leads using google_maps_leads script</content>
          <entry_type>learning</entry_type>
          <tags>["lead-generation", "{industry}", "scraping"]</tags>
          <location>project</location>
        </params>
      </tool_call>
      <expected_output>Knowledge entry created</expected_output>
    </step>
  </process>
  
  <outputs>
    <output name="enriched_leads">
      <description>List of leads with business info and emails</description>
      <source>{step_4_output}</source>
    </output>
    <output name="knowledge_entry_id">
      <description>ID of created knowledge entry</description>
      <source>{step_5_output.entry_id}</source>
    </output>
  </outputs>
</directive>
```

## Tool Call Patterns in Directives

### Script Kiwi Tool Calls

Directives reference Script Kiwi tools in their `<process>` steps:

**Search Pattern:**
```xml
<step name="find_script">
  <tool_call>
    <mcp>script-kiwi</mcp>
    <tool>search</tool>
    <params>
      <query>email enrichment</query>
      <category>enrichment</category>
    </params>
  </tool_call>
</step>
```

**Load Pattern:**
```xml
<step name="load_script">
  <tool_call>
    <mcp>script-kiwi</mcp>
    <tool>load</tool>
    <params>
      <script_name>{step_1_output.script_name}</script_name>
      <download_to_user>true</download_to_user>
    </params>
  </tool_call>
</step>
```

**Run Pattern:**
```xml
<step name="execute_script">
  <tool_call>
    <mcp>script-kiwi</mcp>
    <tool>run</tool>
    <params>
      <script_name>google_maps_leads</script_name>
      <params>
        <search_term>{user_input.industry}</search_term>
        <location>{user_input.location}</location>
      </params>
    </params>
  </tool_call>
</step>
```

### Knowledge Kiwi Tool Calls

Directives reference Knowledge Kiwi tools for knowledge operations:

**Search Knowledge:**
```xml
<step name="research_best_practices">
  <tool_call>
    <mcp>knowledge-kiwi</mcp>
    <tool>search</tool>
    <params>
      <query>lead generation best practices</query>
      <source>local</source>
      <limit>10</limit>
    </params>
  </tool_call>
</step>
```

**Create Entry:**
```xml
<step name="store_learning">
  <tool_call>
    <mcp>knowledge-kiwi</mcp>
    <tool>manage</tool>
    <params>
      <action>create</action>
      <zettel_id>045-learning-{timestamp}</zettel_id>
      <title>What we learned</title>
      <content>{learning_content}</content>
      <entry_type>learning</entry_type>
      <tags>["learnings", "experiments"]</tags>
      <location>project</location>
    </params>
  </tool_call>
</step>
```

**Link Entries:**
```xml
<step name="link_related">
  <tool_call>
    <mcp>knowledge-kiwi</mcp>
    <tool>link</tool>
    <params>
      <action>link</action>
      <from_zettel_id>{current_zettel_id}</from_zettel_id>
      <to_zettel_id>{related_zettel_id}</to_zettel_id>
      <relationship_type>references</relationship_type>
    </params>
  </tool_call>
</step>
```

## Data Flow Between Tools

Directives define how data flows between Script Kiwi and Knowledge Kiwi:

**Example: Scrape → Enrich → Store**
```
Step 1 (Script Kiwi): run("google_maps_leads") 
  → Output: [{name: "Acme Corp", website: "acme.com", ...}]
  
Step 2 (Script Kiwi): run("email_waterfall_enrichment", {input_leads: step_1_output})
  → Output: [{name: "Acme Corp", email: "contact@acme.com", ...}]
  
Step 3 (Knowledge Kiwi): manage({action: "create", zettel_id: "045-leads", content: "Scraped 500 leads, enriched 450 emails"})
  → Output: {zettel_id: "045-leads", location: "project", path: ".ai/knowledge/learnings/045-leads.md"}
```

**Variable Substitution:**
- `{user_input.field}` - From progressive disclosure questions
- `{step_N_output}` - From previous step's output
- `{step_N_output.field}` - Specific field from previous step

## Directive Loading Mechanism

### How Script/Knowledge Kiwi Access Directives

1. **Project Space First**: Check `.ai/directives/custom/` (project-specific)
2. **Context Kiwi Registry**: Query Context Kiwi Supabase if not found locally
3. **Cache Locally**: Download to `.ai/directives/custom/` for faster future access
4. **Refresh Strategy**: Check `updated_at` timestamp, refresh if >24 hours old

### Directive Caching

- Script Kiwi caches directives in `.ai/directives/custom/`
- Knowledge Kiwi can also cache directives (same location)
- Both MCPs can query Context Kiwi Supabase for latest versions
- Lockfiles pin directive versions (same as scripts)

## Complete Workflow Example

**User Request:** "Scrape 500 dental clinic leads in Texas and enrich their emails"

**Agent Flow:**

1. **Load Directive** (Context Kiwi):
   ```
   get_directive("scrape_and_enrich_leads")
   ```
   - Directive contains progressive disclosure questions
   - Agent asks: "What industry? (dental clinics) What location? (Texas) How many? (500)"

2. **Follow Directive Steps**:

   **Step 1**: Search for scraping script
   ```
   script-kiwi.search({query: "google maps leads", category: "scraping"})
   → Returns: {name: "google_maps_leads", ...}
   ```

   **Step 2**: Load the script
   ```
   script-kiwi.load({script_name: "google_maps_leads", download_to_user: true})
   → Returns: {script_path: "...", params: {...}}
   ```

   **Step 3**: Run scraping script
   ```
   script-kiwi.run({
     script_name: "google_maps_leads",
     params: {search_term: "dental clinic", location: "Texas", max_results: 500}
   })
   → Returns: [{name: "Smile Dental", website: "...", ...}, ...]
   ```

   **Step 4**: Search for enrichment script
   ```
   script-kiwi.search({query: "email enrichment", category: "enrichment"})
   → Returns: {name: "email_waterfall_enrichment", ...}
   ```

   **Step 5**: Run enrichment script
   ```
   script-kiwi.run({
     script_name: "email_waterfall_enrichment",
     params: {input_leads: step_3_output, strategy: "cost_effective"}
   })
   → Returns: [{name: "Smile Dental", email: "contact@...", ...}, ...]
   ```

   **Step 6**: Store learnings in Knowledge Kiwi
   ```
   knowledge-kiwi.manage({
     action: "create",
     zettel_id: "045-dental-leads-texas",
     title: "Dental clinic lead generation in Texas",
     content: "Successfully scraped 500 leads, enriched 450 emails",
     entry_type: "learning",
     tags: ["lead-generation", "dental", "texas"],
     location: "project"
   })
   → Returns: {zettel_id: "045-dental-leads-texas", location: "project", path: ".ai/knowledge/learnings/045-dental-leads-texas.md"}
   ```

3. **Return Results**:
   - Enriched leads (from Script Kiwi)
   - Knowledge entry ID (from Knowledge Kiwi)
   - Execution metrics (cost, duration, etc.)

## Key Principles

1. **Directives are Workflows**: They define step-by-step processes, not just tool calls
2. **Tools are Capabilities**: Script/Knowledge Kiwi provide the actual execution/knowledge operations
3. **Agent Orchestrates**: The LLM reads directives and calls tools in the right order
4. **Data Flows Between Steps**: Output from one step becomes input to the next
5. **Progressive Disclosure**: Directives ask questions before starting (via Context Kiwi)
6. **Self-Annealing**: When workflows fail, directives are updated with learnings

## Directive vs Tool Responsibility

| Responsibility | Context Kiwi (Directives) | Script/Knowledge Kiwi (Tools) |
|----------------|---------------------------|-------------------------------|
| **What** | Define workflow steps | Execute individual operations |
| **How** | Step-by-step instructions | Deterministic code execution |
| **When** | Progressive disclosure questions | Parameter validation |
| **Why** | Business logic, decision rules | Technical implementation |
| **Where** | XML files in registry | Python modules in registry |

## Integration Points

### Context Kiwi → Script Kiwi
- Directives reference Script Kiwi tools (`search`, `load`, `run`)
- Directives define which scripts to use for which tasks
- Directives contain parameter mapping (user input → script params)

### Context Kiwi → Knowledge Kiwi
- Directives reference Knowledge Kiwi tools (`search`, `get`, `manage`, `link`, `help`)
- Directives define when to store learnings (using `manage` with `action: "create"`)
- Directives specify knowledge entry structure and source selection (`source: "local"` | `"registry"`)

### Script Kiwi → Knowledge Kiwi
- Script outputs can be stored as knowledge entries
- Script execution learnings go to Knowledge Kiwi
- Knowledge search can inform script parameter selection

## Benefits of This Pattern

1. **Separation of Concerns**: Directives = workflow logic, Tools = execution
2. **Reusability**: Same scripts/knowledge tools used by multiple directives
3. **Maintainability**: Update directives without changing tool code
4. **Discoverability**: Agents can search for scripts/knowledge independently
5. **Versioning**: Directives and tools versioned separately (lockfiles)
6. **Self-Improvement**: Failed workflows update directives, not tools

---

**Summary:** Context Kiwi directives are the "conductor" that orchestrates Script Kiwi (the "orchestra") and Knowledge Kiwi (the "library") to accomplish complex workflows. The agent reads the directive, follows the steps, and calls the appropriate MCP tools in sequence.

