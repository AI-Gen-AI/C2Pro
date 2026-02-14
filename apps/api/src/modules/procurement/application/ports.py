"""
I9 Procurement Planning Application Service
Test Suite ID: TS-I9-PROC-APP-001
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.modules.procurement.domain.entities import ProcurementPlanItem
from src.modules.procurement.domain.services import ProcurementIntelligenceService


class PlanningDecision(BaseModel):
    """Service output for procurement planning decisions."""

    plan_fingerprint: str
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    requires_human_review: bool = False


class ProcurementPlanningService:
    """Builds procurement planning outputs with deterministic conflict logic."""

    def __init__(self) -> None:
        self.intelligence = ProcurementIntelligenceService()

    async def build_procurement_plan(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date,
    ) -> PlanningDecision:
        # Deterministic snapshot seed: same project/tenant/date => same synthetic input set.
        plan_items = [
            ProcurementPlanItem(
                item_name="Primary Switchgear",
                required_on_site_date=required_on_site,
                optimal_order_date=required_on_site - timedelta(days=10),
                total_cost=Decimal("150000.00"),
            )
        ]
        current_date = required_on_site - timedelta(days=3)
        conflicts = self.intelligence.detect_conflicts(plan_items, current_date=current_date)
        fingerprint = self.intelligence.generate_plan_fingerprint(plan_items)

        return PlanningDecision(
            plan_fingerprint=fingerprint,
            conflicts=[conflict.model_dump(mode="json") for conflict in conflicts],
            requires_human_review=any(conflict.impact in {"HIGH", "CRITICAL"} for conflict in conflicts),
        )

