"""V3 durable resume model: fenced operations, attempt ledger, provenance.

C2PRO P0b crash-safe HITL resume V3.

This is the ONLY durable resume model. An earlier `hitl_resume_operations`
design proved recovery but could not distinguish ATTEMPTS: a taken-over
operation reused one row, so a stale worker that woke up still matched the
operation and there was no way to tell which checkpoint descendants belonged
to which attempt. It was never released, so it is not migrated away from --
it is simply not created. This table provides:

* ``resume_operations`` -- one stable lifecycle row per EXACT review row
  (not per checkpoint: the operation outlives any single attempt).
* ``resume_operation_attempts`` -- an append-only ownership/decision ledger.
  Every takeover or decision change is a new, immutable attempt.
* A monotonic ``fencing_token``. Every durable writer re-verifies it inside
  its own persistence transaction, so a stale owner whose lease expired can
  still compute but can never write.
* ``decision_revision`` -- a changed decision before N17 supersedes prior
  attempts and their checkpoint descendants.
* Operation provenance on ``analyses`` and ``project_events`` so durable
  effects are keyed to the operation, with partial unique indexes that fence
  re-entry without touching historical rows.

Ownership timing uses ``clock_timestamp()`` at the call sites (never
application time, and never ``now()``, which is transaction-start time and
would make a long transaction look permanently fresh).

Revision ID: 20260923_0001
Revises: 20260914_0005
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from alembic import op

revision = "20260923_0001"
down_revision = "20260914_0005"
branch_labels = None
depends_on = None

_TENANT_PREDICATE = (
    "tenant_id = COALESCE("
    "NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id)"
)


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    for action, clause in (
        ("SELECT", "USING"),
        ("INSERT", "WITH CHECK"),
        ("UPDATE", "USING"),
        ("DELETE", "USING"),
    ):
        op.execute(
            f"CREATE POLICY tenant_isolation_{action.lower()} ON {table} "
            f"FOR {action} {clause} ({_TENANT_PREDICATE})"
        )


def upgrade() -> None:
    op.create_table(
        "resume_operations",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PGUUID(as_uuid=True), nullable=False, index=True),
        # Identity: the EXACT review row. item_id is a business key and is
        # NOT unique across legacy duplicates.
        sa.Column("review_row_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("project_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("document_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("thread_id", sa.String(512), nullable=True),
        # The IMMUTABLE human-interrupt checkpoint. The only checkpoint a new
        # attempt may ever restart from.
        sa.Column("source_checkpoint_id", sa.String(255), nullable=True),
        # Terminal checkpoint of the attempt that actually finished.
        sa.Column("terminal_checkpoint_id", sa.String(255), nullable=True),
        # Current ownership.
        sa.Column("current_attempt_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("owner_token", PGUUID(as_uuid=True), nullable=True),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("decision_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("decision", sa.String(32), nullable=True),
        sa.Column("decision_hash", sa.String(128), nullable=True),
        sa.Column("reviewer", sa.String(256), nullable=True),
        sa.Column("phase", sa.String(40), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        # Durable business outcome.
        sa.Column("analysis_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operation_metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # One lifecycle row per review row.
    op.create_index(
        "uq_resume_operations_review_row",
        "resume_operations",
        ["review_row_id"],
        unique=True,
    )
    # Reconciliation pages nonterminal operations by phase/schedule.
    op.create_index(
        "ix_resume_operations_phase_next_attempt",
        "resume_operations",
        ["phase", "next_attempt_at"],
    )
    _enable_rls("resume_operations")

    op.create_table(
        "resume_operation_attempts",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PGUUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "operation_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("resume_operations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_token", PGUUID(as_uuid=True), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column("decision_revision", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("decision_hash", sa.String(128), nullable=True),
        sa.Column("reviewer", sa.String(256), nullable=True),
        sa.Column("source_checkpoint_id", sa.String(255), nullable=True),
        sa.Column("terminal_checkpoint_id", sa.String(255), nullable=True),
        # ACTIVE | SUPERSEDED | ABANDONED | COMPLETED | FAILED
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    # The fence is monotonic per operation: two attempts can never share one.
    op.create_index(
        "uq_resume_attempts_operation_fence",
        "resume_operation_attempts",
        ["operation_id", "fencing_token"],
        unique=True,
    )
    _enable_rls("resume_operation_attempts")

    # -- durable effect provenance ------------------------------------------
    for column in (
        sa.Column("resume_operation_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("resume_attempt_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("fencing_token", sa.BigInteger(), nullable=True),
        sa.Column("decision_revision", sa.Integer(), nullable=True),
    ):
        op.add_column("analyses", column)

    # Operation-keyed: N17 re-entry finds the existing analysis instead of
    # persisting a second one. PARTIAL so every historical and non-HITL
    # analysis is untouched and legitimate re-analyses stay possible.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_analyses_resume_operation
        ON analyses (resume_operation_id)
        WHERE resume_operation_id IS NOT NULL
        """
    )

    op.add_column(
        "project_events",
        sa.Column("resume_operation_id", PGUUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "project_events",
        sa.Column("resume_attempt_id", PGUUID(as_uuid=True), nullable=True),
    )
    # Exactly one analysis.persisted and one graph.completed per operation.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_project_events_resume_operation_type
        ON project_events (resume_operation_id, event_type)
        WHERE resume_operation_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_project_events_resume_operation_type")
    op.drop_column("project_events", "resume_attempt_id")
    op.drop_column("project_events", "resume_operation_id")
    op.execute("DROP INDEX IF EXISTS uq_analyses_resume_operation")
    for name in (
        "decision_revision",
        "fencing_token",
        "resume_attempt_id",
        "resume_operation_id",
    ):
        op.drop_column("analyses", name)
    op.execute("ALTER TABLE resume_operation_attempts DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "uq_resume_attempts_operation_fence", table_name="resume_operation_attempts"
    )
    op.drop_table("resume_operation_attempts")
    op.execute("ALTER TABLE resume_operations DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_resume_operations_phase_next_attempt", table_name="resume_operations")
    op.drop_index("uq_resume_operations_review_row", table_name="resume_operations")
    op.drop_table("resume_operations")
