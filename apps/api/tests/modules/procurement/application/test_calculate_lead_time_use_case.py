"""
Calculate Lead Time Use Case tests.

Refers to Suite ID: TS-UA-PROC-UC-002.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.procurement.application.use_cases.calculate_lead_time_use_case import (
    CalculateLeadTimeUseCase,
)
from src.procurement.domain.models import BOMItem, ProcurementStatus
from src.procurement.domain.lead_time_calculator import LeadTimeResult


class TestCalculateLeadTimeUseCase:
    """Refers to Suite ID: TS-UA-PROC-UC-002."""

    @pytest.mark.asyncio
    async def test_001_calculates_lead_time_for_bom_items(self) -> None:
        project_id = uuid4()
        tenant_id = uuid4()
        bom_item = BOMItem(
            project_id=project_id,
            item_name="Valve",
            quantity=Decimal("2"),
            procurement_status=ProcurementStatus.PENDING,
        )

        bom_repo = AsyncMock()
        bom_repo.get_by_project.return_value = [bom_item]

        calculator = AsyncMock()
        calculator.calculate_lead_time.return_value = LeadTimeResult(
            required_on_site_date=date(2026, 6, 1),
            optimal_order_date=date(2026, 3, 1),
            lead_time_breakdown=None,
            alerts=[],
        )

        use_case = CalculateLeadTimeUseCase(
            bom_repository=bom_repo,
            lead_time_calculator=calculator,
        )

        results = await use_case.execute(
            project_id=project_id,
            required_on_site=date(2026, 6, 1),
            tenant_id=tenant_id,
        )

        bom_repo.get_by_project.assert_awaited_once_with(project_id, tenant_id)
        calculator.calculate_lead_time.assert_awaited_once()
        assert results[bom_item.id].optimal_order_date == date(2026, 3, 1)

    @pytest.mark.asyncio
    async def test_002_no_bom_items_returns_empty(self) -> None:
        project_id = uuid4()
        tenant_id = uuid4()

        bom_repo = AsyncMock()
        bom_repo.get_by_project.return_value = []

        calculator = AsyncMock()

        use_case = CalculateLeadTimeUseCase(
            bom_repository=bom_repo,
            lead_time_calculator=calculator,
        )

        results = await use_case.execute(
            project_id=project_id,
            required_on_site=date(2026, 6, 1),
            tenant_id=tenant_id,
        )

        calculator.calculate_lead_time.assert_not_awaited()
        assert results == {}

    @pytest.mark.asyncio
    async def test_003_skips_items_without_lead_time(self) -> None:
        project_id = uuid4()
        tenant_id = uuid4()
        bom_item = BOMItem(
            project_id=project_id,
            item_name="Valve",
            quantity=Decimal("2"),
            procurement_status=ProcurementStatus.PENDING,
        )

        bom_repo = AsyncMock()
        bom_repo.get_by_project.return_value = [bom_item]

        calculator = AsyncMock()
        calculator.calculate_lead_time.return_value = None

        use_case = CalculateLeadTimeUseCase(
            bom_repository=bom_repo,
            lead_time_calculator=calculator,
        )

        results = await use_case.execute(
            project_id=project_id,
            required_on_site=date(2026, 6, 1),
            tenant_id=tenant_id,
        )

        assert results == {}
