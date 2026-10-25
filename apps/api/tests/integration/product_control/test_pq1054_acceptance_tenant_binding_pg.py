"""#1054: execute the real #1053 + #1054 migration SQL on disposable PostgreSQL.

Each test builds, inside a transaction that is always rolled back, a random
role and schema reproducing the production acceptance-role privilege shape:
11 full-table SELECT grants and one 7-column grant on tenant relations whose
only RLS check is the caller-settable app.current_tenant GUC, plus the nine
project-only tables of #1053. No production DSN is accepted.

Tenant A owns the approved synthetic project P and a second project Q;
tenant B owns project R. Only (A, P) rows may ever be visible to the role.
"""

from __future__ import annotations

import os
from importlib import util
from pathlib import Path
from types import ModuleType
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest

asyncpg = pytest.importorskip("asyncpg")

_DSN = os.environ.get("C2PRO_MIGRATED_TEST_DSN")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires PostgreSQL *_test DSN"),
]

_VERSIONS = Path(__file__).resolve().parents[3] / "alembic" / "versions"
APPROVED_PROJECT = UUID("e7c6031f-cd9e-4642-a5ea-35a0207ceaeb")
TENANT_A, TENANT_B = uuid4(), uuid4()
PROJECT_Q, PROJECT_R = uuid4(), uuid4()
DPO_COLUMNS = ("document_id", "tenant_id", "revision_id", "generation", "stage", "phase", "outcome")
DPO_DENIED = ("owner_token", "fencing_token", "last_error")


def _load(name: str) -> ModuleType:
    path = _VERSIONS / name
    spec = util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M1053 = _load("20261017_0001_pq939_readonly_snapshot_column_grants.py")
M1054 = _load("20261022_0001_pq1054_acceptance_tenant_binding.py")
TENANT_PROJECT = [t for t, mode in M1054.TENANT_RELATIONS.items() if mode == "tenant_project"]


class Fixture:
    def __init__(self) -> None:
        suffix = uuid4().hex[:10]
        self.schema = f"pq1054_{suffix}"
        self.anchor = f"pq1054_sec_{suffix}"
        self.role = f"pq1054_ro_{suffix}"
        self.app = f"pq1054_app_{suffix}"

    def sql(self, statement: str) -> str:
        """Run the migration's own SQL, renaming only fixture identities."""
        return (
            statement.replace("public.", f"{self.schema}.")
            .replace("ns.nspname = 'public'", f"ns.nspname = '{self.schema}'")
            .replace("c2pro_security", self.anchor)
            .replace("c2pro_prod_acceptance_ro", self.role)
        )

    async def run(self, conn, statements: tuple[str, ...]) -> None:
        for statement in statements:
            await conn.execute(self.sql(statement))

    async def build(self, conn) -> None:
        s, role, app = self.schema, self.role, self.app
        await conn.execute(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS INHERIT")
        await conn.execute(f"CREATE ROLE {app} LOGIN NOSUPERUSER NOBYPASSRLS")
        await conn.execute(f"CREATE SCHEMA {s}")
        await conn.execute(f"GRANT USAGE ON SCHEMA {s} TO {role}, {app}")
        guc = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"

        await conn.execute(f"CREATE TABLE {s}.tenants (id uuid PRIMARY KEY, name text)")
        await conn.execute(
            f"CREATE TABLE {s}.projects (id uuid PRIMARY KEY, tenant_id uuid NOT NULL)"
        )
        await conn.execute(
            f"CREATE POLICY tenant_isolation ON {s}.tenants USING (id = {guc})"
        )
        for table in TENANT_PROJECT:
            await conn.execute(
                f"CREATE TABLE {s}.{table} (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
                "tenant_id uuid NOT NULL, project_id uuid NOT NULL, payload text)"
            )
        await conn.execute(
            f"CREATE TABLE {s}.document_processing_operations (document_id uuid NOT NULL, "
            "tenant_id uuid NOT NULL, revision_id uuid, generation int, stage text, "
            "phase text, outcome text, owner_token text, fencing_token bigint, last_error text)"
        )
        for table in ("projects", *TENANT_PROJECT, "document_processing_operations"):
            await conn.execute(
                f"CREATE POLICY tenant_isolation ON {s}.{table} USING (tenant_id = {guc})"
            )
        for table in M1054.TENANT_RELATIONS:
            await conn.execute(f"ALTER TABLE {s}.{table} ENABLE ROW LEVEL SECURITY")
            # Production: these four have RLS enabled but FORCE RLS off.
            if table not in {"document_artifacts", "document_revisions",
                             "project_events", "project_snapshots"}:
                await conn.execute(f"ALTER TABLE {s}.{table} FORCE ROW LEVEL SECURITY")
        for table in M1053.PROJECT_ONLY_TABLES:
            await conn.execute(
                f"CREATE TABLE {s}.{table} (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
                "project_id uuid NOT NULL, payload text)"
            )
            await conn.execute(f"ALTER TABLE {s}.{table} ENABLE ROW LEVEL SECURITY")
            await conn.execute(f"ALTER TABLE {s}.{table} FORCE ROW LEVEL SECURITY")
            await conn.execute(
                f"CREATE POLICY tenant_read ON {s}.{table} USING (project_id IN "
                f"(SELECT p.id FROM {s}.projects p WHERE p.tenant_id = {guc}))"
            )

        # Exactly the catalogued privilege surface: 11 full-table + 7 columns.
        full = ", ".join(
            f"{s}.{t}" for t in M1054.TENANT_RELATIONS if t != "document_processing_operations"
        )
        await conn.execute(f"GRANT SELECT ON {full} TO {role}")
        await conn.execute(
            f"GRANT SELECT ({', '.join(DPO_COLUMNS)}) ON {s}.document_processing_operations TO {role}"
        )
        await conn.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {s} TO {app}")

        await conn.executemany(
            f"INSERT INTO {s}.tenants (id, name) VALUES ($1, $2)",
            [(TENANT_A, "synthetic"), (TENANT_B, "other")],
        )
        scopes = [(TENANT_A, APPROVED_PROJECT), (TENANT_A, PROJECT_Q), (TENANT_B, PROJECT_R)]
        await conn.executemany(
            f"INSERT INTO {s}.projects (id, tenant_id) VALUES ($2, $1)", scopes
        )
        for table in TENANT_PROJECT:
            await conn.executemany(
                f"INSERT INTO {s}.{table} (tenant_id, project_id) VALUES ($1, $2)", scopes
            )
        await conn.execute(
            f"INSERT INTO {s}.document_processing_operations (document_id, tenant_id, owner_token) "
            f"SELECT id, tenant_id, 'secret' FROM {s}.documents"
        )
        for table in M1053.PROJECT_ONLY_TABLES:
            await conn.executemany(
                f"INSERT INTO {s}.{table} (project_id) VALUES ($1)",
                [(APPROVED_PROJECT,), (PROJECT_Q,), (PROJECT_R,)],
            )

    async def upgrade(self, conn) -> None:
        await self.run(conn, M1053.UPGRADE_STATEMENTS)
        await self.run(conn, M1054.UPGRADE_STATEMENTS)

    async def bind(self, conn, tenant: UUID = TENANT_A) -> None:
        await conn.execute(
            f"INSERT INTO {self.anchor}.acceptance_tenant_binding "
            "(role_name, tenant_id, project_id, bound_by) VALUES ($1, $2, $3, 'pg-fixture')",
            self.role, tenant, APPROVED_PROJECT,
        )

    async def visible(self, conn, login: str, guc: str, set_role: str | None = None) -> dict:
        """Rows visible per relation as {approved, other_project_same_tenant, other_tenant}."""
        s = self.schema
        out: dict[str, tuple[int, int, int]] = {}
        async with conn.transaction():
            await conn.execute(f"SET LOCAL ROLE {login}")
            if set_role:
                await conn.execute(f"SET LOCAL ROLE {set_role}")
            await conn.execute("SELECT set_config('app.current_tenant', $1, true)", guc)
            row = await conn.fetchrow(
                f"SELECT count(*) FILTER (WHERE id = $1), 0, count(*) FILTER (WHERE id = $2) "
                f"FROM {s}.tenants", TENANT_A, TENANT_B,
            )
            out["tenants"] = tuple(row)
            row = await conn.fetchrow(
                f"SELECT count(*) FILTER (WHERE id = $1), count(*) FILTER (WHERE id = $2), "
                f"count(*) FILTER (WHERE id = $3) FROM {s}.projects",
                APPROVED_PROJECT, PROJECT_Q, PROJECT_R,
            )
            out["projects"] = tuple(row)
            for table in TENANT_PROJECT:
                row = await conn.fetchrow(
                    f"SELECT count(*) FILTER (WHERE project_id = $1), "
                    f"count(*) FILTER (WHERE project_id = $2), "
                    f"count(*) FILTER (WHERE project_id = $3) FROM {s}.{table}",
                    APPROVED_PROJECT, PROJECT_Q, PROJECT_R,
                )
                out[table] = tuple(row)
            row = await conn.fetchrow(
                f"SELECT count(o.document_id) FILTER (WHERE d.project_id = $1), "
                f"count(o.document_id) FILTER (WHERE d.project_id = $2), "
                f"count(o.document_id) FILTER (WHERE d.project_id = $3) "
                f"FROM {s}.document_processing_operations o "
                f"LEFT JOIN {s}.documents d ON d.id = o.document_id",
                APPROVED_PROJECT, PROJECT_Q, PROJECT_R,
            )
            out["document_processing_operations"] = tuple(row)
            for table in M1053.PROJECT_ONLY_TABLES:
                try:
                    async with conn.transaction():
                        row = await conn.fetchrow(
                            f"SELECT count(id) FILTER (WHERE project_id = $1), "
                            f"count(id) FILTER (WHERE project_id = $2), "
                            f"count(id) FILTER (WHERE project_id = $3) FROM {s}.{table}",
                            APPROVED_PROJECT, PROJECT_Q, PROJECT_R,
                        )
                    out[table] = tuple(row)
                except asyncpg.InsufficientPrivilegeError:
                    out[table] = "denied"
            # SET LOCAL outlives a released savepoint; restore the fixture owner.
            await conn.execute("RESET ROLE")
        return out


async def _connect():
    assert _DSN is not None
    parsed = urlparse(_DSN)
    assert parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    assert parsed.path.rsplit("/", 1)[-1].endswith("_test")
    return await asyncpg.connect(_DSN)


async def _in_rolled_back_fixture(body) -> None:
    conn = await _connect()
    try:
        txn = conn.transaction()
        await txn.start()
        try:
            fx = Fixture()
            await fx.build(conn)
            await body(conn, fx)
        finally:
            # Never commit a synthetic role, schema or anchor row.
            await txn.rollback()
    finally:
        await conn.close()


async def _expect_error(conn, statement: str, *args, match: str) -> None:
    with pytest.raises(asyncpg.PostgresError, match=match):
        async with conn.transaction():
            await conn.execute(statement, *args)


ALL_21 = (*M1054.TENANT_RELATIONS, *M1053.PROJECT_ONLY_TABLES)
APPROVED_ONLY = dict.fromkeys(ALL_21, (1, 0, 0))
NOTHING = dict.fromkeys(ALL_21, (0, 0, 0))


async def test_attack_reproduces_on_the_unbound_privilege_surface() -> None:
    async def body(conn, fx: Fixture) -> None:
        seen = await fx.visible(conn, fx.role, str(TENANT_B))
        for table in M1054.TENANT_RELATIONS:
            assert seen[table][2] == 1, f"{table}: foreign tenant not reproduced"
        for table in M1053.PROJECT_ONLY_TABLES:
            assert seen[table] == "denied"

    await _in_rolled_back_fixture(body)


async def test_binding_confines_role_to_approved_tenant_and_project_on_all_21() -> None:
    async def body(conn, fx: Fixture) -> None:
        await fx.upgrade(conn)
        # Fail closed: no anchor row means nothing is readable, whatever the GUC.
        for guc in (str(TENANT_A), str(TENANT_B), ""):
            assert await fx.visible(conn, fx.role, guc) == NOTHING

        await fx.bind(conn)
        assert await fx.visible(conn, fx.role, str(TENANT_A)) == APPROVED_ONLY
        assert await fx.visible(conn, fx.role, str(TENANT_B)) == NOTHING
        assert await fx.visible(conn, fx.role, "") == NOTHING
        # An unrelated application role keeps its normal tenant RLS behaviour.
        app_b = await fx.visible(conn, fx.app, str(TENANT_B))
        assert all(app_b[t] == (0, 0, 1) for t in ALL_21)

    await _in_rolled_back_fixture(body)


async def test_inheritance_and_set_role_paths_stay_bound() -> None:
    async def body(conn, fx: Fixture) -> None:
        noinherit = f"{fx.role}_ni"
        creator = f"{fx.role}_cr"
        await conn.execute(f"CREATE ROLE {noinherit} LOGIN NOINHERIT IN ROLE {fx.role}")
        # The catalogued single direct member is most likely the creating role:
        # PG16+ grants a CREATEROLE creator ADMIN-only membership (INHERIT and
        # SET FALSE). PG15 (CI) has no such options; model it as NOINHERIT.
        pg16 = await conn.fetchval("SELECT current_setting('server_version_num')::int >= 160000")
        if pg16:
            await conn.execute(f"CREATE ROLE {creator} CREATEROLE NOSUPERUSER")
            await conn.execute(
                f"GRANT {fx.role} TO {creator} WITH ADMIN TRUE, INHERIT FALSE, SET FALSE"
            )
        else:
            await conn.execute(f"CREATE ROLE {creator} CREATEROLE NOSUPERUSER NOINHERIT")
            await conn.execute(f"GRANT {fx.role} TO {creator} WITH ADMIN OPTION")
        await fx.upgrade(conn)
        await fx.bind(conn)

        assert await fx.visible(
            conn, noinherit, str(TENANT_B), set_role=fx.role
        ) == NOTHING
        assert await fx.visible(
            conn, noinherit, str(TENANT_A), set_role=fx.role
        ) == APPROVED_ONLY
        await _expect_error(
            conn, f"SET LOCAL ROLE {noinherit}; SELECT 1 FROM {fx.schema}.tenants",
            match="permission denied",
        )
        if pg16:
            # SET ROLE is authorized against the session user, so check the
            # creator's effective rights as PostgreSQL itself evaluates them.
            rights = await conn.fetchrow(
                "SELECT pg_has_role($1, $2, 'USAGE'), pg_has_role($1, $2, 'SET')",
                creator, fx.role,
            )
            assert tuple(rights) == (False, False)
        else:
            assert await fx.visible(
                conn, creator, str(TENANT_B), set_role=fx.role
            ) == NOTHING

    await _in_rolled_back_fixture(body)


async def test_inheriting_rls_subject_member_aborts_both_migrations() -> None:
    async def body(conn, fx: Fixture) -> None:
        await conn.execute(f"CREATE ROLE {fx.role}_m LOGIN INHERIT IN ROLE {fx.role}")
        with pytest.raises(asyncpg.PostgresError, match="MEMBERSHIP_GUARD_FAILED"):
            async with conn.transaction():
                await fx.run(conn, M1053.UPGRADE_STATEMENTS)
        with pytest.raises(asyncpg.PostgresError, match="PQ1054_READONLY_ROLE_MEMBERSHIP_GUARD_FAILED"):
            async with conn.transaction():
                await fx.run(conn, M1054.UPGRADE_STATEMENTS)

    await _in_rolled_back_fixture(body)


async def test_role_cannot_tamper_with_anchor_policies_or_rls() -> None:
    async def body(conn, fx: Fixture) -> None:
        await fx.upgrade(conn)
        await fx.bind(conn)
        a, s, r = fx.anchor, fx.schema, fx.role
        for statement in (
            f"UPDATE {a}.acceptance_tenant_binding SET tenant_id = '{TENANT_B}'",
            f"DELETE FROM {a}.acceptance_tenant_binding",
            f"INSERT INTO {a}.acceptance_tenant_binding VALUES ('{r}', '{TENANT_B}', "
            f"'{APPROVED_PROJECT}', now(), 'x')",
            f"CREATE TABLE {a}.shadow (id int)",
            f"DROP POLICY pq1054_acceptance_tenant_bound ON {s}.projects",
            f"ALTER TABLE {s}.projects DISABLE ROW LEVEL SECURITY",
            f"INSERT INTO {s}.projects (id, tenant_id) VALUES (gen_random_uuid(), '{TENANT_A}')",
            f"SELECT {', '.join(DPO_DENIED)} FROM {s}.document_processing_operations",
        ):
            await _expect_error(
                conn, f"SET LOCAL ROLE {r}; {statement}",
                match="permission denied|must be owner",
            )
        selectable = await conn.fetchval(
            "SELECT array_agg(attname::text ORDER BY attnum) FROM pg_attribute "
            "WHERE attrelid = $1::regclass AND attnum > 0 "
            "AND has_column_privilege($2, attrelid, attnum, 'SELECT')",
            f"{s}.document_processing_operations", r,
        )
        assert tuple(selectable) == DPO_COLUMNS
        # The anchor itself only accepts the acceptance role and approved project.
        await _expect_error(
            conn,
            f"INSERT INTO {a}.acceptance_tenant_binding VALUES ('other', $1, $2, now(), 'x')",
            TENANT_B, APPROVED_PROJECT, match="check constraint",
        )
        await _expect_error(
            conn,
            f"UPDATE {a}.acceptance_tenant_binding SET project_id = $1",
            PROJECT_Q, match="check constraint",
        )

    await _in_rolled_back_fixture(body)


async def test_post_condition_rejects_unbound_readable_relations() -> None:
    async def body(conn, fx: Fixture) -> None:
        s, r = fx.schema, fx.role
        await conn.execute(f"CREATE TABLE {s}.drift_table (tenant_id uuid)")
        await conn.execute(f"ALTER TABLE {s}.drift_table ENABLE ROW LEVEL SECURITY")
        await conn.execute(f"GRANT SELECT (tenant_id) ON {s}.drift_table TO {r}")
        await fx.run(conn, M1053.UPGRADE_STATEMENTS)
        with pytest.raises(asyncpg.PostgresError, match="UNBOUND_READABLE_RELATIONS.*drift_table"):
            async with conn.transaction():
                await fx.run(conn, M1054.UPGRADE_STATEMENTS)
        await conn.execute(f"DROP TABLE {s}.drift_table")
        await conn.execute(f"CREATE VIEW {s}.drift_view AS SELECT * FROM {s}.projects")
        await conn.execute(f"GRANT SELECT ON {s}.drift_view TO {r}")
        with pytest.raises(asyncpg.PostgresError, match="UNBOUND_READABLE_RELATIONS.*drift_view"):
            async with conn.transaction():
                await fx.run(conn, M1054.UPGRADE_STATEMENTS)

    await _in_rolled_back_fixture(body)


async def test_post_condition_requires_effective_schema_usage() -> None:
    async def body(conn, fx: Fixture) -> None:
        # A Supabase-style extension view may grant SELECT to PUBLIC without
        # granting USAGE on its schema. That is not effective read access.
        hidden_schema = f"{fx.schema}_hidden"
        await conn.execute(f"CREATE SCHEMA {hidden_schema}")
        await conn.execute(
            f"CREATE VIEW {hidden_schema}.stats_view AS SELECT id FROM {fx.schema}.projects"
        )
        await conn.execute(f"GRANT SELECT ON {hidden_schema}.stats_view TO PUBLIC")
        assert not await conn.fetchval(
            "SELECT has_schema_privilege($1, $2, 'USAGE')", fx.role, hidden_schema
        )
        await fx.run(conn, M1053.UPGRADE_STATEMENTS)
        await fx.run(conn, M1054.UPGRADE_STATEMENTS)
        await fx.run(conn, M1054.DOWNGRADE_STATEMENTS)
        # With both rights, this is a genuinely readable unbound view: DENY.
        await conn.execute(f"GRANT USAGE ON SCHEMA {hidden_schema} TO {fx.role}")
        with pytest.raises(asyncpg.PostgresError, match="UNBOUND_READABLE_RELATIONS.*stats_view"):
            async with conn.transaction():
                await fx.run(conn, M1054.UPGRADE_STATEMENTS)

    await _in_rolled_back_fixture(body)


async def test_revoke_public_execute_preserves_named_application_grants() -> None:
    async def body(conn, fx: Fixture) -> None:
        app_function = f"{fx.schema}.is_project_member(uuid)"
        await conn.execute(
            f"CREATE FUNCTION {fx.schema}.is_project_member(uuid) RETURNS boolean "
            "AS 'SELECT false;' LANGUAGE SQL SECURITY DEFINER"
        )
        await conn.execute(f"GRANT EXECUTE ON FUNCTION {app_function} TO {fx.app}")
        assert await conn.fetchval(
            "SELECT has_function_privilege($1, $2, 'EXECUTE')", fx.role, app_function
        )
        await fx.upgrade(conn)
        assert not await conn.fetchval(
            "SELECT has_function_privilege($1, $2, 'EXECUTE')", fx.role, app_function
        )
        assert await conn.fetchval(
            "SELECT has_function_privilege($1, $2, 'EXECUTE')", fx.app, app_function
        )

    await _in_rolled_back_fixture(body)


async def test_post_condition_rejects_a_restrictive_policy_that_is_not_the_binding() -> None:
    async def body(conn, fx: Fixture) -> None:
        s, r = fx.schema, fx.role
        await conn.execute(f"CREATE TABLE {s}.drift_table (tenant_id uuid)")
        await conn.execute(f"ALTER TABLE {s}.drift_table ENABLE ROW LEVEL SECURITY")
        await conn.execute(f"GRANT SELECT ON {s}.drift_table TO {r}")
        # Restrictive and scoped to the role, but binds nothing.
        await conn.execute(
            f"CREATE POLICY lax ON {s}.drift_table AS RESTRICTIVE FOR SELECT TO {r} USING (true)"
        )
        await fx.run(conn, M1053.UPGRADE_STATEMENTS)
        with pytest.raises(asyncpg.PostgresError, match="UNBOUND_READABLE_RELATIONS.*drift_table"):
            async with conn.transaction():
                await fx.run(conn, M1054.UPGRADE_STATEMENTS)

    await _in_rolled_back_fixture(body)


@pytest.mark.parametrize("parent_right", ["select", "owner"])
async def test_role_that_can_set_role_into_a_parent_aborts_migration(parent_right: str) -> None:
    async def body(conn, fx: Fixture) -> None:
        parent = f"{fx.role}_grp"
        await conn.execute(f"CREATE ROLE {parent} NOLOGIN")
        await conn.execute(f"GRANT USAGE ON SCHEMA {fx.schema} TO {parent}")
        if parent_right == "select":
            # As the parent, the policies bound TO the acceptance role do not
            # apply and the caller-set tenant GUC alone decides.
            await conn.execute(f"GRANT SELECT ON {fx.schema}.tenants TO {parent}")
            probe, guc = f"SELECT count(*) FROM {fx.schema}.tenants WHERE id = $1", str(TENANT_B)
        else:
            # An owner bypasses RLS that is not FORCEd: every tenant, no GUC.
            await conn.execute(f"ALTER TABLE {fx.schema}.document_artifacts OWNER TO {parent}")
            probe, guc = (
                f"SELECT count(*) FROM {fx.schema}.document_artifacts WHERE tenant_id = $1", ""
            )
        await conn.execute(f"GRANT {parent} TO {fx.role}")
        # The attack, reproduced before the migration.
        async with conn.transaction():
            await conn.execute(f"SET LOCAL ROLE {fx.role}")
            await conn.execute(f"SET LOCAL ROLE {parent}")
            await conn.execute("SELECT set_config('app.current_tenant', $1, true)", guc)
            assert await conn.fetchval(probe, TENANT_B) == 1
            await conn.execute("RESET ROLE")
        await fx.run(conn, M1053.UPGRADE_STATEMENTS)
        with pytest.raises(
            asyncpg.PostgresError, match=f"PQ1054_READONLY_ROLE_PARENT_ROLE_GUARD_FAILED: {parent}"
        ):
            async with conn.transaction():
                await fx.run(conn, M1054.UPGRADE_STATEMENTS)

    await _in_rolled_back_fixture(body)


async def test_security_definer_executable_by_role_aborts_migration() -> None:
    async def body(conn, fx: Fixture) -> None:
        # Runs with its owner's rights: RLS on tenants never applies inside it.
        await conn.execute(
            f"CREATE FUNCTION {fx.schema}.leak_tenants() RETURNS bigint "
            f"LANGUAGE sql SECURITY DEFINER AS $$ SELECT count(*) FROM {fx.schema}.tenants $$"
        )
        await conn.execute(f"REVOKE ALL ON FUNCTION {fx.schema}.leak_tenants() FROM PUBLIC")
        await fx.run(conn, M1053.UPGRADE_STATEMENTS)
        # Not executable by the role: the binding applies.
        await fx.run(conn, M1054.UPGRADE_STATEMENTS)
        await fx.run(conn, M1054.DOWNGRADE_STATEMENTS)
        await conn.execute(f"GRANT EXECUTE ON FUNCTION {fx.schema}.leak_tenants() TO {fx.role}")
        with pytest.raises(asyncpg.PostgresError, match="PQ1054_SECURITY_DEFINER_EXECUTABLE"):
            async with conn.transaction():
                await fx.run(conn, M1054.UPGRADE_STATEMENTS)

    await _in_rolled_back_fixture(body)


@pytest.mark.parametrize("via_public", [False, True])
async def test_default_privileges_reaching_role_abort_migration(via_public: bool) -> None:
    async def body(conn, fx: Fixture) -> None:
        # A parent role is refused outright (PARENT_ROLE_GUARD), so the
        # indirect path left is a default privilege granted to PUBLIC.
        grantee = "PUBLIC" if via_public else fx.role
        # Every table the app role creates later would be readable unbound.
        await conn.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {fx.app} IN SCHEMA {fx.schema} "
            f"GRANT SELECT ON TABLES TO {grantee}"
        )
        await fx.run(conn, M1053.UPGRADE_STATEMENTS)
        with pytest.raises(asyncpg.PostgresError, match="PQ1054_DEFAULT_PRIVILEGES_WIDEN_ROLE"):
            async with conn.transaction():
                await fx.run(conn, M1054.UPGRADE_STATEMENTS)

    await _in_rolled_back_fixture(body)


async def test_role_owning_a_relation_aborts_migration() -> None:
    async def body(conn, fx: Fixture) -> None:
        await conn.execute(f"CREATE TABLE {fx.schema}.owned (id int)")
        await conn.execute(f"ALTER TABLE {fx.schema}.owned OWNER TO {fx.role}")
        await fx.run(conn, M1053.UPGRADE_STATEMENTS)
        with pytest.raises(asyncpg.PostgresError, match="PQ1054_READONLY_ROLE_OWNS_RELATION"):
            async with conn.transaction():
                await fx.run(conn, M1054.UPGRADE_STATEMENTS)

    await _in_rolled_back_fixture(body)


async def test_downgrade_removes_only_the_binding() -> None:
    async def body(conn, fx: Fixture) -> None:
        await fx.upgrade(conn)
        await fx.bind(conn)
        await fx.run(conn, M1054.DOWNGRADE_STATEMENTS)
        assert await conn.fetchval(
            "SELECT count(*) FROM pg_policy WHERE polname = 'pq1054_acceptance_tenant_bound'"
        ) == 0
        assert await conn.fetchval(
            "SELECT count(*) FROM pg_namespace WHERE nspname = $1", fx.anchor
        ) == 0
        # #1053 policies and grants are untouched by the #1054 downgrade.
        assert await conn.fetchval(
            "SELECT count(*) FROM pg_policy WHERE polname = 'pq939_acceptance_project_readonly' "
            "AND polrelid::regclass::text LIKE $1", f"{fx.schema}.%"
        ) == len(M1053.PROJECT_ONLY_TABLES)
        # Documented consequence: the GUC-only exposure on the 12 relations returns.
        seen = await fx.visible(conn, fx.role, str(TENANT_B))
        assert all(seen[t][2] == 1 for t in M1054.TENANT_RELATIONS)

    await _in_rolled_back_fixture(body)


async def test_missing_binding_column_aborts_migration() -> None:
    async def body(conn, fx: Fixture) -> None:
        await conn.execute(f"ALTER TABLE {fx.schema}.analyses DROP COLUMN project_id")
        await fx.run(conn, M1053.UPGRADE_STATEMENTS)
        with pytest.raises(asyncpg.PostgresError, match="PQ1054_REQUIRED_COLUMN_GUARD_FAILED: analyses"):
            async with conn.transaction():
                await fx.run(conn, M1054.UPGRADE_STATEMENTS)

    await _in_rolled_back_fixture(body)
