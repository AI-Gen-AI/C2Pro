-- ===================================================================
-- Clerk + Supabase RLS Integration
-- Location: infrastructure/supabase/migrations/003_clerk_integration.sql
-- ===================================================================
-- 
-- This migration updates RLS policies to work with Clerk authentication
-- and adds Clerk-specific fields to existing tables
--
-- IMPORTANT: Run this AFTER deploying Clerk to production
-- 

-- ===================================================================
-- 1. Update users table to include clerk_user_id
-- ===================================================================

-- Add clerk_user_id column if it doesn't exist
ALTER TABLE users
ADD COLUMN IF NOT EXISTS clerk_user_id TEXT UNIQUE;

-- Add comment for clarity
COMMENT ON COLUMN users.clerk_user_id IS 
  'Maps to Clerk auth.users.id for JWT verification';

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_users_clerk_user_id 
  ON users(clerk_user_id);

-- ===================================================================
-- 2. Add organizations table (maps Clerk orgs to tenants)
-- ===================================================================

CREATE TABLE IF NOT EXISTS organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  
  -- Clerk fields
  clerk_org_id TEXT UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  
  -- Metadata
  is_demo BOOLEAN DEFAULT FALSE,
  tier VARCHAR(50) DEFAULT 'free', -- free, pro, enterprise
  
  -- Audit
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(tenant_id, clerk_org_id)
);

-- RLS for organizations table
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see organizations they belong to
CREATE POLICY "org_isolation" ON organizations
FOR ALL USING (
  tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
);

-- Create index for fast lookups
CREATE INDEX idx_organizations_clerk_org_id ON organizations(clerk_org_id);
CREATE INDEX idx_organizations_tenant_id ON organizations(tenant_id);

-- ===================================================================
-- 3. Add organization_members table (for RBAC)
-- ===================================================================

CREATE TABLE IF NOT EXISTS organization_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Clerk role
  role VARCHAR(50) DEFAULT 'member', -- admin, member, guest
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(organization_id, user_id)
);

-- RLS for organization_members
ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_members_isolation" ON organization_members
FOR ALL USING (
  organization_id IN (
    SELECT id FROM organizations 
    WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
  )
);

-- Create indexes
CREATE INDEX idx_org_members_organization_id ON organization_members(organization_id);
CREATE INDEX idx_org_members_user_id ON organization_members(user_id);

-- ===================================================================
-- 4. Update existing RLS policies to work with Clerk
-- ===================================================================

-- Projects table - use tenant_id from JWT
DROP POLICY IF EXISTS "tenant_isolation_projects" ON projects;

CREATE POLICY "tenant_isolation_projects" ON projects
FOR ALL USING (
  tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
);

-- Documents table
DROP POLICY IF EXISTS "tenant_isolation_documents" ON documents;

CREATE POLICY "tenant_isolation_documents" ON documents
FOR ALL USING (
  project_id IN (
    SELECT id FROM projects 
    WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
  )
);

-- Stakeholders table
DROP POLICY IF EXISTS "tenant_isolation_stakeholders" ON stakeholders;

CREATE POLICY "tenant_isolation_stakeholders" ON stakeholders
FOR ALL USING (
  project_id IN (
    SELECT id FROM projects 
    WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
  )
);

-- WBS Items table
DROP POLICY IF EXISTS "tenant_isolation_wbs" ON wbs_items;

CREATE POLICY "tenant_isolation_wbs" ON wbs_items
FOR ALL USING (
  project_id IN (
    SELECT id FROM projects 
    WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
  )
);

-- BOM Items table
DROP POLICY IF EXISTS "tenant_isolation_bom" ON bom_items;

CREATE POLICY "tenant_isolation_bom" ON bom_items
FOR ALL USING (
  project_id IN (
    SELECT id FROM projects 
    WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
  )
);

-- Clauses table
DROP POLICY IF EXISTS "tenant_isolation_clauses" ON clauses;

CREATE POLICY "tenant_isolation_clauses" ON clauses
FOR ALL USING (
  project_id IN (
    SELECT id FROM projects 
    WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
  )
);

-- ===================================================================
-- 5. Helper function to map Clerk org to tenant
-- ===================================================================

CREATE OR REPLACE FUNCTION get_tenant_id_from_clerk_org(clerk_org_id TEXT)
RETURNS UUID AS $$
  SELECT tenant_id FROM organizations
  WHERE clerk_org_id = $1
  LIMIT 1;
$$ LANGUAGE SQL STABLE;

-- ===================================================================
-- 6. Helper function to check user role in organization
-- ===================================================================

CREATE OR REPLACE FUNCTION user_has_role_in_org(
  user_id UUID,
  org_id UUID,
  required_role VARCHAR
)
RETURNS BOOLEAN AS $$
  SELECT EXISTS(
    SELECT 1 FROM organization_members
    WHERE organization_members.user_id = $1
    AND organization_members.organization_id = $2
    AND organization_members.role = $3
  );
$$ LANGUAGE SQL STABLE;

-- ===================================================================
-- 7. Create views for easier querying
-- ===================================================================

-- View: Current user's organizations and their role
CREATE OR REPLACE VIEW v_user_organizations AS
SELECT 
  om.organization_id,
  om.user_id,
  om.role,
  o.clerk_org_id,
  o.name,
  o.tenant_id,
  o.tier,
  o.is_demo,
  om.created_at
FROM organization_members om
JOIN organizations o ON o.id = om.organization_id
WHERE om.user_id = auth.uid();

-- ===================================================================
-- 8. Grant permissions
-- ===================================================================

-- Allow authenticated users to read organizations
GRANT SELECT ON organizations TO authenticated;
GRANT SELECT ON organization_members TO authenticated;
GRANT SELECT ON v_user_organizations TO authenticated;

-- ===================================================================
-- 9. Verify RLS is enabled on all tables
-- ===================================================================

-- Check that RLS is enabled on all critical tables
-- Run this query to verify:
/*
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN (
  'organizations',
  'organization_members',
  'projects',
  'documents',
  'stakeholders',
  'wbs_items',
  'bom_items',
  'clauses'
)
ORDER BY tablename;

-- All should show rowsecurity = true
*/

-- ===================================================================
-- 10. Notes for Integration
-- ===================================================================

/*
CLERK JWT Structure:
{
  "sub": "user_xxxxx",
  "email": "user@example.com",
  "org_id": "org_xxxxx",
  "org_role": "admin",
  "tenant_id": "actual-tenant-uuid",  <- Added by your app
  "iat": 1234567890,
  "exp": 1234571490
}

Your backend needs to:
1. Verify the Clerk JWT signature
2. Extract "org_id" from JWT
3. Look up in organizations table to find tenant_id
4. Pass tenant_id to RLS context (via SET app.current_tenant_id)

Example in FastAPI:
  - User sends JWT from Clerk
  - Your middleware verifies JWT
  - Extracts org_id from JWT
  - Queries: SELECT tenant_id FROM organizations WHERE clerk_org_id = org_id
  - Sets Supabase context with tenant_id
  - RLS policies automatically filter by tenant_id
*/

-- ===================================================================
-- Verification Script (run after migration)
-- ===================================================================

-- Check organizations table exists
SELECT COUNT(*) as org_count FROM organizations;

-- Check RLS is enabled
SELECT tablename, rowsecurity FROM pg_tables 
WHERE tablename = 'organizations';

-- Test: Try to read organizations (should use RLS)
-- SELECT * FROM organizations; -- Only returns orgs for current tenant
