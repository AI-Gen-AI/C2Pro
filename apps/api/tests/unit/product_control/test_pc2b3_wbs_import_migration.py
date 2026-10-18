"""TS-UT-PC2B3-MIGRATION-001 -- PC-2b.3 WBS import migration (static guarantees).

Behaviour (upgrade/downgrade, enum downgrade fail-closed, RLS with a NOBYPASSRLS probe, schema
parity with the ORM) runs on a real PostgreSQL in
tests/integration/product_control/test_pc2b3_wbs_import_migration_db.py.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from src.documents.domain.models import DocumentType
from src.wbs.adapters.persistence import import_ddl

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
MIGRATION = API_ROOT / "alembic" / "versions" / "20261007_0003_pc2b3_wbs_import_sources.py"
SUPABASE = REPO_ROOT / "supabase" / "migrations"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MIGRATION.stem, MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sql(statements: tuple[str, ...]) -> str:
    return re.sub(r"\s+", " ", " ".join(statements))


def test_extends_the_single_chain_after_the_current_head() -> None:
    module = _load()
    assert (module.revision, module.down_revision) == ("20261007_0003", "20261007_0002")
    children = [p.name for p in MIGRATION.parent.glob("*.py")
                if 'down_revision = "20261007_0002"' in p.read_text(encoding="utf-8")]
    assert children == [MIGRATION.name]


def test_supabase_mirror_is_rendered_from_the_alembic_statements() -> None:
    module = _load()
    mirror = SUPABASE / module.SUPABASE_MIRROR
    assert mirror.read_text(encoding="utf-8") == module.supabase_sql()
    assert module.SUPABASE_MIRROR > "20261007000200_p0c_recovery_authority_read_grant.sql"
    assert mirror.read_text(encoding="utf-8").index("ADD VALUE IF NOT EXISTS 'wbs'") < mirror.read_text(
        encoding="utf-8").index("CREATE TABLE public.wbs_import_sources")


def test_orm_ddl_is_identical_to_the_migration() -> None:
    module = _load()
    assert import_ddl.FUNCTION_STATEMENTS == module.FUNCTION_STATEMENTS
    assert import_ddl.TRIGGER_STATEMENTS == module.TRIGGER_STATEMENTS
    sql = _sql((module.IMPORT_SOURCES_SQL, *module.CHANGE_SET_LINK_STATEMENTS))
    for check in (import_ddl.IMPORT_STATUS_CHECK, import_ddl.SOURCE_IMPORT_CHECK,
                  import_ddl.IMPORT_REVIEW_FIRST_BASELINE_CHECK):
        assert _sql((check,)) in sql


def test_the_python_enum_and_the_database_enum_agree() -> None:
    module = _load()
    assert DocumentType.WBS.value == "wbs" and "'wbs'" in module.ENUM_STATEMENT


def test_enum_downgrade_fails_closed_and_never_coerces_wbs_to_other() -> None:
    module = _load()
    downgrade = _sql(module.DOWNGRADE_STATEMENTS)
    assert "RAISE EXCEPTION" in module.ENUM_DOWNGRADE_SQL and "WBS source documents exist" in module.ENUM_DOWNGRADE_SQL
    assert "'other'" not in downgrade.lower().replace("'other'::", "")
    assert downgrade.index("DROP TABLE IF EXISTS public.wbs_import_sources") < downgrade.index("document_type_pc2b3_old")


def test_rls_forced_and_data_api_roles_revoked() -> None:
    module = _load()
    sql = _sql(module.UPGRADE_STATEMENTS)
    assert "ALTER TABLE public.wbs_import_sources ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE public.wbs_import_sources FORCE ROW LEVEL SECURITY" in sql
    assert sql.count("CREATE POLICY wbs_import_sources_tenant_") == 4
    assert "REVOKE ALL ON TABLE public.wbs_import_sources FROM" in sql
    assert all(f"REVOKE ALL ON FUNCTION {s} FROM PUBLIC" in sql for s in module.FUNCTION_SIGNATURES)


def test_no_percent_sign_reaches_op_execute() -> None:
    module = _load()
    assert "%" not in "".join((module.ENUM_STATEMENT, *module.UPGRADE_STATEMENTS, *module.DOWNGRADE_STATEMENTS))
