-- #686: least-privileged recovery authority read grant.
-- Mirror of apps/api/alembic/versions/20261007_0002_p0c_recovery_authority_read_grant.py (rendered from UPGRADE_STATEMENTS; do not edit by hand).

DO $do$
DECLARE
    rls_enabled boolean;
    rls_forced boolean;
BEGIN
    SELECT c.relrowsecurity, c.relforcerowsecurity
      INTO rls_enabled, rls_forced
      FROM pg_class c
     WHERE c.oid = 'public.document_processing_operations'::regclass;

    IF NOT coalesce(rls_enabled, false) OR NOT coalesce(rls_forced, false) THEN
        RAISE EXCEPTION 'public.document_processing_operations must have RLS and FORCE RLS before qualification access is granted';
    END IF;
END
$do$;

DO $do$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_prod_acceptance_ro') THEN
        GRANT SELECT (document_id, tenant_id, revision_id, generation, stage, phase, outcome)
            ON public.document_processing_operations
            TO c2pro_prod_acceptance_ro;
    END IF;
END
$do$;
