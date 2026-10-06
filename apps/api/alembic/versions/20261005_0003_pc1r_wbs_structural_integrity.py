"""PC-1R (#886, ADR-029): canonical WBS structural integrity, project as implicit root.

Revision ID: 20261005_0003
Revises: 20261005_0002
Create Date: 2026-10-05

ADR-029 makes the project the implicit root of its one canonical WBS: top-level
branches are ``parent_id IS NULL`` and there may be several. Hierarchy authority is
``(parent_id, sort_order)``; ``depth``/``lft``/``rgt`` are derived caches and the
visible ``code`` is display data. This revision is STRUCTURAL ONLY -- no baseline,
change-set or approval semantics (PC-2a).

PREFLIGHT (fail closed, no mutation)
------------------------------------
Raises, naming aggregate counts, if any row has a missing parent, a cross-project or
cross-tenant parent, a parent cycle, or a duplicate ``(project_id, code)``. Nothing is
auto-repaired, re-rooted or deleted. FORCE ROW LEVEL SECURITY is lifted (and restored)
inside the same block, as ADR-025 did: it would hide rows from an owner without
BYPASSRLS and make the preflight and the backfill vacuous.

CHANGES
-------
* ``sort_order`` -- backfilled densely per ``(project_id, parent_id)`` in the order users
  see today (nested set, then code, then id); NOT NULL; ``UNIQUE NULLS NOT DISTINCT
  (project_id, parent_id, sort_order) DEFERRABLE INITIALLY DEFERRED`` so top-level
  siblings are covered and reorders/swaps work inside one transaction (PG >= 15).
* Parent FK: ``ON DELETE SET NULL`` (silently re-rooted children) becomes the composite
  ``(tenant_id, project_id, parent_id) -> (tenant_id, project_id, id) ON DELETE NO ACTION``
  (deferred to commit):
  same tenant, same project, never a silent re-root. MATCH SIMPLE leaves top-level rows
  unchecked by design.
* ``uq_wbs_nodes_project_code`` becomes DEFERRABLE INITIALLY DEFERRED (code swaps).
* ``wbs_nodes.source_document_id``: ``ON DELETE CASCADE`` -> ``ON DELETE SET NULL``
  (provenance; deleting a document never deletes WBS scope).
* ``stakeholder_wbs_raci.wbs_item_id`` (CASCADE) and ``procurement_bom_items.wbs_item_id``
  (SET NULL) -> ``ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED``: a node with RACI/BOM
  links cannot be deleted silently. The check is deferred to COMMIT because PostgreSQL runs
  each cascaded delete as its own internal statement: an immediate check could fire while a
  project/tenant deletion has removed the WBS rows but not yet the RACI/BOM rows, making the
  outcome depend on trigger order. The parent FK is deferred for the same reason. Re-added
  NOT VALID and validated in an exception block (ADR-025 pattern).
* Derived-cache guard: a deferred constraint trigger asserts ``depth = 0`` without a
  parent and ``parent.depth + 1`` otherwise, for the row and its children, at commit.
  This also makes a cycle impossible to commit. A plain CHECK is deliberately NOT used:
  it is not deferrable and rejects legitimate two-statement structural writes.

RLS / grants are untouched. The trigger function is SECURITY INVOKER with a pinned
search_path and no PUBLIC EXECUTE grant (trigger invocation does not need it).

DOWNGRADE restores the previous constraint definitions exactly and drops ``sort_order``
and the trigger; it never deletes or rewrites WBS rows.

Supabase CLI mirror: supabase/migrations/20261005000300_pc1r_wbs_structural_integrity.sql,
rendered from ``UPGRADE_STATEMENTS`` by ``supabase_sql()`` (parity is tested).
"""

from __future__ import annotations

from alembic import op

revision = "20261005_0003"
down_revision = "20261005_0002"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261005000300_pc1r_wbs_structural_integrity.sql"

_LIFT_FORCED_RLS = """
    SELECT COALESCE(array_agg(c.oid::regclass), ARRAY[]::regclass[]) INTO forced
    FROM pg_class c
    WHERE c.relforcerowsecurity AND c.oid = to_regclass('public.wbs_nodes');
    FOREACH rel IN ARRAY forced LOOP
        EXECUTE format('ALTER TABLE %s NO FORCE ROW LEVEL SECURITY', rel);
    END LOOP;
"""

_RESTORE_FORCED_RLS = """
    FOREACH rel IN ARRAY forced LOOP
        EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', rel);
    END LOOP;
"""

PREFLIGHT_SQL = f"""
DO $$
DECLARE
    forced regclass[];
    rel regclass;
    missing_parents bigint;
    cross_scope_parents bigint;
    cyclic_nodes bigint;
    duplicate_codes bigint;
BEGIN
{_LIFT_FORCED_RLS}
    SELECT count(*) INTO missing_parents
    FROM public.wbs_nodes c
    WHERE c.parent_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM public.wbs_nodes p WHERE p.id = c.parent_id);

    SELECT count(*) INTO cross_scope_parents
    FROM public.wbs_nodes c
    JOIN public.wbs_nodes p ON p.id = c.parent_id
    WHERE p.project_id <> c.project_id OR p.tenant_id <> c.tenant_id;

    WITH RECURSIVE ancestry(node_id, ancestor_id) AS (
        SELECT id, parent_id FROM public.wbs_nodes WHERE parent_id IS NOT NULL
        UNION ALL
        SELECT a.node_id, n.parent_id
        FROM ancestry a
        JOIN public.wbs_nodes n ON n.id = a.ancestor_id
        WHERE n.parent_id IS NOT NULL
    ) CYCLE ancestor_id SET is_cycle USING walked
    SELECT count(DISTINCT node_id) INTO cyclic_nodes FROM ancestry WHERE is_cycle;

    SELECT count(*) INTO duplicate_codes
    FROM (
        SELECT project_id, code FROM public.wbs_nodes GROUP BY project_id, code HAVING count(*) > 1
    ) duplicates;

    IF missing_parents + cross_scope_parents + cyclic_nodes + duplicate_codes > 0 THEN
        RAISE EXCEPTION
            'PC-1R preflight failed (no row was changed): % missing parent, % cross-project or cross-tenant parent, '
            '% node(s) in or under a parent cycle, % duplicate code(s). Repair explicitly; nothing is auto-repaired.',
            missing_parents, cross_scope_parents, cyclic_nodes, duplicate_codes;
    END IF;
{_RESTORE_FORCED_RLS}
END $$
"""

BACKFILL_SORT_ORDER_SQL = f"""
DO $$
DECLARE
    forced regclass[];
    rel regclass;
BEGIN
{_LIFT_FORCED_RLS}
    WITH ranked AS (
        SELECT id, row_number() OVER (PARTITION BY project_id, parent_id ORDER BY lft, code, id) AS position
        FROM public.wbs_nodes
    )
    UPDATE public.wbs_nodes n SET sort_order = ranked.position
    FROM ranked
    WHERE ranked.id = n.id;
{_RESTORE_FORCED_RLS}
END $$
"""

HIERARCHY_CACHE_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_nodes_verify_hierarchy_cache()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    node public.wbs_nodes%ROWTYPE;
    parent_depth integer;
BEGIN
    -- Deferred: judge the row as it stands at commit, not as it was when queued.
    SELECT * INTO node FROM public.wbs_nodes WHERE id = NEW.id;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;
    IF node.parent_id IS NULL THEN
        IF node.depth <> 0 THEN
            RAISE EXCEPTION 'wbs_nodes hierarchy cache: top-level node % must have depth 0, has %',
                node.id, node.depth USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    ELSE
        SELECT depth INTO parent_depth FROM public.wbs_nodes WHERE id = node.parent_id;
        IF parent_depth IS NULL OR node.depth <> parent_depth + 1 THEN
            RAISE EXCEPTION 'wbs_nodes hierarchy cache: node % depth % is not parent depth % + 1',
                node.id, node.depth, parent_depth USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.wbs_nodes child WHERE child.parent_id = node.id AND child.depth <> node.depth + 1
    ) THEN
        RAISE EXCEPTION 'wbs_nodes hierarchy cache: children of % are not at depth %',
            node.id, node.depth + 1 USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NULL;
END
$fn$
"""

UPGRADE_STATEMENTS: tuple[str, ...] = (
    PREFLIGHT_SQL,
    "ALTER TABLE public.wbs_nodes ADD COLUMN sort_order integer",
    BACKFILL_SORT_ORDER_SQL,
    "ALTER TABLE public.wbs_nodes ALTER COLUMN sort_order SET NOT NULL",
    "ALTER TABLE public.wbs_nodes ADD CONSTRAINT uq_wbs_nodes_sibling_order "
    "UNIQUE NULLS NOT DISTINCT (project_id, parent_id, sort_order) DEFERRABLE INITIALLY DEFERRED",
    "ALTER TABLE public.wbs_nodes ADD CONSTRAINT uq_wbs_nodes_tenant_project_id UNIQUE (tenant_id, project_id, id)",
    "ALTER TABLE public.wbs_nodes DROP CONSTRAINT IF EXISTS wbs_nodes_parent_id_fkey",
    "ALTER TABLE public.wbs_nodes ADD CONSTRAINT fk_wbs_nodes_parent_same_project "
    "FOREIGN KEY (tenant_id, project_id, parent_id) REFERENCES public.wbs_nodes (tenant_id, project_id, id) "
    "ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED",
    "ALTER TABLE public.wbs_nodes DROP CONSTRAINT IF EXISTS uq_wbs_nodes_project_code",
    "ALTER TABLE public.wbs_nodes ADD CONSTRAINT uq_wbs_nodes_project_code "
    "UNIQUE (project_id, code) DEFERRABLE INITIALLY DEFERRED",
    "ALTER TABLE public.wbs_nodes DROP CONSTRAINT IF EXISTS wbs_nodes_source_document_id_fkey",
    "ALTER TABLE public.wbs_nodes ADD CONSTRAINT wbs_nodes_source_document_id_fkey "
    "FOREIGN KEY (source_document_id) REFERENCES public.documents (id) ON DELETE SET NULL",
    "ALTER TABLE public.stakeholder_wbs_raci DROP CONSTRAINT IF EXISTS stakeholder_wbs_raci_wbs_item_id_fkey",
    "ALTER TABLE public.stakeholder_wbs_raci ADD CONSTRAINT stakeholder_wbs_raci_wbs_item_id_fkey "
    "FOREIGN KEY (wbs_item_id) REFERENCES public.wbs_nodes (id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED "
    "NOT VALID",
    """
DO $$
BEGIN
    ALTER TABLE public.stakeholder_wbs_raci VALIDATE CONSTRAINT stakeholder_wbs_raci_wbs_item_id_fkey;
EXCEPTION WHEN foreign_key_violation THEN
    RAISE WARNING 'stakeholder_wbs_raci_wbs_item_id_fkey is enforced for new writes but left NOT VALID '
        'until the rows pointing at non-canonical WBS ids are reviewed';
END $$
""",
    "ALTER TABLE public.procurement_bom_items DROP CONSTRAINT IF EXISTS procurement_bom_items_wbs_item_id_fkey",
    "ALTER TABLE public.procurement_bom_items ADD CONSTRAINT procurement_bom_items_wbs_item_id_fkey "
    "FOREIGN KEY (wbs_item_id) REFERENCES public.wbs_nodes (id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED "
    "NOT VALID",
    """
DO $$
BEGIN
    ALTER TABLE public.procurement_bom_items VALIDATE CONSTRAINT procurement_bom_items_wbs_item_id_fkey;
EXCEPTION WHEN foreign_key_violation THEN
    RAISE WARNING 'procurement_bom_items_wbs_item_id_fkey is enforced for new writes but left NOT VALID '
        'until the rows pointing at non-canonical WBS ids are reviewed';
END $$
""",
    HIERARCHY_CACHE_FUNCTION_SQL,
    "REVOKE ALL ON FUNCTION public.wbs_nodes_verify_hierarchy_cache() FROM PUBLIC",
    "DROP TRIGGER IF EXISTS trg_wbs_nodes_hierarchy_cache ON public.wbs_nodes",
    "CREATE CONSTRAINT TRIGGER trg_wbs_nodes_hierarchy_cache "
    "AFTER INSERT OR UPDATE OF parent_id, depth, project_id, tenant_id ON public.wbs_nodes "
    "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.wbs_nodes_verify_hierarchy_cache()",
)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    "DROP TRIGGER IF EXISTS trg_wbs_nodes_hierarchy_cache ON public.wbs_nodes",
    "DROP FUNCTION IF EXISTS public.wbs_nodes_verify_hierarchy_cache()",
    "ALTER TABLE public.procurement_bom_items DROP CONSTRAINT IF EXISTS procurement_bom_items_wbs_item_id_fkey",
    # Previous definitions, re-added the ADR-025 way: NOT VALID, then validated only if every row
    # qualifies (rows pointing at non-canonical ids keep the FK NOT VALID, as they did before).
    "ALTER TABLE public.procurement_bom_items ADD CONSTRAINT procurement_bom_items_wbs_item_id_fkey "
    "FOREIGN KEY (wbs_item_id) REFERENCES public.wbs_nodes (id) ON DELETE SET NULL NOT VALID",
    """
DO $$
BEGIN
    ALTER TABLE public.procurement_bom_items VALIDATE CONSTRAINT procurement_bom_items_wbs_item_id_fkey;
EXCEPTION WHEN foreign_key_violation THEN
    RAISE WARNING 'procurement_bom_items_wbs_item_id_fkey left NOT VALID (pre-existing non-canonical references)';
END $$
""",
    "ALTER TABLE public.stakeholder_wbs_raci DROP CONSTRAINT IF EXISTS stakeholder_wbs_raci_wbs_item_id_fkey",
    "ALTER TABLE public.stakeholder_wbs_raci ADD CONSTRAINT stakeholder_wbs_raci_wbs_item_id_fkey "
    "FOREIGN KEY (wbs_item_id) REFERENCES public.wbs_nodes (id) ON DELETE CASCADE NOT VALID",
    """
DO $$
BEGIN
    ALTER TABLE public.stakeholder_wbs_raci VALIDATE CONSTRAINT stakeholder_wbs_raci_wbs_item_id_fkey;
EXCEPTION WHEN foreign_key_violation THEN
    RAISE WARNING 'stakeholder_wbs_raci_wbs_item_id_fkey left NOT VALID (pre-existing non-canonical references)';
END $$
""",
    "ALTER TABLE public.wbs_nodes DROP CONSTRAINT IF EXISTS wbs_nodes_source_document_id_fkey",
    "ALTER TABLE public.wbs_nodes ADD CONSTRAINT wbs_nodes_source_document_id_fkey "
    "FOREIGN KEY (source_document_id) REFERENCES public.documents (id) ON DELETE CASCADE",
    "ALTER TABLE public.wbs_nodes DROP CONSTRAINT IF EXISTS uq_wbs_nodes_project_code",
    "ALTER TABLE public.wbs_nodes ADD CONSTRAINT uq_wbs_nodes_project_code UNIQUE (project_id, code)",
    "ALTER TABLE public.wbs_nodes DROP CONSTRAINT IF EXISTS fk_wbs_nodes_parent_same_project",
    "ALTER TABLE public.wbs_nodes ADD CONSTRAINT wbs_nodes_parent_id_fkey "
    "FOREIGN KEY (parent_id) REFERENCES public.wbs_nodes (id) ON DELETE SET NULL",
    "ALTER TABLE public.wbs_nodes DROP CONSTRAINT IF EXISTS uq_wbs_nodes_tenant_project_id",
    "ALTER TABLE public.wbs_nodes DROP CONSTRAINT IF EXISTS uq_wbs_nodes_sibling_order",
    "ALTER TABLE public.wbs_nodes DROP COLUMN IF EXISTS sort_order",
)


def supabase_sql() -> str:
    """The Supabase CLI mirror: the same upgrade statements, in order."""
    header = (
        "-- PC-1R (#886, ADR-029): canonical WBS structural integrity, project as implicit root.\n"
        "-- Mirror of apps/api/alembic/versions/20261005_0003_pc1r_wbs_structural_integrity.py "
        "(rendered from UPGRADE_STATEMENTS; do not edit by hand).\n"
    )
    return header + "\n" + "\n\n".join(statement.strip() + ";" for statement in UPGRADE_STATEMENTS) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
