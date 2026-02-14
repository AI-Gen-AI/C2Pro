from __future__ import annotations

from typing import Iterable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Analysis, Alert
from src.analysis.ports.analysis_repository import IAnalysisRepository
from src.projects.adapters.persistence.models import ProjectORM


class SqlAlchemyAnalysisRepository(IAnalysisRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_analysis(self, analysis: Analysis) -> None:
        self.session.add(analysis)

    async def add_alerts(self, alerts: Iterable[Alert]) -> None:
        self.session.add_all(list(alerts))

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
