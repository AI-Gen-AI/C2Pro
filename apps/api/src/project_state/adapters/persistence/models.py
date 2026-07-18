"""SQLAlchemy ORM models for the ProjectState aggregate (ADR-014 / TASK-V3-014-03).

TS-UT-PS-ADP-001
"""
# ruff: noqa: E402  — _utcnow helper must be defined before SQLAlchemy models that use it as a default

from __future__ import annotations

from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.json_types import JsonDict


class ProjectStateORM(Base):
    __tablename__ = "project_states"

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    document_revision_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    procurement_refs: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        {"info": {"rls_policy": "tenant_isolation"}},
    )


class ProjectStateEntityORM(Base):
    __tablename__ = "project_state_entities"

    entity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_states.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    source_revision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    extraction_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    payload: Mapped[JsonDict] = mapped_column(
        JSONB, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        {"info": {"rls_policy": "tenant_isolation"}},
    )
