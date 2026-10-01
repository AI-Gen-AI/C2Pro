"""#758 P1-B: which lineages a direct HITL resume may resolve without a checkpoint id.

`CheckpointService` deliberately falls back to "latest checkpoint for this
thread" when no checkpoint id was recorded. Whether that is SAFE depends
entirely on whether the thread belonged to one processing attempt:

* `document:{uuid}:analysis` -- the pre-#758 DETERMINISTIC SHARED thread. Every
  attempt on that document wrote to it, so latest-by-thread can resolve a
  superseded attempt's checkpoint. Fail closed.
* `document:{uuid}:g{generation}:f{fence}:analysis` -- authority-scoped, so the
  thread holds exactly one attempt's checkpoints. Safe.
* a bare UUID thread -- production's legacy shape. Read-only inspection found 6
  pending analysis_critique reviews of exactly this shape, all with
  checkpoint_id NULL and all with checkpoint records; they resume only through
  this fallback, so it must keep working.

An explicit checkpoint id is always allowed: it names one exact checkpoint, and
CheckpointService already fails closed when the saver returns a different one.

The guard is asserted at its true boundary -- a refused lineage must never
reach the checkpointer at all.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.core import checkpoint_lineage as lineage
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowRequest,
    ResumeWorkflowUseCase,
    WorkflowDecision,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus

pytestmark = pytest.mark.asyncio


def _review(*, thread_id: str, checkpoint_id: str | None) -> ReviewItem:
    metadata: dict = {
        "document_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "thread_id": thread_id,
    }
    if checkpoint_id is not None:
        metadata["checkpoint_id"] = checkpoint_id
    return ReviewItem(
        item_id=uuid4(),
        item_type="contract",
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        confidence=0.42,
        impact_level=ImpactLevel.HIGH,
        created_at=datetime.now(UTC),
        sla_due_date=datetime.now(UTC) + timedelta(hours=24),
        metadata=metadata,
    )


def _use_case(review: ReviewItem) -> tuple[ResumeWorkflowUseCase, MagicMock]:
    repo = AsyncMock()
    repo.get_review_item.return_value = review
    repo.tenant_id = uuid4()
    checkpoint_service = MagicMock()
    # Returning None stops the run right after restore, which keeps the
    # assertion boundary exactly where the guard is: was the checkpointer
    # consulted at all, and with what?
    checkpoint_service.restore_checkpoint = AsyncMock(return_value=None)
    use_case = ResumeWorkflowUseCase(
        review_queue_repo=repo,
        checkpoint_service=checkpoint_service,
        graph_app=MagicMock(),
    )
    return use_case, checkpoint_service


async def _resume(use_case: ResumeWorkflowUseCase, review: ReviewItem) -> None:
    await use_case.execute(
        review_id=review.item_id,
        request=ResumeWorkflowRequest(
            decision=WorkflowDecision.APPROVE, feedback="", approved_by="Reviewer"
        ),
    )


async def test_deterministic_shared_thread_without_checkpoint_id_fails_closed() -> None:
    """Case 1: the shared pre-#758 thread with no checkpoint id must be refused.

    Latest-by-thread there is authority-unsafe: several processing attempts
    wrote to that one thread, so it can resolve a superseded attempt's
    checkpoint. Refuse rather than resume superseded evidence.
    """
    shared = lineage.legacy_shared_analysis_thread_id(uuid4())
    review = _review(thread_id=shared, checkpoint_id=None)
    use_case, checkpoint_service = _use_case(review)

    with pytest.raises(ValueError, match="shared"):
        await _resume(use_case, review)

    checkpoint_service.restore_checkpoint.assert_not_awaited()


async def test_deterministic_shared_thread_with_explicit_checkpoint_id_is_allowed() -> None:
    """Case 2: an exact checkpoint id names one checkpoint, so it stays permitted."""
    shared = lineage.legacy_shared_analysis_thread_id(uuid4())
    review = _review(thread_id=shared, checkpoint_id="cp-exact")
    use_case, checkpoint_service = _use_case(review)

    with pytest.raises(ValueError, match="Checkpoint not found"):
        await _resume(use_case, review)

    checkpoint_service.restore_checkpoint.assert_awaited_once_with(
        thread_id=shared, checkpoint_id="cp-exact"
    )


async def test_legacy_uuid_thread_without_checkpoint_id_stays_compatible() -> None:
    """Case 3: production's 6 pending reviews. The fallback must keep working."""
    legacy_uuid = str(uuid4())
    assert not lineage.is_legacy_shared_analysis_thread(legacy_uuid)
    assert not lineage.is_authority_scoped_analysis_thread(legacy_uuid)
    review = _review(thread_id=legacy_uuid, checkpoint_id=None)
    use_case, checkpoint_service = _use_case(review)

    with pytest.raises(ValueError, match="Checkpoint not found"):
        await _resume(use_case, review)

    checkpoint_service.restore_checkpoint.assert_awaited_once_with(
        thread_id=legacy_uuid, checkpoint_id=None
    )


async def test_authority_scoped_thread_without_checkpoint_id_is_safe() -> None:
    """Case 4: attempt-pure by construction, so latest-by-thread stays allowed."""
    document_id = uuid4()
    scoped = f"document:{document_id}:g1:f7:analysis"
    assert lineage.is_authority_scoped_analysis_thread(scoped)
    review = _review(thread_id=scoped, checkpoint_id=None)
    use_case, checkpoint_service = _use_case(review)

    with pytest.raises(ValueError, match="Checkpoint not found"):
        await _resume(use_case, review)

    checkpoint_service.restore_checkpoint.assert_awaited_once_with(
        thread_id=scoped, checkpoint_id=None
    )
