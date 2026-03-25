"""
I9 - Procurement Planning Repository Contracts (Application)
Test Suite ID: TS-I9-PROC-APP-002
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.procurement.application.planning_service import (
    ProcurementPlanningService,
    ProcurementSnapshotRepository,
)
from src.procurement.domain.models import ProcurementPlanItem, ProcurementPriority


@pytest.fixture
def mock_repository() -> AsyncMock:
    repo = AsyncMock(spec=ProcurementSnapshotRepository)
    repo.get_snapshot_items.return_value = [
        ProcurementPlanItem(
            bom_item_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            item_name="Primary Switchgear",
            quantity=Decimal("1"),
            required_on_site_date=date(2026, 9, 1),
            optimal_order_date=date(2026, 8, 20),
            total_cost=Decimal("150000.00"),
            priority=ProcurementPriority.CRITICAL,
        )
    ]
    return repo


@pytest.mark.asyncio
async def test_i9_build_procurement_plan_uses_repository_snapshot_with_tenant_scope(
    mock_repository: AsyncMock,
) -> None:
    """I9 app contract: service must request snapshot via repository using project+tenant scope."""
    service = ProcurementPlanningService(
        repository=mock_repository,
        decision_repository=AsyncMock(),
        uow=AsyncMock()
    )
    project_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    tenant_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    required = date(2026, 9, 1)

    decision = await service.build_procurement_plan(
        project_id=project_id,
        tenant_id=tenant_id,
        required_on_site=required,
    )

    mock_repository.get_snapshot_items.assert_awaited_once_with(
        project_id=project_id,
        tenant_id=tenant_id,
        required_on_site=required,
    )
    assert decision.plan_fingerprint


@pytest.mark.asyncio
async def test_i9_build_procurement_plan_propagates_repository_failures_without_fallback(
    mock_repository: AsyncMock,
) -> None:
    """I9 app contract: repository failures must fail fast (no synthetic fallback generation)."""
    mock_repository.get_snapshot_items.side_effect = RuntimeError("snapshot unavailable")
    service = ProcurementPlanningService(
        repository=mock_repository,
        decision_repository=AsyncMock(),
        uow=AsyncMock()
    )

    with pytest.raises(RuntimeError, match="snapshot unavailable"):
        await service.build_procurement_plan(
            project_id=uuid4(),
            tenant_id=uuid4(),
            required_on_site=date(2026, 9, 1),
        )
