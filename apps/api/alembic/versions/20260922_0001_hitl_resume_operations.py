"""Durable HITL resume operations + N17 idempotency fence.

C2PRO P0b crash-safe HITL resume recovery.

Two durable structures, both required for crash consistency:

1. ``hitl_resume_operations`` -- the durable state machine for one resume of
   one review row at one checkpoint. The previous design kept an opaque
   ``resume_claim`` blob in review_items.review_metadata, which could be
   orphaned forever by a hard process death (no lease, no phase, no
   recovery evidence). This table records the phase, a renewable lease and
   -- critically -- the durable completion identity, so a retry can tell
   "the graph already crossed N17 for THIS operation" apart from "the graph
   never ran", without replaying N17.

2. ``analyses.idempotency_key`` + a PARTIAL unique index. This is the only
   thing that makes N17 genuinely idempotent across a crash in the window
   between the analysis commit and the phase transition that records it.
   The index is partial (WHERE idempotency_key IS NOT NULL) so every
   pre-existing analysis and every non-HITL analysis path is unaffected and
   legitimate re-analyses/revisions stay possible -- a unique constraint on
   project_id would have wrongly forbidden those.

Revision ID: 20260922_0001
Revises: 20260914_0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "20260922_0001"
down_revision = "20260914_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hitl_resume_operations",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PGUUID(as_uuid=True), nullable=False, index=True),
        # The EXACT review row (primary key), never the business item_id --
        # item_id is not unique across legacy duplicates.
        sa.Column("review_row_id", PGUUID(as_uuid=True), nullable=False),
        # '' rather than NULL when a resume legitimately falls back to the
        # thread's latest checkpoint: NULLs are distinct in a UNIQUE index,
        # which would silently permit duplicate operations.
        sa.Column("checkpoint_key", sa.String(255), nullable=False, server_default=""),
        sa.Column("thread_id", sa.String(512), nullable=True),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("token", PGUUID(as_uuid=True), nullable=False),
        # Durable completion identity: which analysis THIS operation produced.
        sa.Column("analysis_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("operation_metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("claimed_at", sa.DateTime(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    # One operation per (review row, checkpoint). A retry after a crash finds
    # this row rather than starting a second, competing operation.
    op.create_index(
        "uq_hitl_resume_operations_row_checkpoint",
        "hitl_resume_operations",
        ["review_row_id", "checkpoint_key"],
        unique=True,
    )
    op.create_index(
        "ix_hitl_resume_operations_phase",
        "hitl_resume_operations",
        ["phase"],
    )

    op.execute("ALTER TABLE hitl_resume_operations ENABLE ROW LEVEL SECURITY")
    for action, clause in (
        ("SELECT", "USING"),
        ("INSERT", "WITH CHECK"),
        ("UPDATE", "USING"),
        ("DELETE", "USING"),
    ):
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{action.lower()} ON hitl_resume_operations
            FOR {action}
            {clause} (
                tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    tenant_id
                )
            )
            """
        )

    op.add_column(
        "analyses",
        sa.Column("idempotency_key", sa.String(255), nullable=True),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_analyses_idempotency_key
        ON analyses (idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_analyses_idempotency_key")
    op.drop_column("analyses", "idempotency_key")
    op.execute("ALTER TABLE hitl_resume_operations DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_hitl_resume_operations_phase", table_name="hitl_resume_operations")
    op.drop_index(
        "uq_hitl_resume_operations_row_checkpoint", table_name="hitl_resume_operations"
    )
    op.drop_table("hitl_resume_operations")
