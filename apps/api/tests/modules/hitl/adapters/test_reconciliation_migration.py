"""TS-DB-MIG-REC-001

Regression checks for the first forward-only reconciliation migration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


class TestReconciliationMigration:
    @staticmethod
    def _migration_path() -> Path:
        repo_root = Path(__file__).resolve().parents[6]
        return (
            repo_root
            / "apps"
            / "api"
            / "alembic"
            / "versions"
            / "20260319_0002_reconcile_clerk_and_mcp_views.py"
        )

    def test_migration_file_exists(self) -> None:
        assert self._migration_path().exists()

    def test_migration_revision_chain(self) -> None:
        spec = importlib.util.spec_from_file_location("migration", self._migration_path())
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.revision == "20260319_0002"
        assert module.down_revision == "20260319_0001"

    def test_migration_owns_reconciliation_surface(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "ADD COLUMN IF NOT EXISTS clerk_org_id" in contents
        assert "CREATE UNIQUE INDEX IF NOT EXISTS ix_tenants_clerk_org_id" in contents
        assert "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_clerk_user_id" in contents
        assert "CREATE OR REPLACE VIEW v_project_summary" in contents
        assert "CREATE OR REPLACE VIEW v_project_alerts" in contents
        assert "CREATE OR REPLACE VIEW v_project_clauses" in contents
        assert "CREATE OR REPLACE VIEW v_project_stakeholders" in contents
        assert "CREATE OR REPLACE VIEW v_project_wbs" in contents
        assert "CREATE OR REPLACE VIEW v_project_bom" in contents
        assert "CREATE OR REPLACE VIEW v_raci_matrix" in contents
        assert "CREATE OR REPLACE VIEW v_coherence_breakdown" in contents
