"""TS-UD-PROC-BOM-IDEM-001: budget entity extraction replaces BOM rows per source document."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.documents.adapters.extraction.documents_entity_extraction_service import (
    DocumentsEntityExtractionService,
)
from src.documents.domain.models import Document, DocumentStatus, DocumentType


class _FakeBOMUseCase:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def replace_for_source_document(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs["bom_items"]


@pytest.mark.asyncio
async def test_budget_extraction_replaces_bom_rows_once_per_source_document() -> None:
    """TS-UD-PROC-BOM-IDEM-001: reparse persistence is scoped to the source budget document."""
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    bom_use_case = _FakeBOMUseCase()
    service = DocumentsEntityExtractionService(
        stakeholder_use_case_factory=lambda: object(),
        wbs_use_case_factory=lambda: object(),
        bom_use_case_factory=lambda: bom_use_case,
        user_id=uuid4(),
    )
    document = Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.BUDGET,
        filename="budget.xlsx",
        upload_status=DocumentStatus.PARSED,
    )

    summary = await service.extract_entities_from_document(
        document=document,
        parsed_payload={
            "budget": [
                {"item": "Concrete", "quantity": "2", "unit_price": "10", "total": "20"},
                {"item": "Steel", "quantity": "3", "unit_price": "5", "total": "15"},
            ]
        },
        tenant_id=tenant_id,
    )

    assert summary["bom_items"] == 2
    assert len(bom_use_case.calls) == 1
    call = bom_use_case.calls[0]
    assert call["project_id"] == project_id
    assert call["source_document_id"] == document_id
    assert call["tenant_id"] == tenant_id
    assert [item.item_name for item in call["bom_items"]] == ["Concrete", "Steel"]
    assert all(item.source_document_id == document_id for item in call["bom_items"])
