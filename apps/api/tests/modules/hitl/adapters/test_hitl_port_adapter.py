"""
TS-UC-HITL-ADAPTER-001 — HITLServiceAdapter unit tests.

Pure unit tests: no DB, no HTTP, no external services.
"""

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.hitl.adapters.hitl_port_adapter import HITLServiceAdapter
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus


def _make_review_item(**overrides) -> ReviewItem:
    now = datetime.now()
    defaults = {
        "item_id": uuid4(),
        "item_type": "extraction",
        "current_status": ReviewStatus.PENDING_REVIEW_REQUIRED,
        "confidence": 0.35,
        "impact_level": ImpactLevel.HIGH,
        "created_at": now,
        "sla_due_date": now,
        "approved_by": None,
        "approved_at": None,
        "item_data": {},
        "metadata": {},
    }
    defaults.update(overrides)
    return ReviewItem(**defaults)


class TestHITLServiceAdapter:
    @pytest.mark.asyncio
    async def test_001_route_for_review_valid_impact_level(self):
        service = AsyncMock()
        service.route_for_review.return_value = ReviewStatus.PENDING_REVIEW_REQUIRED

        adapter = HITLServiceAdapter(service=service)
        item_id = uuid4()
        tenant_id = uuid4()
        item_data = {"key": "val"}

        result = await adapter.route_for_review(
            item_id=item_id,
            item_type="extraction",
            confidence=0.3,
            impact_level="HIGH",
            item_data=item_data,
            tenant_id=tenant_id,
        )

        assert result == "PENDING_REVIEW_REQUIRED"
        service.route_for_review.assert_awaited_once_with(
            item_id=item_id,
            item_type="extraction",
            confidence=0.3,
            impact_level=ImpactLevel.HIGH,
            item_data=item_data,
        )

    @pytest.mark.asyncio
    async def test_002_impact_level_fallback_to_medium(self):
        service = AsyncMock()
        service.route_for_review.return_value = ReviewStatus.APPROVED

        adapter = HITLServiceAdapter(service=service)
        item_id = uuid4()
        tenant_id = uuid4()

        result = await adapter.route_for_review(
            item_id=item_id,
            item_type="doc",
            confidence=0.9,
            impact_level="INVALID_LEVEL",
            item_data={},
            tenant_id=tenant_id,
        )

        assert result == "APPROVED"
        service.route_for_review.assert_awaited_once_with(
            item_id=item_id,
            item_type="doc",
            confidence=0.9,
            impact_level=ImpactLevel.MEDIUM,
            item_data={},
        )

    @pytest.mark.asyncio
    async def test_003_lowercase_impact_level_maps_correctly(self):
        service = AsyncMock()
        service.route_for_review.return_value = ReviewStatus.APPROVED

        adapter = HITLServiceAdapter(service=service)
        item_id = uuid4()
        tenant_id = uuid4()

        result = await adapter.route_for_review(
            item_id=item_id,
            item_type="doc",
            confidence=0.9,
            impact_level="low",
            item_data={},
            tenant_id=tenant_id,
        )

        assert result == "APPROVED"
        service.route_for_review.assert_awaited_once_with(
            item_id=item_id,
            item_type="doc",
            confidence=0.9,
            impact_level=ImpactLevel.LOW,
            item_data={},
        )

    @pytest.mark.asyncio
    async def test_004_approve_item_returns_correct_dict(self):
        service = AsyncMock()
        now = datetime(2026, 6, 1, 12, 0, 0)
        item = _make_review_item(
            item_type="clause",
            current_status=ReviewStatus.APPROVED,
            confidence=0.8,
            impact_level=ImpactLevel.MEDIUM,
            approved_by="reviewer@test.com",
            approved_at=now,
        )
        service.approve_item.return_value = item

        adapter = HITLServiceAdapter(service=service)
        reviewer_id = uuid4()
        tenant_id = uuid4()

        result = await adapter.approve_item(
            item_id=item.item_id,
            reviewer_id=reviewer_id,
            reviewer_name="reviewer@test.com",
            tenant_id=tenant_id,
        )

        assert result["item_id"] == str(item.item_id)
        assert result["item_type"] == "clause"
        assert result["current_status"] == "APPROVED"
        assert result["confidence"] == 0.8
        assert result["impact_level"] == "MEDIUM"
        assert result["approved_by"] == "reviewer@test.com"
        assert result["approved_at"] == now.isoformat()
        service.approve_item.assert_awaited_once_with(
            item_id=item.item_id,
            reviewer_id=reviewer_id,
            reviewer_name="reviewer@test.com",
        )

    @pytest.mark.asyncio
    async def test_005_approve_item_approved_at_none(self):
        service = AsyncMock()
        item = _make_review_item(
            approved_by=None,
            approved_at=None,
        )
        service.approve_item.return_value = item

        adapter = HITLServiceAdapter(service=service)
        reviewer_id = uuid4()
        tenant_id = uuid4()

        result = await adapter.approve_item(
            item_id=item.item_id,
            reviewer_id=reviewer_id,
            reviewer_name="someone",
            tenant_id=tenant_id,
        )

        assert result["approved_at"] is None
        assert result["approved_by"] is None
