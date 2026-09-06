"""Shared helpers for the P0-SEC-B fail-closed policy migration tooling.

The mirror generator, the self-verifying gate and the security tests all need
the SQL that the Alembic migration actually emits.  This module captures those
statements in one place so the emitted-SQL contract has exactly one definition.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = (
    REPO_ROOT
    / "apps/api/alembic/versions/20260905_0001_p0_sec_b_fail_closed_policies.py"
)
MIRROR_PATH = (
    REPO_ROOT
    / "supabase/migrations/20260905000100_p0_sec_b_fail_closed_policies.sql"
)


def load_migration() -> types.ModuleType:
    """Import the migration with a stub ``alembic.op`` that records emitted SQL."""
    collected: list[str] = []
    stub = types.ModuleType("alembic")
    stub.op = types.SimpleNamespace(execute=lambda sql: collected.append(str(sql)))  # type: ignore[attr-defined]
    saved = sys.modules.get("alembic")
    sys.modules["alembic"] = stub
    try:
        spec = importlib.util.spec_from_file_location("p0_sec_b_migration", MIGRATION_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {MIGRATION_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    finally:
        if saved is not None:
            sys.modules["alembic"] = saved
        else:
            sys.modules.pop("alembic", None)
    module._collected = collected  # type: ignore[attr-defined]
    return module


def emitted_statements(direction: str) -> list[str]:
    """Return the SQL statements ``direction`` emits, each ending in a semicolon."""
    module = load_migration()
    module._collected.clear()  # type: ignore[attr-defined]
    getattr(module, direction)()
    return [
        statement.strip().rstrip(";") + ";"
        for statement in module._collected  # type: ignore[attr-defined]
    ]


def emitted_sql(direction: str) -> str:
    """Return ``direction``'s emitted SQL as one script."""
    return "\n\n".join(emitted_statements(direction))
