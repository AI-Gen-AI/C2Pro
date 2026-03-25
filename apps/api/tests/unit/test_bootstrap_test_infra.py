"""TS-CI-BACKEND-GUARDS-002

Regression checks for backend test infrastructure bootstrap readiness.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import psycopg


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
