"""
C2PRO P0b RAG reprocess idempotency hotfix.

Production evidence: document_chunks went 23 -> 46 after a single reprocess
of the same immutable document. RagService.ingest_document appended a fresh
batch of chunks on every call without ever removing the prior batch.

Proves: ingesting the same document twice leaves exactly the LATEST batch's
chunk count in document_chunks, not the sum of both.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from src.core.auth.models import Tenant
from src.documents.adapters.persistence.models import DocumentChunkORM, DocumentORM
from src.documents.adapters.rag import rag_service as rag_service_module
from src.documents.adapters.rag.rag_service import RagService
from src.projects.adapters.persistence.models import ProjectORM

pytestmark = pytest.mark.asyncio


def _fake_embed(dimension: int = 1536):
    async def _embed(texts: list[str]) -> list[list[float]]:
        return [[0.001 * (i + 1)] * dimension for i, _ in enumerate(texts)]

    return _embed


async def _seed_document(db) -> tuple:
    tenant_id, project_id, document_id = uuid4(), uuid4(), uuid4()
    db.add(
        Tenant(
            id=tenant_id,
            name="RAG Idempotency Tenant",
            slug=f"rag-idem-{tenant_id.hex[:8]}",
            subscription_plan="professional",
            is_active=True,
        )
    )
    await db.commit()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant_id,
            name="RAG Idempotency Project",
            code="RAG-IDEM",
            start_date=datetime.now(),
        )
    )
    await db.commit()
    db.add(
        DocumentORM(
            id=document_id,
            tenant_id=tenant_id,
            project_id=project_id,
            document_type="contract",
            filename="rag-idempotency.pdf",
            upload_status="parsed_pending_analysis",
        )
    )
    await db.commit()
    return tenant_id, project_id, document_id


async def test_reprocessing_same_document_replaces_chunks_not_appends(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rag_service_module, "_embed_texts", _fake_embed())

    tenant_id, project_id, document_id = await _seed_document(db)
    service = RagService(db_session=db)

    # Long enough text to split into multiple chunks (chunk_size=1000).
    text_content = ("Contract clause text for RAG ingestion. " * 60).strip()

    first_count = await service.ingest_document(
        tenant_id=tenant_id,
        document_id=document_id,
        project_id=project_id,
        text_content=text_content,
        metadata={"document_type": "contract"},
    )
    assert first_count > 0

    from sqlalchemy import select

    rows_after_first = (
        await db.execute(
            select(DocumentChunkORM).where(DocumentChunkORM.document_id == document_id)
        )
    ).scalars().all()
    assert len(rows_after_first) == first_count

    # Reprocess: same document, same content (immutable document -> same
    # chunk plan), simulating the exact production scenario.
    second_count = await service.ingest_document(
        tenant_id=tenant_id,
        document_id=document_id,
        project_id=project_id,
        text_content=text_content,
        metadata={"document_type": "contract"},
    )
    assert second_count == first_count

    rows_after_second = (
        await db.execute(
            select(DocumentChunkORM).where(DocumentChunkORM.document_id == document_id)
        )
    ).scalars().all()
    assert len(rows_after_second) == first_count, (
        f"reprocess must replace, not append: expected {first_count} chunks, "
        f"found {len(rows_after_second)} (production regression was 23 -> 46)"
    )

    # The actual row ids must differ (delete+insert, not a no-op skip) --
    # proves the replace really happened rather than accidentally matching
    # counts by coincidence.
    ids_after_first = {row.id for row in rows_after_first}
    ids_after_second = {row.id for row in rows_after_second}
    assert ids_after_first.isdisjoint(ids_after_second)


async def test_reprocessing_with_different_content_still_replaces_not_appends(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reprocess that legitimately changes chunk count (different content)
    must still fully replace the prior set, never leaving stale chunks
    mixed in alongside the new ones.
    """
    monkeypatch.setattr(rag_service_module, "_embed_texts", _fake_embed())

    tenant_id, project_id, document_id = await _seed_document(db)
    service = RagService(db_session=db)

    short_text = "Short clause text."
    long_text = ("Longer contract clause text for RAG ingestion. " * 80).strip()

    first_count = await service.ingest_document(
        tenant_id=tenant_id,
        document_id=document_id,
        project_id=project_id,
        text_content=short_text,
    )
    second_count = await service.ingest_document(
        tenant_id=tenant_id,
        document_id=document_id,
        project_id=project_id,
        text_content=long_text,
    )
    assert second_count > first_count

    from sqlalchemy import select

    rows = (
        await db.execute(
            select(DocumentChunkORM).where(DocumentChunkORM.document_id == document_id)
        )
    ).scalars().all()
    assert len(rows) == second_count, "stale chunks from the first ingestion must be gone"
