"""
SQLAlchemy ORM model for Project.

This is the persistence adapter for the Project domain entity.
Maps domain concepts to database tables.
Refers to Test Suite IDs: TS-E2E-SEC-TNT-001, TS-UD-PROJ-001.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.json_types import JsonDict


def _utcnow_naive() -> datetime:
    """Return UTC now normalized to a naive timestamp for legacy TIMESTAMP columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class ProjectORM(Base):
    __tablename__ = "projects"

    # Primary identifiers
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

    # Basic information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # Project classification - using PostgreSQL enum types (native values)
    project_type: Mapped[str] = mapped_column(
        Enum(
            "construction", "engineering", "industrial", "infrastructure", "other",
            name="projecttype",
            create_type=False,
        ),
        nullable=False,
        default="construction",
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "draft", "active", "completed", "archived",
            name="projectstatus",
            create_type=False,
        ),
        nullable=False,
        default="draft",
        index=True,
    )

    # Financial
    estimated_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    # Timeline
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Analysis state
    coherence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_analysis_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Project metadata (flexible JSON storage)
    # Note: Column is named 'metadata_json' to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    metadata_json: Mapped[JsonDict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
    )

    @property
    def project_metadata(self) -> JsonDict:
        """Backward-compatible alias for the persisted metadata payload."""
        return self.metadata_json or {}

    @project_metadata.setter
    def project_metadata(self, value: JsonDict) -> None:
        self.metadata_json = value

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow_naive, onupdate=_utcnow_naive)

    # Relationships (intentionally omitted to avoid cross-module ORM coupling)
