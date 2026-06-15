"""Snapshot retention and partition tests (ADR-015 / TASK-V3-015-06).

TS-IT-TSR-001
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger

pytestmark = pytest.mark.asyncio


async def _append_snapshot(
    repo: SqlAlchemyProjectSnapshotRepository,
    *,
    project_id,
    tenant_id,
    captured_at: datetime,
) -> ProjectSnapshot:
    snapshot = ProjectSnapshot(
        snapshot_id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=captured_at,
        trigger=SnapshotTrigger.SCHEDULED,
        health_vector={"status": "pending_health_engine"},
        counts={},
        totals={},
        created_at=captured_at,
    )
    return await repo.append_snapshot(snapshot)


async def test_snapshot_retention_keeps_recent_weekly_and_drops_old_partitions(
    db: AsyncSession,
) -> None:
    from src.core.tasks.snapshot_retention import (
        ensure_project_snapshot_partitions,
        project_snapshot_partition_name,
        run_snapshot_retention_once,
    )

    now = datetime(2026, 6, 16, 12, 0, 0)
    tenant_id = uuid4()
    project_id = uuid4()
    repo = SqlAlchemyProjectSnapshotRepository(db)

    await ensure_project_snapshot_partitions(
        db,
        anchor=now,
        months_back=42,
        months_ahead=2,
    )
    await db.commit()

    recent_one = await _append_snapshot(
        repo,
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=now - timedelta(days=5),
    )
    recent_two = await _append_snapshot(
        repo,
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=now - timedelta(days=30),
    )
    old_week_one = await _append_snapshot(
        repo,
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=now - timedelta(days=120),
    )
    old_week_duplicate = await _append_snapshot(
        repo,
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=now - timedelta(days=119),
    )
    old_other_week = await _append_snapshot(
        repo,
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=now - timedelta(days=130),
    )
    ancient = await _append_snapshot(
        repo,
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=datetime(2023, 1, 15, 12, 0, 0),
    )
    await db.commit()

    await run_snapshot_retention_once(
        db,
        now=now,
        daily_retention_days=90,
        partition_retention_days=730,
    )
    await db.commit()

    retained = await repo.list_since(project_id, tenant_id, datetime(2020, 1, 1))
    retained_ids = {snapshot.snapshot_id for snapshot in retained}
    assert recent_one.snapshot_id in retained_ids
    assert recent_two.snapshot_id in retained_ids
    assert old_other_week.snapshot_id in retained_ids
    assert old_week_one.snapshot_id not in retained_ids
    assert old_week_duplicate.snapshot_id in retained_ids
    assert ancient.snapshot_id not in retained_ids

    dropped_partition = project_snapshot_partition_name(datetime(2023, 1, 1))
    partition_result = await db.execute(
        text("SELECT to_regclass(:partition_name)"),
        {"partition_name": dropped_partition},
    )
    assert partition_result.scalar_one() is None

    future_partition = project_snapshot_partition_name(datetime(2026, 8, 1))
    future_partition_result = await db.execute(
        text("SELECT to_regclass(:partition_name)"),
        {"partition_name": future_partition},
    )
    assert future_partition_result.scalar_one() == future_partition

    future = await _append_snapshot(
        repo,
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=datetime(2026, 8, 5, 12, 0, 0),
    )
    await db.commit()
    retained_after_future_insert = await repo.latest(project_id, tenant_id)
    assert retained_after_future_insert is not None
    assert retained_after_future_insert.snapshot_id == future.snapshot_id
