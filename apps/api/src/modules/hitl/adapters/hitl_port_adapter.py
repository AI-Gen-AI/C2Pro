"""Adapter that bridges HumanInTheLoopService to the HITLPort protocol.

The DecisionOrchestrationService depends on HITLPort (Protocol) which expects:
  - route_for_review(..., impact_level: str, ...) -> str
  - approve_item(...) -> dict[str, Any]

HumanInTheLoopService uses domain types (ImpactLevel enum, ReviewItem model).
This adapter translates between the two.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.modules.hitl.application.ports import HumanInTheLoopService
from src.modules.hitl.domain.entities import ImpactLevel


class HITLServiceAdapter:
    """Satisfies the HITLPort protocol by wrapping HumanInTheLoopService."""

    def __init__(self, service: HumanInTheLoopService) -> None:
        self._service = service

    async def route_for_review(
        self,
        item_id: UUID,
        item_type: str,
        confidence: float,
        impact_level: str,
        item_data: dict[str, Any],
    ) -> str:
        # Convert string impact_level to ImpactLevel enum
        try:
            level = ImpactLevel(impact_level.upper())
        except ValueError:
            level = ImpactLevel.MEDIUM

        status = await self._service.route_for_review(
            item_id=item_id,
            item_type=item_type,
            confidence=confidence,
            impact_level=level,
            item_data=item_data,
        )
        return status.value

    async def approve_item(
        self,
        item_id: UUID,
        reviewer_id: UUID,
        reviewer_name: str,
    ) -> dict[str, Any]:
        item = await self._service.approve_item(
            item_id=item_id,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
        )
        return {
            "item_id": str(item.item_id),
            "item_type": item.item_type,
            "current_status": item.current_status.value,
            "confidence": item.confidence,
            "impact_level": item.impact_level.value,
            "approved_by": item.approved_by,
            "approved_at": item.approved_at.isoformat() if item.approved_at else None,
        }
