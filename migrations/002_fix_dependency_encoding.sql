-- Migration: Fix dependency metadata schema and corrupted data
-- 
-- Problem: `dependencies` and `tech_stack` columns were created as `text[]` instead of `jsonb`
-- This caused double-encoding: dict objects were serialized to JSON strings, then stored as text[] elements
--
-- Solution:
-- 1. Convert column types from text[] to jsonb
-- 2. Parse the JSON-encoded strings back into proper objects

-- Step 1: Drop defaults (they're text[] defaults that won't work with jsonb)
ALTER TABLE scripts ALTER COLUMN dependencies DROP DEFAULT;
ALTER TABLE scripts ALTER COLUMN tech_stack DROP DEFAULT;
ALTER TABLE scripts ALTER COLUMN required_env_vars DROP DEFAULT;
ALTER TABLE scripts ALTER COLUMN tags DROP DEFAULT;

-- Step 2: Convert column types to jsonb
-- Note: Cannot use subqueries in USING clause, so just convert array to jsonb directly
-- The double-encoded strings will still be strings inside the jsonb, we'll fix that next
ALTER TABLE scripts ALTER COLUMN dependencies TYPE jsonb USING to_jsonb(dependencies);
ALTER TABLE scripts ALTER COLUMN tech_stack TYPE jsonb USING to_jsonb(tech_stack);
ALTER TABLE scripts ALTER COLUMN required_env_vars TYPE jsonb USING to_jsonb(required_env_vars);
ALTER TABLE scripts ALTER COLUMN tags TYPE jsonb USING to_jsonb(tags);

-- Step 3: Set new jsonb defaults
ALTER TABLE scripts ALTER COLUMN dependencies SET DEFAULT '[]'::jsonb;
ALTER TABLE scripts ALTER COLUMN tech_stack SET DEFAULT '[]'::jsonb;
ALTER TABLE scripts ALTER COLUMN required_env_vars SET DEFAULT '[]'::jsonb;
ALTER TABLE scripts ALTER COLUMN tags SET DEFAULT '[]'::jsonb;

-- Step 4: Fix the double-encoded data in dependencies
-- After to_jsonb(), we have: ["{\\"name\\":\\"pkg\\",\\"version\\":null}"]
-- We need: [{"name":"pkg","version":null}]
UPDATE scripts
SET dependencies = (
    SELECT jsonb_agg(
        CASE 
            -- If the element is a string that contains JSON, parse it
            WHEN jsonb_typeof(elem) = 'string' THEN (elem #>> '{}')::jsonb
            -- Otherwise keep it as-is (already an object)
            ELSE elem
        END
    )
    FROM jsonb_array_elements(dependencies) AS elem
)
WHERE dependencies IS NOT NULL 
  AND jsonb_array_length(dependencies) > 0
  AND EXISTS (
    SELECT 1 
    FROM jsonb_array_elements(dependencies) AS elem 
    WHERE jsonb_typeof(elem) = 'string'
  );

-- Step 5: Fix tech_stack (same issue, simpler data)
UPDATE scripts
SET tech_stack = (
    SELECT jsonb_agg(
        CASE 
            WHEN jsonb_typeof(elem) = 'string' THEN elem
            ELSE elem
        END
    )
    FROM jsonb_array_elements(tech_stack) AS elem
)
WHERE tech_stack IS NOT NULL AND jsonb_array_length(tech_stack) > 0;

-- Step 6: Verify the fix
SELECT name, pg_typeof(dependencies) as dep_type, dependencies 
FROM scripts 
WHERE name = 'extract_youtube_transcript';
