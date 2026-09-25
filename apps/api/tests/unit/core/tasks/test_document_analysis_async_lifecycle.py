"""TDD RED guards for document-analysis async resource ownership."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.analysis.adapters.graph import workflow
from src.core.tasks import ingestion_tasks
from src.documents.domain.models import Document, DocumentStatus, DocumentType


class LoopOwnershipError(RuntimeError):
    """A deterministic stand-in for an async resource bound to one loop."""


class ExpectedAnalysisFailure(RuntimeError):
    """The original analysis failure that must survive DLQ persistence."""


class _LoopBoundCheckpointer:
    def __init__(self) -> None:
        self.owner: asyncio.AbstractEventLoop | None = None

    async def checkpoint_write(self) -> None:
        current = asyncio.get_running_loop()
        if self.owner is None:
            self.owner = current
            return
        if self.owner is not current:
            raise LoopOwnershipError("checkpointer reused from a closed task loop")


class _CheckpointingGraph:
    def __init__(self, checkpointer: _LoopBoundCheckpointer) -> None:
        self.checkpointer = checkpointer

    async def ainvoke(self, _state: object, _config: object) -> dict[str, str]:
        await self.checkpointer.checkpoint_write()
        return {"analysis_id": "analysis-loop-safe"}


class _DocumentRepository:
    def __init__(self, document: Document) -> None:
        self.document = document
        self.updated_statuses: list[DocumentStatus] = []

    async def get_by_id(self, _tenant_id: object, _document_id: object) -> Document:
        return self.document

    async def update_status(
        self, _tenant_id: object, _document_id: object, status: DocumentStatus
    ) -> None:
        self.updated_statuses.append(status)


def _parsed_document() -> Document:
    return Document(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.PARSED_PENDING_ANALYSIS,
        created_by=uuid4(),
        document_metadata={"parsed_text": "Loop ownership contract text."},
    )


def _analysis_session() -> AsyncMock:
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    return session


@pytest.fixture(autouse=True)
def _restore_workflow_globals():
    original_pool = workflow._checkpointer_pool
    original_ready = workflow._checkpointer_ready
    original_graph = workflow._graph_app
    workflow._checkpointer_pool = None
    workflow._checkpointer_ready = False
    workflow._graph_app = None
    yield
    workflow._checkpointer_pool = original_pool
    workflow._checkpointer_ready = original_ready
    workflow._graph_app = original_graph


def _install_real_analysis_path_with_loop_bound_checkpointer(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Document, _DocumentRepository]:
    document = _parsed_document()
    repository = _DocumentRepository(document)
    session = _analysis_session()

    monkeypatch.setattr(ingestion_tasks, "init_db", AsyncMock())
    monkeypatch.setattr(ingestion_tasks, "get_raw_session", lambda: session)
    monkeypatch.setattr(
        ingestion_tasks,
        "SqlAlchemyDocumentRepository",
        lambda *, session: repository,
    )
    monkeypatch.setattr(ingestion_tasks, "get_document_rag_chunk_count", AsyncMock(return_value=1))
    monkeypatch.setattr(workflow, "ensure_checkpointer_ready", AsyncMock())
    monkeypatch.setattr(workflow, "_build_checkpointer", _LoopBoundCheckpointer)
    monkeypatch.setattr(
        workflow,
        "compile_workflow",
        lambda *, checkpointer, persist_diagram: _CheckpointingGraph(checkpointer),
    )

    class _WorkflowOrchestrator:
        async def run(
            self, initial_state: dict[str, object], *, thread_id: str
        ) -> dict[str, object]:
            return await workflow.run_orchestration(initial_state, thread_id)

    class _Factory:
        @staticmethod
        def create() -> _WorkflowOrchestrator:
            return _WorkflowOrchestrator()

    monkeypatch.setattr(ingestion_tasks, "AnalysisOrchestratorFactory", _Factory)
    monkeypatch.setattr(ingestion_tasks, "_push_trigger_failure_to_dlq", AsyncMock())
    return document, repository


def test_sequential_analysis_task_loops_do_not_reuse_a_loop_bound_checkpointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RED: each analysis task must own the saver used by its asyncio.run loop."""
    document, repository = _install_real_analysis_path_with_loop_bound_checkpointer(monkeypatch)
    task = SimpleNamespace(request=SimpleNamespace(id="analysis-loop-ownership"))

    first = ingestion_tasks.process_document_analysis_async(
        task, tenant_id=str(document.tenant_id), document_id=str(document.id)
    )
    second = ingestion_tasks.process_document_analysis_async(
        task, tenant_id=str(document.tenant_id), document_id=str(document.id)
    )

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert repository.updated_statuses == [DocumentStatus.ANALYZED, DocumentStatus.ANALYZED]


def test_analysis_failure_persists_dlq_in_the_analysis_resource_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RED: failure bookkeeping must not move a loop-owned DB session to another run."""
    analysis_loop: asyncio.AbstractEventLoop | None = None
    persisted: list[object] = []

    async def fail_analysis(**_kwargs: object) -> None:
        nonlocal analysis_loop
        analysis_loop = asyncio.get_running_loop()
        raise ExpectedAnalysisFailure("graph failed after task resources were opened")

    @asynccontextmanager
    async def loop_owned_tenant_session(_tenant_id: UUID):
        if analysis_loop is not asyncio.get_running_loop():
            raise LoopOwnershipError("DLQ persistence crossed into a second task loop")
        session = SimpleNamespace(
            add=lambda record: persisted.append(record),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        yield session

    monkeypatch.setattr(ingestion_tasks, "_run_document_analysis", fail_analysis)
    monkeypatch.setattr(
        "src.core.dlq.dlq_service.get_session_with_tenant", loop_owned_tenant_session
    )
    task = SimpleNamespace(request=SimpleNamespace(id="analysis-dlq-loop"))

    with pytest.raises(ExpectedAnalysisFailure):
        ingestion_tasks.process_document_analysis_async(
            task,
            tenant_id=str(uuid4()),
            document_id=str(uuid4()),
        )

    assert len(persisted) == 1


def test_process_document_async_does_not_enter_the_cached_analysis_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scope guard: real parsing does not enter the cached analysis graph."""
    document = _parsed_document()
    document.upload_status = DocumentStatus.QUEUED
    session = _analysis_session()
    repository = AsyncMock()
    repository.get_by_id_internal.return_value = document
    repository.get_project_tenant_id.return_value = document.tenant_id
    repository.list_clauses_for_document.return_value = []

    class _Extraction:
        extract_entities_from_document = AsyncMock(return_value={})

    class _Rag:
        ingest_document_chunks = AsyncMock(
            return_value=SimpleNamespace(outcome=ingestion_tasks.RagIngestionOutcome.INGESTED)
        )

    class _Trigger:
        execute = AsyncMock(
            return_value={"task_id": "queued", "task_name": "documents.analyze_document"}
        )

    def graph_must_not_be_constructed() -> object:
        raise AssertionError("process_document_async must not construct the analysis graph")

    monkeypatch.setattr(ingestion_tasks, "init_db", AsyncMock())
    monkeypatch.setattr(ingestion_tasks, "get_raw_session", lambda: session)
    monkeypatch.setattr(
        ingestion_tasks,
        "SqlAlchemyDocumentRepository",
        lambda *, session: repository,
    )
    monkeypatch.setattr(
        ingestion_tasks, "DocumentsEntityExtractionService", lambda **_kwargs: _Extraction()
    )
    monkeypatch.setattr(ingestion_tasks, "SqlAlchemyRagIngestionService", lambda **_kwargs: _Rag())
    monkeypatch.setattr(
        ingestion_tasks, "TriggerDocumentAnalysisUseCase", lambda **_kwargs: _Trigger()
    )
    monkeypatch.setattr(ingestion_tasks, "resolve_source_revision", AsyncMock(return_value=None))
    monkeypatch.setattr(
        ingestion_tasks, "fetch_source_file", AsyncMock(return_value="contract.pdf")
    )
    monkeypatch.setattr(
        ingestion_tasks.file_parser,
        "parse_document_file",
        AsyncMock(return_value={"text_blocks": [{"text": "contract text"}]}),
    )
    monkeypatch.setattr(workflow, "get_graph_app", graph_must_not_be_constructed)
    task = SimpleNamespace(request=SimpleNamespace(id="parse-scope-guard"))
    document_id = str(document.id)

    first = ingestion_tasks.process_document_async(task, document_id)
    second = ingestion_tasks.process_document_async(task, document_id)

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert workflow._graph_app is None
