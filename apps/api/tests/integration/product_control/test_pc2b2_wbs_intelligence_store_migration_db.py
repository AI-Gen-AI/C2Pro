"""PC-2b.2 intelligence store migration on a real PostgreSQL (TS-INT-PC2B2-MIGRATION-001).

Upgrades a disposable database from the PC-2a head to ``20261007_0001`` and proves: nothing is
seeded; the three tables are RLS ENABLED + FORCED and isolate tenants for a NOBYPASSRLS role
(#921 acceptance 37-39), fail closed without a tenant context (41) and refuse a reference into
another tenant (40); the guard functions and constraints equal the ORM schema the integration
suites use; the Data API roles get nothing; downgrade then upgrade round-trips.

Requires ``C2PRO_MIGRATION_SCRATCH_DSN`` (a disposable ``*_test`` database).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.wbs.adapters.persistence import (
    intelligence_models,  # noqa: F401 - registers the ORM tables
)
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
    _tenant_project,
)

asyncpg = pytest.importorskip("asyncpg")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not SCRATCH_DSN, reason="requires C2PRO_MIGRATION_SCRATCH_DSN"),
]

BEFORE = "20261006_0003"
PC2B2 = "20261007_0001"
TABLES = ("wbs_intelligence_runs", "wbs_intelligence_items", "wbs_intelligence_decisions")
FUNCTIONS = ("wbs_intelligence_runs_guard", "wbs_intelligence_items_guard", "wbs_intelligence_decisions_guard")
_ROLE = "c2pro_pc2b2_rls_probe"
_D = "sha256:" + "a" * 64


async def _seed(conn: Any, tenant: UUID, project: UUID) -> dict[str, UUID]:
    """One completed run with a finding and its decision, loaded as the owner with triggers off (seed only)."""
    run, item, decision = uuid4(), uuid4(), uuid4()
    await conn.execute("SET session_replication_role = replica")
    await conn.execute(
        "INSERT INTO wbs_intelligence_runs (id, tenant_id, project_id, mode, execution_type, target_kind, "
        "evidence_set_digest, proposal_contract_version, qualification_vocab_version, orchestration_version, "
        "idempotency_key, status, outcome, qualification, qualification_digest, requested_by, requested_by_kind, "
        "started_at, completed_at) VALUES ($1, $2, $3, 'REVIEW_OPTIMIZE', 'DETERMINISTIC', 'NONE', $4, 'v', 'v', 'v', "
        "$4, 'COMPLETED', 'COMPLETE', '{}'::jsonb, $4, $5, 'human', now(), now())", run, tenant, project, _D, uuid4())
    body = json.dumps({"finding_id": str(item), "dimension": "GRANULARITY", "status": "WARNING",
                       "method": "DETERMINISTIC", "summary": "s"})
    await conn.execute(
        "INSERT INTO wbs_intelligence_items (id, tenant_id, project_id, run_id, kind, ref, ordinal, contract_version, "
        "body, body_digest) VALUES ($1, $2, $3, $4, 'FINDING', 'dq-001', 1, 'wbs-qualification/v1', $5::jsonb, $6)",
        item, tenant, project, run, body, _D)
    await conn.execute(
        "INSERT INTO wbs_intelligence_decisions (id, tenant_id, project_id, run_id, item_id, item_kind, decision, "
        "batch_id, decided_by, decided_by_kind) VALUES ($1, $2, $3, $4, $5, 'FINDING', 'ACKNOWLEDGE', $6, $7, 'human')",
        decision, tenant, project, run, item, uuid4(), uuid4())
    await conn.execute("SET session_replication_role = DEFAULT")
    return {"run": run, "item": item, "decision": decision}


async def test_upgrade_seeds_nothing_and_round_trips() -> None:
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", BEFORE)
        conn = await _connect()
        try:
            tenant, project = await _tenant_project(conn)
        finally:
            await conn.close()
        _alembic("upgrade", PC2B2)
        conn = await _connect()
        try:
            for table in TABLES:
                assert await conn.fetchval(f"SELECT count(*) FROM {table}") == 0  # nothing seeded
                assert tuple(await conn.fetchrow(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = $1::regclass",
                    f"public.{table}")) == (True, True)
            await _seed(conn, tenant, project)
        finally:
            await conn.close()
        _alembic("downgrade", BEFORE)
        conn = await _connect()
        try:
            for table in TABLES:
                assert not await conn.fetchval(f"SELECT to_regclass('public.{table}') IS NOT NULL")
            assert not await conn.fetchval("SELECT count(*) FROM pg_proc WHERE proname = ANY($1::text[])", list(FUNCTIONS))
            assert await conn.fetchval("SELECT count(*) FROM projects WHERE id = $1", project) == 1
            assert await conn.fetchval("SELECT to_regclass('public.wbs_change_sets') IS NOT NULL")
        finally:
            await conn.close()
        _alembic("upgrade", PC2B2)
        conn = await _connect()
        try:
            await _seed(conn, tenant, project)
            await conn.execute("DELETE FROM projects WHERE id = $1", project)  # history leaves with its project only
            for table in TABLES:
                assert await conn.fetchval(f"SELECT count(*) FROM {table} WHERE project_id = $1", project) == 0
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()


async def test_37_to_41_rls_isolates_every_table_for_a_nobypassrls_role() -> None:
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", PC2B2)
        conn = await _connect()
        try:
            tenant_a, project_a = await _tenant_project(conn)
            tenant_b, project_b = await _tenant_project(conn)
            a = await _seed(conn, tenant_a, project_a)
            b = await _seed(conn, tenant_b, project_b)
            await conn.execute(f"DROP ROLE IF EXISTS {_ROLE}")
            await conn.execute(f"CREATE ROLE {_ROLE} NOLOGIN NOBYPASSRLS")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {_ROLE}")
            await conn.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(TABLES)} TO {_ROLE}")
            await conn.execute(f"GRANT SELECT ON projects, users, wbs_change_sets TO {_ROLE}")
            try:
                for table, key in zip(TABLES, ("run", "item", "decision"), strict=True):
                    async with conn.transaction():
                        await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                        await conn.execute("SELECT set_config('app.current_tenant', $1, true)", str(tenant_a))
                        assert [r["id"] for r in await conn.fetch(f"SELECT id FROM {table}")] == [a[key]], table
                        assert await conn.fetchval(f"SELECT count(*) FROM {table} WHERE id = $1", b[key]) == 0
                        assert await conn.execute(f"DELETE FROM {table} WHERE tenant_id = $1", tenant_b) == "DELETE 0"
                    async with conn.transaction():  # 41: no tenant context -> nothing, fail closed
                        await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                        await conn.execute("SELECT set_config('app.current_tenant', '', true)")
                        assert await conn.fetchval(f"SELECT count(*) FROM {table}") == 0, table
                # 40: tenant A cannot write a row of tenant B (RLS WITH CHECK)...
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    async with conn.transaction():
                        await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                        await conn.execute("SELECT set_config('app.current_tenant', $1, true)", str(tenant_a))
                        await conn.execute(
                            "INSERT INTO wbs_intelligence_runs (id, tenant_id, project_id, mode, execution_type, "
                            "target_kind, evidence_set_digest, proposal_contract_version, qualification_vocab_version, "
                            "orchestration_version, idempotency_key, status, requested_by, requested_by_kind, "
                            "started_at) VALUES ($1, $2, $3, 'REVIEW_OPTIMIZE', 'DETERMINISTIC', 'NONE', $4, 'v', 'v', "
                            "'v', $4, 'RUNNING', $5, 'service', now())", uuid4(), tenant_b, project_b, _D, uuid4())
                # ...nor attach an item to B's run, whatever tenant it claims (B's run is invisible to A)
                for claimed_tenant, claimed_project in ((tenant_b, project_b), (tenant_a, project_a)):
                    with pytest.raises((asyncpg.RestrictViolationError, asyncpg.ForeignKeyViolationError,
                                        asyncpg.InsufficientPrivilegeError)):
                        async with conn.transaction():
                            await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                            await conn.execute("SELECT set_config('app.current_tenant', $1, true)", str(tenant_a))
                            await conn.execute(
                                "INSERT INTO wbs_intelligence_items (id, tenant_id, project_id, run_id, kind, ref, "
                                "ordinal, contract_version, body, body_digest) VALUES ($1, $2, $3, $4, 'FINDING', 'x', "
                                "9, 'wbs-qualification/v1', '{}'::jsonb, $5)",
                                uuid4(), claimed_tenant, claimed_project, b["run"], _D)
            finally:
                await conn.execute(f"REVOKE ALL ON {', '.join(TABLES)}, projects, users, wbs_change_sets FROM {_ROLE}")
                await conn.execute(f"REVOKE ALL ON SCHEMA public FROM {_ROLE}")
                await conn.execute(f"DROP ROLE {_ROLE}")
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
UNION ALL
SELECT 'function', p.proname, md5(pg_get_functiondef(p.oid)), ''
  FROM pg_proc p
 WHERE p.pronamespace = 'public'::regnamespace AND p.proname = ANY($2::text[])
"""


async def test_migrated_schema_matches_the_orm_schema(db: AsyncSession) -> None:
    orm_rows = (await db.execute(text(_SCHEMA_QUERY.replace("$1::text[]", ":tables").replace("$2::text[]", ":functions")),
                                 {"tables": list(TABLES), "functions": list(FUNCTIONS)})).all()
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", PC2B2)
        conn = await _connect()
        try:
            migrated_rows = await conn.fetch(_SCHEMA_QUERY, list(TABLES), list(FUNCTIONS))
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()
    assert len(migrated_rows) == len(orm_rows) > 30
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
        _alembic("upgrade", PC2B2)
        conn = await _connect()
        try:
            for role in ("anon", "authenticated"):
                for table in TABLES:
                    assert not await conn.fetchval(
                        "SELECT has_table_privilege($1, $2, 'SELECT, INSERT, UPDATE, DELETE')", role, f"public.{table}")
                for function in FUNCTIONS:
                    assert not await conn.fetchval("SELECT has_function_privilege($1, $2, 'EXECUTE')", role,
                                                   f"public.{function}()")
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
