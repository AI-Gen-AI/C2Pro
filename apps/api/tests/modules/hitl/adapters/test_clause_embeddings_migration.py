"""TS-DB-MIG-REC-008

Regression checks for clause embeddings migration chain and ownership.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


class TestClauseEmbeddingsMigration:
    @staticmethod
    def _migration_path() -> Path:
        repo_root = Path(__file__).resolve().parents[6]
        return (
            repo_root
            / "apps"
            / "api"
            / "alembic"
            / "versions"
            / "20260401_0001_add_clause_embeddings.py"
        )

    def test_migration_file_exists(self) -> None:
        assert self._migration_path().exists()

    def test_migration_revision_chain(self) -> None:
        spec = importlib.util.spec_from_file_location("migration", self._migration_path())
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.revision == "20260401_0001"
        assert module.down_revision == "20260321_0002"

    def test_migration_owns_clause_embeddings_objects(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "clause_embeddings" in contents
        assert "vector(1536)" in contents
        assert "find_similar_clauses" in contents
        assert "find_cross_document_pairs" in contents
