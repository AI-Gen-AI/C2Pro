-- TS-SEC-RLS-CLAUSE-EMBEDDINGS-001
-- Mathematical isolation proof for clause_embeddings via app.current_tenant GUC.

BEGIN;

SELECT set_config('app.current_tenant', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', true);

DO $$
DECLARE
    tenant_a_rows integer;
    tenant_b_visible_to_a integer;
BEGIN
    SELECT COUNT(*)
    INTO tenant_a_rows
    FROM clause_embeddings ce
    JOIN projects p ON p.id = ce.project_id
    WHERE p.tenant_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid;

    SELECT COUNT(*)
    INTO tenant_b_visible_to_a
    FROM clause_embeddings ce
    JOIN projects p ON p.id = ce.project_id
    WHERE p.tenant_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid;

    IF tenant_b_visible_to_a <> 0 THEN
        RAISE EXCEPTION 'RLS isolation failed: tenant A can read % tenant B rows', tenant_b_visible_to_a;
    END IF;

    RAISE NOTICE 'RLS isolation pass: tenant A rows=% and tenant B visible rows=%', tenant_a_rows, tenant_b_visible_to_a;
END $$;

ROLLBACK;
