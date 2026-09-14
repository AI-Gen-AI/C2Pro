-- ADR-025 (1/2): the canonical Project Controls WBS can hold every application WBS node.
-- Mirror of apps/api/alembic/versions/20260915_0001_adr025_canonical_wbs_schema.py (rendered from UPGRADE_STATEMENTS; do not edit by hand).

ALTER TABLE public.wbs_nodes
    ALTER COLUMN code TYPE varchar,
    ALTER COLUMN name TYPE varchar,
    ALTER COLUMN budget_allocated TYPE numeric(18, 2),
    ALTER COLUMN budget_spent TYPE numeric(18, 2);

ALTER TABLE public.wbs_nodes ADD COLUMN IF NOT EXISTS source_clause_id uuid;

ALTER TABLE public.wbs_nodes ADD COLUMN IF NOT EXISTS source_document_id uuid;

ALTER TABLE public.wbs_nodes ADD COLUMN IF NOT EXISTS version integer NOT NULL DEFAULT 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.wbs_nodes'::regclass AND conname = 'wbs_nodes_source_document_id_fkey'
    ) THEN
        ALTER TABLE public.wbs_nodes
            ADD CONSTRAINT wbs_nodes_source_document_id_fkey
            FOREIGN KEY (source_document_id) REFERENCES public.documents (id) ON DELETE CASCADE;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_wbs_nodes_project_source_document
    ON public.wbs_nodes (project_id, source_document_id);

DO $$
DECLARE
    legacy text;
BEGIN
    FOREACH legacy IN ARRAY ARRAY['procurement_wbs_items', 'wbs_items'] LOOP
        IF to_regclass('public.' || legacy) IS NULL THEN
            CONTINUE;  -- the Supabase CLI schema never had wbs_items
        END IF;
        EXECUTE format(
            'ALTER TABLE public.%I '
            'ADD COLUMN IF NOT EXISTS canonical_wbs_node_id uuid, '
            'ADD COLUMN IF NOT EXISTS canonical_mapping text, '
            'ADD COLUMN IF NOT EXISTS canonical_mapping_reason text',
            legacy
        );
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = format('public.%I', legacy)::regclass
              AND conname = 'ck_' || legacy || '_canonical_mapping'
        ) THEN
            EXECUTE format(
                'ALTER TABLE public.%I ADD CONSTRAINT %I CHECK '
                '(canonical_mapping IS NULL OR canonical_mapping IN (''DIRECT_MAP'', ''DERIVED_MAP'', ''AMBIGUOUS'', ''ORPHAN''))',
                legacy,
                'ck_' || legacy || '_canonical_mapping'
            );
        END IF;
    END LOOP;
END
$$;
