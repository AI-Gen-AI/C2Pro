"""
I11 HITL application service implementation.
Test Suite ID: TS-I11-HITL-APP-001
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from src.modules.hitl.domain.entities import (
    ImpactLevel,
    ReviewItem,
    ReviewStatus,
    SLACheckResult,
)
from src.modules.hitl.domain.services import ConfidenceRouter
from src.modules.hitl.ports.notification_service import INotificationService
from src.modules.hitl.ports.review_queue_repository import IReviewQueueRepository


class HumanInTheLoopService:
    """Enforces confidence gates, review routing, and SLA escalations."""

    _ERR_NOT_FOUND = "Review item with ID {item_id} not found."
    _ERR_REQUIRES_HUMAN_APPROVAL = "requires human approval"
    _ERR_TENANT_MISMATCH = "tenant mismatch"

    def __init__(
        self,
        review_queue_repo: IReviewQueueRepository,
        notification_service: INotificationService,
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
        status = self.confidence_router.determine_review_status(
            confidence, impact_level
        )
        sla_due = datetime.now() + (
            timedelta(days=3)
            if status != ReviewStatus.APPROVED
            else timedelta(days=7)
        )

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

    async def approve_item(
        self, item_id: UUID, reviewer_id: UUID, reviewer_name: str
    ) -> ReviewItem:
        _ = reviewer_id
        item = await self.review_queue_repo.get_review_item(item_id)
        if not item:
            raise ValueError(self._ERR_NOT_FOUND.format(item_id=item_id))

        if item.current_status not in {
            ReviewStatus.PENDING_REVIEW_REQUIRED,
            ReviewStatus.PENDING_REVIEW_CONDITIONAL,
        }:
            raise ValueError(
                f"Item {item_id} cannot be approved from status {item.current_status.value}."
            )

        item.current_status = ReviewStatus.APPROVED
        item.approved_by = reviewer_name
        item.approved_at = datetime.now()
        await self.review_queue_repo.update_review_item(item)
        return item

    async def check_and_escalate_slas(self) -> list[SLACheckResult]:
        overdue_items = await self.review_queue_repo.get_overdue_items()
        results: list[SLACheckResult] = []

        for item in overdue_items:
            if item.current_status == ReviewStatus.ESCALATED:
                continue
            item.current_status = ReviewStatus.ESCALATED
            item.metadata["escalated_at"] = datetime.now().isoformat()
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

    async def release_item(
        self,
        item_id: UUID,
        reviewer_tenant_id: UUID | None = None,
    ) -> ReviewItem:
        item = await self.review_queue_repo.get_review_item(item_id)
        if not item:
            raise ValueError(self._ERR_NOT_FOUND.format(item_id=item_id))
        if reviewer_tenant_id is not None:
            item_tenant = item.metadata.get("tenant_id")
            if isinstance(item_tenant, str) and item_tenant != str(reviewer_tenant_id):
                raise ValueError(self._ERR_TENANT_MISMATCH)
        if item.current_status != ReviewStatus.APPROVED:
            raise ValueError(self._ERR_REQUIRES_HUMAN_APPROVAL)
        if not item.approved_by or not item.approved_at:
            raise ValueError("Approved item missing explicit reviewer information.")

        item.current_status = ReviewStatus.CLOSED
        await self.review_queue_repo.update_review_item(item)
        return item
