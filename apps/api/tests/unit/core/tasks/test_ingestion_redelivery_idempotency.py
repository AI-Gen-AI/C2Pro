"""#711 RED contracts for duplicate delivery and obsolete revision fencing."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest

from src.core.tasks.ingestion_tasks import _process, _run_document_analysis
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.documents.ports.rag_ingestion_service import (
    RagIngestionOutcome,
    RagIngestionResult,
)
from src.temporal.domain.document_revision import DocumentRevision


def _document(*, status: DocumentStatus, document_id: UUID | None = None) -> Document:
    return Document(
        id=document_id or uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=status,
        created_by=uuid4(),
        document_metadata={"parsed_text": "contract text"},
    )


def _session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _session_factory(session: AsyncMock):
    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx




@pytest.mark.asyncio
async def test_same_document_delivery_twice_emits_durable_seams_once() -> None:
    """The second delivery after the ingestion commit is a pure no-op."""
    document = _document(status=DocumentStatus.UPLOADED)
    session = _session()
    repo = Mock()
    repo.get_by_id_internal = AsyncMock(return_value=document)
    repo.get_project_tenant_id = AsyncMock(return_value=document.tenant_id)
    repo.list_clauses_for_document = AsyncMock(return_value=[])
    repo.add_clause = AsyncMock()
    repo.update_metadata = AsyncMock()

    async def _update_status(_tenant_id, _document_id, status, **_kwargs):
        document.upload_status = status

    repo.update_status = AsyncMock(side_effect=_update_status)

    class _NoRevisionLineage:
        def __init__(self, _session: object) -> None:
            pass

        async def get_current(self, _document_id: object, _tenant_id: object):
            return None

        async def get_by_id(self, _revision_id: object, _tenant_id: object):
            return None

    storage = Mock()
    storage.download_file = AsyncMock(return_value=Mock())
    parser = AsyncMock(return_value=_parsed_payload())
    extraction = AsyncMock(return_value={"stakeholders": 1})
    rag = AsyncMock(
        return_value=RagIngestionResult(
            outcome=RagIngestionOutcome.INGESTED,
            chunks=4,
        )
    )
    trigger = AsyncMock(return_value={"status": "started", "task_id": "analysis-1"})

    with (
        patch("src.core.tasks.ingestion_tasks.init_db", new=AsyncMock()),
        patch("src.core.tasks.ingestion_tasks.get_raw_session", _session_factory(session)),
        patch(
            "src.core.tasks.ingestion_tasks.SqlAlchemyDocumentRepository",
            return_value=repo,
        ),
        patch(
            "src.core.tasks.ingestion_tasks.SqlAlchemyDocumentRevisionRepository",
            _NoRevisionLineage,
        ),
        patch(
            "src.core.tasks.ingestion_tasks.build_storage_service",
            return_value=storage,
        ),
        patch(
            "src.core.tasks.ingestion_tasks.file_parser.parse_document_file",
            new=parser,
        ),
        patch(
            "src.core.tasks.ingestion_tasks.DocumentsEntityExtractionService"
        ) as extraction_cls,
        patch(
            "src.core.tasks.ingestion_tasks.SqlAlchemyRagIngestionService"
        ) as rag_cls,
        patch(
            "src.core.tasks.ingestion_tasks.TriggerDocumentAnalysisUseCase"
        ) as trigger_cls,
    ):
        extraction_cls.return_value.extract_entities_from_document = extraction
        rag_cls.return_value.ingest_document_chunks = rag
        trigger_cls.return_value.execute = trigger

        first = await _process(document.id)
        second = await _process(document.id)

    assert first["status"] == "success"
    assert second["status"] == "already_ingested"
    parser.assert_awaited_once()
    extraction.assert_awaited_once()
    rag.assert_awaited_once()
    trigger.assert_awaited_once()
    repo.update_metadata.assert_awaited_once()
    repo.list_clauses_for_document.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_status"),
    [
        (DocumentStatus.ANALYZED, "already_complete"),
        (DocumentStatus.PARSED_PENDING_ANALYSIS, "already_ingested"),
    ],
)
async def test_ingestion_redelivery_does_not_restart_completed_ingestion(
    status: DocumentStatus,
    expected_status: str,
) -> None:
    """ACK-loss redelivery must not parse/extract/chunk/trigger a second time."""
    document = _document(status=status)
    session = _session()
    repo = Mock()
    repo.get_by_id_internal = AsyncMock(return_value=document)
    repo.get_project_tenant_id = AsyncMock(return_value=document.tenant_id)
    repo.update_status = AsyncMock()

    with (
        patch("src.core.tasks.ingestion_tasks.init_db", new=AsyncMock()),
        patch("src.core.tasks.ingestion_tasks.get_raw_session", _session_factory(session)),
        patch(
            "src.core.tasks.ingestion_tasks.SqlAlchemyDocumentRepository",
            return_value=repo,
        ),
        patch(
            "src.core.tasks.ingestion_tasks.build_storage_service",
            side_effect=AssertionError("redelivery must not touch storage"),
        ),
        patch(
            "src.core.tasks.ingestion_tasks.TriggerDocumentAnalysisUseCase",
            side_effect=AssertionError("redelivery must not enqueue analysis"),
        ),
    ):
        result = await _process(document.id)

    assert result["status"] == expected_status
    repo.update_status.assert_not_called()


def _revision(
    *,
    revision_id: UUID,
    document: Document,
    rev_no: int,
    valid_to: datetime | None,
) -> DocumentRevision:
    return DocumentRevision(
        revision_id=revision_id,
        document_id=document.id,
        project_id=document.project_id,
        tenant_id=document.tenant_id,
        rev_no=rev_no,
        parent_revision_id=None,
        blob_hash=("a" if rev_no == 1 else "b") * 64,
        blob_key=f"revisions/{revision_id}.pdf",
        valid_from=datetime(2026, 9, 27, tzinfo=UTC),
        valid_to=valid_to,
        created_at=datetime(2026, 9, 27, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_obsolete_revision_redelivery_cannot_mutate_current_document() -> None:
    """A late task pinned to revision A must not overwrite revision B state."""
    document = _document(status=DocumentStatus.UPLOADED)
    old_id = uuid4()
    current_id = uuid4()
    old_revision = _revision(
        revision_id=old_id,
        document=document,
        rev_no=1,
        valid_to=datetime(2026, 9, 27, 8, 0, tzinfo=UTC),
    )
    current_revision = _revision(
        revision_id=current_id,
        document=document,
        rev_no=2,
        valid_to=None,
    )

    class _RevisionRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_id(self, revision_id: UUID, tenant_id: UUID):
            assert tenant_id == document.tenant_id
            return old_revision if revision_id == old_id else None

        async def get_current(self, document_id: UUID, tenant_id: UUID):
            assert document_id == document.id
            assert tenant_id == document.tenant_id
            return current_revision

    session = _session()
    repo = Mock()
    repo.get_by_id_internal = AsyncMock(return_value=document)
    repo.get_project_tenant_id = AsyncMock(return_value=document.tenant_id)
    repo.update_status = AsyncMock()

    with (
        patch("src.core.tasks.ingestion_tasks.init_db", new=AsyncMock()),
        patch("src.core.tasks.ingestion_tasks.get_raw_session", _session_factory(session)),
        patch(
            "src.core.tasks.ingestion_tasks.SqlAlchemyDocumentRepository",
            return_value=repo,
        ),
        patch(
            "src.core.tasks.ingestion_tasks.SqlAlchemyDocumentRevisionRepository",
            _RevisionRepo,
        ),
        patch(
            "src.core.tasks.ingestion_tasks.build_storage_service",
            side_effect=AssertionError("superseded revision must not touch storage"),
        ),
    ):
        result = await _process(document.id, old_id)

    assert result["status"] == "superseded"
    assert result["revision_id"] == str(old_id)
    assert result["current_revision_id"] == str(current_id)
    repo.update_status.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_analysis_delivery_short_circuits_terminal_document() -> None:
    """A duplicate analysis message must not rerun the graph after ANALYZED."""
    document = _document(status=DocumentStatus.ANALYZED)
    session = _session()
    repo = Mock()
    repo.get_by_id = AsyncMock(return_value=document)
    repo.update_status = AsyncMock()

    with (
        patch("src.core.tasks.ingestion_tasks.init_db", new=AsyncMock()),
        patch("src.core.tasks.ingestion_tasks.get_raw_session", _session_factory(session)),
        patch(
            "src.core.tasks.ingestion_tasks.SqlAlchemyDocumentRepository",
            return_value=repo,
        ),
        patch(
            "src.core.tasks.ingestion_tasks.get_document_rag_chunk_count",
            side_effect=AssertionError("duplicate analysis must not inspect RAG"),
        ),
    ):
        result = await _run_document_analysis(
            tenant_id=document.tenant_id,
            document_id=document.id,
            orchestrator=Mock(),
        )

    assert result["status"] == "already_complete"
    assert result["document_status"] == DocumentStatus.ANALYZED.value
    repo.update_status.assert_not_called()
