"""
I11 - Human-in-the-Loop Review Queue Service (Application)
Test Suite ID: TS-I11-HITL-APP-001
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.hitl.application.ports import (
    HumanInTheLoopService,
    NotificationService,
    ReviewQueueRepository,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus
from src.modules.hitl.domain.services import ConfidenceRouter


@pytest.fixture
def mock_review_queue_repo() -> AsyncMock:
    repo = AsyncMock(spec=ReviewQueueRepository)
    repo.add_review_item.return_value = uuid4()
    repo.get_review_item.return_value = None
    repo.update_review_item.return_value = None
    repo.get_overdue_items.return_value = []
    return repo


@pytest.fixture
def mock_notification_service() -> AsyncMock:
    service = AsyncMock(spec=NotificationService)
    service.send_notification.return_value = None
    service.send_escalation_alert.return_value = None
    return service


@pytest.fixture
def hitl_service(
    mock_review_queue_repo: AsyncMock,
    mock_notification_service: AsyncMock,
) -> HumanInTheLoopService:
    return HumanInTheLoopService(
        review_queue_repo=mock_review_queue_repo,
        notification_service=mock_notification_service,
        confidence_router=ConfidenceRouter(low_confidence_threshold=0.3, high_confidence_threshold=0.8),
    )


@pytest.mark.asyncio
async def test_i11_high_impact_output_cannot_bypass_review(
    hitl_service: HumanInTheLoopService,
    mock_review_queue_repo: AsyncMock,
) -> None:
    """Refers to I11.2: high-impact outputs must route to review queue and remain blocked."""
    status = await hitl_service.route_for_review(
        item_id=uuid4(),
        item_type="CoherenceAlert",
        confidence=0.95,
        impact_level=ImpactLevel.HIGH,
        item_data={"message": "Critical legal interpretation"},
    )

    assert status in {
        ReviewStatus.PENDING_REVIEW_REQUIRED,
        ReviewStatus.PENDING_REVIEW_CONDITIONAL,
    }
    mock_review_queue_repo.add_review_item.assert_called_once()


@pytest.mark.asyncio
async def test_i11_stale_review_task_triggers_escalation(
    hitl_service: HumanInTheLoopService,
    mock_review_queue_repo: AsyncMock,
    mock_notification_service: AsyncMock,
) -> None:
    """Refers to I11.3: overdue review items must escalate and notify reviewers."""
    overdue_item = ReviewItem(
        item_id=uuid4(),
        item_type="CoherenceAlert",
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        confidence=0.4,
        impact_level=ImpactLevel.MEDIUM,
        created_at=datetime.now() - timedelta(days=3),
        sla_due_date=datetime.now() - timedelta(days=1),
        item_data={},
    )
    mock_review_queue_repo.get_overdue_items.return_value = [overdue_item]

    results = await hitl_service.check_and_escalate_slas()

    assert len(results) == 1
    assert results[0].new_status == ReviewStatus.ESCALATED
    mock_review_queue_repo.update_review_item.assert_called_once()
    mock_notification_service.send_escalation_alert.assert_called_once_with(overdue_item)


@pytest.mark.asyncio
async def test_i11_release_requires_explicit_approval_metadata(
    hitl_service: HumanInTheLoopService,
    mock_review_queue_repo: AsyncMock,
) -> None:
    """Refers to I11.6: approved outputs must include approved_by and approved_at before release."""
    item = ReviewItem(
        item_id=uuid4(),
        item_type="CoherenceAlert",
        current_status=ReviewStatus.APPROVED,
        confidence=0.9,
        impact_level=ImpactLevel.HIGH,
        created_at=datetime.now() - timedelta(hours=3),
        sla_due_date=datetime.now() + timedelta(days=1),
        approved_by=None,
        approved_at=None,
        item_data={},
    )
    mock_review_queue_repo.get_review_item.return_value = item

    with pytest.raises(ValueError, match="Approved item missing explicit reviewer information."):
        await hitl_service.release_item(item.item_id)

