from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable
from uuid import UUID

from src.analysis.ports.types import AnalysisRecord, AlertRecord


class IAnalysisRepository(ABC):
    @abstractmethod
    async def add_analysis(self, analysis: AnalysisRecord) -> None:
        ...

    @abstractmethod
    async def add_alerts(self, alerts: Iterable[AlertRecord]) -> None:
        ...

    @abstractmethod
    async def list_recent(self, *, limit: int, offset: int) -> list[AnalysisRecord]:
        ...

    @abstractmethod
    async def count_all(self) -> int:
        ...

    @abstractmethod
    async def commit(self) -> None:
        ...

    @abstractmethod
    async def flush(self) -> None:
        ...
