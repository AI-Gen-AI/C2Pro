"""
I11 HITL Application Service
Test Suite ID: TS-I11-HITL-APP-001
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus, SLACheckResult
from src.modules.hitl.domain.services import ConfidenceRouter


class ReviewQueueRepository(ABC):
    @abstractmethod
    async def add_review_item(self, item: ReviewItem) -> UUID:
        raise NotImplementedError

    @abstractmethod
    async def get_review_item(self, item_id: UUID) -> ReviewItem | None:
        raise NotImplementedError

    @abstractmethod
    async def update_review_item(self, item: ReviewItem) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_overdue_items(self) -> list[ReviewItem]:
        raise NotImplementedError


class NotificationService(ABC):
    @abstractmethod
    async def send_notification(self, recipient_id: UUID, message: str, item: ReviewItem) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_escalation_alert(self, item: ReviewItem) -> None:
        raise NotImplementedError


class HumanInTheLoopService:
    """Enforces confidence gates, review routing, and SLA escalations."""

    def __init__(
        self,
        review_queue_repo: ReviewQueueRepository,
        notification_service: NotificationService,
        confidence_router: ConfidenceRouter,
    ):
        self.review_queue_repo = review_queue_repo
        self.notification_service = notification_service
        self.confidence_router = confidence_router

    async def route_for_review(
        self,
        item_id: UUID,
        item_type: str,
        confidence: float,
        impact_level: ImpactLevel,
        item_data: dict[str, Any],
    ) -> ReviewStatus:
        status = self.confidence_router.determine_review_status(confidence, impact_level)
        sla_due = datetime.now() + (timedelta(days=3) if status != ReviewStatus.APPROVED else timedelta(days=7))

        review_item = ReviewItem(
            item_id=item_id,
            item_type=item_type,
            current_status=status,
            confidence=confidence,
            impact_level=impact_level,
            created_at=datetime.now(),
            sla_due_date=sla_due,
            item_data=item_data,
        )
        await self.review_queue_repo.add_review_item(review_item)
        return status

    async def approve_item(self, item_id: UUID, reviewer_id: UUID, reviewer_name: str) -> ReviewItem:
        item = await self.review_queue_repo.get_review_item(item_id)
        if not item:
            raise ValueError(f"Review item with ID {item_id} not found.")

        if item.current_status not in {
            ReviewStatus.PENDING_REVIEW_REQUIRED,
            ReviewStatus.PENDING_REVIEW_CONDITIONAL,
        }:
            raise ValueError(f"Item {item_id} cannot be approved from status {item.current_status.value}.")

        item.current_status = ReviewStatus.APPROVED
        item.approved_by = reviewer_name
        item.approved_at = datetime.now()
        await self.review_queue_repo.update_review_item(item)
        return item

    async def check_and_escalate_slas(self) -> list[SLACheckResult]:
        overdue_items = await self.review_queue_repo.get_overdue_items()
        results: list[SLACheckResult] = []

        for item in overdue_items:
            item.current_status = ReviewStatus.ESCALATED
            await self.review_queue_repo.update_review_item(item)
            await self.notification_service.send_escalation_alert(item)
            results.append(
                SLACheckResult(
                    item_id=item.item_id,
                    is_overdue=True,
                    new_status=ReviewStatus.ESCALATED,
                    escalation_triggered=True,
                    message=f"SLA breached for item {item.item_id}. Escalation triggered.",
                )
            )

        return results

    async def release_item(self, item_id: UUID) -> ReviewItem:
        item = await self.review_queue_repo.get_review_item(item_id)
        if not item:
            raise ValueError(f"Review item with ID {item_id} not found.")
        if item.current_status != ReviewStatus.APPROVED:
            raise ValueError(f"Item {item_id} is not approved and cannot be released.")
        if not item.approved_by or not item.approved_at:
            raise ValueError("Approved item missing explicit reviewer information.")

        item.current_status = ReviewStatus.CLOSED
        await self.review_queue_repo.update_review_item(item)
        return item

