from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any
from uuid import UUID

from src.analysis.ports.types import AlertWrite, AnalysisRecord, AnalysisWrite


class IAnalysisRepository(ABC):
    @abstractmethod
    async def add_analysis(self, analysis: AnalysisWrite, tenant_id: UUID | None = None) -> None:
        ...

    @abstractmethod
    async def add_alerts(self, alerts: Iterable[AlertWrite], tenant_id: UUID | None = None) -> None:
        ...

    @abstractmethod
    async def get_result_json(
        self, analysis_id: UUID, tenant_id: UUID
    ) -> dict[str, Any] | None:
        """Exact tenant-scoped read of one analysis' ``result_json``.

        Returns ``None`` when the analysis does not exist for this tenant. A returned
        mapping without the versioned assessment key means the analysis predates L4-3
        (UNAVAILABLE), never "evaluated and empty".
        """
        ...

    @abstractmethod
    async def list_recent(
        self, *, limit: int, offset: int, tenant_id: UUID | None = None
    ) -> list[AnalysisRecord]:
        ...

    @abstractmethod
    async def count_all(self, tenant_id: UUID | None = None) -> int:
        ...

    @abstractmethod
    async def commit(self) -> None:
        ...

    @abstractmethod
    async def flush(self) -> None:
        ...
