"""
SQLAlchemy ORM models for Stakeholder bounded context, used by the persistence adapter.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.approval import ApprovalStatus # Assuming this is a global enum

# Import enums from our domain models
from src.stakeholders.domain.models import PowerLevel, InterestLevel, StakeholderQuadrant, RACIRole

# TYPE_CHECKING imports need to be adjusted for the new module structure
if TYPE_CHECKING:
    from src.core.auth.models import User


class StakeholderORM(Base):
    """
    SQLAlchemy model for Stakeholder.
    """

    __tablename__ = "stakeholders"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Project relationship
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identification
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Classification
    power_level: Mapped[PowerLevel] = mapped_column(SQLEnum(PowerLevel), default=PowerLevel.MEDIUM)
    interest_level: Mapped[InterestLevel] = mapped_column(
        SQLEnum(InterestLevel), default=InterestLevel.MEDIUM
    )
    quadrant: Mapped[StakeholderQuadrant | None] = mapped_column(
        SQLEnum(StakeholderQuadrant), nullable=True
    )

    # Contact
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Traceability
    source_clause_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clauses.id"),
        nullable=True,
        index=True,
    )
    extracted_from_document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )

    # Approval workflow
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        SQLEnum(ApprovalStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=ApprovalStatus.PENDING,
        index=True,
        nullable=False,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stakeholder Metadata (custom data)
    stakeholder_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    reviewer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[reviewed_by],
        lazy="select",
    )

    raci_assignments: Mapped[list["StakeholderWBSRaciORM"]] = relationship(
        "StakeholderWBSRaciORM",
        back_populates="stakeholder",
        lazy="select",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_stakeholders_project", "project_id"),
        Index("ix_stakeholders_quadrant", "quadrant"),
        Index("ix_stakeholders_clause", "source_clause_id"),
        Index("ix_stakeholders_email", "email"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )


class StakeholderWBSRaciORM(Base):
    """
    SQLAlchemy model for RACI Matrix assignment.
    """

    __tablename__ = "stakeholder_wbs_raci"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Relationships
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stakeholder_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stakeholders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    wbs_item_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wbs_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # RACI Role
    raci_role: Mapped[RACIRole] = mapped_column(SQLEnum(RACIRole), nullable=False, index=True)

    # Evidence
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    generated_automatically: Mapped[bool] = mapped_column(Boolean, default=True)
    manually_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    stakeholder: Mapped["StakeholderORM"] = relationship(
        "StakeholderORM", back_populates="raci_assignments", lazy="selectin"
    )

    verifier: Mapped["User"] = relationship("User", foreign_keys=[verified_by], lazy="select")

    # Indexes
    __table_args__ = (
        Index("ix_raci_stakeholder", "stakeholder_id"),
        Index("ix_raci_wbs", "wbs_item_id"),
        Index("ix_raci_role", "raci_role"),
        {"info": {"rls_policy": "tenant_isolation"}},
    )
