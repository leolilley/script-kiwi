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
    
    -- Categorization (dynamic - user/LLM decides)
    category text NOT NULL,  -- Any category name (e.g., 'scraping', 'data-processing', 'api-integration')
    subcategory text,        -- Optional nested category (e.g., 'google-maps', 'email-finding')
    description text,
    
    -- Metadata (like directives)
    author_id uuid REFERENCES users(id),
    is_official boolean DEFAULT false,
    download_count integer DEFAULT 0,
    quality_score numeric(3, 2) DEFAULT 0 CHECK (quality_score >= 0 AND quality_score <= 1),
    
    -- Status
    deprecated boolean DEFAULT false,
    deprecated_reason text,
    
    -- Script-specific
    module_path text NOT NULL,  -- 'execution.scraping.google_maps'
    
    -- Dependencies
    tech_stack jsonb DEFAULT '[]',           -- ['python', 'apify']
    dependencies jsonb DEFAULT '[]',         -- [{"name": "apify-client", "version": ">=0.1.0"}]
    required_env_vars jsonb DEFAULT '[]',    -- ['APIFY_API_TOKEN']
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
    tags jsonb DEFAULT '[]',
    
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
    success_rate numeric,
    rank numeric
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id,
        s.name,
        s.category,
        s.description,
        s.quality_score,
        s.success_rate,
        ts_rank(s.search_vector, plainto_tsquery('english', search_query))::numeric as rank
    FROM scripts s
    WHERE 
        (search_category IS NULL OR s.category = search_category)
        AND s.search_vector @@ plainto_tsquery('english', search_query)
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