"""TS-UD-PROC-WBS-IDEM-001: schedule entity extraction replaces WBS rows per source document."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.documents.adapters.extraction.documents_entity_extraction_service import (
    DocumentsEntityExtractionService,
)
from src.documents.domain.models import Document, DocumentStatus, DocumentType


class _FakeWBSUseCase:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def replace_for_source_document(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs["wbs_items"]


@pytest.mark.asyncio
async def test_schedule_extraction_replaces_wbs_rows_once_per_source_document() -> None:
    """TS-UD-PROC-WBS-IDEM-001: reparse persistence is scoped to the source schedule document.

    Guards the two live bugs: a schedule re-parse must replace its own WBS rows
    (no uq_procurement_wbs_project_code collision) and every row must carry the
    source_document_id that the FK cascade relies on when the document is deleted.
    """
    tenant_id = uuid4()
    project_id = uuid4()
    document_id = uuid4()
    wbs_use_case = _FakeWBSUseCase()
    service = DocumentsEntityExtractionService(
        stakeholder_use_case_factory=lambda: object(),
        wbs_use_case_factory=lambda: wbs_use_case,
        bom_use_case_factory=lambda: object(),
        user_id=uuid4(),
    )
    document = Document(
        id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_type=DocumentType.SCHEDULE,
        filename="schedule.xlsx",
        upload_status=DocumentStatus.PARSED,
    )

    summary = await service.extract_entities_from_document(
        document=document,
        parsed_payload={
            "schedule": [
                {"task": "Mobilization"},
                {"task": "Excavation"},
                {"description": "row with no task name is skipped"},
            ]
        },
        tenant_id=tenant_id,
    )

    assert summary["wbs_items"] == 2
    # Exactly one persistence call — the whole schedule is replaced atomically.
    assert len(wbs_use_case.calls) == 1
    call = wbs_use_case.calls[0]
    assert call["project_id"] == project_id
    assert call["source_document_id"] == document_id
    assert call["tenant_id"] == tenant_id
    assert [item.wbs_code for item in call["wbs_items"]] == ["SCH-001", "SCH-002"]
    assert all(item.source_document_id == document_id for item in call["wbs_items"])


@pytest.mark.asyncio
async def test_schedule_with_only_unnamed_rows_persists_nothing() -> None:
    """TS-UD-PROC-WBS-IDEM-001: a schedule whose rows lack task names triggers no WBS write."""
    wbs_use_case = _FakeWBSUseCase()
    service = DocumentsEntityExtractionService(
        stakeholder_use_case_factory=lambda: object(),
        wbs_use_case_factory=lambda: wbs_use_case,
        bom_use_case_factory=lambda: object(),
        user_id=uuid4(),
    )
    document = Document(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_type=DocumentType.SCHEDULE,
        filename="schedule.xlsx",
        upload_status=DocumentStatus.PARSED,
    )

    summary = await service.extract_entities_from_document(
        document=document,
        parsed_payload={"schedule": [{"note": "no task"}, {"note": "also none"}]},
        tenant_id=document.tenant_id,
    )

    assert summary["wbs_items"] == 0
    assert wbs_use_case.calls == []
