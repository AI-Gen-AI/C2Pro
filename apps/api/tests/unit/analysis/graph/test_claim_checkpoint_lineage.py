"""Unit coverage for the #758 review lineage claim.

Every branch exercised directly with mocks -- no LangGraph runtime, no real
database -- so codecov patch coverage reflects this function regardless of
which CI job partitions the DB-backed integration suites (the same reason
test_persist_real_checkpoint_id.py exists).

The behavioural proof -- that a takeover whose checkpoint binding FAILS still
leaves the review resumable only through the current attempt's lineage --
lives in
tests/integration/document_flow/test_758_checkpoint_lineage_authority_fence.py,
against real PostgreSQL and a real AsyncPostgresSaver.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.analysis.adapters.graph import review_lineage
from src.core import checkpoint_lineage as lineage
from src.core.processing_authority import (
    ProcessingAuthority,
    ProcessingStage,
    bound_authority,
)
from src.core.resume_lineage import ReviewLineage
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus

pytestmark = pytest.mark.asyncio

_TENANT = uuid4()
_DOCUMENT = uuid4()


def _authority(*, fence: int = 2) -> ProcessingAuthority:
    return ProcessingAuthority(
        tenant_id=_TENANT,
        document_id=_DOCUMENT,
        revision_id=None,
        generation=1,
        stage=ProcessingStage.ANALYSIS,
        attempt_id=uuid4(),
        owner_token=uuid4(),
        fencing_token=fence,
    )


def _review(*, thread_id: str | None, row_id: UUID | None) -> ReviewItem:
    metadata: dict[str, Any] = {}
    if thread_id is not None:
        metadata["thread_id"] = thread_id
    if row_id is not None:
        metadata["row_id"] = str(row_id)
    return ReviewItem(
        item_id=uuid4(),
        item_type="contract",
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        confidence=0.2,
        impact_level=ImpactLevel.HIGH,
        created_at=datetime.now(UTC),
        sla_due_date=datetime.now(UTC) + timedelta(days=3),
        metadata=metadata,
    )


def _stored(
    *, thread_id: str | None, generation: int | None = 1, fence: int | None = 1
) -> ReviewLineage:
    """The lineage currently recorded on the review row.

    #758 P1: the claim compares the WHOLE identity -- the thread plus the
    processing generation and fencing token that bound it -- so the stored
    stamp has to be expressible independently of the thread name.
    """
    return ReviewLineage(
        review_row_id=uuid4(),
        thread_id=thread_id,
        document_id=_DOCUMENT,
        lineage_generation=generation,
        lineage_fencing_token=fence,
        authority_generation=generation,
        authority_fencing_token=fence,
    )


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    service: MagicMock,
    stored: ReviewLineage | None = None,
) -> list[Any]:
    """Patch the seams the claim uses, recording fence_current calls."""
    fenced: list[Any] = []

    @asynccontextmanager
    async def _session(_tenant_id):
        yield MagicMock()

    async def _fence(session):
        fenced.append(session)

    async def _read_lineage(_session: Any, **_kwargs: Any) -> ReviewLineage | None:
        return stored

    monkeypatch.setattr(review_lineage, "get_session_with_tenant", _session)
    monkeypatch.setattr(review_lineage, "fence_current", _fence)
    monkeypatch.setattr(review_lineage, "read_review_lineage", _read_lineage)
    monkeypatch.setattr(
        review_lineage, "get_hitl_service_for_graph", lambda *, session, tenant_id: service
    )
    return fenced


def _service(review: ReviewItem | None) -> MagicMock:
    service = MagicMock()
    service.review_queue_repo = AsyncMock()
    service.review_queue_repo.find_active_review.return_value = review
    return service


def _state(thread_id: str) -> dict[str, Any]:
    return {
        "thread_id": thread_id,
        "tenant_id": str(_TENANT),
        "document_id": str(_DOCUMENT),
    }


def _scoped(fence: int = 2) -> str:
    return lineage.analysis_thread_id(
        document_id=_DOCUMENT, authority=_authority(fence=fence)
    )


async def test_takeover_claims_the_review_and_clears_the_stale_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The core case: the review named the superseded attempt's thread."""
    row_id = uuid4()
    review = _review(thread_id=_scoped(fence=1), row_id=row_id)
    service = _service(review)
    fenced = _patch(
        monkeypatch, service, _stored(thread_id=_scoped(fence=1), generation=1, fence=1)
    )
    mine = _scoped(fence=2)

    with bound_authority(_authority(fence=2)):
        await review_lineage.claim_review_lineage_for_current_attempt(**_state(mine))

    # The stamp travels with the thread: a thread with somebody else's
    # generation/fence beside it is a contradiction every later seam reads as
    # "not current", which would strand a review this attempt legitimately owns.
    service.review_queue_repo.claim_checkpoint_lineage.assert_awaited_once_with(
        row_id=row_id, thread_id=mine, lineage_generation=1, lineage_fencing_token=2
    )
    assert fenced, "the claim must run inside the #711 fence"


async def test_claim_is_skipped_when_the_review_already_names_this_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A redelivery re-adopting the same grant must be a no-op."""
    mine = _scoped(fence=2)
    service = _service(_review(thread_id=mine, row_id=uuid4()))
    _patch(monkeypatch, service, _stored(thread_id=mine, generation=1, fence=2))

    with bound_authority(_authority(fence=2)):
        await review_lineage.claim_review_lineage_for_current_attempt(**_state(mine))

    service.review_queue_repo.claim_checkpoint_lineage.assert_not_awaited()


async def test_a_review_this_attempt_created_is_still_stamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The thread already matches, but nothing recorded WHICH attempt owns it.

    `route_for_review` writes the thread and knows nothing about the #711
    grant, so a freshly created review carries a thread with no generation or
    fence beside it. Unfenced rows are deliberately exempt from the currency
    comparison -- that is what keeps production's legacy reviews working --
    which would leave every NEW review equally exempt if the claim stopped at
    "the thread already matches". It must stamp instead.
    """
    row_id = uuid4()
    mine = _scoped(fence=2)
    service = _service(_review(thread_id=mine, row_id=row_id))
    _patch(monkeypatch, service, _stored(thread_id=mine, generation=None, fence=None))

    with bound_authority(_authority(fence=2)):
        await review_lineage.claim_review_lineage_for_current_attempt(**_state(mine))

    service.review_queue_repo.claim_checkpoint_lineage.assert_awaited_once_with(
        row_id=row_id, thread_id=mine, lineage_generation=1, lineage_fencing_token=2
    )


async def test_claim_is_skipped_without_an_active_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing to take over when this attempt created the review itself."""
    service = _service(None)
    _patch(monkeypatch, service, None)

    with bound_authority(_authority()):
        await review_lineage.claim_review_lineage_for_current_attempt(**_state(_scoped()))

    service.review_queue_repo.claim_checkpoint_lineage.assert_not_awaited()


async def test_claim_never_runs_outside_a_processing_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A direct HITL resume re-executes this node; it must not rewrite the lineage.

    Resume runs with no ambient authority, and the node it resumes runs from
    the top -- so without this guard a resume could rebind the very lineage it
    is replaying.
    """
    service = _service(_review(thread_id=_scoped(fence=1), row_id=uuid4()))
    _patch(monkeypatch, service, _stored(thread_id=_scoped(fence=1)))

    # No bound_authority: current_authority() is None.
    await review_lineage.claim_review_lineage_for_current_attempt(**_state(_scoped(fence=2)))

    service.review_queue_repo.find_active_review.assert_not_awaited()
    service.review_queue_repo.claim_checkpoint_lineage.assert_not_awaited()


async def test_legacy_lineage_is_never_claimed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production's legacy UUID threads must be left exactly as they are.

    Read-only production inspection found pending analysis_critique reviews on
    36-character UUID threads with checkpoint_id NULL, resumable only through
    the thread-only fallback. Rebinding them would break that.
    """
    service = _service(_review(thread_id=str(uuid4()), row_id=uuid4()))
    _patch(monkeypatch, service, _stored(thread_id=str(uuid4()), generation=None, fence=None))

    with bound_authority(_authority()):
        # This run's own thread is a legacy UUID, not authority-scoped.
        await review_lineage.claim_review_lineage_for_current_attempt(**_state(str(uuid4())))

    service.review_queue_repo.find_active_review.assert_not_awaited()
    service.review_queue_repo.claim_checkpoint_lineage.assert_not_awaited()


async def test_incomplete_state_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(_review(thread_id=_scoped(fence=1), row_id=uuid4()))
    _patch(monkeypatch, service, _stored(thread_id=_scoped(fence=1)))

    with bound_authority(_authority()):
        for partial in (
            {"thread_id": None, "tenant_id": str(_TENANT), "document_id": str(_DOCUMENT)},
            {"thread_id": _scoped(), "tenant_id": None, "document_id": str(_DOCUMENT)},
            {"thread_id": _scoped(), "tenant_id": str(_TENANT), "document_id": None},
        ):
            await review_lineage.claim_review_lineage_for_current_attempt(**partial)

    service.review_queue_repo.claim_checkpoint_lineage.assert_not_awaited()


async def test_claim_fails_closed_when_the_row_identity_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail CLOSED: never proceed to an actionable review we could not claim.

    Unlike the routing block above it -- which fails OPEN to an interrupt
    because pausing for a human beats auto-approving -- an unclaimable lineage
    must abort the attempt, leaving the document pending and retryable.
    """
    service = _service(_review(thread_id=_scoped(fence=1), row_id=None))
    _patch(monkeypatch, service, _stored(thread_id=_scoped(fence=1)))

    with bound_authority(_authority(fence=2)), pytest.raises(RuntimeError, match="row identity"):
        await review_lineage.claim_review_lineage_for_current_attempt(**_state(_scoped(fence=2)))

    service.review_queue_repo.claim_checkpoint_lineage.assert_not_awaited()


async def test_claim_propagates_a_persistence_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed claim must not be swallowed into a best-effort no-op."""
    service = _service(_review(thread_id=_scoped(fence=1), row_id=uuid4()))
    service.review_queue_repo.claim_checkpoint_lineage.side_effect = RuntimeError("db down")
    _patch(monkeypatch, service, _stored(thread_id=_scoped(fence=1)))

    with bound_authority(_authority(fence=2)), pytest.raises(RuntimeError, match="db down"):
        await review_lineage.claim_review_lineage_for_current_attempt(**_state(_scoped(fence=2)))
