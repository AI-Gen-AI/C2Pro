"""A17 transaction/idempotence smoke against disposable PostgreSQL; synthetic rows only."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.application import project_evaluation as subject
from src.coherence.domain.score_reasons import WITHHELD_EVALUATION_EVENT
from src.coherence.router import get_coherence_dashboard
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.models import ProjectEventORM


@pytest.mark.asyncio
async def test_a17_same_approval_commits_one_coherence_result_across_workers(
    db: AsyncSession,
    test_tenant,
    monkeypatch: pytest.MonkeyPatch,
):
    tenant, project_id, actor, review_id = test_tenant.id, uuid4(), uuid4(), uuid4()
    project = ProjectORM(
        id=project_id,
        tenant_id=tenant,
        name="Synthetic A17 idempotence",
        code=f"A17-{uuid4().hex[:8]}",
        description="isolated scoring-only test",
    )
    db.add(project)
    await db.commit()
    engine = db.bind
    assert engine is not None

    @asynccontextmanager
    async def scoped_session(tenant_id):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # A fresh authenticated DB session before the human approval must not
    # inherit an invented Score from an earlier login or a stale process cache.
    async with scoped_session(tenant) as before_db:
        before = await get_coherence_dashboard(
            project_id,
            current_user=SimpleNamespace(tenant_id=tenant, id=actor),
            db=before_db,
            flags_service=None,
        )
    assert before.coherence_score is None

    calls = []

    async def fake_scoring(payload, session, user, *, review_id):
        assert user.tenant_id == tenant and payload.project_id == project_id
        calls.append(review_id)
        session.add(
            CoherenceResultORM(
                project_id=project_id,
                tenant_id=tenant,
                global_score=83,
                category_scores={"SCOPE": 83},
                category_details=[],
                alerts=[],
                score_version="coherence-v1",
                scoring_snapshot={"a17_approval_id": str(review_id)},
            )
        )
        # Allow second worker to attempt simultaneous lock acquisition.
        await asyncio.sleep(0.05)

    monkeypatch.setattr(subject, "get_session_with_tenant", scoped_session)
    monkeypatch.setattr(subject, "_run_evaluation", fake_scoring)

    async def once():
        await subject.run_project_evaluation_after_approval(
            tenant_id=tenant,
            project_id=project_id,
            actor_user_id=actor,
            review_id=review_id,
        )

    await asyncio.gather(once(), once())
    await once()  # idempotent later replay, too
    async with scoped_session(tenant) as session:
        found = await session.scalars(
            select(CoherenceResultORM).where(
                CoherenceResultORM.tenant_id == tenant,
                CoherenceResultORM.project_id == project_id,
                CoherenceResultORM.scoring_snapshot["a17_approval_id"].astext == str(review_id),
            )
        )
        rows = list(found)
    assert len(rows) == 1
    assert rows[0].global_score == 83
    assert calls == [review_id]

    # The second user principal emulates re-authentication after logout.
    # No HTTP session, identity object or DB connection is reused.
    relogin_actor = uuid4()
    async with scoped_session(tenant) as after_db:
        after = await get_coherence_dashboard(
            project_id,
            current_user=SimpleNamespace(tenant_id=tenant, id=relogin_actor),
            db=after_db,
            flags_service=None,
        )
    assert after.coherence_score == 83
    assert after.global_score == 83
    assert after.sub_scores["SCOPE"] == 83

    # A different tenant principal must not observe the project/Score even
    # when asking for the correct UUID; authorization is server-side.
    foreign_tenant = uuid4()
    async with scoped_session(foreign_tenant) as foreign_db:
        with pytest.raises(HTTPException) as exc:
            await get_coherence_dashboard(
                project_id,
                current_user=SimpleNamespace(tenant_id=foreign_tenant, id=uuid4()),
                db=foreign_db,
                flags_service=None,
            )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_a17_withheld_result_is_durable_and_idempotent_after_reauthentication(
    db: AsyncSession,
    test_tenant,
    monkeypatch: pytest.MonkeyPatch,
):
    """An unassessed Score is an explicit event, not a fabricated numeric row."""
    tenant, project_id, actor, review_id = test_tenant.id, uuid4(), uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant,
            name="Synthetic A17 withheld evidence",
            code=f"A17-W-{uuid4().hex[:8]}",
        )
    )
    await db.commit()
    engine = db.bind
    assert engine is not None

    @asynccontextmanager
    async def scoped_session(tenant_id):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    calls = []

    async def withheld_evaluation(payload, session, user, *, review_id):
        assert user.tenant_id == tenant and payload.project_id == project_id
        calls.append(review_id)
        await subject._record_approval_withheld(
            session,
            tenant_id=tenant,
            project_id=project_id,
            actor_user_id=actor,
            approval_id=str(review_id),
            reason="insufficient_evidence",
            missing_dimensions=["BUDGET"],
            score_version="coherence-v1",
            alert_count=0,
        )
        await asyncio.sleep(0.05)

    monkeypatch.setattr(subject, "get_session_with_tenant", scoped_session)
    monkeypatch.setattr(subject, "_run_evaluation", withheld_evaluation)

    async def attempt():
        await subject.run_project_evaluation_after_approval(
            tenant_id=tenant,
            project_id=project_id,
            actor_user_id=actor,
            review_id=review_id,
        )

    await asyncio.gather(attempt(), attempt())
    await attempt()  # repeated approval after another login
    assert calls == [review_id]

    async with scoped_session(tenant) as fresh_session:
        withheld_rows = (
            await fresh_session.scalars(
                select(ProjectEventORM).where(
                    ProjectEventORM.tenant_id == tenant,
                    ProjectEventORM.project_id == project_id,
                    ProjectEventORM.event_type == WITHHELD_EVALUATION_EVENT,
                    ProjectEventORM.payload["a17_approval_id"].astext == str(review_id),
                )
            )
        ).all()
        scores = (
            await fresh_session.scalars(
                select(CoherenceResultORM).where(
                    CoherenceResultORM.tenant_id == tenant,
                    CoherenceResultORM.project_id == project_id,
                )
            )
        ).all()
    assert len(withheld_rows) == 1
    assert withheld_rows[0].payload["score_reason"] == "insufficient_evidence"
    assert not scores

    # Second session, second principal: the dashboard continues to say
    # "not evaluated", rather than showing an invented 0 or a trusted 100.
    async with scoped_session(tenant) as relogin_session:
        response = await get_coherence_dashboard(
            project_id,
            current_user=SimpleNamespace(tenant_id=tenant, id=uuid4()),
            db=relogin_session,
            flags_service=None,
        )
    assert response.global_score is None
    assert response.coherence_score is None
    assert response.score_reason == "insufficient_evidence"


@pytest.mark.asyncio
async def test_a17_no_clauses_persists_withheld_after_approval_not_http_failure(
    db: AsyncSession,
    test_tenant,
    monkeypatch: pytest.MonkeyPatch,
):
    """Real PG, real no-clause evaluator, 2 concurrent workers + replay.

    This fixture deliberately has zero uploaded/parsed documents. HITL approval
    was already authorized upstream; the background result is unassessed, never
    an exception to the response, an invented score, or a duplicate event.
    """
    tenant, project_id, actor, review_id = test_tenant.id, uuid4(), uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant,
            name="A17 Missing Clauses Synthetic",
            code=f"A17-NODOC-{uuid4().hex[:8]}",
        )
    )
    await db.commit()
    engine = db.bind
    assert engine is not None

    @asynccontextmanager
    async def scoped_session(bound_tenant):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": str(bound_tenant)},
            )
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    monkeypatch.setattr(subject, "get_session_with_tenant", scoped_session)

    async def approve_retry():
        await subject.run_project_evaluation_after_approval(
            tenant_id=tenant,
            project_id=project_id,
            actor_user_id=actor,
            review_id=review_id,
        )

    await asyncio.gather(approve_retry(), approve_retry())
    await approve_retry()  # idempotent replay with same approval identifier

    async with scoped_session(tenant) as verification:
        events = list(
            (
                await verification.scalars(
                    select(ProjectEventORM).where(
                        ProjectEventORM.tenant_id == tenant,
                        ProjectEventORM.project_id == project_id,
                        ProjectEventORM.event_type == WITHHELD_EVALUATION_EVENT,
                        ProjectEventORM.payload["a17_approval_id"].astext == str(review_id),
                    )
                )
            ).all()
        )
        scores = list(
            (
                await verification.scalars(
                    select(CoherenceResultORM).where(
                        CoherenceResultORM.tenant_id == tenant,
                        CoherenceResultORM.project_id == project_id,
                    )
                )
            ).all()
        )
    assert len(events) == 1
    assert events[0].payload["score_reason"] == subject.NO_DOCUMENT_CLAUSES_REASON
    assert set(events[0].payload["score_missing_dimensions"]) == set(
        subject.NO_DOCUMENT_CLAUSES_DIMENSIONS
    )
    assert not scores

    # A different authenticated principal, freshly obtained session: reason
    # must survive; other tenant must not retrieve the same approval event.
    async with scoped_session(tenant) as relogin_session:
        summary = await get_coherence_dashboard(
            project_id,
            current_user=SimpleNamespace(tenant_id=tenant, id=uuid4()),
            db=relogin_session,
            flags_service=None,
        )
    assert summary.global_score is None
    assert summary.coherence_score is None
    assert summary.score_reason == subject.NO_DOCUMENT_CLAUSES_REASON

    alien = uuid4()
    async with scoped_session(alien) as foreign_session:
        foreign = await foreign_session.scalar(
            select(ProjectEventORM.event_id).where(
                ProjectEventORM.tenant_id == alien,
                ProjectEventORM.project_id == project_id,
                ProjectEventORM.event_type == WITHHELD_EVALUATION_EVENT,
            )
        )
        assert foreign is None
        with pytest.raises(HTTPException) as exc:
            await get_coherence_dashboard(
                project_id,
                current_user=SimpleNamespace(tenant_id=alien, id=uuid4()),
                db=foreign_session,
                flags_service=None,
            )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_a17_failure_rolls_back_and_retry_scores_once_pg(
    db: AsyncSession,
    test_tenant,
    monkeypatch: pytest.MonkeyPatch,
):
    """Evaluation failure is retryable, does not create a success/withheld marker."""
    tenant, project_id, actor, review_id = test_tenant.id, uuid4(), uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant,
            name="A17 Retry Synthetic",
            code=f"A17-RETRY-{uuid4().hex[:8]}",
        )
    )
    await db.commit()
    engine = db.bind
    assert engine is not None

    @asynccontextmanager
    async def scoped_session(bound_tenant):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": str(bound_tenant)},
            )
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    attempts: list[int] = []

    async def flaky_graph(payload, session, user, *, review_id):
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            # A partial write must be rolled back on failure.
            session.add(
                CoherenceResultORM(
                    project_id=project_id,
                    tenant_id=tenant,
                    global_score=99,
                    category_scores={"SCOPE": 99},
                    category_details=[],
                    alerts=[],
                    score_version="coherence-v1",
                    scoring_snapshot={"a17_approval_id": str(review_id)},
                )
            )
            raise RuntimeError("synthetic evaluation failure after write")
        session.add(
            CoherenceResultORM(
                project_id=project_id,
                tenant_id=tenant,
                global_score=67,
                category_scores={"SCOPE": 67},
                category_details=[],
                alerts=[],
                score_version="coherence-v1",
                scoring_snapshot={"a17_approval_id": str(review_id)},
            )
        )

    monkeypatch.setattr(subject, "get_session_with_tenant", scoped_session)
    monkeypatch.setattr(subject, "_run_evaluation", flaky_graph)

    async def attempt():
        return await subject.run_project_evaluation_after_approval(
            tenant_id=tenant,
            project_id=project_id,
            actor_user_id=actor,
            review_id=review_id,
        )

    assert await attempt() is None
    async with scoped_session(tenant) as verify_failed:
        assert not list(
            (
                await verify_failed.scalars(
                    select(CoherenceResultORM).where(CoherenceResultORM.project_id == project_id)
                )
            ).all()
        )
        assert not list(
            (
                await verify_failed.scalars(
                    select(ProjectEventORM).where(
                        ProjectEventORM.project_id == project_id,
                        ProjectEventORM.event_type == WITHHELD_EVALUATION_EVENT,
                    )
                )
            ).all()
        )
    assert await attempt() is None
    assert await attempt() is None
    assert attempts == [1, 2]
    async with scoped_session(tenant) as verify_success:
        results = list(
            (
                await verify_success.scalars(
                    select(CoherenceResultORM).where(
                        CoherenceResultORM.tenant_id == tenant,
                        CoherenceResultORM.project_id == project_id,
                    )
                )
            ).all()
        )
    assert len(results) == 1
    assert results[0].global_score == 67
