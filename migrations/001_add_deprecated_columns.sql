-- ============================================
-- MIGRATION: Add deprecated columns to scripts table
-- Purpose: Enable soft-deletion of scripts via deprecation
-- Date: 2024-12-18
-- ============================================

-- Add deprecated column
-- This allows marking scripts as deprecated without deleting them
ALTER TABLE scripts
ADD COLUMN IF NOT EXISTS deprecated BOOLEAN DEFAULT false;

-- Add deprecated_reason column (optional)
-- This stores the reason why a script was deprecated
ALTER TABLE scripts
ADD COLUMN IF NOT EXISTS deprecated_reason TEXT;

-- Add index for better query performance on deprecated scripts
CREATE INDEX IF NOT EXISTS idx_scripts_deprecated 
ON scripts(deprecated) 
WHERE deprecated = true;

-- Add comment for documentation
COMMENT ON COLUMN scripts.deprecated IS 'Whether this script has been deprecated (soft delete)';
COMMENT ON COLUMN scripts.deprecated_reason IS 'Optional reason for deprecation';

-- Verification query (run after applying migration)
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'scripts' 
-- AND column_name IN ('deprecated', 'deprecated_reason');
