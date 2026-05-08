"""
I11 - Human-in-the-Loop Workflow Integration (RED)
Test Suite ID: TS-I11-HITL-INT-001
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.modules.hitl.application.ports import HumanInTheLoopService
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus
from src.modules.hitl.domain.services import ConfidenceRouter


def _configured_service() -> tuple[HumanInTheLoopService, AsyncMock, AsyncMock]:
    review_queue_repo = AsyncMock()
    notification_service = AsyncMock()
    service = HumanInTheLoopService(
        review_queue_repo=review_queue_repo,
        notification_service=notification_service,
        confidence_router=ConfidenceRouter(
            low_confidence_threshold=0.3,
            high_confidence_threshold=0.8,
        ),
    )
    return service, review_queue_repo, notification_service


@pytest.mark.asyncio
async def test_i11_int_high_impact_item_cannot_be_released_without_explicit_human_approval_red() -> None:
    """
    TS-I11-HITL-INT-001:
    high-impact item must remain blocked until explicit approval metadata exists.
    """
    service, review_queue_repo, _ = _configured_service()
    item_id = uuid4()

    status = await service.route_for_review(
        item_id=item_id,
        item_type="CoherenceAlert",
        confidence=0.95,
        impact_level=ImpactLevel.HIGH,
        item_data={"source": "analysis"},
    )
    assert status == ReviewStatus.PENDING_REVIEW_REQUIRED

    review_queue_repo.get_review_item.return_value = ReviewItem(
        item_id=item_id,
        item_type="CoherenceAlert",
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        confidence=0.95,
        impact_level=ImpactLevel.HIGH,
        created_at=datetime.now() - timedelta(hours=1),
        sla_due_date=datetime.now() + timedelta(days=2),
        item_data={"source": "analysis"},
    )

    with pytest.raises(ValueError, match="requires human approval"):
        await service.release_item(item_id)


@pytest.mark.asyncio
async def test_i11_int_sla_escalation_sets_metadata_and_is_idempotent_red() -> None:
    """
    TS-I11-HITL-INT-001:
    SLA escalation must stamp metadata and avoid duplicate escalation notifications.
    """
    service, review_queue_repo, notification_service = _configured_service()
    item_id = uuid4()
    tenant_id = uuid4()
    overdue_item = ReviewItem(
        item_id=item_id,
        item_type="CoherenceAlert",
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        confidence=0.4,
        impact_level=ImpactLevel.HIGH,
        created_at=datetime.now() - timedelta(days=4),
        sla_due_date=datetime.now() - timedelta(hours=3),
        item_data={},
        metadata={"tenant_id": str(tenant_id)},
    )

    review_queue_repo.get_overdue_items.side_effect = [
        [overdue_item],
        [
            ReviewItem(
                item_id=item_id,
                item_type="CoherenceAlert",
                current_status=ReviewStatus.ESCALATED,
                confidence=0.4,
                impact_level=ImpactLevel.HIGH,
                created_at=overdue_item.created_at,
                sla_due_date=overdue_item.sla_due_date,
                item_data={},
                metadata={
                    "tenant_id": str(tenant_id),
                    "escalated_at": datetime.now().isoformat(),
                },
            )
        ],
    ]

    first = await service.check_and_escalate_slas()
    second = await service.check_and_escalate_slas()

    assert len(first) == 1
    assert first[0].new_status == ReviewStatus.ESCALATED
    assert first[0].escalation_triggered is True
    assert len(second) == 0
    notification_service.send_escalation_alert.assert_awaited_once_with(overdue_item, tenant_id)


@pytest.mark.asyncio
async def test_i11_int_tenant_mismatch_blocks_release_red() -> None:
    """
    TS-I11-HITL-INT-001:
    release must be blocked if reviewer tenant does not match item tenant scope.
    """
    service, review_queue_repo, _ = _configured_service()
    item_id = uuid4()
    item_tenant = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    reviewer_tenant = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    review_queue_repo.get_review_item.return_value = ReviewItem(
        item_id=item_id,
        item_type="CoherenceAlert",
        current_status=ReviewStatus.APPROVED,
        confidence=0.91,
        impact_level=ImpactLevel.MEDIUM,
        created_at=datetime.now() - timedelta(hours=2),
        sla_due_date=datetime.now() + timedelta(days=1),
        approved_by="reviewer@example.com",
        approved_at=datetime.now() - timedelta(minutes=30),
        item_data={},
        metadata={"tenant_id": str(item_tenant)},
    )

    with pytest.raises(ValueError, match="tenant mismatch"):
        await service.release_item(
            item_id=item_id,
            reviewer_tenant_id=reviewer_tenant,
        )
