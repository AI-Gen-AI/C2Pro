"""SQLAlchemy ORM models for temporal layer (ADR-015)."""
# ruff: noqa: E402

from __future__ import annotations

from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DDL,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class DocumentRevisionORM(Base):
    __tablename__ = "document_revisions"

    revision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    rev_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_revisions.revision_id", ondelete="SET NULL"),
        nullable=True,
    )
    blob_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    blob_key: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "rev_no", name="uq_docrev_document_revno"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )


class ProjectEventORM(Base):
    __tablename__ = "project_events"

    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    actor: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_revision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_revisions.revision_id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_project_events_project_occurred", "project_id", "occurred_at"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )


class ProjectSnapshotORM(Base):
    __tablename__ = "project_snapshots"

    snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    trigger: Mapped[str] = mapped_column(String(40), nullable=False)
    health_vector: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    coherence_subscore: Mapped[float | None] = mapped_column(Float, nullable=True)
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    totals: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    source_event_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_events.event_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "trigger IN ('revision_ingested','graph_completed','hitl_correction',"
            "'scheduled','baseline_changed')",
            name="ck_project_snapshots_trigger",
        ),
        Index("ix_project_snapshots_project_captured", "project_id", "captured_at"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )


_POLICY_USING = (
    "tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), "
    "'')::uuid, tenant_id)"
)


def _install_temporal_ddl(table: Any, table_name: str, prefix: str, block_delete: bool) -> None:
    operations = "UPDATE OR DELETE" if block_delete else "UPDATE"
    message = (
        "project_events is append-only" if block_delete else "project_snapshots is insert-only"
    )
    function_name = f"prevent_{table_name}_mutation"
    trigger_name = f"trg_{table_name}_immutable"

    statements = [
        f"""
        CREATE OR REPLACE FUNCTION {function_name}()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '{message}';
        END;
        $$ LANGUAGE plpgsql
        """,
        f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}",
        f"""
        CREATE TRIGGER {trigger_name}
        BEFORE {operations} ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION {function_name}()
        """,
        f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY",
    ]
    policy_specs = {
        "select": f"FOR SELECT USING ({_POLICY_USING})",
        "insert": f"FOR INSERT WITH CHECK ({_POLICY_USING})",
        "update": f"FOR UPDATE USING ({_POLICY_USING})",
        "delete": f"FOR DELETE USING ({_POLICY_USING})",
    }
    for suffix, clause in policy_specs.items():
        policy_name = f"{prefix}_{suffix}"
        statements.append(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE tablename = '{table_name}' AND policyname = '{policy_name}'
                ) THEN
                    CREATE POLICY {policy_name} ON {table_name} {clause};
                END IF;
            END $$;
            """
        )

    for statement in statements:
        event.listen(
            table,
            "after_create",
            DDL(statement).execute_if(dialect="postgresql"),
        )


_install_temporal_ddl(
    ProjectEventORM.__table__, "project_events", "project_events", block_delete=True
)
_install_temporal_ddl(
    ProjectSnapshotORM.__table__,
    "project_snapshots",
    "project_snapshots",
    block_delete=False,
)
