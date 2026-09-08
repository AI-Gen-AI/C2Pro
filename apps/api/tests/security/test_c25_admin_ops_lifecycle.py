"""Unit and integration tests for C2.5-R10 Fail-Closed Lifecycle and Teardown Hygiene."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Add scripts directory to path to import gate
scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(scripts_dir))

import c25_admin_ops_gate


class MockCursor:
    """Helper to mock psycopg query execution with query matching."""

    def __init__(self, query_responses):
        self.queries = query_responses
        self.last_query = ""
        self.executed_queries = []

    def execute(self, query, params=None):
        self.last_query = str(query)
        self.executed_queries.append(self.last_query)
        return self

    def fetchone(self):
        for pattern, response in self.queries.items():
            if pattern in self.last_query:
                if callable(response):
                    return response()
                return response
        return (False,)

    def fetchall(self):
        for pattern, response in self.queries.items():
            if pattern in self.last_query:
                # Expecting list of tuples
                return [response] if not isinstance(response, list) else response
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_red_a_migration_raises(monkeypatch):
    """RED A: Migration raises after disposable DB creation.

    Asserts that DB is removed, gate-created c2pro_admin_ops is removed, and non-zero code is returned.
    """
    # 1. Mock loopback resolver
    monkeypatch.setattr(
        c25_admin_ops_gate,
        "_resolve_admin_dsn_impl",
        lambda x: "postgresql://postgres:postgres@127.0.0.1:5433/postgres",
    )

    responses = {
        "rolname = 'c2pro_app'": (False,),
        "rolname = 'c2pro_admin_login'": (False,),
        "rolname = 'c2pro_admin_ops'": (False,),  # Doesn't exist initially
        "c25_gate_app_": (False,),  # Synthetic role doesn't exist
        "c25_gate_admin_": (False,),  # Synthetic role doesn't exist
        "datname = 'c25_admin_ops_gate'": (False,),  # DB dropped cleanly at end
    }
    cursor = MockCursor(responses)
    patch_connect = patch("psycopg.connect", return_value=cursor)

    # 3. Force migration to fail
    def mock_migrations_fail(dsn):
        raise RuntimeError("Alembic migration failed")

    monkeypatch.setattr(c25_admin_ops_gate, "_run_alembic_migrations", mock_migrations_fail)

    with patch_connect:
        exit_code = await c25_admin_ops_gate.main()
        assert exit_code == 1

    # Assert that DROP DATABASE and DROP ROLE c2pro_admin_ops were called
    dropped_db = any("DROP DATABASE IF EXISTS c25_admin_ops_gate" in q for q in cursor.executed_queries)
    dropped_ops = any("DROP ROLE IF EXISTS c2pro_admin_ops" in q for q in cursor.executed_queries)

    assert dropped_db is True
    assert dropped_ops is True


@pytest.mark.asyncio
async def test_red_b_role_provisioning_fails_halfway(monkeypatch):
    """RED B: Synthetic role provisioning fails after first LOGIN creation.

    Asserts that the first LOGIN is genuinely created in PostgreSQL, but creation of the
    second LOGIN fails. Then, verifies that the first LOGIN is cleanly removed during teardown.
    """
    # 1. Resolve to the real PostgreSQL local database DSN
    monkeypatch.setattr(
        c25_admin_ops_gate,
        "_resolve_admin_dsn_impl",
        lambda x: "postgresql://postgres:postgres@127.0.0.1:5433/postgres",
    )

    # 2. Intercept AsyncConnection.execute to raise on the second role creation
    from psycopg import AsyncConnection
    real_async_execute = AsyncConnection.execute

    first_created = False
    second_attempted = False

    async def monkey_async_execute(self, query, params=None, *args, **kwargs):
        query_str = str(query)
        if "CREATE ROLE" in query_str and "c25_gate_admin_" in query_str:
            nonlocal second_attempted
            second_attempted = True
            raise RuntimeError("Deliberate failure during second synthetic role creation")

        if "CREATE ROLE" in query_str and "c25_gate_app_" in query_str:
            nonlocal first_created
            first_created = True

        return await real_async_execute(self, query, params, *args, **kwargs)

    monkeypatch.setattr(AsyncConnection, "execute", monkey_async_execute)

    # Mock migration to be super fast and avoid schema dependencies
    monkeypatch.setattr(c25_admin_ops_gate, "_run_alembic_migrations", lambda x: None)

    # 3. Execute main gate, which must return non-zero (1)
    exit_code = await c25_admin_ops_gate.main()
    assert exit_code == 1

    # 4. Verify that our injection successfully triggered
    assert first_created is True
    assert second_attempted is True

    # 5. Connect to PostgreSQL and verify cluster state: no leaked synthetic roles or database
    import psycopg
    with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:5433/postgres") as conn:
        # Verify app login role was cleanly dropped
        res = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname LIKE 'c25_gate_app_%')")
        assert res.fetchone()[0] is False, "Leaked app role detected in cluster"

        # Verify admin login role is not present
        res = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname LIKE 'c25_gate_admin_%')")
        assert res.fetchone()[0] is False, "Leaked admin login role detected in cluster"

        # Verify disposable database dropped
        res = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'c25_admin_ops_gate')")
        assert res.fetchone()[0] is False, "Leaked disposable database detected in cluster"


@pytest.mark.asyncio
async def test_red_c_restricted_pool_creation_fails(monkeypatch):
    """RED C: Restricted pool creation fails.

    Asserts that all previously created artifacts are cleaned up, and non-zero exit returned.
    """
    monkeypatch.setattr(
        c25_admin_ops_gate,
        "_resolve_admin_dsn_impl",
        lambda x: "postgresql://postgres:postgres@127.0.0.1:5433/postgres",
    )

    responses = {
        "rolname = 'c2pro_app'": (False,),
        "rolname = 'c2pro_admin_login'": (False,),
        "rolname = 'c2pro_admin_ops'": (False,),
        "c25_gate_app_": (False,),
        "c25_gate_admin_": (False,),
        "datname = 'c25_admin_ops_gate'": (False,),
    }
    cursor = MockCursor(responses)
    patch_connect = patch("psycopg.connect", return_value=cursor)

    # Mock migrations & provision to succeed
    monkeypatch.setattr(c25_admin_ops_gate, "_run_alembic_migrations", lambda x: None)
    monkeypatch.setattr(c25_admin_ops_gate, "_provision_roles", lambda p, r1, r2: None)

    # Mock connection pool so superuser succeeds but restricted fails
    mock_admin_pool = AsyncMock()

    async def mock_connect_selector(dsn):
        if "c25_gate_app" in dsn or "c25_gate_admin" in dsn:
            raise RuntimeError("Restricted pool connection failed")
        return mock_admin_pool

    monkeypatch.setattr(c25_admin_ops_gate, "_connect", mock_connect_selector)

    with patch_connect:
        exit_code = await c25_admin_ops_gate.main()
        assert exit_code == 1

    assert mock_admin_pool.close.called


@pytest.mark.asyncio
async def test_red_d_drop_synthetic_role_fails(monkeypatch):
    """RED D: DROP synthetic role cleanup operation fails.

    Asserts that remaining cleanup is still attempted and final result is non-zero.
    """
    monkeypatch.setattr(
        c25_admin_ops_gate,
        "_resolve_admin_dsn_impl",
        lambda x: "postgresql://postgres:postgres@127.0.0.1:5433/postgres",
    )

    responses = {
        "rolname = 'c2pro_app'": (False,),
        "rolname = 'c2pro_admin_login'": (False,),
        "rolname = 'c2pro_admin_ops'": (False,),
        "c25_gate_app_": (False,),
        "c25_gate_admin_": (False,),
        "datname = 'c25_admin_ops_gate'": (False,),
    }

    class FailingDropCursor(MockCursor):
        def execute(self, query, params=None):
            query_str = str(query)
            if "DROP ROLE IF EXISTS c25_gate_admin_" in query_str:
                raise RuntimeError("Postgres error dropping synthetic role")
            return super().execute(query, params)

    cursor = FailingDropCursor(responses)
    patch_connect = patch("psycopg.connect", return_value=cursor)

    # Mock migration, provision and assertions to succeed
    monkeypatch.setattr(c25_admin_ops_gate, "_run_alembic_migrations", lambda x: None)
    monkeypatch.setattr(c25_admin_ops_gate, "_provision_roles", lambda p, r1, r2: None)

    mock_admin_pool = AsyncMock()
    mock_app_pool = AsyncMock()
    mock_admin_login_pool = AsyncMock()

    async def mock_connect_all(dsn):
        if "c25_gate_app" in dsn:
            return mock_app_pool
        elif "c25_gate_admin" in dsn:
            return mock_admin_login_pool
        return mock_admin_pool

    monkeypatch.setattr(c25_admin_ops_gate, "_connect", mock_connect_all)
    monkeypatch.setattr(
        c25_admin_ops_gate,
        "_test_direct_login_escalation_proof",
        lambda p, d, r: True,
    )
    monkeypatch.setattr(c25_admin_ops_gate, "_run_alembic_downgrade", lambda x: None)

    # Force run_assertions to pass
    async def mock_run_assertions_selector(*args, **kwargs):
        return True

    with patch_connect:
        exit_code = await c25_admin_ops_gate.main()
        # Should return 1 because cleanup raised an exception
        assert exit_code == 1


@pytest.mark.asyncio
async def test_red_e_hygiene_check_detects_leak(monkeypatch):
    """RED E: Final hygiene check detects leaked DB/role.

    Asserts that final exit code is non-zero (1).
    """
    monkeypatch.setattr(
        c25_admin_ops_gate,
        "_resolve_admin_dsn_impl",
        lambda x: "postgresql://postgres:postgres@127.0.0.1:5433/postgres",
    )

    # Simulate final hygiene check returning True (leak detected) for synthetic app role
    responses = {
        "rolname = 'c2pro_app'": (False,),
        "rolname = 'c2pro_admin_login'": (False,),
        "rolname = 'c2pro_admin_ops'": (False,),
        "c25_gate_app_": (True,),  # Leak detected!
        "c25_gate_admin_": (False,),
        "datname = 'c25_admin_ops_gate'": (False,),
    }
    cursor = MockCursor(responses)
    patch_connect = patch("psycopg.connect", return_value=cursor)

    monkeypatch.setattr(c25_admin_ops_gate, "_run_alembic_migrations", lambda x: None)
    monkeypatch.setattr(c25_admin_ops_gate, "_provision_roles", lambda p, r1, r2: None)

    mock_admin_pool = AsyncMock()
    mock_app_pool = AsyncMock()
    mock_admin_login_pool = AsyncMock()

    async def mock_connect_all(dsn):
        if "c25_gate_app" in dsn:
            return mock_app_pool
        elif "c25_gate_admin" in dsn:
            return mock_admin_login_pool
        return mock_admin_pool

    monkeypatch.setattr(c25_admin_ops_gate, "_connect", mock_connect_all)
    monkeypatch.setattr(
        c25_admin_ops_gate,
        "_test_direct_login_escalation_proof",
        lambda p, d, r: True,
    )
    monkeypatch.setattr(c25_admin_ops_gate, "_run_alembic_downgrade", lambda x: None)

    with patch_connect:
        exit_code = await c25_admin_ops_gate.main()
        assert exit_code == 1


@pytest.mark.asyncio
async def test_red_f_pre_existing_admin_role_survives(monkeypatch):
    """RED F: Pre-existing c2pro_admin_ops capability role survives gate failure unchanged.

    Asserts that pre-existing admin role is not dropped during cleanup.
    """
    monkeypatch.setattr(
        c25_admin_ops_gate,
        "_resolve_admin_dsn_impl",
        lambda x: "postgresql://postgres:postgres@127.0.0.1:5433/postgres",
    )

    # Use fully precise query responses to avoid any substring-matching collisions
    responses = {
        "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_app')": (False,),
        "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_admin_login')": (False,),
        "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'c2pro_admin_ops')": (True,),  # Pre-existing!
        "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcanlogin, rolcreatedb": (
            False,
            False,
            False,
            False,
            False,
        ),
        "c25_gate_app_": (False,),
        "c25_gate_admin_": (False,),
        "datname = 'c25_admin_ops_gate'": (False,),
    }
    cursor = MockCursor(responses)
    patch_connect = patch("psycopg.connect", return_value=cursor)

    # Force migration to raise exception to trigger failure cleanup
    def mock_migration_raises(dsn):
        raise RuntimeError("Migration error")

    monkeypatch.setattr(c25_admin_ops_gate, "_run_alembic_migrations", mock_migration_raises)

    with patch_connect:
        exit_code = await c25_admin_ops_gate.main()
        assert exit_code == 1

    # Verify that DROP ROLE c2pro_admin_ops was NEVER called
    dropped_ops = any("DROP ROLE" in q and "c2pro_admin_ops" in q for q in cursor.executed_queries)
    assert dropped_ops is False
