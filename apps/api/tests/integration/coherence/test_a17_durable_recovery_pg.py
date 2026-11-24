"""A17: durable approval despite killed HTTP process; disposable PostgreSQL only."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from runpy import run_path
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.application import project_evaluation as subject
from src.coherence.domain.score_reasons import WITHHELD_EVALUATION_EVENT
from src.core.tasks.coherence_reconciler import reconcile_pending_postapproval
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.models import ProjectEventORM


@pytest_asyncio.fixture
async def a17_pg_trigger(db: AsyncSession):
    """Test metadata.create_all does not run Alembic DDL; install real PG trigger."""
    migration = run_path(
        str(
            Path(__file__).parents[3] / "alembic/versions/20261123_0001_a17_durable_postapproval.py"
        )
    )
    await db.execute(text(migration["FUNCTION_SQL"]))
    await db.execute(text(migration["CREATE_TRIGGER_SQL"]))
    await db.commit()


def _sessions(engine):
    @asynccontextmanager
    async def scoped(tenant):
        async with AsyncSession(engine, expire_on_commit=False) as s:
            await s.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(tenant)}
            )
            try:
                yield s
                await s.commit()
            except BaseException:
                await s.rollback()
                raise

    @asynccontextmanager
    async def scan():
        async with AsyncSession(engine, expire_on_commit=False) as s:
            yield s

    return scoped, scan


async def _approval_fixture(db, tenant):
    project, review = uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project,
            tenant_id=tenant,
            name="Synthetic A17 durable",
            code=f"A17-DUR-{uuid4().hex[:8]}",
        )
    )
    # No ORM relationship dependency edge; persist FK parent before child.
    await db.flush()
    db.add(
        ReviewItemORM(
            id=review,
            item_id=uuid4(),
            tenant_id=tenant,
            project_id=project,
            item_type="analysis_critique",
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
            confidence=0.8,
            impact_level=ImpactLevel.HIGH,
            sla_due_date=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
            review_metadata={"project_id": str(project)},
            item_data={},
        )
    )
    await db.commit()
    scoped, scan = _sessions(db.bind)
    # This COMMIT is the last operation of the HTTP process in the simulation:
    # no BackgroundTasks or Celery task is ever invoked from the approval.
    async with scoped(tenant) as s:
        await s.execute(
            update(ReviewItemORM)
            .where(ReviewItemORM.id == review, ReviewItemORM.tenant_id == tenant)
            .values(
                current_status=ReviewStatus.APPROVED,
                approved_at=datetime.now(UTC).replace(tzinfo=None),
                approved_by="Synthetic reviewer",
            )
        )
    async with scoped(tenant) as s:
        trigger = await s.scalar(
            text(
                "SELECT count(*) FROM pg_trigger WHERE tgrelid='review_items'::regclass "
                "AND tgname='tr_a17_stamp_postapproval_obligation' AND NOT tgisinternal"
            )
        )
        assert trigger == 1, f"A17 PG trigger not installed: {trigger}"
        valid_project = await s.scalar(
            text("SELECT id FROM projects WHERE id=:project AND tenant_id=:tenant"),
            {"project": project, "tenant": tenant},
        )
        assert valid_project == project, "A17 tenant-scoped project not visible"
        metadata = await s.scalar(
            select(ReviewItemORM.review_metadata).where(ReviewItemORM.id == review)
        )
        assert metadata["a17_score_obligation"]["state"] == "pending"
        assert metadata["a17_score_obligation"]["review_id"] == str(review)
    return project, review, scoped, scan


@pytest.mark.asyncio
async def test_committed_approval_then_crash_recovers_one_score(
    db: AsyncSession,
    test_tenant,
    a17_pg_trigger,
    monkeypatch: pytest.MonkeyPatch,
):
    tenant = test_tenant.id
    project, review, scoped, scan = await _approval_fixture(db, tenant)
    monkeypatch.setattr(subject, "get_session_with_tenant", scoped)
    called = []

    async def fake_score(payload, session, user, *, review_id):
        assert user.tenant_id == tenant and user.id is None
        called.append(review_id)
        session.add(
            CoherenceResultORM(
                project_id=project,
                tenant_id=tenant,
                global_score=72,
                category_scores={"SCOPE": 72},
                category_details=[],
                alerts=[],
                score_version="coherence-v1",
                scoring_snapshot={"a17_approval_id": str(review_id)},
            )
        )

    monkeypatch.setattr(subject, "_run_evaluation", fake_score)
    # New process/sessions, no original HTTP callback: Beat reconstructs job.
    result = await reconcile_pending_postapproval(
        scan_factory=scan,
        tenant_factory=scoped,
        evaluator=subject.run_project_evaluation_after_approval,
    )
    assert result == {"scanned": 1, "completed": 1, "retry": 0, "operator_required": 0}
    assert called == [review]
    assert (
        await reconcile_pending_postapproval(
            scan_factory=scan,
            tenant_factory=scoped,
            evaluator=subject.run_project_evaluation_after_approval,
        )
    )["scanned"] == 0
    # The delayed pre-crash task may still race after restart.
    await subject.run_project_evaluation_after_approval(
        tenant_id=tenant,
        project_id=project,
        review_id=review,
        actor_user_id=uuid4(),
    )
    async with scoped(tenant) as s:
        rows = list(
            (
                await s.scalars(
                    select(CoherenceResultORM).where(
                        CoherenceResultORM.tenant_id == tenant,
                        CoherenceResultORM.project_id == project,
                    )
                )
            ).all()
        )
        decision = await s.scalar(select(ReviewItemORM).where(ReviewItemORM.id == review))
    assert len(rows) == 1 and rows[0].global_score == 72
    assert decision.current_status == ReviewStatus.APPROVED
    assert decision.review_metadata["a17_score_obligation"]["state"] == "done"
    assert called == [review]


@pytest.mark.asyncio
async def test_crash_recovery_no_document_clauses_has_no_score(
    db: AsyncSession,
    test_tenant,
    a17_pg_trigger,
    monkeypatch: pytest.MonkeyPatch,
):
    tenant = test_tenant.id
    project, review, scoped, scan = await _approval_fixture(db, tenant)
    monkeypatch.setattr(subject, "get_session_with_tenant", scoped)

    async def missing_clauses(*args, **kwargs):
        raise HTTPException(404, subject.NO_DOCUMENT_CLAUSES_DETAIL)

    monkeypatch.setattr(subject, "_run_evaluation", missing_clauses)
    result = await reconcile_pending_postapproval(
        scan_factory=scan,
        tenant_factory=scoped,
        evaluator=subject.run_project_evaluation_after_approval,
    )
    assert result["completed"] == 1
    async with scoped(tenant) as s:
        events = list(
            (
                await s.scalars(
                    select(ProjectEventORM).where(
                        ProjectEventORM.tenant_id == tenant,
                        ProjectEventORM.project_id == project,
                        ProjectEventORM.event_type == WITHHELD_EVALUATION_EVENT,
                        ProjectEventORM.payload["a17_approval_id"].astext == str(review),
                    )
                )
            ).all()
        )
        score = await s.scalar(
            select(CoherenceResultORM.id).where(
                CoherenceResultORM.tenant_id == tenant, CoherenceResultORM.project_id == project
            )
        )
        review_row = await s.scalar(select(ReviewItemORM).where(ReviewItemORM.id == review))
    assert len(events) == 1 and events[0].payload["score_reason"] == "no_document_clauses"
    assert score is None
    assert review_row.review_metadata["a17_score_obligation"]["state"] == "done"
    other = uuid4()
    async with scoped(other) as alien:
        assert (
            await alien.scalar(
                select(ReviewItemORM.id).where(
                    ReviewItemORM.id == review, ReviewItemORM.tenant_id == other
                )
            )
            is None
        )


@pytest.mark.asyncio
async def test_failed_recovery_rolls_back_partial_score_then_retries_once(
    db: AsyncSession,
    test_tenant,
    a17_pg_trigger,
    monkeypatch: pytest.MonkeyPatch,
):
    tenant = test_tenant.id
    project, review, scoped, scan = await _approval_fixture(db, tenant)
    monkeypatch.setattr(subject, "get_session_with_tenant", scoped)
    attempts = []

    async def fail_then_score(payload, session, user, *, review_id):
        attempts.append(review_id)
        session.add(
            CoherenceResultORM(
                project_id=project,
                tenant_id=tenant,
                global_score=99 if len(attempts) == 1 else 63,
                category_scores={"SCOPE": 63},
                category_details=[],
                alerts=[],
                score_version="coherence-v1",
                scoring_snapshot={"a17_approval_id": str(review_id)},
            )
        )
        if len(attempts) == 1:
            raise RuntimeError("simulated process death after uncommitted Score")

    monkeypatch.setattr(subject, "_run_evaluation", fail_then_score)
    outcome = await reconcile_pending_postapproval(
        scan_factory=scan,
        tenant_factory=scoped,
        evaluator=subject.run_project_evaluation_after_approval,
    )
    assert outcome["retry"] == 1
    async with scoped(tenant) as s:
        row = await s.scalar(select(ReviewItemORM).where(ReviewItemORM.id == review))
        assert row.current_status == ReviewStatus.APPROVED
        assert row.review_metadata["a17_score_obligation"]["state"] == "pending"
        assert row.review_metadata["a17_score_obligation"]["attempts"] == 1
        assert (
            await s.scalar(
                select(CoherenceResultORM.id).where(
                    CoherenceResultORM.project_id == project,
                    CoherenceResultORM.tenant_id == tenant,
                )
            )
            is None
        )
        # Advance only the synthetic retry deadline, without sleeping.
        await s.execute(
            text("""
          UPDATE review_items
             SET review_metadata = jsonb_set(
                 review_metadata, '{a17_score_obligation,retry_after}',
                 to_jsonb((clock_timestamp()-interval '1 second')::text), true)
           WHERE id = :review AND tenant_id = :tenant
        """),
            {"review": review, "tenant": tenant},
        )

    outcome = await reconcile_pending_postapproval(
        scan_factory=scan,
        tenant_factory=scoped,
        evaluator=subject.run_project_evaluation_after_approval,
    )
    assert outcome["completed"] == 1
    assert attempts == [review, review]
    async with scoped(tenant) as s:
        scores = list(
            (
                await s.scalars(
                    select(CoherenceResultORM).where(
                        CoherenceResultORM.project_id == project,
                        CoherenceResultORM.tenant_id == tenant,
                    )
                )
            ).all()
        )
        review_row = await s.scalar(select(ReviewItemORM).where(ReviewItemORM.id == review))
    assert len(scores) == 1 and scores[0].global_score == 63
    assert review_row.review_metadata["a17_score_obligation"]["state"] == "done"


@pytest.mark.asyncio
async def test_approval_rollback_does_not_leave_pending_obligation(
    db: AsyncSession,
    test_tenant,
    a17_pg_trigger,
):
    tenant = test_tenant.id
    project = uuid4()
    review = uuid4()
    db.add(
        ProjectORM(
            id=project,
            tenant_id=tenant,
            name="A17 rollback negative",
            code=f"A17-ROLL-{uuid4().hex[:8]}",
        )
    )
    await db.flush()
    db.add(
        ReviewItemORM(
            id=review,
            item_id=uuid4(),
            tenant_id=tenant,
            project_id=project,
            item_type="analysis_critique",
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
            confidence=0.8,
            impact_level=ImpactLevel.HIGH,
            sla_due_date=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
            review_metadata={"project_id": str(project)},
            item_data={},
        )
    )
    await db.commit()
    scoped, scan = _sessions(db.bind)
    async with AsyncSession(db.bind, expire_on_commit=False) as aborted:
        await aborted.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(tenant)},
        )
        await aborted.execute(
            update(ReviewItemORM)
            .where(
                ReviewItemORM.id == review,
                ReviewItemORM.tenant_id == tenant,
            )
            .values(
                current_status=ReviewStatus.APPROVED,
                approved_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        inside = await aborted.scalar(
            select(ReviewItemORM.review_metadata).where(ReviewItemORM.id == review)
        )
        assert inside["a17_score_obligation"]["state"] == "pending"
        await aborted.rollback()
    async with scoped(tenant) as verified:
        persisted = await verified.scalar(select(ReviewItemORM).where(ReviewItemORM.id == review))
    assert persisted.current_status == ReviewStatus.PENDING_REVIEW_REQUIRED
    assert "a17_score_obligation" not in persisted.review_metadata
    outcome = await reconcile_pending_postapproval(scan_factory=scan, tenant_factory=scoped)
    assert outcome["scanned"] == 0


@pytest.mark.asyncio
async def test_tenant_scoped_postcommit_recovery_avoids_unscoped_discovery(
    db: AsyncSession,
    test_tenant,
    a17_pg_trigger,
    monkeypatch: pytest.MonkeyPatch,
):
    """A tenant-scoped PG session recovers approval without global enumeration."""
    tenant = test_tenant.id
    project, review, scoped, _ = await _approval_fixture(db, tenant)
    monkeypatch.setattr(subject, "get_session_with_tenant", scoped)

    @asynccontextmanager
    async def unscoped_forbidden():
        raise AssertionError("unscoped tenant discovery must not run")
        yield

    async def no_clauses(*args, **kwargs):
        raise HTTPException(404, subject.NO_DOCUMENT_CLAUSES_DETAIL)

    monkeypatch.setattr(subject, "_run_evaluation", no_clauses)
    recovered = await reconcile_pending_postapproval(
        tenant_id=tenant,
        scan_factory=unscoped_forbidden,
        tenant_factory=scoped,
        evaluator=subject.run_project_evaluation_after_approval,
    )
    assert recovered == {"scanned": 1, "completed": 1, "retry": 0, "operator_required": 0}
    async with scoped(tenant) as session:
        review_row = await session.scalar(
            select(ReviewItemORM).where(
                ReviewItemORM.id == review, ReviewItemORM.tenant_id == tenant
            )
        )
        score = await session.scalar(
            select(CoherenceResultORM.id).where(
                CoherenceResultORM.project_id == project,
                CoherenceResultORM.tenant_id == tenant,
            )
        )
        events = (
            await session.scalars(
                select(ProjectEventORM).where(
                    ProjectEventORM.tenant_id == tenant,
                    ProjectEventORM.project_id == project,
                    ProjectEventORM.event_type == WITHHELD_EVALUATION_EVENT,
                    ProjectEventORM.payload["a17_approval_id"].astext == str(review),
                )
            )
        ).all()
    assert review_row.current_status == ReviewStatus.APPROVED
    assert review_row.review_metadata["a17_score_obligation"]["state"] == "done"
    assert score is None
    assert len(events) == 1
    assert events[0].payload["score_reason"] == "no_document_clauses"
