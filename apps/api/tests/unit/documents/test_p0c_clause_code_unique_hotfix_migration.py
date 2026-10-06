"""#909: production legacy clause-code uniqueness hotfix migration contract."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
MIGRATION = API_ROOT / "alembic" / "versions" / "20261006_0003_drop_legacy_clause_code_unique.py"
SUPABASE = REPO_ROOT / "supabase" / "migrations"
LEGACY_CONSTRAINT = "clauses_project_document_code_unique"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MIGRATION.stem, MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sql(*fragments: str) -> str:
    return re.sub(r"\s+", " ", " ".join(fragments)).strip()


def test_extends_current_single_chain() -> None:
    module = _load()
    assert (module.revision, module.down_revision) == ("20261006_0003", "20261006_0002")


def test_upgrade_drops_only_the_legacy_clause_code_uniqueness() -> None:
    module = _load()
    upgrade = _sql(*module.UPGRADE_STATEMENTS)
    assert (
        "ALTER TABLE public.clauses DROP CONSTRAINT IF EXISTS "
        + LEGACY_CONSTRAINT
    ) in upgrade
    upper = f" {upgrade.upper()} "
    assert " ADD CONSTRAINT " not in upper
    assert " UNIQUE (" not in upper
    assert "ROW LEVEL SECURITY" not in upgrade.upper()
    assert "POLICY" not in upgrade.upper()


def test_downgrade_is_fail_closed_after_valid_multi_revision_duplicates() -> None:
    module = _load()
    downgrade = _sql(*module.DOWNGRADE_STATEMENTS)
    assert "GROUP BY project_id, document_id, clause_code" in downgrade
    assert "HAVING count(*) > 1" in downgrade
    assert "RAISE EXCEPTION" in downgrade
    assert LEGACY_CONSTRAINT in downgrade
    assert downgrade.index("RAISE EXCEPTION") < downgrade.index(
        f"ADD CONSTRAINT {LEGACY_CONSTRAINT}"
    )


def test_every_statement_is_asyncpg_single_statement() -> None:
    module = _load()
    for statement in (*module.UPGRADE_STATEMENTS, *module.DOWNGRADE_STATEMENTS):
        body = re.sub(r"\$(\w*)\$.*?\$\1\$", "", statement, flags=re.DOTALL)
        assert ";" not in body.strip().rstrip(";"), statement[:160]


def test_supabase_mirror_is_rendered_from_the_same_upgrade_statements() -> None:
    module = _load()
    mirror = SUPABASE / module.SUPABASE_MIRROR
    assert mirror.read_text(encoding="utf-8") == module.supabase_sql()
    assert module.SUPABASE_MIRROR == "20261006000300_drop_legacy_clause_code_unique.sql"
