"""
Tests for RoutingPolicy domain model and InMemoryRoutingPolicyRepository
(TASK-V3-020-02 — policy-driven routing).

RED phase: written before implementation.
Scope: RoutingPolicy fields/immutability, DEFAULT_ROUTING_POLICY,
       InMemoryRoutingPolicyRepository lookup logic.
Out of scope: database-backed repo, HTTP endpoints.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.modules.hitl.adapters.in_memory_routing_policy_repository import (
    InMemoryRoutingPolicyRepository,
)
from src.modules.hitl.domain.routing_policy import DEFAULT_ROUTING_POLICY, RoutingPolicy

# ---------------------------------------------------------------------------
# RoutingPolicy model
# ---------------------------------------------------------------------------


class TestRoutingPolicy:
    def test_default_thresholds(self) -> None:
        p = RoutingPolicy()
        assert p.low_confidence_threshold == 0.3
        assert p.high_confidence_threshold == 0.8
        assert p.high_impact_threshold == 0.5

    def test_default_auto_approve_empty(self) -> None:
        assert RoutingPolicy().auto_approve_item_types == frozenset()

    def test_custom_thresholds(self) -> None:
        p = RoutingPolicy(
            low_confidence_threshold=0.1,
            high_confidence_threshold=0.95,
            high_impact_threshold=0.6,
        )
        assert p.low_confidence_threshold == 0.1
        assert p.high_confidence_threshold == 0.95
        assert p.high_impact_threshold == 0.6

    def test_auto_approve_item_types_stored(self) -> None:
        p = RoutingPolicy(auto_approve_item_types=frozenset({"summary", "retrieval"}))
        assert "summary" in p.auto_approve_item_types
        assert "retrieval" in p.auto_approve_item_types
        assert "extraction" not in p.auto_approve_item_types

    def test_is_immutable(self) -> None:
        p = RoutingPolicy()
        with pytest.raises(Exception):
            p.high_impact_threshold = 0.7  # type: ignore[misc]

    def test_equality(self) -> None:
        assert RoutingPolicy() == RoutingPolicy()
        assert RoutingPolicy(high_impact_threshold=0.6) != RoutingPolicy(high_impact_threshold=0.7)


class TestDefaultRoutingPolicy:
    def test_matches_default_constructor(self) -> None:
        assert RoutingPolicy() == DEFAULT_ROUTING_POLICY

    def test_low_threshold(self) -> None:
        assert DEFAULT_ROUTING_POLICY.low_confidence_threshold == 0.3

    def test_high_threshold(self) -> None:
        assert DEFAULT_ROUTING_POLICY.high_confidence_threshold == 0.8

    def test_impact_threshold(self) -> None:
        assert DEFAULT_ROUTING_POLICY.high_impact_threshold == 0.5


# ---------------------------------------------------------------------------
# InMemoryRoutingPolicyRepository
# ---------------------------------------------------------------------------


class TestInMemoryRoutingPolicyRepository:
    @pytest.mark.asyncio
    async def test_returns_default_when_no_overrides(self) -> None:
        repo = InMemoryRoutingPolicyRepository()
        policy = await repo.get_policy(uuid4(), "extraction")
        assert policy == DEFAULT_ROUTING_POLICY

    @pytest.mark.asyncio
    async def test_custom_default_returned(self) -> None:
        custom = RoutingPolicy(high_impact_threshold=0.7)
        repo = InMemoryRoutingPolicyRepository(default_policy=custom)
        policy = await repo.get_policy(uuid4(), "clause")
        assert policy.high_impact_threshold == 0.7

    @pytest.mark.asyncio
    async def test_override_matches_tenant_and_doc_type(self) -> None:
        tenant_id = uuid4()
        override = RoutingPolicy(high_impact_threshold=0.9)
        repo = InMemoryRoutingPolicyRepository(
            overrides={(tenant_id, "contract"): override}
        )
        policy = await repo.get_policy(tenant_id, "contract")
        assert policy.high_impact_threshold == 0.9

    @pytest.mark.asyncio
    async def test_fallback_when_tenant_differs(self) -> None:
        tenant_id = uuid4()
        override = RoutingPolicy(high_impact_threshold=0.9)
        repo = InMemoryRoutingPolicyRepository(
            overrides={(tenant_id, "contract"): override}
        )
        policy = await repo.get_policy(uuid4(), "contract")
        assert policy == DEFAULT_ROUTING_POLICY

    @pytest.mark.asyncio
    async def test_fallback_when_doc_type_differs(self) -> None:
        tenant_id = uuid4()
        override = RoutingPolicy(high_impact_threshold=0.9)
        repo = InMemoryRoutingPolicyRepository(
            overrides={(tenant_id, "contract"): override}
        )
        policy = await repo.get_policy(tenant_id, "budget")
        assert policy == DEFAULT_ROUTING_POLICY

    @pytest.mark.asyncio
    async def test_multiple_overrides_resolved_independently(self) -> None:
        t1, t2 = uuid4(), uuid4()
        p1 = RoutingPolicy(high_impact_threshold=0.6)
        p2 = RoutingPolicy(high_impact_threshold=0.75)
        repo = InMemoryRoutingPolicyRepository(
            overrides={(t1, "contract"): p1, (t2, "budget"): p2}
        )
        assert (await repo.get_policy(t1, "contract")).high_impact_threshold == 0.6
        assert (await repo.get_policy(t2, "budget")).high_impact_threshold == 0.75
        assert await repo.get_policy(t1, "budget") == DEFAULT_ROUTING_POLICY

    @pytest.mark.asyncio
    async def test_empty_overrides_dict(self) -> None:
        repo = InMemoryRoutingPolicyRepository(overrides={})
        policy = await repo.get_policy(uuid4(), "anything")
        assert policy == DEFAULT_ROUTING_POLICY

    @pytest.mark.asyncio
    async def test_override_with_auto_approve_types(self) -> None:
        tenant_id = uuid4()
        policy = RoutingPolicy(auto_approve_item_types=frozenset({"summary"}))
        repo = InMemoryRoutingPolicyRepository(
            overrides={(tenant_id, "summary"): policy}
        )
        resolved = await repo.get_policy(tenant_id, "summary")
        assert "summary" in resolved.auto_approve_item_types


# ---------------------------------------------------------------------------
# RouteForGraphReviewUseCase (policy-driven path)
# ---------------------------------------------------------------------------


class TestRouteForGraphReviewUseCaseWithPolicy:
    """Tests the updated use case that accepts a policy repository."""

    @pytest.mark.asyncio
    async def test_low_confidence_routes_high_impact(self) -> None:
        from unittest.mock import AsyncMock

        from src.modules.hitl.application.route_for_graph_review_use_case import (
            GraphReviewCommand,
            RouteForGraphReviewUseCase,
        )
        from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus

        hitl_service = AsyncMock()
        hitl_service.route_for_review.return_value = ReviewStatus.PENDING_REVIEW_REQUIRED

        repo = InMemoryRoutingPolicyRepository(
            default_policy=RoutingPolicy(high_impact_threshold=0.5)
        )
        uc = RouteForGraphReviewUseCase(hitl_service=hitl_service, policy_repository=repo)
        cmd = GraphReviewCommand(
            document_id=uuid4(),
            tenant_id=uuid4(),
            doc_type="clause",
            confidence=0.3,
            project_id="p",
            retry_count=0,
            critique_notes="",
        )
        result = await uc.execute(cmd)
        assert result.impact_level == ImpactLevel.HIGH

    @pytest.mark.asyncio
    async def test_high_confidence_routes_medium_impact(self) -> None:
        from unittest.mock import AsyncMock

        from src.modules.hitl.application.route_for_graph_review_use_case import (
            GraphReviewCommand,
            RouteForGraphReviewUseCase,
        )
        from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus

        hitl_service = AsyncMock()
        hitl_service.route_for_review.return_value = ReviewStatus.APPROVED

        repo = InMemoryRoutingPolicyRepository(
            default_policy=RoutingPolicy(high_impact_threshold=0.5)
        )
        uc = RouteForGraphReviewUseCase(hitl_service=hitl_service, policy_repository=repo)
        cmd = GraphReviewCommand(
            document_id=uuid4(),
            tenant_id=uuid4(),
            doc_type="extraction",
            confidence=0.85,
            project_id="p",
            retry_count=0,
            critique_notes="",
        )
        result = await uc.execute(cmd)
        assert result.impact_level == ImpactLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_per_tenant_override_changes_routing(self) -> None:
        """Same confidence, different tenants → different impact due to policy."""
        from unittest.mock import AsyncMock

        from src.modules.hitl.application.route_for_graph_review_use_case import (
            GraphReviewCommand,
            RouteForGraphReviewUseCase,
        )
        from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus

        hitl_service = AsyncMock()
        hitl_service.route_for_review.return_value = ReviewStatus.APPROVED

        tenant_strict = uuid4()
        repo = InMemoryRoutingPolicyRepository(
            default_policy=RoutingPolicy(high_impact_threshold=0.5),
            overrides={
                (tenant_strict, "contract"): RoutingPolicy(high_impact_threshold=0.9)
            },
        )
        uc = RouteForGraphReviewUseCase(hitl_service=hitl_service, policy_repository=repo)

        # default tenant: confidence=0.7 > 0.5 → MEDIUM
        cmd_default = GraphReviewCommand(
            document_id=uuid4(),
            tenant_id=uuid4(),
            doc_type="contract",
            confidence=0.7,
            project_id="p",
            retry_count=0,
            critique_notes="",
        )
        result_default = await uc.execute(cmd_default)
        assert result_default.impact_level == ImpactLevel.MEDIUM

        # strict tenant: confidence=0.7 < 0.9 → HIGH
        cmd_strict = GraphReviewCommand(
            document_id=uuid4(),
            tenant_id=tenant_strict,
            doc_type="contract",
            confidence=0.7,
            project_id="p",
            retry_count=0,
            critique_notes="",
        )
        result_strict = await uc.execute(cmd_strict)
        assert result_strict.impact_level == ImpactLevel.HIGH

    @pytest.mark.asyncio
    async def test_auto_approve_item_type_bypasses_review(self) -> None:
        """doc_type in policy.auto_approve_item_types → APPROVED without calling hitl_service."""
        from unittest.mock import AsyncMock

        from src.modules.hitl.application.route_for_graph_review_use_case import (
            GraphReviewCommand,
            RouteForGraphReviewUseCase,
        )
        from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus

        hitl_service = AsyncMock()

        repo = InMemoryRoutingPolicyRepository(
            default_policy=RoutingPolicy(auto_approve_item_types=frozenset({"summary"}))
        )
        uc = RouteForGraphReviewUseCase(hitl_service=hitl_service, policy_repository=repo)
        cmd = GraphReviewCommand(
            document_id=uuid4(),
            tenant_id=uuid4(),
            doc_type="summary",
            confidence=0.1,
            project_id="p",
            retry_count=0,
            critique_notes="",
        )
        result = await uc.execute(cmd)
        assert result.review_status == ReviewStatus.APPROVED
        assert result.impact_level == ImpactLevel.LOW
        hitl_service.route_for_review.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_auto_approve_type_still_routes_normally(self) -> None:
        from unittest.mock import AsyncMock

        from src.modules.hitl.application.route_for_graph_review_use_case import (
            GraphReviewCommand,
            RouteForGraphReviewUseCase,
        )
        from src.modules.hitl.domain.entities import ReviewStatus

        hitl_service = AsyncMock()
        hitl_service.route_for_review.return_value = ReviewStatus.PENDING_REVIEW_REQUIRED

        repo = InMemoryRoutingPolicyRepository(
            default_policy=RoutingPolicy(auto_approve_item_types=frozenset({"summary"}))
        )
        uc = RouteForGraphReviewUseCase(hitl_service=hitl_service, policy_repository=repo)
        cmd = GraphReviewCommand(
            document_id=uuid4(),
            tenant_id=uuid4(),
            doc_type="extraction",
            confidence=0.3,
            project_id="p",
            retry_count=0,
            critique_notes="",
        )
        await uc.execute(cmd)
        hitl_service.route_for_review.assert_awaited_once()
