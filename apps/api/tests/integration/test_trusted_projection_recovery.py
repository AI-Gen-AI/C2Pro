"""G4 real-PostgreSQL recovery contract for a TRUSTED document projection.

The test exercises the routing ledger and persisted ACK, but substitutes the
Celery publish operation. It does not claim that Railway Beat was observed.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.core.tasks import project_graph_tasks as tasks
from tests.integration.document_flow.test_budget_revision_authority_flow import _trust
from tests.integration.document_flow.test_contract_revision_authority_flow import _contract_scenario
from tests.integration.document_flow.test_contract_schedule_completion_flow import worker  # noqa: F401


@pytest.mark.asyncio
async def test_trusted_pending_projection_reenqueues_then_only_real_loaded_artifact_is_acknowledged(
    db: AsyncSession, worker, test_user, monkeypatch
) -> None:
    project_id, contract, revision = await _contract_scenario(db, worker, test_user)
    await _trust(db, test_user, project_id, contract, revision)

    ledger = text(
        "SELECT artifact_id, projection_state, enqueue_attempts "
        "FROM system_recovery.trusted_projection_index "
        "WHERE tenant_id = :tenant AND project_id = :project "
        "AND document_id = :document"
    )
    params = {
        "tenant": test_user.tenant_id,
        "project": project_id,
        "document": contract.id,
    }
    rows = (await db.execute(ledger, params)).all()
    assert len(rows) == 1, "a real trusted artifact must create one durable obligation"
    artifact_id: UUID = rows[0].artifact_id
    assert rows[0].projection_state == "pending"

    old = (datetime.now(UTC) - timedelta(minutes=5)).replace(tzinfo=None)
    await db.execute(
        text(
            "UPDATE system_recovery.trusted_projection_index "
            "SET created_at = :old, last_checked_at = NULL "
            "WHERE artifact_id = :aid"
        ),
        {"old": old, "aid": artifact_id},
    )
    await db.commit()

    @asynccontextmanager
    async def session_for_reconciler():
        yield db

    publish = AsyncMock()
    monkeypatch.setattr(tasks, "init_db", AsyncMock())
    monkeypatch.setattr(tasks, "get_raw_session", session_for_reconciler)
    monkeypatch.setattr(tasks, "is_project_graph_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(tasks, "enqueue_project_graph", publish)

    counts = await tasks.reconcile_trusted_projections(
        grace_seconds=120, batch_size=10
    )
    assert counts == {"scanned": 1, "enqueued": 1, "flag_disabled": 0, "exhausted": 0}
    publish.assert_awaited_once_with(
        project_id=project_id, tenant_id=test_user.tenant_id
    )
    pending = (await db.execute(ledger, params)).one()
    assert pending.projection_state == "pending"
    assert pending.enqueue_attempts == 1, "enqueue is NOT a projection ACK"

    repository = SqlAlchemyDocumentArtifactRepository(db)
    trusted = await repository.list_trusted_for_project(
        project_id=project_id, tenant_id=test_user.tenant_id
    )
    assert len(trusted) == 1
    assert trusted[0].document_id == str(contract.id)
    assert await repository.mark_loaded_projected(
        project_id=project_id, tenant_id=test_user.tenant_id
    ) == 1
    await db.commit()
    assert (await db.execute(ledger, params)).one().projection_state == "projected"

    publish.reset_mock()
    again = await tasks.reconcile_trusted_projections(
        grace_seconds=120, batch_size=10
    )
    assert again["scanned"] == again["enqueued"] == 0
    publish.assert_not_awaited()
