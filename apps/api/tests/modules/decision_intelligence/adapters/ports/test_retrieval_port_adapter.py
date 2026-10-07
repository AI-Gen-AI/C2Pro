"""Unit tests for RetrievalPortAdapter.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.decision_intelligence.adapters.ports.retrieval_port_adapter import (
    RetrievalPortAdapter,
)

_SCOPE = {"tenant_id": uuid4(), "project_id": uuid4()}


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
    result = await adapter.retrieve("", **_SCOPE)
    assert len(result) == 1
    assert result[0]["score"] == 0.5


@pytest.mark.asyncio
async def test_retrieve_returns_fallback_when_embedding_fails() -> None:
    adapter = RetrievalPortAdapter(
        session_provider=_session_provider([]),
        embed_fn=AsyncMock(side_effect=RuntimeError("embed fail")),
    )
    result = await adapter.retrieve("query", **_SCOPE)
    assert len(result) == 1
    assert "baseline" in result[0]["text"].lower()


@pytest.mark.asyncio
async def test_retrieve_maps_distance_to_score() -> None:
    rows = [("Evidence one", 0.2), ("Evidence two", 0.4)]
    adapter = RetrievalPortAdapter(
        session_provider=_session_provider(rows),
        embed_fn=AsyncMock(return_value=[[0.1] * 8]),
    )
    result = await adapter.retrieve("decision intelligence", **_SCOPE)
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
    result = await adapter.retrieve("query", **_SCOPE)
    assert len(result) == 1
    assert result[0]["score"] == 0.5


@pytest.mark.asyncio
async def test_retrieve_returns_fallback_when_db_empty() -> None:
    adapter = RetrievalPortAdapter(
        session_provider=_session_provider([]),
        embed_fn=AsyncMock(return_value=[[0.1] * 4]),
    )
    result = await adapter.retrieve("query", **_SCOPE)
    assert len(result) == 1
    assert result[0]["score"] == 0.5


# --------------------------------------------------------------------------- P0 tenant scope
# The application role bypasses RLS: the tenant and project must be bound in the SQL itself.
@pytest.mark.asyncio
async def test_retrieve_binds_the_callers_tenant_and_project_in_sql() -> None:
    session = _make_session([("Evidence", 0.1)])

    @asynccontextmanager
    async def _provider():
        yield session

    tenant_id, project_id = uuid4(), uuid4()
    adapter = RetrievalPortAdapter(session_provider=_provider, embed_fn=AsyncMock(return_value=[[0.1] * 8]))
    await adapter.retrieve("query", tenant_id=tenant_id, project_id=project_id)

    statement, params = session.execute.await_args.args
    sql = " ".join(str(statement).split())
    assert "dc.tenant_id = CAST(:tenant_id AS uuid)" in sql
    assert "dc.project_id = CAST(:project_id AS uuid)" in sql
    assert params["tenant_id"] == str(tenant_id) and params["project_id"] == str(project_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["tenant_id", "project_id"])
async def test_retrieve_without_a_scope_fails_closed_without_querying(missing: str) -> None:
    session = _make_session([("Foreign evidence", 0.1)])

    @asynccontextmanager
    async def _provider():
        yield session

    embed = AsyncMock(return_value=[[0.1] * 8])
    adapter = RetrievalPortAdapter(session_provider=_provider, embed_fn=embed)
    scope = {"tenant_id": uuid4(), "project_id": uuid4(), missing: None}
    result = await adapter.retrieve("query", **scope)

    session.execute.assert_not_awaited()
    embed.assert_not_awaited()
    assert "Foreign evidence" not in [item["text"] for item in result]
