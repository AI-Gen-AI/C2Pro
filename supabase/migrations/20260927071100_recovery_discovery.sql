-- #711 narrow recovery discovery across FORCE-RLS documents.
-- Mirror of apps/api/alembic/versions/20260927_0711_recovery_discovery.py.
-- Alembic is authoritative.

CREATE SCHEMA IF NOT EXISTS system_recovery;

CREATE OR REPLACE FUNCTION system_recovery.list_stale_document_candidates(
    p_stale_after_seconds integer,
    p_limit integer
)
RETURNS TABLE (
    document_id uuid,
    tenant_id uuid
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT d.id, d.tenant_id
      FROM public.documents AS d
     WHERE d.upload_status::text IN ('parsing', 'parsed_pending_analysis')
       AND d.updated_at <=
           clock_timestamp()
           - make_interval(secs => GREATEST(p_stale_after_seconds, 1))
     ORDER BY d.updated_at, d.id
     LIMIT LEAST(GREATEST(p_limit, 1), 100);
$$;

REVOKE ALL ON SCHEMA system_recovery FROM PUBLIC;
REVOKE ALL ON FUNCTION
    system_recovery.list_stale_document_candidates(integer, integer)
FROM PUBLIC;

DO $$
DECLARE role_name text;
BEGIN
    FOR role_name IN
        SELECT rolname
          FROM pg_roles
         WHERE rolname IN ('anon', 'authenticated', 'service_role')
    LOOP
        EXECUTE format(
            'REVOKE ALL ON SCHEMA system_recovery FROM %I',
            role_name
        );
        EXECUTE format(
            'REVOKE ALL ON FUNCTION '
            'system_recovery.list_stale_document_candidates(integer, integer) '
            'FROM %I',
            role_name
        );
    END LOOP;
END
$$;

COMMENT ON FUNCTION
    system_recovery.list_stale_document_candidates(integer, integer)
IS
    'Issue #711: minimal cross-tenant discovery for stale document processing recovery. Returns identifiers only; all mutation is performed later under tenant-scoped RLS.';
