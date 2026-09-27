"""#712: `_run_document_analysis` must durably mark a genuinely incomplete,
non-HITL analysis attempt so the Documents list can tell "failed, retry me"
apart from "hasn't started" and from "paused for a human review" -- without
adding a new stored DocumentStatus for it. `_process` must clear a stale flag
at the start of every fresh parse pass, so a re-upload/reprocess is never
haunted by a prior attempt's failure.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.tasks import ingestion_tasks
from src.documents.domain.models import Document, DocumentStatus, DocumentType


class _FakeRepository:
    def __init__(self, document: Document) -> None:
        self.document = document
        self.updated_statuses: list[DocumentStatus] = []
        self.updated_metadata: list[dict[str, object]] = []

    async def get_by_id(self, _tenant_id: object, _document_id: object) -> Document:
        return self.document

    async def get_by_id_internal(self, _document_id: object) -> Document:
        return self.document

    async def update_status(
        self, _tenant_id: object, _document_id: object, status: DocumentStatus, **_: object
    ) -> None:
        self.updated_statuses.append(status)

    async def update_metadata(
        self, _tenant_id: object, _document_id: object, document_metadata: dict[str, object]
    ) -> None:
        self.updated_metadata.append(dict(document_metadata))
        self.document.document_metadata = dict(document_metadata)


class _FakeOrchestrator:
    def __init__(self, *, analysis_id: str | None, human_approval_required: bool) -> None:
        self._result = {
            "analysis_id": analysis_id,
            "human_approval_required": human_approval_required,
        }

    async def run(self, _initial_state: dict[str, object], *, thread_id: str) -> dict[str, object]:
        return self._result


def _parsed_document(**metadata_overrides: object) -> Document:
    return Document(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.PARSED_PENDING_ANALYSIS,
        created_by=uuid4(),
        document_metadata={"parsed_text": "Some contract text.", **metadata_overrides},
    )


def _session() -> AsyncMock:
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    return session


def _install(monkeypatch: pytest.MonkeyPatch, document: Document, *, chunk_count: int = 1) -> _FakeRepository:
    repository = _FakeRepository(document)
    session = _session()
    monkeypatch.setattr(ingestion_tasks, "init_db", AsyncMock())
    monkeypatch.setattr(ingestion_tasks, "get_raw_session", lambda: session)
    monkeypatch.setattr(
        ingestion_tasks, "SqlAlchemyDocumentRepository", lambda *, session: repository
    )
    monkeypatch.setattr(
        ingestion_tasks, "get_document_rag_chunk_count", AsyncMock(return_value=chunk_count)
    )
    return repository


@pytest.mark.asyncio
async def test_incomplete_non_hitl_attempt_sets_the_retryable_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An incomplete, non-HITL outcome is retryable, so `_run_document_analysis`
    raises to trigger Celery's autoretry -- but the degraded flag must already
    be durably committed before that raise (see the docstring on
    ``AnalysisIncompleteRetryableError``)."""
    document = _parsed_document()
    repository = _install(monkeypatch, document)
    orchestrator = _FakeOrchestrator(analysis_id=None, human_approval_required=False)

    with pytest.raises(ingestion_tasks.AnalysisIncompleteRetryableError):
        await ingestion_tasks._run_document_analysis(
            tenant_id=document.tenant_id, document_id=document.id, orchestrator=orchestrator
        )

    assert repository.updated_metadata[-1]["analysis_last_attempt_incomplete"] is True


@pytest.mark.asyncio
async def test_hitl_pause_never_sets_the_retryable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _parsed_document()
    repository = _install(monkeypatch, document)
    orchestrator = _FakeOrchestrator(analysis_id=None, human_approval_required=True)

    result = await ingestion_tasks._run_document_analysis(
        tenant_id=document.tenant_id, document_id=document.id, orchestrator=orchestrator
    )

    assert result["status"] == "waiting_for_review"
    assert not repository.updated_metadata or "analysis_last_attempt_incomplete" not in (
        repository.updated_metadata[-1]
    )


@pytest.mark.asyncio
async def test_successful_analysis_clears_a_previously_set_retryable_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _parsed_document(analysis_last_attempt_incomplete=True)
    repository = _install(monkeypatch, document)
    orchestrator = _FakeOrchestrator(analysis_id="analysis-1", human_approval_required=False)

    result = await ingestion_tasks._run_document_analysis(
        tenant_id=document.tenant_id, document_id=document.id, orchestrator=orchestrator
    )

    assert result["status"] == "completed"
    assert "analysis_last_attempt_incomplete" not in repository.updated_metadata[-1]


@pytest.mark.asyncio
async def test_fresh_parse_pass_clears_a_stale_retryable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    document = Document(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_type=DocumentType.SCHEDULE,
        filename="schedule.bc3",
        upload_status=DocumentStatus.ERROR,
        created_by=uuid4(),
        document_metadata={"analysis_last_attempt_incomplete": True},
    )
    repository = _FakeRepository(document)
    repository.get_project_tenant_id = AsyncMock(return_value=document.tenant_id)  # type: ignore[attr-defined]
    repository.list_clauses_for_document = AsyncMock(return_value=[])  # type: ignore[attr-defined]
    session = _session()

    monkeypatch.setattr(ingestion_tasks, "init_db", AsyncMock())
    monkeypatch.setattr(ingestion_tasks, "get_raw_session", lambda: session)
    monkeypatch.setattr(
        ingestion_tasks, "SqlAlchemyDocumentRepository", lambda *, session: repository
    )
    monkeypatch.setattr(
        ingestion_tasks,
        "build_storage_service",
        lambda: AsyncMock(),
    )
    monkeypatch.setattr(
        ingestion_tasks,
        "resolve_source_revision",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(ingestion_tasks, "fetch_source_file", AsyncMock(return_value="/tmp/fake"))
    monkeypatch.setattr(
        ingestion_tasks,
        "file_parser",
        AsyncMock(parse_document_file=AsyncMock(return_value={"text_blocks": []})),
    )

    class _NoOpEntityExtraction:
        async def extract_entities_from_document(self, **_: object) -> dict[str, object]:
            return {}

    monkeypatch.setattr(
        ingestion_tasks,
        "DocumentsEntityExtractionService",
        lambda **_: _NoOpEntityExtraction(),
    )

    class _NoOpRagIngestion:
        def __init__(self, **_: object) -> None:
            pass

        async def ingest_document_chunks(self, **_: object) -> object:
            from src.documents.ports.rag_ingestion_service import RagIngestionOutcome

            return type(
                "RagResult", (), {"outcome": RagIngestionOutcome.NOT_REQUIRED, "chunk_count": 0}
            )()

    monkeypatch.setattr(ingestion_tasks, "SqlAlchemyRagIngestionService", _NoOpRagIngestion)
    monkeypatch.setattr(
        ingestion_tasks,
        "TriggerDocumentAnalysisUseCase",
        lambda **_: AsyncMock(execute=AsyncMock(return_value={})),
    )

    await ingestion_tasks._process(document.id)

    final_metadata = repository.updated_metadata[-1]
    assert "analysis_last_attempt_incomplete" not in final_metadata
