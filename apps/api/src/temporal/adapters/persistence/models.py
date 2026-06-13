"""SQLAlchemy ORM model for DocumentRevision (ADR-015 / TASK-V3-015-01)."""
# ruff: noqa: E402

from __future__ import annotations

from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class DocumentRevisionORM(Base):
    __tablename__ = "document_revisions"

    revision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    rev_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_revisions.revision_id", ondelete="SET NULL"),
        nullable=True,
    )
    blob_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    blob_key: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("document_id", "rev_no", name="uq_docrev_document_revno"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )
