"""
I9 - Procurement Planning Intelligence Service (Application)
Test Suite ID: TS-I9-PROC-APP-001
"""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, Field

try:
    from src.modules.procurement.application.ports import ProcurementPlanningService
except ImportError:
    class PlanningDecision(BaseModel):
        plan_fingerprint: str
        conflicts: list[dict[str, Any]] = Field(default_factory=list)
        requires_human_review: bool = False

    class ProcurementPlanningService:
        async def build_procurement_plan(
            self,
            project_id: UUID,
            tenant_id: UUID,
            required_on_site: date,
        ) -> PlanningDecision:
            return PlanningDecision(plan_fingerprint="", conflicts=[], requires_human_review=False)


@pytest.mark.asyncio
async def test_i9_service_marks_human_review_required_when_high_impact_conflicts_detected() -> None:
    """Refers to I9.4: high-impact procurement conflicts must force human review gate."""
    service = ProcurementPlanningService()

    decision = await service.build_procurement_plan(
        project_id=uuid4(),
        tenant_id=uuid4(),
        required_on_site=date(2026, 9, 1),
    )

    assert len(decision.conflicts) > 0
    assert any(c.get("impact") in {"HIGH", "CRITICAL"} for c in decision.conflicts)
    assert decision.requires_human_review is True


@pytest.mark.asyncio
async def test_i9_service_output_is_deterministic_for_same_project_snapshot() -> None:
    """Refers to I9.3: same project snapshot must produce same plan fingerprint."""
    service = ProcurementPlanningService()
    project_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    tenant_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    required = date(2026, 9, 1)

    decision_a = await service.build_procurement_plan(project_id=project_id, tenant_id=tenant_id, required_on_site=required)
    decision_b = await service.build_procurement_plan(project_id=project_id, tenant_id=tenant_id, required_on_site=required)

    assert decision_a.plan_fingerprint
    assert decision_a.plan_fingerprint == decision_b.plan_fingerprint
