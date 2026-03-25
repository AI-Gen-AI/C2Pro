"""
I9 - Procurement Planning Intelligence Service (Application)
Test Suite ID: TS-I9-PROC-APP-001
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.procurement.application.planning_service import ProcurementPlanningService
from src.procurement.domain.models import ProcurementPlanItem, ProcurementPriority


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_snapshot_items.return_value = [
        ProcurementPlanItem(
            bom_item_id=uuid4(),
            item_name="High Impact Item",
            quantity=Decimal("1"),
            required_on_site_date=date(2026, 9, 1),
            optimal_order_date=date(2026, 8, 25), # Late if current date is near 9/1
            total_cost=Decimal("100000.00"),
            priority=ProcurementPriority.CRITICAL,
        )
    ]
    return repo


@pytest.mark.asyncio
async def test_i9_service_marks_human_review_required_when_high_impact_conflicts_detected() -> None:
    """Refers to I9.4: high-impact procurement conflicts must force human review gate."""
    repo = AsyncMock()
    # To trigger high impact conflict, we need current_date > optimal_order_date
    # in build_procurement_plan: current_date = target_date - 3 days
    # target_date = 2026-09-01 => current_date = 2026-08-29
    # If optimal_order_date = 2026-08-25, it's 4 days late => HIGH impact (>=7 is CRITICAL)
    repo.get_snapshot_items.return_value = [
        ProcurementPlanItem(
            bom_item_id=uuid4(),
            item_name="High Impact Item",
            quantity=Decimal("1"),
            required_on_site_date=date(2026, 9, 1),
            optimal_order_date=date(2026, 8, 25),
            total_cost=Decimal("100000.00"),
            priority=ProcurementPriority.CRITICAL,
        )
    ]
    service = ProcurementPlanningService(
        repository=repo,
        decision_repository=AsyncMock(),
        uow=AsyncMock()
    )

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
    repo = AsyncMock()
    items = [
        ProcurementPlanItem(
            bom_item_id=uuid4(),
            item_name="Item A",
            quantity=Decimal("1"),
            required_on_site_date=date(2026, 9, 1),
            optimal_order_date=date(2026, 8, 20),
            total_cost=Decimal("10000.00"),
            priority=ProcurementPriority.MEDIUM,
        )
    ]
    repo.get_snapshot_items.return_value = items
    service = ProcurementPlanningService(
        repository=repo,
        decision_repository=AsyncMock(),
        uow=AsyncMock()
    )
    project_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    tenant_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    required = date(2026, 9, 1)

    decision_a = await service.build_procurement_plan(project_id=project_id, tenant_id=tenant_id, required_on_site=required)
    decision_b = await service.build_procurement_plan(project_id=project_id, tenant_id=tenant_id, required_on_site=required)

    assert decision_a.plan_fingerprint
    assert decision_a.plan_fingerprint == decision_b.plan_fingerprint
