"""
Unit coverage for workflow._persist_real_checkpoint_id (C2PRO P0b HITL resume
hotfix). Each branch exercised directly with mocks -- no LangGraph runtime,
no real database -- so codecov patch coverage reflects this function
regardless of which CI job partitions the heavier DB-backed integration
suites.

Behavioral proof that this function persists a REAL, non-fabricated
checkpoint id end-to-end against a real database lives in
tests/modules/integration/test_p0b_hitl_resume_hotfix.py.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.analysis.adapters.graph import workflow
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus


def _make_review(*, checkpoint_id: str | None) -> ReviewItem:
    # row_id is what _to_domain always projects out of the primary key; the
    # lineage claim on the rebind path addresses the EXACT row by it.
    metadata: dict = {"thread_id": "thr-1", "row_id": str(uuid4())}
    if checkpoint_id is not None:
        metadata["checkpoint_id"] = checkpoint_id
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


def _patch_session_and_service(monkeypatch: pytest.MonkeyPatch, service: MagicMock) -> None:
    """Patch the two local imports inside _persist_real_checkpoint_id."""

    @asynccontextmanager
    async def _fake_get_session_with_tenant(tenant_id):
        yield MagicMock()

    monkeypatch.setattr(
        "src.core.database.get_session_with_tenant", _fake_get_session_with_tenant
    )
    monkeypatch.setattr(
        "src.analysis.adapters.graph.dependencies.get_hitl_service_for_graph",
        lambda *, session, tenant_id: service,
    )


def _config(thread_id: str = "thr-1") -> dict:
    return {"configurable": {"thread_id": thread_id}}


async def test_returns_immediately_without_document_id(monkeypatch: pytest.MonkeyPatch) -> None:
    app = MagicMock()
    app.aget_state = AsyncMock()

    await workflow._persist_real_checkpoint_id(
        app, _config(), thread_id="thr-1", document_id=None, tenant_id=str(uuid4())
    )

    app.aget_state.assert_not_called()


async def test_returns_immediately_without_tenant_id(monkeypatch: pytest.MonkeyPatch) -> None:
    app = MagicMock()
    app.aget_state = AsyncMock()

    await workflow._persist_real_checkpoint_id(
        app, _config(), thread_id="thr-1", document_id=str(uuid4()), tenant_id=None
    )

    app.aget_state.assert_not_called()


async def test_aget_state_failure_is_caught_and_does_not_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = MagicMock()
    app.aget_state = AsyncMock(side_effect=RuntimeError("checkpointer unavailable"))
    service = MagicMock()
    service.review_queue_repo = AsyncMock()
    _patch_session_and_service(monkeypatch, service)

    await workflow._persist_real_checkpoint_id(
        app, _config(), thread_id="thr-1", document_id=str(uuid4()), tenant_id=str(uuid4())
    )

    service.review_queue_repo.find_active_review.assert_not_called()


async def test_missing_checkpoint_id_in_snapshot_is_a_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=SimpleNamespace(config={"configurable": {"thread_id": "thr-1"}})
    )
    service = MagicMock()
    service.review_queue_repo = AsyncMock()
    _patch_session_and_service(monkeypatch, service)

    await workflow._persist_real_checkpoint_id(
        app, _config(), thread_id="thr-1", document_id=str(uuid4()), tenant_id=str(uuid4())
    )

    service.review_queue_repo.find_active_review.assert_not_called()


async def test_no_active_review_found_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=SimpleNamespace(
            config={"configurable": {"thread_id": "thr-1", "checkpoint_id": "real-cp-1"}}
        )
    )
    service = MagicMock()
    service.review_queue_repo = AsyncMock()
    service.review_queue_repo.find_active_review.return_value = None
    _patch_session_and_service(monkeypatch, service)

    await workflow._persist_real_checkpoint_id(
        app, _config(), thread_id="thr-1", document_id=str(uuid4()), tenant_id=str(uuid4())
    )

    service.review_queue_repo.update_review_item.assert_not_called()


async def test_review_already_carrying_checkpoint_id_is_not_overwritten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=SimpleNamespace(
            config={"configurable": {"thread_id": "thr-1", "checkpoint_id": "new-cp"}}
        )
    )
    review = _make_review(checkpoint_id="already-set-cp")
    service = MagicMock()
    service.review_queue_repo = AsyncMock()
    service.review_queue_repo.find_active_review.return_value = review
    _patch_session_and_service(monkeypatch, service)

    await workflow._persist_real_checkpoint_id(
        app, _config(), thread_id="thr-1", document_id=str(uuid4()), tenant_id=str(uuid4())
    )

    service.review_queue_repo.update_review_item.assert_not_called()
    assert review.metadata["checkpoint_id"] == "already-set-cp"


async def test_a_first_binding_within_this_attempt_does_not_claim_the_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Attaching the checkpoint id inside THIS attempt's thread is not a rebind.

    Nothing about the lineage changed, so re-stamping it would be a pointless
    write -- and clearing the checkpoint id, which the claim deliberately
    does, would undo the binding this call exists to make.
    """
    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=SimpleNamespace(
            config={"configurable": {"thread_id": "thr-1", "checkpoint_id": "real-cp-7"}}
        )
    )
    review = _make_review(checkpoint_id=None)
    service = MagicMock()
    service.review_queue_repo = AsyncMock()
    service.review_queue_repo.find_active_review.return_value = review
    _patch_session_and_service(monkeypatch, service)

    await workflow._persist_real_checkpoint_id(
        app, _config(), thread_id="thr-1", document_id=str(uuid4()), tenant_id=str(uuid4())
    )

    service.review_queue_repo.claim_checkpoint_lineage.assert_not_awaited()
    assert review.metadata["checkpoint_id"] == "real-cp-7"


async def test_real_checkpoint_id_is_persisted_onto_the_pending_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=SimpleNamespace(
            config={"configurable": {"thread_id": "thr-1", "checkpoint_id": "real-cp-42"}}
        )
    )
    review = _make_review(checkpoint_id=None)
    service = MagicMock()
    service.review_queue_repo = AsyncMock()
    service.review_queue_repo.find_active_review.return_value = review
    _patch_session_and_service(monkeypatch, service)

    await workflow._persist_real_checkpoint_id(
        app, _config(), thread_id="thr-1", document_id=str(uuid4()), tenant_id=str(uuid4())
    )

    service.review_queue_repo.update_review_item.assert_called_once_with(review)
    assert review.metadata["checkpoint_id"] == "real-cp-42"
    assert review.metadata["thread_id"] == "thr-1"


async def test_persist_block_exception_is_caught_and_does_not_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=SimpleNamespace(
            config={"configurable": {"thread_id": "thr-1", "checkpoint_id": "real-cp-1"}}
        )
    )
    service = MagicMock()
    service.review_queue_repo = AsyncMock()
    service.review_queue_repo.find_active_review.side_effect = RuntimeError("db down")
    _patch_session_and_service(monkeypatch, service)

    # Must not raise -- checkpoint capture is best-effort per the docstring.
    await workflow._persist_real_checkpoint_id(
        app, _config(), thread_id="thr-1", document_id=str(uuid4()), tenant_id=str(uuid4())
    )


async def test_review_bound_to_a_superseded_lineage_is_rebound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#758: a takeover must re-bind a review that names another attempt's thread.

    The old guard ("bind only when nothing is bound yet") left the current
    review pointing at the superseded attempt's checkpoint forever. Keyed on
    the LINEAGE: a different thread means a different processing attempt.

    The move goes through `claim_checkpoint_lineage`, not `update_review_item`
    alone: only that path can carry the thread, the processing generation and
    the fencing token together and null the superseded checkpoint id. Moving
    the thread on its own would leave this attempt's thread beside the
    previous attempt's stamp, which every later seam reads as "not current".
    """
    app = MagicMock()
    app.aget_state = AsyncMock(
        return_value=SimpleNamespace(
            config={"configurable": {"thread_id": "thr-2", "checkpoint_id": "cp-b"}}
        )
    )
    review = _make_review(checkpoint_id="cp-a")  # metadata thread_id == "thr-1"
    service = MagicMock()
    service.review_queue_repo = AsyncMock()
    service.review_queue_repo.find_active_review.return_value = review
    _patch_session_and_service(monkeypatch, service)

    await workflow._persist_real_checkpoint_id(
        app, _config("thr-2"), thread_id="thr-2", document_id=str(uuid4()),
        tenant_id=str(uuid4()),
    )

    service.review_queue_repo.update_review_item.assert_called_once()
    service.review_queue_repo.claim_checkpoint_lineage.assert_awaited_once()
    claimed = service.review_queue_repo.claim_checkpoint_lineage.await_args.kwargs
    assert claimed["thread_id"] == "thr-2"
    assert claimed["row_id"] == UUID(str(review.metadata["row_id"]))
    assert review.metadata["checkpoint_id"] == "cp-b"
    assert review.metadata["thread_id"] == "thr-2", "the thread must be overwritten"


def test_needs_rebinding_is_keyed_on_the_lineage() -> None:
    """Pinned directly: within one attempt the binding must not slide forward.

    The bound checkpoint is the interrupt point resume replays; moving it to a
    later checkpoint on the same thread would break that, which is why the
    rule compares threads and not checkpoint ids.
    """
    assert workflow._needs_rebinding(_make_review(checkpoint_id=None), "thr-1") is True
    assert workflow._needs_rebinding(_make_review(checkpoint_id="cp-a"), "thr-2") is True
    assert workflow._needs_rebinding(_make_review(checkpoint_id="cp-a"), "thr-1") is False
