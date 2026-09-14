"""ADR-025 migrations: static guarantees of the canonical WBS reconciliation.

The data behaviour (legacy mapping, reference integrity, downgrade) is exercised on a real
PostgreSQL by tests/integration/product_control/test_adr025_wbs_legacy_data_migration.py; these
checks pin the properties a reviewer must not lose when editing the SQL.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
VERSIONS = API_ROOT / "alembic" / "versions"
SUPABASE = REPO_ROOT / "supabase" / "migrations"
SCHEMA = VERSIONS / "20260914_0004_adr025_canonical_wbs_schema.py"
DATA = VERSIONS / "20260914_0005_adr025_canonical_wbs_data_and_references.py"


def _load(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sql(*fragments: str) -> str:
    return re.sub(r"\s+", " ", " ".join(fragments))


def test_migrations_extend_the_single_linear_chain_after_the_p0c_and_ir6_revisions() -> None:
    schema, data = _load(SCHEMA), _load(DATA)
    assert (schema.revision, schema.down_revision) == ("20260914_0004", "20260914_0003")
    assert (data.revision, data.down_revision) == ("20260914_0005", "20260914_0004")


@pytest.mark.parametrize("path", [SCHEMA, DATA])
def test_every_statement_is_a_single_statement(path: Path) -> None:
    module = _load(path)
    for statement in (*module.UPGRADE_STATEMENTS, *module.DOWNGRADE_STATEMENTS):
        body = re.sub(r"\$(\w*)\$.*?\$\1\$", "", statement, flags=re.DOTALL)
        assert ";" not in body.strip().rstrip(";"), statement[:120]


@pytest.mark.parametrize("path", [SCHEMA, DATA])
def test_supabase_mirror_is_rendered_from_the_alembic_statements(path: Path) -> None:
    module = _load(path)
    mirror = SUPABASE / module.SUPABASE_MIRROR
    assert mirror.read_text(encoding="utf-8") == module.supabase_sql()


def test_schema_migration_widens_without_truncation_and_creates_no_table() -> None:
    schema = _load(SCHEMA)
    upgrade = _sql(*schema.UPGRADE_STATEMENTS)
    assert "ALTER COLUMN code TYPE varchar," in upgrade
    assert "numeric(18, 2)" in upgrade
    assert "CREATE TABLE" not in upgrade.upper()
    assert set(schema.MAPPING_CLASSES) == {"DIRECT_MAP", "DERIVED_MAP", "AMBIGUOUS", "ORPHAN"}
    downgrade = _sql(*schema.DOWNGRADE_STATEMENTS)
    assert "no data was truncated" in downgrade


def test_data_mapping_classifies_every_legacy_row_and_never_deletes_one() -> None:
    data = _load(DATA)
    mapping = _sql(data.MAP_LEGACY_WBS_SQL)
    for classification in ("DIRECT_MAP", "DERIVED_MAP", "AMBIGUOUS", "ORPHAN"):
        assert f"'{classification}'" in mapping
    assert "rows were left unclassified" in mapping
    assert "was not copied" in mapping
    assert "project_already_has_canonical_wbs" in mapping  # hierarchies are never merged
    assert not re.search(r"\bDELETE\s+FROM\s+public\.(procurement_wbs_items|wbs_items|wbs_nodes)\b", mapping)
    upgrade = _sql(*data.UPGRADE_STATEMENTS)
    assert not re.search(r"\bDELETE\s+FROM\s+public\.", upgrade)
    assert not re.search(r"\bUPDATE\s+public\.(stakeholder_wbs_raci|procurement_bom_items)\b", upgrade)


def test_forced_row_security_is_lifted_and_restored_in_the_same_block() -> None:
    data = _load(DATA)
    for block in (data.MAP_LEGACY_WBS_SQL, data.WRITE_BACK_MANAGED_NODES_SQL, data.REMOVE_WRITTEN_BACK_NODES_SQL):
        sql = _sql(block)
        assert sql.index("NO FORCE ROW LEVEL SECURITY") < sql.rindex("'ALTER TABLE %s FORCE ROW LEVEL SECURITY'")


@pytest.mark.parametrize(
    ("constraint", "on_delete"),
    [("stakeholder_wbs_raci_wbs_item_id_fkey", "CASCADE"), ("procurement_bom_items_wbs_item_id_fkey", "SET NULL")],
)
def test_references_point_at_the_canonical_wbs_not_valid_then_validated(constraint: str, on_delete: str) -> None:
    data = _load(DATA)
    upgrade = _sql(*data.UPGRADE_STATEMENTS)
    assert f"ADD CONSTRAINT {constraint} FOREIGN KEY (wbs_item_id) REFERENCES public.wbs_nodes (id) ON DELETE {on_delete} NOT VALID" in upgrade
    assert f"VALIDATE CONSTRAINT {constraint}" in upgrade
    assert "EXCEPTION WHEN foreign_key_violation THEN RAISE WARNING" in upgrade


def test_mcp_views_read_only_the_canonical_wbs_and_keep_owner_and_grants() -> None:
    data = _load(DATA)
    for view_sql in (data.V_RACI_MATRIX_SQL, data.V_PROJECT_WBS_SQL):
        sql = _sql(view_sql)
        assert "public.wbs_nodes" in sql
        assert not re.search(r"\b(FROM|JOIN)\s+public\.(wbs_items|procurement_wbs_items)\b", sql)
        assert "NULLIF(current_setting('app.current_tenant', true), '')::uuid" in sql
    recreate = _sql(data.RECREATE_VIEW_SQL)
    assert "aclexplode" in recreate and "GRANT" in recreate and "OWNER TO" in recreate
    assert "security_invoker = true" in recreate


def test_legacy_stores_become_read_only_without_blocking_referential_actions() -> None:
    data = _load(DATA)
    function = _sql(data.WRITE_BLOCK_FUNCTION_SQL)
    assert "ADR-025" in function
    assert "pg_trigger_depth() > 1" in function
    assert "SECURITY INVOKER" in function and "SET search_path" in function
    assert "REVOKE ALL ON FUNCTION public.adr025_reject_legacy_wbs_write() FROM PUBLIC" in _sql(
        data.REVOKE_WRITE_BLOCK_FUNCTION_SQL
    )
    triggers = _sql(data.LEGACY_WRITE_BLOCK_TRIGGERS_SQL)
    assert "'procurement_wbs_items', 'wbs_items'" in triggers
    assert "BEFORE INSERT OR UPDATE OR DELETE" in triggers
