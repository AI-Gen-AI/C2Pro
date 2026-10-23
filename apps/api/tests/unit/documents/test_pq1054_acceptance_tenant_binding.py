"""#1054 security contract: tenant binding of the acceptance read role, without data mutation."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

API_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = API_ROOT.parents[1]
SOURCE = (
    API_ROOT / "alembic" / "versions"
    / "20261022_0001_pq1054_acceptance_tenant_binding.py"
)
# The twelve relations from the 17-Oct metadata-only catalog in #1054.
EXPECTED_TENANT_RELATIONS = {
    "tenants",
    "projects",
    "documents",
    "document_revisions",
    "document_artifacts",
    "clauses",
    "project_events",
    "analyses",
    "document_chunks",
    "project_snapshots",
    "review_items",
    "document_processing_operations",
}


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(SOURCE.stem, SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_single_linear_alembic_chain_after_pq939() -> None:
    m = _migration()
    assert (m.revision, m.down_revision) == ("20261022_0001", "20261017_0001")
    assert m.branch_labels is None
    heads = {
        path.name for path in SOURCE.parent.glob("*.py")
        if f'down_revision = "{m.revision}"' in path.read_text()
    }
    assert heads == set(), "a later migration must chain after 20261022_0001 explicitly"


def test_exactly_the_twelve_catalogued_relations_in_python_and_sql() -> None:
    m = _migration()
    assert set(m.TENANT_RELATIONS) == EXPECTED_TENANT_RELATIONS
    assert m.ROLE == "c2pro_prod_acceptance_ro"
    for table, mode in m.TENANT_RELATIONS.items():
        assert m.BIND_SQL.count(f"('{table}', '{mode}')") == 1
        assert m.UNBIND_SQL.count(f"('{table}')") == 1


def test_only_restrictive_select_policies_and_no_widened_privileges() -> None:
    m = _migration()
    sql = "\n".join(m.UPGRADE_STATEMENTS)
    assert "AS RESTRICTIVE FOR SELECT TO %I" in m.BIND_SQL
    assert "PERMISSIVE" not in sql
    assert not re.search(r"GRANT\s+(ALL|INSERT|UPDATE|DELETE)", sql)
    assert "BYPASSRLS" not in sql.upper().replace("ROLBYPASSRLS", "")
    for forbidden in ("DISABLE ROW LEVEL SECURITY", "NO FORCE ROW LEVEL SECURITY",
                      "ALTER ROLE", "CREATE ROLE", "DROP POLICY", "INSERT INTO",
                      "UPDATE ", "DELETE FROM"):
        assert forbidden not in sql, forbidden
    # The only grants are read access to the anchor itself.
    grants = re.findall(r"GRANT [^']+", m.BIND_SQL)
    assert grants == [
        "GRANT USAGE ON SCHEMA c2pro_security TO c2pro_prod_acceptance_ro",
        "GRANT SELECT ON TABLE c2pro_security.acceptance_tenant_binding ",
    ]


def test_fail_closed_guards_present() -> None:
    sql = _migration().BIND_SQL
    for gate in (
        "rolcanlogin",
        "NOT rolsuper",
        "NOT rolbypassrls",
        "pg_has_role(member.oid, role_oid, 'USAGE')",
        "relowner = role_oid",
        "c.relrowsecurity",
        "PQ1054_REQUIRED_COLUMN_GUARD_FAILED",
        "has_any_column_privilege",
        "c.relkind IN ('v', 'm', 'f')",
        "NOT p.polpermissive",
        "PQ1054_UNBOUND_READABLE_RELATIONS",
    ):
        assert gate in sql, gate


def test_anchor_is_owner_only_and_pinned_to_role_and_approved_project() -> None:
    m = _migration()
    assert m.REVOKE_SCHEMA_SQL == "REVOKE ALL ON SCHEMA c2pro_security FROM PUBLIC"
    assert "FROM PUBLIC" in m.REVOKE_ANCHOR_SQL
    assert "CHECK (role_name = 'c2pro_prod_acceptance_ro')" in m.CREATE_ANCHOR_SQL
    assert f"CHECK (project_id = '{m.APPROVED_PROJECT}'::uuid)" in m.CREATE_ANCHOR_SQL
    # The synthetic tenant id is a protected secret and must never be committed.
    uuids = set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                           SOURCE.read_text()))
    assert uuids == {m.APPROVED_PROJECT}


def test_downgrade_drops_only_this_binding() -> None:
    m = _migration()
    sql = "\n".join(m.DOWNGRADE_STATEMENTS)
    assert "pq1054_acceptance_tenant_bound" in sql
    assert "pq939" not in sql
    assert "REVOKE" not in sql
    assert "CASCADE" not in sql


def test_supabase_mirror_is_byte_exact() -> None:
    m = _migration()
    mirror = REPO_ROOT / "supabase" / "migrations" / m.SUPABASE_MIRROR
    assert mirror.read_text() == m.supabase_sql()
