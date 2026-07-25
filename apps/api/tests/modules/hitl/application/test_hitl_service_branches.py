"""
Branch coverage tests for HumanInTheLoopService error paths.

Test Suite: TS-I11-HITL-APP-001
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.hitl.application.human_in_the_loop_service import (
    HumanInTheLoopService,
)
from src.modules.hitl.domain.entities import (
    ImpactLevel,
    ReviewItem,
    ReviewStatus,
)
from src.modules.hitl.domain.services import ConfidenceRouter
from src.modules.hitl.ports.notification_service import INotificationService
from src.modules.hitl.ports.review_queue_repository import IReviewQueueRepository


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock(spec=IReviewQueueRepository)
    return repo


@pytest.fixture
def mock_notification() -> AsyncMock:
    svc = AsyncMock(spec=INotificationService)
    return svc


@pytest.fixture
def hitl_service(mock_repo: AsyncMock, mock_notification: AsyncMock) -> HumanInTheLoopService:
    return HumanInTheLoopService(
        review_queue_repo=mock_repo,
        notification_service=mock_notification,
        confidence_router=ConfidenceRouter(
            low_confidence_threshold=0.3,
            high_confidence_threshold=0.8,
        ),
    )


@pytest.mark.asyncio
class TestApproveItemBranches:
    async def test_approve_item_not_found_raises(
        self,
        hitl_service: HumanInTheLoopService,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_review_item.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await hitl_service.approve_item(
                item_id=uuid4(),
                reviewer_id=uuid4(),
                reviewer_name="reviewer",
            )

    async def test_approve_item_wrong_status_raises(
        self,
        hitl_service: HumanInTheLoopService,
        mock_repo: AsyncMock,
    ) -> None:
        item = ReviewItem(
            item_id=uuid4(),
            item_type="CoherenceAlert",
            current_status=ReviewStatus.CLOSED,
            confidence=0.5,
            impact_level=ImpactLevel.LOW,
            created_at=datetime.now(),
            sla_due_date=datetime.now() + timedelta(days=1),
            item_data={},
        )
        mock_repo.get_review_item.return_value = item

        with pytest.raises(ValueError, match="cannot be approved"):
            await hitl_service.approve_item(
                item_id=item.item_id,
                reviewer_id=uuid4(),
                reviewer_name="reviewer",
            )


@pytest.mark.asyncio
class TestReleaseItemBranches:
    async def test_release_item_not_found_raises(
        self,
        hitl_service: HumanInTheLoopService,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_review_item.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await hitl_service.release_item(item_id=uuid4())

    async def test_release_item_wrong_tenant_raises(
        self,
        hitl_service: HumanInTheLoopService,
        mock_repo: AsyncMock,
    ) -> None:
        item_tenant_id = uuid4()
        reviewer_tenant_id = uuid4()
        item = ReviewItem(
            item_id=uuid4(),
            item_type="CoherenceAlert",
            current_status=ReviewStatus.APPROVED,
            confidence=0.9,
            impact_level=ImpactLevel.HIGH,
            created_at=datetime.now(),
            sla_due_date=datetime.now() + timedelta(days=1),
            approved_by="reviewer",
            approved_at=datetime.now(),
            item_data={},
            metadata={"tenant_id": str(item_tenant_id)},
        )
        mock_repo.get_review_item.return_value = item

        with pytest.raises(ValueError, match="tenant mismatch"):
            await hitl_service.release_item(
                item_id=item.item_id,
                reviewer_tenant_id=reviewer_tenant_id,
            )

    async def test_release_item_not_approved_raises(
        self,
        hitl_service: HumanInTheLoopService,
        mock_repo: AsyncMock,
    ) -> None:
        item = ReviewItem(
            item_id=uuid4(),
            item_type="CoherenceAlert",
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
            confidence=0.5,
            impact_level=ImpactLevel.MEDIUM,
            created_at=datetime.now(),
            sla_due_date=datetime.now() + timedelta(days=1),
            item_data={},
        )
        mock_repo.get_review_item.return_value = item

        with pytest.raises(ValueError, match="requires human approval"):
            await hitl_service.release_item(item_id=item.item_id)
