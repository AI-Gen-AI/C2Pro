"""IR-6: databases built by Alembic can store every ClauseType the application produces.

20260310_0001 creates ``clausetype`` (only IF NOT EXISTS) with a legacy vocabulary that lacks five
``ClauseType`` values. Production kept an older type that has them, but any database built from
the Alembic chain (CI, new environments) rejects milestone / responsibility / quality /
termination / dispute on write.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from src.documents.domain.models import ClauseType

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
MIGRATION = API_ROOT / "alembic" / "versions" / "20260914_0002_ir6_clausetype_application_values.py"
SUPABASE = REPO_ROOT / "supabase" / "migrations" / "20260914000200_ir6_clausetype_application_values.sql"
ALEMBIC_CREATE = API_ROOT / "alembic" / "versions" / "20260310_0001_add_documents_tables.py"
MISSING_ON_FRESH_DATABASES = {"milestone", "responsibility", "quality", "termination", "dispute"}


def _created_labels() -> set[str]:
    source = ALEMBIC_CREATE.read_text(encoding="utf-8")
    match = re.search(r"CREATE TYPE clausetype AS ENUM \(([^)]*)\)", source)
    assert match, "clausetype DDL not found"
    return set(re.findall(r"'([a-z_]+)'", match.group(1)))


def test_the_gap_is_exactly_the_application_values_the_create_lacks() -> None:
    application = {member.value for member in ClauseType}
    assert application - _created_labels() == MISSING_ON_FRESH_DATABASES


def test_migration_adds_every_missing_value_after_the_p0c_indexes() -> None:
    spec = importlib.util.spec_from_file_location("ir6_clausetype", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.revision == "20260914_0002"
    assert module.down_revision == "20260913_0002"
    assert set(module.NEW_VALUES) == MISSING_ON_FRESH_DATABASES
    source = MIGRATION.read_text(encoding="utf-8")
    assert "autocommit_block" in source
    assert "ADD VALUE IF NOT EXISTS" in source


def test_supabase_mirror_adds_the_same_values() -> None:
    sql = SUPABASE.read_text(encoding="utf-8")
    added = set(re.findall(r"ALTER TYPE (?:public\.)?clausetype ADD VALUE IF NOT EXISTS '([a-z_]+)'", sql))
    assert added == MISSING_ON_FRESH_DATABASES
