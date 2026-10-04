"""
Bulk Review Alerts Use Case.

Line B review-integrity boundary: bulk actions are bounded and validated before
the first alert mutation so the endpoint cannot become a HITL bypass.
"""
from __future__ import annotations

from uuid import UUID

from src.alerts.application.dtos import BulkOperationResponse
from src.alerts.application.ports.alert_repository import IAlertRepository
from src.alerts.domain.enums import AlertSeverity


class BulkReviewPolicyError(ValueError):
    """Raised when a bulk review request would bypass review-integrity policy."""


class BulkReviewAlertsUseCase:
    MAX_BULK_APPROVALS = 5
    INDIVIDUAL_REVIEW_SEVERITIES = {
        AlertSeverity.HIGH,
        AlertSeverity.CRITICAL,
    }

    def __init__(self, repository: IAlertRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        alert_ids: list[str],
        tenant_id: UUID,
        user_id: UUID,
        decision: str,
        comment: str = "",
    ) -> BulkOperationResponse:
        """Apply one bounded review decision after policy prevalidation."""

        unique_ids = list(dict.fromkeys(alert_ids))
        normalized_comment = comment.strip()

        if decision == "approve" and len(unique_ids) > self.MAX_BULK_APPROVALS:
            raise BulkReviewPolicyError(
                f"Bulk approval maximum is {self.MAX_BULK_APPROVALS} alerts; "
                "larger selections require smaller reviewed batches."
            )
        if decision == "reject" and not normalized_comment:
            raise BulkReviewPolicyError(
                "Bulk rejection requires a non-empty audit reason."
            )

        alerts = []
        errors: list[str] = []
        for alert_id_str in unique_ids:
            try:
                alert_id = UUID(alert_id_str)
            except ValueError:
                errors.append(alert_id_str)
                continue

            alert = await self._repository.get_by_id(alert_id, tenant_id)
            if alert is None:
                errors.append(alert_id_str)
                continue
            alerts.append(alert)

        if decision == "approve":
            high_risk = [
                alert
                for alert in alerts
                if alert.severity in self.INDIVIDUAL_REVIEW_SEVERITIES
            ]
            if high_risk:
                raise BulkReviewPolicyError(
                    "High and critical alerts require individual review and "
                    "cannot be bulk approved."
                )

        for alert in alerts:
            alert.apply_review(user_id, decision, normalized_comment)
            alert.append_history("reviewed", user_id, decision=decision)
            await self._repository.save(alert, tenant_id)

        if alerts:
            await self._repository.commit()

        return BulkOperationResponse(
            processed_count=len(alerts),
            decision=decision,
            warning=f"{len(errors)} alerts not found" if errors else None,
            alert_ids=unique_ids,
        )
