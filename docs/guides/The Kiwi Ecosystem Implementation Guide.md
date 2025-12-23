# Complete Kiwi Ecosystem Implementation Guide

Let's build the entire system, end-to-end.

---

## Part 1: Supabase Projects Setup

### Create New Supabase Projects

```bash
# Go to supabase.com and create:
1. script-kiwi (new project)
2. knowledge-kiwi (new project)

# You already have:
3. context-kiwi (existing: mrecfyfjpwzrzxoiooew)
4. campaign-kiwi (existing)
```

---

## Part 2: Database Schemas

### 2.1 Script Kiwi Database Schema

```sql
-- ============================================
-- SCRIPT KIWI DATABASE SCHEMA
-- Extends Context Kiwi pattern for scripts
-- ============================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ==========================================
-- USERS (Same as Context Kiwi)
-- ==========================================
CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    email text UNIQUE,
    username text UNIQUE NOT NULL,
    trust_score integer DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- ==========================================
-- SCRIPTS (Mirrors directives structure)
-- ==========================================
CREATE TABLE scripts (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name text UNIQUE NOT NULL,
    
    -- Categorization
    category text NOT NULL CHECK (category IN (
        'scraping',      -- Google Maps, LinkedIn, etc.
        'enrichment',    -- Email finding, validation
        'extraction',    -- YouTube, websites, GitHub
        'validation',    -- Data quality checks
        'maintenance',   -- Cleanup, cost reports
        'utility'        -- Helper functions
    )),
    subcategory text,
    description text,
    
    -- Metadata (like directives)
    author_id uuid REFERENCES users(id),
    is_official boolean DEFAULT false,
    download_count integer DEFAULT 0,
    quality_score numeric(3, 2) DEFAULT 0 CHECK (quality_score >= 0 AND quality_score <= 1),
    
    -- Script-specific
    module_path text NOT NULL,  -- 'execution.scraping.google_maps'
    
    -- Dependencies
    tech_stack jsonb DEFAULT '[]',           -- ['python', 'apify']
    dependencies jsonb DEFAULT '[]',         -- [{"name": "apify-client", "version": ">=0.1.0"}]
    required_env_vars text[] DEFAULT '{}',   -- ['APIFY_API_TOKEN']
    required_scripts uuid[] DEFAULT '{}',    -- Other scripts this depends on
    
    -- Cost estimation
    estimated_cost_usd numeric(10, 4),
    estimated_time_seconds integer,
    cost_per_unit numeric(10, 4),  -- e.g., $0.001 per lead
    cost_unit text,                 -- 'lead', 'email', 'video', etc.
    
    -- Usage tracking
    usage_count integer DEFAULT 0,
    success_rate numeric(5, 2),              -- % successful runs
    avg_execution_time_sec numeric(10, 2),
    last_used_at timestamptz,
    
    -- Search
    tags text[] DEFAULT '{}',
    
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Full-text search support
ALTER TABLE scripts ADD COLUMN tsv tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english', 
            name || ' ' || 
            COALESCE(description, '') || ' ' || 
            COALESCE(category, '') || ' ' ||
            COALESCE(subcategory, '') || ' ' ||
            array_to_string(tags, ' ')
        )
    ) STORED;

-- ==========================================
-- SCRIPT VERSIONS (Mirrors directive_versions)
-- ==========================================
CREATE TABLE script_versions (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    script_id uuid NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
    version text NOT NULL,
    content text NOT NULL,  -- Actual Python code
    content_hash text NOT NULL,  -- SHA256 hash (first 16 chars)
    changelog text,
    is_latest boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    UNIQUE(script_id, version)
);

-- Semver validation function
CREATE OR REPLACE FUNCTION is_valid_semver(version text)
RETURNS boolean AS $$
BEGIN
    RETURN version ~ '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Add semver check constraint
ALTER TABLE script_versions
ADD CONSTRAINT valid_semver CHECK (is_valid_semver(version));

-- ==========================================
-- EXECUTIONS (Mirrors runs)
-- ==========================================
CREATE TABLE executions (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    script_name text NOT NULL,
    script_version text,
    
    -- Status
    status text NOT NULL CHECK (status IN ('success', 'error', 'timeout', 'cancelled', 'partial_success')),
    
    -- Execution details
    duration_sec numeric(10, 3),
    cost_usd numeric(10, 4),
    
    -- Data
    inputs jsonb,           -- Parameters passed to script
    outputs jsonb,          -- Results from script
    error text,             -- Error message if failed
    error_traceback text,   -- Full traceback
    
    -- Metrics
    api_calls_made integer,
    rows_processed integer,
    
    -- Context
    user_id uuid REFERENCES users(id),
    project_context jsonb,
    
    created_at timestamptz DEFAULT now()
);

-- ==========================================
-- LOCKFILES (Same as Context Kiwi)
-- ==========================================
CREATE TABLE lockfiles (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_hash text NOT NULL,
    user_id uuid REFERENCES users(id),
    locked_versions jsonb NOT NULL,  -- {"google_maps_scraper": "1.2.0", ...}
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- ==========================================
-- SCRIPT FEEDBACK
-- ==========================================
CREATE TABLE script_feedback (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    script_id uuid REFERENCES scripts(id) ON DELETE CASCADE,
    user_id uuid REFERENCES users(id),
    rating integer CHECK (rating >= 1 AND rating <= 5),
    comment text,
    issues jsonb,  -- Structured issue reports: [{"type": "bug", "description": "..."}]
    created_at timestamptz DEFAULT now()
);

-- ==========================================
-- INDEXES
-- ==========================================

-- Scripts
CREATE INDEX idx_scripts_name ON scripts(name);
CREATE INDEX idx_scripts_category ON scripts(category);
CREATE INDEX idx_scripts_subcategory ON scripts(subcategory);
CREATE INDEX idx_scripts_author ON scripts(author_id);
CREATE INDEX idx_scripts_official ON scripts(is_official) WHERE is_official = true;
CREATE INDEX idx_scripts_quality ON scripts(quality_score DESC);
CREATE INDEX idx_scripts_tsv ON scripts USING gin(tsv);
CREATE INDEX idx_scripts_tags ON scripts USING gin(tags);

-- Script versions
CREATE INDEX idx_script_versions_script ON script_versions(script_id);
CREATE INDEX idx_script_versions_latest ON script_versions(script_id) WHERE is_latest = true;

-- Executions
CREATE INDEX idx_executions_script_name ON executions(script_name);
CREATE INDEX idx_executions_status ON executions(status);
CREATE INDEX idx_executions_user ON executions(user_id);
CREATE INDEX idx_executions_created ON executions(created_at DESC);

-- Lockfiles
CREATE INDEX idx_lockfiles_project ON lockfiles(project_hash);
CREATE INDEX idx_lockfiles_user ON lockfiles(user_id);

-- Feedback
CREATE INDEX idx_feedback_script ON script_feedback(script_id);
CREATE INDEX idx_feedback_user ON script_feedback(user_id);
CREATE INDEX idx_feedback_rating ON script_feedback(rating);

-- ==========================================
-- TRIGGERS
-- ==========================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER scripts_updated_at
    BEFORE UPDATE ON scripts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER lockfiles_updated_at
    BEFORE UPDATE ON lockfiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ==========================================
-- FUNCTIONS
-- ==========================================

-- Search scripts (full-text + semantic)
CREATE OR REPLACE FUNCTION search_scripts(
    search_query text,
    search_category text DEFAULT NULL,
    limit_count integer DEFAULT 10
)
RETURNS TABLE (
    id uuid,
    name text,
    category text,
    description text,
    quality_score numeric,
    rank real
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id,
        s.name,
        s.category,
        s.description,
        s.quality_score,
        ts_rank(s.tsv, plainto_tsquery('english', search_query)) as rank
    FROM scripts s
    WHERE 
        s.tsv @@ plainto_tsquery('english', search_query)
        AND (search_category IS NULL OR s.category = search_category)
    ORDER BY rank DESC, s.quality_score DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Get latest script version
CREATE OR REPLACE FUNCTION get_latest_version(script_name_param text)
RETURNS TABLE (
    version text,
    content text,
    created_at timestamptz
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sv.version,
        sv.content,
        sv.created_at
    FROM script_versions sv
    JOIN scripts s ON s.id = sv.script_id
    WHERE s.name = script_name_param AND sv.is_latest = true
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Update script quality score based on feedback
CREATE OR REPLACE FUNCTION update_script_quality()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE scripts
    SET quality_score = (
        SELECT AVG(rating) / 5.0
        FROM script_feedback
        WHERE script_id = NEW.script_id
    )
    WHERE id = NEW.script_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER feedback_updates_quality
    AFTER INSERT OR UPDATE ON script_feedback
    FOR EACH ROW
    EXECUTE FUNCTION update_script_quality();

-- Update script success rate from executions
CREATE OR REPLACE FUNCTION update_script_metrics()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE scripts
    SET 
        success_rate = (
            SELECT 
                (COUNT(*) FILTER (WHERE status = 'success')::numeric / 
                 NULLIF(COUNT(*), 0)) * 100
            FROM executions
            WHERE script_name = NEW.script_name
        ),
        avg_execution_time_sec = (
            SELECT AVG(duration_sec)
            FROM executions
            WHERE script_name = NEW.script_name AND status = 'success'
        ),
        usage_count = (
            SELECT COUNT(*)
            FROM executions
            WHERE script_name = NEW.script_name
        ),
        last_used_at = NEW.created_at
    WHERE name = NEW.script_name;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER execution_updates_metrics
    AFTER INSERT ON executions
    FOR EACH ROW
    EXECUTE FUNCTION update_script_metrics();

-- ==========================================
-- ROW LEVEL SECURITY (RLS)
-- ==========================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE scripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE script_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE lockfiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE script_feedback ENABLE ROW LEVEL SECURITY;

-- Public scripts viewable by all
CREATE POLICY "Public scripts are viewable"
    ON scripts FOR SELECT
    USING (is_official = true);

-- Users can view their own scripts
CREATE POLICY "Users view own scripts"
    ON scripts FOR SELECT
    USING (auth.uid() = author_id);

-- Users can create scripts
CREATE POLICY "Users create scripts"
    ON scripts FOR INSERT
    WITH CHECK (auth.uid() = author_id);

-- Users can update their own scripts
CREATE POLICY "Users update own scripts"
    ON scripts FOR UPDATE
    USING (auth.uid() = author_id);

-- Script versions inherit script permissions
CREATE POLICY "View script versions"
    ON script_versions FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM scripts
            WHERE scripts.id = script_versions.script_id
            AND (scripts.is_official = true OR scripts.author_id = auth.uid())
        )
    );

-- Users can view their own executions
CREATE POLICY "Users view own executions"
    ON executions FOR SELECT
    USING (auth.uid() = user_id);

-- Users can create executions
CREATE POLICY "Users create executions"
    ON executions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can view/manage their lockfiles
CREATE POLICY "Users manage lockfiles"
    ON lockfiles FOR ALL
    USING (auth.uid() = user_id);

-- Users can provide feedback
CREATE POLICY "Users provide feedback"
    ON script_feedback FOR ALL
    USING (auth.uid() = user_id);

-- ==========================================
-- INITIAL DATA (Optional)
-- ==========================================

-- Create system user for official scripts
INSERT INTO users (id, username, email, trust_score)
VALUES (
    '00000000-0000-0000-0000-000000000000',
    'system',
    'system@script-kiwi.com',
    100
) ON CONFLICT (id) DO NOTHING;

-- ==========================================
-- COMMENTS
-- ==========================================

COMMENT ON TABLE scripts IS 'Registry of executable scripts';
COMMENT ON TABLE script_versions IS 'Version history for scripts (immutable)';
COMMENT ON TABLE executions IS 'Execution logs for script runs';
COMMENT ON TABLE lockfiles IS 'Version pinning per project';
COMMENT ON TABLE script_feedback IS 'User ratings and feedback';

COMMENT ON COLUMN scripts.module_path IS 'Python module path: execution.scraping.google_maps';
COMMENT ON COLUMN scripts.quality_score IS 'Quality score 0.0-1.0 based on feedback';
COMMENT ON COLUMN scripts.success_rate IS 'Percentage of successful executions';
COMMENT ON COLUMN executions.status IS 'success, error, timeout, cancelled, partial_success';
```

---

### 2.2 Knowledge Kiwi Database Schema

```sql
-- ============================================
-- KNOWLEDGE KIWI DATABASE SCHEMA
-- Personal knowledge base / Zettelkasten
-- ============================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Fuzzy text search

-- ==========================================
-- KNOWLEDGE ENTRIES
-- ==========================================
CREATE TABLE knowledge_entries (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Zettelkasten ID (your existing system)
    zettel_id text UNIQUE NOT NULL,  -- e.g., "001-apify-basics"
    
    -- Content
    title text NOT NULL,
    content text NOT NULL,
    content_format text DEFAULT 'markdown' CHECK (content_format IN ('markdown', 'text', 'code', 'json')),
    
    -- Categorization
    entry_type text NOT NULL CHECK (entry_type IN (
        'api_fact',      -- API documentation snippets
        'pattern',       -- Reusable patterns
        'concept',       -- Mental models
        'learning',      -- Things you've learned
        'experiment',    -- Experiment results
        'reference',     -- Quick reference notes
        'template',      -- Code/content templates
        'workflow'       -- Process documentation
    )),
    
    -- Source tracking
    source_type text CHECK (source_type IN (
        'youtube',
        'docs',
        'experiment',
        'manual',
        'chat',
        'book',
        'article',
        'course'
    )),
    source_url text,
    source_metadata jsonb,  -- {title, author, timestamp, etc.}
    
    -- Zettelkasten relationships
    links_to text[] DEFAULT '{}',  -- Array of zettel_ids
    tags text[] DEFAULT '{}',
    
    -- Vector search (OpenAI ada-002 or similar)
    embedding vector(1536),
    embedding_model text DEFAULT 'text-embedding-ada-002',
    embedding_updated_at timestamptz,
    
    -- Usage tracking
    accessed_count integer DEFAULT 0,
    last_accessed_at timestamptz,
    relevance_score numeric(3, 2) DEFAULT 0 CHECK (relevance_score >= 0 AND relevance_score <= 1),
    
    -- Metadata
    user_id uuid,  -- For multi-user setups
    is_public boolean DEFAULT false,
    
    -- File sync metadata
    file_path text,  -- Path in local filesystem
    file_hash text,  -- SHA256 of file content
    last_synced_at timestamptz,
    
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Full-text search support
ALTER TABLE knowledge_entries ADD COLUMN tsv tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english', 
            title || ' ' || 
            content || ' ' || 
            array_to_string(tags, ' ')
        )
    ) STORED;

-- ==========================================
-- KNOWLEDGE RELATIONSHIPS
-- ==========================================
CREATE TABLE knowledge_relationships (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_entry_id uuid REFERENCES knowledge_entries(id) ON DELETE CASCADE,
    to_entry_id uuid REFERENCES knowledge_entries(id) ON DELETE CASCADE,
    
    relationship_type text NOT NULL CHECK (relationship_type IN (
        'references',    -- A → B: A mentions B
        'contradicts',   -- A ⊗ B: A disagrees with B
        'extends',       -- A ⊃ B: A builds on B
        'implements',    -- A ⇒ B: A is implementation of B concept
        'supersedes',    -- A ⇨ B: A replaces/updates B
        'depends_on',    -- A → B: A requires understanding B first
        'related',       -- A ↔ B: General relationship
        'example_of'     -- A is example of B
    )),
    
    strength numeric(3, 2) DEFAULT 1.0 CHECK (strength >= 0 AND strength <= 1),
    notes text,
    
    created_at timestamptz DEFAULT now(),
    UNIQUE(from_entry_id, to_entry_id, relationship_type)
);

-- ==========================================
-- KNOWLEDGE COLLECTIONS
-- ==========================================
CREATE TABLE knowledge_collections (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name text NOT NULL,
    description text,
    tags text[] DEFAULT '{}',
    entry_ids uuid[] DEFAULT '{}',  -- Ordered list
    
    -- Collection type
    collection_type text CHECK (collection_type IN (
        'topic',         -- Topic-based grouping
        'project',       -- Project-specific knowledge
        'learning_path', -- Ordered learning sequence
        'reference',     -- Quick reference collection
        'archive'        -- Archived/deprecated notes
    )),
    
    is_public boolean DEFAULT false,
    user_id uuid,
    
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- ==========================================
-- KNOWLEDGE QUERIES (Analytics)
-- ==========================================
CREATE TABLE knowledge_queries (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text text NOT NULL,
    query_type text CHECK (query_type IN ('semantic', 'fulltext', 'hybrid', 'graph')),
    query_embedding vector(1536),
    
    -- Results
    results_count integer,
    results_returned jsonb,  -- Array of entry IDs with scores
    results_clicked uuid[],  -- Which entries were actually used
    
    -- Context
    user_id uuid,
    session_id uuid,
    
    created_at timestamptz DEFAULT now()
);

-- ==========================================
-- SYNC LOG (Track file ↔ DB sync)
-- ==========================================
CREATE TABLE sync_log (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    sync_type text NOT NULL CHECK (sync_type IN ('push', 'pull', 'bidirectional')),
    direction text CHECK (direction IN ('file_to_db', 'db_to_file')),
    
    -- Files affected
    files_synced integer DEFAULT 0,
    files_added integer DEFAULT 0,
    files_modified integer DEFAULT 0,
    files_deleted integer DEFAULT 0,
    
    -- Entries affected
    entries_synced integer DEFAULT 0,
    entries_added integer DEFAULT 0,
    entries_modified integer DEFAULT 0,
    entries_deleted integer DEFAULT 0,
    
    -- Status
    status text CHECK (status IN ('success', 'partial', 'error')),
    error_message text,
    
    -- Timing
    duration_sec numeric(10, 3),
    
    user_id uuid,
    created_at timestamptz DEFAULT now()
);

-- ==========================================
-- INDEXES
-- ==========================================

-- Knowledge entries
CREATE INDEX idx_knowledge_zettel ON knowledge_entries(zettel_id);
CREATE INDEX idx_knowledge_type ON knowledge_entries(entry_type);
CREATE INDEX idx_knowledge_source ON knowledge_entries(source_type);
CREATE INDEX idx_knowledge_user ON knowledge_entries(user_id);
CREATE INDEX idx_knowledge_public ON knowledge_entries(is_public) WHERE is_public = true;

-- Vector similarity search (IVFFlat index for large datasets)
CREATE INDEX idx_knowledge_embedding ON knowledge_entries 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Full-text search
CREATE INDEX idx_knowledge_tsv ON knowledge_entries USING gin(tsv);

-- Tag search
CREATE INDEX idx_knowledge_tags ON knowledge_entries USING gin(tags);

-- Link search
CREATE INDEX idx_knowledge_links ON knowledge_entries USING gin(links_to);

-- Fuzzy search on zettel_id
CREATE INDEX idx_knowledge_zettel_trgm ON knowledge_entries USING gin(zettel_id gin_trgm_ops);

-- Relationships
CREATE INDEX idx_relationships_from ON knowledge_relationships(from_entry_id);
CREATE INDEX idx_relationships_to ON knowledge_relationships(to_entry_id);
CREATE INDEX idx_relationships_type ON knowledge_relationships(relationship_type);

-- Collections
CREATE INDEX idx_collections_type ON knowledge_collections(collection_type);
CREATE INDEX idx_collections_user ON knowledge_collections(user_id);
CREATE INDEX idx_collections_entries ON knowledge_collections USING gin(entry_ids);
CREATE INDEX idx_collections_tags ON knowledge_collections USING gin(tags);

-- Queries (analytics)
CREATE INDEX idx_queries_user ON knowledge_queries(user_id);
CREATE INDEX idx_queries_session ON knowledge_queries(session_id);
CREATE INDEX idx_queries_created ON knowledge_queries(created_at DESC);

-- Sync log
CREATE INDEX idx_sync_log_type ON sync_log(sync_type);
CREATE INDEX idx_sync_log_created ON sync_log(created_at DESC);

-- ==========================================
-- TRIGGERS
-- ==========================================

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER knowledge_entries_updated_at
    BEFORE UPDATE ON knowledge_entries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER knowledge_collections_updated_at
    BEFORE UPDATE ON knowledge_collections
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Update embedding timestamp when embedding changes
CREATE OR REPLACE FUNCTION update_embedding_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.embedding IS DISTINCT FROM OLD.embedding THEN
        NEW.embedding_updated_at = now();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER knowledge_entries_embedding_updated
    BEFORE UPDATE ON knowledge_entries
    FOR EACH ROW
    EXECUTE FUNCTION update_embedding_timestamp();

-- ==========================================
-- SEARCH FUNCTIONS
-- ==========================================

-- Semantic search (vector similarity)
CREATE OR REPLACE FUNCTION search_knowledge_semantic(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.7,
    match_count integer DEFAULT 10,
    filter_type text DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    zettel_id text,
    title text,
    content text,
    entry_type text,
    similarity float,
    tags text[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        k.id,
        k.zettel_id,
        k.title,
        k.content,
        k.entry_type,
        1 - (k.embedding <=> query_embedding) as similarity,
        k.tags
    FROM knowledge_entries k
    WHERE 
        k.embedding IS NOT NULL
        AND 1 - (k.embedding <=> query_embedding) > match_threshold
        AND (filter_type IS NULL OR k.entry_type = filter_type)
    ORDER BY k.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Full-text search
CREATE OR REPLACE FUNCTION search_knowledge_fulltext(
    search_query text,
    match_count integer DEFAULT 10,
    filter_type text DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    zettel_id text,
    title text,
    content text,
    entry_type text,
    rank real,
    tags text[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        k.id,
        k.zettel_id,
        k.title,
        k.content,
        k.entry_type,
        ts_rank(k.tsv, plainto_tsquery('english', search_query)) as rank,
        k.tags
    FROM knowledge_entries k
    WHERE 
        k.tsv @@ plainto_tsquery('english', search_query)
        AND (filter_type IS NULL OR k.entry_type = filter_type)
    ORDER BY rank DESC
    LIMIT match_count;
END;
$$;

-- Hybrid search (semantic + full-text)
CREATE OR REPLACE FUNCTION search_knowledge_hybrid(
    search_query text,
    query_embedding vector(1536),
    match_count integer DEFAULT 10,
    semantic_weight float DEFAULT 0.7,
    filter_type text DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    zettel_id text,
    title text,
    content text,
    entry_type text,
    combined_score float,
    tags text[]
)
LANGUAGE plpgsql
AS $$
DECLARE
    fulltext_weight float := 1.0 - semantic_weight;
BEGIN
    RETURN QUERY
    SELECT
        k.id,
        k.zettel_id,
        k.title,
        k.content,
        k.entry_type,
        (
            (1 - (k.embedding <=> query_embedding)) * semantic_weight +
            (ts_rank(k.tsv, plainto_tsquery('english', search_query)) / 0.1) * fulltext_weight
        ) as combined_score,
        k.tags
    FROM knowledge_entries k
    WHERE 
        k.embedding IS NOT NULL
        AND (
            k.tsv @@ plainto_tsquery('english', search_query)
            OR 1 - (k.embedding <=> query_embedding) > 0.6
        )
        AND (filter_type IS NULL OR k.entry_type = filter_type)
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$;

-- Graph traversal (find related entries via relationships)
CREATE OR REPLACE FUNCTION find_related_entries(
    entry_id_param uuid,
    max_depth integer DEFAULT 2,
    min_strength float DEFAULT 0.5,
    max_results integer DEFAULT 20
)
RETURNS TABLE (
    id uuid,
    zettel_id text,
    title text,
    entry_type text,
    relationship_path text[],
    total_strength float,
    depth integer
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE related AS (
        -- Base case: direct relationships
        SELECT
            ke.id,
            ke.zettel_id,
            ke.title,
            ke.entry_type,
            ARRAY[kr.relationship_type] as relationship_path,
            kr.strength as total_strength,
            1 as depth
        FROM knowledge_relationships kr
        JOIN knowledge_entries ke ON kr.to_entry_id = ke.id
        WHERE kr.from_entry_id = entry_id_param
            AND kr.strength >= min_strength
        
        UNION ALL
        
        -- Recursive case: follow relationships
        SELECT
            ke.id,
            ke.zettel_id,
            ke.title,
            ke.entry_type,
            r.relationship_path || kr.relationship_type,
            r.total_strength * kr.strength,
            r.depth + 1
        FROM related r
        JOIN knowledge_relationships kr ON kr.from_entry_id = r.id
        JOIN knowledge_entries ke ON kr.to_entry_id = ke.id
        WHERE r.depth < max_depth
            AND kr.strength >= min_strength
            AND ke.id != entry_id_param  -- Prevent returning source
            AND NOT ke.id = ANY(  -- Prevent cycles
                SELECT DISTINCT from_entry_id 
                FROM knowledge_relationships 
                WHERE to_entry_id = entry_id_param
            )
    )
    SELECT DISTINCT ON (r.id) 
        r.id,
        r.zettel_id,
        r.title,
        r.entry_type,
        r.relationship_path,
        r.total_strength,
        r.depth
    FROM related r
    ORDER BY r.id, r.total_strength DESC, r.depth ASC
    LIMIT max_results;
END;
$$;

-- Get entry by zettel_id with related entries
CREATE OR REPLACE FUNCTION get_entry_with_context(
    zettel_id_param text
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    result jsonb;
    entry_uuid uuid;
BEGIN
    -- Get the entry
    SELECT id INTO entry_uuid
    FROM knowledge_entries
    WHERE zettel_id = zettel_id_param;
    
    IF entry_uuid IS NULL THEN
        RETURN NULL;
    END IF;
    
    -- Build result with entry + related entries
    SELECT jsonb_build_object(
        'entry', row_to_json(ke.*),
        'related', (
            SELECT jsonb_agg(row_to_json(r.*))
            FROM find_related_entries(entry_uuid, 1, 0.5, 10) r
        ),
        'backlinks', (
            SELECT jsonb_agg(jsonb_build_

object(
                'zettel_id', ke2.zettel_id,
                'title', ke2.title,
                'relationship_type', kr.relationship_type
            ))
            FROM knowledge_relationships kr
            JOIN knowledge_entries ke2 ON kr.from_entry_id = ke2.id
            WHERE kr.to_entry_id = entry_uuid
        )
    ) INTO result
    FROM knowledge_entries ke
    WHERE ke.id = entry_uuid;
    
    RETURN result;
END;
$$;

-- ==========================================
-- ROW LEVEL SECURITY (RLS)
-- ==========================================

ALTER TABLE knowledge_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_log ENABLE ROW LEVEL SECURITY;

-- For single-user setup (simpler)
CREATE POLICY "Enable all for authenticated users"
    ON knowledge_entries FOR ALL
    USING (auth.uid() IS NOT NULL OR is_public = true)
    WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Enable relationships for authenticated"
    ON knowledge_relationships FOR ALL
    USING (auth.uid() IS NOT NULL)
    WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Enable collections for authenticated"
    ON knowledge_collections FOR ALL
    USING (auth.uid() IS NOT NULL OR is_public = true)
    WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Enable queries for authenticated"
    ON knowledge_queries FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Enable sync_log for authenticated"
    ON sync_log FOR ALL
    USING (auth.uid() IS NOT NULL)
    WITH CHECK (auth.uid() IS NOT NULL);

-- ==========================================
-- COMMENTS
-- ==========================================

COMMENT ON TABLE knowledge_entries IS 'Personal knowledge base entries (Zettelkasten)';
COMMENT ON TABLE knowledge_relationships IS 'Explicit relationships between knowledge entries';
COMMENT ON TABLE knowledge_collections IS 'Grouped collections of related entries';
COMMENT ON TABLE knowledge_queries IS 'Search query analytics';
COMMENT ON TABLE sync_log IS 'File system sync history';

COMMENT ON COLUMN knowledge_entries.zettel_id IS 'Unique Zettelkasten ID (e.g., "001-apify-basics")';
COMMENT ON COLUMN knowledge_entries.embedding IS 'Vector embedding for semantic search (1536 dimensions)';
COMMENT ON COLUMN knowledge_relationships.strength IS 'Relationship strength 0.0-1.0';
```

---

## Part 3: File System Structure

```bash
# Create the complete directory structure

# ==========================================
# SCRIPT KIWI
# ==========================================
mkdir -p ~/projects/script-kiwi
cd ~/projects/script-kiwi

# Project structure
mkdir -p script_kiwi/{execution/{scraping,enrichment,extraction,validation,maintenance,utility},api,tools,directives,config,utils}
mkdir -p tests/{execution,api,tools}
mkdir -p docs/{guides,examples}
mkdir -p .ai/{directives/custom,scripts,patterns}
mkdir -p .script-kiwi/scripts/{scraping,enrichment,extraction,validation,maintenance,utility}

# Create __init__.py files
touch script_kiwi/__init__.py
touch script_kiwi/execution/__init__.py
touch script_kiwi/execution/{scraping,enrichment,extraction,validation,maintenance,utility}/__init__.py
touch script_kiwi/api/__init__.py
touch script_kiwi/tools/__init__.py
touch script_kiwi/tools/__init__.py

# ==========================================
# KNOWLEDGE KIWI
# ==========================================
mkdir -p ~/projects/knowledge-kiwi
cd ~/projects/knowledge-kiwi

# Project structure
mkdir -p src/knowledge-kiwi-mcp/{api,tools,sync,utils}
mkdir -p tests/{api,tools,sync}
mkdir -p docs/{guides,examples}
mkdir -p knowledge/base/{apis,patterns,concepts,learnings,experiments,references,templates,workflows}
mkdir -p knowledge/{embeddings,cache,index}
mkdir -p .knowledge-kiwi/{cache,config}
mkdir -p .ai/directives/custom

# Create __init__.py files
touch src/knowledge-kiwi-mcp/__init__.py
touch src/knowledge-kiwi-mcp/{api,tools,sync,utils}/__init__.py

# ==========================================
# USER SPACE (HOME DIRECTORY)
# ==========================================
mkdir -p ~/.context-kiwi/{directives,cache}
mkdir -p ~/.script-kiwi/scripts/{scraping,enrichment,extraction,validation,maintenance,utility}
mkdir -p ~/.knowledge-kiwi/{cache,config}
```

---

## Part 4: Script Kiwi MCP Implementation

### 4.1 Project Configuration

```toml
# ~/projects/script-kiwi/pyproject.toml

[project]
name = "script-kiwi"
version = "0.1.0"
description = "Script execution MCP server with directive-based architecture"
authors = [{name = "Your Name", email = "you@example.com"}]
readme = "README.md"
requires-python = ">=3.10"

dependencies = [
    "mcp>=0.1.0",
    "supabase>=2.0.0",
    "httpx>=0.25.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "apify-client>=1.7.0",
    "beautifulsoup4>=4.12.0",
    "requests>=2.31.0",
    "aiofiles>=23.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]

[build-system]
requires = ["setuptools>=68.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.black]
line-length = 100
target-version = ['py310']

[tool.ruff]
line-length = 100
target-version = "py310"
```

### 4.2 Environment Configuration

```bash
# ~/projects/script-kiwi/.env.example

# Supabase (Script Kiwi DB)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=your-service-role-key

# External APIs
APIFY_API_TOKEN=your-apify-token
ANYMAILFINDER_API_KEY=your-anymailfinder-key
LEAD_MAGIC_API_KEY=your-leadmagic-key

# OpenAI (for embeddings if needed)
OPENAI_API_KEY=your-openai-key

# Server
SERVER_NAME=script-kiwi
LOG_LEVEL=INFO
```

### 4.3 Core MCP Server

```python
# ~/projects/script-kiwi/script_kiwi/server.py

import os
import sys
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_env()

# Import tools
from .tools import (
    SearchTool,
    LoadTool,
    RunTool,
    PublishTool,
    HelpTool
)

class ScriptKiwiMCP:
    """Script execution MCP server with directive-based architecture"""
    
    def __init__(self):
        self.server = Server("script-kiwi")
        self.setup_tools()
    
    def setup_tools(self):
        """Register the 6 core tools"""
        
        # Tool search
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="search",
                    description="Search for scripts by intent or keywords. Returns matching scripts with confidence scores.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Natural language query or keywords (e.g., 'scrape Google Maps', 'enrich emails')"
                            },
                            "category": {
                                "type": "string",
                                "enum": ["scraping", "enrichment", "extraction", "validation", "maintenance", "utility", "all"],
                                "description": "Filter by script category"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 10
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="load",
                    description="Load complete specification and directive for a script. Returns inputs, process, examples.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "script_name": {
                                "type": "string",
                                "description": "Name of the script to load"
                            },
                            "sections": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Specific sections to load (inputs, process, examples, all)",
                                "default": ["all"]
                            }
                        },
                        "required": ["script_name"]
                    }
                ),
                Tool(
                    name="run",
                    description="Run a script with validation and progressive disclosure. Handles pre-flight checks.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "script_name": {
                                "type": "string",
                                "description": "Name of the script to execute"
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Parameters to pass to the script"
                            },
                            "dry_run": {
                                "type": "boolean",
                                "description": "If true, validate inputs but don't execute",
                                "default": False
                            }
                        },
                        "required": ["script_name", "parameters"]
                    }
                ),
                Tool(
                    name="publish",
                    description="Publish a script to the registry with versioning.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "script_name": {
                                "type": "string",
                                "description": "Name of the script to publish"
                            },
                            "version": {
                                "type": "string",
                                "description": "Semver version (e.g., '1.2.0')"
                            },
                            "category": {
                                "type": "string",
                                "enum": ["scraping", "enrichment", "extraction", "validation", "maintenance", "utility"]
                            }
                        },
                        "required": ["script_name", "version"]
                    }
                ),
                Tool(
                    name="help",
                    description="Get workflow guidance, examples, and troubleshooting for scripts.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "What do you need help with?"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context about your situation"
                            }
                        },
                        "required": ["query"]
                    }
                )
            ]
        
        # Tool execution
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            if name == "search":
                tool = SearchTool()
                result = await tool.execute(arguments)
            elif name == "load":
                tool = LoadTool()
                result = await tool.execute(arguments)
            elif name == "run":
                tool = RunTool()
                result = await tool.execute(arguments)
            elif name == "publish":
                tool = PublishTool()
                result = await tool.execute(arguments)
            elif name == "help":
                tool = HelpTool()
                result = await tool.execute(arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
            
            return [TextContent(type="text", text=result)]
    
    async def run(self):
        """Start the MCP server"""
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )

def main():
    """Entry point for the MCP server"""
    server = ScriptKiwiMCP()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()
```

### 4.4 Core Tools Implementation

```python
# ~/projects/script-kiwi/script_kiwi/tools/search.py

from typing import Dict, List, Any
from ...api.script_registry import ScriptRegistry
import json

class SearchTool:
    """Search for scripts by intent or keywords"""
    
    def __init__(self):
        self.registry = ScriptRegistry()
    
    async def execute(self, params: Dict[str, Any]) -> str:
        """
        Search scripts across all tiers (remote, user, project)
        
        Args:
            query: Search query
            category: Optional category filter
            limit: Max results
        
        Returns:
            JSON string with matching scripts and confidence scores
        """
        query = params.get("query", "")
        category = params.get("category", "all")
        limit = params.get("limit", 10)
        
        if not query:
            return json.dumps({
                "error": "Query is required",
                "suggestion": "Try: search({'query': 'scrape Google Maps'})"
            })
        
        # Search all tiers
        results = await self.registry.search_scripts(
            query=query,
            category=None if category == "all" else category,
            limit=limit
        )
        
        # Format results
        formatted = []
        for script in results:
            formatted.append({
                "name": script["name"],
                "category": script["category"],
                "description": script["description"],
                "confidence": script.get("rank", 0.5),
                "tier": script.get("tier", "core"),
                "quality_score": script.get("quality_score", 0),
                "success_rate": script.get("success_rate"),
                "estimated_cost": script.get("estimated_cost_usd"),
            })
        
        return json.dumps({
            "query": query,
            "results_count": len(formatted),
            "results": formatted,
            "next_steps": [
                "Use load({'script_name': '...'}) to see details",
                "Use run({'script_name': '...', 'params': {...}}) to run"
            ]
        }, indent=2)
```

```python
# ~/projects/script-kiwi/script_kiwi/tools/load.py

from typing import Dict, Any
from ...api.script_registry import ScriptRegistry
from ...api.directive_loader import DirectiveLoader
import json

class LoadTool:
    """Load script specification and directive"""
    
    def __init__(self):
        self.registry = ScriptRegistry()
        self.directive_loader = DirectiveLoader()
    
    async def execute(self, params: Dict[str, Any]) -> str:
        """
        Load script details and associated directive
        
        Args:
            script_name: Name of script
            sections: Which sections to load (inputs, process, examples, all)
        
        Returns:
            JSON with script spec and directive content
        """
        script_name = params.get("script_name", "")
        sections = params.get("sections", ["all"])
        
        if not script_name:
            return json.dumps({
                "error": "script_name is required"
            })
        
        # Get script from registry
        script = await self.registry.get_script(script_name)
        if not script:
            return json.dumps({
                "error": f"Script not found: {script_name}",
                "suggestion": "Use search({'query': '...'}) to find available scripts"
            })
        
        # Load associated directive (if exists)
        directive = await self.directive_loader.load_for_script(script_name)
        
        # Build response based on requested sections
        response = {
            "script": {
                "name": script["name"],
                "category": script["category"],
                "description": script["description"],
                "module_path": script["module_path"],
                "version": script.get("version", "unknown"),
                "quality_score": script.get("quality_score", 0),
                "success_rate": script.get("success_rate"),
            }
        }
        
        if "all" in sections or "inputs" in sections:
            response["inputs"] = directive.get("inputs", {}) if directive else {}
        
        if "all" in sections or "process" in sections:
            response["process"] = directive.get("process", "") if directive else ""
        
        if "all" in sections or "examples" in sections:
            response["examples"] = directive.get("examples", []) if directive else []
        
        if "all" in sections or "cost" in sections:
            response["cost_estimate"] = {
                "base_cost_usd": script.get("estimated_cost_usd"),
                "cost_per_unit": script.get("cost_per_unit"),
                "cost_unit": script.get("cost_unit"),
            }
        
        if "all" in sections or "dependencies" in sections:
            response["dependencies"] = {
                "packages": script.get("required_packages", []),
                "env_vars": script.get("required_env_vars", []),
                "scripts": script.get("required_scripts", []),
            }
        
        response["next_steps"] = [
            "Review the inputs and provide required parameters",
            f"Use run({{'script_name': '{script_name}', 'params': {{...}}}}) to run",
            "Use dry_run=true to validate without executing"
        ]
        
        return json.dumps(response, indent=2)
```

```python
# ~/projects/script-kiwi/script_kiwi/tools/run.py

from typing import Dict, Any
import importlib
import json
from ...api.script_registry import ScriptRegistry
from ...api.execution_logger import ExecutionLogger

class RunTool:
    """Execute scripts with validation and progressive disclosure"""
    
    def __init__(self):
        self.registry = ScriptRegistry()
        self.logger = ExecutionLogger()
    
    async def execute(self, params: Dict[str, Any]) -> str:
        """
        Execute a script with pre-flight checks
        
        Args:
            script_name: Name of script to run
            parameters: Script parameters
            dry_run: If true, validate only
        
        Returns:
            JSON with execution results or validation errors
        """
        script_name = params.get("script_name", "")
        script_params = params.get("parameters", {})
        dry_run = params.get("dry_run", False)
        
        if not script_name:
            return json.dumps({"error": "script_name is required"})
        
        # Get script metadata
        script = await self.registry.get_script(script_name)
        if not script:
            return json.dumps({
                "error": f"Script not found: {script_name}"
            })
        
        # Pre-flight checks
        validation = await self._validate_inputs(script, script_params)
        if not validation["valid"]:
            return json.dumps({
                "status": "validation_failed",
                "errors": validation["errors"],
                "missing_inputs": validation["missing"],
                "suggestions": validation["suggestions"]
            })
        
        # Dry run stops here
        if dry_run:
            return json.dumps({
                "status": "validation_passed",
                "message": "Script is ready to execute",
                "estimated_cost": script.get("estimated_cost_usd"),
                "estimated_time": script.get("estimated_time_seconds"),
            })
        
        # Import and execute
        try:
            execution_id = await self.logger.start_execution(
                script_name=script_name,
                script_version=script.get("version"),
                params=script_params
            )
            
            # Dynamic import
            module_path = script["module_path"]
            module = importlib.import_module(f"script_kiwi.{module_path}")
            
            # Execute (script must implement execute(params: dict) -> dict)
            if hasattr(module, 'execute'):
            result = await module.execute(script_params)
            elif hasattr(module, 'main'):
                result = await module.main(script_params)
            else:
                raise ValueError(f"Script {script_name} has no execute() or main() function")
            
            # Log success
            await self.logger.complete_execution(
                execution_id=execution_id,
                status="success",
                result=result
            )
            
            return json.dumps({
                "status": "success",
                "execution_id": str(execution_id),
                "result": result,
                "metrics": {
                    "duration_sec": result.get("duration_sec"),
                    "cost_usd": result.get("cost_usd"),
                    "rows_processed": result.get("rows_processed"),
                }
            }, indent=2)
            
        except Exception as e:
            # Log error
            await self.logger.complete_execution(
                execution_id=execution_id,
                status="error",
                error=str(e)
            )
            
            return json.dumps({
                "status": "error",
                "execution_id": str(execution_id),
                "error": str(e),
                "troubleshooting": [
                    "Check error message above",
                    "Verify all required environment variables are set",
                    "Use help() tool for guidance"
                ]
            })
    
    async def _validate_inputs(self, script: Dict, params: Dict) -> Dict:
        """Validate script inputs"""
        # This would check required params, types, etc.
        # Placeholder implementation
        return {
            "valid": True,
            "errors": [],
            "missing": [],
            "suggestions": []
        }
```

```python
# ~/projects/script-kiwi/script_kiwi/tools/help.py

from typing import Dict, Any
import json

class HelpTool:
    """Provide workflow guidance and troubleshooting"""
    
    async def execute(self, params: Dict[str, Any]) -> str:
        """
        Get help with scripts and workflows
        
        Args:
            query: What you need help with
            context: Additional context
        
        Returns:
            Helpful guidance and examples
        """
        query = params.get("query", "").lower()
        context = params.get("context", "")
        
        # Pattern matching for common queries
        if "scrape" in query or "leads" in query:
            return self._help_scraping()
        elif "email" in query or "enrich" in query:
            return self._help_enrichment()
        elif "workflow" in query or "campaign" in query:
            return self._help_workflow()
        else:
            return self._help_general()
    
    def _help_scraping(self) -> str:
        return json.dumps({
            "topic": "Lead Scraping",
            "workflow": [
                "1. Search for scraping script: search({'query': 'scrape Google Maps'})",
                "2. Load script details: load({'script_name': 'google_maps_leads'})",
                "3. Run with params: run({'script_name': 'google_maps_leads', 'params': {search_term: '...', location: '...'}})",
                "4. Results saved to execution log"
            ],
            "common_scripts": [
                "google_maps_leads - Scrape local businesses from Google Maps",
                "linkedin_scraper - Extract LinkedIn profiles",
                "website_crawler - Crawl and extract from websites"
            ],
            "tips": [
                "Start with small counts (10-50) to test",
                "Check cost estimates before large runs",
                "Use location splitting for >1000 results"
            ],
            "examples": [
                {
                    "task": "Scrape 100 dentists in Texas",
                    "steps": [
                        "search({'query': 'google maps dentist'})",
                        "load({'script_name': 'google_maps_leads'})",
                        "run({'script_name': 'google_maps_leads', 'params': {search_term: 'dentist', location: 'Texas', count: 100}})"
                    ]
                }
            ]
        }, indent=2)
    
    def _help_enrichment(self) -> str:
        return json.dumps({
            "topic": "Email Enrichment",
            "workflow": [
                "1. Have leads with company names/domains",
                "2. Search: search({'query': 'enrich emails'})",
                "3. Load: load({'script_name': 'email_waterfall'})",
                "4. Run: run({'script_name': 'email_waterfall', 'params': {leads: [...]}})",
                "5. Get results with enriched emails"
            ],
            "strategies": {
                "waterfall": "Try multiple sources (cost-effective)",
                "premium": "Use best source first (fastest)",
                "validation_only": "Just validate existing emails"
            },
            "tips": [
                "Waterfall strategy saves money (starts with free methods)",
                "Success rate typically 70-90% for business emails",
                "Always validate before sending campaigns"
            ]
        }, indent=2)
    
    def _help_workflow(self) -> str:
        return json.dumps({
            "topic": "Complete Outbound Campaign Workflow",
            "steps": [
                {
                    "phase": "1. Lead Generation",
                    "scripts": ["google_maps_leads", "linkedin_scraper"],
                    "output": "List of companies with contact info"
                },
                {
                    "phase": "2. Email Enrichment",
                    "scripts": ["email_waterfall", "email_validation"],
                    "output": "Valid email addresses"
                },
                {
                    "phase": "3. Research (use web_search via Anthropic API)",
                    "action": "Research each company for personalization",
                    "output": "Company insights stored in Knowledge Kiwi"
                },
                {
                    "phase": "4. Campaign Creation (use Campaign Kiwi MCP)",
                    "action": "Create campaign and generate emails",
                    "output": "Personalized emails ready to send"
                },
                {
                    "phase": "5. Monitoring (use Campaign Kiwi MCP)",
                    "action": "Track sends, opens, replies",
                    "output": "Campaign analytics"
                }
            ],
            "example_prompt": "Find 500 SaaS founders in Austin, enrich emails, research companies, create personalized campaign"
        }, indent=2)
    
    def _help_general(self) -> str:
        return json.dumps({
            "available_tools": [
                "search - Find scripts by intent",
                "load - Get script details",
                "run - Run a script",
                "publish - Publish script to registry",
                "help - Get guidance (this tool)"
            ],
            "script_categories": [
                "scraping - Extract data from web",
                "enrichment - Add emails, contacts",
                "extraction - YouTube, docs, GitHub",
                "validation - Check data quality",
                "maintenance - Cleanup, reports",
                "utility - Helper functions"
            ],
            "getting_started": [
                "1. Use search() to find what you need",
                "2. Use load() to see how to use it",
                "3. Use run() to execute it",
                "4. Use publish() to share scripts",
                "5. Use help() if you get stuck"
            ],
            "tips": [
                "All scripts have cost estimates",
                "Use dry_run=true to test without executing",
                "Check execution logs for history"
            ]
        }, indent=2)
```

---

## Part 5: Knowledge Kiwi MCP Implementation

### 5.1 Project Configuration

```toml
# ~/projects/knowledge-kiwi/pyproject.toml

[project]
name = "knowledge-kiwi-mcp"
version = "0.1.0"
description = "Knowledge base MCP server with Zettelkasten support"
authors = [{name = "Your Name", email = "you@example.com"}]
readme = "README.md"
requires-python = ">=3.10"

dependencies = [
    "mcp>=0.1.0",
    "supabase>=2.0.0",
    "httpx>=0.25.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "openai>=1.0.0",  # For embeddings
    "markdown>=3.5.0",
    "pyyaml>=6.0.0",
    "aiofiles>=23.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]

[build-system]
requires = ["setuptools>=68.0.0", "wheel"]
build-backend = "setuptools.build_meta"
```

### 5.2 Core MCP Server

```python
# ~/projects/knowledge-kiwi/src/knowledge-kiwi-mcp/server.py

import os
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent
import asyncio
from dotenv import load_dotenv

load_dotenv()

from .tools import (
    CreateEntryTool,
    GetEntryTool,
    UpdateEntryTool,
    DeleteEntryTool,
    SearchKnowledgeTool,
    LinkEntriesTool,
    CreateCollectionTool,
    SyncToDatabaseTool,
    SyncFromDatabaseTool,
)

class KnowledgeKiwiMCP:
    """Knowledge base MCP server with Zettelkasten support"""
    
    def __init__(self):
        self.server = Server("knowledge-kiwi-mcp")
        self.setup_tools()
    
    def setup_tools(self):
        """Register knowledge management tools"""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="create_entry",
                    description="Create a new knowledge entry in your Zettelkasten",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "zettel_id": {"type": "string", "description": "Unique ID (e.g., '042-email-deliverability')"},
                            "title": {"type": "string"},
                            "content": {"type": "string"},
                            "entry_type": {
                                "type": "string",
                                "enum": ["api_fact", "pattern", "concept", "learning", "experiment", "reference", "template", "workflow"]
                            },
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "source_type": {"type": "string", "enum": ["youtube", "docs", "experiment", "manual", "chat", "book", "article"]},
                            "source_url": {"type": "string"},
                        },
                        "required": ["zettel_id", "title", "content", "entry_type"]
                    }
                ),
                Tool(
                    name="get_entry",
                    description="Get a knowledge entry by zettel_id, with related entries and backlinks",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "zettel_id": {"type": "string"}
                        },
                        "required": ["zettel_id"]
                    }
                ),
                Tool(
                    name="update_entry",
                    description="Update an existing knowledge entry",
                    inputSchema={
                        "type": "object",
