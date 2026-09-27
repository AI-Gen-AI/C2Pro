"""#711 durable recovery discovery index outside tenant-scoped business reads.

Revision ID: 20260927_0711
Revises: 20260923_0001
Create Date: 2026-09-27

The documents table is FORCE-RLS and must stay fail-closed. A scheduler with no
tenant cannot discover stale rows from that table. This migration therefore
creates a minimal internal projection containing only recovery routing data:
document_id, tenant_id, upload_status and updated_at.

The projection is maintained transactionally by a trigger on documents.
Runtime recovery scans the projection, then re-enters the normal tenant-scoped
session before locking or mutating the document.

No BYPASSRLS role, cross-tenant business-table policy or extra credential is
introduced.
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "20260927_0711"
down_revision: str | None = "20260923_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill_existing_documents() -> None:
    """Backfill under an ACCESS EXCLUSIVE lock and restore FORCE-RLS exactly."""
    bind = op.get_bind()
    has_upload_status = bool(
        bind.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                      FROM pg_attribute
                     WHERE attrelid = 'public.documents'::regclass
                       AND attname = 'upload_status'
                       AND NOT attisdropped
                )
                """
            )
        ).scalar_one()
    )
    if not has_upload_status:
        return

    force_rls = bool(
        bind.execute(
            text(
                """
                SELECT relforcerowsecurity
                  FROM pg_class
                 WHERE oid = 'public.documents'::regclass
                """
            )
        ).scalar_one()
    )

    op.execute("LOCK TABLE public.documents IN ACCESS EXCLUSIVE MODE")
    if force_rls:
        op.execute("ALTER TABLE public.documents NO FORCE ROW LEVEL SECURITY")
    try:
        op.execute(
            """
            INSERT INTO system_recovery.document_work_index (
                document_id,
                tenant_id,
                upload_status,
                updated_at
            )
            SELECT id, tenant_id, upload_status::text, updated_at
              FROM public.documents
            ON CONFLICT (document_id) DO UPDATE
                SET tenant_id = EXCLUDED.tenant_id,
                    upload_status = EXCLUDED.upload_status,
                    updated_at = EXCLUDED.updated_at
            """
        )
    finally:
        if force_rls:
            op.execute("ALTER TABLE public.documents FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS system_recovery")
    op.execute("REVOKE ALL ON SCHEMA system_recovery FROM PUBLIC")

    op.execute(
        """
        CREATE TABLE system_recovery.document_work_index (
            document_id uuid PRIMARY KEY
                REFERENCES public.documents(id) ON DELETE CASCADE,
            tenant_id uuid NOT NULL,
            upload_status text NULL,
            updated_at timestamp without time zone NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_document_work_index_recovery_scan
            ON system_recovery.document_work_index
                (upload_status, updated_at, document_id)
        """
    )
    op.execute(
        "REVOKE ALL ON TABLE system_recovery.document_work_index FROM PUBLIC"
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION system_recovery.sync_document_work_index()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, system_recovery
        AS $recovery$
        DECLARE
            row_json jsonb := to_jsonb(NEW);
            row_updated_at timestamp without time zone;
        BEGIN
            BEGIN
                row_updated_at := NULLIF(row_json ->> 'updated_at', '')::timestamp;
            EXCEPTION WHEN invalid_datetime_format THEN
                row_updated_at := NULL;
            END;

            INSERT INTO system_recovery.document_work_index (
                document_id,
                tenant_id,
                upload_status,
                updated_at
            )
            VALUES (
                NEW.id,
                NEW.tenant_id,
                row_json ->> 'upload_status',
                COALESCE(row_updated_at, clock_timestamp() AT TIME ZONE 'UTC')
            )
            ON CONFLICT (document_id) DO UPDATE
                SET tenant_id = EXCLUDED.tenant_id,
                    upload_status = EXCLUDED.upload_status,
                    updated_at = EXCLUDED.updated_at;
            RETURN NEW;
        END
        $recovery$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION system_recovery.sync_document_work_index() "
        "FROM PUBLIC"
    )
    op.execute(
        """
        CREATE TRIGGER trg_documents_recovery_index
        AFTER INSERT OR UPDATE ON public.documents
        FOR EACH ROW
        EXECUTE FUNCTION system_recovery.sync_document_work_index()
        """
    )

    _backfill_existing_documents()


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_documents_recovery_index ON public.documents"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS system_recovery.sync_document_work_index()"
    )
    op.execute("DROP TABLE IF EXISTS system_recovery.document_work_index")
    op.execute("DROP SCHEMA IF EXISTS system_recovery")
