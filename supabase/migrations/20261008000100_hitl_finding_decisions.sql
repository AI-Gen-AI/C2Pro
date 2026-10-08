-- PQ-HITL-04B1 (#940): immutable tenant-bound decision-event ledger schema; no operational API.
-- Mirror of apps/api/alembic/versions/20261008_0001_hitl_finding_decisions.py.

ALTER TABLE public.review_items ADD CONSTRAINT uq_review_items_id_tenant_hitl UNIQUE (id, tenant_id);

CREATE TABLE public.hitl_finding_decisions (
    event_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    review_row_id uuid NOT NULL,
    document_id uuid NOT NULL,
    document_revision_id uuid NOT NULL,
    artifact_id uuid NOT NULL,
    artifact_version integer NOT NULL,
    artifact_hash varchar(64) NOT NULL,
    generation bigint NOT NULL,
    fencing_token bigint NOT NULL,
    thread_id varchar(512) NOT NULL,
    checkpoint_id varchar(255) NOT NULL,
    finding_id varchar(64) NOT NULL,
    finding_kind varchar(16) NOT NULL,
    action varchar(32) NOT NULL,
    reviewer_id varchar(256) NOT NULL,
    created_by varchar(256) NOT NULL,
    reason text,
    proposed_text text,
    expected_ledger_revision bigint NOT NULL,
    ledger_revision bigint NOT NULL,
    idempotency_key varchar(128) NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT fk_hitl_finding_review FOREIGN KEY (review_row_id, tenant_id)
        REFERENCES public.review_items (id, tenant_id) ON DELETE RESTRICT,
    CONSTRAINT fk_hitl_finding_artifact FOREIGN KEY (artifact_id, tenant_id, project_id)
        REFERENCES public.document_artifacts (artifact_id, tenant_id, project_id) ON DELETE RESTRICT,
    CONSTRAINT fk_hitl_finding_revision FOREIGN KEY (document_revision_id, document_id, project_id, tenant_id)
        REFERENCES public.document_revisions (revision_id, document_id, project_id, tenant_id) ON DELETE RESTRICT,
    CONSTRAINT uq_hitl_finding_revision UNIQUE (tenant_id, review_row_id, ledger_revision),
    CONSTRAINT uq_hitl_finding_idempotency UNIQUE (tenant_id, review_row_id, idempotency_key),
    CONSTRAINT ck_hitl_finding_revision CHECK (ledger_revision = expected_ledger_revision + 1
        AND expected_ledger_revision >= 0),
    CONSTRAINT ck_hitl_finding_identity CHECK (artifact_version >= 1 AND generation >= 0
        AND fencing_token >= 0 AND artifact_hash ~ '^[0-9a-f]{64}$'
        AND finding_id ~ '^[0-9a-f]{64}$' AND length(btrim(thread_id)) > 0
        AND length(btrim(checkpoint_id)) > 0 AND length(btrim(idempotency_key)) >= 8),
    CONSTRAINT ck_hitl_finding_kind CHECK (finding_kind IN ('RISK', 'CRITIQUE')),
    CONSTRAINT ck_hitl_finding_action CHECK (action IN ('CONFIRMED', 'CORRECTION_PROPOSED', 'DISMISSED', 'NEEDS_INFO')),
    CONSTRAINT ck_hitl_finding_human CHECK (length(btrim(reviewer_id)) > 0
        AND created_by = reviewer_id),
    CONSTRAINT ck_hitl_finding_change CHECK (
        (action = 'CONFIRMED' AND proposed_text IS NULL)
        OR (action = 'CORRECTION_PROPOSED' AND length(btrim(coalesce(reason, ''))) > 0
            AND length(btrim(coalesce(proposed_text, ''))) > 0)
        OR (action IN ('DISMISSED', 'NEEDS_INFO') AND length(btrim(coalesce(reason, ''))) > 0
            AND proposed_text IS NULL)
    )
);

CREATE INDEX ix_hitl_finding_tenant_candidate ON public.hitl_finding_decisions (tenant_id, review_row_id, artifact_hash, finding_id);

CREATE FUNCTION public.hitl_finding_decisions_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_review public.review_items%ROWTYPE;
    v_artifact public.document_artifacts%ROWTYPE;
    v_authority public.document_processing_operations%ROWTYPE;
    v_current_revision bigint;
BEGIN
    IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'HITL finding decision events are append-only';
    END IF;
    -- Always lock the EXACT review row first. Never lock a document or the
    -- processing-authority row here (see #758 lock-order deadlock regression).
    SELECT * INTO v_review FROM public.review_items
     WHERE id = NEW.review_row_id AND tenant_id = NEW.tenant_id
     FOR UPDATE;
    IF NOT FOUND OR v_review.project_id IS DISTINCT FROM NEW.project_id
        OR v_review.document_id IS DISTINCT FROM NEW.document_id
        OR v_review.current_status::text NOT IN (
            'PENDING_REVIEW_REQUIRED', 'PENDING_REVIEW_CONDITIONAL', 'ESCALATED'
        ) OR v_review.thread_id IS DISTINCT FROM NEW.thread_id
        OR v_review.checkpoint_id IS DISTINCT FROM NEW.checkpoint_id
        OR v_review.lineage_generation IS DISTINCT FROM NEW.generation
        OR v_review.lineage_fencing_token IS DISTINCT FROM NEW.fencing_token
        OR coalesce(v_review.review_metadata->>'trust_candidate_required', 'false') <> 'true'
        OR v_review.review_metadata->'candidate_binding'->>'artifact_id'
            IS DISTINCT FROM NEW.artifact_id::text
        OR v_review.review_metadata->'candidate_binding'->>'document_id'
            IS DISTINCT FROM NEW.document_id::text
        OR v_review.review_metadata->'candidate_binding'->>'artifact_version'
            IS DISTINCT FROM NEW.artifact_version::text
        OR v_review.review_metadata->'candidate_binding'->>'artifact_hash'
            IS DISTINCT FROM NEW.artifact_hash THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'finding decision requires exact pending bound review and lineage';
    END IF;

    SELECT * INTO v_artifact FROM public.document_artifacts
     WHERE artifact_id = NEW.artifact_id AND tenant_id = NEW.tenant_id
       AND project_id = NEW.project_id AND document_id = NEW.document_id
       AND document_revision_id = NEW.document_revision_id;
    IF NOT FOUND OR v_artifact.trust_state <> 'proposed'
       OR v_artifact.artifact_version <> NEW.artifact_version
       OR v_artifact.artifact_hash IS DISTINCT FROM NEW.artifact_hash THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'finding decision source must be exact proposed artifact revision';
    END IF;

    -- Read the live authority without locking it: acquiring that lock after
    -- the review row would invert the #758 lock order. Final settlement has
    -- its own stronger atomic concurrency gate.
    SELECT * INTO v_authority FROM public.document_processing_operations
     WHERE document_id = NEW.document_id AND tenant_id = NEW.tenant_id;
    IF NOT FOUND OR v_authority.revision_id IS DISTINCT FROM NEW.document_revision_id
        OR v_authority.generation IS DISTINCT FROM NEW.generation
        OR v_authority.fencing_token IS DISTINCT FROM NEW.fencing_token
        OR v_authority.stage <> 'ANALYSIS' THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'finding decision refers to stale document processing authority';
    END IF;

    SELECT coalesce(max(ledger_revision), 0) INTO v_current_revision
      FROM public.hitl_finding_decisions
     WHERE tenant_id = NEW.tenant_id AND review_row_id = NEW.review_row_id;
    IF v_current_revision IS DISTINCT FROM NEW.expected_ledger_revision
        OR NEW.ledger_revision <> v_current_revision + 1 THEN
        RAISE EXCEPTION USING ERRCODE = 'serialization_failure',
            MESSAGE = 'stale HITL finding decision ledger revision';
    END IF;
    RETURN NEW;
END
$fn$;

REVOKE ALL ON FUNCTION public.hitl_finding_decisions_guard() FROM PUBLIC;

CREATE TRIGGER trg_hitl_finding_decisions_guard BEFORE INSERT OR UPDATE OR DELETE ON public.hitl_finding_decisions FOR EACH ROW EXECUTE FUNCTION public.hitl_finding_decisions_guard();

ALTER TABLE public.hitl_finding_decisions ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.hitl_finding_decisions FORCE ROW LEVEL SECURITY;

CREATE POLICY hitl_finding_decisions_select ON public.hitl_finding_decisions FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY hitl_finding_decisions_insert ON public.hitl_finding_decisions FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

REVOKE ALL ON TABLE public.hitl_finding_decisions FROM PUBLIC;

DO $do$
DECLARE v_role text;
BEGIN
    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_role) THEN
            EXECUTE 'REVOKE ALL ON TABLE public.hitl_finding_decisions FROM ' || quote_ident(v_role);
            EXECUTE 'REVOKE ALL ON FUNCTION public.hitl_finding_decisions_guard() FROM ' || quote_ident(v_role);
        END IF;
    END LOOP;
END
$do$;
