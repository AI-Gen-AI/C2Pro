"""#711 document-processing authority: attempts, fencing tokens, DB-clock leases.

Revision ID: 20260928_0711
Revises: 20260927_0711
Create Date: 2026-09-28

One row per document names the canonical revision and processing generation
being worked on, the stage (INGESTION -> ANALYSIS) and the exact attempt that
owns it: attempt_id + owner_token + a monotonic fencing_token under a lease
measured by PostgreSQL's clock. Every canonical durable write re-verifies the
row inside its own transaction (src/core/processing_authority.py), so a
worker whose lease expired and was taken over can keep computing but can never
persist.

Tenant-owned business data: fail-closed NULLIF tenant policies and FORCE RLS,
like every other tenant table. Cross-tenant discovery keeps using the minimal
system_recovery.document_work_index; no BYPASSRLS role is introduced.

Rows are created lazily for documents that predate this revision (first
acquire / recovery claim), so no backfill is required.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260928_0711"
down_revision: str | None = "20260927_0711"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "public.document_processing_operations"
_TENANT = "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {_TABLE} (
            document_id uuid PRIMARY KEY
                REFERENCES public.documents(id) ON DELETE CASCADE,
            tenant_id uuid NOT NULL,
            revision_id uuid NULL,
            generation bigint NOT NULL DEFAULT 1,
            stage varchar(16) NOT NULL,
            phase varchar(16) NOT NULL,
            attempt_id uuid NULL,
            owner_token uuid NULL,
            fencing_token bigint NOT NULL DEFAULT 0,
            lease_expires_at timestamp without time zone NULL,
            heartbeat_at timestamp without time zone NULL,
            attempt_count integer NOT NULL DEFAULT 0,
            failure_count integer NOT NULL DEFAULT 0,
            outcome varchar(64) NULL,
            last_error text NULL,
            created_at timestamp without time zone NOT NULL DEFAULT now(),
            updated_at timestamp without time zone NOT NULL DEFAULT now(),
            CONSTRAINT ck_document_processing_operations_stage
                CHECK (stage IN ('INGESTION','ANALYSIS')),
            CONSTRAINT ck_document_processing_operations_phase
                CHECK (phase IN ('PENDING','CLAIMED','RUNNING','COMPLETED','FAILED')),
            CONSTRAINT ck_document_processing_operations_fence
                CHECK (fencing_token >= 0)
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_document_processing_operations_tenant_id ON {_TABLE} (tenant_id)"
    )
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    for action, clause in (
        ("select", "USING"),
        ("insert", "WITH CHECK"),
        ("update", "USING"),
        ("delete", "USING"),
    ):
        op.execute(
            f"CREATE POLICY tenant_isolation_{action} ON {_TABLE} "
            f"FOR {action.upper()} {clause} ({_TENANT})"
        )


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {_TABLE}")
