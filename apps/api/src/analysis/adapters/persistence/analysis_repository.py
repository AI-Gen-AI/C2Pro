from __future__ import annotations

from typing import Iterable

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

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
