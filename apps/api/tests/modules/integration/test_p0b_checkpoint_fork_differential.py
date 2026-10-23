"""Real PostgreSQL + LangGraph differential for HITL takeover (fencing_token > 1).

A takeover attempt resumes from an ``aupdate_state`` FORK of the interrupt
checkpoint (``ResumeWorkflowUseCase._fork_for_attempt``). LangGraph reports the
fork's pending task WITHOUT its interrupt payload (``tasks[].interrupts == ()``),
which looked like a lost interrupt. This suite pins the behaviour that actually
matters, on the real graph, the real ``AsyncPostgresSaver`` and real PostgreSQL:

* the metadata difference is real (so a future LangGraph change is noticed), and
* the fork's ``Command(resume=...)`` IS consumed: N13 completes, N17 persists
  exactly one analysis, ``analysis_id`` matches the persisted row and the
  ``graph.completed`` event, and a repeated approval never re-runs the graph.

The decisive precondition is ``source_checkpoint_id == restored.checkpoint_id``
with ``fencing_token == 2``: the first attempt died before advancing the thread,
so the takeover cannot use the "pin the source checkpoint" branch and must fork.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Analysis
from src.core.auth.models import Tenant, User
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.adapters.persistence.resume_ownership import Phase
from src.modules.hitl.domain.entities import ReviewStatus
from src.temporal.adapters.persistence.models import ProjectEventORM
from tests.modules.integration import test_p0b_crash_safe_resume_recovery as recovery
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (  # noqa: F401
    InjectedCrash,
    _approve,
    _arrange,
    _counts,
    _operation_row,
    _reload,
    _use_case,
    independent_sessions,  # pytest fixture re-export
    real_saver,  # pytest fixture re-export
)

pytestmark = pytest.mark.asyncio


class _ObservedGraph:
    """Delegates to the REAL compiled graph and records what the attempt resumed from."""

    def __init__(self, app: Any, saver: Any) -> None:
        self._app = app
        self.checkpointer = saver
        self.resumed_config: dict[str, Any] | None = None
        self.pending_before_resume: dict[str, Any] | None = None

    async def aget_state(self, config: dict[str, Any]) -> Any:
        return await self._app.aget_state(config)

    async def aupdate_state(self, config: dict[str, Any], values: dict[str, Any]) -> Any:
        return await self._app.aupdate_state(config, values)

    async def ainvoke(self, payload: Any, config: dict[str, Any]) -> dict[str, Any]:
        self.resumed_config = config
        snapshot = await self._app.aget_state(config)
        self.pending_before_resume = {
            "checkpoint_id": config["configurable"].get("checkpoint_id"),
            "next": tuple(snapshot.next),
            "interrupt_counts": [len(t.interrupts) for t in snapshot.tasks],
        }
        return await self._app.ainvoke(payload, config)


async def test_takeover_fork_with_source_equal_restored_consumes_interrupt_and_persists_once(
    real_saver, independent_sessions, db: AsyncSession, test_user: User
) -> None:
    saver, register = real_saver
    tenant = await db.get(Tenant, test_user.tenant_id)
    arranged = await _arrange(db, tenant, saver, register)
    recovery.N17_RUNS.clear()

    # Attempt 1 is claimed (fencing_token=1) and dies before the graph advances.
    class _DiesBeforeGraph:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise InjectedCrash("worker lost after claim, before graph")

    with pytest.raises(InjectedCrash):
        await _use_case(db, tenant, saver, _DiesBeforeGraph(), independent_sessions).execute(
            review_id=arranged.review_item_id, request=_approve()
        )
    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.phase == Phase.FAILED_RETRYABLE.value
    assert op.fencing_token == 1
    assert list(recovery.N17_RUNS) == []

    # Precondition of the P1 case: the thread did NOT advance, so the interrupt
    # checkpoint is still the latest one (source_checkpoint_id == restored).
    latest = await arranged.app.aget_state({"configurable": {"thread_id": _thread(arranged)}})
    assert latest.config["configurable"]["checkpoint_id"] == arranged.checkpoint_id
    assert latest.next == ("human_interrupt",)
    assert any(task.interrupts for task in latest.tasks), "the original keeps its interrupt"

    # Attempt 2 (fencing_token=2) takes over.
    observed = _ObservedGraph(arranged.app, saver)
    response = await _use_case(db, tenant, saver, observed, independent_sessions).execute(
        review_id=arranged.review_item_id, request=_approve()
    )
    assert response.status == "resumed"

    # The takeover really resumed through a fork (not the original) ...
    assert observed.pending_before_resume is not None
    assert observed.pending_before_resume["checkpoint_id"] != arranged.checkpoint_id
    # ... whose pending task LangGraph reports without interrupt payload ...
    assert observed.pending_before_resume["next"] == ("human_interrupt",)
    assert observed.pending_before_resume["interrupt_counts"] == [0]
    # ... and still the resume was consumed all the way to durable persistence.
    assert list(recovery.N17_RUNS) == [str(arranged.document_id)], "N17 runs exactly once"

    op = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op.fencing_token == 2
    assert op.attempts == 2
    assert op.analysis_id is not None
    assert op.terminal_checkpoint_id

    analyses = (
        (await db.execute(select(Analysis).where(Analysis.project_id == arranged.project_id)))
        .scalars()
        .all()
    )
    assert len(analyses) == 1
    assert analyses[0].id == op.analysis_id, "operation analysis_id is the persisted row"

    events = (
        (
            await db.execute(
                select(ProjectEventORM).where(
                    ProjectEventORM.project_id == arranged.project_id,
                    ProjectEventORM.event_type == "graph.completed",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].payload["analysis_id"] == str(analyses[0].id)

    review = await _reload(db, ReviewItemORM, arranged.review_row_id)
    assert review.current_status == ReviewStatus.APPROVED.value

    # A repeated approval is idempotent: no new attempt, no second graph run.
    class _MustNotRun:
        checkpointer = saver

        async def ainvoke(self, *_a: Any, **_k: Any) -> dict:
            raise AssertionError("a finalized operation must never re-run the graph")

    again = await _use_case(db, tenant, saver, _MustNotRun(), independent_sessions).execute(
        review_id=arranged.review_item_id, request=_approve()
    )
    assert again.status in {"resumed", ReviewStatus.APPROVED.value}
    assert list(recovery.N17_RUNS) == [str(arranged.document_id)]
    assert await _counts(db, arranged.project_id) == (1, 1)
    op_after = await _operation_row(independent_sessions, tenant.id, arranged.review_row_id)
    assert op_after.fencing_token == 2
    assert op_after.attempts == 2


def _thread(arranged: Any) -> str:
    return f"document:{arranged.document_id}:analysis"
