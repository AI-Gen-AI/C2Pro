"""#870 recurrence guard for project_snapshots partition RLS."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATION = (
    REPO_ROOT
    / "apps/api/alembic/versions/20261005_0002_project_snapshot_partition_rls.py"
)
MIRROR = REPO_ROOT / "supabase/migrations/20261005000200_project_snapshot_partition_rls.sql"
RETENTION = REPO_ROOT / "apps/api/src/core/tasks/snapshot_retention.py"
MODELS = REPO_ROOT / "apps/api/src/temporal/adapters/persistence/models.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_870", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_repairs_all_attached_snapshot_partitions() -> None:
    module = _load_migration()
    sql = "\n".join(module.UPGRADE_STATEMENTS)
    assert module.revision == "20261005_0002"
    assert module.down_revision == "20261005_0001"
    assert "pg_inherits" in sql
    assert "project_snapshots" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY" not in sql
    assert "%" not in sql
    assert "quote_ident(partition_row.schema_name)" in sql
    assert "quote_ident(partition_row.table_name)" in sql
    assert "JOIN pg_class child_rel" in sql


def test_supabase_mirror_matches_canonical_migration() -> None:
    module = _load_migration()
    assert MIRROR.read_text(encoding="utf-8") == module.supabase_sql()


def test_runtime_partition_creator_enables_rls_on_every_new_leaf() -> None:
    body = RETENTION.read_text(encoding="utf-8")
    assert "ALTER TABLE {partition_name} ENABLE ROW LEVEL SECURITY" in body
    assert "ALTER TABLE project_snapshots_default ENABLE ROW LEVEL SECURITY" in body


def test_orm_bootstrap_partition_creator_enables_rls() -> None:
    body = MODELS.read_text(encoding="utf-8")
    assert "ALTER TABLE project_snapshots_default ENABLE ROW LEVEL SECURITY" in body
    assert "ALTER TABLE %%I ENABLE ROW LEVEL SECURITY" in body


def test_security_downgrade_does_not_reopen_rls() -> None:
    module = _load_migration()
    assert module.downgrade() is None
