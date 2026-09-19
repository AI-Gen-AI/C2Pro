-- TASK-DOC-WBS-ORPHAN-IDEM: schedule re-parses must replace the WBS rows produced
-- by the same source document instead of colliding on
-- uq_procurement_wbs_project_code, and deleting a document must cascade to its
-- schedule-derived WBS rows so orphaned activities no longer inflate the audit.
--
-- Mirrors the BOM linkage added in 20260628000100_add_bom_source_document_id.sql.
-- Mirror of apps/api/alembic/versions/20260814_0002_add_wbs_source_document_id.py

ALTER TABLE public.procurement_wbs_items
    ADD COLUMN IF NOT EXISTS source_document_id uuid;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_procurement_wbs_items_source_document'
    ) THEN
        ALTER TABLE public.procurement_wbs_items
            ADD CONSTRAINT fk_procurement_wbs_items_source_document
            FOREIGN KEY (source_document_id)
            REFERENCES public.documents(id)
            ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_procurement_wbs_project_source_document
    ON public.procurement_wbs_items(project_id, source_document_id);

-- Backfill the new FK column from the source_document_id previously stored in
-- wbs_metadata (JSONB), but only where the referenced document still exists.
-- Rows pointing at a deleted (or non-UUID) document remain NULL -- those are
-- true orphans or manual/AI-generated rows and must not gain a dangling FK.
UPDATE public.procurement_wbs_items AS w
SET source_document_id = sub.doc_id
FROM (
    SELECT wi.id AS wbs_id,
           (wi.wbs_metadata->>'source_document_id')::uuid AS doc_id
    FROM public.procurement_wbs_items wi
    WHERE wi.source_document_id IS NULL
      AND wi.wbs_metadata ? 'source_document_id'
      AND wi.wbs_metadata->>'source_document_id'
            ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
) AS sub
JOIN public.documents d ON d.id = sub.doc_id
WHERE w.id = sub.wbs_id;
