"""TS-DB-MIG-REC-005

Regression checks for MCP function reconciliation migration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


class TestMCPFunctionReconciliationMigration:
    @staticmethod
    def _migration_path() -> Path:
        repo_root = Path(__file__).resolve().parents[6]
        return (
            repo_root
            / "apps"
            / "api"
            / "alembic"
            / "versions"
            / "20260319_0006_reconcile_mcp_functions.py"
        )

    def test_migration_file_exists(self) -> None:
        assert self._migration_path().exists()

    def test_migration_revision_chain(self) -> None:
        spec = importlib.util.spec_from_file_location("migration", self._migration_path())
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.revision == "20260319_0006"
        assert module.down_revision == "20260319_0005"

    def test_migration_owns_all_mcp_functions(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "fn_get_clause_by_id" in contents
        assert "fn_get_stakeholder_by_id" in contents
        assert "fn_get_neighbors" in contents
        assert "fn_find_path" in contents
        assert "fn_get_subgraph" in contents
        assert "knowledge_graph_edges" in contents
        assert "knowledge_graph_nodes" in contents

    def test_stakeholder_function_casts_created_at_to_timestamp_without_timezone(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "s.created_at::timestamp without time zone" in contents

    def test_graph_functions_avoid_output_name_ambiguity(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "best_nodes" in contents
        assert "best_edge_types" in contents
        assert "node_depth" in contents
        assert "walk_depth" in contents
        assert "ORDER BY depth, e.id" not in contents
        assert ")::text[] AS path_labels" in contents
