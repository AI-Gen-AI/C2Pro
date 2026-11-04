-- C2Pro: revision-scoped source observations for XLSX budgets and schedules.
-- Mirror of Alembic 20261104_0001_document_source_units.py.
-- Additive schema only; no data backfill and no trust promotion.

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
);

CREATE INDEX IF NOT EXISTS ix_document_source_units_project
    ON public.document_source_units (tenant_id, project_id, family, revision_id);
CREATE INDEX IF NOT EXISTS ix_document_source_units_document
    ON public.document_source_units (tenant_id, document_id, revision_id);

ALTER TABLE public.document_source_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_source_units FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS document_source_units_tenant_select ON public.document_source_units;
CREATE POLICY document_source_units_tenant_select ON public.document_source_units
    FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS document_source_units_tenant_insert ON public.document_source_units;
CREATE POLICY document_source_units_tenant_insert ON public.document_source_units
    FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS document_source_units_tenant_update ON public.document_source_units;
CREATE POLICY document_source_units_tenant_update ON public.document_source_units
    FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DROP POLICY IF EXISTS document_source_units_tenant_delete ON public.document_source_units;
CREATE POLICY document_source_units_tenant_delete ON public.document_source_units
    FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
