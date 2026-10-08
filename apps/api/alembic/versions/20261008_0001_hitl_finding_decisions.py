"""PQ-HITL-04B1: append-only, fail-closed per-finding HITL event ledger schema.

Revision ID: 20261008_0001
Revises: 20261007_0003

Schema only: NO finding write API and NO independent trust/settlement authority.
Run #940B2 guarded writer and dedicated PostgreSQL RLS/concurrency tests before
ever using this table in a runtime review route. Never migrate B decisions.
"""
from __future__ import annotations

from alembic import op

revision = "20261008_0001"
down_revision = "20261007_0003"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261008000100_hitl_finding_decisions.sql"

UPGRADE_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE public.review_items ADD CONSTRAINT uq_review_items_id_tenant_hitl UNIQUE (id, tenant_id)",
    "CREATE TABLE public.hitl_finding_decisions (\n    event_id uuid PRIMARY KEY,\n    tenant_id uuid NOT NULL,\n    project_id uuid NOT NULL,\n    review_row_id uuid NOT NULL,\n    document_id uuid NOT NULL,\n    document_revision_id uuid NOT NULL,\n    artifact_id uuid NOT NULL,\n    artifact_version integer NOT NULL,\n    artifact_hash varchar(64) NOT NULL,\n    generation bigint NOT NULL,\n    fencing_token bigint NOT NULL,\n    thread_id varchar(512) NOT NULL,\n    checkpoint_id varchar(255) NOT NULL,\n    finding_id varchar(64) NOT NULL,\n    source_item_id text NOT NULL,\n    source_ordinal integer NOT NULL,\n    finding_kind varchar(16) NOT NULL,\n    action varchar(32) NOT NULL,\n    reviewer_id varchar(256) NOT NULL,\n    created_by varchar(256) NOT NULL,\n    reason text,\n    proposed_text text,\n    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,\n    expected_ledger_revision bigint NOT NULL,\n    ledger_revision bigint NOT NULL,\n    idempotency_key varchar(128) NOT NULL,\n    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),\n    CONSTRAINT fk_hitl_finding_review FOREIGN KEY (review_row_id, tenant_id)\n        REFERENCES public.review_items (id, tenant_id) ON DELETE RESTRICT,\n    CONSTRAINT fk_hitl_finding_artifact FOREIGN KEY (artifact_id, tenant_id, project_id)\n        REFERENCES public.document_artifacts (artifact_id, tenant_id, project_id) ON DELETE RESTRICT,\n    CONSTRAINT fk_hitl_finding_revision FOREIGN KEY (document_revision_id, document_id, project_id, tenant_id)\n        REFERENCES public.document_revisions (revision_id, document_id, project_id, tenant_id) ON DELETE RESTRICT,\n    CONSTRAINT uq_hitl_finding_revision UNIQUE (tenant_id, review_row_id, ledger_revision),\n    CONSTRAINT uq_hitl_finding_idempotency UNIQUE (tenant_id, review_row_id, idempotency_key),\n    CONSTRAINT ck_hitl_finding_revision CHECK (ledger_revision = expected_ledger_revision + 1\n        AND expected_ledger_revision >= 0),\n    CONSTRAINT ck_hitl_finding_identity CHECK (artifact_version >= 1 AND generation >= 0\n        AND fencing_token >= 0 AND artifact_hash ~ '^[0-9a-f]{64}$'\n        AND finding_id ~ '^[0-9a-f]{64}$' AND length(btrim(thread_id)) > 0\n        AND length(btrim(checkpoint_id)) > 0 AND length(btrim(idempotency_key)) >= 8),\n    CONSTRAINT ck_hitl_finding_source CHECK (length(btrim(source_item_id)) > 0 AND source_ordinal >= 0 AND jsonb_typeof(evidence_refs) = 'array'),\n    CONSTRAINT ck_hitl_finding_kind CHECK (finding_kind IN ('RISK', 'CRITIQUE')),\n    CONSTRAINT ck_hitl_finding_action CHECK (action IN ('CONFIRMED', 'CORRECTION_PROPOSED', 'DISMISSED', 'NEEDS_INFO')),\n    CONSTRAINT ck_hitl_finding_human CHECK (length(btrim(reviewer_id)) > 0\n        AND created_by = reviewer_id),\n    CONSTRAINT ck_hitl_finding_change CHECK (\n        (action = 'CONFIRMED' AND proposed_text IS NULL)\n        OR (action = 'CORRECTION_PROPOSED' AND length(btrim(coalesce(reason, ''))) > 0\n            AND length(btrim(coalesce(proposed_text, ''))) > 0)\n        OR (action IN ('DISMISSED', 'NEEDS_INFO') AND length(btrim(coalesce(reason, ''))) > 0\n            AND proposed_text IS NULL)\n    )\n)",
    "CREATE INDEX ix_hitl_finding_tenant_candidate ON public.hitl_finding_decisions (tenant_id, review_row_id, artifact_hash, finding_id)",
    "CREATE FUNCTION public.hitl_finding_decisions_guard()\nRETURNS trigger\nLANGUAGE plpgsql\nSECURITY INVOKER\nSET search_path = public, pg_temp\nAS $fn$\nDECLARE\n    v_review public.review_items%ROWTYPE;\n    v_artifact public.document_artifacts%ROWTYPE;\n    v_authority public.document_processing_operations%ROWTYPE;\n    v_current_revision bigint;\nBEGIN\n    IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN\n        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',\n            MESSAGE = 'HITL finding decision events are append-only';\n    END IF;\n    -- Always lock the EXACT review row first. Never lock a document or the\n    -- processing-authority row here (see #758 lock-order deadlock regression).\n    SELECT * INTO v_review FROM public.review_items\n     WHERE id = NEW.review_row_id AND tenant_id = NEW.tenant_id\n     FOR UPDATE;\n    IF NOT FOUND OR v_review.project_id IS DISTINCT FROM NEW.project_id\n        OR v_review.document_id IS DISTINCT FROM NEW.document_id\n        OR v_review.current_status::text NOT IN (\n            'PENDING_REVIEW_REQUIRED', 'PENDING_REVIEW_CONDITIONAL', 'ESCALATED'\n        ) OR v_review.thread_id IS DISTINCT FROM NEW.thread_id\n        OR v_review.checkpoint_id IS DISTINCT FROM NEW.checkpoint_id\n        OR v_review.lineage_generation IS DISTINCT FROM NEW.generation\n        OR v_review.lineage_fencing_token IS DISTINCT FROM NEW.fencing_token\n        OR coalesce(v_review.review_metadata->>'trust_candidate_required', 'false') <> 'true'\n        OR v_review.review_metadata->'candidate_binding'->>'artifact_id'\n            IS DISTINCT FROM NEW.artifact_id::text\n        OR v_review.review_metadata->'candidate_binding'->>'document_id'\n            IS DISTINCT FROM NEW.document_id::text\n        OR v_review.review_metadata->'candidate_binding'->>'artifact_version'\n            IS DISTINCT FROM NEW.artifact_version::text\n        OR v_review.review_metadata->'candidate_binding'->>'artifact_hash'\n            IS DISTINCT FROM NEW.artifact_hash THEN\n        RAISE EXCEPTION USING ERRCODE = 'check_violation',\n            MESSAGE = 'finding decision requires exact pending bound review and lineage';\n    END IF;\n\n    SELECT * INTO v_artifact FROM public.document_artifacts\n     WHERE artifact_id = NEW.artifact_id AND tenant_id = NEW.tenant_id\n       AND project_id = NEW.project_id AND document_id = NEW.document_id\n       AND document_revision_id = NEW.document_revision_id;\n    IF NOT FOUND OR v_artifact.trust_state <> 'proposed'\n       OR v_artifact.artifact_version <> NEW.artifact_version\n       OR v_artifact.artifact_hash IS DISTINCT FROM NEW.artifact_hash THEN\n        RAISE EXCEPTION USING ERRCODE = 'check_violation',\n            MESSAGE = 'finding decision source must be exact proposed artifact revision';\n    END IF;\n\n    -- Read the live authority without locking it: acquiring that lock after\n    -- the review row would invert the #758 lock order. Final settlement has\n    -- its own stronger atomic concurrency gate.\n    SELECT * INTO v_authority FROM public.document_processing_operations\n     WHERE document_id = NEW.document_id AND tenant_id = NEW.tenant_id;\n    IF NOT FOUND OR v_authority.revision_id IS DISTINCT FROM NEW.document_revision_id\n        OR v_authority.generation IS DISTINCT FROM NEW.generation\n        OR v_authority.fencing_token IS DISTINCT FROM NEW.fencing_token\n        OR v_authority.stage <> 'ANALYSIS' THEN\n        RAISE EXCEPTION USING ERRCODE = 'check_violation',\n            MESSAGE = 'finding decision refers to stale document processing authority';\n    END IF;\n\n    SELECT coalesce(max(ledger_revision), 0) INTO v_current_revision\n      FROM public.hitl_finding_decisions\n     WHERE tenant_id = NEW.tenant_id AND review_row_id = NEW.review_row_id;\n    IF v_current_revision IS DISTINCT FROM NEW.expected_ledger_revision\n        OR NEW.ledger_revision <> v_current_revision + 1 THEN\n        RAISE EXCEPTION USING ERRCODE = 'serialization_failure',\n            MESSAGE = 'stale HITL finding decision ledger revision';\n    END IF;\n    RETURN NEW;\nEND\n$fn$",
    "REVOKE ALL ON FUNCTION public.hitl_finding_decisions_guard() FROM PUBLIC",
    "CREATE TRIGGER trg_hitl_finding_decisions_guard BEFORE INSERT OR UPDATE OR DELETE ON public.hitl_finding_decisions FOR EACH ROW EXECUTE FUNCTION public.hitl_finding_decisions_guard()",
    "ALTER TABLE public.hitl_finding_decisions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.hitl_finding_decisions FORCE ROW LEVEL SECURITY",
    "CREATE POLICY hitl_finding_decisions_select ON public.hitl_finding_decisions FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)",
    "CREATE POLICY hitl_finding_decisions_insert ON public.hitl_finding_decisions FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)",
    "REVOKE ALL ON TABLE public.hitl_finding_decisions FROM PUBLIC",
    "DO $do$\nDECLARE v_role text;\nBEGIN\n    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP\n        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_role) THEN\n            EXECUTE 'REVOKE ALL ON TABLE public.hitl_finding_decisions FROM ' || quote_ident(v_role);\n            EXECUTE 'REVOKE ALL ON FUNCTION public.hitl_finding_decisions_guard() FROM ' || quote_ident(v_role);\n        END IF;\n    END LOOP;\nEND\n$do$",
)
DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    "DO $do$\nBEGIN\n    IF EXISTS (SELECT 1 FROM public.hitl_finding_decisions LIMIT 1) THEN\n        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',\n            MESSAGE = 'cannot downgrade populated immutable HITL finding decision ledger';\n    END IF;\nEND\n$do$",
    "DROP TABLE public.hitl_finding_decisions",
    "DROP FUNCTION public.hitl_finding_decisions_guard()",
    "ALTER TABLE public.review_items DROP CONSTRAINT uq_review_items_id_tenant_hitl",
)


def supabase_sql() -> str:
    header = (
        "-- PQ-HITL-04B1 (#940): immutable tenant-bound decision-event ledger schema; no operational API.\n"
        "-- Mirror of apps/api/alembic/versions/20261008_0001_hitl_finding_decisions.py.\n"
    )
    return header + "\n" + "\n\n".join(s.strip() + ";" for s in UPGRADE_STATEMENTS) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
