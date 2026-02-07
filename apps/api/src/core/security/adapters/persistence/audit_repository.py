"""
SQLAlchemy implementation of the audit repository.

Refers to Suite ID: TS-INT-DB-AUD-001.
"""

from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security.audit_trail import AuditEvent
from src.core.security.adapters.persistence.models import AuditLogORM


class SQLAlchemyAuditRepository:
    """Refers to Suite ID: TS-INT-DB-AUD-001."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _orm_to_domain(self, orm: AuditLogORM) -> AuditEvent:
        return AuditEvent(
            event_id=orm.id,
            tenant_id=orm.tenant_id,
            actor_id=orm.actor_id,
            action=orm.action,
            resource_type=orm.resource_type,
            resource_id=orm.resource_id,
            timestamp=orm.timestamp,
            metadata=orm.metadata_json or {},
            previous_hash=orm.previous_hash,
            event_hash=orm.event_hash,
        )

    async def create(self, event: AuditEvent) -> AuditEvent:
        orm = AuditLogORM(
            id=event.event_id,
            tenant_id=event.tenant_id,
            actor_id=event.actor_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            timestamp=event.timestamp,
            metadata_json=event.metadata or {},
            previous_hash=event.previous_hash,
            event_hash=event.event_hash,
        )
        self.session.add(orm)
        await self.session.flush()
        await self.session.refresh(orm)
        return self._orm_to_domain(orm)

    async def list_by_tenant(self, tenant_id: str) -> List[AuditEvent]:
        result = await self.session.execute(
            select(AuditLogORM)
            .where(AuditLogORM.tenant_id == tenant_id)
            .order_by(AuditLogORM.timestamp)
        )
        return [self._orm_to_domain(orm) for orm in result.scalars().all()]
