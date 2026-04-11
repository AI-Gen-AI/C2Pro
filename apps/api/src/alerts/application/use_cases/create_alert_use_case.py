"""
Create Alert Use Case.

Use case for creating new alerts with tenant isolation.
TASK-IMPL-003: Fixed tenant_id propagation to repository.
Refers to Suite ID: TS-E2E-FLW-JRN-001.
Refers to Suite ID: TS-BUG-ALRT-IMPORT-001.
"""
from __future__ import annotations

from uuid import UUID, uuid4

from src.alerts.application.ports.alert_repository import IAlertRepository
from src.alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from src.alerts.domain.models import Alert


class CreateAlertUseCase:
    def __init__(self, repository: IAlertRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        project_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        rule_code: str,
        category: str,
        severity: str,
        message: str,
        affected_entities: dict | None = None,
    ) -> Alert:
        """Create a new alert with tenant isolation."""
        alert = Alert(
            id=uuid4(),
            project_id=project_id,
            severity=AlertSeverity(severity.lower()),
            category=category,
            status=AlertStatus.OPEN,
            approval_status=ApprovalStatus.PENDING,
            rule_id=rule_code,
            title=message,
            description=message,
            affected_entities=affected_entities or {},
            alert_metadata={},
        )
        alert.append_history("created", user_id, rule_code=rule_code)

        await self._repository.create(alert, tenant_id=tenant_id)
        await self._repository.commit()
        return alert
