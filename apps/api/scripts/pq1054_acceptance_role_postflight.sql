-- #1054 POST-MIGRATION anchor attestation. Run only after owner inserts the anchor.
-- Invoke with psql -v expected_tenant="$PROD_ACCEPTANCE_EXPECTED_TENANT_ID"
--   -f apps/api/scripts/pq1054_acceptance_role_postflight.sql
-- Owner-level read-only session. Never print the protected tenant UUID.
\set ON_ERROR_STOP on
\if :{?expected_tenant}
\else
  \echo 'PQ1054_EXPECTED_TENANT_REQUIRED'
  \quit 3
\endif
BEGIN READ ONLY;
-- Store the psql-provided UUID in a transaction-local setting without printing it.
SELECT pg_catalog.set_config('c2pro.expected_tenant', :'expected_tenant', true) \g /dev/null
DO $pq1054_postflight$
DECLARE
    n bigint;
    valid_binding boolean;
BEGIN
    IF pg_catalog.to_regclass('c2pro_security.acceptance_tenant_binding') IS NULL THEN
        RAISE EXCEPTION 'PQ1054_ANCHOR_TABLE_MISSING';
    END IF;
    EXECUTE $check$
      SELECT count(*),
             coalesce(bool_and(
               b.role_name = 'c2pro_prod_acceptance_ro'
               AND b.tenant_id::text = pg_catalog.current_setting('c2pro.expected_tenant')
               AND b.project_id = 'e7c6031f-cd9e-4642-a5ea-35a0207ceaeb'::uuid
               AND EXISTS (
                 SELECT 1 FROM public.projects p
                 WHERE p.id = b.project_id AND p.tenant_id = b.tenant_id
               )
             ), false)
      FROM c2pro_security.acceptance_tenant_binding b
    $check$ INTO n, valid_binding;
    IF n <> 1 OR valid_binding IS NOT TRUE THEN
        RAISE EXCEPTION 'PQ1054_ANCHOR_POSTFLIGHT_FAILED';
    END IF;
    RAISE NOTICE 'PQ1054_ANCHOR_POSTFLIGHT_PASS';
END
$pq1054_postflight$;
ROLLBACK;
