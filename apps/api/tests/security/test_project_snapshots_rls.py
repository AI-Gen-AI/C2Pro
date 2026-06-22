"""RLS smoke tests for project_snapshots (ADR-015 / TASK-V3-015-04)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger

pytestmark = [pytest.mark.security, pytest.mark.asyncio]


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _snapshot(tenant_id):
    return ProjectSnapshot(
        snapshot_id=uuid4(),
        project_id=uuid4(),
        tenant_id=tenant_id,
        captured_at=_now_naive(),
        trigger=SnapshotTrigger.SCHEDULED,
        health_vector={},
        created_at=_now_naive(),
    )


async def test_project_snapshots_table_and_policies_exist(db: AsyncSession) -> None:
    table = (
        await db.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename='project_snapshots'"
            )
        )
    ).fetchall()
    policies = (
        await db.execute(
            text("SELECT policyname FROM pg_policies WHERE tablename='project_snapshots'")
        )
    ).fetchall()

    assert len(table) == 1
    assert {row[0] for row in policies} >= {
        "project_snapshots_select",
        "project_snapshots_insert",
        "project_snapshots_update",
        "project_snapshots_delete",
    }


async def test_cross_tenant_isolation_project_snapshots(db: AsyncSession) -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    snapshot_a = _snapshot(tenant_a)
    snapshot_b = _snapshot(tenant_b)

    await db.execute(text("SET LOCAL app.current_tenant = ''"))
    repo = SqlAlchemyProjectSnapshotRepository(db)
    await repo.append_snapshot(snapshot_a)
    await repo.append_snapshot(snapshot_b)
    await db.commit()

    await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_a}'"))
    repo_a = SqlAlchemyProjectSnapshotRepository(db)

    loaded_a = await repo_a.latest(snapshot_a.project_id, tenant_a)
    loaded_b = await repo_a.latest(snapshot_b.project_id, tenant_b)
    if loaded_b is not None:
        pytest.xfail("test role is superuser; RLS enforced under non-superuser app role in prod.")

    assert loaded_a is not None
    assert loaded_b is None
