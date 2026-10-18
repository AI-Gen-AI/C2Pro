"""PC-2b.4 (#923) offline merge gate -- Reviewer session ownership (TS-INT-PC2B4-SESSION-001).

The review commits (the RUNNING run must be visible before any model call), so it owns the session
it is given for the whole call: it refuses a session that carries any caller work -- an open
transaction, or pending ORM changes -- instead of committing or discarding it, binds the tenant in
its own first transaction, and ends every transaction it opens on every path (success, failure,
finalization failure, cancellation, reuse and refusal), so it never strands a lock either.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.exceptions import C2ProException
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.wbs.adapters.persistence.governance_models import WBSChangeSetORM
from src.wbs.adapters.persistence.intelligence_models import WBSIntelligenceRunORM
from src.wbs.intelligence.application.service import WBSIntelligenceService
from src.wbs.intelligence.reviewer import service as reviewer_service
from src.wbs.intelligence.reviewer.fake_model import FakeReviewerModelAdapter
from src.wbs.intelligence.reviewer.model_port import ModelCallRequest
from src.wbs.intelligence.reviewer.service import ReviewResult, ReviewTargetKind
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import Scope
from tests.modules.integration.test_pc2b4_wbs_reviewer import _chunk, _model, _reviewer, _world

pytestmark = pytest.mark.asyncio

NOT_OWNED = "WBS_REVIEWER_SESSION_NOT_OWNED"


def _engine() -> Any:
    return create_async_engine(os.environ["TEST_DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://"))


async def _review(db: AsyncSession, s: Scope, change_set_id: UUID, ids: dict[str, UUID], *,
                  target: ReviewTargetKind = ReviewTargetKind.DRAFT, **kwargs: Any) -> ReviewResult:
    return await _reviewer(db, _model(ids)).review(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                   target=target, change_set_id=change_set_id, **kwargs)


async def _runs(project_id: UUID) -> list[str]:
    """Run statuses as another session sees them (committed state only)."""
    engine = _engine()
    try:
        async with async_sessionmaker(engine)() as other:
            return list((await other.execute(select(WBSIntelligenceRunORM.status).where(
                WBSIntelligenceRunORM.project_id == project_id))).scalars())
    finally:
        await engine.dispose()


async def _document_id(db: AsyncSession, s: Scope) -> UUID:
    document_id = await db.scalar(select(DocumentORM.id).where(DocumentORM.project_id == s.project).limit(1))
    assert document_id is not None
    return document_id


async def _chunks(project_id: UUID, content: str) -> int:
    engine = _engine()
    try:
        async with async_sessionmaker(engine)() as other:
            return int(await other.scalar(text(
                "SELECT count(*) FROM document_chunks WHERE project_id = :p AND content = :c"),
                {"p": project_id, "c": content}) or 0)
    finally:
        await engine.dispose()


# =========================================================================== caller work is never touched
async def test_own_01_a_pending_sql_write_is_refused_and_left_to_the_caller(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    marker = f"caller-work-{uuid4()}"
    await _chunk(db, s.tenant, s.project, await _document_id(db, s), marker, {"note": "unrelated"})  # caller's open tx
    with pytest.raises(C2ProException) as refused:
        await _review(db, s, change_set_id, ids)
    assert refused.value.code == NOT_OWNED
    assert db.in_transaction()  # the caller's transaction is still the caller's
    assert await _chunks(s.project, marker) == 0  # never committed on the caller's behalf
    await db.rollback()  # the caller decides
    assert await _chunks(s.project, marker) == 0
    assert await _runs(s.project) == []  # and no review ran


async def test_own_02_a_pending_orm_object_is_refused_and_left_to_the_caller(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    document = DocumentORM(id=uuid4(), project_id=s.project, tenant_id=s.tenant, document_type=DocumentType.CONTRACT,
                           filename="caller.pdf", file_format=".pdf", upload_status=DocumentStatus.PARSED,
                           created_by=s.author.user_id, file_hash="c" * 64, storage_url="k/caller")
    db.add(document)  # pending, not flushed: no transaction has begun yet
    with pytest.raises(C2ProException) as refused:
        await _review(db, s, change_set_id, ids)
    assert refused.value.code == NOT_OWNED
    assert document in db.new  # still pending, still the caller's
    db.expunge(document)
    assert await db.scalar(select(func.count()).select_from(DocumentORM).where(DocumentORM.id == document.id)) == 0
    assert await _runs(s.project) == []


async def test_own_03_a_caller_read_transaction_is_refused_not_ended(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    await db.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(s.tenant)})
    with pytest.raises(C2ProException) as refused:
        await _review(db, s, change_set_id, ids)
    assert refused.value.code == NOT_OWNED
    assert await db.scalar(text("SELECT current_setting('app.current_tenant', true)")) == str(s.tenant)  # not ended
    await db.rollback()


async def test_own_03b_a_session_bound_to_a_caller_connection_is_refused(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    document_id = await _document_id(db, s)
    await db.commit()
    marker = f"connection-work-{uuid4()}"
    engine = _engine()
    try:
        async with engine.connect() as conn:
            await conn.begin()  # the caller's own transaction on its own connection
            await conn.execute(text(
                "INSERT INTO document_chunks (id, tenant_id, document_id, project_id, content, embedding, metadata) "
                "VALUES (:id, :t, :d, :p, :c, CAST(:e AS vector), CAST('{}' AS jsonb))"),
                {"id": uuid4(), "t": s.tenant, "d": document_id, "p": s.project, "c": marker,
                 "e": "[" + ",".join(["0"] * 1536) + "]"})
            joined = AsyncSession(bind=conn, expire_on_commit=False)  # commit/rollback would join the caller's
            with pytest.raises(C2ProException) as refused:
                await _reviewer(joined, _model(ids)).review(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                            target=ReviewTargetKind.DRAFT, change_set_id=change_set_id)
            assert refused.value.code == NOT_OWNED
            assert conn.in_transaction()  # the caller's transaction is still the caller's
            assert await conn.scalar(text("SELECT count(*) FROM document_chunks WHERE content = :c"),
                                     {"c": marker}) == 1
            await joined.close()
            await conn.rollback()  # the caller decides
    finally:
        await engine.dispose()
    assert await _chunks(s.project, marker) == 0
    assert await _runs(s.project) == []


# =========================================================================== every path ends its own transaction
async def test_own_04_success_ends_its_transaction_and_the_caller_keeps_its_own_boundaries(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    result = await _review(db, s, change_set_id, ids)
    assert result.run.status == "COMPLETED" and not db.in_transaction()
    marker = f"after-{uuid4()}"
    await _chunk(db, s.tenant, s.project, await _document_id(db, s), marker, {"note": "later caller work"})
    await db.rollback()  # the caller's later transaction is independent of the review's
    assert await _chunks(s.project, marker) == 0
    assert await _runs(s.project) == ["COMPLETED"]  # the review's own work is durable


async def test_own_05_a_pipeline_failure_ends_its_transaction(db: AsyncSession,
                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    s, change_set_id, ids = await _world(db)

    async def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("pipeline failure")

    monkeypatch.setattr(reviewer_service, "run_review_pipeline", broken)
    result = await _review(db, s, change_set_id, ids)
    assert result.run.status == "FAILED" and not db.in_transaction()
    assert await _runs(s.project) == ["FAILED"]


async def test_own_06_a_recovered_finalization_failure_ends_its_transaction(
        db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    s, change_set_id, ids = await _world(db)

    async def failing(self: WBSIntelligenceService, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("finalization failure")

    monkeypatch.setattr(WBSIntelligenceService, "complete_run", failing)
    result = await _review(db, s, change_set_id, ids)
    assert result.run.status == "FAILED" and not db.in_transaction()


async def test_own_07_an_unrecoverable_finalization_failure_still_ends_its_transaction(
        db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    s, change_set_id, ids = await _world(db)

    async def failing(self: WBSIntelligenceService, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("finalization failure")

    monkeypatch.setattr(WBSIntelligenceService, "complete_run", failing)
    monkeypatch.setattr(WBSIntelligenceService, "fail_run", failing)
    with pytest.raises(RuntimeError):
        await _review(db, s, change_set_id, ids)
    assert not db.in_transaction()  # nothing half-written is left for the caller to commit
    assert await _runs(s.project) == ["RUNNING"]  # the lease fails it later (never silently COMPLETED)


async def test_own_08_cancellation_ends_its_transaction(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    result = await _review(db, s, change_set_id, ids, cancelled=lambda: True)
    assert result.run.status == "CANCELLED" and not db.in_transaction()


async def test_own_09_a_cancelled_task_ends_its_transaction(db: AsyncSession,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    s, change_set_id, ids = await _world(db)

    async def lost(self: FakeReviewerModelAdapter, request: ModelCallRequest) -> Any:
        raise asyncio.CancelledError

    monkeypatch.setattr(FakeReviewerModelAdapter, "complete", lost)
    with pytest.raises(asyncio.CancelledError):
        await _review(db, s, change_set_id, ids)
    assert not db.in_transaction()


async def test_own_09b_a_cancellation_inside_its_own_transaction_ends_it_and_its_lock(
        db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    s, change_set_id, ids = await _world(db)

    async def cancelled_while_reading(*args: Any, **kwargs: Any) -> Any:
        raise asyncio.CancelledError  # after the target was captured FOR SHARE, before the run opened

    monkeypatch.setattr(reviewer_service, "inventory_evidence", cancelled_while_reading)
    with pytest.raises(asyncio.CancelledError):
        await _review(db, s, change_set_id, ids)
    assert not db.in_transaction()
    await _no_lock_on(change_set_id)


async def test_own_10_a_reused_run_ends_its_transaction_and_holds_no_lock(
        db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    s, change_set_id, ids = await _world(db)

    async def lost(self: FakeReviewerModelAdapter, request: ModelCallRequest) -> Any:
        raise asyncio.CancelledError

    monkeypatch.setattr(FakeReviewerModelAdapter, "complete", lost)
    with pytest.raises(asyncio.CancelledError):
        await _review(db, s, change_set_id, ids)
    await db.rollback()
    monkeypatch.undo()
    reused = await _review(db, s, change_set_id, ids)
    assert reused.reused and not db.in_transaction()
    await _no_lock_on(change_set_id)


async def test_own_11_a_refused_target_ends_its_transaction_and_holds_no_lock(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    with pytest.raises(C2ProException) as refused:  # a plain DRAFT is not an IMPORT_REVIEW candidate
        await _review(db, s, change_set_id, ids, target=ReviewTargetKind.IMPORT_REVIEW)
    assert refused.value.code == "WBS_REVIEWER_NOT_IMPORT_REVIEW"
    assert not db.in_transaction()
    await _no_lock_on(change_set_id)


async def _no_lock_on(change_set_id: UUID) -> None:
    engine = _engine()
    try:
        async with async_sessionmaker(engine)() as other:
            await other.execute(select(WBSChangeSetORM.id).where(WBSChangeSetORM.id == change_set_id)
                                .with_for_update(nowait=True))  # raises if the review still holds FOR SHARE
            await other.rollback()
    finally:
        await engine.dispose()


# =========================================================================== the review binds its own tenant
async def test_own_12_the_first_transaction_binds_the_tenant(db: AsyncSession,
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    s, change_set_id, ids = await _world(db)
    seen: list[str | None] = []
    original = WBSIntelligenceService._require_project

    async def observing(self: WBSIntelligenceService, *args: Any, **kwargs: Any) -> Any:
        seen.append(await self.session.scalar(text("SELECT current_setting('app.current_tenant', true)")))
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(WBSIntelligenceService, "_require_project", observing)
    result = await _review(db, s, change_set_id, ids)
    assert result.run.status == "COMPLETED"
    assert seen == [str(s.tenant)]  # the RLS second wall is up before the first read
