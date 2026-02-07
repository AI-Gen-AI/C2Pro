"""
Generate BOM Use Case tests.

Refers to Suite ID: TS-UA-PROC-UC-001.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.procurement.application.use_cases.generate_bom_use_case import GenerateBOMUseCase
from src.procurement.domain.models import BOMItem, BudgetItem, WBSItem


class TestGenerateBOMUseCase:
    """Refers to Suite ID: TS-UA-PROC-UC-001."""

    @pytest.mark.asyncio
    async def test_001_generates_and_persists_bom_items(self) -> None:
        project_id = uuid4()
        tenant_id = uuid4()
        wbs_items = [
            WBSItem(project_id=project_id, code="1", name="Root", level=1),
            WBSItem(project_id=project_id, code="1.1", name="Leaf", level=2, parent_code="1"),
        ]
        budget_items = [BudgetItem(id=uuid4(), name="Steel", code="B-01", amount=1000.0)]
        generated_items = [
            BOMItem(project_id=project_id, item_name="Steel", quantity=Decimal("2"))
        ]

        wbs_repo = AsyncMock()
        wbs_repo.get_by_project.return_value = wbs_items

        bom_repo = AsyncMock()
        bom_repo.bulk_create.return_value = generated_items

        generator = AsyncMock()
        generator.generate_bom.return_value = generated_items

        use_case = GenerateBOMUseCase(
            wbs_repository=wbs_repo,
            bom_repository=bom_repo,
            bom_generation_service=generator,
        )

        result = await use_case.execute(
            project_id=project_id,
            budget_items=budget_items,
            tenant_id=tenant_id,
        )

        wbs_repo.get_by_project.assert_awaited_once_with(project_id, tenant_id)
        generator.generate_bom.assert_awaited_once_with(
            wbs_items=wbs_items,
            budget_items=budget_items,
        )
        bom_repo.bulk_create.assert_awaited_once_with(generated_items)
        assert result == generated_items

    @pytest.mark.asyncio
    async def test_002_no_wbs_items_returns_empty(self) -> None:
        project_id = uuid4()
        tenant_id = uuid4()

        wbs_repo = AsyncMock()
        wbs_repo.get_by_project.return_value = []

        bom_repo = AsyncMock()
        generator = AsyncMock()

        use_case = GenerateBOMUseCase(
            wbs_repository=wbs_repo,
            bom_repository=bom_repo,
            bom_generation_service=generator,
        )

        result = await use_case.execute(
            project_id=project_id,
            budget_items=[],
            tenant_id=tenant_id,
        )

        generator.generate_bom.assert_not_awaited()
        bom_repo.bulk_create.assert_not_awaited()
        assert result == []

    @pytest.mark.asyncio
    async def test_003_no_generated_items_returns_empty(self) -> None:
        project_id = uuid4()
        tenant_id = uuid4()
        wbs_items = [WBSItem(project_id=project_id, code="1", name="Root", level=1)]

        wbs_repo = AsyncMock()
        wbs_repo.get_by_project.return_value = wbs_items

        bom_repo = AsyncMock()
        generator = AsyncMock()
        generator.generate_bom.return_value = []

        use_case = GenerateBOMUseCase(
            wbs_repository=wbs_repo,
            bom_repository=bom_repo,
            bom_generation_service=generator,
        )

        result = await use_case.execute(
            project_id=project_id,
            budget_items=[],
            tenant_id=tenant_id,
        )

        bom_repo.bulk_create.assert_not_awaited()
        assert result == []
