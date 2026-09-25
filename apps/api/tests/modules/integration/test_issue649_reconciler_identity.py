"""Real PostgreSQL regressions for recovery identity, not human revision APIs.

Mutations caught: empty feedback fallback; generic human reacquisition;
business-ID lookup; live-lease bypass; resetting durable N17 progress.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.core.auth.models import Tenant
from src.core.tasks import hitl_resume_reconciler as reconciler
from src.modules.hitl.adapters.checkpoint_service import CheckpointService
from src.modules.hitl.adapters.persistence import resume_ownership as claims
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.adapters.persistence.repository import SqlAlchemyReviewQueueRepository
from src.modules.hitl.adapters.persistence.resume_recovery import (
    RecoveryOutcome,
    ResumeRecoveryRequest,
    acquire_for_reconciliation,
)
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowRequest,
    ResumeWorkflowUseCase,
    WorkflowDecision,
)
from tests.modules.integration.test_issue649_hitl_audit_idempotency import (
    _events,
    request_sessions,  # noqa: F401
    snapshot_enqueues,  # noqa: F401
)
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    N17_RUNS,
    _arrange,
    _reload,
    _use_case,
    independent_sessions,  # noqa: F401
    real_saver,  # noqa: F401
)

pytestmark = pytest.mark.asyncio


async def _operation(sessions, tenant, row_id):
    async with sessions(tenant.id) as session:
        return (
            (
                await session.execute(
                    text(
                        "SELECT * FROM resume_operations WHERE review_row_id = :r AND tenant_id = :t"
                    ),
                    {"r": row_id, "t": tenant.id},
                )
            )
            .mappings()
            .one()
        )


async def _claim(sessions, tenant, arranged, *, decision="reject", feedback="human reason"):
    ownership, _, _ = await claims.acquire(
        review_row_id=arranged.review_row_id,
        tenant_id=tenant.id,
        project_id=arranged.project_id,
        document_id=arranged.document_id,
        thread_id=f"document:{arranged.document_id}:analysis",
        source_checkpoint_id=arranged.checkpoint_id,
        decision=decision,
        feedback=feedback,
        reviewer="Original reviewer",
        session_factory=sessions,
    )
    assert ownership is not None
    return ownership


async def _expire(sessions, tenant, row_id):
    async with sessions(tenant.id) as session:
        await session.execute(
            text(
                "UPDATE resume_operations SET lease_expires_at = clock_timestamp() - interval '1 second', "
                "next_attempt_at = NULL WHERE review_row_id = :r"
            ),
            {"r": row_id},
        )


async def _sweep(
    sessions, tenant, saver, app, *, entered=None, proceed=None, scan_pids=None, batch_size=20
):
    @asynccontextmanager
    async def factory(tenant_id):
        async with sessions(tenant_id or tenant.id) as session:
            if tenant_id is None and scan_pids is not None:
                scan_pids.append(
                    (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
                )
            yield session

    class PausedUseCase(ResumeWorkflowUseCase):
        async def _barrier(self):
            if entered is not None:
                entered.set()
                await asyncio.wait_for(proceed.wait(), 10)

        async def execute(self, *args, **kwargs):
            await self._barrier()
            return await super().execute(*args, **kwargs)

        async def recover(self, *args, **kwargs):
            await self._barrier()
            return await super().recover(*args, **kwargs)

    def build(session, tenant_id):
        return PausedUseCase(
            review_queue_repo=SqlAlchemyReviewQueueRepository(session, tenant_id),
            checkpoint_service=CheckpointService(saver),
            graph_app=app,
            claim_session_factory=sessions,
        )

    return await reconciler._sweep_async(
        batch_size=batch_size, session_factory=factory, use_case_factory=build
    )


async def test_legacy_unknown_feedback_never_becomes_empty(
    db,
    test_user,
    real_saver,
    independent_sessions,
    snapshot_enqueues,
):
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    await _claim(independent_sessions, tenant, arranged)
    before = await _operation(independent_sessions, tenant, arranged.review_row_id)
    async with independent_sessions(tenant.id) as session:
        await session.execute(
            text(
                "UPDATE resume_operations SET operation_metadata = operation_metadata - 'feedback' "
                "WHERE id = :id"
            ),
            {"id": before["id"]},
        )
    await _expire(independent_sessions, tenant, arranged.review_row_id)
    N17_RUNS.clear()
    result = await _sweep(independent_sessions, tenant, saver, arranged.app)
    after = await _operation(independent_sessions, tenant, arranged.review_row_id)
    assert after["decision_revision"] == 1
    assert after["decision_hash"] == before["decision_hash"]
    assert after["decision"] == "reject"
    assert after["phase"] == "OPERATOR_REQUIRED"
    assert "missing_authoritative_feedback" in after["last_error"]
    assert result["recovered"] == 0
    stored = await _reload(db, ReviewItemORM, arranged.review_row_id)
    assert stored.review_metadata.get("rejection_reason") is None
    assert stored.review_decision is None
    assert not await _events(db, arranged.project_id, "hitl.correction")
    assert not await _events(db, arranged.project_id, "analysis.persisted")
    assert N17_RUNS == []


@pytest.mark.parametrize("changed", [True, False], ids=["human_revision", "live_owner"])
async def test_scan_loses_to_new_human_owner(
    db,
    test_user,
    real_saver,
    independent_sessions,
    request_sessions,
    snapshot_enqueues,
    changed,
):
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    await _claim(independent_sessions, tenant, arranged)
    await _expire(independent_sessions, tenant, arranged.review_row_id)
    entered, proceed = asyncio.Event(), asyncio.Event()
    scan_pids, human_pids = [], []

    @asynccontextmanager
    async def human_sessions(tenant_id):
        async with request_sessions() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(tenant_id)}
            )
            human_pids.append((await session.execute(text("SELECT pg_backend_pid()"))).scalar_one())
            yield session
            await session.commit()

    task = asyncio.create_task(
        _sweep(
            independent_sessions,
            tenant,
            saver,
            arranged.app,
            entered=entered,
            proceed=proceed,
            scan_pids=scan_pids,
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 10)
        await _claim(
            human_sessions,
            tenant,
            arranged,
            feedback="new human reason" if changed else "human reason",
        )
        winner = await _operation(independent_sessions, tenant, arranged.review_row_id)
        assert set(scan_pids).isdisjoint(human_pids), "real separate PostgreSQL connections"
        proceed.set()
        result = await asyncio.wait_for(task, 20)
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    after = await _operation(independent_sessions, tenant, arranged.review_row_id)
    for key in (
        "decision",
        "decision_hash",
        "decision_revision",
        "fencing_token",
        "current_attempt_id",
        "owner_token",
    ):
        assert after[key] == winner[key], key
    assert result["recovered"] == 0
    assert not await _events(db, arranged.project_id, "hitl.correction")


async def test_recovery_keeps_exact_duplicate_review_row(
    db,
    test_user,
    real_saver,
    independent_sessions,
    snapshot_enqueues,
):
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    await _claim(independent_sessions, tenant, arranged)
    await _expire(independent_sessions, tenant, arranged.review_row_id)
    original = await _reload(db, ReviewItemORM, arranged.review_row_id)
    sibling_id = uuid4()
    db.add(
        ReviewItemORM(
            id=sibling_id,
            tenant_id=tenant.id,
            item_id=original.item_id,
            item_type=original.item_type,
            current_status=original.current_status,
            confidence=original.confidence,
            impact_level=original.impact_level,
            sla_due_date=original.sla_due_date,
            created_at=original.created_at + timedelta(days=1),
            item_data=dict(original.item_data),
            review_metadata=dict(original.review_metadata),
            thread_id=original.thread_id,
            checkpoint_id=original.checkpoint_id,
            project_id=original.project_id,
            document_id=original.document_id,
            review_type=original.review_type,
        )
    )
    await db.commit()
    repo = SqlAlchemyReviewQueueRepository(db, tenant.id)
    canonical = await repo.get_review_item(arranged.review_item_id)
    assert canonical.metadata["row_id"] == str(sibling_id)
    result = await _sweep(independent_sessions, tenant, saver, arranged.app)
    target = await _reload(db, ReviewItemORM, arranged.review_row_id)
    sibling = await _reload(db, ReviewItemORM, sibling_id)
    assert target.current_status == "REJECTED"
    assert target.review_decision == "human reason"
    assert sibling.current_status == "PENDING_REVIEW_REQUIRED"
    assert sibling.approved_at is None and sibling.review_decision is None
    async with independent_sessions(tenant.id) as session:
        assert (
            await session.execute(
                text("SELECT count(*) FROM resume_operations WHERE review_row_id = :r"),
                {"r": sibling_id},
            )
        ).scalar_one() == 0
    events = await _events(db, arranged.project_id, "hitl.correction")
    assert len(events) == 1 and events[0].payload["review_row_id"] == str(arranged.review_row_id)
    assert result["recovered"] == 1


@pytest.mark.parametrize(
    "boundary", ["after_graph_before_terminal_marker", "after_terminal_marker_before_finalize"]
)
async def test_recovery_preserves_post_n17_decision_and_effects(
    db,
    test_user,
    real_saver,
    independent_sessions,
    snapshot_enqueues,
    boundary,
):
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)

    async def crash(stage):
        if stage == boundary:
            raise RuntimeError("injected crash after durable effects")

    with pytest.raises(RuntimeError, match="injected crash"):
        await _use_case(db, tenant, saver, arranged.app, independent_sessions, fault=crash).execute(
            arranged.review_row_id,
            ResumeWorkflowRequest(
                WorkflowDecision.APPROVE, "approved human text", "Original reviewer"
            ),
        )
    before = await _operation(independent_sessions, tenant, arranged.review_row_id)
    assert before["phase"] in {"N17_DURABLE", "GRAPH_COMPLETED"}
    n17_before = list(N17_RUNS)
    await _expire(independent_sessions, tenant, arranged.review_row_id)
    result = await _sweep(independent_sessions, tenant, saver, arranged.app)
    after = await _operation(independent_sessions, tenant, arranged.review_row_id)
    assert result["recovered"] == 1, result
    assert after["phase"] == "FINALIZED_APPROVED"
    assert after["fencing_token"] == before["fencing_token"] + 1
    assert after["current_attempt_id"] != before["current_attempt_id"]
    assert after["owner_token"] != before["owner_token"]
    if boundary == "after_terminal_marker_before_finalize":
        assert n17_before == N17_RUNS, "terminal recovery must not invoke the graph"
    for key in ("decision", "decision_hash", "decision_revision", "analysis_id", "reviewer"):
        assert after[key] == before[key], key
    assert after["operation_metadata"]["feedback"] == "approved human text"
    for event_type in ("analysis.persisted", "graph.completed", "hitl.correction"):
        assert len(await _events(db, arranged.project_id, event_type)) == 1


def _expected(row):
    return ResumeRecoveryRequest(
        operation_id=row["id"],
        review_row_id=row["review_row_id"],
        tenant_id=row["tenant_id"],
        expected_decision=row["decision"],
        expected_decision_hash=row["decision_hash"],
        expected_decision_revision=row["decision_revision"],
        expected_fencing_token=row["fencing_token"],
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation_id", uuid4()),
        ("review_row_id", uuid4()),
        ("tenant_id", uuid4()),
        ("expected_decision", "approve"),
        ("expected_decision_hash", "stale hash"),
        ("expected_decision_revision", 0),
        ("expected_fencing_token", 0),
    ],
)
async def test_every_scanned_identity_is_required(
    db,
    test_user,
    real_saver,
    independent_sessions,
    field,
    value,
):
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    await _claim(independent_sessions, tenant, arranged)
    await _expire(independent_sessions, tenant, arranged.review_row_id)
    before = await _operation(independent_sessions, tenant, arranged.review_row_id)
    refused = await acquire_for_reconciliation(
        replace(_expected(before), **{field: value}),
        session_factory=independent_sessions,
    )
    assert refused.outcome in {RecoveryOutcome.STALE, RecoveryOutcome.NOT_VISIBLE}
    assert refused.ownership is None
    after = await _operation(independent_sessions, tenant, arranged.review_row_id)
    assert dict(after) == dict(before)
    wrong_tenant_repo = SqlAlchemyReviewQueueRepository(db, uuid4())
    assert await wrong_tenant_repo.get_review_item_by_row_id(arranged.review_row_id) is None


@pytest.mark.parametrize(
    "mode",
    [
        "explicit_empty",
        "legacy_verified",
        "legacy_verified_empty",
        "corrupt_feedback",
        "legacy_empty_unknown",
    ],
)
async def test_feedback_requires_plaintext_and_matching_durable_hash(
    db,
    test_user,
    real_saver,
    independent_sessions,
    snapshot_enqueues,
    mode,
):
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    feedback = (
        ""
        if mode in {"explicit_empty", "legacy_verified_empty", "legacy_empty_unknown"}
        else "human reason"
    )
    await _claim(independent_sessions, tenant, arranged, feedback=feedback)
    await _expire(independent_sessions, tenant, arranged.review_row_id)
    before = await _operation(independent_sessions, tenant, arranged.review_row_id)
    async with independent_sessions(tenant.id) as session:
        if mode in {"legacy_verified", "legacy_verified_empty", "legacy_empty_unknown"}:
            await session.execute(
                text("UPDATE resume_operations SET operation_metadata = '{}' WHERE id = :id"),
                {"id": before["id"]},
            )
        if mode in {"legacy_verified", "legacy_verified_empty"}:
            await session.execute(
                text("UPDATE review_items SET review_decision = :feedback WHERE id = :id"),
                {"id": arranged.review_row_id, "feedback": feedback},
            )
        if mode == "corrupt_feedback":
            await session.execute(
                text(
                    'UPDATE resume_operations SET operation_metadata = \'{"feedback":"wrong"}\' WHERE id = :id'
                ),
                {"id": before["id"]},
            )
    result = await _sweep(independent_sessions, tenant, saver, arranged.app)
    after = await _operation(independent_sessions, tenant, arranged.review_row_id)
    assert after["decision_hash"] == before["decision_hash"]
    assert after["decision_revision"] == 1
    if mode in {"corrupt_feedback", "legacy_empty_unknown"}:
        assert result["recovered"] == 0
        assert after["phase"] == "OPERATOR_REQUIRED"
        assert not await _events(db, arranged.project_id, "hitl.correction")
    else:
        assert result["recovered"] == 1
        assert after["operation_metadata"]["feedback"] == feedback
        review = await _reload(db, ReviewItemORM, arranged.review_row_id)
        assert review.review_metadata["rejection_reason"] == feedback
        assert (await _events(db, arranged.project_id, "hitl.correction"))[0].payload[
            "reason"
        ] == feedback


@pytest.mark.parametrize(
    "mode", ["retry_due_later", "failed_but_live", "malformed_lease", "finalized", "operator"]
)
async def test_recovery_refuses_due_phase_and_live_owner_even_when_retryable(
    db,
    test_user,
    real_saver,
    independent_sessions,
    mode,
):
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    ownership = await _claim(independent_sessions, tenant, arranged)
    updates = {
        "retry_due_later": "lease_expires_at = clock_timestamp() - interval '1 second', next_attempt_at = clock_timestamp() + interval '1 hour'",
        "failed_but_live": "phase = 'FAILED_RETRYABLE'",
        "malformed_lease": "lease_expires_at = NULL",
        "finalized": "phase = 'FINALIZED_REJECTED'",
        "operator": "phase = 'OPERATOR_REQUIRED'",
    }
    async with independent_sessions(tenant.id) as session:
        await session.execute(
            text("UPDATE resume_operations SET " + updates[mode] + " WHERE id = :id"),
            {"id": ownership.operation_id},
        )
    before = await _operation(independent_sessions, tenant, arranged.review_row_id)
    result = await acquire_for_reconciliation(
        _expected(before), session_factory=independent_sessions
    )
    assert (
        result.outcome
        == {
            "retry_due_later": RecoveryOutcome.NOT_DUE,
            "failed_but_live": RecoveryOutcome.BUSY,
            "malformed_lease": RecoveryOutcome.BUSY,
            "finalized": RecoveryOutcome.ALREADY_FINALIZED,
            "operator": RecoveryOutcome.OPERATOR_REQUIRED,
        }[mode]
    )
    assert dict(await _operation(independent_sessions, tenant, arranged.review_row_id)) == dict(
        before
    )


async def test_quarantine_fences_late_failure_handler(
    db,
    test_user,
    real_saver,
    independent_sessions,
):
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    old_owner = await _claim(independent_sessions, tenant, arranged)
    await _expire(independent_sessions, tenant, arranged.review_row_id)
    async with independent_sessions(tenant.id) as session:
        await session.execute(
            text("UPDATE resume_operations SET operation_metadata = '{}' WHERE id = :id"),
            {"id": old_owner.operation_id},
        )
    before = await _operation(independent_sessions, tenant, arranged.review_row_id)
    result = await acquire_for_reconciliation(
        _expected(before), session_factory=independent_sessions
    )
    assert result.outcome == RecoveryOutcome.OPERATOR_REQUIRED
    await claims.record_failure(
        ownership=old_owner, error="late failed graph", session_factory=independent_sessions
    )
    assert not await claims.renew(
        ownership=old_owner, lease_seconds=120, session_factory=independent_sessions
    )
    after = await _operation(independent_sessions, tenant, arranged.review_row_id)
    assert after["phase"] == "OPERATOR_REQUIRED"
    assert after["last_error"] == "missing_authoritative_feedback"
    assert after["fencing_token"] == old_owner.fencing_token + 1


async def test_deleted_review_operation_cannot_starve_bounded_sweep(
    db,
    test_user,
    real_saver,
    independent_sessions,
    snapshot_enqueues,
):
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    orphan = await _arrange(db, tenant, saver, register)
    await _claim(independent_sessions, tenant, orphan)
    await _expire(independent_sessions, tenant, orphan.review_row_id)
    async with independent_sessions(tenant.id) as session:
        await session.execute(
            text("DELETE FROM review_items WHERE id = :id"), {"id": orphan.review_row_id}
        )
        await session.execute(
            text(
                "UPDATE resume_operations SET updated_at = clock_timestamp() - interval '1 day' WHERE review_row_id = :id"
            ),
            {"id": orphan.review_row_id},
        )
    valid = await _arrange(db, tenant, saver, register)
    await _claim(independent_sessions, tenant, valid)
    await _expire(independent_sessions, tenant, valid.review_row_id)
    result = await _sweep(independent_sessions, tenant, saver, valid.app, batch_size=1)
    assert result["recovered"] == 1
    assert (await _operation(independent_sessions, tenant, valid.review_row_id))[
        "phase"
    ] == "FINALIZED_REJECTED"


async def test_human_retry_keeps_document_identity_from_exact_review(
    db,
    test_user,
    real_saver,
    independent_sessions,
    snapshot_enqueues,
):
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    await _claim(independent_sessions, tenant, arranged, decision="approve")
    await _expire(independent_sessions, tenant, arranged.review_row_id)
    async with independent_sessions(tenant.id) as session:
        await session.execute(
            text("UPDATE resume_operations SET document_id = NULL WHERE review_row_id = :r"),
            {"r": arranged.review_row_id},
        )
    await _use_case(db, tenant, saver, arranged.app, independent_sessions).execute(
        arranged.review_row_id,
        ResumeWorkflowRequest(WorkflowDecision.APPROVE, "human reason", "Original reviewer"),
    )
    assert (await _operation(independent_sessions, tenant, arranged.review_row_id))[
        "phase"
    ] == "FINALIZED_APPROVED"
