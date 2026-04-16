"""Unit tests for IngestionPortAdapter.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

import pytest

from src.modules.decision_intelligence.adapters.ports.ingestion_port_adapter import (
    IngestionPortAdapter,
)


@pytest.mark.asyncio
async def test_ingest_document_returns_empty_result_for_empty_bytes() -> None:
    adapter = IngestionPortAdapter()
    result = await adapter.ingest_document(b"")
    assert result == {"chunks": [], "page_count": 0, "source": "empty"}


@pytest.mark.asyncio
async def test_ingest_document_falls_back_to_plaintext_when_not_pdf() -> None:
    adapter = IngestionPortAdapter(chunk_chars=20, chunk_overlap=5)
    text = "Clause A. " * 10
    result = await adapter.ingest_document(text.encode("utf-8"))

    assert result["source"] == "plaintext"
    assert result["page_count"] == 1
    assert len(result["chunks"]) >= 1
    for chunk in result["chunks"]:
        assert chunk["page"] == 1
        assert chunk["text"]
        assert "offset" in chunk


@pytest.mark.asyncio
async def test_ingest_document_chunks_respect_overlap() -> None:
    adapter = IngestionPortAdapter(chunk_chars=10, chunk_overlap=3)
    data = "abcdefghijabcdefghij"
    result = await adapter.ingest_document(data.encode("utf-8"))
    offsets = [c["offset"] for c in result["chunks"]]
    assert offsets[0] == 0
    # step = chunk_chars - overlap = 7
    assert offsets[1] == 7


@pytest.mark.asyncio
async def test_chunk_chars_must_be_positive() -> None:
    with pytest.raises(ValueError):
        IngestionPortAdapter(chunk_chars=0)


@pytest.mark.asyncio
async def test_chunk_overlap_must_be_less_than_chunk_chars() -> None:
    with pytest.raises(ValueError):
        IngestionPortAdapter(chunk_chars=10, chunk_overlap=10)
