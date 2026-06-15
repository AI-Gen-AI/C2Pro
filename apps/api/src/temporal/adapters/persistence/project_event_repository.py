"""SqlAlchemyProjectEventRepository (ADR-015 / TASK-V3-015-03).

LOCKED INVARIANT: NEVER call session commit(). The use case owns the transaction.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence.models import ProjectEventORM
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.ports.project_event_repository import IProjectEventRepository


class SqlAlchemyProjectEventRepository(IProjectEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(orm: ProjectEventORM) -> ProjectEvent:
        return ProjectEvent(
            event_id=orm.event_id,
            project_id=orm.project_id,
            tenant_id=orm.tenant_id,
            event_type=orm.event_type,
            payload=orm.payload,
            actor=orm.actor,
            confidence=orm.confidence,
            source_revision_id=orm.source_revision_id,
            evidence_refs=orm.evidence_refs,
            occurred_at=orm.occurred_at,
            created_at=orm.created_at,
        )

    async def append(self, event: ProjectEvent) -> ProjectEvent:
        self._session.add(
            ProjectEventORM(
                event_id=event.event_id,
                project_id=event.project_id,
                tenant_id=event.tenant_id,
                event_type=event.event_type,
                payload=event.payload,
                actor=event.actor,
                confidence=event.confidence,
                source_revision_id=event.source_revision_id,
                evidence_refs=[ref.model_dump(mode="json") for ref in event.evidence_refs],
                occurred_at=event.occurred_at,
                created_at=event.created_at,
            )
        )
        await self._session.flush()
        return event

    async def list_for_project(
        self,
        project_id: UUID,
        tenant_id: UUID,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[ProjectEvent]:
        stmt = (
            select(ProjectEventORM)
            .where(
                ProjectEventORM.project_id == project_id,
                ProjectEventORM.tenant_id == tenant_id,
            )
            .order_by(ProjectEventORM.occurred_at.asc())
        )
        if since is not None:
            stmt = stmt.where(ProjectEventORM.occurred_at >= since)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return [self._to_domain(orm) for orm in result.scalars().all()]
