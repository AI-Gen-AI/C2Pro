"""TS-INT-MOD-DOC-001: parsed documents enqueue full async analysis."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from src.documents.application.trigger_document_analysis_use_case import (
    TriggerDocumentAnalysisUseCase,
)
from src.documents.domain.models import Document, DocumentStatus, DocumentType


@dataclass
class _ParsedDocumentRepository:
    document: Document | None

    async def get_by_id(self, tenant_id: UUID, document_id: UUID) -> Document | None:
        assert tenant_id
        assert document_id
        return self.document


class _TaskStub:
    name = "documents.analyze_document"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def apply_async(self, *, kwargs: dict, queue: str):
        self.calls.append({"kwargs": kwargs, "queue": queue})
        return SimpleNamespace(id="analysis-task-123")


@pytest.mark.asyncio
async def test_trigger_enqueues_full_analysis_task_on_document_parsing_queue() -> None:
    tenant_id = uuid4()
    document_id = uuid4()
    document = Document(
        id=document_id,
        project_id=uuid4(),
        tenant_id=tenant_id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.PARSED_PENDING_ANALYSIS,
        document_metadata={"parsed_text": "Contract text"},
    )
    task = _TaskStub()
    use_case = TriggerDocumentAnalysisUseCase(
        document_repository=_ParsedDocumentRepository(document),
        analysis_task=task,
    )

    result = await use_case.execute(tenant_id=tenant_id, document_id=document_id)

    assert result == {
        "status": "queued",
        "task_id": "analysis-task-123",
        "task_name": "documents.analyze_document",
        "queue": "document_parsing",
    }
    assert task.calls == [
        {
            "kwargs": {
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
            },
            "queue": "document_parsing",
        }
    ]
