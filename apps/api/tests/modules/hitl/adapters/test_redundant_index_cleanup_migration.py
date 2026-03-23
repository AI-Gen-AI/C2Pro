"""TS-DB-MIG-REC-007

Regression checks for redundant index cleanup migration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


class TestRedundantIndexCleanupMigration:
    @staticmethod
    def _migration_path() -> Path:
        repo_root = Path(__file__).resolve().parents[6]
        return (
            repo_root
            / "apps"
            / "api"
            / "alembic"
            / "versions"
            / "20260319_0008_drop_redundant_indexes.py"
        )

    def test_migration_file_exists(self) -> None:
        assert self._migration_path().exists()

    def test_migration_revision_chain(self) -> None:
        spec = importlib.util.spec_from_file_location("migration", self._migration_path())
        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.revision == "20260319_0008"
        assert module.down_revision == "20260319_0007"

    def test_migration_drops_redundant_idx_family(self) -> None:
        contents = self._migration_path().read_text(encoding="utf-8")

        assert "DROP INDEX IF EXISTS public.idx_ai_logs_project;" in contents
        assert "DROP INDEX IF EXISTS public.idx_alerts_analysis;" in contents
        assert "DROP INDEX IF EXISTS public.idx_analyses_project;" in contents
        assert "DROP INDEX IF EXISTS public.idx_audit_resource;" in contents
        assert "DROP INDEX IF EXISTS public.idx_extractions_document;" in contents
        assert "DROP INDEX IF EXISTS public.idx_raci_stakeholder;" in contents
        assert "DROP INDEX IF EXISTS public.idx_stakeholders_project;" in contents
        assert "DROP INDEX IF EXISTS public.idx_users_clerk_user_id;" in contents
