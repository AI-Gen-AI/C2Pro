"""TS-DB-MIG-RLS-001

Regression checks for RLS and composite indexes migration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


class TestRlsAndIndexesMigration:
    @staticmethod
    def _migration_path() -> Path:
        repo_root = Path(__file__).resolve().parents[6]
        return (
            repo_root
            / "apps"
            / "api"
            / "alembic"
            / "versions"
            / "20260403_0001_enable_rls_composite_indexes.py"
        )

    def test_migration_file_exists(self) -> None:
        assert self._migration_path().exists()

    def test_migration_revision_chain(self) -> None:
        spec = importlib.util.spec_from_file_location("migration", self._migration_path())
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.revision == "20260403_0001"
        assert module.down_revision == "20260401_0001"

    def test_migration_enables_rls_on_documents(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "ALTER TABLE documents ENABLE ROW LEVEL SECURITY" in contents
        assert "documents_tenant_isolation_select" in contents
        assert "documents_tenant_isolation_insert" in contents
        assert "documents_tenant_isolation_update" in contents
        assert "documents_tenant_isolation_delete" in contents

    def test_migration_enables_rls_on_clauses(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "ALTER TABLE clauses ENABLE ROW LEVEL SECURITY" in contents
        assert "clauses_tenant_isolation_select" in contents
        assert "clauses_tenant_isolation_insert" in contents
        assert "clauses_tenant_isolation_update" in contents
        assert "clauses_tenant_isolation_delete" in contents

    def test_migration_adds_composite_indexes(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "ix_documents_tenant_status" in contents
        assert "ix_documents_tenant_type" in contents
        assert "ix_documents_tenant_created" in contents
        assert "ix_clauses_tenant_project_type" in contents
        assert "ix_clauses_tenant_project_code" in contents
        assert "ix_clauses_tenant_verified" in contents

    def test_migration_enables_pg_stat_statements(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "pg_stat_statements" in contents
        assert '_ensure_extension("pg_stat_statements")' in contents
        assert "CREATE EXTENSION IF NOT EXISTS {extension_name}" in contents
