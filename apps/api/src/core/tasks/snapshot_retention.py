"""Project snapshot retention tasks (ADR-015 / TASK-V3-015-06).

TS-IT-TSR-001
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_raw_session, init_db
from src.core.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_DEFAULT_DAILY_RETENTION_DAYS = 90
_DEFAULT_PARTITION_RETENTION_DAYS = 730
_PARTITION_NAME_RE = re.compile(r"^project_snapshots_[0-9]{4}_[0-9]{2}$")


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _month_start(value: datetime | date) -> date:
    return date(value.year, value.month, 1)


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    return date(value.year + month_index // 12, month_index % 12 + 1, 1)


def project_snapshot_partition_name(month_start: datetime | date) -> str:
    month = _month_start(month_start)
    return f"project_snapshots_{month:%Y_%m}"


async def _is_partitioned(session: AsyncSession) -> bool:
    result = await session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_partitioned_table pt
                JOIN pg_class c ON c.oid = pt.partrelid
                WHERE c.relname = 'project_snapshots'
            )
            """
        )
    )
    return bool(result.scalar_one())


async def _execute_partition_sql(
    session: AsyncSession,
    *,
    partition_name: str,
    start: date,
    end: date,
) -> None:
    if _PARTITION_NAME_RE.fullmatch(partition_name) is None:
        raise ValueError(f"Invalid project snapshot partition name: {partition_name}")
    await session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF project_snapshots
            FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')
            """
        )
    )


async def ensure_project_snapshot_partitions(
    session: AsyncSession,
    *,
    anchor: datetime | None = None,
    months_back: int = 0,
    months_ahead: int = 2,
) -> None:
    if not await _is_partitioned(session):
        return

    await session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS project_snapshots_default
            PARTITION OF project_snapshots DEFAULT
            """
        )
    )
    base_month = _month_start(anchor or _utcnow())
    for offset in range(-months_back, months_ahead + 1):
        start = _add_months(base_month, offset)
        end = _add_months(start, 1)
        await _execute_partition_sql(
            session,
            partition_name=project_snapshot_partition_name(start),
            start=start,
            end=end,
        )


async def _delete_extra_weekly_snapshots(
    session: AsyncSession,
    *,
    cutoff: datetime,
) -> int:
    result = await session.execute(
        text(
            """
            WITH ranked AS (
                SELECT
                    tableoid,
                    ctid,
                    row_number() OVER (
                        PARTITION BY tenant_id, project_id, date_trunc('week', captured_at)
                        ORDER BY captured_at DESC, created_at DESC
                    ) AS rn
                FROM project_snapshots
                WHERE captured_at < :cutoff
            )
            DELETE FROM project_snapshots ps
            USING ranked
            WHERE ps.tableoid = ranked.tableoid
              AND ps.ctid = ranked.ctid
              AND ranked.rn > 1
            """
        ),
        {"cutoff": cutoff},
    )
    return int(result.rowcount or 0)


async def _drop_old_partitions(
    session: AsyncSession,
    *,
    older_than: datetime,
) -> list[str]:
    if not await _is_partitioned(session):
        return []

    cutoff_month = _month_start(older_than)
    result = await session.execute(
        text(
            """
            SELECT child.relname
            FROM pg_inherits
            JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
            JOIN pg_class child ON pg_inherits.inhrelid = child.oid
            WHERE parent.relname = 'project_snapshots'
              AND child.relname ~ '^project_snapshots_[0-9]{4}_[0-9]{2}$'
            """
        )
    )

    dropped: list[str] = []
    for partition_name in result.scalars().all():
        _, _, year_text, month_text = partition_name.split("_")
        partition_month = date(int(year_text), int(month_text), 1)
        if partition_month < cutoff_month:
            await session.execute(text(f"DROP TABLE IF EXISTS {partition_name}"))
            dropped.append(partition_name)
    return dropped


async def run_snapshot_retention_once(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    daily_retention_days: int = _DEFAULT_DAILY_RETENTION_DAYS,
    partition_retention_days: int = _DEFAULT_PARTITION_RETENTION_DAYS,
) -> dict[str, object]:
    current_time = now or _utcnow()
    await ensure_project_snapshot_partitions(session, anchor=current_time, months_ahead=2)
    deleted = await _delete_extra_weekly_snapshots(
        session,
        cutoff=current_time - timedelta(days=daily_retention_days),
    )
    dropped = await _drop_old_partitions(
        session,
        older_than=current_time - timedelta(days=partition_retention_days),
    )
    return {"deleted": deleted, "dropped_partitions": dropped}


async def _run_snapshot_retention_async() -> dict[str, object]:
    await init_db()
    async with get_raw_session() as session:
        try:
            result = await run_snapshot_retention_once(session)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            logger.exception("snapshot_retention_failed")
            raise


@celery_app.task(
    name="project_snapshots.retention",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
)
def run_snapshot_retention(_self) -> dict[str, object]:
    return asyncio.run(_run_snapshot_retention_async())
