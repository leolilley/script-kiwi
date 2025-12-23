# Sample Directive Example

## Complete Working Directive

This is a complete, working example of a directive that orchestrates Script Kiwi and Knowledge Kiwi tools.

**File:** `.ai/directives/custom/scrape_and_enrich_leads.md`

```xml
<?xml version="1.0"?>
<directive>
  <metadata>
    <name>scrape_and_enrich_leads</name>
    <description>Scrape leads from Google Maps and enrich with email addresses</description>
    <version>1.0.0</version>
    <author>system</author>
    <created_at>2025-01-15T10:00:00Z</created_at>
    <updated_at>2025-01-15T10:00:00Z</updated_at>
  </metadata>
  
  <progressive_disclosure>
    <initial_questions>
      <question type="text">What industry or business type to target?</question>
      <question type="text">What location (city, state, or region)?</question>
      <question type="number">How many leads do you need?</question>
      <question type="select" options="['cost_effective', 'best_quality', 'guess_only']">What enrichment strategy? (cost_effective tries free methods first, best_quality uses premium APIs, guess_only doesn't spend money)</question>
    </initial_questions>
    <decision_gate>Ready to proceed with scraping and enrichment?</decision_gate>
  </progressive_disclosure>
  
  <inputs>
    <input name="industry" type="string" required="true">
      <description>Industry or business type to search for</description>
      <example>dental clinic</example>
    </input>
    <input name="location" type="string" required="true">
      <description>Location to search in</description>
      <example>Texas</example>
    </input>
    <input name="count" type="integer" required="true" min="1" max="10000">
      <description>Number of leads to scrape</description>
      <example>500</example>
    </input>
    <input name="enrichment_strategy" type="string" required="false" default="cost_effective">
      <description>Email enrichment strategy</description>
      <options>cost_effective, best_quality, guess_only</options>
    </input>
  </inputs>
  
  <process>
    <step number="1" name="search_scraping_script">
      <description>Search Script Kiwi for a lead scraping script</description>
      <tool_call>
        <mcp>script-kiwi</mcp>
        <tool>search</tool>
        <params>
          <query>google maps leads scraping</query>
          <category>scraping</category>
          <limit>5</limit>
        </params>
      </tool_call>
      <expected_output>
        <field name="scripts">Array of matching scripts</field>
        <field name="scripts[0].name">Script name (e.g., "google_maps_leads")</field>
      </expected_output>
      <error_handling>
        <if condition="no_results">
          <action>Suggest alternative search terms or check Script Kiwi registry</action>
        </if>
      </error_handling>
    </step>
    
    <step number="2" name="load_scraping_script">
      <description>Load the scraping script details</description>
      <tool_call>
        <mcp>script-kiwi</mcp>
        <tool>load</tool>
        <params>
          <script_name>{step_1_output.scripts[0].name}</script_name>
          <download_to_user>true</download_to_user>
        </params>
      </tool_call>
      <expected_output>
        <field name="script_path">Path to loaded script</field>
        <field name="inputs">Required input parameters</field>
      </expected_output>
    </step>
    
    <step number="3" name="run_scraping">
      <description>Execute the scraping script to collect leads</description>
      <tool_call>
        <mcp>script-kiwi</mcp>
        <tool>run</tool>
        <params>
          <script_name>{step_1_output.scripts[0].name}</script_name>
          <params>
            <search_term>{inputs.industry}</search_term>
            <location>{inputs.location}</location>
            <max_results>{inputs.count}</max_results>
          </params>
        </params>
      </tool_call>
      <expected_output>
        <field name="status">"success"</field>
        <field name="data.leads">Array of lead objects with business info</field>
        <field name="metadata.cost_usd">Cost of scraping operation</field>
        <field name="metadata.rows_processed">Number of leads scraped</field>
      </expected_output>
      <error_handling>
        <if condition="execution_failed">
          <action>Check error message, verify API keys, retry with smaller count</action>
        </if>
      </error_handling>
    </step>
    
    <step number="4" name="search_enrichment_script">
      <description>Search for email enrichment script</description>
      <tool_call>
        <mcp>script-kiwi</mcp>
        <tool>search</tool>
        <params>
          <query>email enrichment waterfall</query>
          <category>enrichment</category>
        </params>
      </tool_call>
      <expected_output>
        <field name="scripts[0].name">Enrichment script name (e.g., "email_waterfall_enrichment")</field>
      </expected_output>
    </step>
    
    <step number="5" name="run_enrichment">
      <description>Enrich leads with email addresses</description>
      <tool_call>
        <mcp>script-kiwi</mcp>
        <tool>run</tool>
        <params>
          <script_name>{step_4_output.scripts[0].name}</script_name>
          <params>
            <input_leads>{step_3_output.data.leads}</input_leads>
            <strategy>{inputs.enrichment_strategy}</strategy>
          </params>
        </params>
      </tool_call>
      <expected_output>
        <field name="status">"success"</field>
        <field name="data.enriched_leads">Array of leads with email addresses</field>
        <field name="data.enriched_count">Number of leads successfully enriched</field>
        <field name="metadata.cost_usd">Total cost of enrichment</field>
      </expected_output>
    </step>
    
    <step number="6" name="store_knowledge">
      <description>Store learnings in Knowledge Kiwi</description>
      <tool_call>
        <mcp>knowledge-kiwi</mcp>
        <tool>manage</tool>
        <params>
          <action>create</action>
          <zettel_id>045-lead-gen-{inputs.industry}-{timestamp}</zettel_id>
          <title>Lead generation: {inputs.industry} in {inputs.location}</title>
          <content>
            Successfully scraped {step_3_output.metadata.rows_processed} leads and enriched {step_5_output.data.enriched_count} emails.
            
            Strategy: {inputs.enrichment_strategy}
            Total cost: ${step_3_output.metadata.cost_usd + step_5_output.metadata.cost_usd}
            
            Scripts used:
            - {step_1_output.scripts[0].name} (scraping)
            - {step_4_output.scripts[0].name} (enrichment)
          </content>
          <entry_type>learning</entry_type>
          <tags>
            <tag>lead-generation</tag>
            <tag>{inputs.industry}</tag>
            <tag>scraping</tag>
            <tag>enrichment</tag>
          </tags>
          <source_type>experiment</source_type>
          <location>project</location>
        </params>
      </tool_call>
      <expected_output>
        <field name="zettel_id">Zettel ID for reference</field>
        <field name="location">Where entry was created (project/user)</field>
        <field name="path">File path to entry</field>
      </expected_output>
    </step>
  </process>
  
  <outputs>
    <output name="enriched_leads">
      <description>List of leads with business info and email addresses</description>
      <source>{step_5_output.data.enriched_leads}</source>
      <format>Array of objects with: name, website, email, phone, address</format>
    </output>
    <output name="knowledge_entry">
      <description>Created knowledge entry details for future reference</description>
      <source>{step_6_output.zettel_id}</source>
    </output>
    <output name="summary">
      <description>Execution summary</description>
      <source>
        {
          "leads_scraped": {step_3_output.metadata.rows_processed},
          "emails_enriched": {step_5_output.data.enriched_count},
          "total_cost_usd": {step_3_output.metadata.cost_usd + step_5_output.metadata.cost_usd},
          "enrichment_rate": {step_5_output.data.enriched_count / step_3_output.metadata.rows_processed}
        }
      </source>
    </output>
  </outputs>
  
  <edge_cases>
    <case name="no_results">
      <description>No leads found for search term</description>
      <handling>Return empty array, suggest alternative search terms</handling>
    </case>
    <case name="enrichment_failed">
      <description>Email enrichment returns 0% success rate</description>
      <handling>Return leads without emails, log warning, suggest manual research</handling>
    </case>
    <case name="cost_exceeded">
      <description>Estimated cost exceeds budget</description>
      <handling>Stop before execution, ask for confirmation or reduce count</handling>
    </case>
  </edge_cases>
  
  <error_handling>
    <strategy>Continue on non-critical errors, stop on critical failures</strategy>
    <critical_errors>
      <error>SCRIPT_NOT_FOUND</error>
      <error>MISSING_ENV_VARS</error>
      <error>INVALID_PARAMETERS</error>
    </critical_errors>
    <non_critical_errors>
      <error>ENRICHMENT_PARTIAL_FAILURE</error>
      <error>KNOWLEDGE_STORE_FAILED</error>
    </non_critical_errors>
  </error_handling>
  
  <self_annealing_log>
    <entry date="2025-01-15">
      <event>Initial creation</event>
      <notes>Created basic workflow for scraping and enrichment</notes>
    </entry>
  </self_annealing_log>
</directive>
```

## How the Agent Uses This Directive

1. **Agent reads directive** from Context Kiwi
2. **Progressive disclosure**: Agent asks user the 4 questions
3. **Agent follows steps in order**:
   - Step 1: Calls `script-kiwi.search({"query": "google maps leads scraping"})`
   - Step 2: Calls `script-kiwi.load({"script_name": "google_maps_leads"})`
   - Step 3: Calls `script-kiwi.run({"script_name": "google_maps_leads", "params": {...}})`
   - Step 4: Calls `script-kiwi.search({"query": "email enrichment waterfall"})`
   - Step 5: Calls `script-kiwi.run({"script_name": "email_waterfall_enrichment", "params": {...}})`
   - Step 6: Calls `knowledge-kiwi.manage({action: "create", ...})`
4. **Agent returns outputs** to user

## Key Features

- **Variable substitution**: `{inputs.industry}`, `{step_3_output.data.leads}`
- **Error handling**: Specific actions for different error types
- **Cost tracking**: Aggregates costs from multiple steps
- **Knowledge storage**: Automatically stores learnings
- **Self-annealing**: Logs improvements for future updates

---

**See `Directive-Orchestration-Pattern.md` for complete documentation on directive structure and tool call patterns.**

