"""PC-2b.4 (#923) review corrections -- database part (TS-INT-PC2B4-REVIEW-CORRECTIONS-001).

* Finding 1: a review with different ``ReviewLimits`` is a NEW run; the same inputs with the same
  execution configuration reuse the run; FAILED runs are still never reused.
* Finding 2: ``ManifestScopedChunkReader`` bounds the result INSIDE SQL (per document and in total,
  deterministic order), matches the exact authorized (document, revision) pairs in SQL, never fails
  on a malformed or oversized ``chunk_index`` and still excludes unstamped legacy chunks. Rows are
  counted at the session boundary, so a Python-side filter cannot hide an unbounded read.

Runs under the privileged (BYPASSRLS) test role; the NOBYPASSRLS wall is
tests/integration/product_control/test_pc2b4_reviewer_retrieval_rls_db.py.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.wbs.adapters.persistence.intelligence_models import WBSIntelligenceRunORM
from src.wbs.intelligence.reviewer.evidence import ManifestScopedChunkReader
from src.wbs.intelligence.reviewer.limits import ReviewLimits, execution_config_digest
from src.wbs.intelligence.reviewer.model_port import ReviewTask
from src.wbs.intelligence.reviewer.service import ReviewTargetKind
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import _scope
from tests.modules.integration.test_pc2b4_wbs_reviewer import (
    _chunk,
    _count,
    _document,
    _model,
    _reviewer,
    _world,
)

pytestmark = pytest.mark.asyncio


# =========================================================================== Finding 1
async def _review(db: AsyncSession, s: Any, change_set_id: UUID, ids: dict[str, UUID],
                  limits: ReviewLimits | None = None, model: Any = None) -> Any:
    result = await _reviewer(db, model or _model(ids), limits=limits).review(
        project_id=s.project, tenant_id=s.tenant, actor=s.author, target=ReviewTargetKind.DRAFT,
        change_set_id=change_set_id)
    await db.commit()
    return result


async def test_f1_different_limits_open_a_new_run_and_equal_limits_reuse_it(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    tight = ReviewLimits(max_calls=12, max_excerpts=10)
    first = await _review(db, s, change_set_id, ids)
    again = await _review(db, s, change_set_id, ids)
    assert not first.reused and again.reused and again.run.id == first.run.id

    other = await _review(db, s, change_set_id, ids, limits=tight)
    assert not other.reused and other.run.id != first.run.id  # different execution conditions: a new run
    assert other.run.idempotency_key != first.run.idempotency_key
    provenance = other.run.model_provenance or {}
    assert provenance["limits"]["max_calls"] == 12
    assert provenance["execution_config_digest"] == execution_config_digest(tight)

    reused = await _review(db, s, change_set_id, ids, limits=ReviewLimits(max_calls=12, max_excerpts=10))
    assert reused.reused and reused.run.id == other.run.id
    assert await _count(db, WBSIntelligenceRunORM, project_id=s.project) == 2


async def test_f1_a_failed_run_is_still_never_reused(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    limits = ReviewLimits(max_calls=10)
    broken = _model(ids)
    broken.script[ReviewTask.REDUCE] = ["not json"]
    failed = await _review(db, s, change_set_id, ids, limits=limits, model=broken)
    assert failed.run.status == "FAILED"
    retried = await _review(db, s, change_set_id, ids, limits=limits)
    assert not retried.reused and retried.run.id != failed.run.id and retried.run.status == "COMPLETED"


# =========================================================================== Finding 2
class _Rows:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _CountingSession:
    """Records how many rows the database returned -- before any Python-side filtering."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.returned: list[int] = []

    async def execute(self, *args: Any, **kwargs: Any) -> _Rows:
        rows = list((await self.session.execute(*args, **kwargs)).all())
        self.returned.append(len(rows))
        return _Rows(rows)


def _reader(db: AsyncSession) -> tuple[ManifestScopedChunkReader, _CountingSession]:
    counting = _CountingSession(db)
    return ManifestScopedChunkReader(counting), counting  # type: ignore[arg-type]


async def test_f2_more_chunks_than_the_limits_are_bounded_by_the_database(db: AsyncSession) -> None:
    s = await _scope(db)
    first = await _document(db, s, chunks=tuple(f"A{i:02d}" for i in range(12)))
    second = await _document(db, s, chunks=tuple(f"B{i:02d}" for i in range(12)))
    reader, counting = _reader(db)
    chunks = await reader.read(tenant_id=s.tenant, project_id=s.project, allowed=[first, second],
                               per_document=3, total=5)
    assert counting.returned == [5]  # bounded in SQL, not after materialization
    assert [c.content for c in chunks] == ["A00", "B00", "A01", "B01", "A02"]  # deterministic, fair, priority order
    again = await reader.read(tenant_id=s.tenant, project_id=s.project, allowed=[first, second],
                              per_document=3, total=5)
    assert [c.content for c in again] == [c.content for c in chunks]
    one = await reader.read(tenant_id=s.tenant, project_id=s.project, allowed=[first], per_document=3, total=40)
    assert [c.content for c in one] == ["A00", "A01", "A02"] and counting.returned[-1] == 3


async def test_f2_cross_paired_document_revision_metadata_is_excluded_by_sql(db: AsyncSession) -> None:
    s = await _scope(db)
    document_a, revision_a = await _document(db, s, chunks=("A current",))
    document_b, revision_b = await _document(db, s, chunks=("B current",))
    await _chunk(db, s.tenant, s.project, document_a, "A stamped with B's revision", {"revision_id": str(revision_b)})
    await _chunk(db, s.tenant, s.project, document_b, "B stamped with A's revision", {"revision_id": str(revision_a)})
    await _chunk(db, s.tenant, s.project, document_a, "A unstamped legacy", {"chunk_index": 0})
    await db.commit()
    reader, counting = _reader(db)
    chunks = await reader.read(tenant_id=s.tenant, project_id=s.project,
                               allowed=[(document_a, revision_a), (document_b, revision_b)])
    assert counting.returned == [2]  # the database never returns a cross-paired or unstamped row
    assert sorted(c.content for c in chunks) == ["A current", "B current"]
    assert {(c.document_id, c.revision_id) for c in chunks} == {(document_a, revision_a), (document_b, revision_b)}


async def test_f2_an_oversized_or_malformed_chunk_index_never_fails_the_query(db: AsyncSession) -> None:
    s = await _scope(db)
    document_id, revision_id = await _document(db, s, chunks=("ordered first",))
    for content, index in (("huge text index", "99999999999999999999999"), ("huge number index", 10 ** 30),
                           ("negative index", -1), ("fractional index", 1.5), ("textual index", "first"),
                           ("long digits", "9" * 5000)):
        await _chunk(db, s.tenant, s.project, document_id, content,
                     {"revision_id": str(revision_id), "chunk_index": index, "page": "9" * 5000,
                      "char_start": "9" * 5000, "char_end": "9" * 5000})
    await db.commit()
    reader, counting = _reader(db)
    chunks = await reader.read(tenant_id=s.tenant, project_id=s.project, allowed=[(document_id, revision_id)],
                               per_document=40, total=40)
    assert counting.returned == [7]
    assert chunks[0].content == "ordered first"  # a well-formed index sorts before the unusable ones
    assert all(c.page is None and c.char_start is None for c in chunks[1:])


async def test_f2_missing_tenant_or_project_is_refused_and_bounds_must_be_positive(db: AsyncSession) -> None:
    reader, counting = _reader(db)
    for tenant, project in ((None, uuid4()), (uuid4(), None)):
        with pytest.raises(ValueError):
            await reader.read(tenant_id=tenant, project_id=project, allowed=[(uuid4(), uuid4())])  # type: ignore[arg-type]
    for per_document, total in ((0, 5), (5, 0)):
        with pytest.raises(ValueError):
            await reader.read(tenant_id=uuid4(), project_id=uuid4(), allowed=[(uuid4(), uuid4())],
                              per_document=per_document, total=total)
    assert counting.returned == []  # refused before any query
