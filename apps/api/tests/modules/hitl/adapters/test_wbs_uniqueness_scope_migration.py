"""TS-INT-DB-WBS-001

Regression checks for project-scoped procurement WBS uniqueness migration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


class TestWbsUniquenessScopeMigration:
    @staticmethod
    def _migration_path() -> Path:
        repo_root = Path(__file__).resolve().parents[6]
        return (
            repo_root
            / "apps"
            / "api"
            / "alembic"
            / "versions"
            / "20260321_0001_fix_wbs_code_uniqueness_scope.py"
        )

    def test_migration_file_exists(self) -> None:
        assert self._migration_path().exists()

    def test_migration_revision_chain(self) -> None:
        spec = importlib.util.spec_from_file_location("migration", self._migration_path())
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.revision == "20260321_0001"
        assert module.down_revision == "20260320_0001"

    def test_migration_is_idempotent_when_constraints_already_exist(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "uq_procurement_wbs_project_code" in contents
        assert "fk_wbs_parent_per_project" in contents
        assert "IF NOT EXISTS" in contents

    def test_migration_handles_legacy_parent_fk_names_before_dropping_unique_key(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "parent_fk" in contents
        assert "DROP CONSTRAINT IF EXISTS %I" in contents
        assert contents.index("DROP CONSTRAINT IF EXISTS %I") < contents.index(
            "procurement_wbs_items_code_key"
        )

    def test_migration_drops_any_self_referencing_fk_before_dropping_legacy_unique_key(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "conrelid = 'procurement_wbs_items'::regclass" in contents
        assert "confrelid = 'procurement_wbs_items'::regclass" in contents
        assert "contype = 'f'" in contents
        assert contents.index("confrelid = 'procurement_wbs_items'::regclass") < contents.index(
            "procurement_wbs_items_code_key"
        )
