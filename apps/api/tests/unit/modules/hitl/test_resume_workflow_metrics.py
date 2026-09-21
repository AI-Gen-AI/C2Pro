"""
Unit tests for ResumeWorkflowUseCase metric instrumentation (TASK-BCK-032).

Verifies that the use case calls the correct metric recorders on each
branch: checkpoint-not-found, workflow-resume-error, and happy-path
approve/reject. These assertions pin the contract between the use case
and `src.core.observability.monitoring`.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.core.observability import monitoring
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowRequest,
    ResumeWorkflowUseCase,
    WorkflowDecision,
)
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus


def _make_review_item(
    *,
    status: ReviewStatus = ReviewStatus.PENDING_REVIEW_REQUIRED,
    checkpoint_id: str | None = "cp-1",
    thread_id: str | None = "thr-1",
) -> ReviewItem:
    metadata: dict = {}
    if checkpoint_id is not None:
        metadata["checkpoint_id"] = checkpoint_id
    if thread_id is not None:
        metadata["thread_id"] = thread_id
    return ReviewItem(
        item_id=uuid4(),
        item_type="clause",
        current_status=status,
        confidence=0.42,
        impact_level=ImpactLevel.HIGH,
        created_at=datetime.now(UTC),
        sla_due_date=datetime.now(UTC) + timedelta(hours=24),
        metadata=metadata,
    )


@pytest.fixture
def review_queue_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def checkpoint_service():
    """C2PRO P0b true-resume hotfix: the use case now restores the exact
    checkpoint CONFIG (restore_checkpoint), not just the checkpoint body.
    """
    from src.modules.hitl.adapters.checkpoint_service import CheckpointRestore

    svc = MagicMock()
    svc.load_checkpoint = AsyncMock()
    svc.extract_state = MagicMock(return_value={"foo": "bar"})

    async def _restore(thread_id, checkpoint_id=None):
        checkpoint = await svc.load_checkpoint(
            thread_id=thread_id, checkpoint_id=checkpoint_id
        )
        if checkpoint is None:
            return None
        configurable = {"thread_id": thread_id, "checkpoint_ns": ""}
        if checkpoint_id:
            configurable["checkpoint_id"] = checkpoint_id
        return CheckpointRestore(
            checkpoint=checkpoint, config={"configurable": configurable}, metadata={}
        )

    svc.restore_checkpoint = _restore
    return svc


@pytest.fixture
def graph_app():
    """A resume must return a state carrying analysis_id -- that is the
    signal durable persistence (N17) actually ran.
    """
    app = MagicMock()
    app.aupdate_state = AsyncMock()
    app.ainvoke = AsyncMock(return_value={"analysis_id": "analysis-1"})
    return app


@pytest.fixture
def claim_session_factory():
    """Stub the exactly-once claim's own session so these unit tests need
    no database; the claim always succeeds here.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory(_tenant_id):
        session = MagicMock()
        session.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=(1,))))
        yield session

    return _factory


@pytest.fixture
def use_case(review_queue_repo, checkpoint_service, graph_app, claim_session_factory):
    review_queue_repo.tenant_id = uuid4()
    return ResumeWorkflowUseCase(
        review_queue_repo=review_queue_repo,
        checkpoint_service=checkpoint_service,
        graph_app=graph_app,
        claim_session_factory=claim_session_factory,
    )


async def test_checkpoint_not_found_emits_checkpoint_load_error(
    use_case, review_queue_repo, checkpoint_service, monkeypatch
):
    """A missing checkpoint must bump the named checkpoint-load counter."""
    item = _make_review_item()
    review_queue_repo.get_review_item.return_value = item
    checkpoint_service.load_checkpoint.return_value = None

    spy_chk = MagicMock()
    spy_resume = MagicMock()
    spy_latency = MagicMock()
    monkeypatch.setattr(
        "src.modules.hitl.application.resume_workflow_use_case.record_hitl_checkpoint_load_error",
        spy_chk,
    )
    monkeypatch.setattr(
        "src.modules.hitl.application.resume_workflow_use_case.record_hitl_resume_error",
        spy_resume,
    )
    monkeypatch.setattr(
        "src.modules.hitl.application.resume_workflow_use_case.record_hitl_resume_latency",
        spy_latency,
    )

    with pytest.raises(ValueError):
        await use_case.execute(
            review_id=item.item_id,
            request=ResumeWorkflowRequest(
                decision=WorkflowDecision.APPROVE, feedback="ok"
            ),
        )

    spy_chk.assert_any_call("not_found")
    spy_resume.assert_called_once_with("checkpoint_not_found")
    spy_latency.assert_called_once()  # latency is always recorded


async def test_workflow_resume_failure_emits_workflow_resume_error(
    use_case, review_queue_repo, checkpoint_service, graph_app, monkeypatch
):
    """A failure inside graph_app.aupdate_state must bump the workflow-error counter."""
    item = _make_review_item()
    review_queue_repo.get_review_item.return_value = item
    checkpoint_service.load_checkpoint.return_value = {
        "id": "cp-1",
        "channel_values": {"__root__": {"foo": "bar"}},
    }
    graph_app.ainvoke.side_effect = RuntimeError("langgraph down")

    spy_wf = MagicMock()
    spy_resume = MagicMock()
    monkeypatch.setattr(
        "src.modules.hitl.application.resume_workflow_use_case.record_hitl_workflow_resume_error",
        spy_wf,
    )
    monkeypatch.setattr(
        "src.modules.hitl.application.resume_workflow_use_case.record_hitl_resume_error",
        spy_resume,
    )

    # C2PRO P0b true-resume hotfix: the workflow error is no longer
    # swallowed into a "_with_errors" status. Swallowing it is exactly what
    # let the system report a successful approval while N17 never ran, so
    # the failure now propagates and the decision is not recorded.
    with pytest.raises(RuntimeError):
        await use_case.execute(
            review_id=item.item_id,
            request=ResumeWorkflowRequest(
                decision=WorkflowDecision.APPROVE, feedback="please continue"
            ),
        )

    spy_wf.assert_called_once_with("approve")
    spy_resume.assert_called_once_with("workflow_error")


async def test_happy_path_approve_records_attempt_and_latency(
    use_case, review_queue_repo, checkpoint_service, monkeypatch
):
    item = _make_review_item()
    review_queue_repo.get_review_item.return_value = item
    checkpoint_service.load_checkpoint.return_value = {
        "id": "cp-1",
        "channel_values": {"__root__": {"foo": "bar"}},
    }

    spy_attempt = MagicMock()
    spy_latency = MagicMock()
    monkeypatch.setattr(
        "src.modules.hitl.application.resume_workflow_use_case.record_hitl_resume_attempt",
        spy_attempt,
    )
    monkeypatch.setattr(
        "src.modules.hitl.application.resume_workflow_use_case.record_hitl_resume_latency",
        spy_latency,
    )

    resp = await use_case.execute(
        review_id=item.item_id,
        request=ResumeWorkflowRequest(
            decision=WorkflowDecision.APPROVE, feedback="approved by PM"
        ),
    )

    spy_attempt.assert_called_once()
    args, _ = spy_attempt.call_args
    assert args[0] == "approve"
    assert args[1] == "resumed"
    spy_latency.assert_called_once()
    assert resp.status == "resumed"


async def test_happy_path_reject_records_attempt_with_rejected_status(
    use_case, review_queue_repo, checkpoint_service, monkeypatch
):
    item = _make_review_item()
    review_queue_repo.get_review_item.return_value = item
    checkpoint_service.load_checkpoint.return_value = {
        "id": "cp-1",
        "channel_values": {"__root__": {"foo": "bar"}},
    }

    spy_attempt = MagicMock()
    monkeypatch.setattr(
        "src.modules.hitl.application.resume_workflow_use_case.record_hitl_resume_attempt",
        spy_attempt,
    )

    resp = await use_case.execute(
        review_id=item.item_id,
        request=ResumeWorkflowRequest(
            decision=WorkflowDecision.REJECT, feedback="ambiguous clause"
        ),
    )

    args, _ = spy_attempt.call_args
    assert args[0] == "reject"
    assert args[1] == "rejected"
    assert resp.status == "rejected"


async def test_resume_succeeds_without_checkpoint_id_using_thread_id_only(
    use_case, review_queue_repo, checkpoint_service, monkeypatch
):
    """C2PRO P0b HITL resume hotfix: checkpoint_id is optional.

    thread_id alone must be sufficient to resume -- CheckpointService.
    load_checkpoint already falls back to the latest checkpoint for a thread
    when checkpoint_id is omitted, which for a freshly-interrupted thread IS
    the interrupt point. A review that never had a real checkpoint_id
    captured (e.g. the capture step failed, or hasn't run yet) must not be
    permanently blocked from resuming.
    """
    item = _make_review_item(checkpoint_id=None, thread_id="thr-no-checkpoint")
    review_queue_repo.get_review_item.return_value = item
    checkpoint_service.load_checkpoint.return_value = {
        "id": "latest",
        "channel_values": {"__root__": {"foo": "bar"}},
    }

    spy_warning = MagicMock()
    monkeypatch.setattr(
        "src.modules.hitl.application.resume_workflow_use_case.logger.warning",
        spy_warning,
    )

    resp = await use_case.execute(
        review_id=item.item_id,
        request=ResumeWorkflowRequest(
            decision=WorkflowDecision.APPROVE, feedback="thread_id alone suffices"
        ),
    )

    assert resp.status == "resumed"
    checkpoint_service.load_checkpoint.assert_called_once_with(
        thread_id="thr-no-checkpoint", checkpoint_id=None
    )
    # The specific warning must be emitted. (Assert on its presence rather
    # than an exact call count: a successful resume legitimately emits other
    # best-effort warnings, e.g. from the post-resume document transition.)
    warned = [c.args[0] for c in spy_warning.call_args_list if c.args]
    assert "resuming_without_explicit_checkpoint_id" in warned


async def test_resume_raises_when_thread_id_missing_even_without_checkpoint_id(
    use_case, review_queue_repo
):
    """thread_id remains hard-required: absence must still fail fast."""
    item = _make_review_item(checkpoint_id=None, thread_id=None)
    review_queue_repo.get_review_item.return_value = item

    with pytest.raises(ValueError, match="missing thread_id"):
        await use_case.execute(
            review_id=item.item_id,
            request=ResumeWorkflowRequest(decision=WorkflowDecision.APPROVE, feedback="x"),
        )


def test_use_case_imports_new_recorders():
    """Smoke assertion: the use case module must wire the new recorders."""
    from src.modules.hitl.application import resume_workflow_use_case as mod

    assert hasattr(mod, "record_hitl_checkpoint_load_error")
    assert hasattr(mod, "record_hitl_workflow_resume_error")
    # And the recorders themselves remain callable
    assert callable(monitoring.record_hitl_checkpoint_load_error)
    assert callable(monitoring.record_hitl_workflow_resume_error)
    assert callable(monitoring.record_hitl_decision)
