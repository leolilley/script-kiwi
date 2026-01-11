# Script Categorization Guide

## How Script Categories Work

Script Kiwi uses **dynamic, directory-based categorization** - you (or the LLM) decide the category names. No hardcoded list!

**Key Features:**
- ✅ **Dynamic categories** - Any category name is valid
- ✅ **Nested subfolders** - Support for subcategories (e.g., `scraping/google-maps/`)
- ✅ **Auto-detection** - Category extracted from directory structure
- ✅ **Flexible** - Organize scripts however makes sense for your project

---

## 📁 Directory-Based Categorization (Primary Method)

### How It Works

Scripts are organized in category directories. **The directory name IS the category.**

**Simple structure:**
```
.ai/scripts/
├── scraping/          → category: "scraping"
├── enrichment/        → category: "enrichment"
└── data-processing/   → category: "data-processing"
```

**Nested structure (subcategories):**
```
.ai/scripts/
├── scraping/
│   ├── google-maps/   → category: "scraping" (subcategory: "google-maps")
│   └── linkedin/      → category: "scraping" (subcategory: "linkedin")
├── data-processing/
│   ├── etl/           → category: "data-processing" (subcategory: "etl")
│   └── api-integration/ → category: "data-processing" (subcategory: "api-integration")
└── utility/
    └── helpers/        → category: "utility" (subcategory: "helpers")
```

**The first directory level is the category. Subdirectories are subcategories.**

### Examples

**Simple category:**
```
.ai/scripts/scraping/google_maps_leads.py
→ category: "scraping"
```

**Nested subcategory:**
```
.ai/scripts/scraping/google-maps/google_maps_leads.py
→ category: "scraping"
→ subcategory: "google-maps" (stored separately)
```

**Custom category:**
```
.ai/scripts/data-processing/api-integration/stripe_webhook.py
→ category: "data-processing"
→ subcategory: "api-integration"
```

---

## 🔍 Category Resolution Process

### 1. **When Publishing** (`publish` tool)

**Priority:**
1. **Explicit parameter** - If you pass `category` in the `publish()` call, that's used
2. **Directory structure** - If no category parameter, inferred from file location
3. **Default** - Falls back to `"utility"` if can't be determined

**Code:**
```python
# In publish.py line 65
category=category or "utility"
```

**Example:**
```python
# Explicit category
publish({
    "script_name": "my_script",
    "version": "1.0.0",
    "category": "scraping"  # ← Explicit category
})

# Inferred from directory
# If script is at: .ai/scripts/scraping/my_script.py
# Category is automatically "scraping"
```

### 2. **When Loading** (`load` tool)

**Priority:**
1. **Directory structure** - Category inferred from where script is found
2. **Registry data** - If loaded from registry, uses stored category
3. **Default** - Falls back to `"utility"`

**Code:**
```python
# In load.py line 61
"category": resolved.get("category") or "utility"
```

### 3. **When Searching** (`search` tool)

**Category is used as a filter:**
- If `category="scraping"` → Only searches scraping scripts
- If `category="all"` → Searches all categories

### 4. **When Resolving** (`ScriptResolver`)

**How category is determined from path:**

```python
# If script is at: .ai/scripts/scraping/example.py
# The resolver checks:
# 1. If category parameter provided → uses that
# 2. If no category → searches all category directories
# 3. When found, the directory name becomes the category
```

**Current Limitation:**
- The resolver doesn't currently extract category from the path
- It relies on the category parameter or defaults to "utility"

---

## 🎯 Dynamic Categories

**Any category name is valid!** No restrictions.

**Common examples:**
- `scraping` - Web scraping scripts
- `enrichment` - Data enrichment
- `data-processing` - Data transformation
- `api-integration` - API integrations
- `validation` - Data validation
- `utility` - Helper functions
- `custom-category` - Your own categories!

**Subcategories supported:**
- `scraping/google-maps/` - Nested organization
- `data-processing/etl/` - Subcategories
- `api-integration/stripe/` - Service-specific

---

## 🔧 Current Implementation Details

### What Works:
- ✅ **Explicit category** in `publish()` - Works perfectly
- ✅ **Directory structure** - Scripts organized by category
- ✅ **Registry storage** - Category stored in database
- ✅ **Search filtering** - Can filter by category

### What's Missing:
- ⚠️ **Auto-detection from path** - Resolver doesn't extract category from directory name
- ⚠️ **Category inference** - When loading from project/user space, category defaults to "utility" instead of using directory name

---

## 💡 How to Use Categories

### Best Practice: Explicit Category

Always specify category when publishing:

```python
publish({
    "script_name": "google_maps_leads",
    "version": "1.0.0",
    "category": "scraping"  # ← Always specify
})
```

### Directory Organization

Organize scripts by category in directories:

```bash
.ai/scripts/
├── scraping/
│   ├── google_maps_leads.py
│   └── linkedin_scraper.py
├── enrichment/
│   ├── email_finder.py
│   └── contact_enricher.py
└── validation/
    └── email_validator.py
```

### Search by Category

```python
# Search only scraping scripts
search({
    "query": "maps",
    "category": "scraping"
})

# Search all categories
search({
    "query": "email",
    "category": "all"  # or omit category
})
```

---

## ✅ Category Extraction (Fixed)

**Status:** Category is now automatically extracted from directory path!

**How it works:**
- When a script is found in `.ai/scripts/scraping/example.py`
- The resolver extracts `"scraping"` from the parent directory name
- This category is included in the resolved result

**Example:**
- Script at: `.ai/scripts/scraping/example.py`
- Load result: `"category": "scraping"` ✅ (automatically detected)

---

## 📝 Summary

**Category is determined by:**

1. **Explicit parameter** (when publishing) - Highest priority
   - If you pass `category` in `publish()`, that's used
   - Example: `publish({"category": "data-processing"})`

2. **Directory structure (file location)** - ✅ **AUTO-DETECTED**
   - Automatically extracted from first directory level
   - Supports nested subcategories
   - Example: `.ai/scripts/data-processing/api-integration/script.py` → category: `"data-processing"`

3. **Registry data** (when loading from registry)
   - Uses the category stored in the database
   - Set when script was originally published

4. **Default** - Falls back to `"utility"` if can't be determined

**Key Features:**
- ✅ **Dynamic** - Any category name is valid (no hardcoded list)
- ✅ **Nested** - Supports subfolders for subcategories
- ✅ **Auto-detection** - Category extracted from directory path
- ✅ **Flexible** - Organize however makes sense

**Best Practice:**
- Organize scripts in category directories
- Use nested folders for subcategories if needed
- Category will be automatically detected from directory structure
- Or specify explicitly when publishing for clarity

