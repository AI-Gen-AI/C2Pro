"""PC-2a.1 WBS governance migration on a real PostgreSQL (TS-INT-PC2A1-MIGRATION-001).

Upgrades a disposable database through ``20261005_0003`` (PC-1R), seeds the production
legacy shape (23 flat schedule-derived rows), then upgrades to PC-2a.1 and proves:

* nothing is seeded, approved or reclassified -- the legacy rows only gain the defaults;
* RLS is ENABLED + FORCED on every governance table and isolates tenants for an ordinary
  NOBYPASSRLS role (no tenant context = no rows, no writes);
* downgrade removes the governance schema without touching live WBS rows, and the
  upgrade re-applies;
* the migrated schema and the ORM (create_all) schema are the same: constraints, triggers
  and indexes match one for one, so the integration suites test the production invariants.

Requires ``C2PRO_MIGRATION_SCRATCH_DSN`` (a disposable ``*_test`` database).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.product_control.test_adr025_wbs_legacy_data_migration import (
    SCRATCH_DSN,
    _alembic,
    _drop_scratch_database,
    _recreate_scratch_database,
    _security_snapshot,
)

asyncpg = pytest.importorskip("asyncpg")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not SCRATCH_DSN, reason="requires C2PRO_MIGRATION_SCRATCH_DSN"),
]

BEFORE = "20261005_0003"
PC2A1 = "20261006_0001"
TABLES = ("wbs_change_sets", "wbs_change_set_nodes", "wbs_change_set_lineage", "wbs_baselines", "wbs_baseline_nodes")
_ROLE = "c2pro_pc2a1_rls_probe"


async def _connect() -> Any:
    assert SCRATCH_DSN is not None
    return await asyncpg.connect(SCRATCH_DSN)


async def _tenant_project(conn: Any) -> tuple[UUID, UUID]:
    tenant, project = uuid4(), uuid4()
    await conn.execute("INSERT INTO tenants (id, name, slug, subscription_plan) VALUES ($1, 'pc2a1', $2, 'free')",
                       tenant, f"pc2a1-{tenant}")
    await conn.execute(
        "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency) "
        "VALUES ($1, $2, 'pc2a1', $3, 'construction', 'active', 'EUR')", project, tenant, f"P-{project.hex[:8]}")
    return tenant, project


async def _wbs_snapshot(conn: Any) -> list[tuple[Any, ...]]:
    rows = await conn.fetch(
        "SELECT id, project_id, tenant_id, parent_id, sort_order, code, name, lft, rgt, depth, version, updated_at "
        "FROM wbs_nodes ORDER BY id")
    return [tuple(row) for row in rows]


async def _tables_exist(conn: Any) -> bool:
    return bool(await conn.fetchval("SELECT to_regclass('public.wbs_change_sets') IS NOT NULL"))


async def _seed_governance_rows(conn: Any, tenant: UUID, project: UUID) -> None:
    """One row per governance table, written as the owner with triggers/FKs off (seed only)."""
    change_set, baseline, node = uuid4(), uuid4(), uuid4()
    await conn.execute("SET session_replication_role = replica")
    await conn.execute(
        "INSERT INTO wbs_change_sets (id, tenant_id, project_id, origin, entry_mode, title, created_by, "
        "created_by_kind) VALUES ($1, $2, $3, 'manual', 'GENERATE', 'seed', $4, 'human')",
        change_set, tenant, project, uuid4())
    await conn.execute(
        "INSERT INTO wbs_change_set_nodes (change_set_id, node_id, tenant_id, project_id, sort_order, name, "
        "origin_kind) VALUES ($1, $2, $3, $4, 1, 'seed', 'minted')", change_set, node, tenant, project)
    await conn.execute(
        "INSERT INTO wbs_change_set_lineage (change_set_id, kind, source_node_id, target_node_id, tenant_id, "
        "project_id) VALUES ($1, 'SPLIT', $2, $3, $4, $5)", change_set, uuid4(), node, tenant, project)
    await conn.execute(
        "INSERT INTO wbs_baselines (id, tenant_id, project_id, baseline_no, source_change_set_id, tree_digest, "
        "change_set_digest, node_count, approved_by, approved_by_kind) VALUES "
        "($1, $2, $3, 1, $4, $5, $5, 1, $6, 'human')",
        baseline, tenant, project, change_set, "sha256:" + "0" * 64, uuid4())
    await conn.execute(
        "INSERT INTO wbs_baseline_nodes (baseline_id, node_id, tenant_id, project_id, sort_order, code, name) "
        "VALUES ($1, $2, $3, $4, 1, '1', 'seed')", baseline, node, tenant, project)
    await conn.execute("SET session_replication_role = DEFAULT")


async def test_upgrade_seeds_nothing_and_round_trips_without_touching_live_wbs() -> None:
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", BEFORE)
        conn = await _connect()
        try:
            tenant, project = await _tenant_project(conn)
            for index in range(1, 24):  # production shape: 23 flat schedule-derived rows
                await conn.execute(
                    "INSERT INTO wbs_nodes (id, project_id, tenant_id, code, name, lft, rgt, depth, sort_order, "
                    "node_type, metadata, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, $7, 0, $8, "
                    "'activity', '{}'::jsonb, now(), now())",
                    uuid4(), project, tenant, f"SCH-{index:03d}", f"Activity {index}", 2 * index - 1, 2 * index, index)
            before = await _wbs_snapshot(conn)
            security_before = await _security_snapshot(conn)
        finally:
            await conn.close()

        _alembic("upgrade", PC2A1)
        conn = await _connect()
        try:
            assert await _wbs_snapshot(conn) == before
            assert await _security_snapshot(conn) == security_before  # existing RLS/grants untouched
            governed = await conn.fetch("SELECT DISTINCT control_level, decomposition_kind, dictionary FROM wbs_nodes")
            assert [tuple(row) for row in governed] == [("none", None, None)]
            for table in TABLES:
                assert await conn.fetchval(f"SELECT count(*) FROM {table}") == 0  # nothing seeded or approved
                flags = await conn.fetchrow(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = $1::regclass",
                    f"public.{table}")
                assert tuple(flags) == (True, True)
                assert await conn.fetchval(
                    "SELECT count(*) FROM pg_policies WHERE schemaname = 'public' AND tablename = $1", table) == 4
        finally:
            await conn.close()

        _alembic("downgrade", BEFORE)
        conn = await _connect()
        try:
            assert not await _tables_exist(conn)
            assert await _wbs_snapshot(conn) == before
            assert not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'wbs_nodes' "
                "AND column_name IN ('control_level', 'decomposition_kind', 'dictionary'))")
            assert not await conn.fetchval("SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = "
                                           "'uq_projects_tenant_id')")
        finally:
            await conn.close()

        _alembic("upgrade", "head")
        conn = await _connect()
        try:
            assert await _tables_exist(conn) and await _wbs_snapshot(conn) == before
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()


async def test_rls_isolates_every_governance_table_for_an_ordinary_role() -> None:
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", PC2A1)
        conn = await _connect()
        try:
            tenant_a, project_a = await _tenant_project(conn)
            tenant_b, project_b = await _tenant_project(conn)
            await _seed_governance_rows(conn, tenant_a, project_a)
            await _seed_governance_rows(conn, tenant_b, project_b)
            await conn.execute(f"DROP ROLE IF EXISTS {_ROLE}")
            await conn.execute(f"CREATE ROLE {_ROLE} NOLOGIN NOBYPASSRLS")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {_ROLE}")
            await conn.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(TABLES)} TO {_ROLE}")
            try:
                for table in TABLES:
                    async with conn.transaction():
                        await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                        await conn.execute("SELECT set_config('app.current_tenant', $1, true)", str(tenant_a))
                        tenants = await conn.fetch(f"SELECT DISTINCT tenant_id FROM {table}")
                        assert [row["tenant_id"] for row in tenants] == [tenant_a], table
                        # Writes are refused outside the session tenant (WITH CHECK)...
                        with pytest.raises(asyncpg.PostgresError):
                            async with conn.transaction():
                                await conn.execute(f"UPDATE {table} SET tenant_id = $1", tenant_b)
                        # ...and the other tenant's rows are invisible to UPDATE/DELETE.
                        assert await conn.execute(f"DELETE FROM {table} WHERE tenant_id = $1", tenant_b) == "DELETE 0"
                    async with conn.transaction():
                        await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                        await conn.execute("SELECT set_config('app.current_tenant', '', true)")
                        assert await conn.fetchval(f"SELECT count(*) FROM {table}") == 0, table  # fail closed
            finally:
                await conn.execute(f"REVOKE ALL ON {', '.join(TABLES)} FROM {_ROLE}")
                await conn.execute(f"REVOKE ALL ON SCHEMA public FROM {_ROLE}")
                await conn.execute(f"DROP ROLE {_ROLE}")
            # FORCE RLS applies to the table owner too when it does not hold BYPASSRLS.
            for table in TABLES:
                assert await conn.fetchval(
                    "SELECT relforcerowsecurity FROM pg_class WHERE oid = $1::regclass", f"public.{table}")
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()


_SCHEMA_QUERY = """
SELECT 'constraint' AS kind, c.conrelid::regclass::text AS tbl, c.conname AS name,
       pg_get_constraintdef(c.oid) AS definition
  FROM pg_constraint c
 WHERE c.conrelid::regclass::text = ANY($1::text[]) AND c.contype <> 'n'
UNION ALL
SELECT 'trigger', t.tgrelid::regclass::text, t.tgname, pg_get_triggerdef(t.oid)
  FROM pg_trigger t
 WHERE t.tgrelid::regclass::text = ANY($1::text[]) AND NOT t.tgisinternal
UNION ALL
SELECT 'index', i.tablename, i.indexname, i.indexdef
  FROM pg_indexes i
 WHERE i.schemaname = 'public' AND i.tablename = ANY($1::text[])
"""

_LIVE_COLUMNS_QUERY = """
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
 WHERE conname IN ('ck_wbs_nodes_control_level', 'ck_wbs_nodes_decomposition_kind', 'ck_wbs_nodes_dictionary',
                   'uq_projects_tenant_id')
"""


def _normalize(rows: Any) -> set[tuple[str, ...]]:
    return {tuple(" ".join(str(value).split()) for value in row) for row in rows}


async def test_migrated_schema_matches_the_orm_schema(db: AsyncSession) -> None:
    """The create_all schema used by the integration suites enforces the migrated invariants.

    The ORM mirrors the migrated HEAD: later revisions extend these tables (PC-2b.3 adds the
    IMPORT_REVIEW source link to ``wbs_change_sets``), so the comparison is against head.
    """
    orm_rows = (await db.execute(text(_SCHEMA_QUERY.replace("$1::text[]", ":tables")), {"tables": list(TABLES)})).all()
    orm_live = (await db.execute(text(_LIVE_COLUMNS_QUERY))).all()
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", "head")
        conn = await _connect()
        try:
            migrated_rows = await conn.fetch(_SCHEMA_QUERY, list(TABLES))
            migrated_live = await conn.fetch(_LIVE_COLUMNS_QUERY)
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()
    assert _normalize(migrated_rows) == _normalize(orm_rows)
    assert _normalize(migrated_live) == _normalize(orm_live)


async def test_supabase_api_roles_get_no_table_or_function_access() -> None:
    """Supabase default privileges grant new public tables/functions to anon/authenticated:
    the migration must take them away (guarded, so plain PostgreSQL still migrates)."""
    await _recreate_scratch_database()
    created: list[str] = []
    try:
        _alembic("upgrade", BEFORE)
        conn = await _connect()
        try:
            for role in ("anon", "authenticated"):
                if not await conn.fetchval("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = $1)", role):
                    await conn.execute(f"CREATE ROLE {role} NOLOGIN")
                    created.append(role)
            await conn.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated")
            await conn.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO anon, authenticated")
        finally:
            await conn.close()
        _alembic("upgrade", PC2A1)
        conn = await _connect()
        try:
            for role in ("anon", "authenticated"):
                for table in TABLES:
                    assert not await conn.fetchval(
                        "SELECT has_table_privilege($1, $2, 'SELECT, INSERT, UPDATE, DELETE')", role, f"public.{table}")
                functions = await conn.fetch(
                    "SELECT p.oid::regprocedure::text AS signature FROM pg_proc p "
                    "WHERE p.pronamespace = 'public'::regnamespace AND p.proname LIKE 'wbs\\_%'")
                governance = [f["signature"] for f in functions if f["signature"] != "wbs_nodes_verify_hierarchy_cache()"]
                assert len(governance) == 10
                for signature in governance:
                    assert not await conn.fetchval("SELECT has_function_privilege($1, $2, 'EXECUTE')", role, signature)
            await conn.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated")
            await conn.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon, authenticated")
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()
        if created:
            conn = await _connect_maintenance()
            try:
                for role in created:
                    await conn.execute(f"DROP ROLE IF EXISTS {role}")
            finally:
                await conn.close()


async def _connect_maintenance() -> Any:
    assert SCRATCH_DSN is not None
    return await asyncpg.connect(SCRATCH_DSN.rsplit("/", 1)[0] + "/postgres")
