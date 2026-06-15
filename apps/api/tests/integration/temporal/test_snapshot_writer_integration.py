"""Integration tests for SnapshotWriter (ADR-015 / TASK-V3-015-05)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.domain.contracts import BudgetItem
from src.project_state.adapters.persistence.project_state_repository import (
    SqlAlchemyProjectStateRepository,
)
from src.project_state.domain.aggregate import ProjectState
from src.project_state.domain.entities import ProjectBudgetItem
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.domain.project_snapshot import SnapshotTrigger

pytestmark = pytest.mark.asyncio


async def test_snapshot_writer_appends_snapshot_and_latest_returns_it(
    db: AsyncSession,
) -> None:
    from src.temporal.application.snapshot_writer import SnapshotWriter

    project_id = uuid4()
    tenant_id = uuid4()
    state_repo = SqlAlchemyProjectStateRepository(db)
    snapshot_repo = SqlAlchemyProjectSnapshotRepository(db)

    await state_repo.save(
        ProjectState(
            project_id=project_id,
            tenant_id=tenant_id,
            budget_items=[
                ProjectBudgetItem(
                    entity_id=uuid4(),
                    payload=BudgetItem(name="Concrete", amount=42.0),
                )
            ],
        )
    )
    await db.commit()

    snapshot = await SnapshotWriter(
        project_state_repository=state_repo,
        snapshot_repository=snapshot_repo,
    ).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.REVISION_INGESTED,
    )
    await db.commit()

    latest = await snapshot_repo.latest(project_id, tenant_id)
    assert latest is not None
    assert latest.snapshot_id == snapshot.snapshot_id
    assert latest.counts["budget_items"] == 1
    assert latest.totals["budget_amount"] == 42.0
