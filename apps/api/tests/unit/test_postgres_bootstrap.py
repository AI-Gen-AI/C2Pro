"""TS-E2E-SEC-TNT-001

Regression coverage for PostgreSQL test bootstrap transaction handling.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.support.postgres_bootstrap import (
    reset_public_schema,
    run_postgres_test_bootstrap,
)


class _FakeTransaction:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class _FakeConnection:
    def __init__(self) -> None:
        self.transaction = _FakeTransaction()
        self.executed_sql: list[str] = []

    async def begin(self) -> _FakeTransaction:
        return self.transaction

    async def execute(self, statement: Any) -> None:
        self.executed_sql.append(str(statement))


class _FakeConnectionContext:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeEngine:
    def __init__(self, connections: list[_FakeConnection]) -> None:
        self._connections = connections
        self.opened = 0

    def connect(self) -> _FakeConnectionContext:
        connection = self._connections[self.opened]
        self.opened += 1
        return _FakeConnectionContext(connection)


@pytest.mark.asyncio
async def test_run_postgres_test_bootstrap_recovers_from_cleanup_failure() -> None:
    """TS-E2E-SEC-TNT-001 keeps prepare work in a fresh transaction after cleanup fails."""

    cleanup_connection = _FakeConnection()
    prepare_connection = _FakeConnection()
    engine = _FakeEngine([cleanup_connection, prepare_connection])
    prepare_calls = 0
    warnings: list[str] = []

    async def cleanup_step(connection: _FakeConnection) -> None:
        raise RuntimeError("drop_all failed")

    async def prepare_step(connection: _FakeConnection) -> None:
        nonlocal prepare_calls
        prepare_calls += 1
        await connection.execute("PREPARE")

    await run_postgres_test_bootstrap(
        engine,
        cleanup_step=cleanup_step,
        prepare_step=prepare_step,
        warning_sink=lambda exc: warnings.append(str(exc)),
    )

    assert cleanup_connection.transaction.rollbacks == 1
    assert cleanup_connection.transaction.commits == 0
    assert prepare_connection.transaction.commits == 1
    assert prepare_connection.transaction.rollbacks == 0
    assert prepare_calls == 1
    assert warnings == ["drop_all failed"]
    assert cleanup_connection.executed_sql[:2] == [
        "SET LOCAL search_path TO public",
        "SELECT 1",
    ]
    assert prepare_connection.executed_sql[:3] == [
        "SET LOCAL search_path TO public",
        "SELECT 1",
        "PREPARE",
    ]


@pytest.mark.asyncio
async def test_reset_public_schema_recreates_public_schema() -> None:
    """TS-E2E-SEC-TNT-001 resets stale public schema objects before metadata recreation."""

    connection = _FakeConnection()

    await reset_public_schema(connection)

    assert connection.executed_sql == [
        'DROP SCHEMA IF EXISTS public CASCADE',
        'CREATE SCHEMA public',
        'SET search_path TO public',
    ]
