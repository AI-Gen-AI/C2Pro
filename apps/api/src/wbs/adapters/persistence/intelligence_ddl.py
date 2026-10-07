"""WBS intelligence store guard functions and triggers (PC-2b.2 #921).

A literal copy of the DDL in alembic revision ``20261007_0001``: the test schema is built
with ``Base.metadata.create_all`` and must carry the same database-enforced invariants.
tests/unit/product_control/test_pc2b2_wbs_intelligence_store_migration.py keeps the two equal.
Edit the migration first (or add a new one), then mirror it here.
"""

from __future__ import annotations

RUNS_GUARD_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_intelligence_runs_guard()
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
                MESSAGE = 'WBS intelligence runs are audit history: cancel instead of deleting';
        END IF;
        RETURN OLD;
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status NOT IN ('REQUESTED', 'RUNNING') THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'a WBS intelligence run starts REQUESTED or RUNNING';
        END IF;
        IF NEW.requested_by_kind = 'human' THEN
            PERFORM public.wbs_governance_require_user_role(NEW.tenant_id, NEW.requested_by, ARRAY['admin', 'user'],
                                                            'requesting a WBS intelligence run');
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status IN ('COMPLETED', 'FAILED', 'CANCELLED') THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS intelligence run is ' || OLD.status || ' and immutable';
    END IF;
    IF (NEW.id, NEW.tenant_id, NEW.project_id, NEW.mode, NEW.execution_type, NEW.target_kind, NEW.target_change_set_id,
        NEW.target_baseline_id, NEW.target_import_id, NEW.target_digest, NEW.target_change_set_revision,
        NEW.target_base_baseline_id, NEW.evidence_set_digest, NEW.profile_refs, NEW.proposal_contract_version,
        NEW.qualification_vocab_version, NEW.orchestration_version, NEW.idempotency_key, NEW.rerun_nonce,
        NEW.model_provenance, NEW.requested_by, NEW.requested_by_kind, NEW.created_at)
       IS DISTINCT FROM
       (OLD.id, OLD.tenant_id, OLD.project_id, OLD.mode, OLD.execution_type, OLD.target_kind, OLD.target_change_set_id,
        OLD.target_baseline_id, OLD.target_import_id, OLD.target_digest, OLD.target_change_set_revision,
        OLD.target_base_baseline_id, OLD.evidence_set_digest, OLD.profile_refs, OLD.proposal_contract_version,
        OLD.qualification_vocab_version, OLD.orchestration_version, OLD.idempotency_key, OLD.rerun_nonce,
        OLD.model_provenance, OLD.requested_by, OLD.requested_by_kind, OLD.created_at) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'a WBS intelligence run keeps its input identity';
    END IF;
    v_transition := OLD.status || '>' || NEW.status;
    IF v_transition NOT IN ('REQUESTED>RUNNING', 'REQUESTED>FAILED', 'REQUESTED>CANCELLED', 'RUNNING>COMPLETED',
                            'RUNNING>FAILED', 'RUNNING>CANCELLED') THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'WBS intelligence run cannot move ' || v_transition;
    END IF;
    RETURN NEW;
END
$fn$"""


ITEMS_GUARD_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_intelligence_items_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS intelligence items are immutable (insert-only)';
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM public.wbs_intelligence_runs r WHERE r.id = OLD.run_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'WBS intelligence items are immutable (insert-only)';
        END IF;
        RETURN OLD;
    END IF;
    -- A run hidden by the writer's RLS context is simply not found: fail closed.
    IF NOT EXISTS (SELECT 1 FROM public.wbs_intelligence_runs r
                    WHERE r.id = NEW.run_id AND r.tenant_id = NEW.tenant_id AND r.project_id = NEW.project_id
                      AND r.status = 'RUNNING') THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS intelligence items are recorded only while their run is RUNNING';
    END IF;
    RETURN NEW;
END
$fn$"""


DECISIONS_GUARD_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_intelligence_decisions_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_run_status text;
    v_body_digest text;
    v_cs_status text;
    v_cs_revision integer;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS intelligence decisions are append-only';
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM public.wbs_intelligence_items i WHERE i.id = OLD.item_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'WBS intelligence decisions are append-only';
        END IF;
        RETURN OLD;
    END IF;
    -- A decision is a human choice about a suggestion, never a WBS approval: an active human
    -- admin or user of the tenant (never api, AI or a service).
    PERFORM public.wbs_governance_require_user_role(NEW.tenant_id, NEW.decided_by, ARRAY['admin', 'user'],
                                                    'deciding a WBS intelligence item');
    SELECT r.status INTO v_run_status FROM public.wbs_intelligence_runs r
     WHERE r.id = NEW.run_id AND r.tenant_id = NEW.tenant_id AND r.project_id = NEW.project_id;
    IF v_run_status IS DISTINCT FROM 'COMPLETED' THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'only the items of a COMPLETED WBS intelligence run are decided';
    END IF;
    IF NEW.decision IN ('APPLY_AS_PROPOSED', 'APPLY_WITH_HUMAN_EDIT') THEN
        SELECT i.body_digest INTO v_body_digest FROM public.wbs_intelligence_items i WHERE i.id = NEW.item_id;
        IF NEW.proposal_body_digest IS DISTINCT FROM v_body_digest THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'an applied decision references the stored proposal digest';
        END IF;
        SELECT cs.status, cs.revision INTO v_cs_status, v_cs_revision FROM public.wbs_change_sets cs
         WHERE cs.id = NEW.change_set_id AND cs.tenant_id = NEW.tenant_id AND cs.project_id = NEW.project_id;
        IF v_cs_status IS DISTINCT FROM 'DRAFT' OR v_cs_revision < NEW.change_set_revision_after THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'a proposal is applied only into a DRAFT change set of its project, through its governed commands';
        END IF;
    END IF;
    RETURN NEW;
END
$fn$"""


FUNCTION_STATEMENTS: tuple[str, ...] = (RUNS_GUARD_FUNCTION_SQL, ITEMS_GUARD_FUNCTION_SQL, DECISIONS_GUARD_FUNCTION_SQL)

TRIGGER_STATEMENTS: tuple[str, ...] = (
    "CREATE TRIGGER trg_wbs_intelligence_runs_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_intelligence_runs "
    "FOR EACH ROW EXECUTE FUNCTION public.wbs_intelligence_runs_guard()",
    "CREATE TRIGGER trg_wbs_intelligence_items_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_intelligence_items "
    "FOR EACH ROW EXECUTE FUNCTION public.wbs_intelligence_items_guard()",
    "CREATE TRIGGER trg_wbs_intelligence_decisions_guard BEFORE INSERT OR UPDATE OR DELETE "
    "ON public.wbs_intelligence_decisions FOR EACH ROW EXECUTE FUNCTION public.wbs_intelligence_decisions_guard()",
)

# The idempotency backstop's predicate (same as the migration's partial unique index).
REUSABLE_KEY_INDEX_WHERE = "status IN ('REQUESTED', 'RUNNING', 'COMPLETED')"


__all__ = [
    "DECISIONS_GUARD_FUNCTION_SQL",
    "FUNCTION_STATEMENTS",
    "ITEMS_GUARD_FUNCTION_SQL",
    "REUSABLE_KEY_INDEX_WHERE",
    "RUNS_GUARD_FUNCTION_SQL",
    "TRIGGER_STATEMENTS",
]
