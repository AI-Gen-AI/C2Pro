"""
HITL graph routing use case.

Determines impact level from confidence, routes through existing
ConfidenceRouter + HumanInTheLoopService. The LangGraph Interrupt
stays in the node — this use case handles only domain/application work.

Refers to TASK-IMPL-010.6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.modules.hitl.application.human_in_the_loop_service import (
    HumanInTheLoopService,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus


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

    Uses existing ConfidenceRouter (inside HumanInTheLoopService) for
    review status determination. Impact level is derived from confidence.
    """

    def __init__(
        self,
        hitl_service: HumanInTheLoopService,
        high_impact_threshold: float = 0.5,
    ) -> None:
        self._hitl = hitl_service
        self._high_impact_threshold = high_impact_threshold

    async def execute(self, command: GraphReviewCommand) -> GraphReviewResult:
        impact = (
            ImpactLevel.HIGH
            if command.confidence < self._high_impact_threshold
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
