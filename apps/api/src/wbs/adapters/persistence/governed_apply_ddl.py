"""Governed-apply trigger functions and triggers (PC-2a.2 #896).

A literal copy of the DDL in alembic revision ``20261006_0002``: the test schema is built
with ``Base.metadata.create_all`` and must carry the same database-enforced invariants.
tests/unit/product_control/test_pc2a2_wbs_governed_apply_migration.py keeps the two equal.
Edit the migration first (or add a new one), then mirror it here.
"""

from __future__ import annotations

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
        -- Serialize with a governed apply, which holds the project row FOR UPDATE until its baseline
        -- commits: a racing write waits here (KEY SHARE, as the wbs_nodes FK check already takes)
        -- and then reads that baseline. A project being deleted takes its WBS with it (cascade).
        PERFORM 1 FROM public.projects p WHERE p.id = v_project FOR KEY SHARE;
        CONTINUE WHEN NOT FOUND;
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

RETIREMENTS_TRIGGER_SQL = (
    'CREATE TRIGGER trg_wbs_change_set_retirements_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_'
    'change_set_retirements FOR EACH ROW EXECUTE FUNCTION public.wbs_change_set_retirements_guard()'
)
LIVE_WRITE_TRIGGER_SQL = (
    'CREATE TRIGGER trg_wbs_nodes_governed_write_guard BEFORE INSERT OR DELETE OR UPDATE OF id, tenant_id'
    ', project_id, parent_id, sort_order, code, name, control_level, decomposition_kind, dictionary ON pu'
    'blic.wbs_nodes FOR EACH ROW EXECUTE FUNCTION public.wbs_nodes_governed_write_guard()'
)
TRIGGER_STATEMENTS: tuple[str, ...] = (RETIREMENTS_TRIGGER_SQL, LIVE_WRITE_TRIGGER_SQL)
