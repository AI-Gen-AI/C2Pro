"""#758: a resume finalization and a new document generation must not deadlock.

The two transactions that meet at the concurrent approve/reupload boundary
touch the same four tables, and until this fix they walked them in opposite
directions::

    reupload / reprocess   documents -> document_processing_operations
                                     -> review_items
    finalization           resume_operations -> review_items -> documents

So the reupload held the document and waited on the review, while the
approval held the review and waited on the document: a genuine PostgreSQL
lock cycle, on exactly the boundary #758 exists to make safe.

Finalization now takes the document row FIRST, which puts it on the single
canonical order every other transaction already follows (see the lock-order
section of ``resume_ownership``'s module docstring).

These tests prove it against REAL PostgreSQL over two genuinely separate
connections -- a shared session would let every assertion pass while proving
nothing about lock arbitration. The pause point is production's own
``fault("document")`` hook, which fires immediately before the document
write, i.e. exactly inside the historical inversion window.

Both arrival orders are covered, and both must terminate. What is asserted is
not just "no deadlock" but WHICH row the second transaction blocks on, read
out of ``pg_stat_activity`` -- the lock order becomes an observed fact rather
than something inferred from the code. Every session carries a bounded
``lock_timeout`` so a regression fails instead of hanging.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.analysis.adapters.persistence.models import Analysis
from src.analysis.domain.enums import AnalysisStatus, AnalysisType
from src.core import processing_authority as pa
from src.core import resume_lineage
from src.core.auth.models import User
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.domain.models import DocumentStatus
from src.modules.hitl.adapters.persistence import resume_ownership
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.adapters.persistence.resume_ownership import OwnershipError, Phase
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.projects.adapters.persistence.models import ProjectORM

pytestmark = pytest.mark.asyncio

#: A hang GUARD, not the mechanism. A genuine lock cycle is detected by
#: PostgreSQL's own `deadlock_timeout` (1s by default) and surfaces as
#: DeadlockDetected long before this elapses, so a regression fails fast and
#: loudly. This only stops a test from wedging a connection if the handshake
#: below ever goes wrong, and it has to stay well ABOVE the handshake's own
#: deadlines or a legitimately queued transaction would be cut off and the
#: test would prove nothing.
LOCK_TIMEOUT = "30s"

#: How long to wait for the second transaction to show up as blocked. Bounded
#: far below LOCK_TIMEOUT so the queued transaction is still waiting when the
#: assertion reads it.
BLOCK_OBSERVE_TIMEOUT = 8.0


def _dsn(db: AsyncSession) -> str:
    url = db.get_bind().url
    if url.get_driver_name() != "asyncpg":
        url = url.set(drivername="postgresql+asyncpg")
    return url.render_as_string(hide_password=False)


@pytest.fixture
async def sessions(db: AsyncSession):
    """A session factory on its OWN engine, with a bounded lock timeout.

    Separate connections are the whole point: lock conflicts have to be
    arbitrated by PostgreSQL between real concurrent transactions.
    """
    engine = create_async_engine(_dsn(db), pool_size=10, max_overflow=10)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def factory(tenant_id: UUID | None):
        async with maker() as session:
            await session.execute(text(f"SET lock_timeout = '{LOCK_TIMEOUT}'"))
            if tenant_id is not None:
                await session.execute(
                    text("SELECT set_config('app.current_tenant', :t, true)"),
                    {"t": str(tenant_id)},
                )
            yield session
            await session.commit()

    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_recovery_discovery_rows(db: AsyncSession, test_user: User):
    """The #711 discovery index is migration-owned and survives the schema reset."""
    tenant_id = test_user.tenant_id
    yield
    await db.rollback()
    await db.execute(
        text("DELETE FROM system_recovery.document_work_index WHERE tenant_id = :t"),
        {"t": tenant_id},
    )
    await db.commit()


@dataclass(frozen=True)
class _Seeded:
    document_id: UUID
    project_id: UUID
    review_row_id: UUID
    thread_id: str
    checkpoint_id: str
    generation: int
    authority: pa.ProcessingAuthority


async def _seed(db: AsyncSession, tenant_id: UUID) -> _Seeded:
    """A document paused at the HITL gate, with a fenced pending review.

    No graph is needed here: these tests are about lock arbitration between
    two transactions, so the review is seeded in the shape the #711/#758
    paths produce -- an authority-scoped thread stamped with the grant that
    bound it.
    """
    project_id, document_id = uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant_id,
            name="758 lock order",
            code=f"P-{uuid4().hex[:8]}",
            start_date=datetime.now(),
        )
    )
    await db.commit()
    db.add(
        DocumentORM(
            id=document_id,
            tenant_id=tenant_id,
            project_id=project_id,
            document_type="contract",
            filename="lock_order.pdf",
            upload_status="parsed_pending_analysis",
        )
    )
    await db.commit()

    granted = await pa.acquire(
        db,
        tenant_id=tenant_id,
        document_id=document_id,
        stage=pa.ProcessingStage.ANALYSIS,
    )
    await db.commit()
    assert granted.authority is not None, granted.outcome
    authority = granted.authority
    thread_id = (
        f"document:{document_id}:g{authority.generation}:f{authority.fencing_token}:analysis"
    )

    review = ReviewItemORM(
        id=uuid4(),
        item_id=document_id,
        item_type="contract",
        current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        confidence=0.8,
        impact_level=ImpactLevel.HIGH,
        tenant_id=tenant_id,
        sla_due_date=datetime.now(),
        item_data={},
        review_metadata={"tenant_id": str(tenant_id), "document_id": str(document_id)},
        project_id=project_id,
        document_id=document_id,
        review_type="analysis_critique",
        thread_id=thread_id,
        checkpoint_id="cp-interrupt-1",
        lineage_generation=authority.generation,
        lineage_fencing_token=authority.fencing_token,
    )
    db.add(review)
    await db.commit()

    return _Seeded(
        document_id=document_id,
        project_id=project_id,
        review_row_id=review.id,
        thread_id=thread_id,
        checkpoint_id="cp-interrupt-1",
        generation=authority.generation,
        authority=authority,
    )


async def _own(seeded: _Seeded, tenant_id: UUID, sessions: Any, decision: str) -> Any:
    ownership, _phase, refusal = await resume_ownership.acquire(
        review_row_id=seeded.review_row_id,
        tenant_id=tenant_id,
        project_id=seeded.project_id,
        document_id=seeded.document_id,
        thread_id=seeded.thread_id,
        source_checkpoint_id=seeded.checkpoint_id,
        decision=decision,
        feedback="",
        reviewer="Reviewer",
        session_factory=sessions,
    )
    assert ownership is not None, refusal
    return ownership


async def _make_approvable(
    seeded: _Seeded, tenant_id: UUID, ownership: Any, sessions: Any
) -> None:
    """Advance the operation to the only phase an approval may finalize from.

    Driven through the durable columns rather than a graph run: these tests
    are about lock order, and `finalize_v3`'s approve preconditions
    (GRAPH_COMPLETED + an operation-keyed analysis) are what make it reach
    the document write at all.
    """
    async with sessions(tenant_id) as session:
        analysis_id = uuid4()
        # Through the ORM, so the row satisfies every column the application
        # itself requires rather than a hand-maintained INSERT.
        session.add(
            Analysis(
                id=analysis_id,
                tenant_id=tenant_id,
                project_id=seeded.project_id,
                analysis_type=AnalysisType.COHERENCE,
                status=AnalysisStatus.COMPLETED,
                resume_operation_id=ownership.operation_id,
                resume_attempt_id=ownership.attempt_id,
            )
        )
        await session.flush()
        await session.execute(
            text(
                "UPDATE resume_operations SET phase = 'GRAPH_COMPLETED', "
                "       analysis_id = cast(:a as uuid), "
                "       terminal_checkpoint_id = 'cp-terminal' "
                " WHERE id = cast(:o as uuid)"
            ),
            {"a": str(analysis_id), "o": str(ownership.operation_id)},
        )


# ── the generation transition, in production's statement order ─────────────


async def _begin_new_generation(
    sessions: Any, tenant_id: UUID, document_id: UUID, *, reprocess: bool
) -> int:
    """Drive the generation transition exactly as production sequences it.

    Both entry points mutate the DOCUMENT and then call
    ``begin_processing_generation`` in the same transaction: the reprocess
    route via ``update_status``, the reupload use case via ``update_version``.
    Those two repository calls, in that order, are the lock sequence under
    test -- document first, authority row second, reviews last.
    """
    async with sessions(tenant_id) as session:
        repo = SqlAlchemyDocumentRepository(session=session)
        if reprocess:
            await repo.update_status(tenant_id, document_id, DocumentStatus.UPLOADED)
        else:
            await repo.update_version(
                tenant_id=tenant_id,
                document_id=document_id,
                version=2,
                file_hash=uuid4().hex,
                filename="lock_order_v2.pdf",
                status=DocumentStatus.UPLOADED,
            )
        generation = await repo.begin_processing_generation(tenant_id, document_id)
    assert generation is not None
    return generation


# ── observing WHICH row a transaction is blocked on ────────────────────────


async def _blocked_statement(
    db: AsyncSession, *, timeout: float = BLOCK_OBSERVE_TIMEOUT
) -> str:
    """The SQL of the backend currently waiting on a row lock.

    This is what turns the lock ORDER into an observed fact. A transaction
    blocked on the document row is sitting in `UPDATE documents`; one blocked
    on the review row is sitting in the `review_items` stamp. Reading the
    statement therefore says exactly where in its sequence the transaction
    got as far as -- which is the difference between the fixed order and the
    inverted one.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        await db.rollback()
        rows = (
            await db.execute(
                text(
                    "SELECT query FROM pg_stat_activity "
                    " WHERE wait_event_type = 'Lock' AND state = 'active' "
                    "   AND pid <> pg_backend_pid()"
                )
            )
        ).all()
        if rows:
            return " | ".join(str(r.query) for r in rows)
        await asyncio.sleep(0.2)
    raise AssertionError("no transaction ever blocked on a row lock")


async def _review(db: AsyncSession, review_row_id: UUID) -> Any:
    await db.rollback()
    return (
        await db.execute(
            select(ReviewItemORM)
            .where(ReviewItemORM.id == review_row_id)
            .execution_options(populate_existing=True)
        )
    ).scalars().one()


async def _document(db: AsyncSession, document_id: UUID) -> Any:
    await db.rollback()
    return (
        await db.execute(
            select(DocumentORM)
            .where(DocumentORM.id == document_id)
            .execution_options(populate_existing=True)
        )
    ).scalars().one()


async def _operation(db: AsyncSession, review_row_id: UUID) -> Any:
    await db.rollback()
    return (
        await db.execute(
            text("SELECT * FROM resume_operations WHERE review_row_id = :r"),
            {"r": review_row_id},
        )
    ).first()


# ── finalization first, generation second ──────────────────────────────────


@pytest.mark.parametrize("legacy_review", [True, False], ids=["legacy", "fenced"])
@pytest.mark.parametrize("reprocess", [False, True], ids=["reupload", "reprocess"])
async def test_finalization_then_generation_serializes_without_deadlock(
    db: AsyncSession, test_user: User, sessions: Any, reprocess: bool, legacy_review: bool
) -> None:
    """The historical cycle, driven deterministically from the approval side.

    The pause is production's own `fault("document")`, which fires with the
    operation and the review already locked and the document write still
    ahead. Before the fix that is the inversion window: the generation
    transition would take the document, then block on the review, while the
    approval woke up and blocked on the document.

    With the document taken first, the generation transition cannot get past
    its FIRST statement, so it holds nothing and no cycle can form. That is
    asserted by reading the statement it is stuck on.

    The LEGACY review shape is what completes the cycle and so is covered
    explicitly: the generation transition only takes a review row lock when
    ``stamp_superseded_reviews`` actually matches something, which it does
    only for a row that records no lineage yet. With a fenced review the two
    transactions contend on the document alone -- still an inversion to fix,
    but not one that deadlocks, and testing only that shape would have let
    the real cycle through.
    """
    tenant_id = UUID(str(test_user.tenant_id))
    seeded = await _seed(db, tenant_id)
    if legacy_review:
        await db.execute(
            text(
                "UPDATE review_items SET lineage_generation = NULL, "
                "lineage_fencing_token = NULL WHERE id = :r"
            ),
            {"r": seeded.review_row_id},
        )
        await db.commit()
    ownership = await _own(seeded, tenant_id, sessions, "reject")

    at_document, release = asyncio.Event(), asyncio.Event()

    async def _pause(marker: str) -> None:
        if marker == "document":
            at_document.set()
            await release.wait()

    finalize = asyncio.create_task(
        resume_ownership.finalize_v3(
            ownership=ownership,
            review_row_id=seeded.review_row_id,
            approved=False,
            approved_by="Reviewer",
            feedback="needs changes",
            document_id=seeded.document_id,
            session_factory=sessions,
            fault=_pause,
        )
    )
    await asyncio.wait_for(at_document.wait(), 20)

    generation = asyncio.create_task(
        _begin_new_generation(
            sessions, tenant_id, seeded.document_id, reprocess=reprocess
        )
    )

    try:
        # The generation transition must be stuck on the DOCUMENT -- its first
        # statement -- not on the review after having taken the document.
        blocked = await _blocked_statement(db)
        assert "documents" in blocked.lower(), (
            "the generation transition got past the document row and blocked "
            f"later, which is the inverted order that deadlocks: {blocked}"
        )
        assert "review_items" not in blocked.lower(), (
            f"blocked on the review while holding the document -- inverted: {blocked}"
        )
        assert not generation.done()
    finally:
        # Always release, even on a failed assertion: a paused transaction
        # left holding row locks would wedge the per-test schema reset and
        # turn a clear failure into a hang.
        release.set()

    await asyncio.wait_for(finalize, 30)
    new_generation = await asyncio.wait_for(generation, 30)

    # Both committed, in order, with truthful state.
    assert new_generation == seeded.generation + 1
    review = await _review(db, seeded.review_row_id)
    assert review.current_status is ReviewStatus.REJECTED, "the decision landed first"
    assert review.lineage_generation == (None if legacy_review else seeded.generation), (
        "a DECIDED review must not be stamped or re-stamped by the transition"
    )
    document = await _document(db, seeded.document_id)
    assert str(document.upload_status) == DocumentStatus.UPLOADED.value, (
        "the generation transition's document status must be the final one"
    )
    operation = await _operation(db, seeded.review_row_id)
    assert operation.phase == Phase.FINALIZED_REJECTED.value


# ── generation first, finalization second ──────────────────────────────────


@pytest.mark.parametrize("reprocess", [False, True], ids=["reupload", "reprocess"])
async def test_generation_then_approval_fails_closed_without_deadlock(
    db: AsyncSession, test_user: User, sessions: Any, reprocess: bool
) -> None:
    """Reverse arrival: the new generation wins the document, the approval loses.

    The approval blocks on the document row rather than deadlocking, and once
    the generation commits it does NOT get to finalize: the lineage CAS in
    `verify_in_transaction` sees that the attempt which bound this review no
    longer owns the document. Fail closed -- no approved review, no ANALYZED
    document, no rewritten durable phase.

    This is the semantic half of the fix: serializing the two transactions
    must not turn a superseded approval into a successful one.
    """
    tenant_id = UUID(str(test_user.tenant_id))
    seeded = await _seed(db, tenant_id)
    ownership = await _own(seeded, tenant_id, sessions, "approve")
    await _make_approvable(seeded, tenant_id, ownership, sessions)

    # Hold the generation transition open with the document locked.
    held = asyncio.Event()
    committed = asyncio.Event()

    async def _generation_holding_the_document() -> int:
        async with sessions(tenant_id) as session:
            repo = SqlAlchemyDocumentRepository(session=session)
            if reprocess:
                await repo.update_status(
                    tenant_id, seeded.document_id, DocumentStatus.UPLOADED
                )
            else:
                await repo.update_version(
                    tenant_id=tenant_id,
                    document_id=seeded.document_id,
                    version=2,
                    file_hash=uuid4().hex,
                    filename="lock_order_v2.pdf",
                    status=DocumentStatus.UPLOADED,
                )
            generation = await repo.begin_processing_generation(
                tenant_id, seeded.document_id
            )
            held.set()
            await committed.wait()
        return int(generation or 0)

    generation = asyncio.create_task(_generation_holding_the_document())
    await asyncio.wait_for(held.wait(), 20)

    approval = asyncio.create_task(
        resume_ownership.finalize_v3(
            ownership=ownership,
            review_row_id=seeded.review_row_id,
            approved=True,
            approved_by="Reviewer",
            feedback="",
            document_id=seeded.document_id,
            session_factory=sessions,
        )
    )
    try:
        blocked = await _blocked_statement(db)
        assert "documents" in blocked.lower(), (
            f"the approval must queue behind the document row, not elsewhere: {blocked}"
        )
        assert not approval.done(), "the approval must still be queued, not resolved"
    finally:
        committed.set()

    new_generation = await asyncio.wait_for(generation, 30)
    assert new_generation == seeded.generation + 1

    with pytest.raises(OwnershipError, match="Lineage superseded"):
        await asyncio.wait_for(approval, 30)

    review = await _review(db, seeded.review_row_id)
    assert review.current_status is ReviewStatus.PENDING_REVIEW_REQUIRED, (
        "a superseded approval finalized the current review"
    )
    document = await _document(db, seeded.document_id)
    assert str(document.upload_status) != "analyzed", (
        "a superseded approval marked the current document ANALYZED"
    )
    operation = await _operation(db, seeded.review_row_id)
    assert operation.phase == Phase.GRAPH_COMPLETED.value, (
        "durable evidence must survive a refused finalization"
    )
    lineage = await resume_lineage.read_review_lineage(
        db, review_row_id=seeded.review_row_id, tenant_id=tenant_id
    )
    assert lineage is not None and not lineage.is_current_for_document


# ── the canonical order, measured rather than reasoned about ───────────────


async def _locked_rows(sessions: Any, tenant_id: UUID, seeded: _Seeded) -> dict[str, str]:
    """Which of the three rows are row-locked by somebody else right now.

    Row locks live in the tuple header, not in ``pg_locks``, so the only
    reliable probe is to ask for each row with ``FOR UPDATE NOWAIT`` from a
    separate connection and see which ones refuse.
    """
    probes = (
        (
            "documents",
            "SELECT id FROM documents WHERE id = cast(:i as uuid) FOR UPDATE NOWAIT",
            str(seeded.document_id),
        ),
        (
            "review_items",
            "SELECT id FROM review_items WHERE id = cast(:i as uuid) FOR UPDATE NOWAIT",
            str(seeded.review_row_id),
        ),
        (
            "document_processing_operations",
            "SELECT document_id FROM document_processing_operations "
            " WHERE document_id = cast(:i as uuid) FOR UPDATE NOWAIT",
            str(seeded.document_id),
        ),
    )
    held: dict[str, str] = {}
    async with sessions(tenant_id) as probe:
        for name, sql, row_id in probes:
            try:
                await probe.execute(text(sql), {"i": row_id})
                held[name] = "free"
            except Exception:  # noqa: BLE001 - NOWAIT refusal is the signal
                held[name] = "locked"
                await probe.rollback()
                await probe.execute(
                    text("SELECT set_config('app.current_tenant', :t, true)"),
                    {"t": str(tenant_id)},
                )
    return held


@pytest.mark.parametrize("legacy_review", [True, False], ids=["legacy", "fenced"])
@pytest.mark.parametrize("reprocess", [False, True], ids=["reupload", "reprocess"])
async def test_generation_transition_holds_the_document_before_the_authority_row(
    db: AsyncSession, test_user: User, sessions: Any, reprocess: bool, legacy_review: bool
) -> None:
    """The canonical order, asserted as an observed fact.

    This is the invariant the deadlock hinges on, and it cannot be read off
    the code: the reprocess route changes the document status through the ORM,
    which only STAGES the ``UPDATE documents``. Measured, the reprocess
    transition used to hold the authority row and the review while the
    document row was still free -- the exact inversion that deadlocks against
    a HITL finalization once finalization is on the canonical order.

    Both entry points and both review shapes are covered, because the review
    lock only appears for a legacy row (the stamp matches nothing once a
    review already records its lineage) and that difference hid the reprocess
    case entirely.
    """
    tenant_id = UUID(str(test_user.tenant_id))
    seeded = await _seed(db, tenant_id)
    if legacy_review:
        await db.execute(
            text(
                "UPDATE review_items SET lineage_generation = NULL, "
                "lineage_fencing_token = NULL WHERE id = :r"
            ),
            {"r": seeded.review_row_id},
        )
        await db.commit()

    async with sessions(tenant_id) as session:
        repo = SqlAlchemyDocumentRepository(session=session)
        if reprocess:
            await repo.update_status(
                tenant_id, seeded.document_id, DocumentStatus.UPLOADED
            )
        else:
            await repo.update_version(
                tenant_id=tenant_id,
                document_id=seeded.document_id,
                version=2,
                file_hash=uuid4().hex,
                filename="lock_order_v2.pdf",
                status=DocumentStatus.UPLOADED,
            )
        await repo.begin_processing_generation(tenant_id, seeded.document_id)

        held = await _locked_rows(sessions, tenant_id, seeded)
        assert held["documents"] == "locked", (
            "the generation transition holds the authority row while the DOCUMENT "
            f"row is still free -- the inverted order: {held}"
        )
        assert held["document_processing_operations"] == "locked", held
        if legacy_review:
            assert held["review_items"] == "locked", (
                "a legacy review must be stamped inside this transaction"
            )
        await session.rollback()


async def test_the_authority_fence_holds_the_document_before_the_authority_row(
    db: AsyncSession, test_user: User, sessions: Any
) -> None:
    """The analysis worker's terminal write follows the same order.

    ``settle`` fences through ``verify_in_transaction``, in the same
    transaction as the document status write -- which the repository also only
    STAGES. So that transaction used to take the authority row first and the
    document row at commit, inverting against a reupload. Same root cause,
    same fix, and worth pinning separately because it is reached from the
    analysis worker rather than from an HTTP request.
    """
    tenant_id = UUID(str(test_user.tenant_id))
    seeded = await _seed(db, tenant_id)

    # The grant `_seed` already took is still the live one -- its lease has
    # not expired -- so this is the same authority the analysis worker would
    # be holding when it reaches its terminal write.
    async with sessions(tenant_id) as session:
        repo = SqlAlchemyDocumentRepository(session=session)
        await repo.update_status(
            tenant_id, seeded.document_id, DocumentStatus.PARSED_PENDING_ANALYSIS
        )
        await pa.settle(
            session,
            seeded.authority,
            phase=pa.ProcessingPhase.PENDING,
            outcome="waiting_for_review",
        )

        held = await _locked_rows(sessions, tenant_id, seeded)
        assert held["documents"] == "locked", (
            f"the fenced terminal write left the document row free: {held}"
        )
        assert held["document_processing_operations"] == "locked", held
        await session.rollback()
