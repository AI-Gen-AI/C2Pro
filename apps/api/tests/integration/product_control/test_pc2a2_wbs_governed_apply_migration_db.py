"""PC-2a.2 governed-apply migration on a real PostgreSQL (TS-INT-PC2A2-MIGRATION-001).

Upgrades a disposable database through ``20261006_0001`` (PC-2a.1), seeds the production legacy
shape, then upgrades to ``20261006_0002`` and proves: nothing is seeded or mutated; the
retirement table is RLS ENABLED + FORCED and isolates tenants for a NOBYPASSRLS role (#896
test 55); the live-write guard refuses governed writes once a baseline exists while a project
delete still cascades; the migrated schema equals the ORM schema; the Data API roles get
nothing; downgrade then upgrade round-trips without touching live rows.

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
)
from tests.integration.product_control.test_pc2a1_wbs_governance_migration_db import (
    _connect,
    _connect_maintenance,
    _normalize,
    _seed_governance_rows,
    _tenant_project,
    _wbs_snapshot,
)

asyncpg = pytest.importorskip("asyncpg")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not SCRATCH_DSN, reason="requires C2PRO_MIGRATION_SCRATCH_DSN"),
]

BEFORE = "20261006_0001"
GOVERNANCE_REQUIRED = "WBS_GOVERNANCE_REQUIRED"
_INSERT_LIVE_ROW = (
    "INSERT INTO wbs_nodes (id, project_id, tenant_id, code, name, lft, rgt, depth, sort_order, node_type, metadata, "
    "created_at, updated_at) VALUES ($1, $2, $3, 'NEW-1', 'New', 900, 901, 0, 99, 'activity', '{}'::jsonb, now(), now())"
)
_OWNER = "c2pro_pc2a2_owner_probe"
PC2A2 = "20261006_0002"
TABLE = "wbs_change_set_retirements"
_ROLE = "c2pro_pc2a2_rls_probe"


async def _legacy(conn: Any, tenant: UUID, project: UUID, count: int) -> list[UUID]:
    ids = []
    for index in range(1, count + 1):
        node_id = uuid4()
        await conn.execute(
            "INSERT INTO wbs_nodes (id, project_id, tenant_id, code, name, lft, rgt, depth, sort_order, node_type, "
            "metadata, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, $7, 0, $8, 'activity', '{}'::jsonb, "
            "now(), now())", node_id, project, tenant, f"SCH-{index:03d}", f"Activity {index}", 2 * index - 1, 2 * index, index)
        ids.append(node_id)
    return ids


async def _seed_retirement(conn: Any, tenant: UUID, project: UUID) -> None:
    await conn.execute("SET session_replication_role = replica")
    change_set = uuid4()
    await conn.execute(
        "INSERT INTO wbs_change_sets (id, tenant_id, project_id, origin, entry_mode, title, created_by, "
        "created_by_kind) VALUES ($1, $2, $3, 'manual', 'GENERATE', 'seed', $4, 'human')", change_set, tenant, project, uuid4())
    await conn.execute(
        "INSERT INTO wbs_change_set_retirements (change_set_id, node_id, tenant_id, project_id, disposition, source, "
        "snapshot) VALUES ($1, $2, $3, $4, 'RETIRED_ON_BASELINE', 'legacy', '{}'::jsonb)", change_set, uuid4(), tenant, project)
    await conn.execute("SET session_replication_role = DEFAULT")


async def test_upgrade_round_trips_and_the_live_guard_governs_only_baselined_projects() -> None:
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", BEFORE)
        conn = await _connect()
        try:
            tenant, project = await _tenant_project(conn)
            legacy = await _legacy(conn, tenant, project, 23)
            before = await _wbs_snapshot(conn)
        finally:
            await conn.close()
        _alembic("upgrade", PC2A2)
        conn = await _connect()
        try:
            assert await _wbs_snapshot(conn) == before  # nothing seeded or mutated
            assert await conn.fetchval(f"SELECT count(*) FROM {TABLE}") == 0
            assert tuple(await conn.fetchrow(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = $1::regclass", f"public.{TABLE}")) == (True, True)
            # LEGACY_UNGOVERNED and APPROVED_BASELINE alike: governed live content is closed to every
            # direct writer (even the owner); non-governed attributes stay writable
            for governed in (False, True):
                if governed:  # seeded as the owner with triggers off
                    await _seed_governance_rows(conn, tenant, project)
                for sql, args in (("UPDATE wbs_nodes SET name = 'Renamed' WHERE id = $1", (legacy[0],)),
                                  ("UPDATE wbs_nodes SET code = 'X' WHERE id = $1", (legacy[1],)),
                                  ("DELETE FROM wbs_nodes WHERE id = $1", (legacy[1],)),
                                  (_INSERT_LIVE_ROW, (uuid4(), project, tenant))):
                    with pytest.raises(asyncpg.RestrictViolationError, match=GOVERNANCE_REQUIRED):
                        await conn.execute(sql, *args)
                await conn.execute("UPDATE wbs_nodes SET description = 'kept writable' WHERE id = $1", legacy[1])
            # a forged apply marker (unknown or not SUBMITTED) does not open the gate
            async with conn.transaction():
                await conn.execute("SELECT set_config('c2pro.wbs_governed_apply', $1, true)", str(uuid4()))
                with pytest.raises(asyncpg.RestrictViolationError, match=GOVERNANCE_REQUIRED):
                    async with conn.transaction():
                        await conn.execute("UPDATE wbs_nodes SET name = 'x' WHERE id = $1", legacy[1])
        finally:
            await conn.close()

        _alembic("downgrade", BEFORE)
        conn = await _connect()
        try:
            assert not await conn.fetchval(f"SELECT to_regclass('public.{TABLE}') IS NOT NULL")
            assert not await conn.fetchval("SELECT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_wbs_nodes_governed_write_guard')")
            assert await conn.fetchval("SELECT count(*) FROM wbs_nodes") == 23
        finally:
            await conn.close()
        _alembic("upgrade", PC2A2)
        conn = await _connect()
        try:
            assert await conn.fetchval(f"SELECT to_regclass('public.{TABLE}') IS NOT NULL")
            # deleting a governed project still cascades through the guard...
            await conn.execute("DELETE FROM projects WHERE id = $1", project)
            assert await conn.fetchval("SELECT count(*) FROM wbs_nodes WHERE project_id = $1", project) == 0
            # ...and so does deleting a tenant (tenant -> projects and tenant -> wbs_nodes cascades),
            # leaving no governance history behind
            other_tenant, other_project = await _tenant_project(conn)
            await conn.execute("SET session_replication_role = replica")
            await _legacy(conn, other_tenant, other_project, 3)
            await conn.execute("SET session_replication_role = DEFAULT")
            await _seed_governance_rows(conn, other_tenant, other_project)
            await conn.execute("DELETE FROM tenants WHERE id = $1", other_tenant)
            for table in ("wbs_nodes", "wbs_change_sets", "wbs_change_set_nodes", "wbs_change_set_lineage",
                          TABLE, "wbs_baselines", "wbs_baseline_nodes"):
                assert await conn.fetchval(f"SELECT count(*) FROM {table} WHERE project_id = $1", other_project) == 0, table
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()


async def _submitted_change_set(conn: Any, tenant: UUID, project: UUID) -> UUID:
    """A SUBMITTED first-baseline change set, loaded as the owner with triggers off (seed only)."""
    change_set = uuid4()
    await conn.execute("SET session_replication_role = replica")
    await conn.execute(
        "INSERT INTO wbs_change_sets (id, tenant_id, project_id, origin, entry_mode, title, created_by, created_by_kind, "
        "status, revision, submitted_revision, submitted_digest, submitted_by, submitted_at) VALUES "
        "($1, $2, $3, 'manual', 'GENERATE', 'seed', $4, 'human', 'SUBMITTED', 1, 1, $5, $4, now())",
        change_set, tenant, project, uuid4(), "sha256:" + "1" * 64)
    await conn.execute("SET session_replication_role = DEFAULT")
    return change_set


async def test_the_live_guard_fails_closed_without_the_rows_tenant_context() -> None:
    """#896 hardening P/Q: a missing or foreign ``app.current_tenant`` never reads as "no authority".

    The probe role OWNS the tables without BYPASSRLS. ``wbs_nodes`` (RLS not forced) lets its owner
    through, while the FORCE RLS governance tables hide every row without the row's tenant
    context: precisely where a fail-open guard would conclude "no baseline, write allowed".
    The control proves the same write passes once the real apply state is visible.
    """
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", PC2A2)
        conn = await _connect()
        try:
            tenant, project = await _tenant_project(conn)
            other_tenant, _ = await _tenant_project(conn)
            await conn.execute("SET session_replication_role = replica")
            node = (await _legacy(conn, tenant, project, 1))[0]
            await conn.execute("SET session_replication_role = DEFAULT")
            change_set = await _submitted_change_set(conn, tenant, project)
            await conn.execute(f"DROP ROLE IF EXISTS {_OWNER}")
            await conn.execute(f"CREATE ROLE {_OWNER} NOLOGIN NOBYPASSRLS")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {_OWNER}")
            await conn.execute(f"GRANT SELECT ON projects, tenants TO {_OWNER}")
            for table in ("wbs_nodes", "wbs_change_sets", "wbs_baselines"):
                await conn.execute(f"ALTER TABLE {table} OWNER TO {_OWNER}")
            outcomes: dict[str, str] = {}
            tx = conn.transaction()
            await tx.start()
            try:
                # the in-transaction authority row a real approve = apply inserts first
                await conn.execute("SET LOCAL session_replication_role = replica")
                await conn.execute(
                    "INSERT INTO wbs_baselines (id, tenant_id, project_id, baseline_no, source_change_set_id, "
                    "tree_digest, change_set_digest, node_count, approved_by, approved_by_kind) VALUES "
                    "($1, $2, $3, 1, $4, $5, $5, 1, $6, 'human')",
                    uuid4(), tenant, project, change_set, "sha256:" + "1" * 64, uuid4())
                await conn.execute("SET LOCAL session_replication_role = DEFAULT")
                await conn.execute(f"SET LOCAL ROLE {_OWNER}")
                await conn.execute("SELECT set_config('c2pro.wbs_governed_apply', $1, true)", str(change_set))
                for case, context in (("P missing", ""), ("Q foreign", str(other_tenant)), ("control", str(tenant))):
                    await conn.execute("SELECT set_config('app.current_tenant', $1, true)", context)
                    try:
                        async with conn.transaction():
                            await conn.execute("UPDATE wbs_nodes SET name = 'forged' WHERE id = $1", node)
                        outcomes[case] = "allowed"
                    except asyncpg.PostgresError as exc:
                        outcomes[case] = f"{type(exc).__name__}: {exc}"
            finally:
                await tx.rollback()
            for case in ("P missing", "Q foreign"):
                assert outcomes[case].startswith("RestrictViolationError") and GOVERNANCE_REQUIRED in outcomes[case], outcomes
            assert outcomes["control"] == "allowed", outcomes
            assert await conn.fetchval("SELECT name FROM wbs_nodes WHERE id = $1", node) == "Activity 1"
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()
        conn = await _connect_maintenance()
        try:
            await conn.execute(f"DROP ROLE IF EXISTS {_OWNER}")
        finally:
            await conn.close()


async def test_rls_isolates_the_retirement_table_for_an_ordinary_role() -> None:
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", PC2A2)
        conn = await _connect()
        try:
            tenant_a, project_a = await _tenant_project(conn)
            tenant_b, project_b = await _tenant_project(conn)
            await _seed_retirement(conn, tenant_a, project_a)
            await _seed_retirement(conn, tenant_b, project_b)
            await conn.execute(f"DROP ROLE IF EXISTS {_ROLE}")
            await conn.execute(f"CREATE ROLE {_ROLE} NOLOGIN NOBYPASSRLS")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {_ROLE}")
            await conn.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {TABLE} TO {_ROLE}")
            try:
                async with conn.transaction():
                    await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                    await conn.execute("SELECT set_config('app.current_tenant', $1, true)", str(tenant_a))
                    assert [r["tenant_id"] for r in await conn.fetch(f"SELECT DISTINCT tenant_id FROM {TABLE}")] == [tenant_a]
                    assert await conn.execute(f"DELETE FROM {TABLE} WHERE tenant_id = $1", tenant_b) == "DELETE 0"
                async with conn.transaction():
                    await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                    await conn.execute("SELECT set_config('app.current_tenant', '', true)")
                    assert await conn.fetchval(f"SELECT count(*) FROM {TABLE}") == 0  # fail closed
            finally:
                await conn.execute(f"REVOKE ALL ON {TABLE} FROM {_ROLE}")
                await conn.execute(f"REVOKE ALL ON SCHEMA public FROM {_ROLE}")
                await conn.execute(f"DROP ROLE {_ROLE}")
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()


_SCHEMA_QUERY = """
SELECT 'constraint', c.conrelid::regclass::text, c.conname, pg_get_constraintdef(c.oid)
  FROM pg_constraint c WHERE c.conrelid::regclass::text = $1 AND c.contype <> 'n'
UNION ALL
SELECT 'trigger', t.tgrelid::regclass::text, t.tgname, pg_get_triggerdef(t.oid)
  FROM pg_trigger t WHERE t.tgrelid::regclass::text IN ($1, 'wbs_nodes') AND NOT t.tgisinternal
   AND t.tgname IN ('trg_wbs_change_set_retirements_guard', 'trg_wbs_nodes_governed_write_guard')
UNION ALL
SELECT 'index', i.tablename, i.indexname, i.indexdef FROM pg_indexes i WHERE i.schemaname = 'public' AND i.tablename = $1
UNION ALL
SELECT 'function', p.proname, md5(pg_get_functiondef(p.oid)), ''
  FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace
   AND p.proname IN ('wbs_change_set_retirements_guard', 'wbs_nodes_governed_write_guard')
"""


async def test_migrated_schema_matches_the_orm_schema(db: AsyncSession) -> None:
    orm_rows = (await db.execute(text(_SCHEMA_QUERY.replace("$1", ":t")), {"t": TABLE})).all()
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", PC2A2)
        conn = await _connect()
        try:
            migrated_rows = await conn.fetch(_SCHEMA_QUERY, TABLE)
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()
    assert len(migrated_rows) == len(orm_rows) > 8
    assert _normalize(migrated_rows) == _normalize(orm_rows)


async def test_supabase_api_roles_get_no_access() -> None:
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
            await conn.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO anon, authenticated")
        finally:
            await conn.close()
        _alembic("upgrade", PC2A2)
        conn = await _connect()
        try:
            for role in ("anon", "authenticated"):
                assert not await conn.fetchval(
                    "SELECT has_table_privilege($1, $2, 'SELECT, INSERT, UPDATE, DELETE')", role, f"public.{TABLE}")
                for signature in ("wbs_change_set_retirements_guard()", "wbs_nodes_governed_write_guard()"):
                    assert not await conn.fetchval("SELECT has_function_privilege($1, $2, 'EXECUTE')", role, signature)
            await conn.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated")
            await conn.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon, authenticated")
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
