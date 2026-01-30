from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List, Optional
from uuid import UUID

from src.analysis.domain.enums import AlertSeverity, AlertStatus
from src.analysis.application.dtos import AlertCreate
from src.analysis.ports.types import AlertRecord
from src.core.pagination import Page


class AlertRepository(ABC):
    @abstractmethod
    async def list_for_project(
        self,
        project_id: UUID,
        severities: Optional[List[AlertSeverity]] = None,
        statuses: Optional[List[AlertStatus]] = None,
        category: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Page[AlertRecord]:
        ...

    @abstractmethod
    async def get_stats(self, project_id: UUID) -> dict[str, int]:
        ...

    @abstractmethod
    async def get_by_id(self, alert_id: UUID) -> AlertRecord | None:
        ...

    @abstractmethod
    async def create(self, payload: AlertCreate) -> AlertRecord:
        ...

    @abstractmethod
    async def update(self, alert: AlertRecord) -> None:
        ...

    @abstractmethod
    async def delete(self, alert_id: UUID) -> bool:
        ...

    @abstractmethod
    async def commit(self) -> None:
        ...

    @abstractmethod
    async def refresh(self, entity: object) -> None:
        ...
