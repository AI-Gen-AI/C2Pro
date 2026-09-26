"""Regression tests for the local/CI bootstrap network target boundary.

The canonical bootstrap may start and probe only the repository's fixed local
PostgreSQL/Redis services.  CLI input must never be able to redirect database
connections to an arbitrary network destination.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    scripts_dir = repo_root / "apps" / "api" / "scripts"
    module_path = scripts_dir / "bootstrap_test_infra.py"
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location("bootstrap_test_infra_network_boundary", module_path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--database-url", "postgresql://postgres:postgres@203.0.113.10:5432/evil"),
        ("--admin-url", "postgresql://postgres:postgres@203.0.113.10:5432/postgres"),
        ("--database-name", "redirected_db"),
    ],
)
def test_cli_cannot_override_database_network_target(monkeypatch, flag: str, value: str) -> None:
    """Arbitrary DB destinations must be rejected by argparse before any I/O."""
    module = _load_module()
    monkeypatch.setattr(module, "_ensure_db_ready", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "_ensure_redis_ready", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sys, "argv", ["bootstrap_test_infra.py", flag, value])

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 2


def test_database_connection_targets_are_fixed_loopback_literals() -> None:
    """The strings consumed by DB clients must contain no caller-controlled host."""
    module = _load_module()

    assert getattr(module, "ADMIN_DATABASE_URL", None) == (
        "postgresql://postgres:postgres@127.0.0.1:5433/postgres"
    )
    assert getattr(module, "TEST_DATABASE_URL", None) == (
        "postgresql://postgres:postgres@127.0.0.1:5433/c2pro_test"
    )
    assert getattr(module, "TEST_DATABASE_NAME", None) == "c2pro_test"
