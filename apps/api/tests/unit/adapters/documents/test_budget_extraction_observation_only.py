"""#860 -- budget entity extraction OBSERVES budget lines; it never writes canonical BOM.

Supersedes TS-UD-PROC-BOM-IDEM-001 (budget extraction replaced BOM rows per source
document). A budget line is not a canonical BOM item: extraction counts the observed
lines, requests no write use case, and reparsing is therefore trivially idempotent.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.documents.adapters.extraction.documents_entity_extraction_service import (
    DocumentsEntityExtractionService,
)
from src.documents.domain.models import Document, DocumentStatus, DocumentType


class _ExplodingFactory:
    """Any use case requested for a budget is a governance violation."""

    def __call__(self) -> object:
        raise AssertionError("budget extraction must not request a write use case")


def _budget_document() -> Document:
    return Document(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_type=DocumentType.BUDGET,
        filename="budget.xlsx",
        upload_status=DocumentStatus.PARSED,
    )


@pytest.mark.asyncio
async def test_budget_extraction_counts_lines_and_writes_nothing_on_every_reparse() -> None:
    service = DocumentsEntityExtractionService(
        stakeholder_use_case_factory=_ExplodingFactory(),
        user_id=uuid4(),
    )
    document = _budget_document()
    payload = {
        "budget": [
            {"item": "Concrete", "quantity": "2", "unit_price": "10", "total": "20"},
            {"item": "Steel", "quantity": "3", "unit_price": "5", "total": "15"},
            {"item": "Subtotal without quantity", "total": "35"},
        ]
    }

    summaries = [
        await service.extract_entities_from_document(
            document=document, parsed_payload=payload, tenant_id=document.tenant_id
        )
        for _ in range(2)
    ]

    assert summaries[0] == summaries[1] == {
        "stakeholders": 0,
        "wbs_items": 0,
        "bom_items": 0,
        "schedule_activities": 0,
        "budget_lines": 2,
    }
