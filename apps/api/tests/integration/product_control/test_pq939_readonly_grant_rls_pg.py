"""#939: execute the real grant migration against disposable PostgreSQL fixtures.

A transaction on the dedicated *_test database creates a random role, schema,
nine project-only tables and synthetic tenants. No production DSN is accepted.
The Alembic migration SQL is exercised (with only schema/role identifiers
substituted to isolate fixtures), then its real downgrade SQL is verified.
"""

from __future__ import annotations

import os
from importlib import util
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest

asyncpg = pytest.importorskip("asyncpg")

_DSN = os.environ.get("C2PRO_MIGRATED_TEST_DSN")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires migrated PostgreSQL *_test DSN"),
]

_API = Path(__file__).resolve().parents[3]
_MIGRATION = (
    _API / "alembic" / "versions"
    / "20261017_0001_pq939_readonly_snapshot_column_grants.py"
)
APPROVED_PROJECT = UUID("e7c6031f-cd9e-4642-a5ea-35a0207ceaeb")


def _migration():
    spec = util.spec_from_file_location("pq939_rls_real_sql", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture_sql(sql: str, schema: str, role: str) -> str:
    """Retain SQL bodies, replacing ONLY isolated fixture identities."""
    assert "public." in sql
    assert "c2pro_prod_acceptance_ro" in sql
    return (
        sql.replace("public.", f"{schema}.")
        .replace("ns.nspname = 'public'", f"ns.nspname = '{schema}'")
        .replace("c2pro_prod_acceptance_ro", role)
    )


async def test_migration_enforces_restrictive_rls_for_two_synthetic_tenants() -> None:
    """Actual PostgreSQL: approved row YES; same/other-tenant rows NO.

    Even a malicious caller changing the tenant GUC cannot cause the newly
    granted role to see a project other than the pinned synthetic one.
    """
    assert _DSN is not None
    parsed = urlparse(_DSN)
    assert parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    assert parsed.path.rsplit("/", 1)[-1].endswith("_test")

    suffix = uuid4().hex[:12]
    schema = f"pq939_rls_{suffix}"
    role = f"pq939_ro_{suffix}"
    tenant_a, tenant_b = uuid4(), uuid4()
    project_b, other_project_a = uuid4(), uuid4()
    m = _migration()

    conn = await asyncpg.connect(_DSN)
    try:
        # NEVER auto-commit a successful synthetic role/schema fixture.
        # An asyncpg transaction context commits on normal exit, so rollback
        # explicitly even when every assertion succeeds.
        txn = conn.transaction()
        await txn.start()
        try:
            await conn.execute(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS")
            await conn.execute(f"CREATE SCHEMA {schema}")
            await conn.execute(f"GRANT USAGE ON SCHEMA {schema} TO {role}")
            await conn.execute(
                f"CREATE TABLE {schema}.projects (id uuid PRIMARY KEY, tenant_id uuid NOT NULL)"
            )
            await conn.executemany(
                f"INSERT INTO {schema}.projects (id, tenant_id) VALUES ($1, $2)",
                [
                    (APPROVED_PROJECT, tenant_a),
                    (project_b, tenant_b),
                    (other_project_a, tenant_a),
                ],
            )
            await conn.execute(f"GRANT SELECT ON {schema}.projects TO {role}")

            for table in m.PROJECT_ONLY_TABLES:
                await conn.execute(
                    f"CREATE TABLE {schema}.{table} "
                    "(id uuid PRIMARY KEY, project_id uuid NOT NULL, payload text)"
                )
                await conn.execute(
                    f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY"
                )
                await conn.execute(
                    f"ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY"
                )
                await conn.execute(
                    f"CREATE POLICY {table}_tenant_read ON {schema}.{table} "
                    "FOR SELECT USING (project_id IN "
                    f"(SELECT p.id FROM {schema}.projects p WHERE p.tenant_id = "
                    "NULLIF(current_setting('app.current_tenant', true), '')::uuid))"
                )
                await conn.executemany(
                    f"INSERT INTO {schema}.{table} (id, project_id, payload) "
                    "VALUES ($1, $2, $3)",
                    [
                        (uuid4(), APPROVED_PROJECT, "approved synthetic"),
                        (uuid4(), project_b, "foreign synthetic"),
                        (uuid4(), other_project_a, "same tenant other project"),
                    ],
                )

            # Exercise the real migration logic, with only fixture namespace
            # and login replacements; no reimplementation of policy clauses.
            await conn.execute(_fixture_sql(m.GRANT_SQL, schema, role))

            policies = await conn.fetch(
                "SELECT c.relname AS table_name, p.polpermissive, p.polcmd::text AS command, "
                "p.polroles, pg_get_expr(p.polqual,p.polrelid) AS expression "
                "FROM pg_catalog.pg_policy p "
                "JOIN pg_catalog.pg_class c ON c.oid=p.polrelid "
                "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname=$1 AND p.polname=$2",
                schema,
                "pq939_acceptance_project_readonly",
            )
            assert {r["table_name"] for r in policies} == set(m.PROJECT_ONLY_TABLES)
            assert all(r["polpermissive"] is False for r in policies)
            assert all(r["command"] == "r" for r in policies)
            assert all(str(APPROVED_PROJECT) in r["expression"] for r in policies)

            await conn.execute(f"SET LOCAL ROLE {role}")
            for tenant_guc, expected in ((tenant_a, 1), (tenant_b, 0)):
                await conn.execute(
                    "SELECT set_config('app.current_tenant', $1, true)",
                    str(tenant_guc),
                )
                for table in m.PROJECT_ONLY_TABLES:
                    result = await conn.fetchval(f"SELECT count(*) FROM {schema}.{table}")
                    assert result == expected, (table, tenant_guc)

                    assert await conn.fetchval(
                        "SELECT has_column_privilege(current_user, "
                        f"'{schema}.{table}', 'project_id', 'SELECT')"
                    ) is True
                    assert await conn.fetchval(
                        "SELECT has_column_privilege(current_user, "
                        f"'{schema}.{table}', 'payload', 'SELECT')"
                    ) is False
                    assert await conn.fetchval(
                        "SELECT has_table_privilege(current_user, "
                        f"'{schema}.{table}', 'INSERT,UPDATE,DELETE')"
                    ) is False

            await conn.execute("RESET ROLE")
            await conn.execute(_fixture_sql(m.REVOKE_SQL, schema, role))
            assert await conn.fetchval(
                "SELECT count(*) FROM pg_catalog.pg_policies "
                "WHERE schemaname=$1 AND policyname=$2",
                schema,
                "pq939_acceptance_project_readonly",
            ) == 0
            for table in m.PROJECT_ONLY_TABLES:
                assert await conn.fetchval(
                    "SELECT has_column_privilege($1, "
                    f"'{schema}.{table}', 'id', 'SELECT')", role
                ) is False
                assert await conn.fetchval(
                    "SELECT has_column_privilege($1, "
                    f"'{schema}.{table}', 'project_id', 'SELECT')", role
                ) is False
        finally:
            await txn.rollback()
    finally:
        await conn.close()


async def test_migration_refuses_role_inherited_by_another_rls_subject_role() -> None:
    """A RESTRICTIVE policy TO the role would silently confine its members."""
    assert _DSN is not None
    parsed = urlparse(_DSN)
    assert parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    assert parsed.path.rsplit("/", 1)[-1].endswith("_test")

    suffix = uuid4().hex[:12]
    schema = f"pq939_mbr_{suffix}"
    role = f"pq939_ro_{suffix}"
    member = f"pq939_member_{suffix}"
    m = _migration()

    conn = await asyncpg.connect(_DSN)
    try:
        txn = conn.transaction()
        await txn.start()
        try:
            await conn.execute(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS")
            await conn.execute(f"CREATE ROLE {member} LOGIN NOSUPERUSER NOBYPASSRLS")
            await conn.execute(f"CREATE SCHEMA {schema}")
            await conn.execute(
                f"CREATE TABLE {schema}.projects (id uuid PRIMARY KEY, tenant_id uuid NOT NULL)"
            )
            for table in m.PROJECT_ONLY_TABLES:
                await conn.execute(
                    f"CREATE TABLE {schema}.{table} (id uuid PRIMARY KEY, project_id uuid NOT NULL)"
                )
                await conn.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
                await conn.execute(f"ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY")
                await conn.execute(
                    f"CREATE POLICY {table}_tenant_read ON {schema}.{table} "
                    "FOR SELECT USING (project_id IN "
                    f"(SELECT p.id FROM {schema}.projects p WHERE p.tenant_id = "
                    "NULLIF(current_setting('app.current_tenant', true), '')::uuid))"
                )

            # NOINHERIT membership grants no privileges: still allowed. PG16+
            # fixes a membership's INHERIT option at GRANT time (from the
            # member's attribute), so set NOINHERIT before granting.
            await conn.execute(f"ALTER ROLE {member} NOINHERIT")
            await conn.execute(f"GRANT {role} TO {member}")
            await conn.execute("SAVEPOINT noinherit")
            await conn.execute(_fixture_sql(m.GRANT_SQL, schema, role))
            await conn.execute("ROLLBACK TO SAVEPOINT noinherit")

            if await conn.fetchval(
                "SELECT current_setting('server_version_num')::int >= 160000"
            ):
                await conn.execute(f"GRANT {role} TO {member} WITH INHERIT TRUE")
            else:
                await conn.execute(f"ALTER ROLE {member} INHERIT")
            with pytest.raises(
                asyncpg.RaiseError, match="PQ939_READONLY_ROLE_MEMBERSHIP_GUARD_FAILED"
            ):
                await conn.execute(_fixture_sql(m.GRANT_SQL, schema, role))
        finally:
            await txn.rollback()
    finally:
        await conn.close()
