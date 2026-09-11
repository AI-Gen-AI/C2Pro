"""TS-CI-BACKEND-GUARDS-002

Regression checks for backend test infrastructure bootstrap readiness.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import psycopg
import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    scripts_dir = repo_root / "apps" / "api" / "scripts"
    module_path = scripts_dir / "bootstrap_test_infra.py"
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location("bootstrap_test_infra", module_path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def test_wait_for_database_ready_retries_after_operational_error(monkeypatch) -> None:
    module = _load_module()
    attempts = 0

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_connect(admin_url: str, autocommit: bool = True):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise psycopg.OperationalError("database system is starting up")
        return _Connection()

    monkeypatch.setattr(module.psycopg, "connect", fake_connect)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    module.wait_for_database_ready(
        admin_url="postgresql://postgres:postgres@localhost:5433/postgres",
        timeout_seconds=5,
        retry_interval_seconds=0,
    )

    assert attempts == 3


def test_resolve_db_test_port_accepts_allowed(monkeypatch) -> None:
    """DB port 5433 must be accepted."""
    monkeypatch.setenv("C2PRO_DB_TEST_PORT", "5433")
    module = _load_module()
    assert module.DB_TEST_PORT == 5433


def test_resolve_db_test_port_rejects_arbitrary(monkeypatch) -> None:
    """DB port 5432 must be rejected before any socket call."""
    monkeypatch.setenv("C2PRO_DB_TEST_PORT", "5432")
    with pytest.raises(ValueError, match="not in allowlist"):
        _load_module()


def test_resolve_db_test_port_rejects_common_alternatives(monkeypatch) -> None:
    """DB ports 80, 443, 65535 must be rejected."""
    for port in ("80", "443", "65535", "3306", "1433"):
        monkeypatch.setenv("C2PRO_DB_TEST_PORT", port)
        with pytest.raises(ValueError, match="not in allowlist"):
            _load_module()


def test_resolve_db_test_port_rejects_non_integer(monkeypatch) -> None:
    """Non-integer DB port must be rejected."""
    monkeypatch.setenv("C2PRO_DB_TEST_PORT", "not-a-port")
    with pytest.raises(ValueError, match="must be an integer"):
        _load_module()


def test_resolve_redis_test_port_accepts_ci(monkeypatch) -> None:
    """Redis port 6379 (GitHub Actions) must be accepted."""
    monkeypatch.setenv("C2PRO_REDIS_TEST_PORT", "6379")
    module = _load_module()
    assert module.REDIS_TEST_PORT == 6379


def test_resolve_redis_test_port_accepts_local(monkeypatch) -> None:
    """Redis port 6380 (local docker-compose) must be accepted."""
    monkeypatch.setenv("C2PRO_REDIS_TEST_PORT", "6380")
    module = _load_module()
    assert module.REDIS_TEST_PORT == 6380


def test_resolve_redis_test_port_rejects_arbitrary(monkeypatch) -> None:
    """Redis port 6378 must be rejected before any socket call."""
    monkeypatch.setenv("C2PRO_REDIS_TEST_PORT", "6378")
    with pytest.raises(ValueError, match="not in allowlist"):
        _load_module()


def test_resolve_redis_test_port_rejects_common_alternatives(monkeypatch) -> None:
    """Redis ports 80, 443, 65535, 26379 must be rejected."""
    for port in ("80", "443", "65535", "26379", "6378"):
        monkeypatch.setenv("C2PRO_REDIS_TEST_PORT", port)
        with pytest.raises(ValueError, match="not in allowlist"):
            _load_module()


def test_resolve_redis_test_port_rejects_non_integer(monkeypatch) -> None:
    """Non-integer Redis port must be rejected."""
    monkeypatch.setenv("C2PRO_REDIS_TEST_PORT", "not-a-port")
    with pytest.raises(ValueError, match="must be an integer"):
        _load_module()


def test_bootstrap_exports_test_database_url_and_prevents_redirect(monkeypatch) -> None:
    """Test that bootstrap_test_infra publishes the canonical TEST_DATABASE_URL to os.environ and prevents arbitrary redirection."""
    import os

    module = _load_module()

    # Clear from environment initially
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)

    # Mock bootstrap_checkpoint_schema to check that os.environ has the correct variable
    captured_env_url = None

    async def mock_bootstrap_checkpoint_schema(dsn: str):
        nonlocal captured_env_url
        captured_env_url = os.environ.get("TEST_DATABASE_URL")

    monkeypatch.setattr(module, "bootstrap_checkpoint_schema", mock_bootstrap_checkpoint_schema)

    # Set up basic arguments and call _ensure_db_ready mocks
    class FakeArgs:
        recreate_db = False
        start_services = False
        wait_seconds = 1

    monkeypatch.setattr(module, "is_port_open", lambda port: True)
    monkeypatch.setattr(module, "wait_for_database_ready", lambda url, timeout: None)
    monkeypatch.setattr(module, "ensure_database_exists", lambda url, name: None)

    async def dummy_bootstrap_admin_role(dsn):
        pass

    monkeypatch.setattr(module, "bootstrap_admin_ops_role", dummy_bootstrap_admin_role)
    monkeypatch.setattr(module, "run_alembic_upgrade", lambda api_dir, dsn: None)
    monkeypatch.setattr(module, "assert_head_revision", lambda dsn, api_dir: "20260907_0001")

    # Run DB preflight
    module._ensure_db_ready(FakeArgs(), Path("/fake/repo"), Path("/fake/api"))

    # Assert 1: os.environ["TEST_DATABASE_URL"] was correctly published before checkpoint bootstrap run
    assert captured_env_url == module.TEST_DATABASE_URL

    # Assert 2: Fixed literal constant check. It must match the expected literal, and callers cannot redirect it.
    assert module.TEST_DATABASE_URL == "postgresql://postgres:postgres@127.0.0.1:5433/c2pro_test"
