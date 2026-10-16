"""#939 security contract: snapshot column permissions, without data mutation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
SOURCE = (
    API_ROOT / "alembic" / "versions"
    / "20261017_0001_pq939_readonly_snapshot_column_grants.py"
)
EXPECTED_PROJECT_ONLY_TABLES = {
    "extractions",
    "procurement_bom_items",
    "procurement_budget_items",
    "procurement_wbs_items",
    "bom_revisions",
    "knowledge_graph_edges",
    "knowledge_graph_nodes",
    "procurement_plan_snapshots",
    "stakeholder_alerts",
}


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(SOURCE.stem, SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_single_linear_alembic_chain() -> None:
    m = _migration()
    assert (m.revision, m.down_revision) == ("20261017_0001", "20261008_0001")
    assert m.branch_labels is None


def test_only_nine_canonical_project_only_tables() -> None:
    m = _migration()
    assert len(m.PROJECT_ONLY_TABLES) == 9
    assert set(m.PROJECT_ONLY_TABLES) == EXPECTED_PROJECT_ONLY_TABLES
    assert m.ROLE == "c2pro_prod_acceptance_ro"
    assert m.COLUMNS == ("id", "project_id")
    for table in EXPECTED_PROJECT_ONLY_TABLES:
        assert m.GRANT_SQL.count("('" + table + "')") == 1
        assert m.REVOKE_SQL.count("('" + table + "')") == 1


def test_guards_enforce_login_non_bypass_force_rls_and_project_policy() -> None:
    sql = _migration().GRANT_SQL
    for gate in (
        "rolcanlogin",
        "NOT rolsuper",
        "NOT rolbypassrls",
        "c.relrowsecurity",
        "c.relforcerowsecurity",
        "AND c.relkind IN ('r', 'p')",
        "attname IN ('id', 'project_id')",
        "pg_catalog.pg_policy",
        "app.current_tenant",
        "projects",
        "has_table_privilege(",
        "'INSERT,UPDATE,DELETE'",
    ):
        assert gate in sql
    assert "RAISE EXCEPTION" in sql
    assert "IF NOT EXISTS" in sql


def test_grant_exactly_identity_and_scope_columns_only() -> None:
    m = _migration()
    sql = m.GRANT_SQL
    assert "GRANT SELECT (id, project_id) ON TABLE public.%I TO %I" in sql
    assert sql.count("GRANT SELECT") == 1
    assert "GRANT SELECT ON" not in sql
    assert "GRANT ALL" not in sql
    assert "ALTER ROLE" not in sql
    assert "BYPASSRLS" not in sql  # only lower-case guard, no mutation
    assert "DISABLE ROW LEVEL SECURITY" not in sql
    assert "SECURITY DEFINER" not in sql
    assert "SET ROLE" not in sql
    assert "INSERT INTO" not in sql
    assert "UPDATE public." not in sql
    assert "DELETE FROM" not in sql
    assert "anon" not in sql
    assert "authenticated" not in sql


def test_downgrade_reverses_only_our_grants() -> None:
    m = _migration()
    down = m.REVOKE_SQL
    assert "REVOKE SELECT (id, project_id) ON TABLE public.%I FROM %I" in down
    assert "REVOKE ALL" not in down
    assert "DROP POLICY" not in down
    assert "DROP ROLE" not in down


def test_supabase_mirror_is_exact_alembic_upgrade() -> None:
    m = _migration()
    mirror = REPO_ROOT / "supabase" / "migrations" / m.SUPABASE_MIRROR
    assert mirror.is_file()
    assert mirror.read_text(encoding="utf-8") == m.supabase_sql()


def test_no_payload_grants_or_production_state_proof_claim() -> None:
    m = _migration()
    sql = m.GRANT_SQL
    # An identity/scope digest cannot prove updates to ungranted columns.
    for forbidden in (
        "document_text",
        "payload",
        "snapshot_data",
        "cost",
        "amount",
        "budget_allocated",
        "metadata",
        "secret",
    ):
        assert forbidden not in sql
    assert "pg_catalog.has_table_privilege" in sql
