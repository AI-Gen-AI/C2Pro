"""PC-2b.3 (#922, ADR-029/ADR-030): WBS import sources + the IMPORT_REVIEW change-set source link.

Revision ID: 20261007_0003
Revises: 20261007_0002
Create Date: 2026-10-07

IMPORTED SOURCE != DRAFT CANDIDATE != APPROVED WBS. Nothing here creates, submits, approves or
applies WBS.

* ``document_type`` gains ``wbs``: an EXTERNAL WBS source document (input only). It never enters
  ingestion, RAG, N1-N17 or any extraction; it is parsed only by the deterministic WBS importer.
* ``document_revisions`` gains ``uq_document_revisions_scope`` (revision, document, project,
  tenant) so an import can bind a revision of the same document, tenant AND project.
* ``wbs_import_sources`` -- one immutable, deterministic parse of ONE revision with ONE parser
  identity and ONE parse configuration: the exact blob hash, parser id/version, normalized
  configuration and its digest, the ``wbs-import-snapshot/v1`` snapshot and its digest, the
  diagnostics and the parse status (READY | READY_WITH_WARNINGS | INVALID -- no workflow
  authority). INSERT-ONLY; it leaves only with its project (tenant/project cascade). The
  revision FK is NO ACTION: deleting an individual source document can never silently remove an
  import (nor, through it, the provenance of an IMPORT_REVIEW change set).
  ``UNIQUE (tenant_id, import_key)``: concurrent identical parse requests serialize on the key.
* ``wbs_change_sets.source_import_id`` -- the first-class, immutable link of an IMPORT_REVIEW draft
  to its exact import (composite tenant/project FK, NO ACTION). ``entry_mode = 'IMPORT_REVIEW'``
  if and only if the link is set; an IMPORT_REVIEW draft has ``origin = 'import'`` and no base
  baseline (v1: an import establishes Baseline #1 only). No change set ever had IMPORT_REVIEW in
  production when this was written (aggregate preflight: 0 rows), so the checks validate at once.
  The link and the imported-node provenance are outside every WBS digest.

SECURITY: RLS ENABLED + FORCED with fail-closed per-operation policies on ``app.current_tenant``;
``anon``/``authenticated`` get nothing (guarded on role existence). The import writer must be an
active human ``admin`` or ``user`` of the tenant. Guard functions are SECURITY INVOKER with a
pinned search_path and no PUBLIC EXECUTE. The SQL contains no percent sign.

DOWNGRADE drops the link, the table and the guards, then removes ``wbs`` from ``document_type``
ONLY when no document uses it: with WBS documents present it FAILS CLOSED (never ``wbs -> other``).

Supabase CLI mirror: supabase/migrations/20261007000300_pc2b3_wbs_import_sources.sql, rendered
from ``ENUM_STATEMENT`` + ``UPGRADE_STATEMENTS`` by ``supabase_sql()`` (parity is tested).
"""

from __future__ import annotations

from alembic import op

revision = "20261007_0003"
down_revision = "20261007_0002"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261007000300_pc2b3_wbs_import_sources.sql"

_TENANT = "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"
_DIGEST = "'^sha256:[0-9a-f]{64}$'"

# ALTER TYPE ... ADD VALUE: the new label is never used in this migration's own transaction.
ENUM_STATEMENT = "ALTER TYPE public.document_type ADD VALUE IF NOT EXISTS 'wbs'"

REVISION_SCOPE_SQL = (
    "ALTER TABLE public.document_revisions ADD CONSTRAINT uq_document_revisions_scope "
    "UNIQUE (revision_id, document_id, project_id, tenant_id)"
)

IMPORT_SOURCES_SQL = f"""
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
    CONSTRAINT ck_wbs_import_sources_blob_hash CHECK (blob_hash ~ '^[0-9a-f]{{64}}$'),
    CONSTRAINT ck_wbs_import_sources_format CHECK (format IN ('xlsx', 'csv', 'json')),
    CONSTRAINT ck_wbs_import_sources_parser CHECK ((format = 'xlsx' AND parser_id = 'wbs-xlsx')
        OR (format = 'csv' AND parser_id = 'wbs-csv') OR (format = 'json' AND parser_id = 'wbs-json')),
    CONSTRAINT ck_wbs_import_sources_parser_version CHECK (parser_version ~ '^v[0-9]+$'),
    CONSTRAINT ck_wbs_import_sources_parse_config CHECK (jsonb_typeof(parse_config) = 'object'),
    CONSTRAINT ck_wbs_import_sources_parse_config_digest CHECK (parse_config_digest ~ {_DIGEST}),
    CONSTRAINT ck_wbs_import_sources_import_key CHECK (import_key ~ {_DIGEST}),
    CONSTRAINT ck_wbs_import_sources_schema CHECK (snapshot_schema_version = 'wbs-import-snapshot/v1'),
    CONSTRAINT ck_wbs_import_sources_snapshot CHECK (jsonb_typeof(snapshot) = 'object'),
    CONSTRAINT ck_wbs_import_sources_snapshot_digest CHECK (snapshot_digest ~ {_DIGEST}),
    CONSTRAINT ck_wbs_import_sources_diagnostics CHECK (jsonb_typeof(diagnostics) = 'array'),
    CONSTRAINT ck_wbs_import_sources_counts CHECK (row_count >= 0 AND warning_count >= 0 AND blocking_count >= 0),
    CONSTRAINT ck_wbs_import_sources_status CHECK (status IN ('READY', 'READY_WITH_WARNINGS', 'INVALID')),
    CONSTRAINT ck_wbs_import_sources_status_counts CHECK ((status = 'INVALID') = (blocking_count > 0)
        AND (status = 'READY_WITH_WARNINGS') = (blocking_count = 0 AND warning_count > 0)),
    CONSTRAINT ck_wbs_import_sources_created_by_kind CHECK (created_by_kind = 'human')
)"""

INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX ix_wbs_import_sources_document ON public.wbs_import_sources (tenant_id, project_id, document_id)",
)

CHANGE_SET_LINK_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE public.wbs_change_sets ADD COLUMN source_import_id uuid",
    "ALTER TABLE public.wbs_change_sets ADD CONSTRAINT fk_wbs_change_sets_source_import "
    "FOREIGN KEY (tenant_id, project_id, source_import_id) "
    "REFERENCES public.wbs_import_sources (tenant_id, project_id, id) ON DELETE NO ACTION",
    "ALTER TABLE public.wbs_change_sets ADD CONSTRAINT ck_wbs_change_sets_source_import "
    "CHECK ((entry_mode = 'IMPORT_REVIEW') = (source_import_id IS NOT NULL))",
    "ALTER TABLE public.wbs_change_sets ADD CONSTRAINT ck_wbs_change_sets_import_review_first_baseline "
    "CHECK (entry_mode <> 'IMPORT_REVIEW' OR (origin = 'import' AND base_baseline_id IS NULL))",
    "CREATE INDEX ix_wbs_change_sets_source_import ON public.wbs_change_sets (source_import_id) "
    "WHERE source_import_id IS NOT NULL",
)

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

FUNCTION_SIGNATURES = (
    "public.wbs_import_sources_guard()",
    "public.wbs_change_sets_source_import_guard()",
)

TRIGGER_STATEMENTS: tuple[str, ...] = (
    "CREATE TRIGGER trg_wbs_import_sources_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_import_sources "
    "FOR EACH ROW EXECUTE FUNCTION public.wbs_import_sources_guard()",
    "CREATE TRIGGER trg_wbs_change_sets_source_import_guard BEFORE INSERT OR UPDATE ON public.wbs_change_sets "
    "FOR EACH ROW EXECUTE FUNCTION public.wbs_change_sets_source_import_guard()",
)

RLS_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE public.wbs_import_sources ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.wbs_import_sources FORCE ROW LEVEL SECURITY",
    f"CREATE POLICY wbs_import_sources_tenant_select ON public.wbs_import_sources FOR SELECT USING ({_TENANT})",
    f"CREATE POLICY wbs_import_sources_tenant_insert ON public.wbs_import_sources FOR INSERT WITH CHECK ({_TENANT})",
    f"CREATE POLICY wbs_import_sources_tenant_update ON public.wbs_import_sources FOR UPDATE USING ({_TENANT}) "
    f"WITH CHECK ({_TENANT})",
    f"CREATE POLICY wbs_import_sources_tenant_delete ON public.wbs_import_sources FOR DELETE USING ({_TENANT})",
)

# Supabase platform roles do not exist on plain PostgreSQL (CI, local): guard on existence.
_REVOKE_DATA_API_TEMPLATE = """
DO $do$
DECLARE
    v_role text;
BEGIN
    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = v_role) THEN
            EXECUTE 'REVOKE ALL ON TABLE public.wbs_import_sources FROM ' || quote_ident(v_role);
            -- Supabase default privileges grant EXECUTE on new public functions to these roles.
            EXECUTE 'REVOKE ALL ON FUNCTION {functions} FROM ' || quote_ident(v_role);
        END IF;
    END LOOP;
END
$do$"""
REVOKE_DATA_API_SQL = _REVOKE_DATA_API_TEMPLATE.replace("{functions}", ", ".join(FUNCTION_SIGNATURES))

UPGRADE_STATEMENTS: tuple[str, ...] = (
    REVISION_SCOPE_SQL,
    IMPORT_SOURCES_SQL,
    *INDEX_STATEMENTS,
    *CHANGE_SET_LINK_STATEMENTS,
    *FUNCTION_STATEMENTS,
    *(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC" for signature in FUNCTION_SIGNATURES),
    *TRIGGER_STATEMENTS,
    *RLS_STATEMENTS,
    REVOKE_DATA_API_SQL,
)

# PostgreSQL cannot drop an enum label: rebuild the type without 'wbs', but ONLY when no document
# uses it. With WBS documents present the downgrade fails closed -- never 'wbs' -> 'other'.
ENUM_DOWNGRADE_SQL = """
DO $do$
DECLARE
    v_labels text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
                    WHERE t.typname = 'document_type' AND e.enumlabel = 'wbs') THEN
        RETURN;
    END IF;
    IF EXISTS (SELECT 1 FROM public.documents d WHERE d.document_type::text = 'wbs') THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'cannot remove document_type wbs: WBS source documents exist (delete or migrate them first)';
    END IF;
    SELECT string_agg(quote_literal(e.enumlabel), ', ' ORDER BY e.enumsortorder) INTO v_labels
      FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
     WHERE t.typname = 'document_type' AND e.enumlabel <> 'wbs';
    ALTER TYPE public.document_type RENAME TO document_type_pc2b3_old;
    EXECUTE 'CREATE TYPE public.document_type AS ENUM (' || v_labels || ')';
    ALTER TABLE public.documents ALTER COLUMN document_type TYPE public.document_type
        USING document_type::text::public.document_type;
    DROP TYPE public.document_type_pc2b3_old;
END
$do$"""

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    "DROP TRIGGER IF EXISTS trg_wbs_change_sets_source_import_guard ON public.wbs_change_sets",
    "DROP INDEX IF EXISTS public.ix_wbs_change_sets_source_import",
    "ALTER TABLE public.wbs_change_sets DROP CONSTRAINT IF EXISTS ck_wbs_change_sets_import_review_first_baseline",
    "ALTER TABLE public.wbs_change_sets DROP CONSTRAINT IF EXISTS ck_wbs_change_sets_source_import",
    "ALTER TABLE public.wbs_change_sets DROP CONSTRAINT IF EXISTS fk_wbs_change_sets_source_import",
    "ALTER TABLE public.wbs_change_sets DROP COLUMN IF EXISTS source_import_id",
    "DROP TABLE IF EXISTS public.wbs_import_sources",
    *(f"DROP FUNCTION IF EXISTS {signature}" for signature in reversed(FUNCTION_SIGNATURES)),
    "ALTER TABLE public.document_revisions DROP CONSTRAINT IF EXISTS uq_document_revisions_scope",
    ENUM_DOWNGRADE_SQL,
)


def supabase_sql() -> str:
    """The Supabase CLI mirror: the enum label, then the same upgrade statements, in order."""
    header = (
        "-- PC-2b.3 (#922): WBS import sources + IMPORT_REVIEW change-set source link (document_type wbs).\n"
        "-- Mirror of apps/api/alembic/versions/20261007_0003_pc2b3_wbs_import_sources.py "
        "(rendered from ENUM_STATEMENT + UPGRADE_STATEMENTS; do not edit by hand).\n"
    )
    statements = (ENUM_STATEMENT, *UPGRADE_STATEMENTS)
    return header + "\n" + "\n\n".join(statement.strip() + ";" for statement in statements) + "\n"


def upgrade() -> None:
    # ADD VALUE runs in its own committed step (the established document_type pattern).
    with op.get_context().autocommit_block():
        op.execute(ENUM_STATEMENT)
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
