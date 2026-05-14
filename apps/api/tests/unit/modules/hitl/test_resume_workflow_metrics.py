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
    svc = MagicMock()
    svc.load_checkpoint = AsyncMock()
    svc.extract_state = MagicMock(return_value={"foo": "bar"})
    return svc


@pytest.fixture
def graph_app():
    app = MagicMock()
    app.aupdate_state = AsyncMock()
    return app


@pytest.fixture
def use_case(review_queue_repo, checkpoint_service, graph_app):
    return ResumeWorkflowUseCase(
        review_queue_repo=review_queue_repo,
        checkpoint_service=checkpoint_service,
        graph_app=graph_app,
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


async def test_workflow_update_failure_emits_workflow_resume_error(
    use_case, review_queue_repo, checkpoint_service, graph_app, monkeypatch
):
    """A failure inside graph_app.aupdate_state must bump the workflow-error counter."""
    item = _make_review_item()
    review_queue_repo.get_review_item.return_value = item
    checkpoint_service.load_checkpoint.return_value = {
        "id": "cp-1",
        "channel_values": {"__root__": {"foo": "bar"}},
    }
    graph_app.aupdate_state.side_effect = RuntimeError("langgraph down")

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

    resp = await use_case.execute(
        review_id=item.item_id,
        request=ResumeWorkflowRequest(
            decision=WorkflowDecision.APPROVE, feedback="please continue"
        ),
    )

    spy_wf.assert_called_once_with("approve")
    spy_resume.assert_called_once_with("workflow_error")
    # Use case swallows the workflow error and returns an errored status
    assert resp.status.endswith("_with_errors")


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


def test_use_case_imports_new_recorders():
    """Smoke assertion: the use case module must wire the new recorders."""
    from src.modules.hitl.application import resume_workflow_use_case as mod

    assert hasattr(mod, "record_hitl_checkpoint_load_error")
    assert hasattr(mod, "record_hitl_workflow_resume_error")
    # And the recorders themselves remain callable
    assert callable(monitoring.record_hitl_checkpoint_load_error)
    assert callable(monitoring.record_hitl_workflow_resume_error)
    assert callable(monitoring.record_hitl_decision)
