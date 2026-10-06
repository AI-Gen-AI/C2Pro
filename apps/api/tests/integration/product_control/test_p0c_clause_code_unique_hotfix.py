"""#909: reproduce the production legacy clause-code constraint on real PostgreSQL."""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration.product_control.test_adr025_wbs_legacy_data_migration import (
    SCRATCH_DSN,
    _alembic,
    _drop_scratch_database,
    _recreate_scratch_database,
)

asyncpg = pytest.importorskip("asyncpg")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not SCRATCH_DSN, reason="requires C2PRO_MIGRATION_SCRATCH_DSN"),
]

BEFORE_HOTFIX = "20261006_0002"
LEGACY_CONSTRAINT = "clauses_project_document_code_unique"


async def test_hotfix_removes_legacy_uniqueness_and_allows_same_code_across_revisions() -> None:
    assert SCRATCH_DSN is not None
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", BEFORE_HOTFIX)
        tenant_id = uuid4()
        project_id = uuid4()
        document_id = uuid4()
        revision_a = uuid4()
        revision_b = uuid4()

        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            force_rls_before = await conn.fetchval(
                "SELECT relforcerowsecurity FROM pg_class "
                "WHERE oid = 'public.clauses'::regclass"
            )
            await conn.execute(
                f"ALTER TABLE public.clauses DROP CONSTRAINT IF EXISTS {LEGACY_CONSTRAINT}"
            )
            await conn.execute(
                f"ALTER TABLE public.clauses ADD CONSTRAINT {LEGACY_CONSTRAINT} "
                "UNIQUE (project_id, document_id, clause_code)"
            )

            # Seed only the exact revision/clauses shape under test. FK triggers are
            # irrelevant here; the legacy UNIQUE index remains enforced in replica mode.
            await conn.execute("SET session_replication_role = replica")
            for rev_no, revision_id in ((1, revision_a), (2, revision_b)):
                await conn.execute(
                    "INSERT INTO document_revisions "
                    "(revision_id, document_id, project_id, tenant_id, rev_no, blob_hash, "
                    "blob_key, valid_from, valid_to) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, now(), "
                    "CASE WHEN $5 = 2 THEN NULL ELSE now() END)",
                    revision_id,
                    document_id,
                    project_id,
                    tenant_id,
                    rev_no,
                    f"{rev_no:064d}",
                    f"k-{rev_no}",
                )

            await conn.execute(
                "INSERT INTO clauses "
                "(id, tenant_id, project_id, document_id, revision_id, clause_code, extracted_entities) "
                "VALUES ($1, $2, $3, $4, $5, 'AUTO-001', '{}'::jsonb)",
                uuid4(),
                tenant_id,
                project_id,
                document_id,
                revision_a,
            )
            with pytest.raises(asyncpg.UniqueViolationError):
                await conn.execute(
                    "INSERT INTO clauses "
                    "(id, tenant_id, project_id, document_id, revision_id, clause_code, extracted_entities) "
                    "VALUES ($1, $2, $3, $4, $5, 'AUTO-001', '{}'::jsonb)",
                    uuid4(),
                    tenant_id,
                    project_id,
                    document_id,
                    revision_b,
                )
            await conn.execute("SET session_replication_role = DEFAULT")
        finally:
            await conn.close()

        _alembic("upgrade", "head")

        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            constraint_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_constraint "
                "WHERE conrelid = 'public.clauses'::regclass AND conname = $1)",
                LEGACY_CONSTRAINT,
            )
            assert constraint_exists is False

            force_rls_after = await conn.fetchval(
                "SELECT relforcerowsecurity FROM pg_class "
                "WHERE oid = 'public.clauses'::regclass"
            )
            assert force_rls_after == force_rls_before

            await conn.execute("SET session_replication_role = replica")
            await conn.execute(
                "INSERT INTO clauses "
                "(id, tenant_id, project_id, document_id, revision_id, clause_code, extracted_entities) "
                "VALUES ($1, $2, $3, $4, $5, 'AUTO-001', '{}'::jsonb)",
                uuid4(),
                tenant_id,
                project_id,
                document_id,
                revision_b,
            )
            rows = await conn.fetch(
                "SELECT revision_id FROM clauses "
                "WHERE project_id = $1 AND document_id = $2 AND clause_code = 'AUTO-001' "
                "ORDER BY revision_id",
                project_id,
                document_id,
            )
            assert {row["revision_id"] for row in rows} == {revision_a, revision_b}
            await conn.execute("SET session_replication_role = DEFAULT")
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()
