"""Store XLSX budget/schedule source units by immutable revision.

Revision ID: 20261104_0001
Revises: 20261101_0001

Additive schema only: no source rows are backfilled or promoted to trusted.
The worker writes these records only in the fenced document ingestion transaction.
"""

from alembic import op

revision = "20261104_0001"
down_revision = "20261101_0001"
branch_labels = None
depends_on = None

_TENANT = "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"

CREATE_SOURCE_UNITS = """
CREATE TABLE IF NOT EXISTS public.document_source_units (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    document_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    blob_hash text NOT NULL,
    family varchar(16) NOT NULL CHECK (family IN ('budget', 'schedule')),
    source_locator text NOT NULL CHECK (length(source_locator) > 0),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    unit_sha256 varchar(64) NOT NULL,
    observed_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_document_source_units_revision_locator
        UNIQUE (tenant_id, document_id, revision_id, family, source_locator),
    CONSTRAINT fk_document_source_units_revision
        FOREIGN KEY (revision_id, document_id, project_id, tenant_id)
        REFERENCES public.document_revisions
            (revision_id, document_id, project_id, tenant_id)
        ON DELETE CASCADE
)
"""

_POLICIES = {
    "select": f"FOR SELECT USING ({_TENANT})",
    "insert": f"FOR INSERT WITH CHECK ({_TENANT})",
    "delete": f"FOR DELETE USING ({_TENANT})",
    "update": f"FOR UPDATE USING ({_TENANT}) WITH CHECK ({_TENANT})",
}


def upgrade() -> None:
    op.execute(CREATE_SOURCE_UNITS)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_source_units_project "
        "ON public.document_source_units (tenant_id, project_id, family, revision_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_source_units_document "
        "ON public.document_source_units (tenant_id, document_id, revision_id)"
    )
    op.execute("ALTER TABLE public.document_source_units ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.document_source_units FORCE ROW LEVEL SECURITY")
    for action, clause in _POLICIES.items():
        op.execute(
            f"DROP POLICY IF EXISTS document_source_units_tenant_{action} "
            "ON public.document_source_units"
        )
        op.execute(
            f"CREATE POLICY document_source_units_tenant_{action} "
            f"ON public.document_source_units {clause}"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.document_source_units")
