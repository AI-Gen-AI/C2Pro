"""Unit coverage for SqlAlchemyReviewQueueRepository.claim_checkpoint_lineage (#758).

Against a mocked AsyncSession -- both the tenant-scoped and tenant-less
branches, plus the not-found refusal -- without a real database. The
behavioural proof that a takeover actually rebinds the review lives in
tests/integration/document_flow/test_758_checkpoint_lineage_authority_fence.py.

This method exists because `update_review_item` deliberately refuses to null
the checkpoint columns (`if checkpoint_id is not None`), so it cannot express
"this lineage is superseded, drop its checkpoint".
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.hitl.adapters.persistence.repository import (
    SqlAlchemyReviewQueueRepository,
)


def _session_returning(orm_row: object | None) -> AsyncMock:
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.first.return_value = orm_row
    session.execute = AsyncMock(return_value=execute_result)
    return session


def _orm() -> MagicMock:
    orm = MagicMock()
    orm.thread_id = "document:old:g1:f1:analysis"
    orm.checkpoint_id = "superseded-cp"
    return orm


async def test_claim_rebinds_the_thread_and_clears_the_superseded_checkpoint() -> None:
    """The checkpoint id MUST be nulled: it names a checkpoint on the old thread.

    Leaving it would produce a (new thread, old checkpoint) pair that does not
    exist and that CheckpointService correctly refuses to restore -- an
    unapprovable review.
    """
    orm = _orm()
    session = _session_returning(orm)
    repo = SqlAlchemyReviewQueueRepository(session=session, tenant_id=uuid4())

    await repo.claim_checkpoint_lineage(row_id=uuid4(), thread_id="document:new:g1:f2:analysis")

    assert orm.thread_id == "document:new:g1:f2:analysis"
    assert orm.checkpoint_id is None
    session.flush.assert_awaited_once()


async def test_claim_works_without_a_tenant_scope() -> None:
    orm = _orm()
    session = _session_returning(orm)
    repo = SqlAlchemyReviewQueueRepository(session=session, tenant_id=None)

    await repo.claim_checkpoint_lineage(row_id=uuid4(), thread_id="t-new")

    assert orm.thread_id == "t-new"
    assert orm.checkpoint_id is None


async def test_claim_refuses_a_missing_row() -> None:
    """Fail closed rather than silently claiming nothing."""
    session = _session_returning(None)
    repo = SqlAlchemyReviewQueueRepository(session=session, tenant_id=uuid4())
    row_id = uuid4()

    with pytest.raises(ValueError, match=str(row_id)):
        await repo.claim_checkpoint_lineage(row_id=row_id, thread_id="t-new")

    session.flush.assert_not_awaited()
