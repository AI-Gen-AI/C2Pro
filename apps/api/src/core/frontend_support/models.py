"""
Frontend support persistence models.

CookieConsentORM  — GDPR cookie consent records (TASK-REV-020).
DisclaimerAcceptanceORM — HITL gate-8 disclaimer acceptances (SEC-014).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class CookieConsentORM(Base):
    """
    Cookie consent persistence model.

    Stores consent records for GDPR compliance tracking.
    Composite unique constraint on (tenant_id, user_id, version) ensures
    one consent record per version per user.
    """

    __tablename__ = "cookie_consents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "version", name="uq_cookie_consent_user_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    version: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    categories: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return f"<CookieConsent tenant={self.tenant_id} user={self.user_id} version={self.version}>"


class DisclaimerAcceptanceORM(Base):
    """
    Gate-8 legal disclaimer acceptance.

    One record per (tenant, user, project, version) — persisted so acceptance
    survives pod restarts and multi-replica deployments.
    """

    __tablename__ = "disclaimer_acceptances"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "user_id", "project_id", "version",
            name="uq_disclaimer_acceptance",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return (
            f"<DisclaimerAcceptance tenant={self.tenant_id} user={self.user_id}"
            f" project={self.project_id} version={self.version}>"
        )
