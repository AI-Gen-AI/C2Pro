"""
Documents → Analysis Integration Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-MOD-DOC-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from src.analysis.ports.orchestrator import AnalysisOrchestrator
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

    async def get_by_id(self, _document_id: UUID) -> Document | None:
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
        self, document_id: UUID, status: DocumentStatus, parsing_error: str | None = None
    ) -> None:
        raise NotImplementedError

    async def update_storage_path(self, document_id: UUID, storage_url: str) -> None:
        raise NotImplementedError

    async def update_version(
        self,
        document_id: UUID,
        version: int,
        file_hash: str,
        filename: str,
        status: DocumentStatus,
    ) -> Document:
        raise NotImplementedError

    async def delete(self, document_id: UUID) -> None:
        raise NotImplementedError

    async def list_for_project(self, project_id: UUID, skip: int, limit: int):
        raise NotImplementedError

    async def get_project_tenant_id(self, _project_id: UUID) -> UUID | None:
        return self.tenant_id

    async def add_clause(self, clause) -> None:
        raise NotImplementedError

    async def clause_exists(self, clause_id: UUID) -> bool:
        raise NotImplementedError

    async def get_clause_text_map(self, clause_ids):
        raise NotImplementedError

    async def get_clauses_by_ids(self, clause_ids):
        raise NotImplementedError

    async def get_clause_by_document_and_code(self, document_id: UUID, clause_code: str):
        raise NotImplementedError

    async def list_clauses_for_document(self, document_id: UUID):
        raise NotImplementedError

    async def commit(self) -> None:
        raise NotImplementedError

    async def refresh(self, entity: object) -> None:
        raise NotImplementedError


class _CapturingOrchestrator(AnalysisOrchestrator):
    def __init__(self) -> None:
        self.last_state: dict | None = None
        self.last_thread_id: str | None = None

    async def run(self, initial_state: dict, thread_id: str) -> dict:
        self.last_state = initial_state
        self.last_thread_id = thread_id
        return {"analysis_id": "analysis-123"}


@pytest.mark.asyncio
class TestDocumentsAnalysisIntegration:
    """Refers to Suite ID: TS-INT-MOD-DOC-001."""

    async def test_triggers_analysis_with_parsed_document_text(self) -> None:
        document_id = uuid4()
        project_id = uuid4()
        tenant_id = uuid4()

        document = Document(
            id=document_id,
            project_id=project_id,
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.PARSED,
            document_metadata={"parsed_text": "Extracted contract text"},
        )

        repo = _FakeDocumentRepository(document=document, tenant_id=tenant_id)
        orchestrator = _CapturingOrchestrator()
        use_case = TriggerDocumentAnalysisUseCase(repo, orchestrator)

        result = await use_case.execute(document_id=document_id)

        assert result["analysis_id"] == "analysis-123"
        assert orchestrator.last_state["document_text"] == "Extracted contract text"
        assert orchestrator.last_state["project_id"] == str(project_id)
        assert orchestrator.last_state["document_id"] == str(document_id)
        assert orchestrator.last_state["tenant_id"] == str(tenant_id)
        assert orchestrator.last_thread_id == str(project_id)

    async def test_raises_when_document_missing(self) -> None:
        repo = _FakeDocumentRepository(document=None, tenant_id=uuid4())
        use_case = TriggerDocumentAnalysisUseCase(repo, _CapturingOrchestrator())

        with pytest.raises(ValueError):
            await use_case.execute(document_id=uuid4())

    async def test_raises_when_parsed_text_missing(self) -> None:
        document = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.PARSED,
            document_metadata={},
        )
        repo = _FakeDocumentRepository(document=document, tenant_id=uuid4())
        use_case = TriggerDocumentAnalysisUseCase(repo, _CapturingOrchestrator())

        with pytest.raises(ValueError):
            await use_case.execute(document_id=document.id)

    async def test_raises_when_document_is_not_parsed(self) -> None:
        document = Document(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.QUEUED,
            document_metadata={"parsed_text": "Extracted contract text"},
        )
        repo = _FakeDocumentRepository(document=document, tenant_id=uuid4())
        use_case = TriggerDocumentAnalysisUseCase(repo, _CapturingOrchestrator())

        with pytest.raises(ValueError, match="document must be parsed before analysis"):
            await use_case.execute(document_id=document.id)
