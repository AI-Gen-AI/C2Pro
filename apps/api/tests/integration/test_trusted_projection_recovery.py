"""G4: real PostgreSQL trusted projection recovery without a live broker.

This test never claims to verify Railway Beat delivery: only the scheduler
registration and durable DB -> requeue -> successful acknowledgment protocol.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.core.tasks import project_graph_tasks as tasks
from tests.integration.document_flow.test_contract_revision_authority_flow import (
    _contract_scenario,
    _propose,
    _trust,
    worker,  # noqa: F401 — pytest fixture using real DOCX/XLSX ingestion
)

pytestmark = pytest.mark.asyncio


async def test_real_trusted_projection_requeues_and_only_success_acknowledges(
    db: AsyncSession, worker, test_user, monkeypatch
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    await _propose(db, test_user, project_id, contract, revision)
    await _trust(db, test_user, project_id, contract, revision)

    tenant_id = test_user.tenant_id
    artifacts = (
        await db.execute(
            text(
                "SELECT artifact_id FROM document_artifacts "
                "WHERE tenant_id = :t AND project_id = :p "
                "AND document_id = :d AND trust_state = 'trusted' "
                "AND lifecycle_status = 'active'"
            ),
            {"t": tenant_id, "p": project_id, "d": contract.id},
        )
    ).scalars().all()
    assert len(artifacts) == 1
    artifact_id = artifacts[0]

    # The real trust decision creates a DB obligation. Backdate ONLY this
    # isolated test row so it crosses the grace window deterministically.
    await db.execute(
        text(
            "UPDATE system_recovery.trusted_projection_index "
            "SET projection_state = 'pending', enqueue_attempts = 0, "
            "created_at = (clock_timestamp() AT TIME ZONE 'UTC') - interval '180 seconds', "
            "last_checked_at = NULL WHERE artifact_id = :a"
        ),
        {"a": artifact_id},
    )
    assert (
        await db.execute(
            text(
                "SELECT count(*) FROM system_recovery.trusted_projection_index "
                "WHERE artifact_id = :a AND projection_state = 'pending'"
            ),
            {"a": artifact_id},
        )
    ).scalar_one() == 1
    await db.commit()

    @asynccontextmanager
    async def db_session():
        yield db

    enqueue = AsyncMock()
    enabled = AsyncMock(return_value=True)
    monkeypatch.setattr(tasks, "init_db", AsyncMock())
    monkeypatch.setattr(tasks, "get_raw_session", db_session)
    monkeypatch.setattr(tasks, "is_project_graph_enabled", enabled)
    monkeypatch.setattr(tasks, "enqueue_project_graph", enqueue)

    first = await tasks.reconcile_trusted_projections(grace_seconds=120)
    assert first["enqueued"] >= 1
    enqueue.assert_any_await(project_id=project_id, tenant_id=tenant_id)

    state = (
        await db.execute(
            text(
                "SELECT projection_state, enqueue_attempts "
                "FROM system_recovery.trusted_projection_index "
                "WHERE artifact_id = :a"
            ),
            {"a": artifact_id},
        )
    ).one()
    assert state.projection_state == "pending", "requeue must not acknowledge work"
    assert state.enqueue_attempts == 1

    repository = SqlAlchemyDocumentArtifactRepository(db)
    trusted = await repository.list_trusted_for_project(
        project_id=project_id, tenant_id=tenant_id
    )
    assert any(item.document_id == str(contract.id) for item in trusted)
    assert await repository.mark_loaded_projected(
        project_id=project_id, tenant_id=tenant_id
    ) >= 1
    await db.commit()

    assert (
        await db.execute(
            text(
                "SELECT projection_state FROM system_recovery.trusted_projection_index "
                "WHERE artifact_id = :a"
            ),
            {"a": artifact_id},
        )
    ).scalar_one() == "projected"

    enqueue.reset_mock()
    again = await tasks.reconcile_trusted_projections(grace_seconds=120)
    assert again["enqueued"] == 0
    enqueue.assert_not_awaited()

    # A newly pending exhausted obligation remains visible to operators;
    # exhaustion cannot silently mark it projected or cause a retry storm.
    await db.execute(
        text(
            "UPDATE system_recovery.trusted_projection_index "
            "SET projection_state = 'pending', enqueue_attempts = 12, "
            "created_at = (clock_timestamp() AT TIME ZONE 'UTC') - interval '180 seconds', "
            "last_checked_at = NULL WHERE artifact_id = :a"
        ),
        {"a": artifact_id},
    )
    await db.commit()
    exhausted = await tasks.reconcile_trusted_projections(grace_seconds=120)
    assert exhausted["exhausted"] >= 1
    enqueue.assert_not_awaited()
    final = (
        await db.execute(
            text(
                "SELECT projection_state, enqueue_attempts "
                "FROM system_recovery.trusted_projection_index WHERE artifact_id = :a"
            ),
            {"a": artifact_id},
        )
    ).one()
    assert final.projection_state == "pending" and final.enqueue_attempts == 12
