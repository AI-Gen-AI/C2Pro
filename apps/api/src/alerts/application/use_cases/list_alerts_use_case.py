"""
List Alerts Use Case.

Use case for listing alerts with tenant isolation.
TASK-IMPL-004: Fixed copy-paste bug where severity was used instead of status.
Refers to Suite ID: TS-BUG-ALRT-IMPORT-001.
"""
from __future__ import annotations

from uuid import UUID

from src.alerts.application.dtos import AlertListResponse
from src.alerts.application.mappers import AlertMapper
from src.alerts.application.ports.alert_repository import IAlertRepository
from src.alerts.domain.enums import AlertSeverity, AlertStatus


class ListAlertsUseCase:
    def __init__(self, repository: IAlertRepository) -> None:
        self._repository = repository

    async def execute_for_project(
        self,
        project_id: UUID,
        tenant_id: UUID,
        status: str | None = None,
        category: str | None = None,
        severity: str | None = None,
    ) -> AlertListResponse:
        """List alerts for a specific project."""
        try:
            status_enum = AlertStatus(status) if status else None
        except ValueError:
            status_enum = None

        try:
            severity_enum = AlertSeverity(severity) if severity else None
        except ValueError:
            severity_enum = None

        alerts = await self._repository.list_for_project(
            project_id=project_id,
            tenant_id=tenant_id,
            status=status_enum,
            category=category,
            severity=severity_enum,
        )
        return AlertListResponse(
            items=AlertMapper.to_response_list(alerts, tenant_id),
            total=len(alerts),
        )

    async def execute_for_tenant(
        self,
        tenant_id: UUID,
        project_id: UUID | None = None,
        document_id: UUID | None = None,
        status: str | None = None,
        category: str | None = None,
        severity: str | None = None,
    ) -> AlertListResponse:
        """List alerts for a tenant with optional filters."""
        try:
            status_enum = AlertStatus(status) if status else None
        except ValueError:
            status_enum = None

        try:
            severity_enum = AlertSeverity(severity) if severity else None
        except ValueError:
            severity_enum = None

        alerts = await self._repository.list_for_tenant(
            tenant_id=tenant_id,
            project_id=project_id,
            document_id=document_id,
            status=status_enum,
            category=category,
            severity=severity_enum,
        )
        return AlertListResponse(
            items=AlertMapper.to_response_list(alerts, tenant_id),
            total=len(alerts),
        )
