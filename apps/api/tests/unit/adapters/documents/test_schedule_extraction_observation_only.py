"""#852: schedule entity extraction observes activities and never writes canonical WBS.

Supersedes TS-UD-PROC-WBS-IDEM-001 ("a re-parse replaces the schedule's own WBS
rows"). That replacement deleted the previous rows WITH THEIR SUBTREES -- human
children, their manually verified RACI and BOM links included -- and created a
project's first WBS from a schedule. A schedule activity is not a WBS node, so
there is nothing to replace: reparse idempotency is now trivially "no WBS write,
same observation" (the real-DB proof is
``tests/integration/document_flow/test_852_schedule_wbs_governance_guard.py``).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.documents.adapters.extraction.documents_entity_extraction_service import (
    DocumentsEntityExtractionService,
)
from src.documents.domain.models import Document, DocumentStatus, DocumentType


class _ExplodingFactory:
    """Any use case requested for a schedule is a governance violation."""

    def __call__(self) -> object:
        raise AssertionError("schedule extraction must not request a write use case")


def _service() -> DocumentsEntityExtractionService:
    return DocumentsEntityExtractionService(
        stakeholder_use_case_factory=_ExplodingFactory(),
        user_id=uuid4(),
    )


def _schedule_document() -> Document:
    return Document(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_type=DocumentType.SCHEDULE,
        filename="schedule.xlsx",
        upload_status=DocumentStatus.PARSED,
    )


@pytest.mark.asyncio
async def test_schedule_reparse_is_stable_and_writes_no_wbs() -> None:
    service = _service()
    document = _schedule_document()
    payload = {
        "schedule": [
            {"task": "Mobilization", "wbs": "1"},
            {"task": "Excavation", "wbs": "1.1", "predecessors": "1"},
            {"description": "row with no task name is not an activity"},
        ]
    }

    first = await service.extract_entities_from_document(
        document=document, parsed_payload=payload, tenant_id=document.tenant_id
    )
    second = await service.extract_entities_from_document(
        document=document, parsed_payload=payload, tenant_id=document.tenant_id
    )

    assert first == second == {
        "stakeholders": 0,
        "wbs_items": 0,
        "bom_items": 0,
        "schedule_activities": 2,
        "budget_lines": 0,
    }


@pytest.mark.asyncio
async def test_schedule_with_only_unnamed_rows_observes_nothing() -> None:
    document = _schedule_document()

    summary = await _service().extract_entities_from_document(
        document=document,
        parsed_payload={"schedule": [{"note": "no task"}, {"note": "also none"}]},
        tenant_id=document.tenant_id,
    )

    assert summary["wbs_items"] == 0
    assert summary["schedule_activities"] == 0
