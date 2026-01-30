from __future__ import annotations

from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Analysis, Alert
from src.analysis.ports.analysis_repository import IAnalysisRepository


class SqlAlchemyAnalysisRepository(IAnalysisRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_analysis(self, analysis: Analysis) -> None:
        self.session.add(analysis)

    async def add_alerts(self, alerts: Iterable[Alert]) -> None:
        self.session.add_all(list(alerts))

    async def list_recent(self, *, limit: int, offset: int) -> list[Analysis]:
        result = await self.session.execute(
            select(Analysis).order_by(Analysis.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count_all(self) -> int:
        total = await self.session.scalar(select(func.count(Analysis.id)))
        return int(total or 0)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
