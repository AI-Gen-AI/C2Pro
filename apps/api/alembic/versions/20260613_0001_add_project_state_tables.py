"""Add ProjectState canonical tables (ADR-014 / TASK-V3-014-04).

Creates the project_states and project_state_entities tables for the
canonical project-intelligence aggregate. These are the permanent home
for all extracted intelligence (clauses, obligations, risks, WBS, budget,
stakeholders, RACI) at the project level.

Design:
  - One row per project in project_states
  - One row per canonical entity in project_state_entities (polymorphic,
    discriminated by entity_type)
  - tenant_id on both tables (denormalized on entities for RLS policies
    without requiring a join)
  - JSONB payload stores the full entity dict including evidence list
  - lifecycle_status governs visibility (active vs superseded)

Reserved doc_type enum values for Procurement Intelligence (Phase 3):
  rfq, quote, purchase_order, bid_tab — handled in a later migration.

Revision ID: 20260613_0001
Revises: 4f92ed11a27b
Create Date: 2026-06-13

Suite ID: TS-INT-ALEMBIC-PS-001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260613_0001"
down_revision: str = "4f92ed11a27b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create project_states and project_state_entities tables."""
    op.execute("SET LOCAL lock_timeout = '30s';")

    # ── project_states ────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE project_states (
            project_id            UUID PRIMARY KEY,
            tenant_id             UUID NOT NULL,
            lifecycle_status      VARCHAR(20) NOT NULL DEFAULT 'active',
            document_revision_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            procurement_refs      JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at            TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
            updated_at            TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),

            CONSTRAINT ck_project_states_lifecycle CHECK (
                lifecycle_status IN ('draft','active','superseded','archived')
            )
        );
        """
    )

    op.execute(
        "CREATE INDEX ix_project_states_tenant_id ON project_states (tenant_id);"
    )

    # ── project_state_entities ────────────────────────────────────
    op.execute(
        """
        CREATE TABLE project_state_entities (
            entity_id            UUID PRIMARY KEY,
            project_id           UUID NOT NULL
                                 REFERENCES project_states (project_id) ON DELETE CASCADE,
            tenant_id            UUID NOT NULL,
            entity_type          VARCHAR(40) NOT NULL,
            lifecycle_status     VARCHAR(20) NOT NULL DEFAULT 'active',
            source_revision_id   UUID,
            extraction_run_id    UUID,
            payload              JSONB NOT NULL,
            created_at           TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
            updated_at           TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),

            CONSTRAINT ck_pse_lifecycle CHECK (
                lifecycle_status IN ('draft','active','superseded','archived')
            ),
            CONSTRAINT ck_pse_entity_type CHECK (
                entity_type IN ('clause','obligation','risk','wbs_activity',
                                'budget_item','stakeholder','raci_cell')
            )
        );
        """
    )

    op.execute(
        "CREATE INDEX ix_pse_project_id ON project_state_entities (project_id);"
    )
    op.execute(
        "CREATE INDEX ix_pse_tenant_id ON project_state_entities (tenant_id);"
    )
    op.execute(
        """
        CREATE INDEX ix_pse_extraction_run
            ON project_state_entities (extraction_run_id)
            WHERE extraction_run_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    """Drop the ProjectState canonical tables."""
    op.execute("DROP TABLE IF EXISTS project_state_entities;")
    op.execute("DROP TABLE IF EXISTS project_states;")
