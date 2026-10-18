"""PC-2b.3 WBS import migration on a real PostgreSQL (TS-INT-PC2B3-MIGRATION-001).

Upgrades a disposable database to ``20261007_0003`` and proves: nothing is seeded; ``wbs`` joins
``document_type``; ``wbs_import_sources`` is RLS ENABLED + FORCED and isolates tenants for a
NOBYPASSRLS role, fails closed without a tenant context and refuses a write into another tenant
(#922 acceptance 53-57); the Data API roles get nothing; the guards and constraints equal the ORM
schema the integration suites use; downgrade removes ``wbs`` only when no WBS document exists and
otherwise FAILS CLOSED (never ``wbs -> other``); upgrade/downgrade/upgrade round-trips.

Requires ``C2PRO_MIGRATION_SCRATCH_DSN`` (a disposable ``*_test`` database).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.wbs.adapters.persistence import import_models  # noqa: F401 - registers the ORM table
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

BEFORE = "20261007_0002"
PC2B3 = "20261007_0003"
TABLES = ("wbs_import_sources",)
FUNCTIONS = ("wbs_import_sources_guard", "wbs_change_sets_source_import_guard")
_ROLE = "c2pro_pc2b3_rls_probe"
_D = "sha256:" + "a" * 64


async def _labels(conn: Any) -> list[str]:
    rows = await conn.fetch("SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                            "WHERE t.typname = 'document_type' ORDER BY e.enumsortorder")
    return [row["enumlabel"] for row in rows]


async def _wbs_document(conn: Any, tenant: UUID, project: UUID) -> tuple[UUID, UUID, str]:
    document, revision = uuid4(), uuid4()
    blob = hashlib.sha256(document.bytes).hexdigest()
    await conn.execute("INSERT INTO documents (id, tenant_id, project_id, document_type, filename) "
                       "VALUES ($1, $2, $3, 'wbs', 'wbs.csv')", document, tenant, project)
    await conn.execute("INSERT INTO document_revisions (revision_id, document_id, project_id, tenant_id, rev_no, "
                       "blob_hash, blob_key, valid_from) VALUES ($1, $2, $3, $4, 1, $5, 'k.csv', now())",
                       revision, document, project, tenant, blob)
    return document, revision, blob


async def _seed_import(conn: Any, tenant: UUID, project: UUID) -> UUID:
    """One import source loaded as the owner with triggers off (seed only)."""
    document, revision, blob = await _wbs_document(conn, tenant, project)
    source = uuid4()
    await conn.execute("SET session_replication_role = replica")
    await conn.execute(
        "INSERT INTO wbs_import_sources (id, tenant_id, project_id, document_id, revision_id, blob_hash, format, "
        "parser_id, parser_version, parse_config, parse_config_digest, import_key, snapshot_schema_version, snapshot, "
        "snapshot_digest, diagnostics, row_count, warning_count, blocking_count, status, created_by, created_by_kind) "
        "VALUES ($1, $2, $3, $4, $5, $6, 'csv', 'wbs-csv', 'v1', '{}'::jsonb, $7, $8, 'wbs-import-snapshot/v1', "
        "$9::jsonb, $7, '[]'::jsonb, 0, 0, 0, 'READY', $10, 'human')",
        source, tenant, project, document, revision, blob, _D, "sha256:" + source.hex + "0" * 32,
        json.dumps({"rows": []}), uuid4())
    await conn.execute("SET session_replication_role = DEFAULT")
    return source


async def test_upgrade_round_trip_and_enum_downgrade_fails_closed() -> None:
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", BEFORE)
        conn = await _connect()
        try:
            assert "wbs" not in await _labels(conn)
            tenant, project = await _tenant_project(conn)
        finally:
            await conn.close()
        _alembic("upgrade", PC2B3)
        conn = await _connect()
        try:
            assert (await _labels(conn))[-1] == "wbs"
            assert await conn.fetchval("SELECT count(*) FROM wbs_import_sources") == 0  # nothing seeded
            assert tuple(await conn.fetchrow("SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                                             "WHERE oid = 'public.wbs_import_sources'::regclass")) == (True, True)
            assert await conn.fetchval("SELECT count(*) FROM wbs_change_sets WHERE source_import_id IS NOT NULL") == 0
            document, _, _ = await _wbs_document(conn, tenant, project)
        finally:
            await conn.close()
        # A WBS document exists: the downgrade FAILS CLOSED and changes nothing.
        with pytest.raises(AssertionError, match="WBS source documents exist"):
            _alembic("downgrade", BEFORE)
        conn = await _connect()
        try:
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == PC2B3
            assert await conn.fetchval("SELECT document_type::text FROM documents WHERE id = $1", document) == "wbs"
            assert await conn.fetchval("SELECT to_regclass('public.wbs_import_sources') IS NOT NULL")
            await conn.execute("DELETE FROM document_revisions WHERE document_id = $1", document)
            await conn.execute("DELETE FROM documents WHERE id = $1", document)
        finally:
            await conn.close()
        _alembic("downgrade", BEFORE)
        conn = await _connect()
        try:
            assert "wbs" not in await _labels(conn)
            assert not await conn.fetchval("SELECT to_regclass('public.wbs_import_sources') IS NOT NULL")
            assert not await conn.fetchval("SELECT count(*) FROM pg_proc WHERE proname = ANY($1::text[])", list(FUNCTIONS))
            assert not await conn.fetchval("SELECT count(*) FROM information_schema.columns WHERE table_name = "
                                           "'wbs_change_sets' AND column_name = 'source_import_id'")
            assert await conn.fetchval("SELECT count(*) FROM projects WHERE id = $1", project) == 1
        finally:
            await conn.close()
        _alembic("upgrade", PC2B3)
        conn = await _connect()
        try:
            source = await _seed_import(conn, tenant, project)
            await conn.execute("DELETE FROM projects WHERE id = $1", project)  # provenance leaves with its project
            assert await conn.fetchval("SELECT count(*) FROM wbs_import_sources WHERE id = $1", source) == 0
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()


async def test_53_to_57_rls_isolates_imports_for_a_nobypassrls_role() -> None:
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", PC2B3)
        conn = await _connect()
        try:
            tenant_a, project_a = await _tenant_project(conn)
            tenant_b, project_b = await _tenant_project(conn)
            a = await _seed_import(conn, tenant_a, project_a)
            b = await _seed_import(conn, tenant_b, project_b)
            await conn.execute(f"DROP ROLE IF EXISTS {_ROLE}")
            await conn.execute(f"CREATE ROLE {_ROLE} NOLOGIN NOBYPASSRLS")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {_ROLE}")
            await conn.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON wbs_import_sources TO {_ROLE}")
            await conn.execute(f"GRANT SELECT ON projects, users, documents, document_revisions TO {_ROLE}")
            try:
                async with conn.transaction():  # 53: tenant A reads only its own imports
                    await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                    await conn.execute("SELECT set_config('app.current_tenant', $1, true)", str(tenant_a))
                    assert [r["id"] for r in await conn.fetch("SELECT id FROM wbs_import_sources")] == [a]
                    assert await conn.fetchval("SELECT count(*) FROM wbs_import_sources WHERE id = $1", b) == 0
                    assert await conn.execute("DELETE FROM wbs_import_sources WHERE tenant_id = $1",
                                              tenant_b) == "DELETE 0"
                async with conn.transaction():  # 56: no tenant context -> nothing, fail closed
                    await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                    await conn.execute("SELECT set_config('app.current_tenant', '', true)")
                    assert await conn.fetchval("SELECT count(*) FROM wbs_import_sources") == 0
                # 54: tenant A cannot write an import into tenant B (RLS WITH CHECK, or the guard first)
                with pytest.raises((asyncpg.InsufficientPrivilegeError, asyncpg.CheckViolationError)):
                    async with conn.transaction():
                        await conn.execute(f"SET LOCAL ROLE {_ROLE}")
                        await conn.execute("SELECT set_config('app.current_tenant', $1, true)", str(tenant_a))
                        await conn.execute(
                            "INSERT INTO wbs_import_sources SELECT gen_random_uuid(), tenant_id, project_id, "
                            "document_id, revision_id, blob_hash, format, parser_id, parser_version, parse_config, "
                            "parse_config_digest, 'sha256:' || repeat('c', 64), snapshot_schema_version, snapshot, "
                            "snapshot_digest, diagnostics, row_count, warning_count, blocking_count, status, created_by, "
                            "created_by_kind, now() FROM wbs_import_sources WHERE id = $1", a)
            finally:
                await conn.execute(f"REVOKE ALL ON wbs_import_sources, projects, users, documents, document_revisions "
                                   f"FROM {_ROLE}")
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
UNION ALL
SELECT 'scope', c.conrelid::regclass::text, c.conname, pg_get_constraintdef(c.oid)
  FROM pg_constraint c WHERE c.conname = 'uq_document_revisions_scope'
"""


async def test_migrated_schema_matches_the_orm_schema(db: AsyncSession) -> None:
    orm_rows = (await db.execute(text(_SCHEMA_QUERY.replace("$1::text[]", ":tables").replace("$2::text[]", ":functions")),
                                 {"tables": list(TABLES), "functions": list(FUNCTIONS)})).all()
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", PC2B3)
        conn = await _connect()
        try:
            migrated_rows = await conn.fetch(_SCHEMA_QUERY, list(TABLES), list(FUNCTIONS))
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()
    assert len(migrated_rows) == len(orm_rows) > 25
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
        _alembic("upgrade", PC2B3)
        conn = await _connect()
        try:
            for role in ("anon", "authenticated"):
                assert not await conn.fetchval("SELECT has_table_privilege($1, 'public.wbs_import_sources', "
                                               "'SELECT, INSERT, UPDATE, DELETE')", role)
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
