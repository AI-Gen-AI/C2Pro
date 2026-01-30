from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.analysis.domain.enums import AlertSeverity, AlertStatus
from src.analysis.ports.alert_repository import AlertRepository
from src.analysis.ports.types import AlertRecord
from src.core.pagination import Page


class ListAlertsUseCase:
    def __init__(self, repository: AlertRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        *,
        project_id: UUID,
        severities: Optional[List[AlertSeverity]] = None,
        statuses: Optional[List[AlertStatus]] = None,
        category: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Page[AlertRecord]:
        return await self.repository.list_for_project(
            project_id=project_id,
            severities=severities,
            statuses=statuses,
            category=category,
            cursor=cursor,
            limit=limit,
        )


class GetAlertsStatsUseCase:
    def __init__(self, repository: AlertRepository) -> None:
        self.repository = repository

    async def execute(self, project_id: UUID) -> dict[str, int]:
        return await self.repository.get_stats(project_id)


class GetAlertUseCase:
    def __init__(self, repository: AlertRepository) -> None:
        self.repository = repository

    async def execute(self, alert_id: UUID) -> AlertRecord:
        alert = await self.repository.get_by_id(alert_id)
        if not alert:
            raise ValueError("alert_not_found")
        return alert


class UpdateAlertStatusUseCase:
    def __init__(self, repository: AlertRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        *,
        alert_id: UUID,
        status: AlertStatus,
        resolution_notes: str | None = None,
    ) -> AlertRecord:
        alert = await self.repository.get_by_id(alert_id)
        if not alert:
            raise ValueError("alert_not_found")

        if alert.status != AlertStatus.OPEN:
            raise ValueError(f"cannot_update_{alert.status.value}")

        if status not in {AlertStatus.RESOLVED, AlertStatus.DISMISSED, AlertStatus.ACKNOWLEDGED}:
            raise ValueError("invalid_status")

        alert.status = status

        if status in {AlertStatus.RESOLVED, AlertStatus.DISMISSED}:
            alert.resolved_at = datetime.utcnow()
            if resolution_notes:
                alert.resolution_notes = resolution_notes

        await self.repository.update(alert)
        await self.repository.commit()
        await self.repository.refresh(alert)
        return alert


class DeleteAlertUseCase:
    def __init__(self, repository: AlertRepository) -> None:
        self.repository = repository

    async def execute(self, alert_id: UUID) -> None:
        deleted = await self.repository.delete(alert_id)
        if not deleted:
            raise ValueError("alert_not_found")
        await self.repository.commit()
