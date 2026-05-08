from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class AuditLogORM(Base):
    """
    Audit persistence models.
    Refers to Suite ID: TS-INT-DB-AUD-001.

    TASK-IMPL-002: Added actor_id, event_hash, previous_hash, timestamp, metadata_json
    to match SQLAlchemyAuditRepository expectations.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    changes: Mapped[dict] = mapped_column(JSONB, default=dict)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self):
        return f"<AuditLog {self.id} action={self.action} resource={self.resource_type}>"

    __table_args__ = (
        {"info": {"rls_policy": "tenant_isolation"}},
    )

