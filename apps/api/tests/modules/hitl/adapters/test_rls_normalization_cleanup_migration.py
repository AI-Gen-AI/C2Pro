"""TS-DB-MIG-REC-006

Regression checks for legacy RLS normalization cleanup migration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


class TestRlsNormalizationCleanupMigration:
    @staticmethod
    def _migration_path() -> Path:
        repo_root = Path(__file__).resolve().parents[6]
        return (
            repo_root
            / "apps"
            / "api"
            / "alembic"
            / "versions"
            / "20260319_0007_normalize_remaining_rls_policies.py"
        )

    def test_migration_file_exists(self) -> None:
        assert self._migration_path().exists()

    def test_migration_revision_chain(self) -> None:
        spec = importlib.util.spec_from_file_location("migration", self._migration_path())
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.revision == "20260319_0007"
        assert module.down_revision == "20260319_0006"

    def test_migration_cleans_legacy_rls_policy_names(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert 'DROP POLICY IF EXISTS "Allow members to access their projects" ON projects;' in contents
        assert 'DROP POLICY IF EXISTS "Allow individual tenant access" ON tenants;' in contents
        assert 'DROP POLICY IF EXISTS tenant_self_only ON tenants;' in contents
        assert 'DROP POLICY IF EXISTS "Allow users to see themselves" ON users;' in contents
        assert "DROP POLICY IF EXISTS tenant_isolation_ai_logs ON ai_usage_logs;" in contents
        assert "DROP POLICY IF EXISTS tenant_isolation_raci ON stakeholder_wbs_raci;" in contents
