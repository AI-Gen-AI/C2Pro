"""
TS-UC-HITL-GRAPH-001 — RouteForGraphReviewUseCase unit tests.

Pure unit tests: no DB, no HTTP, no external services.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.hitl.application.route_for_graph_review_use_case import (
    GraphReviewCommand,
    GraphReviewResult,
    RouteForGraphReviewUseCase,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus


class TestRouteForGraphReviewUseCase:
    @pytest.mark.asyncio
    async def test_001_low_confidence_routes_high_impact(self):
        hitl_service = AsyncMock()
        hitl_service.route_for_review.return_value = ReviewStatus.PENDING_REVIEW_REQUIRED

        uc = RouteForGraphReviewUseCase(
            hitl_service=hitl_service,
            high_impact_threshold=0.5,
        )
        command = GraphReviewCommand(
            document_id=uuid4(),
            tenant_id=uuid4(),
            doc_type="clause",
            confidence=0.3,
            project_id="proj-1",
            retry_count=0,
            critique_notes="",
        )

        result = await uc.execute(command)

        assert result.review_status == ReviewStatus.PENDING_REVIEW_REQUIRED
        assert result.impact_level == ImpactLevel.HIGH
        hitl_service.route_for_review.assert_awaited_once_with(
            item_id=command.document_id,
            item_type="clause",
            confidence=0.3,
            impact_level=ImpactLevel.HIGH,
            item_data={
                "project_id": "proj-1",
                "document_id": str(command.document_id),
                "doc_type": "clause",
                "retry_count": 0,
                "critique_notes": "",
            },
        )

    @pytest.mark.asyncio
    async def test_002_high_confidence_routes_medium_impact(self):
        hitl_service = AsyncMock()
        hitl_service.route_for_review.return_value = ReviewStatus.APPROVED

        uc = RouteForGraphReviewUseCase(
            hitl_service=hitl_service,
            high_impact_threshold=0.5,
        )
        command = GraphReviewCommand(
            document_id=uuid4(),
            tenant_id=uuid4(),
            doc_type="extraction",
            confidence=0.85,
            project_id="proj-2",
            retry_count=2,
            critique_notes="minor issue",
        )

        result = await uc.execute(command)

        assert result.review_status == ReviewStatus.APPROVED
        assert result.impact_level == ImpactLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_003_exact_threshold_confidence_routes_medium(self):
        hitl_service = AsyncMock()
        hitl_service.route_for_review.return_value = ReviewStatus.APPROVED

        uc = RouteForGraphReviewUseCase(
            hitl_service=hitl_service,
            high_impact_threshold=0.5,
        )
        command = GraphReviewCommand(
            document_id=uuid4(),
            tenant_id=uuid4(),
            doc_type="doc",
            confidence=0.5,
            project_id="p",
            retry_count=0,
            critique_notes="",
        )

        result = await uc.execute(command)

        assert result.impact_level == ImpactLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_004_custom_threshold(self):
        hitl_service = AsyncMock()
        hitl_service.route_for_review.return_value = ReviewStatus.PENDING_REVIEW_REQUIRED

        uc = RouteForGraphReviewUseCase(
            hitl_service=hitl_service,
            high_impact_threshold=0.75,
        )
        command = GraphReviewCommand(
            document_id=uuid4(),
            tenant_id=uuid4(),
            doc_type="clause",
            confidence=0.7,
            project_id="p",
            retry_count=0,
            critique_notes="",
        )

        result = await uc.execute(command)

        assert result.impact_level == ImpactLevel.HIGH

    @pytest.mark.asyncio
    async def test_005_item_data_has_all_five_keys(self):
        hitl_service = AsyncMock()
        hitl_service.route_for_review.return_value = ReviewStatus.APPROVED

        uc = RouteForGraphReviewUseCase(hitl_service=hitl_service)
        command = GraphReviewCommand(
            document_id=uuid4(),
            tenant_id=uuid4(),
            doc_type="extraction",
            confidence=0.9,
            project_id="proj-3",
            retry_count=3,
            critique_notes="needs review",
        )

        await uc.execute(command)

        call_kwargs = hitl_service.route_for_review.await_args.kwargs
        item_data = call_kwargs["item_data"]
        assert set(item_data.keys()) == {
            "project_id",
            "document_id",
            "doc_type",
            "retry_count",
            "critique_notes",
        }
        assert item_data["project_id"] == "proj-3"
        assert item_data["retry_count"] == 3

    @pytest.mark.asyncio
    async def test_006_return_type_is_graph_review_result(self):
        hitl_service = AsyncMock()
        hitl_service.route_for_review.return_value = ReviewStatus.ESCALATED

        uc = RouteForGraphReviewUseCase(hitl_service=hitl_service)
        command = GraphReviewCommand(
            document_id=uuid4(),
            tenant_id=uuid4(),
            doc_type="clause",
            confidence=0.1,
            project_id="p",
            retry_count=0,
            critique_notes="",
        )

        result = await uc.execute(command)

        assert isinstance(result, GraphReviewResult)
        assert result.review_status == ReviewStatus.ESCALATED
        assert result.impact_level == ImpactLevel.HIGH
