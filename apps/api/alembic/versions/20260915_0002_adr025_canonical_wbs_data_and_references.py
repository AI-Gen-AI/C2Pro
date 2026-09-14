"""ADR-025 (2/2): one canonical WBS per project; RACI, BOM and MCP views reference it.

Revision ID: 20260915_0002
Revises: 20260915_0001
Create Date: 2026-09-15

ADR-025 / MASTER ``project_controls.invariant=one_project_one_canonical_hierarchical_wbs``: the
canonical Project Controls WBS is ``wbs_nodes``. Before this revision the database carried three
WBS representations: ``wbs_nodes`` (no application writer), ``procurement_wbs_items`` (what the
application wrote) and the legacy ``wbs_items`` (what the Alembic RACI FK and MCP views read).

DATA MAPPING (no silent row loss)
---------------------------------
Every legacy row is classified, and the classification is recorded on the legacy row itself
(``canonical_mapping`` / ``canonical_mapping_reason`` / ``canonical_wbs_node_id``, added by
20260915_0001). Ids are preserved, so existing RACI and BOM references stay meaningful.

- A project that already owns canonical nodes keeps them untouched (two hierarchies are never
  merged): a legacy row with the same id is ``DIRECT_MAP`` (already canonical); any other row is
  ``AMBIGUOUS`` (``project_already_has_canonical_wbs``) and is NOT copied.
- Otherwise the project's ``procurement_wbs_items`` rows are copied into ``wbs_items``-free
  canonical nodes: ``DIRECT_MAP`` when the row's type and level agree with the hierarchy,
  ``DERIVED_MAP`` when the node type had to be inferred or the level recomputed (recorded under
  the reserved ``_adr025`` metadata key the repository understands).
- ``wbs_items`` rows are copied only for projects that have neither canonical nor procurement
  WBS rows. In a project that has procurement rows, a ``wbs_items`` row with the same id and code
  is ``DIRECT_MAP`` to that node; anything else is ``AMBIGUOUS`` (``project_has_procurement_wbs``).
- A copied row whose parent is missing or was not copied becomes a root: ``ORPHAN``.
- A parent cycle is broken deterministically at its lowest code: that row becomes a root,
  ``AMBIGUOUS`` (``parent_cycle_broken_here``); its cycle successors keep their hierarchy.
- Rows that cannot be stored safely (duplicate id/code, missing tenant, out-of-range budget) are
  ``AMBIGUOUS`` with the reason and are NOT copied.
The nested set is computed per project with children ordered by code (byte order), the same
order the repository uses. The mapping raises if any legacy row is left unclassified or any
copied row is missing.

REFERENCES
----------
``stakeholder_wbs_raci.wbs_item_id`` (ON DELETE CASCADE) and ``procurement_bom_items.wbs_item_id``
(ON DELETE SET NULL) are re-pointed to ``wbs_nodes``: added ``NOT VALID`` (enforced for every new
write immediately), then validated inside an exception block. Rows pointing at ids that are not
canonical (e.g. an ``AMBIGUOUS`` legacy row) are never deleted or re-pointed; the constraint stays
``NOT VALID`` with a WARNING until a human reviews them. The MCP views ``v_raci_matrix`` and
``v_project_wbs`` are recreated over ``wbs_nodes`` with their column names, owner, grants and
``security_invoker`` preserved (they only exist on Alembic-managed databases).

LEGACY STORES
-------------
``procurement_wbs_items`` and ``wbs_items`` keep all historical rows but lose runtime authority: a
row trigger rejects direct INSERT/UPDATE/DELETE (message starts with ``ADR-025``); referential
actions such as deleting a project still cascade.

RLS
---
Row security is left exactly as found. Tables under ``FORCE ROW LEVEL SECURITY`` would hide rows
from an owner without BYPASSRLS, so the mapping lifts FORCE and restores it inside the same DO
block (atomic: an error restores it with the rollback).

DOWNGRADE
---------
Application-managed canonical nodes (those carrying the ``_adr025`` key) are written back to
``procurement_wbs_items`` (rows edited after the upgrade are updated, rows created are inserted,
rows deleted are removed from the legacy stores), references and views return to their previous
targets, and a managed node is removed from ``wbs_nodes`` only once a legacy store holds it.
Pre-existing canonical nodes are never touched.

Supabase CLI mirror: supabase/migrations/20260915000200_adr025_canonical_wbs_data_and_references.sql,
rendered from ``UPGRADE_STATEMENTS`` by ``supabase_sql()`` (parity is tested).
"""

from __future__ import annotations

from alembic import op

revision = "20260915_0002"
down_revision = "20260915_0001"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20260915000200_adr025_canonical_wbs_data_and_references.sql"
LEGACY_WBS_TABLES = ("procurement_wbs_items", "wbs_items")

_TENANT_SCOPE = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"

# Tables whose FORCE ROW LEVEL SECURITY is lifted (and restored) while legacy rows are mapped.
_RLS_TABLES = "ARRAY['public.wbs_nodes', 'public.procurement_wbs_items', 'public.wbs_items', 'public.projects', 'public.tenants']"

_LIFT_FORCED_RLS = f"""
    SELECT COALESCE(array_agg(c.oid::regclass), ARRAY[]::regclass[]) INTO forced
    FROM pg_class c
    WHERE c.relforcerowsecurity
      AND c.oid IN (SELECT to_regclass(name) FROM unnest({_RLS_TABLES}) AS name);
    FOREACH rel IN ARRAY forced LOOP
        EXECUTE format('ALTER TABLE %s NO FORCE ROW LEVEL SECURITY', rel);
    END LOOP;
"""

_RESTORE_FORCED_RLS = """
    FOREACH rel IN ARRAY forced LOOP
        EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', rel);
    END LOOP;
"""

MAP_LEGACY_WBS_SQL = f"""
DO $$
DECLARE
    forced regclass[];
    rel regclass;
    has_wbs_items boolean := to_regclass('public.wbs_items') IS NOT NULL;
    cycle_row uuid;
    summary record;
BEGIN
{_LIFT_FORCED_RLS}

    CREATE TEMP TABLE adr025_wbs_candidates (
        source_table text NOT NULL,
        id uuid NOT NULL,
        project_id uuid NOT NULL,
        tenant_id uuid,
        code varchar NOT NULL,
        name varchar NOT NULL,
        description text,
        legacy_level integer,
        item_type text,
        parent_code varchar,
        legacy_parent_id uuid,
        budget_allocated numeric,
        budget_spent numeric,
        planned_start timestamptz,
        planned_end timestamptz,
        actual_start timestamptz,
        actual_end timestamptz,
        source_clause_id uuid,
        source_document_id uuid,
        version integer,
        metadata jsonb,
        created_at timestamp,
        updated_at timestamp,
        migrate boolean NOT NULL DEFAULT false,
        parent_id uuid,
        depth integer,
        lft integer,
        rgt integer,
        canonical_id uuid,
        classification text,
        reason text
    );
    CREATE TEMP TABLE adr025_unreached (id uuid, parent_id uuid, project_id uuid, code varchar);

    INSERT INTO adr025_wbs_candidates (
        source_table, id, project_id, tenant_id, code, name, description, legacy_level, item_type,
        parent_code, budget_allocated, budget_spent, planned_start, planned_end, actual_start,
        actual_end, source_clause_id, source_document_id, version, metadata
    )
    SELECT 'procurement_wbs_items', w.id, w.project_id, p.tenant_id, w.code, w.name, w.description,
        w.level, w.item_type::text, w.parent_code, w.budget_allocated, w.budget_spent, w.planned_start,
        w.planned_end, w.actual_start, w.actual_end, w.source_clause_id, w.source_document_id,
        w.version, w.wbs_metadata
    FROM public.procurement_wbs_items w
    LEFT JOIN public.projects p ON p.id = w.project_id;

    IF has_wbs_items THEN
        INSERT INTO adr025_wbs_candidates (
            source_table, id, project_id, tenant_id, code, name, description, legacy_level, item_type,
            legacy_parent_id, budget_allocated, budget_spent, planned_start, planned_end, actual_start,
            actual_end, source_clause_id, version, metadata, created_at, updated_at
        )
        SELECT 'wbs_items', w.id, w.project_id, p.tenant_id, w.code, w.name, w.description, w.level,
            w.item_type::text, w.parent_id, w.budget_allocated, w.budget_spent, w.planned_start,
            w.planned_end, w.actual_start, w.actual_end, w.source_clause_id, w.version, w.wbs_metadata,
            w.created_at, w.updated_at
        FROM public.wbs_items w
        LEFT JOIN public.projects p ON p.id = w.project_id;
    END IF;

    -- 1. A project that already owns a canonical WBS keeps it; hierarchies are never merged.
    UPDATE adr025_wbs_candidates c
    SET classification = CASE WHEN EXISTS (
            SELECT 1 FROM public.wbs_nodes n WHERE n.id = c.id AND n.project_id = c.project_id
        ) THEN 'DIRECT_MAP' ELSE 'AMBIGUOUS' END,
        reason = CASE WHEN EXISTS (
            SELECT 1 FROM public.wbs_nodes n WHERE n.id = c.id AND n.project_id = c.project_id
        ) THEN 'already_in_canonical_wbs' ELSE 'project_already_has_canonical_wbs' END
    WHERE EXISTS (SELECT 1 FROM public.wbs_nodes n WHERE n.project_id = c.project_id);
    UPDATE adr025_wbs_candidates SET canonical_id = id WHERE reason = 'already_in_canonical_wbs';

    -- 2. The procurement WBS is what the application wrote; legacy wbs_items never compete with it.
    UPDATE adr025_wbs_candidates c
    SET classification = CASE WHEN EXISTS (
            SELECT 1 FROM adr025_wbs_candidates pw
            WHERE pw.source_table = 'procurement_wbs_items' AND pw.id = c.id
              AND pw.project_id = c.project_id AND pw.code = c.code
        ) THEN 'DIRECT_MAP' ELSE 'AMBIGUOUS' END,
        reason = CASE WHEN EXISTS (
            SELECT 1 FROM adr025_wbs_candidates pw
            WHERE pw.source_table = 'procurement_wbs_items' AND pw.id = c.id
              AND pw.project_id = c.project_id AND pw.code = c.code
        ) THEN 'same_node_as_procurement_wbs_item' ELSE 'project_has_procurement_wbs' END
    WHERE c.source_table = 'wbs_items'
      AND c.classification IS NULL
      AND EXISTS (
          SELECT 1 FROM adr025_wbs_candidates pw
          WHERE pw.source_table = 'procurement_wbs_items' AND pw.project_id = c.project_id
      );

    -- 3. Rows that cannot be stored safely are reported, not copied.
    UPDATE adr025_wbs_candidates c SET classification = 'AMBIGUOUS', reason = 'project_tenant_missing'
    WHERE c.classification IS NULL
      AND (c.tenant_id IS NULL OR NOT EXISTS (SELECT 1 FROM public.tenants t WHERE t.id = c.tenant_id));
    UPDATE adr025_wbs_candidates c SET classification = 'AMBIGUOUS', reason = 'id_used_by_another_canonical_node'
    WHERE c.classification IS NULL AND EXISTS (SELECT 1 FROM public.wbs_nodes n WHERE n.id = c.id);
    UPDATE adr025_wbs_candidates c SET classification = 'AMBIGUOUS', reason = 'duplicate_id'
    WHERE c.classification IS NULL
      AND c.id IN (
          SELECT id FROM adr025_wbs_candidates WHERE classification IS NULL GROUP BY id HAVING count(*) > 1
      );
    UPDATE adr025_wbs_candidates c SET classification = 'AMBIGUOUS', reason = 'duplicate_code_in_project'
    WHERE c.classification IS NULL
      AND (c.project_id, c.code) IN (
          SELECT project_id, code FROM adr025_wbs_candidates
          WHERE classification IS NULL GROUP BY project_id, code HAVING count(*) > 1
      );
    UPDATE adr025_wbs_candidates c SET classification = 'AMBIGUOUS', reason = 'budget_out_of_range'
    WHERE c.classification IS NULL
      AND (COALESCE(c.budget_spent, 0) < 0
           OR abs(COALESCE(c.budget_spent, 0)) >= 10000000000000000
           OR abs(COALESCE(c.budget_allocated, 0)) >= 10000000000000000);

    UPDATE adr025_wbs_candidates SET migrate = true WHERE classification IS NULL;

    -- 4. Hierarchy within the copied set.
    UPDATE adr025_wbs_candidates c SET parent_id = parent.id
    FROM adr025_wbs_candidates parent
    WHERE c.migrate AND parent.migrate
      AND parent.project_id = c.project_id
      AND parent.source_table = c.source_table
      AND parent.id <> c.id
      AND ((c.source_table = 'procurement_wbs_items' AND parent.code = c.parent_code)
        OR (c.source_table = 'wbs_items' AND parent.id = c.legacy_parent_id));
    UPDATE adr025_wbs_candidates c SET classification = 'ORPHAN', reason = 'parent_missing_or_not_migrated'
    WHERE c.migrate AND c.parent_id IS NULL AND (c.parent_code IS NOT NULL OR c.legacy_parent_id IS NOT NULL);

    -- 5. Break parent cycles deterministically (lowest code of each cycle becomes a root).
    LOOP
        DELETE FROM adr025_unreached;
        INSERT INTO adr025_unreached (id, parent_id, project_id, code)
        WITH RECURSIVE reachable AS (
            SELECT c.id FROM adr025_wbs_candidates c WHERE c.migrate AND c.parent_id IS NULL
            UNION
            SELECT c.id FROM adr025_wbs_candidates c JOIN reachable r ON c.parent_id = r.id WHERE c.migrate
        )
        SELECT c.id, c.parent_id, c.project_id, c.code
        FROM adr025_wbs_candidates c
        WHERE c.migrate AND NOT EXISTS (SELECT 1 FROM reachable r WHERE r.id = c.id);
        EXIT WHEN NOT EXISTS (SELECT 1 FROM adr025_unreached);

        LOOP  -- prune rows heading no unreached subtree; what remains lies on a parent cycle
            DELETE FROM adr025_unreached u
            WHERE NOT EXISTS (SELECT 1 FROM adr025_unreached child WHERE child.parent_id = u.id);
            EXIT WHEN NOT FOUND;
        END LOOP;

        SELECT u.id INTO cycle_row
        FROM adr025_unreached u
        ORDER BY u.project_id, convert_to(u.code, 'UTF8')
        LIMIT 1;
        IF cycle_row IS NULL THEN
            RAISE EXCEPTION 'ADR-025: unreachable WBS rows without a parent cycle';
        END IF;
        UPDATE adr025_wbs_candidates
        SET parent_id = NULL, classification = 'AMBIGUOUS', reason = 'parent_cycle_broken_here'
        WHERE id = cycle_row AND migrate;
        cycle_row := NULL;
    END LOOP;

    -- 6. Nested set per project: pre-order by code path (byte order), lft = 2*pos - 1 - depth.
    WITH RECURSIVE tree AS (
        SELECT c.id, c.project_id, 0 AS depth, ARRAY[convert_to(c.code, 'UTF8')] AS path, ARRAY[c.id] AS ids
        FROM adr025_wbs_candidates c
        WHERE c.migrate AND c.parent_id IS NULL
        UNION ALL
        SELECT c.id, c.project_id, t.depth + 1, t.path || convert_to(c.code, 'UTF8'), t.ids || c.id
        FROM adr025_wbs_candidates c
        JOIN tree t ON c.parent_id = t.id
        WHERE c.migrate
    ),
    ordered AS (
        SELECT t.id, t.depth, row_number() OVER (PARTITION BY t.project_id ORDER BY t.path) AS pos
        FROM tree t
    ),
    sized AS (
        SELECT o.id, o.depth, (2 * o.pos - 1 - o.depth)::integer AS lft,
               ((SELECT count(*) FROM tree d WHERE o.id = ANY (d.ids)) - 1)::integer AS descendants
        FROM ordered o
    )
    UPDATE adr025_wbs_candidates c
    SET depth = s.depth, lft = s.lft, rgt = s.lft + 2 * s.descendants + 1
    FROM sized s
    WHERE s.id = c.id AND c.migrate;

    UPDATE adr025_wbs_candidates
    SET classification = CASE WHEN item_type IS NOT NULL AND legacy_level = depth + 1 THEN 'DIRECT_MAP' ELSE 'DERIVED_MAP' END,
        reason = CASE WHEN item_type IS NOT NULL AND legacy_level = depth + 1 THEN NULL ELSE concat_ws(
            ',',
            CASE WHEN item_type IS NULL THEN 'node_type_inferred' END,
            CASE WHEN legacy_level IS DISTINCT FROM depth + 1 THEN 'level_recomputed_from_hierarchy' END
        ) END
    WHERE migrate AND classification IS NULL;
    UPDATE adr025_wbs_candidates SET canonical_id = id WHERE migrate;

    -- 7. Copy into the canonical WBS (ids preserved).
    INSERT INTO public.wbs_nodes (
        id, project_id, tenant_id, parent_id, code, name, description, lft, rgt, depth, node_type, status,
        planned_start, planned_end, actual_start, actual_end, budget_allocated, budget_spent,
        source_clause_id, source_document_id, version, metadata, created_at, updated_at
    )
    SELECT
        c.id, c.project_id, c.tenant_id, c.parent_id, c.code, c.name, c.description, c.lft, c.rgt, c.depth,
        COALESCE(c.item_type, 'work_package')::wbsnodetype,
        CASE WHEN c.metadata ->> 'status' IN ('not_started', 'in_progress', 'completed', 'on_hold', 'cancelled')
             THEN (c.metadata ->> 'status')::wbsnodestatus ELSE 'not_started'::wbsnodestatus END,
        c.planned_start, c.planned_end, c.actual_start, c.actual_end, c.budget_allocated,
        COALESCE(c.budget_spent, 0), c.source_clause_id, c.source_document_id, COALESCE(c.version, 1),
        CASE WHEN jsonb_typeof(c.metadata) = 'object' THEN c.metadata
             ELSE jsonb_build_object('legacy_metadata', COALESCE(c.metadata, 'null'::jsonb)) END
        || jsonb_build_object('_adr025', jsonb_build_object(
            'migrated_from', c.source_table,
            'mapping', c.classification,
            'mapping_reason', c.reason,
            'legacy_level', c.legacy_level,
            'node_type_inferred', c.item_type IS NULL
        )),
        COALESCE(c.created_at, (now() AT TIME ZONE 'utc')),
        COALESCE(c.updated_at, (now() AT TIME ZONE 'utc'))
    FROM adr025_wbs_candidates c
    WHERE c.migrate;

    -- A wbs_items twin of a procurement row is canonical only if that procurement row became canonical.
    UPDATE adr025_wbs_candidates c SET canonical_id = c.id
    WHERE c.reason = 'same_node_as_procurement_wbs_item'
      AND EXISTS (SELECT 1 FROM public.wbs_nodes n WHERE n.id = c.id AND n.project_id = c.project_id);
    UPDATE adr025_wbs_candidates c SET classification = 'AMBIGUOUS', reason = 'procurement_twin_not_canonical'
    WHERE c.reason = 'same_node_as_procurement_wbs_item' AND c.canonical_id IS NULL;

    -- 8. Lineage on every legacy row.
    UPDATE public.procurement_wbs_items w
    SET canonical_wbs_node_id = c.canonical_id,
        canonical_mapping = c.classification,
        canonical_mapping_reason = c.reason
    FROM adr025_wbs_candidates c
    WHERE c.source_table = 'procurement_wbs_items' AND c.id = w.id AND c.project_id = w.project_id;
    IF has_wbs_items THEN
        UPDATE public.wbs_items w
        SET canonical_wbs_node_id = c.canonical_id,
            canonical_mapping = c.classification,
            canonical_mapping_reason = c.reason
        FROM adr025_wbs_candidates c
        WHERE c.source_table = 'wbs_items' AND c.id = w.id AND c.project_id = w.project_id;
    END IF;

    -- 9. No silent row loss.
    IF EXISTS (SELECT 1 FROM public.procurement_wbs_items WHERE canonical_mapping IS NULL) THEN
        RAISE EXCEPTION 'ADR-025: procurement_wbs_items rows were left unclassified';
    END IF;
    IF has_wbs_items THEN
        IF EXISTS (SELECT 1 FROM public.wbs_items WHERE canonical_mapping IS NULL) THEN
            RAISE EXCEPTION 'ADR-025: wbs_items rows were left unclassified';
        END IF;
    END IF;
    IF EXISTS (
        SELECT 1 FROM adr025_wbs_candidates c
        WHERE c.migrate AND NOT EXISTS (SELECT 1 FROM public.wbs_nodes n WHERE n.id = c.id)
    ) THEN
        RAISE EXCEPTION 'ADR-025: a legacy WBS row selected for the canonical WBS was not copied';
    END IF;

    FOR summary IN
        SELECT source_table, classification, count(*) AS row_count
        FROM adr025_wbs_candidates GROUP BY source_table, classification ORDER BY 1, 2
    LOOP
        RAISE NOTICE 'ADR-025 WBS mapping: % % = %', summary.source_table, summary.classification, summary.row_count;
    END LOOP;

    DROP TABLE adr025_unreached;
    DROP TABLE adr025_wbs_candidates;
{_RESTORE_FORCED_RLS}
END
$$
"""


def _repoint_fk_sql(*, table: str, constraint: str, target: str, on_delete: str) -> str:
    return f"""
DO $$
DECLARE
    fk record;
BEGIN
    IF to_regclass('public.{table}') IS NULL OR to_regclass('public.{target}') IS NULL THEN
        RETURN;
    END IF;
    FOR fk IN
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
        WHERE c.conrelid = 'public.{table}'::regclass
          AND c.contype = 'f'
          AND a.attname = 'wbs_item_id'
    LOOP
        EXECUTE format('ALTER TABLE public.{table} DROP CONSTRAINT %I', fk.conname);
    END LOOP;

    ALTER TABLE public.{table}
        ADD CONSTRAINT {constraint}
        FOREIGN KEY (wbs_item_id) REFERENCES public.{target} (id) ON DELETE {on_delete} NOT VALID;

    BEGIN
        ALTER TABLE public.{table} VALIDATE CONSTRAINT {constraint};
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE WARNING 'ADR-025: existing {table} rows reference WBS ids absent from {target}; '
            '{constraint} is enforced for new writes but left NOT VALID until those rows are reviewed '
            '(see canonical_mapping on the legacy WBS tables; no row was deleted or re-pointed).';
    END;
END
$$
"""


RACI_FK_SQL = _repoint_fk_sql(
    table="stakeholder_wbs_raci",
    constraint="stakeholder_wbs_raci_wbs_item_id_fkey",
    target="wbs_nodes",
    on_delete="CASCADE",
)
BOM_FK_SQL = _repoint_fk_sql(
    table="procurement_bom_items",
    constraint="procurement_bom_items_wbs_item_id_fkey",
    target="wbs_nodes",
    on_delete="SET NULL",
)
LEGACY_RACI_FK_SQL = _repoint_fk_sql(
    table="stakeholder_wbs_raci",
    constraint="stakeholder_wbs_raci_wbs_item_id_fkey",
    target="wbs_items",
    on_delete="CASCADE",
)
LEGACY_BOM_FK_SQL = _repoint_fk_sql(
    table="procurement_bom_items",
    constraint="fk_bom_wbs",
    target="procurement_wbs_items",
    on_delete="SET NULL",
)

# __VIEW__ is the view name, __DEFINITION__ its CREATE VIEW statement. A view that does not exist
# (Supabase CLI schema) is not created.
RECREATE_VIEW_SQL = """
DO $$
DECLARE
    old_acl aclitem[];
    new_acl aclitem[];
    owner_oid oid;
    rec record;
BEGIN
    SELECT relacl, relowner INTO old_acl, owner_oid FROM pg_class WHERE oid = to_regclass('public.__VIEW__');
    IF owner_oid IS NULL THEN
        RETURN;
    END IF;
    old_acl := COALESCE(old_acl, acldefault('r', owner_oid));

    DROP VIEW public.__VIEW__;
    __DEFINITION__;
    ALTER VIEW public.__VIEW__ SET (security_invoker = true);

    IF owner_oid <> (SELECT oid FROM pg_roles WHERE rolname = current_user) THEN
        BEGIN
            EXECUTE format('ALTER VIEW public.__VIEW__ OWNER TO %I', pg_get_userbyid(owner_oid));
        EXCEPTION WHEN insufficient_privilege THEN
            RAISE WARNING 'ADR-025: could not restore the owner of public.__VIEW__ to %', pg_get_userbyid(owner_oid);
        END;
    END IF;

    SELECT COALESCE(relacl, acldefault('r', relowner)) INTO new_acl
    FROM pg_class WHERE oid = 'public.__VIEW__'::regclass;

    -- Revoke anything the new view received (e.g. via default ACLs) that the old view did not have.
    FOR rec IN
        SELECT n.grantee, n.privilege_type
        FROM aclexplode(new_acl) n
        WHERE NOT EXISTS (
            SELECT 1 FROM aclexplode(old_acl) o
            WHERE o.grantee = n.grantee AND o.privilege_type = n.privilege_type
        )
    LOOP
        EXECUTE format(
            'REVOKE %s ON public.__VIEW__ FROM %s',
            rec.privilege_type,
            CASE WHEN rec.grantee = 0 THEN 'PUBLIC' ELSE quote_ident(pg_get_userbyid(rec.grantee)) END
        );
    END LOOP;

    -- Re-apply every grant the old view had.
    FOR rec IN SELECT grantee, privilege_type, is_grantable FROM aclexplode(old_acl) LOOP
        EXECUTE format(
            'GRANT %s ON public.__VIEW__ TO %s%s',
            rec.privilege_type,
            CASE WHEN rec.grantee = 0 THEN 'PUBLIC' ELSE quote_ident(pg_get_userbyid(rec.grantee)) END,
            CASE WHEN rec.is_grantable THEN ' WITH GRANT OPTION' ELSE '' END
        );
    END LOOP;
END
$$
"""

V_RACI_MATRIX_SQL = f"""
CREATE VIEW public.v_raci_matrix AS
SELECT
    r.id,
    r.project_id,
    p.tenant_id,
    r.stakeholder_id,
    s.name AS stakeholder_name,
    r.wbs_item_id,
    w.code AS wbs_code,
    w.name AS wbs_title,
    r.raci_role,
    r.evidence_text,
    r.generated_automatically,
    r.manually_verified,
    r.created_at
FROM public.stakeholder_wbs_raci r
JOIN public.projects p ON p.id = r.project_id
JOIN public.stakeholders s ON s.id = r.stakeholder_id
LEFT JOIN public.wbs_nodes w ON w.id = r.wbs_item_id
WHERE r.project_id IN (
    SELECT id FROM public.projects WHERE tenant_id = {_TENANT_SCOPE}
)
"""

V_PROJECT_WBS_SQL = f"""
CREATE VIEW public.v_project_wbs AS
SELECT
    w.id,
    w.project_id,
    p.tenant_id,
    w.parent_id,
    w.code AS wbs_code,
    w.name AS title,
    w.description,
    w.depth + 1 AS level,
    CASE WHEN (w.metadata -> '_adr025' ->> 'node_type_inferred') = 'true' THEN NULL
         ELSE w.node_type::text END AS item_type,
    w.planned_start AS start_date,
    w.planned_end AS end_date,
    w.source_clause_id,
    w.created_at,
    w.updated_at
FROM public.wbs_nodes w
JOIN public.projects p ON p.id = w.project_id
WHERE w.project_id IN (
    SELECT id FROM public.projects WHERE tenant_id = {_TENANT_SCOPE}
)
"""

LEGACY_V_RACI_MATRIX_SQL = V_RACI_MATRIX_SQL.replace(
    "LEFT JOIN public.wbs_nodes w", "LEFT JOIN public.wbs_items w"
)

LEGACY_V_PROJECT_WBS_SQL = f"""
CREATE VIEW public.v_project_wbs AS
SELECT
    w.id,
    w.project_id,
    p.tenant_id,
    w.parent_id,
    w.code AS wbs_code,
    w.name AS title,
    w.description,
    w.level,
    w.item_type,
    w.planned_start AS start_date,
    w.planned_end AS end_date,
    w.source_clause_id,
    w.created_at,
    w.updated_at
FROM public.wbs_items w
JOIN public.projects p ON p.id = w.project_id
WHERE w.project_id IN (
    SELECT id FROM public.projects WHERE tenant_id = {_TENANT_SCOPE}
)
"""

WRITE_BLOCK_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.adr025_reject_legacy_wbs_write()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $fn$
BEGIN
    -- Referential actions (e.g. deleting a project cascades to its legacy WBS rows) run nested.
    IF pg_trigger_depth() > 1 THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    RAISE EXCEPTION USING
        ERRCODE = 'restrict_violation',
        MESSAGE = format('ADR-025: %I is a legacy, non-authoritative WBS store and is read-only', TG_TABLE_NAME),
        HINT = 'Write the canonical Project Controls WBS (wbs_nodes) through SQLAlchemyWBSRepository.';
END
$fn$
"""

REVOKE_WRITE_BLOCK_FUNCTION_SQL = """
DO $$
DECLARE
    api_role text;
BEGIN
    REVOKE ALL ON FUNCTION public.adr025_reject_legacy_wbs_write() FROM PUBLIC;
    FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
            EXECUTE format('REVOKE ALL ON FUNCTION public.adr025_reject_legacy_wbs_write() FROM %I', api_role);
        END IF;
    END LOOP;
END
$$
"""

LEGACY_WRITE_BLOCK_TRIGGERS_SQL = """
DO $$
DECLARE
    legacy text;
BEGIN
    FOREACH legacy IN ARRAY ARRAY['procurement_wbs_items', 'wbs_items'] LOOP
        IF to_regclass('public.' || legacy) IS NULL THEN
            CONTINUE;
        END IF;
        EXECUTE format('DROP TRIGGER IF EXISTS trg_adr025_legacy_wbs_read_only ON public.%I', legacy);
        EXECUTE format(
            'CREATE TRIGGER trg_adr025_legacy_wbs_read_only '
            'BEFORE INSERT OR UPDATE OR DELETE ON public.%I '
            'FOR EACH ROW EXECUTE FUNCTION public.adr025_reject_legacy_wbs_write()',
            legacy
        );
    END LOOP;
END
$$
"""

DROP_WRITE_BLOCK_SQL = """
DO $$
DECLARE
    legacy text;
BEGIN
    FOREACH legacy IN ARRAY ARRAY['procurement_wbs_items', 'wbs_items'] LOOP
        IF to_regclass('public.' || legacy) IS NOT NULL THEN
            EXECUTE format('DROP TRIGGER IF EXISTS trg_adr025_legacy_wbs_read_only ON public.%I', legacy);
        END IF;
    END LOOP;
    DROP FUNCTION IF EXISTS public.adr025_reject_legacy_wbs_write();
END
$$
"""

WRITE_BACK_MANAGED_NODES_SQL = f"""
DO $$
DECLARE
    forced regclass[];
    rel regclass;
    has_wbs_items boolean := to_regclass('public.wbs_items') IS NOT NULL;
    affected integer;
BEGIN
{_LIFT_FORCED_RLS}

    -- Application-managed canonical nodes carry the _adr025 key; pre-existing canonical nodes do not.
    CREATE TEMP TABLE adr025_managed_nodes AS
    SELECT
        n.id, n.project_id, n.code, n.name, n.description, n.depth + 1 AS level, parent.code AS parent_code,
        CASE WHEN (n.metadata -> '_adr025' ->> 'node_type_inferred') = 'true'
               OR n.node_type::text NOT IN ('deliverable', 'work_package', 'activity')
             THEN NULL ELSE n.node_type::text END AS item_type,
        n.budget_allocated, n.budget_spent, n.planned_start, n.planned_end, n.actual_start, n.actual_end,
        n.source_clause_id, n.source_document_id, n.version, n.metadata - '_adr025' AS wbs_metadata
    FROM public.wbs_nodes n
    LEFT JOIN public.wbs_nodes parent ON parent.id = n.parent_id
    WHERE n.metadata ? '_adr025'
      AND COALESCE(n.metadata -> '_adr025' ->> 'migrated_from', '') <> 'wbs_items';

    -- Rows the application edited after the upgrade (the repository bumps version on update).
    UPDATE public.procurement_wbs_items w
    SET name = m.name, description = m.description, level = m.level, parent_code = m.parent_code,
        item_type = m.item_type::wbsitemtype, budget_allocated = m.budget_allocated,
        budget_spent = m.budget_spent, planned_start = m.planned_start, planned_end = m.planned_end,
        actual_start = m.actual_start, actual_end = m.actual_end, source_clause_id = m.source_clause_id,
        source_document_id = m.source_document_id, version = m.version, wbs_metadata = m.wbs_metadata
    FROM adr025_managed_nodes m
    WHERE m.id = w.id AND m.project_id = w.project_id AND m.version <> w.version;

    -- Rows the application created after the upgrade.
    INSERT INTO public.procurement_wbs_items (
        id, project_id, code, name, level, description, parent_code, item_type, budget_allocated,
        budget_spent, planned_start, planned_end, actual_start, actual_end, source_clause_id,
        source_document_id, version, wbs_metadata
    )
    SELECT m.id, m.project_id, m.code, m.name, m.level, m.description, m.parent_code, m.item_type::wbsitemtype,
        m.budget_allocated, m.budget_spent, m.planned_start, m.planned_end, m.actual_start, m.actual_end,
        m.source_clause_id, m.source_document_id, m.version, m.wbs_metadata
    FROM adr025_managed_nodes m
    WHERE NOT EXISTS (SELECT 1 FROM public.procurement_wbs_items w WHERE w.id = m.id)
      AND NOT EXISTS (
          SELECT 1 FROM public.procurement_wbs_items w WHERE w.project_id = m.project_id AND w.code = m.code
      );

    SELECT count(*) INTO affected FROM adr025_managed_nodes m
    WHERE NOT EXISTS (SELECT 1 FROM public.procurement_wbs_items w WHERE w.id = m.id);
    IF affected > 0 THEN
        RAISE WARNING 'ADR-025 downgrade: % canonical WBS nodes collide with a procurement_wbs_items code and '
            'stay only in wbs_nodes', affected;
    END IF;

    -- Rows the application deleted after the upgrade (lineage says they had been copied).
    DELETE FROM public.procurement_wbs_items w
    WHERE w.canonical_wbs_node_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM public.wbs_nodes n WHERE n.id = w.canonical_wbs_node_id);
    IF has_wbs_items THEN
        DELETE FROM public.wbs_items w
        WHERE w.canonical_wbs_node_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM public.wbs_nodes n WHERE n.id = w.canonical_wbs_node_id);
    END IF;

    DROP TABLE adr025_managed_nodes;
    -- The procurement parent FK is DEFERRABLE: check it now, since ALTER TABLE refuses pending trigger events.
    SET CONSTRAINTS ALL IMMEDIATE;
{_RESTORE_FORCED_RLS}
END
$$
"""

REMOVE_WRITTEN_BACK_NODES_SQL = f"""
DO $$
DECLARE
    forced regclass[];
    rel regclass;
    has_wbs_items boolean := to_regclass('public.wbs_items') IS NOT NULL;
    remaining integer;
BEGIN
{_LIFT_FORCED_RLS}

    DELETE FROM public.wbs_nodes n
    WHERE n.metadata ? '_adr025'
      AND EXISTS (
          SELECT 1 FROM public.procurement_wbs_items w WHERE w.id = n.id AND w.project_id = n.project_id
      );
    IF has_wbs_items THEN
        DELETE FROM public.wbs_nodes n
        WHERE n.metadata ? '_adr025'
          AND EXISTS (SELECT 1 FROM public.wbs_items w WHERE w.id = n.id AND w.project_id = n.project_id);
    END IF;

    SELECT count(*) INTO remaining FROM public.wbs_nodes n WHERE n.metadata ? '_adr025';
    IF remaining > 0 THEN
        RAISE WARNING 'ADR-025 downgrade: % canonical WBS nodes have no legacy copy and were kept in wbs_nodes', remaining;
    END IF;
{_RESTORE_FORCED_RLS}
END
$$
"""


def _recreate_view(view: str, definition: str) -> str:
    return RECREATE_VIEW_SQL.replace("__VIEW__", view).replace("__DEFINITION__", definition.strip())


# One SQL statement per entry: Alembic runs on asyncpg prepared statements.
UPGRADE_STATEMENTS: tuple[str, ...] = (
    MAP_LEGACY_WBS_SQL,
    RACI_FK_SQL,
    BOM_FK_SQL,
    _recreate_view("v_raci_matrix", V_RACI_MATRIX_SQL),
    _recreate_view("v_project_wbs", V_PROJECT_WBS_SQL),
    WRITE_BLOCK_FUNCTION_SQL,
    REVOKE_WRITE_BLOCK_FUNCTION_SQL,
    LEGACY_WRITE_BLOCK_TRIGGERS_SQL,
)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    DROP_WRITE_BLOCK_SQL,
    _recreate_view("v_project_wbs", LEGACY_V_PROJECT_WBS_SQL),
    _recreate_view("v_raci_matrix", LEGACY_V_RACI_MATRIX_SQL),
    WRITE_BACK_MANAGED_NODES_SQL,
    LEGACY_RACI_FK_SQL,
    LEGACY_BOM_FK_SQL,
    REMOVE_WRITTEN_BACK_NODES_SQL,
)


def supabase_sql() -> str:
    """The Supabase CLI mirror: the same upgrade statements, in order."""
    header = (
        "-- ADR-025 (2/2): one canonical WBS per project; RACI, BOM and MCP views reference it.\n"
        "-- Mirror of apps/api/alembic/versions/20260915_0002_adr025_canonical_wbs_data_and_references.py "
        "(rendered from UPGRADE_STATEMENTS; do not edit by hand).\n"
    )
    return header + "\n" + "\n\n".join(statement.strip() + ";" for statement in UPGRADE_STATEMENTS) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
