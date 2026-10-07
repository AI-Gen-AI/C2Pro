"""PC-2b.2 (#921, ADR-030): WBS intelligence store -- runs, immutable items, human decisions.

Revision ID: 20261007_0001
Revises: 20261006_0003
Create Date: 2026-10-07

Persistence for intelligence ONLY. Nothing here creates, submits, approves or applies WBS: an
item is applied by a human through the unchanged PC-2a governed commands (ADR-029), and the
decision row records what that human chose -- never a baseline approval.

TABLES
------
* ``wbs_intelligence_runs`` -- one run: its exact input identity (mode, execution type, target
  kind/id/digest/revision/base, evidence-set digest, profile pins, contract / vocabulary /
  orchestration versions, idempotency key), its status (REQUESTED -> RUNNING -> COMPLETED |
  FAILED; REQUESTED | RUNNING -> CANCELLED) and, separately, its RunOutcome. The complete
  ``wbs-qualification/v1`` report is stored on the run (one coherent result, every dimension
  once), never spread over fake findings. A DETERMINISTIC run has no model provenance; an AI run
  must carry it. Input identity never changes; a terminal run is frozen. Freshness (STALE) is
  derived on read, never stored.
* ``wbs_intelligence_items`` -- FINDING | PROPOSAL, a typed body (CHECKed keys bound to the row
  identity), INSERT-ONLY and only while the run is RUNNING.
* ``wbs_intelligence_decisions`` -- APPEND-ONLY human decisions: APPLY_AS_PROPOSED,
  APPLY_WITH_HUMAN_EDIT or REJECT for a proposal; ACKNOWLEDGE, DISMISS or NO_CHANGE for a
  finding (the item kind is part of the composite FK, so the vocabularies cannot cross). One
  decision per item. An applied decision names the DRAFT change set, its revisions, the stored
  proposal digest and the exact governed commands that were executed.

IDEMPOTENCY: ``UNIQUE (tenant_id, idempotency_key) WHERE status IN ('REQUESTED', 'RUNNING',
'COMPLETED')`` -- the same key reuses an active or completed run of the same tenant, while a
FAILED or CANCELLED run never blocks a retry; concurrent identical requests serialize on the index.

SECURITY: every row carries ``tenant_id`` and ``project_id``; references are composite
(tenant, project, ...) foreign keys, so no row can point into another project even with known
ids. RLS is ENABLED and FORCED with fail-closed per-operation policies on ``app.current_tenant``;
``anon``/``authenticated`` get nothing (guarded on role existence). Requesters and deciders are
checked against ``users`` (an active human ``admin`` or ``user`` of the tenant -- never ``api``).
Guard functions are SECURITY INVOKER with a pinned search_path and no PUBLIC EXECUTE; history
rows disappear only through the project / tenant cascade. The SQL contains no percent sign.

DOWNGRADE drops the three tables (and their history) and the guard functions only.

Supabase CLI mirror: supabase/migrations/20261007000100_pc2b2_wbs_intelligence_store.sql,
rendered from ``UPGRADE_STATEMENTS`` by ``supabase_sql()`` (parity is tested).
"""

from __future__ import annotations

from alembic import op

revision = "20261007_0001"
down_revision = "20261006_0003"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261007000100_pc2b2_wbs_intelligence_store.sql"

INTELLIGENCE_TABLES = ("wbs_intelligence_runs", "wbs_intelligence_items", "wbs_intelligence_decisions")

_TENANT = "tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid"
_DIGEST = "'^sha256:[0-9a-f]{64}$'"

RUNS_SQL = f"""
CREATE TABLE public.wbs_intelligence_runs (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    mode text NOT NULL,
    execution_type text NOT NULL,
    target_kind text NOT NULL,
    target_change_set_id uuid,
    target_baseline_id uuid,
    target_import_id uuid,
    target_digest text,
    target_change_set_revision integer,
    target_base_baseline_id uuid,
    evidence_set_digest text NOT NULL,
    profile_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    proposal_contract_version text NOT NULL,
    qualification_vocab_version text NOT NULL,
    orchestration_version text NOT NULL,
    idempotency_key text NOT NULL,
    rerun_nonce text,
    model_provenance jsonb,
    status text NOT NULL,
    outcome text,
    qualification jsonb,
    qualification_digest text,
    failure_reason text,
    requested_by uuid NOT NULL,
    requested_by_kind text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    CONSTRAINT uq_wbs_intelligence_runs_tenant_project_id UNIQUE (tenant_id, project_id, id),
    CONSTRAINT fk_wbs_intelligence_runs_project FOREIGN KEY (tenant_id, project_id)
        REFERENCES public.projects (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_wbs_intelligence_runs_target_change_set FOREIGN KEY (tenant_id, project_id, target_change_set_id)
        REFERENCES public.wbs_change_sets (tenant_id, project_id, id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_wbs_intelligence_runs_target_baseline FOREIGN KEY (tenant_id, project_id, target_baseline_id)
        REFERENCES public.wbs_baselines (tenant_id, project_id, id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_wbs_intelligence_runs_target_base_baseline FOREIGN KEY (tenant_id, project_id, target_base_baseline_id)
        REFERENCES public.wbs_baselines (tenant_id, project_id, id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_wbs_intelligence_runs_mode CHECK (mode IN ('GENERATE', 'IMPORT_REVIEW', 'REVIEW_OPTIMIZE')),
    CONSTRAINT ck_wbs_intelligence_runs_execution_type CHECK (execution_type IN ('DETERMINISTIC', 'AI')),
    CONSTRAINT ck_wbs_intelligence_runs_target_kind CHECK (target_kind IN ('NONE', 'IMPORT', 'CANDIDATE', 'BASELINE')),
    CONSTRAINT ck_wbs_intelligence_runs_target_identity CHECK (
        (target_kind = 'NONE' AND num_nonnulls(target_change_set_id, target_baseline_id, target_import_id,
            target_digest, target_change_set_revision, target_base_baseline_id) = 0)
        OR (target_kind = 'CANDIDATE' AND target_change_set_id IS NOT NULL AND target_digest IS NOT NULL
            AND target_change_set_revision IS NOT NULL AND num_nonnulls(target_baseline_id, target_import_id) = 0)
        OR (target_kind = 'BASELINE' AND target_baseline_id IS NOT NULL AND target_digest IS NOT NULL
            AND num_nonnulls(target_change_set_id, target_import_id, target_change_set_revision) = 0)
        OR (target_kind = 'IMPORT' AND target_import_id IS NOT NULL AND target_digest IS NOT NULL
            AND num_nonnulls(target_change_set_id, target_baseline_id, target_change_set_revision) = 0)),
    CONSTRAINT ck_wbs_intelligence_runs_target_revision CHECK (target_change_set_revision IS NULL OR target_change_set_revision >= 1),
    CONSTRAINT ck_wbs_intelligence_runs_digests CHECK (
        evidence_set_digest ~ {_DIGEST} AND idempotency_key ~ {_DIGEST}
        AND (target_digest IS NULL OR target_digest ~ {_DIGEST})
        AND (qualification_digest IS NULL OR qualification_digest ~ {_DIGEST})),
    CONSTRAINT ck_wbs_intelligence_runs_profile_refs CHECK (jsonb_typeof(profile_refs) = 'array'),
    CONSTRAINT ck_wbs_intelligence_runs_versions CHECK (
        length(btrim(proposal_contract_version)) BETWEEN 1 AND 100
        AND length(btrim(qualification_vocab_version)) BETWEEN 1 AND 100
        AND length(btrim(orchestration_version)) BETWEEN 1 AND 100),
    CONSTRAINT ck_wbs_intelligence_runs_rerun_nonce CHECK (rerun_nonce IS NULL OR length(btrim(rerun_nonce)) BETWEEN 1 AND 200),
    CONSTRAINT ck_wbs_intelligence_runs_model_provenance CHECK (
        (execution_type = 'AI') = (model_provenance IS NOT NULL)
        AND (model_provenance IS NULL OR jsonb_typeof(model_provenance) = 'object')),
    CONSTRAINT ck_wbs_intelligence_runs_status CHECK (status IN ('REQUESTED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    CONSTRAINT ck_wbs_intelligence_runs_outcome CHECK (
        (status IN ('REQUESTED', 'RUNNING') AND outcome IS NULL AND completed_at IS NULL)
        OR (status = 'COMPLETED' AND outcome IN ('COMPLETE', 'PARTIAL_PROPOSAL', 'INSUFFICIENT_EVIDENCE')
            AND qualification IS NOT NULL AND started_at IS NOT NULL AND completed_at IS NOT NULL)
        OR (status = 'FAILED' AND outcome = 'FAILED' AND completed_at IS NOT NULL)
        OR (status = 'CANCELLED' AND outcome = 'CANCELLED' AND completed_at IS NOT NULL)),
    CONSTRAINT ck_wbs_intelligence_runs_started CHECK (status <> 'RUNNING' OR started_at IS NOT NULL),
    CONSTRAINT ck_wbs_intelligence_runs_qualification CHECK (
        (qualification IS NULL) = (qualification_digest IS NULL)
        AND (qualification IS NULL OR jsonb_typeof(qualification) = 'object')),
    CONSTRAINT ck_wbs_intelligence_runs_failure_reason CHECK (
        failure_reason IS NULL OR (status IN ('FAILED', 'CANCELLED') AND length(btrim(failure_reason)) BETWEEN 1 AND 2000)),
    CONSTRAINT ck_wbs_intelligence_runs_requested_by_kind CHECK (requested_by_kind IN ('human', 'service'))
)"""

ITEMS_SQL = f"""
CREATE TABLE public.wbs_intelligence_items (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    run_id uuid NOT NULL,
    kind text NOT NULL,
    ref text NOT NULL,
    ordinal integer NOT NULL,
    contract_version text NOT NULL,
    operation text,
    body jsonb NOT NULL,
    body_digest text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_wbs_intelligence_items_scope UNIQUE (tenant_id, project_id, run_id, id, kind),
    CONSTRAINT uq_wbs_intelligence_items_run_ref UNIQUE (run_id, ref),
    CONSTRAINT uq_wbs_intelligence_items_run_ordinal UNIQUE (run_id, ordinal),
    CONSTRAINT fk_wbs_intelligence_items_run FOREIGN KEY (tenant_id, project_id, run_id)
        REFERENCES public.wbs_intelligence_runs (tenant_id, project_id, id) ON DELETE CASCADE,
    CONSTRAINT ck_wbs_intelligence_items_kind CHECK (kind IN ('FINDING', 'PROPOSAL')),
    CONSTRAINT ck_wbs_intelligence_items_ref CHECK (ref ~ '^[a-z][a-z0-9_-]{{0,31}}$'),
    CONSTRAINT ck_wbs_intelligence_items_ordinal CHECK (ordinal >= 1),
    CONSTRAINT ck_wbs_intelligence_items_body_digest CHECK (body_digest ~ {_DIGEST}),
    CONSTRAINT ck_wbs_intelligence_items_typed_body CHECK (
        jsonb_typeof(body) = 'object' AND (
        (kind = 'PROPOSAL' AND contract_version = 'wbs-proposal/v1'
            AND operation IN ('ADD_NODE', 'UPDATE_NODE', 'RECODE_NODE', 'MOVE_NODE', 'REORDER_NODE', 'REMOVE_NODE',
                              'SPLIT_NODE', 'MERGE_NODES')
            AND body ?& ARRAY['item_id', 'ref', 'operation', 'payload', 'affected_node_ids', 'target_fingerprints',
                              'creates_labels', 'uses_labels', 'depends_on', 'rationale', 'evidence', 'confidence_pct',
                              'destructive']
            AND body ->> 'item_id' = id::text AND body ->> 'ref' = ref AND body ->> 'operation' = operation
            AND jsonb_typeof(body -> 'payload') = 'object' AND jsonb_typeof(body -> 'target_fingerprints') = 'object'
            AND jsonb_typeof(body -> 'depends_on') = 'array')
        OR (kind = 'FINDING' AND contract_version = 'wbs-qualification/v1' AND operation IS NULL
            AND body ?& ARRAY['finding_id', 'dimension', 'status', 'method', 'summary']
            AND body ->> 'finding_id' = id::text AND body ->> 'status' IN ('GAP', 'WARNING', 'AMBIGUOUS'))))
)"""

DECISIONS_SQL = f"""
CREATE TABLE public.wbs_intelligence_decisions (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    run_id uuid NOT NULL,
    item_id uuid NOT NULL,
    item_kind text NOT NULL,
    decision text NOT NULL,
    batch_id uuid NOT NULL,
    decided_by uuid NOT NULL,
    decided_by_kind text NOT NULL,
    reason text,
    change_set_id uuid,
    change_set_revision_before integer,
    change_set_revision_after integer,
    proposal_body_digest text,
    applied_commands jsonb,
    applied_commands_digest text,
    label_node_ids jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_wbs_intelligence_decisions_item UNIQUE (item_id),
    CONSTRAINT fk_wbs_intelligence_decisions_item FOREIGN KEY (tenant_id, project_id, run_id, item_id, item_kind)
        REFERENCES public.wbs_intelligence_items (tenant_id, project_id, run_id, id, kind) ON DELETE CASCADE,
    CONSTRAINT fk_wbs_intelligence_decisions_change_set FOREIGN KEY (tenant_id, project_id, change_set_id)
        REFERENCES public.wbs_change_sets (tenant_id, project_id, id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_wbs_intelligence_decisions_vocabulary CHECK (
        (item_kind = 'PROPOSAL' AND decision IN ('APPLY_AS_PROPOSED', 'APPLY_WITH_HUMAN_EDIT', 'REJECT'))
        OR (item_kind = 'FINDING' AND decision IN ('ACKNOWLEDGE', 'DISMISS', 'NO_CHANGE'))),
    CONSTRAINT ck_wbs_intelligence_decisions_human CHECK (decided_by_kind = 'human'),
    CONSTRAINT ck_wbs_intelligence_decisions_application CHECK (
        (decision IN ('APPLY_AS_PROPOSED', 'APPLY_WITH_HUMAN_EDIT')
            AND num_nonnulls(change_set_id, change_set_revision_before, change_set_revision_after, proposal_body_digest,
                             applied_commands, applied_commands_digest, label_node_ids) = 7
            AND change_set_revision_after > change_set_revision_before AND change_set_revision_before >= 1)
        OR (decision NOT IN ('APPLY_AS_PROPOSED', 'APPLY_WITH_HUMAN_EDIT')
            AND num_nonnulls(change_set_id, change_set_revision_before, change_set_revision_after, proposal_body_digest,
                             applied_commands, applied_commands_digest, label_node_ids) = 0)),
    CONSTRAINT ck_wbs_intelligence_decisions_digests CHECK (
        (proposal_body_digest IS NULL OR proposal_body_digest ~ {_DIGEST})
        AND (applied_commands_digest IS NULL OR applied_commands_digest ~ {_DIGEST})),
    CONSTRAINT ck_wbs_intelligence_decisions_payloads CHECK (
        (applied_commands IS NULL OR jsonb_typeof(applied_commands) = 'array')
        AND (label_node_ids IS NULL OR jsonb_typeof(label_node_ids) = 'object')),
    CONSTRAINT ck_wbs_intelligence_decisions_reason CHECK (reason IS NULL OR length(btrim(reason)) BETWEEN 1 AND 4000)
)"""

INDEX_STATEMENTS: tuple[str, ...] = (
    # The idempotency backstop: one active or reusable run per tenant and key. FAILED and
    # CANCELLED runs are outside the predicate, so they never block (or answer) a retry.
    "CREATE UNIQUE INDEX uq_wbs_intelligence_runs_reusable_key ON public.wbs_intelligence_runs "
    "(tenant_id, idempotency_key) WHERE status IN ('REQUESTED', 'RUNNING', 'COMPLETED')",
    "CREATE INDEX ix_wbs_intelligence_runs_project ON public.wbs_intelligence_runs (tenant_id, project_id, created_at)",
    "CREATE INDEX ix_wbs_intelligence_decisions_run ON public.wbs_intelligence_decisions (tenant_id, project_id, run_id)",
    "CREATE INDEX ix_wbs_intelligence_decisions_change_set ON public.wbs_intelligence_decisions (change_set_id)",
)

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

FUNCTION_SIGNATURES = (
    "public.wbs_intelligence_runs_guard()",
    "public.wbs_intelligence_items_guard()",
    "public.wbs_intelligence_decisions_guard()",
)

TRIGGER_STATEMENTS: tuple[str, ...] = (
    "CREATE TRIGGER trg_wbs_intelligence_runs_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_intelligence_runs "
    "FOR EACH ROW EXECUTE FUNCTION public.wbs_intelligence_runs_guard()",
    "CREATE TRIGGER trg_wbs_intelligence_items_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_intelligence_items "
    "FOR EACH ROW EXECUTE FUNCTION public.wbs_intelligence_items_guard()",
    "CREATE TRIGGER trg_wbs_intelligence_decisions_guard BEFORE INSERT OR UPDATE OR DELETE "
    "ON public.wbs_intelligence_decisions FOR EACH ROW EXECUTE FUNCTION public.wbs_intelligence_decisions_guard()",
)


def _rls_statements(table: str) -> tuple[str, ...]:
    return (
        f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY",
        f"CREATE POLICY {table}_tenant_select ON public.{table} FOR SELECT USING ({_TENANT})",
        f"CREATE POLICY {table}_tenant_insert ON public.{table} FOR INSERT WITH CHECK ({_TENANT})",
        f"CREATE POLICY {table}_tenant_update ON public.{table} FOR UPDATE USING ({_TENANT}) WITH CHECK ({_TENANT})",
        f"CREATE POLICY {table}_tenant_delete ON public.{table} FOR DELETE USING ({_TENANT})",
    )


RLS_STATEMENTS: tuple[str, ...] = tuple(statement for table in INTELLIGENCE_TABLES for statement in _rls_statements(table))

# Supabase platform roles do not exist on plain PostgreSQL (CI, local): guard on existence.
_REVOKE_DATA_API_TEMPLATE = """
DO $do$
DECLARE
    v_role text;
BEGIN
    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = v_role) THEN
            EXECUTE 'REVOKE ALL ON TABLE public.wbs_intelligence_runs, public.wbs_intelligence_items, '
                 || 'public.wbs_intelligence_decisions FROM ' || quote_ident(v_role);
            -- Supabase default privileges grant EXECUTE on new public functions to these roles.
            EXECUTE 'REVOKE ALL ON FUNCTION {functions} FROM ' || quote_ident(v_role);
        END IF;
    END LOOP;
END
$do$"""
REVOKE_DATA_API_SQL = _REVOKE_DATA_API_TEMPLATE.replace("{functions}", ", ".join(FUNCTION_SIGNATURES))

UPGRADE_STATEMENTS: tuple[str, ...] = (
    RUNS_SQL,
    ITEMS_SQL,
    DECISIONS_SQL,
    *INDEX_STATEMENTS,
    *FUNCTION_STATEMENTS,
    *(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC" for signature in FUNCTION_SIGNATURES),
    *TRIGGER_STATEMENTS,
    *RLS_STATEMENTS,
    REVOKE_DATA_API_SQL,
)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    "DROP TABLE IF EXISTS public.wbs_intelligence_decisions",
    "DROP TABLE IF EXISTS public.wbs_intelligence_items",
    "DROP TABLE IF EXISTS public.wbs_intelligence_runs",
    *(f"DROP FUNCTION IF EXISTS {signature}" for signature in reversed(FUNCTION_SIGNATURES)),
)


def supabase_sql() -> str:
    """The Supabase CLI mirror: the same upgrade statements, in order."""
    header = (
        "-- PC-2b.2 (#921, ADR-030): WBS intelligence store -- runs, immutable items, append-only human decisions.\n"
        "-- Mirror of apps/api/alembic/versions/20261007_0001_pc2b2_wbs_intelligence_store.py "
        "(rendered from UPGRADE_STATEMENTS; do not edit by hand).\n"
    )
    return header + "\n" + "\n\n".join(statement.strip() + ";" for statement in UPGRADE_STATEMENTS) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
