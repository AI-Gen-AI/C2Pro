"""IR-6: every AlertType value exists in the alerttype enum created by the migrations."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from src.shared_kernel.enums import AlertType

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
VERSIONS = API_ROOT / "alembic" / "versions"
MIGRATION = VERSIONS / "20260914_0003_ir6_alerttype_audit_incomplete.py"
SUPABASE = REPO_ROOT / "supabase" / "migrations" / "20260914000300_ir6_alerttype_audit_incomplete.sql"


def _created_labels() -> set[str]:
    source = (VERSIONS / "20260406_0004_add_alert_type_discriminator.py").read_text(encoding="utf-8")
    match = re.search(r"CREATE TYPE alerttype AS ENUM \(([^)]*)\)", source)
    assert match, "alerttype DDL not found"
    return set(re.findall(r"'([a-z_]+)'", match.group(1)))


def _migration_values() -> set[str]:
    spec = importlib.util.spec_from_file_location("ir6_alerttype", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "20260914_0003"
    assert module.down_revision == "20260914_0002"
    return set(module.NEW_VALUES)


def test_migrations_cover_every_application_alert_type() -> None:
    application = {member.value for member in AlertType}
    assert application <= _created_labels() | _migration_values()


def test_migration_adds_only_values_the_application_defines() -> None:
    assert _migration_values() <= {member.value for member in AlertType}
    assert "autocommit_block" in MIGRATION.read_text(encoding="utf-8")


def test_supabase_mirror_adds_the_same_values() -> None:
    sql = SUPABASE.read_text(encoding="utf-8")
    added = set(re.findall(r"ALTER TYPE (?:public\.)?alerttype ADD VALUE IF NOT EXISTS '([a-z_]+)'", sql))
    assert added == _migration_values()
