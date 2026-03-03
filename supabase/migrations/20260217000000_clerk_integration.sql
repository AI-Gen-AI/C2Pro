-- ===================================================================
-- Clerk + Supabase RLS Integration
-- Migration: 20260217000000_clerk_integration.sql
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
-- Note: Using request.jwt() for Clerk JWT claims
CREATE POLICY "org_isolation" ON organizations
FOR ALL USING (
  tenant_id = (current_setting('request.jwt.claims', true)::json ->> 'tenant_id')::uuid
  OR tenant_id = (current_setting('app.current_tenant_id', true))::uuid
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_organizations_clerk_org_id ON organizations(clerk_org_id);
CREATE INDEX IF NOT EXISTS idx_organizations_tenant_id ON organizations(tenant_id);

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
    WHERE tenant_id = (current_setting('request.jwt.claims', true)::json ->> 'tenant_id')::uuid
    OR tenant_id = (current_setting('app.current_tenant_id', true))::uuid
  )
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_org_members_organization_id ON organization_members(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_members_user_id ON organization_members(user_id);

-- ===================================================================
-- 4. Helper function to map Clerk org to tenant
-- ===================================================================

CREATE OR REPLACE FUNCTION get_tenant_id_from_clerk_org(p_clerk_org_id TEXT)
RETURNS UUID AS $$
  SELECT tenant_id FROM organizations
  WHERE clerk_org_id = p_clerk_org_id
  LIMIT 1;
$$ LANGUAGE SQL STABLE;

-- ===================================================================
-- 5. Helper function to check user role in organization
-- ===================================================================

CREATE OR REPLACE FUNCTION user_has_role_in_org(
  p_user_id UUID,
  p_org_id UUID,
  p_required_role VARCHAR
)
RETURNS BOOLEAN AS $$
  SELECT EXISTS(
    SELECT 1 FROM organization_members
    WHERE organization_members.user_id = p_user_id
    AND organization_members.organization_id = p_org_id
    AND organization_members.role = p_required_role
  );
$$ LANGUAGE SQL STABLE;

-- ===================================================================
-- 6. Function to set tenant context for RLS
-- ===================================================================

CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id UUID)
RETURNS VOID AS $$
BEGIN
  PERFORM set_config('app.current_tenant_id', p_tenant_id::TEXT, true);
END;
$$ LANGUAGE plpgsql;

-- ===================================================================
-- 7. Grant permissions
-- ===================================================================

-- Allow authenticated users to read organizations
GRANT SELECT ON organizations TO authenticated;
GRANT SELECT ON organization_members TO authenticated;

-- ===================================================================
-- 8. Verification queries (run manually after migration)
-- ===================================================================

-- Check organizations table exists
-- SELECT COUNT(*) as org_count FROM organizations;

-- Check RLS is enabled
-- SELECT tablename, rowsecurity FROM pg_tables
-- WHERE tablename = 'organizations';

-- ===================================================================
-- Notes for Integration
-- ===================================================================
/*
CLERK JWT Structure (after custom claims):
{
  "sub": "user_xxxxx",
  "email": "user@example.com",
  "org_id": "org_xxxxx",
  "org_role": "admin",
  "org_public_metadata": {
    "tenant_id": "actual-tenant-uuid",
    "tier": "pro",
    "is_demo": false
  },
  "iat": 1234567890,
  "exp": 1234571490
}

Backend workflow:
1. Verify Clerk JWT signature using JWKS
2. Extract tenant_id from org_public_metadata.tenant_id
3. Call set_tenant_context(tenant_id) before queries
4. RLS policies filter by app.current_tenant_id
*/
