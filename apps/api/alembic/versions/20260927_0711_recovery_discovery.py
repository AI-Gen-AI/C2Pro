"""#711 narrow recovery discovery across FORCE-RLS documents.

Revision ID: 20260927_0711
Revises: 20260923_0001
Create Date: 2026-09-27

The scheduler must discover abandoned processing rows across tenants without
granting the application role BYPASSRLS or disabling tenant isolation.
Only document_id + tenant_id for stale processing states are exposed.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260927_0711"
down_revision: str | None = "20260923_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS system_recovery;")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION system_recovery.list_stale_document_candidates(
            p_stale_after_seconds integer,
            p_limit integer
        )
        RETURNS TABLE (
            document_id uuid,
            tenant_id uuid
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        BEGIN
            -- The Alembic application schema owns upload_status. The historic
            -- Supabase mirror baseline predates that column; keep mirror
            -- migrations replayable without weakening production semantics.
            IF NOT EXISTS (
                SELECT 1
                  FROM pg_attribute
                 WHERE attrelid = 'public.documents'::regclass
                   AND attname = 'upload_status'
                   AND NOT attisdropped
            ) THEN
                RETURN;
            END IF;

            RETURN QUERY EXECUTE
                'SELECT d.id, d.tenant_id
                   FROM public.documents AS d
                  WHERE d.upload_status::text IN (''parsing'', ''parsed_pending_analysis'')
                    AND d.updated_at <=
                        clock_timestamp() - make_interval(secs => GREATEST($1, 1))
                  ORDER BY d.updated_at, d.id
                  LIMIT LEAST(GREATEST($2, 1), 100)'
                USING p_stale_after_seconds, p_limit;
        END
        $;
        """
    )
    op.execute("REVOKE ALL ON SCHEMA system_recovery FROM PUBLIC;")
    op.execute(
        "REVOKE ALL ON FUNCTION "
        "system_recovery.list_stale_document_candidates(integer, integer) "
        "FROM PUBLIC;"
    )
    op.execute(
        """
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
        """
    )
    op.execute(
        """
        COMMENT ON FUNCTION
            system_recovery.list_stale_document_candidates(integer, integer)
        IS
            'Issue #711: minimal cross-tenant discovery for stale document '
            'processing recovery. Returns identifiers only; all mutation is '
            'performed later under tenant-scoped RLS.';
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS "
        "system_recovery.list_stale_document_candidates(integer, integer);"
    )
    op.execute("DROP SCHEMA IF EXISTS system_recovery;")
