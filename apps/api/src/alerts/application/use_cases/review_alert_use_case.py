"""
Review Alert Use Case.

Use case for reviewing (approve/reject) alerts.
Refers to Suite ID: TS-BUG-ALRT-IMPORT-001.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from src.alerts.application.dtos import AlertResponse
from src.alerts.application.mappers import AlertMapper
from src.alerts.application.ports.alert_repository import IAlertRepository
from src.alerts.domain.models import Alert

PreReviewHandler = Callable[[UUID, UUID, str], Awaitable[None]]
PostReviewHandler = Callable[[Alert, UUID, str], Awaitable[None]]


class AlertNotFoundError(Exception):
    """Raised when alert is not found."""
    pass


class ReviewAlertUseCase:
    def __init__(
        self,
        repository: IAlertRepository,
        pre_review_handler: PreReviewHandler | None = None,
        post_review_handler: PostReviewHandler | None = None,
    ) -> None:
        self._repository = repository
        self._pre_review_handler = pre_review_handler
        self._post_review_handler = post_review_handler

    async def execute(
        self,
        alert_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        decision: str,
        comment: str = "",
    ) -> AlertResponse:
        """Review an alert (approve or reject)."""
        if self._pre_review_handler is not None:
            await self._pre_review_handler(alert_id, tenant_id, decision)

        alert = await self._repository.get_by_id(alert_id, tenant_id)
        if not alert:
            raise AlertNotFoundError(f"Alert {alert_id} not found")

        alert.apply_review(user_id, decision, comment)
        alert.append_history("reviewed", user_id, decision=decision)

        await self._repository.save(alert)
        if self._post_review_handler is not None:
            await self._post_review_handler(alert, tenant_id, decision)
        await self._repository.commit()

        return AlertMapper.to_response(alert, tenant_id)
