"""Tests for RouteForGraphReviewUseCase.

TASK-IMPL-010.6: HITL graph routing use case.
Uses existing ConfidenceRouter + HumanInTheLoopService.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.hitl.application.route_for_graph_review_use_case import (
    GraphReviewCommand,
    GraphReviewResult,
    RouteForGraphReviewUseCase,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus


def _make_command(**overrides) -> GraphReviewCommand:
    defaults = dict(
        document_id=uuid4(),
        tenant_id=uuid4(),
        doc_type="contract",
        confidence=0.6,
        project_id=str(uuid4()),
        retry_count=0,
        critique_notes="",
    )
    defaults.update(overrides)
    return GraphReviewCommand(**defaults)


class TestRouteForGraphReviewUseCase:
    def setup_method(self):
        self.hitl_service = MagicMock()
        self.hitl_service.route_for_review = AsyncMock(
            return_value=ReviewStatus.PENDING_REVIEW_REQUIRED
        )
        self.use_case = RouteForGraphReviewUseCase(
            hitl_service=self.hitl_service,
        )

    @pytest.mark.asyncio
    async def test_low_confidence_routes_as_high_impact(self):
        cmd = _make_command(confidence=0.3)
        result = await self.use_case.execute(cmd)

        assert isinstance(result, GraphReviewResult)
        assert result.impact_level == ImpactLevel.HIGH
        call_kwargs = self.hitl_service.route_for_review.call_args
        assert call_kwargs.kwargs["impact_level"] == ImpactLevel.HIGH

    @pytest.mark.asyncio
    async def test_medium_confidence_routes_as_medium_impact(self):
        cmd = _make_command(confidence=0.7)
        result = await self.use_case.execute(cmd)

        assert result.impact_level == ImpactLevel.MEDIUM
        call_kwargs = self.hitl_service.route_for_review.call_args
        assert call_kwargs.kwargs["impact_level"] == ImpactLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_review_item_persisted_with_correct_data(self):
        cmd = _make_command(
            doc_type="budget",
            retry_count=2,
            critique_notes="Missing data",
        )
        await self.use_case.execute(cmd)

        call_kwargs = self.hitl_service.route_for_review.call_args
        assert call_kwargs.kwargs["item_id"] == cmd.document_id
        assert call_kwargs.kwargs["item_type"] == "budget"
        item_data = call_kwargs.kwargs["item_data"]
        assert item_data["retry_count"] == 2
        assert item_data["critique_notes"] == "Missing data"

    @pytest.mark.asyncio
    async def test_review_status_returned(self):
        self.hitl_service.route_for_review = AsyncMock(
            return_value=ReviewStatus.APPROVED
        )
        cmd = _make_command(confidence=0.95)
        result = await self.use_case.execute(cmd)

        assert result.review_status == ReviewStatus.APPROVED

    @pytest.mark.asyncio
    async def test_custom_high_impact_threshold(self):
        use_case = RouteForGraphReviewUseCase(
            hitl_service=self.hitl_service,
            high_impact_threshold=0.7,
        )
        cmd = _make_command(confidence=0.6)
        result = await use_case.execute(cmd)

        assert result.impact_level == ImpactLevel.HIGH
