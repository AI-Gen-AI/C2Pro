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


@pytest.mark.asyncio
async def test_create_bom_item_use_case_preserves_source_document_id() -> None:
    """TS-UD-PROC-BOM-IDEM-001: budget parses carry their source document into BOM persistence."""
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    created_item = BOMItem(
        project_id=project_id,
        item_name="Concrete",
        quantity=Decimal("2"),
        source_document_id=document_id,
    )

    repository = AsyncMock()
    repository.create.return_value = created_item

    use_case = CreateBOMItemUseCase(repository)
    payload = BOMItemCreate(
        project_id=project_id,
        item_code="BUD-0001",
        item_name="Concrete",
        quantity=Decimal("2"),
        unit_price=Decimal("10"),
        total_price=Decimal("20"),
        bom_metadata={"source_document_id": str(document_id)},
    )

    result = await use_case.execute(payload, tenant_id)

    persisted_item = repository.create.await_args.args[0]
    assert persisted_item.source_document_id == document_id
    assert result.source_document_id == document_id


@pytest.mark.asyncio
async def test_replace_bom_items_for_source_document_keeps_other_documents() -> None:
    """TS-UD-PROC-BOM-IDEM-001: set-level replacement is scoped to one budget document."""
    tenant_id = uuid4()
    project_id = uuid4()
    source_document_id = uuid4()
    repository = AsyncMock()
    repository.replace_for_source_document.return_value = [
        BOMItem(
            project_id=project_id,
            item_name="Concrete",
            quantity=Decimal("2"),
            source_document_id=source_document_id,
        )
    ]

    use_case = CreateBOMItemUseCase(repository)
    payload = BOMItemCreate(
        project_id=project_id,
        item_name="Concrete",
        quantity=Decimal("2"),
        source_document_id=source_document_id,
        bom_metadata={"source_document_id": str(source_document_id)},
    )

    result = await use_case.replace_for_source_document(
        project_id=project_id,
        source_document_id=source_document_id,
        bom_items=[payload],
        tenant_id=tenant_id,
    )

    repository.replace_for_source_document.assert_awaited_once()
    args = repository.replace_for_source_document.await_args.kwargs
    assert args["project_id"] == project_id
    assert args["source_document_id"] == source_document_id
    assert args["tenant_id"] == tenant_id
    assert args["bom_items"][0].source_document_id == source_document_id
    assert result[0].item_name == "Concrete"
