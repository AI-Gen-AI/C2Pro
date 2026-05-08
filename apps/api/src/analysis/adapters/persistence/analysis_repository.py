from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert, Analysis
from src.analysis.ports.analysis_repository import IAnalysisRepository
from src.projects.adapters.persistence.models import ProjectORM


class SqlAlchemyAnalysisRepository(IAnalysisRepository):
    def __init__(self, session: AsyncSession, tenant_id: UUID | None = None):
        self.session = session
        self.tenant_id = tenant_id

    async def _verify_project_ownership(self, project_id: UUID) -> bool:
        """Verify that a project belongs to the current tenant."""
        stmt = select(ProjectORM.tenant_id).where(ProjectORM.id == project_id)
        result = await self.session.execute(stmt)
        project_tenant = result.scalar_one_or_none()
        if project_tenant is None:
            return False
        if self.tenant_id is None:
            return True
        return project_tenant == self.tenant_id

    async def add_analysis(self, analysis: Analysis, tenant_id: UUID | None = None) -> None:
        effective_tenant_id = tenant_id or self.tenant_id
        if effective_tenant_id is not None:  # noqa: SIM102
            if not await self._verify_project_ownership(analysis.project_id):
                raise PermissionError("Cannot add analysis for project outside tenant")
        self.session.add(analysis)

    async def add_alerts(self, alerts: Iterable[Alert], tenant_id: UUID | None = None) -> None:
        effective_tenant_id = tenant_id or self.tenant_id
        alert_list = list(alerts)
        for alert in alert_list:
            if effective_tenant_id is not None:  # noqa: SIM102
                if not await self._verify_project_ownership(alert.project_id):
                    raise PermissionError("Cannot add alert for project outside tenant")
        self.session.add_all(alert_list)

    async def list_recent(
        self, *, limit: int, offset: int, tenant_id: UUID | None = None
    ) -> list[Analysis]:
        query = select(Analysis)
        if tenant_id is not None:
            query = query.join(ProjectORM, ProjectORM.id == Analysis.project_id).where(
                ProjectORM.tenant_id == tenant_id
            )
        result = await self.session.execute(
            query.order_by(Analysis.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count_all(self, tenant_id: UUID | None = None) -> int:
        query = select(func.count(Analysis.id))
        if tenant_id is not None:
            query = query.join(ProjectORM, ProjectORM.id == Analysis.project_id).where(
                ProjectORM.tenant_id == tenant_id
            )
        total = await self.session.scalar(query)
        return int(total or 0)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
