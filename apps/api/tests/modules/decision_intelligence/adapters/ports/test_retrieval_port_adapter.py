"""Unit tests for RetrievalPortAdapter.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.modules.decision_intelligence.adapters.ports.retrieval_port_adapter import (
    RetrievalPortAdapter,
)


class _FakeResult:
    def __init__(self, rows: list[tuple[str, float]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[str, float]]:
        return list(self._rows)


def _make_session(rows: list[tuple[str, float]]) -> SimpleNamespace:
    execute = AsyncMock(return_value=_FakeResult(rows))
    return SimpleNamespace(execute=execute)


def _session_provider(rows: list[tuple[str, float]]):
    @asynccontextmanager
    async def _provider():
        yield _make_session(rows)

    return _provider


@pytest.mark.asyncio
async def test_retrieve_returns_fallback_for_empty_query() -> None:
    adapter = RetrievalPortAdapter(
        session_provider=_session_provider([]),
        embed_fn=AsyncMock(),
    )
    result = await adapter.retrieve("")
    assert len(result) == 1
    assert result[0]["score"] == 0.5


@pytest.mark.asyncio
async def test_retrieve_returns_fallback_when_embedding_fails() -> None:
    adapter = RetrievalPortAdapter(
        session_provider=_session_provider([]),
        embed_fn=AsyncMock(side_effect=RuntimeError("embed fail")),
    )
    result = await adapter.retrieve("query")
    assert len(result) == 1
    assert "baseline" in result[0]["text"].lower()


@pytest.mark.asyncio
async def test_retrieve_maps_distance_to_score() -> None:
    rows = [("Evidence one", 0.2), ("Evidence two", 0.4)]
    adapter = RetrievalPortAdapter(
        session_provider=_session_provider(rows),
        embed_fn=AsyncMock(return_value=[[0.1] * 8]),
    )
    result = await adapter.retrieve("decision intelligence")
    assert [item["text"] for item in result] == ["Evidence one", "Evidence two"]
    assert result[0]["score"] == pytest.approx(0.8, rel=1e-3)
    assert result[1]["score"] == pytest.approx(0.6, rel=1e-3)


@pytest.mark.asyncio
async def test_retrieve_returns_fallback_on_db_error() -> None:
    @asynccontextmanager
    async def _broken_provider():
        raise RuntimeError("db fail")
        yield  # type: ignore[unreachable]

    adapter = RetrievalPortAdapter(
        session_provider=_broken_provider,
        embed_fn=AsyncMock(return_value=[[0.1] * 8]),
    )
    result = await adapter.retrieve("query")
    assert len(result) == 1
    assert result[0]["score"] == 0.5


@pytest.mark.asyncio
async def test_retrieve_returns_fallback_when_db_empty() -> None:
    adapter = RetrievalPortAdapter(
        session_provider=_session_provider([]),
        embed_fn=AsyncMock(return_value=[[0.1] * 4]),
    )
    result = await adapter.retrieve("query")
    assert len(result) == 1
    assert result[0]["score"] == 0.5
