"""TS-DB-MIG-REC-008

Regression checks for deduplicated Supabase SQL initializer authority.
"""

from __future__ import annotations

from pathlib import Path


class TestSqlInitializerDeduplication:
    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[6]

    def test_canonical_initializer_is_archived_for_reference(self) -> None:
        archived = (
            self._repo_root()
            / "infrastructure"
            / "supabase"
            / "archive"
            / "migrations"
        )

        archived_initializers = sorted(path.name for path in archived.glob("001*_schema.sql"))

        assert archived_initializers == ["001_init_schema.sql", "001_initial_schema.sql"]

    def test_legacy_initializer_is_archived(self) -> None:
        archived = (
            self._repo_root()
            / "infrastructure"
            / "supabase"
            / "archive"
            / "migrations"
            / "001_initial_schema.sql"
        )

        assert archived.exists()
