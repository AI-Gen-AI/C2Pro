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
from uuid import uuid4

import pytest

from src.analysis.adapters.graph import workflow
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus


def _make_review(*, checkpoint_id: str | None) -> ReviewItem:
    metadata: dict = {"thread_id": "thr-1"}
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
