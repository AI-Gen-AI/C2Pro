"""
HITL graph routing use case (ADR-020, TASK-V3-020-02).

Routes graph extraction results through HITL based on a per-tenant /
per-doc-type RoutingPolicy rather than hardcoded thresholds. The
LangGraph Interrupt stays in the node; this use case handles only
domain/application work.

Refers to TASK-IMPL-010.6, TASK-V3-020-02.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.modules.hitl.adapters.in_memory_routing_policy_repository import (
    InMemoryRoutingPolicyRepository,
)
from src.modules.hitl.application.human_in_the_loop_service import (
    HumanInTheLoopService,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.modules.hitl.ports.routing_policy_repository import IRoutingPolicyRepository


@dataclass(frozen=True)
class GraphReviewCommand:
    """Input for HITL routing from graph context."""

    document_id: UUID
    tenant_id: UUID
    doc_type: str
    confidence: float
    project_id: str
    retry_count: int
    critique_notes: str


@dataclass(frozen=True)
class GraphReviewResult:
    """Result of HITL routing."""

    review_status: ReviewStatus
    impact_level: ImpactLevel


class RouteForGraphReviewUseCase:
    """Routes graph extraction results through HITL for human review.

    Policy is resolved per (tenant_id, doc_type) via IRoutingPolicyRepository.
    When doc_type is in policy.auto_approve_item_types the item is approved
    immediately without calling the HITL service (automation boundary, ADR-020).
    """

    def __init__(
        self,
        hitl_service: HumanInTheLoopService,
        policy_repository: IRoutingPolicyRepository | None = None,
    ) -> None:
        self._hitl = hitl_service
        self._policy_repo: IRoutingPolicyRepository = (
            policy_repository if policy_repository is not None
            else InMemoryRoutingPolicyRepository()
        )

    async def execute(self, command: GraphReviewCommand) -> GraphReviewResult:
        policy = await self._policy_repo.get_policy(command.tenant_id, command.doc_type)

        # Automation boundary: low-risk item types skip human review entirely.
        if command.doc_type in policy.auto_approve_item_types:
            return GraphReviewResult(
                review_status=ReviewStatus.APPROVED,
                impact_level=ImpactLevel.LOW,
            )

        impact = (
            ImpactLevel.HIGH
            if command.confidence < policy.high_impact_threshold
            else ImpactLevel.MEDIUM
        )

        item_data: dict[str, Any] = {
            "project_id": command.project_id,
            "document_id": str(command.document_id),
            "doc_type": command.doc_type,
            "retry_count": command.retry_count,
            "critique_notes": command.critique_notes,
        }

        status = await self._hitl.route_for_review(
            item_id=command.document_id,
            item_type=command.doc_type,
            confidence=command.confidence,
            impact_level=impact,
            item_data=item_data,
        )

        return GraphReviewResult(
            review_status=status,
            impact_level=impact,
        )
