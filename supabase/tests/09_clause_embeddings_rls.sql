-- Suite ID: TASK-SEC-012
-- RLS isolation tests for clause_embeddings.
--
-- Verifies that the tenant_isolation_clause_embeddings policy enforces
-- fail-closed cross-tenant isolation: no rows leak across tenant boundaries
-- and no rows are visible when the GUC is absent.
--
-- Run with: supabase test db  (requires supabase-cli >= 1.x and pgTAP)

BEGIN;

SELECT plan(6);

-- ── Setup ──────────────────────────────────────────────────────────────────

DO $$
DECLARE
  tid_a UUID := '11111111-1111-1111-1111-111111111111';
  tid_b UUID := '22222222-2222-2222-2222-222222222222';
BEGIN
  -- Bypass RLS for setup (service role context)
  SET LOCAL row_security = off;

  -- Ensure tenants exist (idempotent)
  INSERT INTO tenants (id, name, slug, plan)
  VALUES (tid_a, 'Tenant A', 'tenant-a', 'free'),
         (tid_b, 'Tenant B', 'tenant-b', 'free')
  ON CONFLICT (id) DO NOTHING;

  -- Seed one embedding per tenant; project scoping not relevant for this test
  INSERT INTO clause_embeddings (id, tenant_id, project_id, clause_id, text, category, document_type)
  VALUES
    (gen_random_uuid(), tid_a, gen_random_uuid(), 'clause-a-1', 'Tenant A contract text', 'BUDGET', 'contract'),
    (gen_random_uuid(), tid_b, gen_random_uuid(), 'clause-b-1', 'Tenant B contract text', 'TIME',   'contract')
  ON CONFLICT DO NOTHING;
END
$$;

-- ── Test 1: GUC for tenant A → only tenant A rows visible ──────────────────

SET LOCAL app.current_tenant_id = '11111111-1111-1111-1111-111111111111';
SET LOCAL row_security = on;

SELECT results_eq(
  $$ SELECT count(*)::int FROM clause_embeddings $$,
  $$ VALUES (1) $$,
  'Tenant A GUC: exactly 1 row visible (own rows only)'
);

SELECT results_eq(
  $$ SELECT DISTINCT tenant_id::text FROM clause_embeddings $$,
  $$ VALUES ('11111111-1111-1111-1111-111111111111') $$,
  'Tenant A GUC: visible tenant_id matches GUC value'
);

-- ── Test 2: GUC for tenant B → only tenant B rows visible ──────────────────

SET LOCAL app.current_tenant_id = '22222222-2222-2222-2222-222222222222';

SELECT results_eq(
  $$ SELECT count(*)::int FROM clause_embeddings $$,
  $$ VALUES (1) $$,
  'Tenant B GUC: exactly 1 row visible (own rows only)'
);

SELECT results_eq(
  $$ SELECT DISTINCT tenant_id::text FROM clause_embeddings $$,
  $$ VALUES ('22222222-2222-2222-2222-222222222222') $$,
  'Tenant B GUC: visible tenant_id matches GUC value'
);

-- ── Test 3: No GUC set → zero rows (fail-closed) ───────────────────────────

RESET app.current_tenant_id;

SELECT results_eq(
  $$ SELECT count(*)::int FROM clause_embeddings $$,
  $$ VALUES (0) $$,
  'No GUC: zero rows visible (fail-closed)'
);

-- ── Test 4: Cross-tenant INSERT rejected ────────────────────────────────────

SET LOCAL app.current_tenant_id = '11111111-1111-1111-1111-111111111111';

SELECT throws_ok(
  $$
    INSERT INTO clause_embeddings (id, tenant_id, project_id, clause_id, text, category, document_type)
    VALUES (gen_random_uuid(), '22222222-2222-2222-2222-222222222222',
            gen_random_uuid(), 'cross-tenant-clause', 'spoofed text', 'BUDGET', 'contract')
  $$,
  'new row violates row-level security policy',
  'Cross-tenant INSERT is rejected by RLS'
);

SELECT * FROM finish();

ROLLBACK;
