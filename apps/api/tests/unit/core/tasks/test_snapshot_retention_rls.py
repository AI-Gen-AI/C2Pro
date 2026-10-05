"""Focused #870 tests for avoiding repeated RLS DDL locks."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.tasks import snapshot_retention
from src.core.tasks.snapshot_retention import _execute_partition_sql

pytestmark = pytest.mark.asyncio


def _rls_result(enabled: bool) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = enabled
    return result


async def test_existing_secured_partition_skips_repeat_alter() -> None:
    session = AsyncMock()
    session.execute.side_effect = [MagicMock(), _rls_result(True)]

    await _execute_partition_sql(
        session,
        partition_name="project_snapshots_2027_01",
        start=date(2027, 1, 1),
        end=date(2027, 2, 1),
    )

    assert session.execute.await_count == 2
    statements = [str(call.args[0]) for call in session.execute.await_args_list]
    assert "CREATE TABLE IF NOT EXISTS project_snapshots_2027_01" in statements[0]
    assert "relrowsecurity" in statements[1]
    assert all("ALTER TABLE" not in statement for statement in statements)


async def test_unsecured_partition_is_closed_once() -> None:
    session = AsyncMock()
    session.execute.side_effect = [MagicMock(), _rls_result(False), MagicMock()]

    await _execute_partition_sql(
        session,
        partition_name="project_snapshots_2027_01",
        start=date(2027, 1, 1),
        end=date(2027, 2, 1),
    )

    assert session.execute.await_count == 3
    statements = [str(call.args[0]) for call in session.execute.await_args_list]
    assert "relrowsecurity" in statements[1]
    assert (
        "ALTER TABLE project_snapshots_2027_01 ENABLE ROW LEVEL SECURITY"
        in statements[2]
    )



async def test_existing_secured_default_partition_skips_repeat_alter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    is_partitioned = AsyncMock(return_value=True)
    rls_enabled = AsyncMock(return_value=True)
    execute_partition = AsyncMock()

    monkeypatch.setattr(snapshot_retention, "_is_partitioned", is_partitioned)
    monkeypatch.setattr(snapshot_retention, "_rls_enabled", rls_enabled)
    monkeypatch.setattr(
        snapshot_retention,
        "_execute_partition_sql",
        execute_partition,
    )

    await snapshot_retention.ensure_project_snapshot_partitions(
        session,
        anchor=None,
        months_back=0,
        months_ahead=0,
    )

    statements = [str(call.args[0]) for call in session.execute.await_args_list]
    assert len(statements) == 1
    assert "CREATE TABLE IF NOT EXISTS project_snapshots_default" in statements[0]
    assert all("ALTER TABLE" not in statement for statement in statements)
    rls_enabled.assert_awaited_once_with(
        session,
        table_name="project_snapshots_default",
    )
    execute_partition.assert_awaited_once()
