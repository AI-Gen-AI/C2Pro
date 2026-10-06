"""WBS governance trigger functions and triggers (PC-2a.1 #895).

A literal copy of the DDL in alembic revision ``20261006_0001``: the test schema is built
with ``Base.metadata.create_all`` and must carry the same database-enforced invariants.
tests/unit/product_control/test_pc2a1_wbs_governance_migration.py keeps the two equal.
Edit the migration first (or add a new one), then mirror it here.
"""

from __future__ import annotations

CORE_TERMS_SQL = (
    "'area', 'system', 'subsystem', 'discipline', 'deliverable', 'component', "
    "'capability', 'phase', 'package', 'other'"
)
# Governed node content checks shared by live, candidate and baseline nodes.
CONTROL_LEVEL_CHECK = "control_level IN ('none', 'control_account', 'work_package', 'planning_package')"
DECOMPOSITION_KIND_CHECK = (
    "decomposition_kind IS NULL OR ("
    "decomposition_kind ~ '^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$' "
    "AND (split_part(decomposition_kind, ':', 1) <> 'core' OR split_part(decomposition_kind, ':', 2) IN ("
    + CORE_TERMS_SQL
    + ")))"
)
DICTIONARY_CHECK = (
    "dictionary IS NULL OR ("
    "jsonb_typeof(dictionary) = 'object' AND coalesce(dictionary ->> 'schema_version', '') = 'wbs-dictionary/v1')"
)
DIGEST_PATTERN_SQL = "'^sha256:[0-9a-f]{64}$'"

REQUIRE_USER_ROLE_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_governance_require_user_role(p_tenant uuid, p_user uuid, p_roles text[], p_action text)
RETURNS void
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_role text;
BEGIN
    SELECT u.role::text INTO v_role FROM public.users u
     WHERE u.id = p_user AND u.tenant_id = p_tenant AND u.is_active;
    IF v_role IS NULL OR NOT (v_role = ANY (p_roles)) THEN
        RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
            MESSAGE = 'WBS governance: ' || p_action || ' requires an active human '
                      || array_to_string(p_roles, ' or ') || ' of the tenant';
    END IF;
END
$fn$"""

REQUIRE_DISTINCT_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_governance_requires_distinct_approver(p_tenant uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
    SELECT COALESCE((SELECT t.settings #>> '{wbs_governance,require_distinct_approver}'
                       FROM public.tenants t WHERE t.id = p_tenant), 'true') <> 'false'
$fn$"""

CHANGE_SET_GUARD_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_change_sets_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_transition text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM public.projects p WHERE p.id = OLD.project_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'WBS change sets are governance history: withdraw instead of deleting';
        END IF;
        RETURN OLD;
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'DRAFT' OR NEW.revision <> 1 THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'a WBS change set starts as DRAFT revision 1';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status IN ('APPLIED', 'REJECTED', 'WITHDRAWN', 'STALE') THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS change set is ' || OLD.status || ' and immutable';
    END IF;
    IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id OR NEW.project_id <> OLD.project_id
       OR NEW.base_baseline_id IS DISTINCT FROM OLD.base_baseline_id OR NEW.origin <> OLD.origin
       OR NEW.entry_mode <> OLD.entry_mode OR NEW.created_by <> OLD.created_by
       OR NEW.created_by_kind <> OLD.created_by_kind OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS change set identity, base and origin are immutable';
    END IF;
    IF NEW.revision < OLD.revision OR NEW.revision > OLD.revision + 1 THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a WBS change set revision only moves forward by one';
    END IF;
    v_transition := OLD.status || '>' || NEW.status;
    IF OLD.status = 'SUBMITTED' AND NEW.status <> 'DRAFT' AND (
           NEW.revision <> OLD.revision OR NEW.submitted_digest IS DISTINCT FROM OLD.submitted_digest
           OR NEW.submitted_revision IS DISTINCT FROM OLD.submitted_revision
           OR NEW.submitted_by IS DISTINCT FROM OLD.submitted_by
           OR NEW.submitted_at IS DISTINCT FROM OLD.submitted_at
           OR NEW.profile_refs <> OLD.profile_refs OR NEW.evidence_refs <> OLD.evidence_refs
           OR NEW.title <> OLD.title OR NEW.description IS DISTINCT FROM OLD.description) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'a SUBMITTED WBS change set is frozen: reopen it to edit';
    END IF;
    IF NEW.status <> OLD.status AND v_transition NOT IN (
           'DRAFT>SUBMITTED', 'SUBMITTED>APPLIED', 'SUBMITTED>REJECTED', 'DRAFT>WITHDRAWN',
           'SUBMITTED>WITHDRAWN', 'SUBMITTED>DRAFT', 'DRAFT>STALE', 'SUBMITTED>STALE') THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'WBS change set cannot move ' || v_transition;
    END IF;
    IF v_transition = 'DRAFT>SUBMITTED' THEN
        IF NEW.revision <> OLD.revision THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'submit freezes the current revision';
        END IF;
        PERFORM public.wbs_governance_require_user_role(NEW.tenant_id, NEW.submitted_by, ARRAY['admin', 'user'], 'submit');
    ELSIF v_transition = 'SUBMITTED>DRAFT' AND NEW.revision <> OLD.revision + 1 THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'reopening a WBS change set starts a new revision';
    ELSIF v_transition IN ('SUBMITTED>APPLIED', 'SUBMITTED>REJECTED') THEN
        PERFORM public.wbs_governance_require_user_role(NEW.tenant_id, NEW.decided_by, ARRAY['admin'], 'approve or reject');
        IF NEW.decided_by = NEW.submitted_by AND public.wbs_governance_requires_distinct_approver(NEW.tenant_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
                MESSAGE = 'the WBS approver must differ from the submitter (separation of duties)';
        END IF;
        IF v_transition = 'SUBMITTED>APPLIED' AND NOT EXISTS (
               SELECT 1 FROM public.wbs_baselines b
                WHERE b.source_change_set_id = NEW.id AND b.change_set_digest = NEW.submitted_digest
                  AND b.approved_by = NEW.decided_by
                  AND b.parent_baseline_id IS NOT DISTINCT FROM NEW.base_baseline_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'APPLIED requires the baseline created from this exact submitted digest';
        END IF;
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END
$fn$"""

CHANGE_SET_NODES_GUARD_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_change_set_nodes_guard()
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
            MESSAGE = 'candidate WBS nodes are editable only while the change set is DRAFT';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    IF TG_OP = 'UPDATE' AND (NEW.change_set_id <> OLD.change_set_id OR NEW.node_id <> OLD.node_id
           OR NEW.origin_kind <> OLD.origin_kind OR NEW.tenant_id <> OLD.tenant_id OR NEW.project_id <> OLD.project_id) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'a candidate node keeps its identity: remove and add instead';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.origin_kind = 'existing' THEN
            IF v_base IS NULL OR NOT EXISTS (
                   SELECT 1 FROM public.wbs_baseline_nodes bn WHERE bn.baseline_id = v_base AND bn.node_id = NEW.node_id) THEN
                RAISE EXCEPTION USING ERRCODE = 'check_violation',
                    MESSAGE = 'an existing candidate node must reuse an id of the base baseline';
            END IF;
        ELSIF NEW.origin_kind = 'adopted_legacy' THEN
            IF v_base IS NOT NULL OR NOT EXISTS (
                   SELECT 1 FROM public.wbs_nodes w WHERE w.id = NEW.node_id AND w.project_id = v_project) THEN
                RAISE EXCEPTION USING ERRCODE = 'check_violation',
                    MESSAGE = 'only a first baseline may adopt a live legacy id of the same project';
            END IF;
        ELSIF EXISTS (SELECT 1 FROM public.wbs_baseline_nodes bn WHERE bn.node_id = NEW.node_id)
              OR EXISTS (SELECT 1 FROM public.wbs_nodes w WHERE w.id = NEW.node_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'unique_violation',
                MESSAGE = 'a minted WBS id must be new: baseline, retired and live ids are never reused';
        END IF;
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END
$fn$"""

LINEAGE_GUARD_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_change_set_lineage_guard()
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
            MESSAGE = 'lineage edges are immutable: remove and add instead';
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
        -- A DRAFT candidate node deletion may cascade here; anything else is frozen.
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS lineage is editable only while the change set is DRAFT';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.wbs_change_set_nodes n
                    WHERE n.change_set_id = NEW.change_set_id AND n.node_id = NEW.target_node_id
                      AND n.origin_kind = 'minted') THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a lineage target must be a minted identity of the same change set';
    END IF;
    IF (v_base IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.wbs_baseline_nodes bn WHERE bn.baseline_id = v_base AND bn.node_id = NEW.source_node_id))
       OR (v_base IS NULL AND NOT EXISTS (
            SELECT 1 FROM public.wbs_nodes w WHERE w.id = NEW.source_node_id AND w.project_id = v_project)) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a lineage source must be an identity of the base baseline (or a legacy live node for a first baseline)';
    END IF;
    RETURN NEW;
END
$fn$"""

BASELINES_GUARD_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_baselines_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_cs public.wbs_change_sets;
    v_parent_no integer;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation', MESSAGE = 'WBS baselines are immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM public.projects p WHERE p.id = OLD.project_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation', MESSAGE = 'WBS baselines are immutable';
        END IF;
        RETURN OLD;
    END IF;
    SELECT * INTO v_cs FROM public.wbs_change_sets cs WHERE cs.id = NEW.source_change_set_id;
    IF NOT FOUND OR v_cs.project_id <> NEW.project_id OR v_cs.tenant_id <> NEW.tenant_id THEN
        RAISE EXCEPTION USING ERRCODE = 'foreign_key_violation',
            MESSAGE = 'a WBS baseline needs a change set of the same project';
    END IF;
    IF v_cs.status <> 'SUBMITTED' THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'only a SUBMITTED change set can become a baseline';
    END IF;
    IF v_cs.submitted_digest <> NEW.change_set_digest THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'the baseline digest differs from the submitted change-set digest';
    END IF;
    IF v_cs.base_baseline_id IS DISTINCT FROM NEW.parent_baseline_id THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'the change set was proposed against a different (stale) base baseline';
    END IF;
    IF NEW.parent_baseline_id IS NULL THEN
        IF EXISTS (SELECT 1 FROM public.wbs_baselines b WHERE b.project_id = NEW.project_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'unique_violation',
                MESSAGE = 'this project already has an approved first baseline';
        END IF;
    ELSE
        SELECT b.baseline_no INTO v_parent_no FROM public.wbs_baselines b
         WHERE b.id = NEW.parent_baseline_id AND b.project_id = NEW.project_id;
        IF v_parent_no IS NULL OR NEW.baseline_no <> v_parent_no + 1 OR EXISTS (
               SELECT 1 FROM public.wbs_baselines b WHERE b.project_id = NEW.project_id AND b.baseline_no > v_parent_no) THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'a baseline must directly follow the current baseline of its project';
        END IF;
    END IF;
    PERFORM public.wbs_governance_require_user_role(NEW.tenant_id, NEW.approved_by, ARRAY['admin'], 'approval');
    IF NEW.self_approved <> (NEW.approved_by = v_cs.submitted_by) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'self_approved must record whether the approver is the submitter';
    END IF;
    IF NEW.self_approved AND public.wbs_governance_requires_distinct_approver(NEW.tenant_id) THEN
        RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
            MESSAGE = 'the WBS approver must differ from the submitter (separation of duties)';
    END IF;
    RETURN NEW;
END
$fn$"""

BASELINES_COMMIT_CHECK_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_baselines_commit_check()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.wbs_baselines b WHERE b.id = NEW.id) THEN
        RETURN NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.wbs_change_sets cs
                    WHERE cs.id = NEW.source_change_set_id AND cs.status = 'APPLIED'
                      AND cs.decided_by = NEW.approved_by) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a WBS baseline commits only with its change set APPLIED by the same approver';
    END IF;
    IF (SELECT count(*) FROM public.wbs_baseline_nodes bn WHERE bn.baseline_id = NEW.id) <> NEW.node_count THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'the WBS baseline snapshot does not hold exactly node_count nodes';
    END IF;
    RETURN NULL;
END
$fn$"""

BASELINE_NODES_GUARD_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_baseline_nodes_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation', MESSAGE = 'WBS baseline nodes are immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM public.wbs_baselines b WHERE b.id = OLD.baseline_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation', MESSAGE = 'WBS baseline nodes are immutable';
        END IF;
        RETURN OLD;
    END IF;
    RETURN NEW;
END
$fn$"""

BASELINE_NODES_COMMIT_CHECK_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_baseline_nodes_commit_check()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_expected integer;
    v_same_write boolean;
BEGIN
    SELECT b.node_count, (b.xmin = bn.xmin) INTO v_expected, v_same_write
      FROM public.wbs_baselines b
      JOIN public.wbs_baseline_nodes bn ON bn.baseline_id = b.id AND bn.node_id = NEW.node_id
     WHERE b.id = NEW.baseline_id;
    IF v_expected IS NULL OR v_same_write THEN
        RETURN NULL;
    END IF;
    IF (SELECT count(*) FROM public.wbs_baseline_nodes bn WHERE bn.baseline_id = NEW.baseline_id) <> v_expected THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a committed WBS baseline snapshot cannot gain or lose nodes';
    END IF;
    RETURN NULL;
END
$fn$"""

PARENT_CYCLE_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_governance_parent_cycle_check()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_cycle boolean;
BEGIN
    IF TG_TABLE_NAME = 'wbs_change_set_nodes' THEN
        WITH RECURSIVE up (node_id, parent_id) AS (
            SELECT n.node_id, n.parent_id FROM public.wbs_change_set_nodes n
             WHERE n.change_set_id = NEW.change_set_id AND n.node_id = NEW.node_id
            UNION ALL
            SELECT p.node_id, p.parent_id FROM public.wbs_change_set_nodes p
              JOIN up ON p.node_id = up.parent_id
             WHERE p.change_set_id = NEW.change_set_id
        ) CYCLE node_id SET is_cycle USING walked
        SELECT bool_or(is_cycle) INTO v_cycle FROM up;
    ELSE
        WITH RECURSIVE up (node_id, parent_id) AS (
            SELECT n.node_id, n.parent_id FROM public.wbs_baseline_nodes n
             WHERE n.baseline_id = NEW.baseline_id AND n.node_id = NEW.node_id
            UNION ALL
            SELECT p.node_id, p.parent_id FROM public.wbs_baseline_nodes p
              JOIN up ON p.node_id = up.parent_id
             WHERE p.baseline_id = NEW.baseline_id
        ) CYCLE node_id SET is_cycle USING walked
        SELECT bool_or(is_cycle) INTO v_cycle FROM up;
    END IF;
    IF v_cycle THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation', MESSAGE = 'WBS parent cycle';
    END IF;
    RETURN NULL;
END
$fn$"""

FUNCTION_STATEMENTS: tuple[str, ...] = (
    REQUIRE_USER_ROLE_FUNCTION_SQL,
    REQUIRE_DISTINCT_FUNCTION_SQL,
    CHANGE_SET_GUARD_FUNCTION_SQL,
    CHANGE_SET_NODES_GUARD_FUNCTION_SQL,
    LINEAGE_GUARD_FUNCTION_SQL,
    BASELINES_GUARD_FUNCTION_SQL,
    BASELINES_COMMIT_CHECK_FUNCTION_SQL,
    BASELINE_NODES_GUARD_FUNCTION_SQL,
    BASELINE_NODES_COMMIT_CHECK_FUNCTION_SQL,
    PARENT_CYCLE_FUNCTION_SQL,
)

TRIGGER_STATEMENTS: tuple[str, ...] = (
    "CREATE TRIGGER trg_wbs_change_sets_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_change_sets FOR EACH ROW EXECUTE FUNCTION public.wbs_change_sets_guard()",
    "CREATE TRIGGER trg_wbs_change_set_nodes_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_change_set_nodes FOR EACH ROW EXECUTE FUNCTION public.wbs_change_set_nodes_guard()",
    "CREATE CONSTRAINT TRIGGER trg_wbs_change_set_nodes_cycle AFTER INSERT OR UPDATE OF parent_id ON public.wbs_change_set_nodes DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.wbs_governance_parent_cycle_check()",
    "CREATE TRIGGER trg_wbs_change_set_lineage_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_change_set_lineage FOR EACH ROW EXECUTE FUNCTION public.wbs_change_set_lineage_guard()",
    "CREATE TRIGGER trg_wbs_baselines_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_baselines FOR EACH ROW EXECUTE FUNCTION public.wbs_baselines_guard()",
    "CREATE CONSTRAINT TRIGGER trg_wbs_baselines_commit_check AFTER INSERT ON public.wbs_baselines DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.wbs_baselines_commit_check()",
    "CREATE TRIGGER trg_wbs_baseline_nodes_guard BEFORE UPDATE OR DELETE ON public.wbs_baseline_nodes FOR EACH ROW EXECUTE FUNCTION public.wbs_baseline_nodes_guard()",
    "CREATE CONSTRAINT TRIGGER trg_wbs_baseline_nodes_commit_check AFTER INSERT ON public.wbs_baseline_nodes DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.wbs_baseline_nodes_commit_check()",
    "CREATE CONSTRAINT TRIGGER trg_wbs_baseline_nodes_cycle AFTER INSERT ON public.wbs_baseline_nodes DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.wbs_governance_parent_cycle_check()",
)
