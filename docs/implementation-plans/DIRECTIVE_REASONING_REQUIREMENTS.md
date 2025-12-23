# Directive Reasoning Requirements

**Insight:** Directives declare their required reasoning level in metadata. At execution time, check if the current model meets the requirement. No oracle needed - it's deterministic.

**Date:** 2025-01-15  
**Status:** Concept - Ready for Implementation

---

## The Core Concept

### Problem (from video)
- **Oracle Pattern:** Use GPT-5.1 Pro for complex problems that Opus can't handle
- **Approach:** Try with one model, fail, escalate to oracle
- **Issue:** Don't know complexity until you try it, pay for failed attempts

### Kiwi Solution
- **Directive declares requirement:** Author specifies reasoning level needed
- **Execution-time check:** Verify current model meets requirement
- **No oracle needed:** Deterministic check, no trial-and-error

---

## Directive Metadata Structure

### Reasoning Requirement Field

```xml
<directive>
  <metadata>
    <name>scrape_and_enrich_leads</name>
    <description>Scrape leads from Google Maps and enrich with emails</description>
    <version>1.0.0</version>
    <author>system</author>
    <created_at>2025-01-15T10:00:00Z</created_at>
    <updated_at>2025-01-15T10:00:00Z</updated_at>
    
    <!-- NEW: Reasoning requirement -->
    <reasoning_required>medium</reasoning_required>
    <!-- Options: "low" | "medium" | "high" -->
    <!-- Or more specific: "haiku" | "sonnet" | "opus" | "gpt-4" -->
  </metadata>
  
  <process>
    <!-- ... directive steps ... -->
  </process>
</directive>
```

### Reasoning Levels

**Low (`"low"` or `"haiku"`):**
- Simple linear execution
- All Script Kiwi tool calls (deterministic)
- No Knowledge Kiwi searches requiring interpretation
- No conditional logic or decision-making
- **Example:** Run a single script with direct parameter mapping

**Medium (`"medium"` or `"sonnet"`):**
- Mix of Script Kiwi and Knowledge Kiwi
- Some conditional logic
- Basic parameter transformations
- Knowledge Kiwi searches with straightforward interpretation
- **Example:** Search for script, run it, store results in Knowledge Kiwi

**High (`"high"` or `"opus"` / `"gpt-4"`):**
- Multiple Knowledge Kiwi searches requiring synthesis
- Complex conditional logic or loops
- Abstract problem-solving steps
- Research/planning phases
- Error handling with retry logic
- **Example:** Research best practices, analyze findings, plan approach, execute

---

## Execution-Time Model Check

### Before Executing Directive

```python
def can_execute_directive(directive: Dict, current_model: str) -> Tuple[bool, Optional[str]]:
    """
    Check if current model can execute directive.
    
    Args:
        directive: Directive metadata with reasoning_required field
        current_model: Current model identifier (e.g., "claude-haiku-4", "claude-opus-4.5")
    
    Returns:
        (can_execute: bool, message: Optional[str])
    """
    required = directive["metadata"].get("reasoning_required")
    
    if not required:
        # No requirement specified - allow execution (backward compatible)
        return True, None
    
    # Map model names to reasoning levels
    model_levels = {
        "haiku": "low",
        "sonnet": "medium", 
        "opus": "high",
        "gpt-4": "high",
        "gpt-4-turbo": "high",
        "gpt-3.5": "low"
    }
    
    # Extract model level from model name
    current_level = None
    for model_key, level in model_levels.items():
        if model_key in current_model.lower():
            current_level = level
            break
    
    if not current_level:
        # Unknown model - allow but warn
        return True, f"Unknown model {current_model}, proceeding with caution"
    
    # Check if current model meets requirement
    level_hierarchy = {"low": 1, "medium": 2, "high": 3}
    current_value = level_hierarchy.get(current_level, 0)
    required_value = level_hierarchy.get(required, 0)
    
    if current_value >= required_value:
        return True, None
    else:
        return False, (
            f"Directive requires {required} reasoning, but current model ({current_model}) "
            f"only provides {current_level} reasoning. "
            f"Please switch to a model with {required} reasoning capability."
        )
```

### Usage in Context Kiwi

```python
# When loading directive for execution
directive = context_kiwi.get_directive("scrape_and_enrich_leads")
current_model = get_current_model()  # e.g., "claude-haiku-4"

can_execute, message = can_execute_directive(directive, current_model)

if not can_execute:
    return {
        "status": "error",
        "error": "Model capability mismatch",
        "message": message,
        "required_reasoning": directive["metadata"]["reasoning_required"],
        "current_model": current_model,
        "suggestion": f"Switch to a model with {directive['metadata']['reasoning_required']} reasoning"
    }

# Proceed with execution
result = execute_directive(directive, inputs)
```

---

## Examples

### Example 1: Simple Directive (Low Reasoning)

```xml
<directive>
  <metadata>
    <name>run_simple_script</name>
    <reasoning_required>low</reasoning_required>
  </metadata>
  
  <process>
    <step number="1">
      <tool_call>
        <mcp>script-kiwi</mcp>
        <tool>run</tool>
        <params>
          <script_name>extract_youtube_transcript</script_name>
          <params>
            <video_url>{user_input.video_url}</video_url>
          </params>
        </params>
      </tool_call>
    </step>
  </process>
</directive>
```

**Execution Check:**
- Current model: `claude-haiku-4` (low reasoning) ✅
- Can execute: Yes
- No oracle needed - simple deterministic execution

### Example 2: Medium Complexity Directive

```xml
<directive>
  <metadata>
    <name>scrape_and_enrich_leads</name>
    <reasoning_required>medium</reasoning_required>
  </metadata>
  
  <process>
    <step number="1">
      <tool_call>
        <mcp>script-kiwi</mcp>
        <tool>run</tool>
        <params>
          <script_name>google_maps_leads</script_name>
          <params>
            <search_term>{user_input.industry}</search_term>
          </params>
        </params>
      </tool_call>
    </step>
    
    <step number="2">
      <if condition="{step_1_output.count} > 0">
        <tool_call>
          <mcp>script-kiwi</mcp>
          <tool>run</tool>
          <params>
            <script_name>email_waterfall_enrichment</script_name>
            <params>
              <input_leads>{step_1_output}</input_leads>
            </params>
          </params>
        </tool_call>
      </if>
    </step>
    
    <step number="3">
      <tool_call>
        <mcp>knowledge-kiwi</mcp>
        <tool>search</tool>
        <params>
          <query>enrichment best practices</query>
        </params>
      </tool_call>
    </step>
  </process>
</directive>
```

**Execution Check:**
- Current model: `claude-haiku-4` (low reasoning) ❌
- Can execute: No
- Message: "Directive requires medium reasoning, but current model only provides low reasoning. Please switch to a model with medium reasoning capability."
- **No oracle needed** - just check and route to Sonnet

### Example 3: Complex Directive (High Reasoning)

```xml
<directive>
  <metadata>
    <name>research_and_plan_campaign</name>
    <reasoning_required>high</reasoning_required>
  </metadata>
  
  <process>
    <step number="1" name="research">
      <description>Research target market and best practices</description>
      <tool_call>
        <mcp>knowledge-kiwi</mcp>
        <tool>search</tool>
        <params>
          <query>{user_input.industry} lead generation strategies</query>
        </params>
      </tool_call>
    </step>
    
    <step number="2" name="analyze_findings">
      <description>Analyze research findings and plan approach</description>
      <action>
        Review {step_1_output} and determine:
        1. Best scraping strategy
        2. Optimal enrichment approach
        3. Expected success rates
      </action>
    </step>
    
    <step number="3" name="select_scripts">
      <description>Select scripts based on analysis</description>
      <tool_call>
        <mcp>script-kiwi</mcp>
        <tool>search</tool>
        <params>
          <query>{step_2_output.recommended_approach}</query>
        </params>
      </tool_call>
    </step>
  </process>
</directive>
```

**Execution Check:**
- Current model: `claude-sonnet-4.5` (medium reasoning) ❌
- Can execute: No
- Message: "Directive requires high reasoning, but current model only provides medium reasoning. Please switch to Opus or GPT-4."
- **No oracle needed** - just check and route to Opus

---

## Benefits

### 1. **No Oracle Needed**
- **Before:** Try with one model, fail, escalate to oracle
- **After:** Check requirement upfront, route to correct model immediately

### 2. **Deterministic**
- **Before:** Trial-and-error, unpredictable
- **After:** Simple metadata check, always works

### 3. **Cost Optimization**
- **Before:** Might use Opus for simple tasks (waste)
- **After:** Use Haiku for low requirements, Opus only when needed

### 4. **Clear Communication**
- **Before:** User doesn't know why it failed
- **After:** Clear message: "This directive needs Opus, you're using Haiku"

### 5. **Author Control**
- Directive author knows what reasoning is needed
- Declares it upfront in metadata
- No guessing, no analysis needed

---

## Implementation

### Phase 1: Add Metadata Field (Week 1)

1. **Update Directive Schema:**
   - Add `reasoning_required` field to directive metadata
   - Support: `"low"`, `"medium"`, `"high"` (or model-specific: `"haiku"`, `"sonnet"`, `"opus"`)
   - Make it optional for backward compatibility

2. **Update Directive Examples:**
   - Add `reasoning_required` to sample directives
   - Document when to use each level

### Phase 2: Execution-Time Check (Week 2)

1. **Add Check Function:**
   - `can_execute_directive(directive, current_model) -> (bool, message)`
   - Map model names to reasoning levels
   - Return clear error messages

2. **Integrate with Context Kiwi:**
   - Check before executing directive
   - Return helpful error if model doesn't meet requirement
   - Suggest appropriate model

### Phase 3: Model Detection (Week 3)

1. **Detect Current Model:**
   - From MCP client configuration
   - From environment variables
   - From user settings

2. **Model Capability Mapping:**
   - Maintain mapping of models to reasoning levels
   - Support multiple model providers (Claude, GPT, etc.)

### Phase 4: Documentation & Tooling (Week 4)

1. **Documentation:**
   - Guide for directive authors on setting `reasoning_required`
   - Examples of each reasoning level
   - Best practices

2. **Tooling:**
   - Optional: Analysis tool to suggest `reasoning_required` based on directive structure
   - Validation tool to check if requirement matches directive complexity

---

## Optional: Analysis Tool (Not Required)

While the requirement is declared in metadata, you could optionally provide an analysis tool to help authors set it correctly:

```python
def suggest_reasoning_requirement(directive_xml: str) -> str:
    """
    Analyze directive structure and suggest reasoning_required level.
    
    This is OPTIONAL - directive author can set it manually.
    This tool just helps authors make the right choice.
    """
    # Count Knowledge Kiwi calls
    # Count conditional steps
    # Count abstract problem-solving steps
    # Return suggested level
    
    # But the directive author has final say!
```

**Key Point:** The analysis tool is **optional guidance**, not required. The directive author declares the requirement, and execution just checks it.

---

## Comparison with Video's Oracle Pattern

| Aspect | Video's Oracle | Kiwi Directive Requirements |
|--------|----------------|----------------------------|
| **Timing** | After failure | Before execution |
| **Approach** | Trial and error | Metadata check |
| **Determinism** | Unpredictable | Deterministic |
| **Cost** | Pay for failed attempt + oracle | Pay for right model from start |
| **Speed** | Slow (fail, retry) | Fast (check, route) |
| **Transparency** | Black box | Clear requirement + check |
| **Author Control** | None | Author declares requirement |

---

## Key Principles

1. **Directive Author Knows Best:** The person creating the directive knows what reasoning is needed
2. **Declarative, Not Inferred:** Requirement is declared in metadata, not analyzed
3. **Simple Check:** Execution-time check is just a comparison, no complex logic
4. **No Oracle Needed:** Deterministic check eliminates need for trial-and-error
5. **Backward Compatible:** Optional field, existing directives work without it

---

## Questions to Explore

1. **Should we support model-specific requirements?**
   - `reasoning_required="opus"` vs `reasoning_required="high"`
   - Pro: More specific, can require exact model
   - Con: Less flexible, harder to switch providers

2. **Should we validate requirement matches complexity?**
   - Optional validation tool that warns if requirement seems wrong
   - Pro: Catches mistakes
   - Con: Might be opinionated, author knows best

3. **Should we track actual performance vs requirement?**
   - Learn if requirement is too high/low
   - Pro: Can suggest adjustments
   - Con: Adds complexity, author might disagree

4. **How to handle model provider differences?**
   - Claude Opus vs GPT-4 - both "high" but different
   - Pro: Abstract levels (low/medium/high) work across providers
   - Con: Might need provider-specific requirements

---

## Conclusion

**The Key Insight:** Because directives are deterministic workflows, the author can declare the required reasoning level upfront. At execution time, it's just a simple check - no oracle, no analysis, no trial-and-error.

This is **simpler and more powerful** than the video's oracle pattern because:
- **Deterministic:** Always works, no guessing
- **Author-controlled:** Person who knows the workflow sets the requirement
- **Cost-effective:** Right model from the start
- **Transparent:** Clear why a model can't execute

---

**Last Updated:** 2025-01-15  
**Status:** Concept - Ready for Implementation Planning






