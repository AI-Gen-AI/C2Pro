"""
Documents → Analysis Integration Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-MOD-DOC-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from src.documents.application.trigger_document_analysis_use_case import (
    TriggerDocumentAnalysisUseCase,
)
from src.documents.domain.models import (
    Document,
    DocumentAlertSignal,
    DocumentHistorySnapshot,
    DocumentStatus,
    DocumentType,
)
from src.documents.ports.document_repository import IDocumentRepository


@dataclass
class _FakeDocumentRepository(IDocumentRepository):
    document: Document | None
    tenant_id: UUID | None

    async def add(self, document: Document) -> None:
        raise NotImplementedError

    async def get_by_id(self, _tenant_id: UUID, _document_id: UUID) -> Document | None:
        return self.document

    async def get_by_id_internal(self, _document_id: UUID) -> Document | None:
        return self.document

    async def get_document_with_clauses(self, _document_id: UUID) -> Document | None:
        raise NotImplementedError

    async def get_history_snapshot(self, _document_id: UUID) -> DocumentHistorySnapshot | None:
        raise NotImplementedError

    async def list_alert_signals_for_document(
        self, _document_id: UUID
    ) -> list[DocumentAlertSignal]:
        raise NotImplementedError

    async def update_status(
        self,
        tenant_id: UUID,
        document_id: UUID,
        status: DocumentStatus,
        parsing_error: str | None = None,
        parsed_at=None,
    ) -> None:
        raise NotImplementedError

    async def update_metadata(
        self,
        tenant_id: UUID,
        document_id: UUID,
        document_metadata: dict,
    ) -> None:
        raise NotImplementedError

    async def update_storage_path(
        self,
        tenant_id: UUID,
        document_id: UUID,
        storage_url: str,
    ) -> None:
        raise NotImplementedError

    async def update_version(
        self,
        tenant_id: UUID,
        document_id: UUID,
        version: int,
        file_hash: str,
        filename: str,
        status: DocumentStatus,
    ) -> Document:
        raise NotImplementedError

    async def delete(self, tenant_id: UUID, document_id: UUID) -> None:
        raise NotImplementedError

    async def list_for_project(
        self,
        tenant_id: UUID,
        project_id: UUID,
        skip: int,
        limit: int,
    ):
        raise NotImplementedError

    async def get_project_tenant_id(self, _project_id: UUID) -> UUID | None:
        return self.tenant_id

    async def add_clause(self, tenant_id: UUID, clause) -> None:
        raise NotImplementedError

    async def clause_exists(self, tenant_id: UUID, clause_id: UUID) -> bool:
        raise NotImplementedError

    async def get_clause_text_map(self, tenant_id: UUID, clause_ids):
        raise NotImplementedError

    async def get_clauses_by_ids(self, tenant_id: UUID, clause_ids):
        raise NotImplementedError

    async def get_clause_by_document_and_code(
        self,
        tenant_id: UUID,
        document_id: UUID,
        clause_code: str,
    ):
        raise NotImplementedError

    async def list_clauses_for_document(self, tenant_id: UUID, document_id: UUID):
        raise NotImplementedError

    async def commit(self) -> None:
        raise NotImplementedError

    async def refresh(self, entity: object) -> None:
        raise NotImplementedError


class _TaskStub:
    name = "documents.analyze_document"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def apply_async(self, *, kwargs: dict, queue: str):
        self.calls.append({"kwargs": kwargs, "queue": queue})
        return type("AsyncResult", (), {"id": "analysis-task-123"})()


@pytest.mark.asyncio
class TestDocumentsAnalysisIntegration:
    """Refers to Suite ID: TS-INT-MOD-DOC-001."""

    async def test_triggers_analysis_task_with_parsed_document_text(self) -> None:
        document_id = uuid4()
        project_id = uuid4()
        tenant_id = uuid4()

        document = Document(
            id=document_id,
            project_id=project_id,
            tenant_id=tenant_id,
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.PARSED,
            document_metadata={"parsed_text": "Extracted contract text"},
        )

        repo = _FakeDocumentRepository(document=document, tenant_id=tenant_id)
        task = _TaskStub()
        use_case = TriggerDocumentAnalysisUseCase(repo, analysis_task=task)

        result = await use_case.execute(tenant_id=tenant_id, document_id=document_id)

        assert result["status"] == "queued"
        assert result["task_id"] == "analysis-task-123"
        assert task.calls == [
            {
                "kwargs": {
                    "tenant_id": str(tenant_id),
                    "document_id": str(document_id),
                },
                "queue": "document_parsing",
            }
        ]

    async def test_raises_when_document_missing(self) -> None:
        repo = _FakeDocumentRepository(document=None, tenant_id=uuid4())
        use_case = TriggerDocumentAnalysisUseCase(repo, analysis_task=_TaskStub())

        with pytest.raises(ValueError):
            await use_case.execute(tenant_id=repo.tenant_id, document_id=uuid4())

    async def test_enqueues_when_parsed_text_missing(self) -> None:
        """Structured docs (schedule/budget) carry no parsed_text; analysis is still
        enqueued so the best-effort analysis task can mark the document ANALYZED.

        Gating on parsed_text here stranded structured documents forever in
        parsed_pending_analysis and flooded the DLQ.
        """
        document = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.SCHEDULE,
            filename="schedule.xlsx",
            upload_status=DocumentStatus.PARSED,
            document_metadata={},
        )
        repo = _FakeDocumentRepository(document=document, tenant_id=document.tenant_id)
        task = _TaskStub()
        use_case = TriggerDocumentAnalysisUseCase(repo, analysis_task=task)

        result = await use_case.execute(tenant_id=document.tenant_id, document_id=document.id)

        assert result["status"] == "queued"
        assert task.calls == [
            {
                "kwargs": {
                    "tenant_id": str(document.tenant_id),
                    "document_id": str(document.id),
                },
                "queue": "document_parsing",
            }
        ]

    async def test_raises_when_document_is_not_parsed(self) -> None:
        document = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.QUEUED,
            document_metadata={"parsed_text": "Extracted contract text"},
        )
        repo = _FakeDocumentRepository(document=document, tenant_id=document.tenant_id)
        use_case = TriggerDocumentAnalysisUseCase(repo, analysis_task=_TaskStub())

        with pytest.raises(ValueError, match="document must be parsed before analysis"):
            await use_case.execute(tenant_id=document.tenant_id, document_id=document.id)
