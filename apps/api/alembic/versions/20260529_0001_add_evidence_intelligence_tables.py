"""Add Evidence Intelligence Layer shadow tables (ADR-011 Phase 2A.3).

Phase 2A.3 — Minimal shadow persistence for the LEGAL extraction pilot.
Creates two tables:

  * evidence_claims              — validated EvidenceClaim records (claims channel)
  * evidence_extraction_events   — processing_error + out_of_scope channels,
                                   discriminated by event_type (NOT an amorphous JSONB)

Design decisions locked in review (Claude + DeepSeek + Gemini consensus):
  * Definitive table with lifecycle_status (default 'shadow'), NOT a mirror table.
  * extraction_run_id on BOTH tables: enables atomic batch supersession by run,
    and audits which claims/events belong to the same extractor pass.
  * Tenancy columns (tenant_id/project_id/document_id) from day one, indexed.
    RLS policies are DEFERRED to Phase 2A.5 (follow the pattern established in
    20260205_0001_enable_rls_policies.py) — columns exist now, policies later.
  * CHECK constraints enforce enums and [0,1] ranges as a DB-level safety net
    behind the Pydantic validation in the adapter.
  * value JSONB has no shape CHECK by design — each claim_type has its own shape,
    validated in Pydantic before reaching the DB. Integrity of `value` lives in
    the adapter layer; the DB trusts the adapter is the only write path.

Write-only in this phase: the Coherence Engine MUST NOT read these tables yet
(isolation is sacred — reading would bypass the v1 stub and falsify the Phase 5
shadow comparison).

Timestamps are naive UTC to match the rest of the schema (TIMESTAMP WITHOUT TIME
ZONE), per src/coherence/adapters/persistence/models.py::_utcnow_naive.

Revision ID: 20260529_0001
Revises: 20260526_0001
Create Date: 2026-05-29

Suite ID: TS-INT-ALEMBIC-EVI-SHADOW-001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260529_0001"
down_revision: str = "20260526_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create evidence_claims and evidence_extraction_events shadow tables."""
    op.execute("SET LOCAL lock_timeout = '30s';")

    # ------------------------------------------------------------------
    # 1. evidence_claims — the claims channel (definitive table, flagged)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE evidence_claims (
            claim_id              UUID PRIMARY KEY,
            extraction_run_id     UUID NOT NULL,

            -- Tenancy (RLS columns; policies deferred to 2A.5)
            tenant_id             UUID NOT NULL,
            project_id            UUID NOT NULL,
            document_id           UUID NOT NULL,

            -- Claim core
            dimension             VARCHAR(32) NOT NULL,
            claim_type            VARCHAR(64) NOT NULL,
            value                 JSONB NOT NULL,

            -- Technical axis (feeds TRI / Coverage in later phases)
            algorithmic_certainty DOUBLE PRECISION NOT NULL,
            freshness             DOUBLE PRECISION NOT NULL,

            -- Verification (CVC result; UNCERTAIN while CVC is off in 2A)
            verification_status   VARCHAR(32) NOT NULL,
            verification_trace    JSONB NOT NULL DEFAULT '{}'::jsonb,

            -- Lifecycle (shadow until cutover; superseded by batch in 2A.5)
            lifecycle_status      VARCHAR(32) NOT NULL DEFAULT 'shadow',

            -- SourceRef (text_anchor) — physical locator, resilient to OCR
            locator_quality       VARCHAR(32) NOT NULL,
            page                  INTEGER,
            char_start            INTEGER,
            char_end              INTEGER,
            quote                 TEXT,

            created_at            TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),

            -- Enum guards
            CONSTRAINT ck_claims_dimension CHECK (
                dimension IN ('SCOPE','BUDGET','TIME','TECHNICAL','LEGAL','QUALITY')
            ),
            CONSTRAINT ck_claims_verification_status CHECK (
                verification_status IN ('verified','uncertain','unsupported','fabrication_suspected')
            ),
            CONSTRAINT ck_claims_locator_quality CHECK (
                locator_quality IN ('exact','approximate','missing')
            ),
            CONSTRAINT ck_claims_lifecycle_status CHECK (
                lifecycle_status IN ('shadow','active','superseded','discarded')
            ),
            -- Range guards (DB-level net behind Pydantic)
            CONSTRAINT ck_claims_certainty_range CHECK (
                algorithmic_certainty >= 0 AND algorithmic_certainty <= 1
            ),
            CONSTRAINT ck_claims_freshness_range CHECK (
                freshness >= 0 AND freshness <= 1
            )
        );
        """
    )

    # Composite index for tenancy isolation + batch supersession by run.
    # Supersession (2A.5) marks rows of a document whose run != current run,
    # so document_id + extraction_run_id must be cheap to scan together.
    op.execute(
        """
        CREATE INDEX ix_claims_tenancy_doc_run
            ON evidence_claims (tenant_id, project_id, document_id, extraction_run_id);
        """
    )
    op.execute(
        """
        CREATE INDEX ix_claims_doc_lifecycle
            ON evidence_claims (document_id, lifecycle_status);
        """
    )

    # ------------------------------------------------------------------
    # 2. evidence_extraction_events — processing_error + out_of_scope
    #    Typed, discriminated by event_type. JSONB only for free trace.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE evidence_extraction_events (
            event_id          UUID PRIMARY KEY,
            extraction_run_id UUID NOT NULL,

            tenant_id         UUID NOT NULL,
            project_id        UUID NOT NULL,
            document_id       UUID NOT NULL,

            event_type        VARCHAR(32) NOT NULL,
            -- dimension may be NULL on a wrong-dimension drift where it is the
            -- offending value we still want to record; kept nullable on purpose.
            dimension         VARCHAR(32),
            claim_type        VARCHAR(64),
            reason            VARCHAR(64) NOT NULL,
            payload_trace     JSONB NOT NULL DEFAULT '{}'::jsonb,

            created_at        TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),

            CONSTRAINT ck_events_event_type CHECK (
                event_type IN ('processing_error','out_of_scope')
            )
        );
        """
    )

    # Diagnostic index: "how much does the extractor hallucinate vs misroute?"
    # grouped by event_type + reason within a tenant.
    op.execute(
        """
        CREATE INDEX ix_events_diagnostic
            ON evidence_extraction_events (tenant_id, event_type, reason);
        """
    )
    op.execute(
        """
        CREATE INDEX ix_events_doc_run
            ON evidence_extraction_events (document_id, extraction_run_id);
        """
    )


def downgrade() -> None:
    """Drop the Evidence Intelligence shadow tables."""
    op.execute("DROP TABLE IF EXISTS evidence_extraction_events;")
    op.execute("DROP TABLE IF EXISTS evidence_claims;")
