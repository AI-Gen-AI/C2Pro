"""A17 transaction/idempotence smoke against disposable PostgreSQL; synthetic rows only."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.application import project_evaluation as subject
from src.projects.adapters.persistence.models import ProjectORM


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
