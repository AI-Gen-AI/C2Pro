"""Regression tests for canonical coherence score-version Alembic migration.

Suite ID: TS-INT-ALEMBIC-COH-VERSION-001
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260526_0001_coherence_score_version_canonical.py"
)


class _RecordingOp:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: str) -> None:
        self.statements.append(statement)


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "coherence_score_version_canonical_migration",
        MIGRATION_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_recreates_enum_without_unsafe_add_value_before_backfill() -> None:
    """The upgrade must not use new enum labels before transaction commit."""
    migration = _load_migration()
    recorder = _RecordingOp()
    migration.op = recorder

    migration.upgrade()

    sql = "\n".join(recorder.statements)
    assert "ADD VALUE 'coherence-v1'" not in sql
    assert "ADD VALUE 'coherence-v2'" not in sql
    assert "ALTER TYPE coherence_score_version RENAME TO coherence_score_version_old" in sql
    assert "CREATE TYPE coherence_score_version AS ENUM ('coherence-v1', 'coherence-v2')" in sql
    assert "CASE" in sql
    assert "WHEN 'v0_flag_based' THEN 'coherence-v1'" in sql
    assert "WHEN 'v1_exponential_decay' THEN 'coherence-v1'" in sql
