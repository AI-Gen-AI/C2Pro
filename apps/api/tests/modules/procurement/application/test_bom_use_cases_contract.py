"""
Create BOM item use case contract tests.

Refers to Suite ID: TS-UA-PROC-UC-001.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.procurement.application.dtos import BOMItemCreate
from src.procurement.application.use_cases.bom_use_cases import CreateBOMItemUseCase
from src.procurement.domain.models import BOMCategory, BOMItem, ProcurementStatus


@pytest.mark.asyncio
async def test_create_bom_item_use_case_passes_tenant_id_to_repository() -> None:
    """Refers to Suite ID: TS-UA-PROC-UC-001."""
    tenant_id = uuid4()
    project_id = uuid4()
    created_item = BOMItem(project_id=project_id, item_name="Steel", quantity=Decimal("5"))

    repository = AsyncMock()
    repository.create.return_value = created_item

    use_case = CreateBOMItemUseCase(repository)
    payload = BOMItemCreate(
        project_id=project_id,
        wbs_item_id=None,
        item_code="ST-001",
        item_name="Steel",
        description="Rebar",
        category=BOMCategory.MATERIAL,
        quantity=Decimal("5"),
        unit="kg",
        unit_price=Decimal("2.5"),
        total_price=Decimal("12.5"),
        currency="EUR",
        supplier="Acme Steel",
        lead_time_days=14,
        incoterm="FOB",
        procurement_status=ProcurementStatus.PENDING,
        bom_metadata={"source": "lint-002"},
        contract_clause_id=None,
    )

    result = await use_case.execute(payload, tenant_id)

    repository.create.assert_awaited_once()
    assert repository.create.await_args.args[1] == tenant_id
    assert result == created_item
