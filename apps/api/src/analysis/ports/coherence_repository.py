from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Iterable
from uuid import UUID

class ICoherenceRepository(ABC):
    @abstractmethod
    async def list_documents_with_clauses(self, project_id: UUID) -> list[Any]:
        ...

    @abstractmethod
    async def persist_wbs_bom_items(
        self,
        project_id: UUID,
        wbs_items: list[dict],
        bom_items: list[dict],
    ) -> tuple[list[Any], list[Any]]:
        ...

    @abstractmethod
    async def save_analysis_and_alerts(
        self,
        project_id: UUID,
        started_at: datetime,
        coherence_score: float,
        alerts: Iterable[dict],
    ) -> None:
        ...
