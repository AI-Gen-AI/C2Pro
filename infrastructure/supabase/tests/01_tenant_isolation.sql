-- =====================================================
-- C2Pro - pgTAP Security Tests
-- =====================================================
-- Version: 2.4.0
-- Date: 2026-01-13
--
-- Test Suite: Multi-Tenant Isolation & Identity
-- CTO Gates: Gate 1 (Isolation), Gate 2 (Identity)
--
-- This script verifies that Row Level Security (RLS)
-- correctly isolates tenant data and enforces identity
-- constraints.
--
-- Prerequisites:
--   1. Extension pgtap installed
--   2. Migration 001_init_schema.sql applied
--   3. Database must be empty or test data cleaned up
--
-- Usage:
--   pg_prove -d $DATABASE_URL infrastructure/supabase/tests/01_tenant_isolation.sql
--
-- Or run directly:
--   psql $DATABASE_URL -f infrastructure/supabase/tests/01_tenant_isolation.sql
-- =====================================================

-- Enable pgTAP extension
CREATE EXTENSION IF NOT EXISTS pgtap;

BEGIN;

-- =====================================================
-- TEST PLAN
-- =====================================================
-- We'll run 15 tests total
SELECT plan(15);

-- =====================================================
-- HELPER FUNCTIONS FOR AUTH SIMULATION
-- =====================================================

-- Helper: Set session as authenticated user with tenant_id
CREATE OR REPLACE FUNCTION test_set_authenticated_user(
    p_user_id UUID,
    p_tenant_id UUID
) RETURNS VOID AS $$
BEGIN
    -- Simulate Supabase auth.uid()
    PERFORM set_config('request.jwt.claim.sub', p_user_id::text, true);

    -- Simulate Supabase auth.jwt() with tenant_id claim
    PERFORM set_config(
        'request.jwt.claims',
        json_build_object(
            'sub', p_user_id::text,
            'tenant_id', p_tenant_id::text,
            'role', 'authenticated'
        )::text,
        true
    );

    -- Set role to authenticated (required for RLS policies)
    PERFORM set_config('role', 'authenticated', true);
END;
$$ LANGUAGE plpgsql;

-- Helper: Clear authentication (anonymous user)
CREATE OR REPLACE FUNCTION test_clear_auth() RETURNS VOID AS $$
BEGIN
    PERFORM set_config('request.jwt.claim.sub', '', true);
    PERFORM set_config('request.jwt.claims', '', true);
    PERFORM set_config('role', 'anon', true);
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- TEST DATA SETUP
-- =====================================================

-- Clean up any existing test data
DELETE FROM documents WHERE project_id IN (
    SELECT id FROM projects WHERE tenant_id IN (
        SELECT id FROM tenants WHERE slug LIKE 'test-tenant-%'
    )
);
DELETE FROM projects WHERE tenant_id IN (
    SELECT id FROM tenants WHERE slug LIKE 'test-tenant-%'
);
DELETE FROM users WHERE tenant_id IN (
    SELECT id FROM tenants WHERE slug LIKE 'test-tenant-%'
);
DELETE FROM tenants WHERE slug LIKE 'test-tenant-%';

-- Create Tenant A
INSERT INTO tenants (id, name, slug, plan, max_projects, max_users, is_active)
VALUES (
    '11111111-1111-1111-1111-111111111111'::uuid,
    'Test Tenant A',
    'test-tenant-a',
    'pro',
    50,
    20,
    true
);

-- Create Tenant B
INSERT INTO tenants (id, name, slug, plan, max_projects, max_users, is_active)
VALUES (
    '22222222-2222-2222-2222-222222222222'::uuid,
    'Test Tenant B',
    'test-tenant-b',
    'free',
    10,
    5,
    true
);

-- Create User Alice in Tenant A
-- NOTE: In production, users are created via Supabase Auth
-- Here we insert directly for testing
INSERT INTO users (id, tenant_id, email, first_name, last_name, role, is_active)
VALUES (
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid,
    '11111111-1111-1111-1111-111111111111'::uuid,
    'alice@tenant-a.com',
    'Alice',
    'Anderson',
    'owner',
    true
);

-- Create User Bob in Tenant B
INSERT INTO users (id, tenant_id, email, first_name, last_name, role, is_active)
VALUES (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
    'bob@tenant-b.com',
    'Bob',
    'Baker',
    'owner',
    true
);

-- Create Project A1 in Tenant A
INSERT INTO projects (
    id,
    tenant_id,
    name,
    description,
    status,
    created_by
)
VALUES (
    'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1'::uuid,
    '11111111-1111-1111-1111-111111111111'::uuid,
    'Project Alpha',
    'Top secret project for Tenant A',
    'active',
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid
);

-- Create Project B1 in Tenant B
INSERT INTO projects (
    id,
    tenant_id,
    name,
    description,
    status,
    created_by
)
VALUES (
    'b1b1b1b1-b1b1-b1b1-b1b1-b1b1b1b1b1b1'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
    'Project Beta',
    'Confidential project for Tenant B',
    'draft',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid
);

-- =====================================================
-- TEST 1: BASELINE - Verify Test Data Created
-- =====================================================

SELECT is(
    (SELECT COUNT(*)::int FROM tenants WHERE slug LIKE 'test-tenant-%'),
    2,
    'Test 1.1: Two test tenants created'
);

SELECT is(
    (SELECT COUNT(*)::int FROM users WHERE email LIKE '%@tenant-%.com'),
    2,
    'Test 1.2: Two test users created'
);

SELECT is(
    (SELECT COUNT(*)::int FROM projects WHERE name LIKE 'Project %'),
    2,
    'Test 1.3: Two test projects created'
);

-- =====================================================
-- TEST 2: GATE 1 - READ ISOLATION
-- =====================================================
-- Verify that users can ONLY read data from their own tenant

-- Test 2.1: Alice (Tenant A) can see Project A1
SELECT test_set_authenticated_user(
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid,  -- Alice's ID
    '11111111-1111-1111-1111-111111111111'::uuid   -- Tenant A
);

SELECT is(
    (SELECT COUNT(*)::int FROM projects WHERE id = 'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1'::uuid),
    1,
    'Test 2.1: Alice (Tenant A) can see Project A1 (her own project)'
);

-- Test 2.2: Alice (Tenant A) CANNOT see Project B1
SELECT is(
    (SELECT COUNT(*)::int FROM projects WHERE id = 'b1b1b1b1-b1b1-b1b1-b1b1-b1b1b1b1b1b1'::uuid),
    0,
    'Test 2.2: Alice (Tenant A) CANNOT see Project B1 (cross-tenant isolation)'
);

-- Test 2.3: Alice sees exactly 1 project (only her tenant's)
SELECT is(
    (SELECT COUNT(*)::int FROM projects),
    1,
    'Test 2.3: Alice sees exactly 1 project total (strict tenant isolation)'
);

-- Test 2.4: Bob (Tenant B) can see Project B1
SELECT test_set_authenticated_user(
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid,  -- Bob's ID
    '22222222-2222-2222-2222-222222222222'::uuid   -- Tenant B
);

SELECT is(
    (SELECT COUNT(*)::int FROM projects WHERE id = 'b1b1b1b1-b1b1-b1b1-b1b1-b1b1b1b1b1b1'::uuid),
    1,
    'Test 2.4: Bob (Tenant B) can see Project B1 (his own project)'
);

-- Test 2.5: Bob CANNOT see Project A1
SELECT is(
    (SELECT COUNT(*)::int FROM projects WHERE id = 'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1'::uuid),
    0,
    'Test 2.5: Bob (Tenant B) CANNOT see Project A1 (cross-tenant isolation)'
);

-- =====================================================
-- TEST 3: GATE 1 - WRITE ISOLATION
-- =====================================================
-- Verify that users CANNOT modify data from other tenants

-- Test 3.1: Bob (Tenant B) attempts to UPDATE Project A1
SELECT test_set_authenticated_user(
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid,  -- Bob's ID
    '22222222-2222-2222-2222-222222222222'::uuid   -- Tenant B
);

-- Attempt to update Project A1 (belongs to Tenant A)
UPDATE projects
SET description = 'Hacked by Bob!'
WHERE id = 'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1'::uuid;

-- Verify that Project A1 was NOT modified
SELECT test_set_authenticated_user(
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid,  -- Alice's ID
    '11111111-1111-1111-1111-111111111111'::uuid   -- Tenant A
);

SELECT is(
    (SELECT description FROM projects WHERE id = 'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1'::uuid),
    'Top secret project for Tenant A',
    'Test 3.1: Bob (Tenant B) CANNOT update Project A1 (write isolation)'
);

-- Test 3.2: Bob (Tenant B) attempts to DELETE Project A1
SELECT test_set_authenticated_user(
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid,  -- Bob's ID
    '22222222-2222-2222-2222-222222222222'::uuid   -- Tenant B
);

DELETE FROM projects WHERE id = 'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1'::uuid;

-- Verify that Project A1 still exists
SELECT test_set_authenticated_user(
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid,  -- Alice's ID
    '11111111-1111-1111-1111-111111111111'::uuid   -- Tenant A
);

SELECT is(
    (SELECT COUNT(*)::int FROM projects WHERE id = 'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1'::uuid),
    1,
    'Test 3.2: Bob (Tenant B) CANNOT delete Project A1 (write isolation)'
);

-- =====================================================
-- TEST 4: GATE 1 - ANONYMOUS USER BLOCKED
-- =====================================================
-- Verify that unauthenticated users see ZERO data

SELECT test_clear_auth();

SELECT is(
    (SELECT COUNT(*)::int FROM tenants),
    0,
    'Test 4.1: Anonymous user sees 0 tenants (RLS blocks all access)'
);

SELECT is(
    (SELECT COUNT(*)::int FROM projects),
    0,
    'Test 4.2: Anonymous user sees 0 projects (RLS blocks all access)'
);

-- =====================================================
-- TEST 5: GATE 2 - IDENTITY MODEL
-- =====================================================
-- Verify UNIQUE(tenant_id, email) constraint

-- Test 5.1: Same email in DIFFERENT tenants (should succeed)
BEGIN;
    INSERT INTO users (id, tenant_id, email, first_name, last_name, role, is_active)
    VALUES (
        'cccccccc-cccc-cccc-cccc-cccccccccccc'::uuid,
        '11111111-1111-1111-1111-111111111111'::uuid,  -- Tenant A
        'admin@company.com',
        'Charlie',
        'Chen',
        'admin',
        true
    );

    INSERT INTO users (id, tenant_id, email, first_name, last_name, role, is_active)
    VALUES (
        'dddddddd-dddd-dddd-dddd-dddddddddddd'::uuid,
        '22222222-2222-2222-2222-222222222222'::uuid,  -- Tenant B
        'admin@company.com',  -- SAME email, DIFFERENT tenant
        'Diana',
        'Davis',
        'admin',
        true
    );

    SELECT is(
        (SELECT COUNT(*)::int FROM users WHERE email = 'admin@company.com'),
        2,
        'Test 5.1: Same email in DIFFERENT tenants is allowed (B2B enterprise support)'
    );
ROLLBACK;

-- Test 5.2: Same email in SAME tenant (should fail)
SELECT throws_ok(
    $$
        INSERT INTO users (id, tenant_id, email, first_name, last_name, role, is_active)
        VALUES (
            'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'::uuid,
            '11111111-1111-1111-1111-111111111111'::uuid,  -- Tenant A
            'alice@tenant-a.com',  -- DUPLICATE email in SAME tenant
            'Evil',
            'Alice',
            'member',
            true
        );
    $$,
    '23505',  -- unique_violation error code
    NULL,
    'Test 5.2: Duplicate email in SAME tenant is blocked (constraint enforced)'
);

-- =====================================================
-- CLEANUP
-- =====================================================

-- Drop helper functions
DROP FUNCTION IF EXISTS test_set_authenticated_user(UUID, UUID);
DROP FUNCTION IF EXISTS test_clear_auth();

-- Clean up test data
DELETE FROM projects WHERE tenant_id IN (
    SELECT id FROM tenants WHERE slug LIKE 'test-tenant-%'
);
DELETE FROM users WHERE tenant_id IN (
    SELECT id FROM tenants WHERE slug LIKE 'test-tenant-%'
);
DELETE FROM tenants WHERE slug LIKE 'test-tenant-%';

-- =====================================================
-- FINISH TESTS
-- =====================================================

SELECT * FROM finish();

ROLLBACK;
