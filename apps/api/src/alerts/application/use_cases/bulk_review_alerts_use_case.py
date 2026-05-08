"""
Bulk Review Alerts Use Case.
"""
from __future__ import annotations

from uuid import UUID

from src.alerts.application.dtos import BulkOperationResponse
from src.alerts.application.use_cases.review_alert_use_case import (
    AlertNotFoundError,
    ReviewAlertUseCase,
)


class BulkReviewAlertsUseCase:
    def __init__(self, review_use_case: ReviewAlertUseCase) -> None:
        self._review_use_case = review_use_case

    async def execute(
        self,
        alert_ids: list[str],
        tenant_id: UUID,
        user_id: UUID,
        decision: str,
        comment: str = "",
    ) -> BulkOperationResponse:
        """Bulk approve/reject alerts."""
        processed = 0
        errors = []
        for alert_id_str in alert_ids:
            try:
                alert_id = UUID(alert_id_str)
                await self._review_use_case.execute(
                    alert_id=alert_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    decision=decision,
                    comment=comment,
                )
                processed += 1
            except (AlertNotFoundError, ValueError):
                errors.append(alert_id_str)

        return BulkOperationResponse(
            processed_count=processed,
            decision=decision,
            warning=f"{len(errors)} alerts not found" if errors else None,
            alert_ids=alert_ids
        )
