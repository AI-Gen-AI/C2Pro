-- PC-2b.3 (#922): WBS import sources + IMPORT_REVIEW change-set source link (document_type wbs).
-- Mirror of apps/api/alembic/versions/20261007_0003_pc2b3_wbs_import_sources.py (rendered from ENUM_STATEMENT + UPGRADE_STATEMENTS; do not edit by hand).

ALTER TYPE public.document_type ADD VALUE IF NOT EXISTS 'wbs';

ALTER TABLE public.document_revisions ADD CONSTRAINT uq_document_revisions_scope UNIQUE (revision_id, document_id, project_id, tenant_id);

CREATE TABLE public.wbs_import_sources (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    document_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    blob_hash text NOT NULL,
    format text NOT NULL,
    parser_id text NOT NULL,
    parser_version text NOT NULL,
    parse_config jsonb NOT NULL,
    parse_config_digest text NOT NULL,
    import_key text NOT NULL,
    snapshot_schema_version text NOT NULL,
    snapshot jsonb NOT NULL,
    snapshot_digest text NOT NULL,
    diagnostics jsonb NOT NULL,
    row_count integer NOT NULL,
    warning_count integer NOT NULL,
    blocking_count integer NOT NULL,
    status text NOT NULL,
    created_by uuid NOT NULL,
    created_by_kind text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_wbs_import_sources_tenant_project_id UNIQUE (tenant_id, project_id, id),
    CONSTRAINT uq_wbs_import_sources_import_key UNIQUE (tenant_id, import_key),
    CONSTRAINT fk_wbs_import_sources_project FOREIGN KEY (tenant_id, project_id)
        REFERENCES public.projects (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_wbs_import_sources_revision FOREIGN KEY (revision_id, document_id, project_id, tenant_id)
        REFERENCES public.document_revisions (revision_id, document_id, project_id, tenant_id) ON DELETE NO ACTION,
    CONSTRAINT ck_wbs_import_sources_blob_hash CHECK (blob_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_wbs_import_sources_format CHECK (format IN ('xlsx', 'csv', 'json')),
    CONSTRAINT ck_wbs_import_sources_parser CHECK ((format = 'xlsx' AND parser_id = 'wbs-xlsx')
        OR (format = 'csv' AND parser_id = 'wbs-csv') OR (format = 'json' AND parser_id = 'wbs-json')),
    CONSTRAINT ck_wbs_import_sources_parser_version CHECK (parser_version ~ '^v[0-9]+$'),
    CONSTRAINT ck_wbs_import_sources_parse_config CHECK (jsonb_typeof(parse_config) = 'object'),
    CONSTRAINT ck_wbs_import_sources_parse_config_digest CHECK (parse_config_digest ~ '^sha256:[0-9a-f]{64}$'),
    CONSTRAINT ck_wbs_import_sources_import_key CHECK (import_key ~ '^sha256:[0-9a-f]{64}$'),
    CONSTRAINT ck_wbs_import_sources_schema CHECK (snapshot_schema_version = 'wbs-import-snapshot/v1'),
    CONSTRAINT ck_wbs_import_sources_snapshot CHECK (jsonb_typeof(snapshot) = 'object'),
    CONSTRAINT ck_wbs_import_sources_snapshot_digest CHECK (snapshot_digest ~ '^sha256:[0-9a-f]{64}$'),
    CONSTRAINT ck_wbs_import_sources_diagnostics CHECK (jsonb_typeof(diagnostics) = 'array'),
    CONSTRAINT ck_wbs_import_sources_counts CHECK (row_count >= 0 AND warning_count >= 0 AND blocking_count >= 0),
    CONSTRAINT ck_wbs_import_sources_status CHECK (status IN ('READY', 'READY_WITH_WARNINGS', 'INVALID')),
    CONSTRAINT ck_wbs_import_sources_status_counts CHECK ((status = 'INVALID') = (blocking_count > 0)
        AND (status = 'READY_WITH_WARNINGS') = (blocking_count = 0 AND warning_count > 0)),
    CONSTRAINT ck_wbs_import_sources_created_by_kind CHECK (created_by_kind = 'human')
);

CREATE INDEX ix_wbs_import_sources_document ON public.wbs_import_sources (tenant_id, project_id, document_id);

ALTER TABLE public.wbs_change_sets ADD COLUMN source_import_id uuid;

ALTER TABLE public.wbs_change_sets ADD CONSTRAINT fk_wbs_change_sets_source_import FOREIGN KEY (tenant_id, project_id, source_import_id) REFERENCES public.wbs_import_sources (tenant_id, project_id, id) ON DELETE NO ACTION;

ALTER TABLE public.wbs_change_sets ADD CONSTRAINT ck_wbs_change_sets_source_import CHECK ((entry_mode = 'IMPORT_REVIEW') = (source_import_id IS NOT NULL));

ALTER TABLE public.wbs_change_sets ADD CONSTRAINT ck_wbs_change_sets_import_review_first_baseline CHECK (entry_mode <> 'IMPORT_REVIEW' OR (origin = 'import' AND base_baseline_id IS NULL));

CREATE INDEX ix_wbs_change_sets_source_import ON public.wbs_change_sets (source_import_id) WHERE source_import_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.wbs_import_sources_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS import sources are immutable: parse again to create a new import';
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM public.projects p WHERE p.id = OLD.project_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'WBS import sources are provenance history: they leave only with their project';
        END IF;
        RETURN OLD;
    END IF;
    -- The source document hidden by the writer's RLS context is simply not found: fail closed.
    IF NOT EXISTS (SELECT 1 FROM public.documents d
                    WHERE d.id = NEW.document_id AND d.tenant_id = NEW.tenant_id AND d.project_id = NEW.project_id
                      AND d.document_type::text = 'wbs') THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a WBS import source must be a wbs document of the same tenant and project';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.document_revisions r
                    WHERE r.revision_id = NEW.revision_id AND r.document_id = NEW.document_id
                      AND r.tenant_id = NEW.tenant_id AND r.project_id = NEW.project_id
                      AND r.blob_hash = NEW.blob_hash) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a WBS import source binds the exact immutable blob of its document revision';
    END IF;
    PERFORM public.wbs_governance_require_user_role(NEW.tenant_id, NEW.created_by, ARRAY['admin', 'user'],
                                                    'importing a WBS source');
    RETURN NEW;
END
$fn$;

CREATE OR REPLACE FUNCTION public.wbs_change_sets_source_import_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.source_import_id IS DISTINCT FROM OLD.source_import_id THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'the import source of a WBS change set is immutable';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.source_import_id IS NOT NULL AND NOT EXISTS (
           SELECT 1 FROM public.wbs_import_sources i
            WHERE i.id = NEW.source_import_id AND i.tenant_id = NEW.tenant_id AND i.project_id = NEW.project_id
              AND i.status <> 'INVALID') THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'an IMPORT_REVIEW change set needs a valid (non-INVALID) import source of its project';
    END IF;
    RETURN NEW;
END
$fn$;

REVOKE ALL ON FUNCTION public.wbs_import_sources_guard() FROM PUBLIC;

REVOKE ALL ON FUNCTION public.wbs_change_sets_source_import_guard() FROM PUBLIC;

CREATE TRIGGER trg_wbs_import_sources_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_import_sources FOR EACH ROW EXECUTE FUNCTION public.wbs_import_sources_guard();

CREATE TRIGGER trg_wbs_change_sets_source_import_guard BEFORE INSERT OR UPDATE ON public.wbs_change_sets FOR EACH ROW EXECUTE FUNCTION public.wbs_change_sets_source_import_guard();

ALTER TABLE public.wbs_import_sources ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.wbs_import_sources FORCE ROW LEVEL SECURITY;

CREATE POLICY wbs_import_sources_tenant_select ON public.wbs_import_sources FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_import_sources_tenant_insert ON public.wbs_import_sources FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_import_sources_tenant_update ON public.wbs_import_sources FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_import_sources_tenant_delete ON public.wbs_import_sources FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DO $do$
DECLARE
    v_role text;
BEGIN
    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = v_role) THEN
            EXECUTE 'REVOKE ALL ON TABLE public.wbs_import_sources FROM ' || quote_ident(v_role);
            -- Supabase default privileges grant EXECUTE on new public functions to these roles.
            EXECUTE 'REVOKE ALL ON FUNCTION public.wbs_import_sources_guard(), public.wbs_change_sets_source_import_guard() FROM ' || quote_ident(v_role);
        END IF;
    END LOOP;
END
$do$;
