"""
SQLAlchemy implementation of the audit repository.

Refers to Suite ID: TS-INT-DB-AUD-001.
TASK-IMPL-002: Updated to use correct field names matching AuditLogORM model.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security.adapters.persistence.models import AuditLogORM
from src.core.security.audit_trail import AuditEvent


class SQLAlchemyAuditRepository:
    """Refers to Suite ID: TS-INT-DB-AUD-001."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _orm_to_domain(self, orm: AuditLogORM) -> AuditEvent:
        return AuditEvent(
            event_id=orm.id,
            tenant_id=str(orm.tenant_id),
            actor_id=str(orm.actor_id) if orm.actor_id else "system",
            action=orm.action,
            resource_type=orm.resource_type,
            resource_id=str(orm.resource_id) if orm.resource_id else "",
            timestamp=orm.timestamp or orm.created_at,
            metadata=orm.metadata_json or orm.changes or {},
            previous_hash=orm.previous_hash,
            event_hash=orm.event_hash or "",
        )

    async def create(self, event: AuditEvent) -> AuditEvent:
        try:
            actor_id = UUID(event.actor_id) if event.actor_id and event.actor_id != "system" else None
        except (ValueError, AttributeError):
            actor_id = None
        try:
            resource_id = UUID(event.resource_id) if event.resource_id else None
        except (ValueError, AttributeError):
            resource_id = None

        orm = AuditLogORM(
            id=event.event_id,
            tenant_id=UUID(event.tenant_id),
            actor_id=actor_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=resource_id,
            timestamp=event.timestamp,
            metadata_json=event.metadata or {},
            previous_hash=event.previous_hash,
            event_hash=event.event_hash or "",
        )
        self.session.add(orm)
        await self.session.flush()
        await self.session.refresh(orm)
        return self._orm_to_domain(orm)

    async def list_by_tenant(self, tenant_id: str | UUID) -> list[AuditEvent]:
        tenant_uuid = UUID(str(tenant_id)) if isinstance(tenant_id, str) else tenant_id
        result = await self.session.execute(
            select(AuditLogORM)
            .where(AuditLogORM.tenant_id == tenant_uuid)
            .order_by(AuditLogORM.timestamp)
        )
        return [self._orm_to_domain(orm) for orm in result.scalars().all()]
