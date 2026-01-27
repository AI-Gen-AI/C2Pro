from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable
from uuid import UUID

from src.documents.adapters.persistence.models import DocumentORM
from src.procurement.adapters.persistence.models import BOMItemORM, WBSItemORM


class ICoherenceRepository(ABC):
    @abstractmethod
    async def list_documents_with_clauses(self, project_id: UUID) -> list[DocumentORM]:
        ...

    @abstractmethod
    async def persist_wbs_bom_items(
        self,
        project_id: UUID,
        wbs_items: list[dict],
        bom_items: list[dict],
    ) -> tuple[list[WBSItemORM], list[BOMItemORM]]:
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
