"""TS-DB-MIG-REC-002

Regression checks for operational-table reconciliation migration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


class TestOperationalReconciliationMigration:
    @staticmethod
    def _migration_path() -> Path:
        repo_root = Path(__file__).resolve().parents[6]
        return (
            repo_root
            / "apps"
            / "api"
            / "alembic"
            / "versions"
            / "20260319_0003_reconcile_audit_and_ai_usage_logs.py"
        )

    def test_migration_file_exists(self) -> None:
        assert self._migration_path().exists()

    def test_migration_revision_chain(self) -> None:
        spec = importlib.util.spec_from_file_location("migration", self._migration_path())
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.revision == "20260319_0003"
        assert module.down_revision == "20260319_0002"

    def test_migration_owns_operational_tables_and_rls(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "CREATE TABLE IF NOT EXISTS ai_usage_logs" in contents
        assert "CREATE TABLE IF NOT EXISTS audit_logs" in contents
        assert "ENABLE ROW LEVEL SECURITY" in contents
        assert "FORCE ROW LEVEL SECURITY" in contents
        assert "tenant_isolation_ai_usage_logs" in contents
        assert "tenant_isolation_audit_logs" in contents

    def test_migration_reconciles_existing_audit_logs_columns(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "ALTER TABLE audit_logs" in contents
        assert "ADD COLUMN IF NOT EXISTS changes JSONB" in contents
        assert "ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()" in contents
