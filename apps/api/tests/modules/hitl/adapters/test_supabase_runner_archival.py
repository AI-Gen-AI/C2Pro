"""TS-DB-MIG-REC-009

Regression checks for Supabase SQL-runner archival.
"""

from __future__ import annotations

from pathlib import Path


class TestSupabaseRunnerArchival:
    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[6]

    def test_active_supabase_runner_paths_are_removed(self) -> None:
        supabase_dir = self._repo_root() / "infrastructure" / "supabase"

        assert not (supabase_dir / "run_migrations.py").exists()
        assert not (supabase_dir / "rollback_migrations.py").exists()

    def test_active_supabase_supporting_paths_still_exist(self) -> None:
        supabase_dir = self._repo_root() / "infrastructure" / "supabase"

        assert (supabase_dir / "migrations").exists()

    def test_archived_supabase_runner_paths_exist(self) -> None:
        archive_dir = self._repo_root() / "infrastructure" / "supabase" / "archive"

        assert (archive_dir / "migrations").exists()
        assert (archive_dir / "run_migrations.py").exists()
        assert (archive_dir / "rollback_migrations.py").exists()
