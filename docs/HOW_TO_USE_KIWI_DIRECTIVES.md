# How to Use Kiwi Directives

> The philosophy and practice of directive-driven development.

---

## The Core Philosophy

### Directives All The Way Down

Every piece of work should have a directive. When you find yourself doing something manually:

1. **First time:** Do it manually, note the steps
2. **Second time:** Create a directive from your notes
3. **Third time:** Run the directive

The goal is to remove yourself from the loop. LLMs instructing LLMs.

### The Three Kiwis

| Kiwi | What It Stores | When To Use |
|------|----------------|-------------|
| **Context Kiwi** | Directives (HOW) | "How do I do X?" |
| **Script Kiwi** | Scripts (DO) | "Execute X" |
| **Knowledge Kiwi** | Knowledge (KNOW) | "What do I know about X?" |

They work together:
```
Directive says "call this script" → Script executes → Store learnings in Knowledge
```

---

## The Workflow

### 1. Search Before You Build

Always check if something exists:

```
# Check Context Kiwi for directives
search("what you want to do", source="all")

# Check Script Kiwi for execution
script_kiwi.search(query="what you want to do")

# Check Knowledge Kiwi for learnings
knowledge_kiwi.search(query="what you want to know", source="local")
```

Don't reinvent. Build on what exists.

### 2. Run With Context

When running directives, always provide project_path if you're not in the project:

```
run("directive_name", inputs={...}, project_path="/home/leo/projects/my-project")
```

The directive gets:
- Your inputs
- Project context (.ai/project_context.md)
- Patterns (.ai/patterns/*)
- AGENTS.md instructions

### 3. Store Learnings

After execution, store what you learned:

```
knowledge_kiwi.manage(
    action="create",
    zettel_id="descriptive-id",
    title="What I learned",
    content="...",
    entry_type="learning"  # or api_fact, failure, pattern
)
```

This makes the system smarter for next time.

### 4. Anneal On Failure

When a directive fails:

```
run("anneal_directive", inputs={
    directive: "the_directive_that_failed",
    error: "description of what went wrong"
})
```

The directive improves. The system gets smarter.

---

## Implementing Features

### The Flow

```
1. Read the plan doc
   └─ .ai/plans/PLAN_Q1_2026_*.md

2. Break it down
   └─ run("plan_implementation", inputs={work_item: "...", plan_doc: "..."})

3. Implement
   └─ run("implement_kiwi_feature", inputs={feature: "...", repo: "..."})

4. Verify with real usage
   └─ Use GHL Agent (or another agent) to exercise the feature

5. Store learnings
   └─ knowledge_kiwi.manage(action="create", ...)

6. Anneal if needed
   └─ run("anneal_directive", inputs={...})
```

### Key Directives

| Directive | Purpose |
|-----------|---------|
| `plan_implementation` | Break feature into components |
| `implement_kiwi_feature` | Implement with proper process |
| `create_directive` | Create new directives |
| `anneal_directive` | Improve failing directives |
| `context` | Generate project understanding |

---

## Best Practices

### 1. Knowledge First

Before writing code:
- Search Knowledge Kiwi for prior learnings
- Check if someone solved this before
- Don't repeat mistakes already documented

### 2. Small Components

Each piece of work should be:
- Completable in one session
- Testable independently
- Describable in one sentence

If it's bigger, break it down more.

### 3. Test First (When Practical)

Write a failing test that defines success:
```python
def test_feature_works():
    result = feature(valid_input)
    assert result == expected
```

Then implement until it passes.

### 4. Real Usage Is The Best Test

Unit tests are good. Real usage is better.

Use GHL Agent (or your actual agent) to exercise new features. Real data, real edge cases.

### 5. Document Failures

When something breaks:
```
knowledge_kiwi.manage(
    action="create",
    zettel_id="failure-descriptive-name",
    title="Why X failed",
    content="""
## What happened
{description}

## Why it failed
{root cause}

## How to prevent
{mitigation}
    """,
    entry_type="failure"
)
```

Failures are valuable. Don't lose them.

---

## Common Patterns

### Pattern: Feature Implementation

```
# 1. Understand what exists
run("context", project_path="/home/leo/projects/script-kiwi")

# 2. Plan the work
run("plan_implementation", inputs={
    work_item: "parameter_validation",
    plan_doc: ".ai/plans/PLAN_Q1_2026_SCRIPT_KIWI.md"
})

# 3. Implement
run("implement_kiwi_feature", inputs={
    feature: "parameter_validation",
    repo: "script-kiwi",
    test_first: true
})
```

### Pattern: Learning from YouTube

```
# 1. Extract knowledge
run("extract_ghl_knowledge", inputs={
    url: "https://youtube.com/watch?v=..."
}, project_path="/home/leo/projects/ghl-agent")

# 2. Review and refine (human step)

# 3. Store refined knowledge
knowledge_kiwi.manage(action="update", zettel_id="...", ...)
```

### Pattern: Debugging

```
# 1. Capture the failure
knowledge_kiwi.manage(
    action="create",
    zettel_id="debug-session-YYYY-MM-DD",
    title="Debugging X",
    content="symptoms, hypotheses, findings...",
    entry_type="learning"
)

# 2. After fixing, update with solution
knowledge_kiwi.manage(action="update", zettel_id="...", content="...solution...")

# 3. Anneal any directives that contributed to the bug
run("anneal_directive", inputs={directive: "...", error: "..."})
```

---

## Anti-Patterns

### ❌ Manual Repetition

**Bad:** Doing the same thing manually three times.
**Good:** Create a directive after the first time.

### ❌ Forgetting Learnings

**Bad:** Solving the same problem again because you forgot.
**Good:** Store learnings in Knowledge Kiwi immediately.

### ❌ Ignoring Failures

**Bad:** Fixing a bug and moving on.
**Good:** Document the failure, anneal the directive.

### ❌ Skipping Search

**Bad:** Building from scratch without checking.
**Good:** Always search first.

### ❌ Giant Components

**Bad:** "Implement the entire feature" as one task.
**Good:** Break into components < 2 hours each.

---

## Getting Started

### First Time in a Repo

```
# 1. Initialize (if not already done)
run("init", project_path="/path/to/repo")

# 2. Generate context
run("context", project_path="/path/to/repo")

# 3. Read the plan doc
Read .ai/plans/PLAN_*.md
```

### First Time on a Feature

```
# 1. Read the plan
Read the relevant section in .ai/plans/

# 2. Check knowledge base
knowledge_kiwi.search(query="feature name", source="local")

# 3. Plan implementation
run("plan_implementation", inputs={...})

# 4. Execute
run("implement_kiwi_feature", inputs={...})
```

---

## Summary

1. **Search first** - Don't reinvent
2. **Plan before code** - Break it down
3. **Test with real usage** - Not just unit tests
4. **Store learnings** - Make the system smarter
5. **Anneal on failure** - The system improves

*Directives all the way down. Every layer instructs the next.*
