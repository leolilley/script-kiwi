# Setup Guide - Script Kiwi & Knowledge Kiwi

## Step 1: Create Supabase Projects

### Manual Steps (via supabase.com)

1. **Script Kiwi Project**
   - Go to https://supabase.com/dashboard
   - Click "New Project"
   - Name: `script-kiwi`
   - Region: Choose closest to you
   - Database Password: Generate and save securely
   - Wait for project to initialize (~2 minutes)
   - **Save these values:**
     - Project URL: `https://xxxxx.supabase.co`
     - Anon Key: `eyJhbGc...`
     - Service Role Key: `eyJhbGc...` (Settings → API)

2. **Knowledge Kiwi Project**
   - Same process as above
   - Name: `knowledge-kiwi`
   - **Save these values:**
     - Project URL: `https://xxxxx.supabase.co`
     - Anon Key: `eyJhbGc...`
     - Service Role Key: `eyJhbGc...`

### After Creation

Update `.env` files in each project with:
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SECRET_KEY=your-service-role-key

KNOWLEDGE_KIWI_SUPABASE_URL=https://xxxxx.supabase.co
KNOWLEDGE_KIWI_SUPABASE_KEY=your-anon-key
```

## Step 2: Run Database Schemas

### Script Kiwi Schema

1. Go to Script Kiwi project → SQL Editor
2. Copy contents from `docs/script-kiwi-schema.sql`
3. Run the SQL script
4. Verify tables created: `scripts`, `script_versions`, `executions`, `lockfiles`, `script_feedback`

### Knowledge Kiwi Schema

1. Go to Knowledge Kiwi project → SQL Editor
2. Copy contents from `v2/schemas/knowledge-kiwi-schema.sql`
3. Run the SQL script
4. Verify tables created: `knowledge_entries`, `knowledge_relationships`, `knowledge_collections`, `sync_log`

## Step 3: Verify Setup

Run verification scripts:
```bash
# Script Kiwi
cd ~/projects/script-kiwi
python -m script_kiwi.server

# Knowledge Kiwi
cd ~/projects/knowledge-kiwi
python -m knowledge_kiwi_mcp.verify_setup
```

## Next Steps

After Supabase projects are created, proceed with:
- [ ] Run SQL schemas
- [ ] Scaffold repository structures
- [ ] Set up environment variables
- [ ] Test MCP server connections
