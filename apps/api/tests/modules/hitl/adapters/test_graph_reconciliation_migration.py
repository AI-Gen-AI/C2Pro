"""TS-DB-MIG-REC-004

Regression checks for knowledge graph reconciliation migration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


class TestGraphReconciliationMigration:
    @staticmethod
    def _migration_path() -> Path:
        repo_root = Path(__file__).resolve().parents[6]
        return (
            repo_root
            / "apps"
            / "api"
            / "alembic"
            / "versions"
            / "20260319_0005_reconcile_knowledge_graph_tables.py"
        )

    def test_migration_file_exists(self) -> None:
        assert self._migration_path().exists()

    def test_migration_revision_chain(self) -> None:
        spec = importlib.util.spec_from_file_location("migration", self._migration_path())
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.revision == "20260319_0005"
        assert module.down_revision == "20260319_0004"

    def test_migration_owns_knowledge_graph_tables_and_rls(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "CREATE TABLE IF NOT EXISTS knowledge_graph_nodes" in contents
        assert "CREATE TABLE IF NOT EXISTS knowledge_graph_edges" in contents
        assert "tenant_isolation_kg_nodes" in contents
        assert "tenant_isolation_kg_edges" in contents
        assert "FORCE ROW LEVEL SECURITY" in contents
