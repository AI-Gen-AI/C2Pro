"""SqlAlchemyProjectSnapshotRepository (ADR-015 / TASK-V3-015-04).

LOCKED INVARIANT: NEVER call session commit(). The use case owns the transaction.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tenants.types import TenantId
from src.temporal.adapters.persistence.models import ProjectSnapshotORM
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger
from src.temporal.ports.project_snapshot_repository import IProjectSnapshotRepository


class SqlAlchemyProjectSnapshotRepository(IProjectSnapshotRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(orm: ProjectSnapshotORM) -> ProjectSnapshot:
        return ProjectSnapshot(
            snapshot_id=orm.snapshot_id,
            project_id=orm.project_id,
            tenant_id=orm.tenant_id,
            captured_at=orm.captured_at,
            trigger=SnapshotTrigger(orm.trigger),
            health_vector=orm.health_vector,
            coherence_subscore=orm.coherence_subscore,
            counts=orm.counts,
            totals=orm.totals,
            source_event_id=orm.source_event_id,
            created_at=orm.created_at,
        )

    async def append_snapshot(self, snapshot: ProjectSnapshot) -> ProjectSnapshot:
        self._session.add(
            ProjectSnapshotORM(
                snapshot_id=snapshot.snapshot_id,
                project_id=snapshot.project_id,
                tenant_id=snapshot.tenant_id,
                captured_at=snapshot.captured_at,
                trigger=snapshot.trigger.value,
                health_vector=snapshot.health_vector,
                coherence_subscore=snapshot.coherence_subscore,
                counts=snapshot.counts,
                totals=snapshot.totals,
                source_event_id=snapshot.source_event_id,
                created_at=snapshot.created_at,
            )
        )
        await self._session.flush()
        return snapshot

    async def latest(self, project_id: UUID, tenant_id: TenantId) -> ProjectSnapshot | None:
        result = await self._session.execute(
            select(ProjectSnapshotORM)
            .where(
                ProjectSnapshotORM.project_id == project_id,
                ProjectSnapshotORM.tenant_id == tenant_id,
            )
            .order_by(ProjectSnapshotORM.captured_at.desc())
            .limit(1)
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def list_since(
        self, project_id: UUID, tenant_id: TenantId, since: datetime
    ) -> list[ProjectSnapshot]:
        result = await self._session.execute(
            select(ProjectSnapshotORM)
            .where(
                ProjectSnapshotORM.project_id == project_id,
                ProjectSnapshotORM.tenant_id == tenant_id,
                ProjectSnapshotORM.captured_at >= since,
            )
            .order_by(ProjectSnapshotORM.captured_at.asc())
        )
        return [self._to_domain(orm) for orm in result.scalars().all()]
