"""
Bulk Resolve Alerts Use Case.
"""
from __future__ import annotations

from uuid import UUID

from src.alerts.application.dtos import BulkOperationResponse
from src.alerts.application.use_cases.resolve_alert_use_case import (
    AlertNotFoundError,
    ResolveAlertUseCase,
)


class BulkResolveAlertsUseCase:
    def __init__(self, resolve_use_case: ResolveAlertUseCase) -> None:
        self._resolve_use_case = resolve_use_case

    async def execute(
        self,
        alert_ids: list[str],
        tenant_id: UUID,
        user_id: UUID,
        resolution: str,
        root_cause: str | None = None,
    ) -> BulkOperationResponse:
        """Bulk resolve alerts."""
        processed = 0
        errors = []
        for alert_id_str in alert_ids:
            try:
                alert_id = UUID(alert_id_str)
                await self._resolve_use_case.execute(
                    alert_id=alert_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    resolution=resolution,
                    root_cause=root_cause,
                )
                processed += 1
            except (AlertNotFoundError, ValueError):
                errors.append(alert_id_str)

        return BulkOperationResponse(
            processed_count=processed,
            status="resolved",
            warning=f"{len(errors)} alerts not found" if errors else None,
            alert_ids=alert_ids
        )
