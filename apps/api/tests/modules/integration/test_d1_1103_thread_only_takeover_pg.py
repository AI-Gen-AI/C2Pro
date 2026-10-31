"""D1/#1103 exact thread-only crash/takeover differential on main + #1145 test overlay.

Dedicated disposable PostgreSQL test branch ONLY. No application code changes.
The case is intentionally expected to RED if the original interrupt is reused
or old approval is replayed after a crashed first attempt.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select, text

from src.core.auth.models import Tenant, User
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowRequest,
    WorkflowDecision,
)
from src.modules.hitl.domain.entities import ReviewStatus
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    InjectedCrash,
    N17_RUNS,
    _approve,
    _build_graph_with_failing_n17,
    _build_real_graph,
    _arrange,
    _counts,
    _initial_state,
    _operation_row,
    _persist_bound_candidate,
    _persisted_events,
    _reload,
    _seed,
    _use_case,
    independent_sessions,
    real_saver,
)

pytestmark = pytest.mark.asyncio


async def test_d1_1103_thread_only_crash_pre_n17_changed_decision_preserves_source(
    real_saver, independent_sessions, db, test_user: User, test_tenant_2: Tenant,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = str(uuid4())  # Legacy UUID thread; NOT shared document:...:analysis.
    register(thread_id)
    app = _build_real_graph(saver)
    cfg = {"configurable": {"thread_id": thread_id}}
    initial = await app.ainvoke(_initial_state(document, tenant, thread_id), cfg)
    assert "__interrupt__" in initial
    source_id = (await app.aget_state(cfg)).config["configurable"]["checkpoint_id"]

    review = (await db.execute(
        select(ReviewItemORM).where(ReviewItemORM.document_id == document.id)
    )).scalars().one()
    review.thread_id = thread_id
    review.checkpoint_id = None  # ACTUAL thread-only path, not CP7 pinned.
    review.review_metadata = {
        **(review.review_metadata or {}),
        "tenant_id": str(tenant.id),
        "document_id": str(document.id),
    }
    await db.commit()
    await _persist_bound_candidate(db, tenant, document, thread_id)
    await db.refresh(review)
    assert review.checkpoint_id is None and review.thread_id == thread_id

    # Unauthorized reviewer / wrong review ID must never create an operation.
    with pytest.raises(ValueError):
        await _use_case(db, tenant, saver, app, independent_sessions).execute(
            review_id=uuid4(), request=_approve()
        )
    with pytest.raises(ValueError):
        await _use_case(db, test_tenant_2, saver, app, independent_sessions).execute(
            review_id=review.item_id, request=_approve()
        )

    N17_RUNS.clear()
    # Attempt 1 APPROVE: real interrupt consumed, real descendant checkpoint
    # written, injected failure INSIDE N17 BEFORE durable analysis/event.
    with pytest.raises(InjectedCrash):
        await _use_case(
            db, tenant, saver, _build_graph_with_failing_n17(saver),
            independent_sessions,
        ).execute(review_id=review.item_id, request=_approve())

    assert len(N17_RUNS) == 1, "first attempt did advance into N17"
    assert await _counts(db, document.project_id) == (0, 0)
    assert await _persisted_events(db, document.project_id) == 0
    latest_id = (
        await app.aget_state({"configurable": {"thread_id": thread_id}})
    ).config["configurable"]["checkpoint_id"]
    assert latest_id != source_id, "first attempt must leave a descendant"

    async with independent_sessions(tenant.id) as observer:
        source_writes = int(await observer.scalar(text(
            "SELECT count(*) FROM checkpoint_writes "
            "WHERE thread_id=:tid AND checkpoint_id=:cid AND channel='__resume__'"
        ), {"tid": thread_id, "cid": source_id}) or 0)

    # Attempt 2 REJECT changes both the decision and the reviewer.
    # Capture the use-case failure with fence and source-write provenance.
    rejected_request = ResumeWorkflowRequest(
        decision=WorkflowDecision.REJECT,
        feedback="rejected after first attempt crash",
        approved_by="R2",
    )
    try:
        outcome = await _use_case(
            db, tenant, saver, app, independent_sessions,
        ).execute(review_id=review.item_id, request=rejected_request)
    except Exception as exc:
        op = await _operation_row(independent_sessions, tenant.id, review.id)
        pytest.fail(
            f"D1_1103_THREAD_ONLY_TAKEOVER_RED: "
            f"{type(exc).__name__}: {exc}; "
            f"source_resume_writes={source_writes}; "
            f"fencing_token={getattr(op, 'fencing_token', None)}; "
            f"decision_revision={getattr(op, 'decision_revision', None)}; "
            f"attempts={getattr(op, 'attempts', None)}"
        )

    op = await _operation_row(independent_sessions, tenant.id, review.id)
    assert op is not None and op.fencing_token > 1, (
        f"takeover fence missing: op={op}"
    )
    assert op.decision_revision == 2 and op.attempts >= 2
    assert outcome.status == "rejected", "takeover must not replay old APPROVE"
    assert source_writes == 0, (
        f"immutable source has prior __resume__ write: {source_writes}"
    )
    assert len(N17_RUNS) == 1, "no second N17 execution on REJECT"
    assert await _counts(db, document.project_id) == (0, 0)
    assert await _persisted_events(db, document.project_id) == 0
    assert (await _reload(db, ReviewItemORM, review.id)).current_status == (
        ReviewStatus.REJECTED.value
    )

    # Replaying the first, now stale approval cannot produce an analysis.
    stale = await _use_case(
        db, tenant, saver, app, independent_sessions,
    ).execute(review_id=review.item_id, request=_approve())
    assert stale.status == ReviewStatus.REJECTED.value
    assert await _counts(db, document.project_id) == (0, 0)
    assert len(N17_RUNS) == 1


async def test_d1_1103_thread_only_valid_approve_persists_once_without_source_writes(
    real_saver, independent_sessions, db, test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    thread_id = str(uuid4())
    register(thread_id)
    app = _build_real_graph(saver)
    cfg = {"configurable": {"thread_id": thread_id}}
    initial = await app.ainvoke(_initial_state(document, tenant, thread_id), cfg)
    assert "__interrupt__" in initial
    source = (await app.aget_state(cfg)).config["configurable"]["checkpoint_id"]
    review = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().one()
    review.thread_id, review.checkpoint_id = thread_id, None
    review.review_metadata = {
        **(review.review_metadata or {}),
        "tenant_id": str(tenant.id), "document_id": str(document.id),
    }
    await db.commit()
    await _persist_bound_candidate(db, tenant, document, thread_id)
    N17_RUNS.clear()
    result = await _use_case(db, tenant, saver, app, independent_sessions).execute(
        review_id=review.item_id, request=_approve()
    )
    assert result.status == "resumed"
    assert len(N17_RUNS) == 1
    assert await _counts(db, document.project_id) == (1, 1)
    assert await _persisted_events(db, document.project_id) == 1
    async with independent_sessions(tenant.id) as observer:
        assert int(await observer.scalar(text(
            "SELECT count(*) FROM checkpoint_writes "
            "WHERE thread_id=:t AND checkpoint_id=:s AND channel='__resume__'"
        ), {"t": thread_id, "s": source}) or 0) == 0
    op = await _operation_row(independent_sessions, tenant.id, review.id)
    assert op.fencing_token == 1
    assert op.analysis_id is not None
    replay = await _use_case(db, tenant, saver, app, independent_sessions).execute(
        review_id=review.item_id, request=_approve()
    )
    assert replay.status == ReviewStatus.APPROVED.value
    assert len(N17_RUNS) == 1
    assert await _counts(db, document.project_id) == (1, 1)


async def test_d1_1103_takeover_fork_exception_fails_closed(
    real_saver, independent_sessions, db, test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    N17_RUNS.clear()

    class _FirstAttemptDiesBeforeGraph:
        checkpointer = saver
        async def ainvoke(self, *_args, **_kwargs):
            raise InjectedCrash("worker exited before graph resume")

    with pytest.raises(InjectedCrash):
        await _use_case(
            db, tenant, saver, _FirstAttemptDiesBeforeGraph(), independent_sessions,
        ).execute(review_id=arranged.review_item_id, request=_approve())

    class _CannotFork:
        checkpointer = saver
        async def aupdate_state(self, *_args, **_kwargs):
            raise RuntimeError("simulated saver fork failure")
        async def ainvoke(self, *_args, **_kwargs):
            raise AssertionError("should never execute graph without a fork")

    with pytest.raises(RuntimeError, match="checkpoint fork failed"):
        await _use_case(
            db, tenant, saver, _CannotFork(), independent_sessions,
        ).execute(review_id=arranged.review_item_id, request=_approve())
    op = await _operation_row(
        independent_sessions, tenant.id, arranged.review_row_id
    )
    assert op.fencing_token == 2 and op.attempts == 2
    assert len(N17_RUNS) == 0
    assert await _counts(db, arranged.project_id) == (0, 0)
    assert await _persisted_events(db, arranged.project_id) == 0
    assert (await _reload(db, ReviewItemORM, arranged.review_row_id)).current_status == (
        ReviewStatus.PENDING_REVIEW_REQUIRED.value
    )


async def test_d1_1103_wrong_thread_only_identity_is_rejected(
    real_saver, independent_sessions, db, test_user: User,
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    document = await _seed(db, tenant)
    actual_thread = str(uuid4())
    register(actual_thread)
    app = _build_real_graph(saver)
    result = await app.ainvoke(
        _initial_state(document, tenant, actual_thread),
        {"configurable": {"thread_id": actual_thread}},
    )
    assert "__interrupt__" in result
    review = (
        await db.execute(select(ReviewItemORM).where(ReviewItemORM.document_id == document.id))
    ).scalars().one()
    review.thread_id = str(uuid4())  # Another valid UUID, no checkpoint on it.
    review.checkpoint_id = None
    review.review_metadata = {**(review.review_metadata or {}), "tenant_id": str(tenant.id)}
    await db.commit()
    N17_RUNS.clear()
    with pytest.raises(ValueError, match="checkpoint"):
        await _use_case(db, tenant, saver, app, independent_sessions).execute(
            review_id=review.item_id, request=_approve()
        )
    assert len(N17_RUNS) == 0
    assert await _counts(db, document.project_id) == (0, 0)
    assert await _persisted_events(db, document.project_id) == 0
