from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable
from uuid import UUID

from src.analysis.adapters.persistence.models import Analysis, Alert


class IAnalysisRepository(ABC):
    @abstractmethod
    async def add_analysis(self, analysis: Analysis) -> None:
        ...

    @abstractmethod
    async def add_alerts(self, alerts: Iterable[Alert]) -> None:
        ...

    @abstractmethod
    async def commit(self) -> None:
        ...

    @abstractmethod
    async def flush(self) -> None:
        ...
