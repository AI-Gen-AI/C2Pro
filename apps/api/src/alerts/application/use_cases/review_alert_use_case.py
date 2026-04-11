"""
Review Alert Use Case.

Use case for reviewing (approve/reject) alerts.
Refers to Suite ID: TS-BUG-ALRT-IMPORT-001.
"""
from __future__ import annotations

from uuid import UUID

from src.alerts.application.dtos import AlertResponse
from src.alerts.application.mappers import AlertMapper
from src.alerts.application.ports.alert_repository import IAlertRepository


class AlertNotFoundError(Exception):
    """Raised when alert is not found."""
    pass


class ReviewAlertUseCase:
    def __init__(self, repository: IAlertRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        alert_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        decision: str,
        comment: str = "",
    ) -> AlertResponse:
        """Review an alert (approve or reject)."""
        alert = await self._repository.get_by_id(alert_id, tenant_id)
        if not alert:
            raise AlertNotFoundError(f"Alert {alert_id} not found")

        alert.apply_review(user_id, decision, comment)
        alert.append_history("reviewed", user_id, decision=decision)

        await self._repository.save(alert)
        await self._repository.commit()

        return AlertMapper.to_response(alert, tenant_id)
