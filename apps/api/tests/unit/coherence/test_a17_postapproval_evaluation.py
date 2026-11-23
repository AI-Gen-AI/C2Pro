"""JV1-A17: post-approval evaluation must respect human authority and tenant scope.

Synthetic only. No network, databases, providers or private document material.
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks

from src.coherence.application import project_evaluation as subject
from src.modules.hitl.domain.entities import ReviewStatus


def _review(*, project_id=None, tenant_id=None, status=ReviewStatus.APPROVED):
    return SimpleNamespace(
        item_id=uuid4(),
        current_status=status,
        metadata={
            "project_id": str(project_id or uuid4()),
            "tenant_id": str(tenant_id) if tenant_id else None,
        },
        item_data={},
    )


def test_successful_final_approval_enqueues_one_tenant_scoped_task():
    tenant_id, project_id, actor_id = uuid4(), uuid4(), uuid4()
    background = BackgroundTasks()
    review = _review(project_id=project_id, tenant_id=tenant_id)
    assert subject.queue_post_approval_evaluation(
        background,
        review=review,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        newly_approved=True,
    )
    assert len(background.tasks) == 1
    task = background.tasks[0]
    assert task.func is subject.run_project_evaluation_after_approval
    assert task.kwargs == {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "actor_user_id": actor_id,
        "review_id": review.item_id,
    }


@pytest.mark.parametrize(
    "newly_approved,status",
    [
        (False, ReviewStatus.APPROVED),
        (True, ReviewStatus.REJECTED),
        (True, ReviewStatus.PENDING_REVIEW_REQUIRED),
    ],
)
def test_no_task_for_replay_rejection_or_provisional_state(newly_approved, status):
    background = BackgroundTasks()
    assert not subject.queue_post_approval_evaluation(
        background,
        review=_review(status=status),
        tenant_id=uuid4(),
        actor_user_id=uuid4(),
        newly_approved=newly_approved,
    )
    assert background.tasks == []


@pytest.mark.parametrize("project_id", [None, "", "not-a-uuid"])
def test_missing_or_invalid_project_never_enqueues(project_id):
    background = BackgroundTasks()
    review = SimpleNamespace(
        current_status=ReviewStatus.APPROVED, metadata={"project_id": project_id}, item_data={}
    )
    assert not subject.queue_post_approval_evaluation(
        background,
        review=review,
        tenant_id=uuid4(),
        actor_user_id=uuid4(),
        newly_approved=True,
    )
    assert background.tasks == []


def test_mismatched_tenant_metadata_fails_closed():
    background = BackgroundTasks()
    assert not subject.queue_post_approval_evaluation(
        background,
        review=_review(tenant_id=uuid4()),
        tenant_id=uuid4(),
        actor_user_id=uuid4(),
        newly_approved=True,
    )
    assert background.tasks == []


def test_conflicting_project_ids_fail_closed():
    background = BackgroundTasks()
    review = _review(project_id=uuid4())
    review.item_data["project_id"] = str(uuid4())
    assert not subject.queue_post_approval_evaluation(
        background,
        review=review,
        tenant_id=uuid4(),
        actor_user_id=uuid4(),
        newly_approved=True,
    )
    assert background.tasks == []


@pytest.mark.asyncio
async def test_background_scoring_uses_fresh_tenant_scoped_session_and_low_budget(monkeypatch):
    tenant_id, project_id, actor_id = uuid4(), uuid4(), uuid4()
    review_id = uuid4()
    session = SimpleNamespace(execute=AsyncMock(), scalar=AsyncMock(return_value=None))
    tracked = []

    @asynccontextmanager
    async def fake_session(tid):
        tracked.append(("session", tid))
        yield session

    score = AsyncMock()
    monkeypatch.setattr(subject, "get_session_with_tenant", fake_session)
    monkeypatch.setattr(subject, "_run_evaluation", score)
    await subject.run_project_evaluation_after_approval(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_user_id=actor_id,
        review_id=review_id,
    )
    assert tracked == [("session", tenant_id)]
    score.assert_awaited_once()
    payload, db, user = score.await_args.args
    assert db is session
    assert payload.project_id == project_id
    assert payload.low_budget_mode is True
    assert payload.include_rag_similarity is False
    assert user.tenant_id == tenant_id and user.id == actor_id
    assert score.await_args.kwargs["review_id"] == review_id
    session.execute.assert_awaited_once()
    session.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_persisted_approval_prevents_duplicate_evaluation(monkeypatch):
    tenant_id, project_id, actor_id, review_id = uuid4(), uuid4(), uuid4(), uuid4()
    session = SimpleNamespace(execute=AsyncMock(), scalar=AsyncMock(return_value=uuid4()))

    @asynccontextmanager
    async def session_factory(tid):
        assert tid == tenant_id
        yield session

    score = AsyncMock(side_effect=AssertionError("duplicate must not be recalculated"))
    monkeypatch.setattr(subject, "get_session_with_tenant", session_factory)
    monkeypatch.setattr(subject, "_run_evaluation", score)
    await subject.run_project_evaluation_after_approval(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_user_id=actor_id,
        review_id=review_id,
    )
    score.assert_not_awaited()
    session.execute.assert_awaited_once()
    session.scalar.assert_awaited_once()


def test_lock_key_is_deterministic_and_scoped():
    t, p, r = uuid4(), uuid4(), uuid4()
    k = subject._approval_lock_key(t, p, r)
    assert k == subject._approval_lock_key(t, p, r)
    assert k != subject._approval_lock_key(t, p, uuid4())
    assert k != subject._approval_lock_key(t, uuid4(), r)
    assert 0 <= k < (1 << 63)
