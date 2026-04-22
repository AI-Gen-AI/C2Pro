"""Tests for :meth:`PgvectorEmbeddingRepository.load_embeddings_batch`.

Verifies the parser correctly converts pgvector's text output back into
Python floats, skips rows missing a vector, and enforces tenant isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest

from src.coherence.adapters.persistence.pgvector_embedding_repository import (
    PgvectorEmbeddingRepository,
)


@dataclass
class _Row:
    values: tuple[Any, ...]

    def __getitem__(self, idx: int) -> Any:
        return self.values[idx]


class _FakeResult:
    def __init__(self, rows: list[_Row]) -> None:
        self._rows = rows

    def fetchall(self) -> list[_Row]:
        return self._rows


class _FakeSession:
    """Minimal stand-in for ``AsyncSession.execute`` — returns canned rows."""

    def __init__(self, rows: list[_Row]) -> None:
        self._rows = rows
        self.last_bindparams: dict[str, Any] | None = None

    async def execute(self, _stmt: Any, bindparams: dict[str, Any]) -> _FakeResult:
        self.last_bindparams = bindparams
        return _FakeResult(self._rows)


@pytest.mark.asyncio
class TestLoadEmbeddingsBatch:
    async def test_returns_empty_dict_for_no_ids(self) -> None:
        session = _FakeSession(rows=[])
        repo = PgvectorEmbeddingRepository(session=session, tenant_id=None)

        result = await repo.load_embeddings_batch(
            clause_ids=[], project_id=uuid4()
        )

        assert result == {}

    async def test_parses_pgvector_text_into_float_list(self) -> None:
        rows = [
            _Row(values=("BUD-001", "[0.1,0.2,0.3]")),
            _Row(values=("BUD-002", "[1.0, 2.0, 3.0]")),
        ]
        session = _FakeSession(rows=rows)
        repo = PgvectorEmbeddingRepository(session=session, tenant_id=None)

        result = await repo.load_embeddings_batch(
            clause_ids=["BUD-001", "BUD-002"],
            project_id=uuid4(),
        )

        assert result == {
            "BUD-001": [0.1, 0.2, 0.3],
            "BUD-002": [1.0, 2.0, 3.0],
        }

    async def test_omits_rows_without_vector(self) -> None:
        rows = [
            _Row(values=("A", "[0.5,0.5]")),
            _Row(values=("B", None)),
            _Row(values=("C", "")),
        ]
        session = _FakeSession(rows=rows)
        repo = PgvectorEmbeddingRepository(session=session, tenant_id=None)

        result = await repo.load_embeddings_batch(
            clause_ids=["A", "B", "C"], project_id=uuid4()
        )

        assert result == {"A": [0.5, 0.5]}

    async def test_skips_unparseable_rows_without_raising(self) -> None:
        rows = [
            _Row(values=("OK", "[0.1,0.2]")),
            _Row(values=("BAD", "[oops,nan-values]")),
        ]
        session = _FakeSession(rows=rows)
        repo = PgvectorEmbeddingRepository(session=session, tenant_id=None)

        result = await repo.load_embeddings_batch(
            clause_ids=["OK", "BAD"], project_id=uuid4()
        )

        assert "OK" in result
        assert "BAD" not in result

    async def test_enforces_tenant_isolation_when_tenant_set(self) -> None:
        rows = [_Row(values=("X", "[1.0]"))]
        session = _FakeSession(rows=rows)
        repo = PgvectorEmbeddingRepository(session=session, tenant_id=uuid4())

        async def _reject_tenant(_project_id):
            return False

        repo._verify_project_tenant = _reject_tenant  # type: ignore[method-assign]

        with pytest.raises(PermissionError):
            await repo.load_embeddings_batch(
                clause_ids=["X"], project_id=uuid4()
            )
