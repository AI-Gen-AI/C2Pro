"""PC-2b.4 (#923) -- the Reviewer's manifest-scoped chunk reader under RLS (TS-INT-PC2B4-RLS-001).

On a migrated database (``document_chunks`` RLS ENABLED + FORCED, tenant policies), the reader is
run inside a transaction under a NOBYPASSRLS role:

* with tenant A's context it returns only tenant A's authorized chunks -- a forged allow-list
  naming tenant B's document / revision returns nothing of tenant B (two walls: SQL + RLS);
* a forged pair (own document, foreign revision) matches nothing: pairs bind exactly in SQL, and the
  bounded read never returns more than its limits;
* without a tenant context it returns nothing (fail closed);
* asked for tenant B's scope while the context is tenant A, it returns nothing.

The production-like privileged (BYPASSRLS) role is covered in
tests/modules/integration/test_pc2b4_wbs_reviewer.py, where only the SQL predicates separate scopes.
Requires ``C2PRO_MIGRATION_SCRATCH_DSN`` (a disposable ``*_test`` database).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.wbs.intelligence.reviewer.evidence import ManifestScopedChunkReader
from tests.integration.product_control.test_adr025_wbs_legacy_data_migration import (
    SCRATCH_DSN,
    _alembic,
    _drop_scratch_database,
    _recreate_scratch_database,
)
from tests.integration.product_control.test_pc2a1_wbs_governance_migration_db import (
    _connect,
    _tenant_project,
)

asyncpg = pytest.importorskip("asyncpg")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not SCRATCH_DSN, reason="requires C2PRO_MIGRATION_SCRATCH_DSN"),
]

_ROLE = "c2pro_pc2b4_rls_probe"


async def _document_with_chunk(conn: Any, tenant: UUID, project: UUID, content: str) -> tuple[UUID, UUID]:
    document, revision = uuid4(), uuid4()
    blob = hashlib.sha256(content.encode()).hexdigest()
    await conn.execute("INSERT INTO documents (id, tenant_id, project_id, document_type, filename) "
                       "VALUES ($1, $2, $3, 'contract', 'c.pdf')", document, tenant, project)
    await conn.execute("INSERT INTO document_revisions (revision_id, document_id, project_id, tenant_id, rev_no, "
                       "blob_hash, blob_key, valid_from) VALUES ($1, $2, $3, $4, 1, $5, 'k.pdf', now())",
                       revision, document, project, tenant, blob)
    await conn.execute("INSERT INTO document_chunks (id, tenant_id, document_id, project_id, content, embedding, "
                       "metadata) VALUES ($1, $2, $3, $4, $5, $6::vector, $7::jsonb)", uuid4(), tenant, document,
                       project, content, "[" + ",".join(["0"] * 1536) + "]",
                       json.dumps({"revision_id": str(revision)}))
    return document, revision


async def test_the_reader_isolates_tenants_for_a_nobypassrls_role() -> None:
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", "head")
        conn = await _connect()
        try:
            forced = await conn.fetchrow("SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                                         "WHERE oid = 'public.document_chunks'::regclass")
            assert tuple(forced) == (True, True)
            tenant_a, project_a = await _tenant_project(conn)
            tenant_b, project_b = await _tenant_project(conn)
            own = await _document_with_chunk(conn, tenant_a, project_a, "SECRET-A")
            foreign = await _document_with_chunk(conn, tenant_b, project_b, "SECRET-B")
            await conn.execute(f"DROP ROLE IF EXISTS {_ROLE}")
            await conn.execute(f"CREATE ROLE {_ROLE} NOLOGIN NOBYPASSRLS")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {_ROLE}")
            await conn.execute(f"GRANT SELECT ON document_chunks TO {_ROLE}")
        finally:
            await conn.close()

        assert SCRATCH_DSN is not None
        engine = create_async_engine(SCRATCH_DSN.replace("postgresql://", "postgresql+asyncpg://"))
        try:
            async def read(context: str, tenant: UUID, project: UUID) -> list[str]:
                async with AsyncSession(engine) as session, session.begin():
                    await session.execute(text(f"SET LOCAL ROLE {_ROLE}"))
                    await session.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": context})
                    cross = (own[0], foreign[1])  # a forged pair: own document, foreign revision
                    chunks = await ManifestScopedChunkReader(session).read(
                        tenant_id=tenant, project_id=project, allowed=[own, foreign, cross], per_document=1, total=2)
                    return [c.content for c in chunks]

            assert await read(str(tenant_a), tenant_a, project_a) == ["SECRET-A"]
            assert await read("", tenant_a, project_a) == []  # no tenant context: nothing (fail closed)
            assert await read(str(tenant_a), tenant_b, project_b) == []  # B's scope under A's context
        finally:
            await engine.dispose()
            conn = await _connect()
            try:
                await conn.execute(f"REVOKE ALL ON document_chunks FROM {_ROLE}")
                await conn.execute(f"REVOKE ALL ON SCHEMA public FROM {_ROLE}")
                await conn.execute(f"DROP ROLE {_ROLE}")
            finally:
                await conn.close()
    finally:
        await _drop_scratch_database()
