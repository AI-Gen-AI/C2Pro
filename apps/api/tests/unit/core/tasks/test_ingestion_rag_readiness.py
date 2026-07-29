"""TS-UD-OPS-DOCFLOW-B-001: document analysis waits for committed RAG evidence."""

from __future__ import annotations

from uuid import uuid4

import pytest


class _ScalarResult:
    def __init__(self, count: int) -> None:
        self._count = count

    def scalar_one(self) -> int:
        return self._count


class _ChunkCountSession:
    def __init__(self, counts: list[int]) -> None:
        self._counts = iter(counts)
        self.params: list[dict[str, str]] = []

    async def execute(self, _statement: object, params: dict[str, str]) -> _ScalarResult:
        self.params.append(params)
        return _ScalarResult(next(self._counts))


@pytest.mark.asyncio
async def test_rag_readiness_counts_committed_tenant_scoped_chunks() -> None:
    """TS-UD-OPS-DOCFLOW-B-001: analysis reads only committed tenant-scoped evidence."""
    from src.core.tasks.ingestion_tasks import get_document_rag_chunk_count

    tenant_id = uuid4()
    document_id = uuid4()
    session = _ChunkCountSession([3])

    chunk_count = await get_document_rag_chunk_count(
        session=session,
        tenant_id=tenant_id,
        document_id=document_id,
    )

    assert chunk_count == 3
    assert session.params == [
        {"tenant_id": str(tenant_id), "document_id": str(document_id)},
    ]


@pytest.mark.asyncio
async def test_rag_readiness_returns_zero_when_no_chunks_are_committed() -> None:
    """TS-UD-OPS-DOCFLOW-B-001: an unavailable embedding is never analyzed as empty context."""
    from src.core.tasks.ingestion_tasks import get_document_rag_chunk_count

    chunk_count = await get_document_rag_chunk_count(
        session=_ChunkCountSession([0]),
        tenant_id=uuid4(),
        document_id=uuid4(),
    )

    assert chunk_count == 0
