"""WBS import source guard functions and triggers (PC-2b.3 #922).

A literal copy of the DDL in alembic revision ``20261007_0003``: the test schema is built with
``Base.metadata.create_all`` and must carry the same database-enforced invariants.
tests/unit/product_control/test_pc2b3_wbs_import_migration.py keeps the two equal.
Edit the migration first (or add a new one), then mirror it here.
"""

from __future__ import annotations

IMPORT_SOURCES_GUARD_FUNCTION_SQL = """
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
$fn$"""

CHANGE_SET_SOURCE_IMPORT_GUARD_FUNCTION_SQL = """
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
$fn$"""

FUNCTION_STATEMENTS: tuple[str, ...] = (IMPORT_SOURCES_GUARD_FUNCTION_SQL, CHANGE_SET_SOURCE_IMPORT_GUARD_FUNCTION_SQL)

IMPORT_SOURCES_TRIGGER_SQL = (
    "CREATE TRIGGER trg_wbs_import_sources_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_import_sources "
    "FOR EACH ROW EXECUTE FUNCTION public.wbs_import_sources_guard()"
)
CHANGE_SET_SOURCE_IMPORT_TRIGGER_SQL = (
    "CREATE TRIGGER trg_wbs_change_sets_source_import_guard BEFORE INSERT OR UPDATE ON public.wbs_change_sets "
    "FOR EACH ROW EXECUTE FUNCTION public.wbs_change_sets_source_import_guard()"
)
TRIGGER_STATEMENTS: tuple[str, ...] = (IMPORT_SOURCES_TRIGGER_SQL, CHANGE_SET_SOURCE_IMPORT_TRIGGER_SQL)

IMPORT_FORMAT_CHECK = (
    "(format = 'xlsx' AND parser_id = 'wbs-xlsx') OR (format = 'csv' AND parser_id = 'wbs-csv') "
    "OR (format = 'json' AND parser_id = 'wbs-json')"
)
IMPORT_STATUS_CHECK = (
    "(status = 'INVALID') = (blocking_count > 0) "
    "AND (status = 'READY_WITH_WARNINGS') = (blocking_count = 0 AND warning_count > 0)"
)
SOURCE_IMPORT_CHECK = "(entry_mode = 'IMPORT_REVIEW') = (source_import_id IS NOT NULL)"
IMPORT_REVIEW_FIRST_BASELINE_CHECK = "entry_mode <> 'IMPORT_REVIEW' OR (origin = 'import' AND base_baseline_id IS NULL)"
