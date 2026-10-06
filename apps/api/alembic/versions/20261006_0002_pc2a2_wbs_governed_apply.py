"""PC-2a.2 (#896, ADR-029): governed WBS apply -- explicit retirements and the live-write guard.

Revision ID: 20261006_0002
Revises: 20261006_0001
Create Date: 2026-10-06

Additive only. Nothing here applies, seeds or reclassifies WBS; it gives the governed
approve = apply command (application code) the two database primitives it needs:

* ``wbs_change_set_retirements`` -- every identity that leaves the WBS through a change set,
  with its disposition (REMOVED | SPLIT | MERGED | SUPERSEDED | RETIRED_ON_BASELINE) and a
  ``snapshot`` of what it was. Base-baseline identities (Baseline #N -> #N+1) and, for a first
  baseline only, legacy live rows that the reviewed candidate does not adopt. Editable only
  while the change set is DRAFT, never updated; it is the frozen, auditable disposition set
  that apply verifies and executes. History disappears only with its project (cascade).
* ``wbs_nodes_governed_write_guard`` -- once a project has an approved baseline, a live
  ``wbs_nodes`` INSERT / DELETE / governed-column UPDATE is refused unless the transaction is
  the governed apply of a SUBMITTED change set of that project against its CURRENT baseline
  (``c2pro.wbs_governed_apply``). Non-governed attributes (dates, budget, description,
  metadata, hierarchy caches) stay writable. Projects without a baseline are untouched
  (LEGACY_UNGOVERNED transitional writers, PC-1R).

SECURITY: RLS ENABLED + FORCED with fail-closed per-operation policies on the new table;
``anon``/``authenticated`` get nothing (guarded on role existence); functions are SECURITY
INVOKER with a pinned search_path and no PUBLIC EXECUTE. No percent sign in the SQL.

DOWNGRADE drops the trigger, the two functions and the retirement table (and its history);
it never touches live WBS rows.

Supabase CLI mirror: supabase/migrations/20261006000200_pc2a2_wbs_governed_apply.sql,
rendered from ``UPGRADE_STATEMENTS`` by ``supabase_sql()`` (parity is tested).
"""

from __future__ import annotations

from alembic import op

revision = "20261006_0002"
down_revision = "20261006_0001"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261006000200_pc2a2_wbs_governed_apply.sql"

_TENANT = "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"

RETIREMENTS_SQL = """
CREATE TABLE public.wbs_change_set_retirements (
    change_set_id uuid NOT NULL,
    node_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    disposition text NOT NULL,
    source text NOT NULL,
    snapshot jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_wbs_change_set_retirements PRIMARY KEY (change_set_id, node_id),
    CONSTRAINT fk_wbs_change_set_retirements_change_set FOREIGN KEY (tenant_id, project_id, change_set_id)
        REFERENCES public.wbs_change_sets (tenant_id, project_id, id) ON DELETE CASCADE,
    CONSTRAINT ck_wbs_change_set_retirements_disposition CHECK (
        disposition IN ('REMOVED', 'SPLIT', 'MERGED', 'SUPERSEDED', 'RETIRED_ON_BASELINE')),
    CONSTRAINT ck_wbs_change_set_retirements_source CHECK (source IN ('baseline', 'legacy')),
    CONSTRAINT ck_wbs_change_set_retirements_legacy_disposition CHECK (
        disposition <> 'RETIRED_ON_BASELINE' OR source = 'legacy'),
    CONSTRAINT ck_wbs_change_set_retirements_snapshot CHECK (jsonb_typeof(snapshot) = 'object')
)"""

INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX ix_wbs_change_set_retirements_tenant_project "
    "ON public.wbs_change_set_retirements (tenant_id, project_id)",
    "CREATE INDEX ix_wbs_change_set_retirements_node ON public.wbs_change_set_retirements (node_id)",
)

RETIREMENTS_GUARD_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_change_set_retirements_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_status text;
    v_base uuid;
    v_project uuid;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS retirements are immutable: remove and add instead';
    END IF;
    SELECT cs.status, cs.base_baseline_id, cs.project_id INTO v_status, v_base, v_project
      FROM public.wbs_change_sets cs
     WHERE cs.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.change_set_id ELSE NEW.change_set_id END;
    IF NOT FOUND THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION USING ERRCODE = 'foreign_key_violation', MESSAGE = 'unknown WBS change set';
    END IF;
    IF v_status <> 'DRAFT' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS retirements are editable only while the change set is DRAFT';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    IF NEW.source = 'baseline' THEN
        IF v_base IS NULL OR NOT EXISTS (
               SELECT 1 FROM public.wbs_baseline_nodes bn WHERE bn.baseline_id = v_base AND bn.node_id = NEW.node_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'a baseline retirement must name an identity of the base baseline';
        END IF;
    ELSIF v_base IS NOT NULL OR NOT EXISTS (
              SELECT 1 FROM public.wbs_nodes w WHERE w.id = NEW.node_id AND w.project_id = v_project) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'only a first baseline retires live legacy rows of the same project';
    END IF;
    IF EXISTS (SELECT 1 FROM public.wbs_change_set_nodes n
                WHERE n.change_set_id = NEW.change_set_id AND n.node_id = NEW.node_id) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a retired WBS identity cannot stay in the candidate';
    END IF;
    RETURN NEW;
END
$fn$"""

LIVE_WRITE_GUARD_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_nodes_governed_write_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_project uuid;
    v_current uuid;
    v_apply text;
BEGIN
    IF TG_OP = 'UPDATE' AND (NEW.id, NEW.tenant_id, NEW.project_id, NEW.parent_id, NEW.sort_order, NEW.code,
                             NEW.name, NEW.control_level, NEW.decomposition_kind, NEW.dictionary)
                    IS NOT DISTINCT FROM (OLD.id, OLD.tenant_id, OLD.project_id, OLD.parent_id, OLD.sort_order,
                             OLD.code, OLD.name, OLD.control_level, OLD.decomposition_kind, OLD.dictionary) THEN
        RETURN NEW;
    END IF;
    FOREACH v_project IN ARRAY CASE
            WHEN TG_OP = 'INSERT' THEN ARRAY[NEW.project_id]
            WHEN TG_OP = 'DELETE' THEN ARRAY[OLD.project_id]
            ELSE ARRAY[OLD.project_id, NEW.project_id] END LOOP
        -- A project being deleted takes its WBS with it (cascade).
        CONTINUE WHEN NOT EXISTS (SELECT 1 FROM public.projects p WHERE p.id = v_project);
        SELECT b.id INTO v_current FROM public.wbs_baselines b
         WHERE b.project_id = v_project ORDER BY b.baseline_no DESC LIMIT 1;
        CONTINUE WHEN v_current IS NULL;  -- no approved baseline: LEGACY_UNGOVERNED / NO_WBS
        v_apply := NULLIF(current_setting('c2pro.wbs_governed_apply', true), '');
        IF v_apply IS NULL OR NOT EXISTS (
               SELECT 1 FROM public.wbs_change_sets cs
                WHERE cs.id::text = v_apply AND cs.project_id = v_project AND cs.status = 'SUBMITTED'
                  AND cs.base_baseline_id = v_current) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'the WBS of this project is governed by an approved baseline: change it through a WBS change set';
        END IF;
    END LOOP;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END
$fn$"""

FUNCTION_STATEMENTS: tuple[str, ...] = (RETIREMENTS_GUARD_FUNCTION_SQL, LIVE_WRITE_GUARD_FUNCTION_SQL)

FUNCTION_SIGNATURES = (
    "public.wbs_change_set_retirements_guard()",
    "public.wbs_nodes_governed_write_guard()",
)

TRIGGER_STATEMENTS: tuple[str, ...] = (
    "CREATE TRIGGER trg_wbs_change_set_retirements_guard BEFORE INSERT OR UPDATE OR DELETE "
    "ON public.wbs_change_set_retirements FOR EACH ROW EXECUTE FUNCTION public.wbs_change_set_retirements_guard()",
    "CREATE TRIGGER trg_wbs_nodes_governed_write_guard BEFORE INSERT OR DELETE OR UPDATE OF id, tenant_id, "
    "project_id, parent_id, sort_order, code, name, control_level, decomposition_kind, dictionary "
    "ON public.wbs_nodes FOR EACH ROW EXECUTE FUNCTION public.wbs_nodes_governed_write_guard()",
)

_TABLE = "wbs_change_set_retirements"

RLS_STATEMENTS: tuple[str, ...] = (
    f"ALTER TABLE public.{_TABLE} ENABLE ROW LEVEL SECURITY",
    f"ALTER TABLE public.{_TABLE} FORCE ROW LEVEL SECURITY",
    f"CREATE POLICY {_TABLE}_tenant_select ON public.{_TABLE} FOR SELECT USING ({_TENANT})",
    f"CREATE POLICY {_TABLE}_tenant_insert ON public.{_TABLE} FOR INSERT WITH CHECK ({_TENANT})",
    f"CREATE POLICY {_TABLE}_tenant_update ON public.{_TABLE} FOR UPDATE USING ({_TENANT}) WITH CHECK ({_TENANT})",
    f"CREATE POLICY {_TABLE}_tenant_delete ON public.{_TABLE} FOR DELETE USING ({_TENANT})",
)

# Supabase platform roles do not exist on plain PostgreSQL (CI, local): guard on existence.
_REVOKE_DATA_API_TEMPLATE = """
DO $do$
DECLARE
    v_role text;
BEGIN
    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = v_role) THEN
            EXECUTE 'REVOKE ALL ON TABLE public.wbs_change_set_retirements FROM ' || quote_ident(v_role);
            -- Supabase default privileges grant EXECUTE on new public functions to these roles.
            EXECUTE 'REVOKE ALL ON FUNCTION {functions} FROM ' || quote_ident(v_role);
        END IF;
    END LOOP;
END
$do$"""
REVOKE_DATA_API_SQL = _REVOKE_DATA_API_TEMPLATE.replace("{functions}", ", ".join(FUNCTION_SIGNATURES))

UPGRADE_STATEMENTS: tuple[str, ...] = (
    RETIREMENTS_SQL,
    *INDEX_STATEMENTS,
    *FUNCTION_STATEMENTS,
    *(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC" for signature in FUNCTION_SIGNATURES),
    *TRIGGER_STATEMENTS,
    *RLS_STATEMENTS,
    REVOKE_DATA_API_SQL,
)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    "DROP TRIGGER IF EXISTS trg_wbs_nodes_governed_write_guard ON public.wbs_nodes",
    "DROP TABLE IF EXISTS public.wbs_change_set_retirements",
    *(f"DROP FUNCTION IF EXISTS {signature}" for signature in reversed(FUNCTION_SIGNATURES)),
)


def supabase_sql() -> str:
    """The Supabase CLI mirror: the same upgrade statements, in order."""
    header = (
        "-- PC-2a.2 (#896, ADR-029): governed WBS apply -- explicit retirements and the live-write guard.\n"
        "-- Mirror of apps/api/alembic/versions/20261006_0002_pc2a2_wbs_governed_apply.py "
        "(rendered from UPGRADE_STATEMENTS; do not edit by hand).\n"
    )
    return header + "\n" + "\n\n".join(statement.strip() + ";" for statement in UPGRADE_STATEMENTS) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
