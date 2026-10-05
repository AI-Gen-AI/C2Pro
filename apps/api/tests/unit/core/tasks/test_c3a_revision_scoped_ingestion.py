"""C3a: every ingestion path is scoped to exactly one revision (TS-UT-C3A-INGEST-001).

* A legacy delivery without ``revision_id`` acquires its processing authority FOR
  the revision it resolved and ingests, so the analysis that follows is pinned to
  it (never an unbound authority -> unbound artifact).
* RAG readiness counts only the chunks of the revision being analysed: retained
  chunks of a trusted V1 never make a V2 whose embedding failed look ready.
* The synchronous parse path stamps its chunks and parsed text with the revision
  it resolved, so a re-parse never replaces trusted V1 chunks with unstamped ones.
"""

from __future__ import annotations

import contextlib
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from src.core.processing_authority import ProcessingAuthority, ProcessingStage
from src.core.tasks import ingestion_tasks
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.temporal.domain.document_revision import DocumentRevision

pytestmark = pytest.mark.asyncio


def _document(status: DocumentStatus, **metadata: object) -> Document:
    return Document(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=status,
        created_by=uuid4(),
        document_metadata={"parsed_text": "contract text", **metadata},
    )


def _revision(document: Document) -> DocumentRevision:
    now = datetime.now(UTC).replace(tzinfo=None)
    return DocumentRevision(
        revision_id=uuid4(),
        document_id=document.id,
        project_id=document.project_id,
        tenant_id=document.tenant_id,
        rev_no=2,
        parent_revision_id=uuid4(),
        blob_hash="b" * 64,
        blob_key="revisions/b",
        valid_from=now,
        created_at=now,
    )


def _session_factory(session: AsyncMock) -> Any:
    @asynccontextmanager
    async def _ctx():  # noqa: ANN202
        yield session

    return _ctx


async def test_legacy_delivery_acquires_authority_for_the_resolved_revision() -> None:
    document = _document(DocumentStatus.UPLOADED)
    current = _revision(document)
    repo = Mock()
    repo.get_by_id_internal = AsyncMock(return_value=document)
    repo.get_project_tenant_id = AsyncMock(return_value=document.tenant_id)
    repo.update_status = AsyncMock()

    class _Lineage:
        def __init__(self, _session: object) -> None:
            pass

        async def get_current(self, _document_id: object, _tenant_id: object) -> DocumentRevision:
            return current

        async def get_by_id(self, _revision_id: object, _tenant_id: object) -> DocumentRevision:
            return current

    claimed: dict[str, Any] = {}

    async def _claim(_session: object, **kwargs: Any) -> tuple[None, str]:
        claimed.update(kwargs)
        return None, "busy"

    session = AsyncMock()
    with (
        patch.object(ingestion_tasks, "init_db", new=AsyncMock()),
        patch.object(ingestion_tasks, "get_raw_session", _session_factory(session)),
        patch.object(ingestion_tasks, "SqlAlchemyDocumentRepository", return_value=repo),
        patch.object(ingestion_tasks, "SqlAlchemyDocumentRevisionRepository", _Lineage),
        patch.object(ingestion_tasks, "_claim_processing", _claim),
    ):
        # A legacy message: no revision_id. The bytes come from the current revision...
        result = await ingestion_tasks._process(document.id)

    assert result["status"] == "busy"
    # ... and the authority is requested for exactly that revision.
    assert claimed["revision_id"] == current.revision_id


class _Count:
    def __init__(self, count: int) -> None:
        self._count = count

    def scalar_one(self) -> int:
        return self._count


async def test_rag_readiness_counts_only_the_analysed_revisions_chunks() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Count(0))
    revision_id = uuid4()

    count = await ingestion_tasks.get_document_rag_chunk_count(
        session=session, tenant_id=uuid4(), document_id=uuid4(), revision_id=revision_id
    )

    assert count == 0
    statement, params = session.execute.await_args.args
    assert params["revision_id"] == str(revision_id)
    assert "metadata ->> 'revision_id' = :revision_id" in str(statement)


async def test_analysis_readiness_is_scoped_to_the_authority_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document(DocumentStatus.PARSED_PENDING_ANALYSIS)
    revision_id = uuid4()
    grant = ProcessingAuthority(
        tenant_id=document.tenant_id,
        document_id=document.id,
        revision_id=revision_id,
        generation=1,
        stage=ProcessingStage.ANALYSIS,
        attempt_id=uuid4(),
        owner_token=uuid4(),
        fencing_token=1,
    )
    count = AsyncMock(return_value=0)
    monkeypatch.setattr(ingestion_tasks, "get_document_rag_chunk_count", count)
    repo = Mock()
    repo.update_status = AsyncMock()
    repo.update_metadata = AsyncMock()

    # Only the readiness query is under test; whatever happens after it is irrelevant.
    with contextlib.suppress(Exception):
        await ingestion_tasks._analyze_owned(
            session=AsyncMock(),
            repo=repo,
            document=document,
            tenant_id=document.tenant_id,
            document_id=document.id,
            orchestrator=None,
            automatic_retry_available=False,
            grant=grant,
        )

    assert count.await_args.kwargs["revision_id"] == revision_id


async def test_sync_parse_stamps_chunks_and_parsed_text_with_its_revision() -> None:
    from src.documents.application.parse_document_use_case import ParseDocumentUseCase

    document = _document(DocumentStatus.UPLOADED)
    revision = _revision(document)
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=document)
    repo.update_status = AsyncMock()
    repo.update_metadata = AsyncMock()
    repo.commit = AsyncMock()
    revisions = MagicMock()
    revisions.get_current = AsyncMock(return_value=revision)
    rag = MagicMock()
    rag.ingest_document_chunks = AsyncMock()
    parser = MagicMock()
    parser.parse_document_file = AsyncMock(
        return_value={"text_blocks": [{"text": "The contractor pays a delay penalty."}]}
    )
    extraction = MagicMock()
    extraction.extract_entities_from_document = AsyncMock()

    with patch(
        "src.documents.application.parse_document_use_case.fetch_source_file",
        new=AsyncMock(return_value=Path("/tmp/contract.pdf")),
    ):
        await ParseDocumentUseCase(
            document_repository=repo,
            storage_service=MagicMock(),
            file_parser_service=parser,
            entity_extraction_service=extraction,
            rag_ingestion_service=rag,
            revision_repository=revisions,
        ).execute(document.tenant_id, document.id, uuid4())

    assert rag.ingest_document_chunks.await_args.kwargs["revision_id"] == revision.revision_id
    metadata = repo.update_metadata.await_args.args[2]
    assert metadata["parsed_text_revision_id"] == str(revision.revision_id)
