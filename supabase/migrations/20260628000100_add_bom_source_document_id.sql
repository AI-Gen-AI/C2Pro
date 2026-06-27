-- TASK-COH-BUD-IDEM-003: make parsed BOM rows source-document scoped.

ALTER TABLE public.procurement_bom_items
    ADD COLUMN IF NOT EXISTS source_document_id uuid;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_procurement_bom_items_source_document'
    ) THEN
        ALTER TABLE public.procurement_bom_items
            ADD CONSTRAINT fk_procurement_bom_items_source_document
            FOREIGN KEY (source_document_id)
            REFERENCES public.documents(id)
            ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_procurement_bom_project_source_document
    ON public.procurement_bom_items(project_id, source_document_id);

ALTER TABLE public.procurement_bom_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.procurement_bom_items FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_procurement_bom_items ON public.procurement_bom_items;
CREATE POLICY tenant_isolation_procurement_bom_items
    ON public.procurement_bom_items
    FOR ALL
    USING (
        project_id IN (
            SELECT id
            FROM public.projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
    )
    WITH CHECK (
        project_id IN (
            SELECT id
            FROM public.projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
    );
