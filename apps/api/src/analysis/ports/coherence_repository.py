from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from src.core.json_types import JsonDict


class ICoherenceRepository(ABC):
    @abstractmethod
    async def list_documents_with_clauses(self, project_id: UUID) -> list[Any]:
        ...

    @abstractmethod
    async def save_analysis_and_alerts(
        self,
        project_id: UUID,
        started_at: datetime,
        coherence_score: float,
        alerts: Iterable[JsonDict],
    ) -> None:
        ...
