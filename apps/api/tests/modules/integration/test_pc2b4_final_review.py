"""PC-2b.4 (#923) final offline review -- database part (TS-INT-PC2B4-FINAL-REVIEW-001).

* CR-F2 / SEC-P1-3  the RUNNING run is committed before any model call, so another session sees and
  cancels it, and no change-set lock or open transaction is held while the model works; a run that
  was cancelled elsewhere finishes CANCELLED with its usage recorded.
* CR-F2 (lease)     a RUNNING run whose worker was lost is reused only within its lease; afterwards it
  is failed and a new run opens.
* CR-F5             an unexpected pipeline exception persists a FAILED run (static reason) and usage
  instead of leaving nothing behind.
* CR-F6 / SEC-P2-1  contract and scope availability come from the evidence the model actually sees.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.documents.domain.models import DocumentType
from src.temporal.adapters.persistence.models import ProjectEventORM
from src.wbs.adapters.persistence.governance_models import WBSChangeSetORM
from src.wbs.adapters.persistence.intelligence_models import (
    WBSIntelligenceItemORM,
    WBSIntelligenceRunORM,
)
from src.wbs.intelligence.application.service import WBSIntelligenceService
from src.wbs.intelligence.contracts.run import RunOutcome
from src.wbs.intelligence.reviewer import service as reviewer_service
from src.wbs.intelligence.reviewer.fake_model import FakeReviewerModelAdapter
from src.wbs.intelligence.reviewer.model_port import ModelCallRequest
from src.wbs.intelligence.reviewer.service import EVENT_RUN_USAGE, ReviewTargetKind
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import _scope
from tests.modules.integration.test_pc2b4_wbs_reviewer import (
    SPEC,
    _count,
    _document,
    _draft,
    _model,
    _reviewer,
    _world,
)

pytestmark = pytest.mark.asyncio


def _engine() -> Any:
    return create_async_engine(os.environ["TEST_DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://"))


async def _usage_events(db: AsyncSession, run_id: UUID) -> int:
    rows = (await db.execute(select(ProjectEventORM).where(ProjectEventORM.event_type == EVENT_RUN_USAGE))).scalars()
    return sum(1 for event in rows if event.payload.get("run_id") == str(run_id))


# =========================================================================== CR-F2 / SEC-P1-3
async def test_cr_f2_a_running_review_is_visible_cancellable_and_holds_no_lock(
        db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    s, change_set_id, ids = await _world(db)
    entered, release = asyncio.Event(), asyncio.Event()
    original = FakeReviewerModelAdapter.complete

    async def waiting(self: FakeReviewerModelAdapter, request: ModelCallRequest) -> Any:
        entered.set()
        await release.wait()
        return await original(self, request)

    monkeypatch.setattr(FakeReviewerModelAdapter, "complete", waiting)
    engine = _engine()
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as worker, sessions() as human:
            task = asyncio.create_task(_reviewer(worker, _model(ids)).review(
                project_id=s.project, tenant_id=s.tenant, actor=s.author, target=ReviewTargetKind.DRAFT,
                change_set_id=change_set_id))
            outcome: list[Any] = []
            try:
                await asyncio.wait_for(entered.wait(), 20)  # the model is working now
                running = (await human.execute(select(WBSIntelligenceRunORM).where(
                    WBSIntelligenceRunORM.project_id == s.project))).scalars().all()
                assert [r.status for r in running] == ["RUNNING"]  # committed before any model call
                run_id = running[0].id
                await human.execute(text("SET LOCAL lock_timeout = '2s'"))
                await human.execute(select(WBSChangeSetORM.id).where(WBSChangeSetORM.id == change_set_id)
                                    .with_for_update())  # no lock is held while the model works
                await human.rollback()
                await WBSIntelligenceService(human).cancel_run(project_id=s.project, run_id=run_id,
                                                               tenant_id=s.tenant, actor=s.author)
                await human.commit()
            finally:
                release.set()
                outcome = await asyncio.gather(asyncio.wait_for(task, 20), return_exceptions=True)
                await worker.rollback() if isinstance(outcome[0], BaseException) else await worker.commit()
            result = outcome[0]
            assert not isinstance(result, BaseException), result
    finally:
        await engine.dispose()
    assert (result.run.status, result.run.outcome) == ("CANCELLED", "CANCELLED")
    assert await _count(db, WBSIntelligenceItemORM, run_id=result.run.id) == 0
    assert await _usage_events(db, result.run.id) == 1


# =========================================================================== CR-F2 lease
async def test_cr_f2_a_lost_worker_run_is_reused_within_its_lease_and_replaced_after(
        db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    s, change_set_id, ids = await _world(db)

    async def lost(self: FakeReviewerModelAdapter, request: ModelCallRequest) -> Any:
        raise asyncio.CancelledError  # the worker is gone mid-call

    monkeypatch.setattr(FakeReviewerModelAdapter, "complete", lost)
    with pytest.raises(asyncio.CancelledError):
        await _reviewer(db, _model(ids)).review(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                target=ReviewTargetKind.DRAFT, change_set_id=change_set_id)
    await db.rollback()
    monkeypatch.undo()

    within = await _reviewer(db, _model(ids)).review(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                     target=ReviewTargetKind.DRAFT, change_set_id=change_set_id)
    await db.commit()
    assert within.reused and within.run.status == "RUNNING"  # in progress elsewhere: never duplicated

    later = datetime.now(UTC) + timedelta(hours=2)
    monkeypatch.setattr(reviewer_service, "_utcnow", lambda: later)
    after = await _reviewer(db, _model(ids)).review(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                    target=ReviewTargetKind.DRAFT, change_set_id=change_set_id)
    await db.commit()
    assert not after.reused and after.run.id != within.run.id and after.run.status == "COMPLETED"
    stale = await db.scalar(select(WBSIntelligenceRunORM.status).where(WBSIntelligenceRunORM.id == within.run.id)
                            .execution_options(populate_existing=True))
    assert stale == "FAILED"


# =========================================================================== CR-F5
async def test_cr_f5_an_unexpected_pipeline_exception_persists_a_failed_run_and_its_usage(
        db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    s, change_set_id, ids = await _world(db)

    async def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("SECRET-MODEL-TEXT")

    monkeypatch.setattr(reviewer_service, "run_review_pipeline", broken)
    result = await _reviewer(db, _model(ids)).review(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                     target=ReviewTargetKind.DRAFT, change_set_id=change_set_id)
    await db.commit()
    assert (result.run.status, result.run.outcome) == ("FAILED", "FAILED")
    assert "SECRET-MODEL-TEXT" not in (result.run.failure_reason or "")
    assert await _usage_events(db, result.run.id) == 1


# =========================================================================== CR-F6 / SEC-P2-1
async def test_cr_f6_a_contract_without_visible_excerpts_cannot_make_contract_scope_evaluable(
        db: AsyncSession) -> None:
    s = await _scope(db)
    await _document(db, s, chunks=())  # a trusted contract that contributed no excerpt
    await _document(db, s, document_type=DocumentType.SPECIFICATION, chunks=(SPEC,))
    change_set_id, ids = await _draft(db, s)
    gap = [{"dimension": "MISSING_CONTRACT_SCOPE", "status": "GAP", "summary": "Missing scope",
            "evidence": [{"excerpt_id": "E001", "basis": "DIRECT", "quote": "coordinated at each foundation"}]}]
    result = await _reviewer(db, _model(ids, findings=[], proposals=[], qualification=gap)).review(
        project_id=s.project, tenant_id=s.tenant, actor=s.author, target=ReviewTargetKind.DRAFT,
        change_set_id=change_set_id)
    await db.commit()
    report = {r["dimension"]: r for r in result.run.qualification["results"]}
    assert report["MISSING_CONTRACT_SCOPE"]["status"] == "NOT_EVALUATED"
    assert report["MISSING_CONTRACT_SCOPE"]["reason_code"] == "NO_TRUSTED_CONTRACT"


async def test_cr_f6_only_non_scope_trusted_excerpts_abstain_with_zero_calls(db: AsyncSession) -> None:
    s = await _scope(db)
    await _document(db, s, chunks=())  # the trusted contract is not visible
    await _document(db, s, document_type=DocumentType.DRAWING, chunks=("Drawing notes for the trench layout.",))
    change_set_id, ids = await _draft(db, s)
    fake = _model(ids)
    result = await _reviewer(db, fake).review(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                              target=ReviewTargetKind.DRAFT, change_set_id=change_set_id)
    await db.commit()
    assert fake.calls == [] and result.run.outcome == RunOutcome.INSUFFICIENT_EVIDENCE.value
