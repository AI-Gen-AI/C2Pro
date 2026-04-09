"""TS-E2E-SEC-TNT-001

Regression coverage for PostgreSQL test bootstrap transaction handling.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.support.postgres_bootstrap import (
    ensure_pgvector_extension,
    reset_public_schema,
    run_postgres_test_bootstrap,
)


def _normalize_sql(sql: str) -> str:
    return " ".join(sql.split())


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
        self.extension_exists = False
        self.vector_schema: str | None = None

    async def begin(self) -> _FakeTransaction:
        return self.transaction

    async def execute(self, statement: Any):
        sql = str(statement)
        self.executed_sql.append(sql)

        class _FakeResult:
            def __init__(self, scalar_value) -> None:
                self._scalar_value = scalar_value

            def scalar_one(self):
                return self._scalar_value

            def scalar_one_or_none(self):
                return self._scalar_value

        if "SELECT n.nspname" in sql:
            return _FakeResult(self.vector_schema)
        if "SELECT EXISTS (" in sql and "FROM pg_extension" in sql:
            return _FakeResult(self.extension_exists)
        if "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public" in sql:
            self.extension_exists = True
            self.vector_schema = "public"
            return _FakeResult(None)
        if "ALTER EXTENSION vector SET SCHEMA public" in sql:
            self.vector_schema = "public"
            return _FakeResult(None)
        return _FakeResult(None)


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
    extension_connection = _FakeConnection()
    prepare_connection = _FakeConnection()
    engine = _FakeEngine([cleanup_connection, extension_connection, prepare_connection])
    prepare_calls = 0
    warnings: list[str] = []

    async def cleanup_step(_connection: _FakeConnection) -> None:
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
    assert extension_connection.transaction.commits == 1
    assert extension_connection.transaction.rollbacks == 0
    assert prepare_connection.transaction.commits == 1
    assert prepare_connection.transaction.rollbacks == 0
    assert prepare_calls == 1
    assert warnings == ["drop_all failed"]
    assert cleanup_connection.executed_sql[:2] == [
        "SET LOCAL search_path TO public",
        "SELECT 1",
    ]
    assert extension_connection.executed_sql[:2] == [
        "SET LOCAL search_path TO public",
        "SELECT 1",
    ]
    assert _normalize_sql(extension_connection.executed_sql[2]) == _normalize_sql(
        """
        SELECT n.nspname
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'vector'
        ORDER BY CASE WHEN n.nspname = 'public' THEN 0 ELSE 1 END
        LIMIT 1
        """
    )
    assert _normalize_sql(extension_connection.executed_sql[3]) == _normalize_sql(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_extension
            WHERE extname = 'vector'
        )
        """
    )
    assert extension_connection.executed_sql[4] == "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public"
    assert _normalize_sql(extension_connection.executed_sql[5]) == _normalize_sql(
        """
        SELECT n.nspname
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'vector'
        ORDER BY CASE WHEN n.nspname = 'public' THEN 0 ELSE 1 END
        LIMIT 1
        """
    )
    assert prepare_connection.executed_sql == [
        "SET LOCAL search_path TO public",
        "SELECT 1",
        "PREPARE",
    ]


@pytest.mark.asyncio
async def test_run_postgres_test_bootstrap_enables_pgvector_before_prepare() -> None:
    """TS-E2E-SEC-TNT-001 enables pgvector before metadata preparation runs."""

    cleanup_connection = _FakeConnection()
    extension_connection = _FakeConnection()
    prepare_connection = _FakeConnection()
    engine = _FakeEngine([cleanup_connection, extension_connection, prepare_connection])
    prepare_calls = 0

    async def cleanup_step(_connection: _FakeConnection) -> None:
        return None

    async def prepare_step(prepare_connection: _FakeConnection) -> None:
        nonlocal prepare_calls
        prepare_calls += 1
        await prepare_connection.execute("PREPARE")

    await run_postgres_test_bootstrap(
        engine,
        cleanup_step=cleanup_step,
        prepare_step=prepare_step,
        warning_sink=lambda exc: pytest.fail(f"unexpected warning: {exc}"),
    )

    assert prepare_calls == 1
    schema_query = """
        SELECT n.nspname
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'vector'
        ORDER BY CASE WHEN n.nspname = 'public' THEN 0 ELSE 1 END
        LIMIT 1
    """
    assert any(
        _normalize_sql(sql) == _normalize_sql(schema_query)
        for sql in extension_connection.executed_sql
    )
    assert "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public" in extension_connection.executed_sql
    assert prepare_connection.executed_sql == [
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
        "DROP EXTENSION IF EXISTS vector CASCADE",
        'DROP SCHEMA IF EXISTS public CASCADE',
        'CREATE SCHEMA public',
        'SET search_path TO public',
    ]


@pytest.mark.asyncio
async def test_ensure_pgvector_extension_executes_create_extension() -> None:
    """TS-E2E-SEC-TNT-001 enables pgvector before vector-backed metadata DDL."""

    connection = _FakeConnection()

    await ensure_pgvector_extension(connection)

    assert len(connection.executed_sql) == 4
    assert _normalize_sql(connection.executed_sql[0]) == _normalize_sql(
        """
        SELECT n.nspname
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'vector'
        ORDER BY CASE WHEN n.nspname = 'public' THEN 0 ELSE 1 END
        LIMIT 1
        """
    )
    assert _normalize_sql(connection.executed_sql[1]) == _normalize_sql(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_extension
            WHERE extname = 'vector'
        )
        """
    )
    assert connection.executed_sql[2] == "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public"
    assert _normalize_sql(connection.executed_sql[3]) == _normalize_sql(
        """
        SELECT n.nspname
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'vector'
        ORDER BY CASE WHEN n.nspname = 'public' THEN 0 ELSE 1 END
        LIMIT 1
        """
    )
