"""C3a clause revision binding migration on a real PostgreSQL (TS-INT-C3A-MIGRATION-001).

Upgrades a disposable database to the revision BEFORE the binding, seeds legacy
clause rows whose JSONB revision evidence is valid, malformed, unknown, of another
document or of another tenant, then upgrades to head. Proves that only proven
bindings are backfilled (everything else stays NULL), that the composite FK makes
the database reject a clause bound to another document's or tenant's revision,
that FORCE row security is restored, and that downgrade/upgrade round-trips.

Requires ``C2PRO_MIGRATION_SCRATCH_DSN`` (a disposable ``*_test`` database).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

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

BEFORE_BINDING = "20260927_0714"


def _load_migration() -> Any:
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "20261004_0001_clause_revision_binding.py"
    )
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _revision(conn: Any, *, document: UUID, tenant: UUID, rev_no: int, current: bool) -> UUID:
    revision = uuid4()
    await conn.execute(
        "INSERT INTO document_revisions (revision_id, document_id, project_id, tenant_id, rev_no, "
        "blob_hash, blob_key, valid_from, valid_to) VALUES ($1, $2, $3, $4, $5, $6, 'k', now(), "
        "CASE WHEN $7 THEN NULL ELSE now() END)",
        revision, document, uuid4(), tenant, rev_no, f"{rev_no:064d}", current,
    )
    return revision


async def _clause(conn: Any, *, document: UUID, tenant: UUID, evidence: Any) -> UUID:
    clause = uuid4()
    entities = {} if evidence is None else {"evidence_location": evidence}
    await conn.execute(
        "INSERT INTO clauses (id, tenant_id, project_id, document_id, clause_code, extracted_entities) "
        "VALUES ($1, $2, $3, $4, 'C-1', $5::jsonb)",
        clause, tenant, uuid4(), document, json.dumps(entities),
    )
    return clause


async def test_binding_backfills_only_proven_revisions_and_is_enforced_by_the_database() -> None:
    assert SCRATCH_DSN is not None
    migration = _load_migration()
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", BEFORE_BINDING)
        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            tenant, other_tenant = uuid4(), uuid4()
            doc, other_doc = uuid4(), uuid4()
            await conn.execute("SET session_replication_role = replica")  # seed FK parents only
            for document, owner in ((doc, tenant), (other_doc, tenant)):
                await conn.execute(
                    "INSERT INTO documents (id, tenant_id, project_id, document_type, filename, "
                    "upload_status) VALUES ($1, $2, $3, 'contract', 'c.pdf', 'uploaded')",
                    document, owner, uuid4(),
                )
            r1 = await _revision(conn, document=doc, tenant=tenant, rev_no=1, current=False)
            r2 = await _revision(conn, document=doc, tenant=tenant, rev_no=2, current=True)
            r_other_doc = await _revision(conn, document=other_doc, tenant=tenant, rev_no=1, current=True)
            # A (nonsensical) revision row of the same document under ANOTHER tenant.
            r_other_tenant = await _revision(conn, document=doc, tenant=other_tenant, rev_no=9, current=False)

            proven_1 = await _clause(conn, document=doc, tenant=tenant, evidence={"revision_id": str(r1)})
            proven_2 = await _clause(conn, document=doc, tenant=tenant, evidence={"revision_id": str(r2)})
            malformed = await _clause(conn, document=doc, tenant=tenant, evidence={"revision_id": "rev-1"})
            not_object = await _clause(conn, document=doc, tenant=tenant, evidence="page 3")
            unknown = await _clause(conn, document=doc, tenant=tenant, evidence={"revision_id": str(uuid4())})
            cross_doc = await _clause(conn, document=doc, tenant=tenant, evidence={"revision_id": str(r_other_doc)})
            cross_tenant = await _clause(
                conn, document=doc, tenant=tenant, evidence={"revision_id": str(r_other_tenant)}
            )
            no_source = await _clause(conn, document=doc, tenant=tenant, evidence=None)
            await conn.execute("SET session_replication_role = DEFAULT")
            forced_before = {
                table: await conn.fetchval(
                    "SELECT relforcerowsecurity FROM pg_class WHERE oid = $1::regclass",
                    f"public.{table}",
                )
                for table in ("clauses", "document_revisions")
            }
        finally:
            await conn.close()

        _alembic("upgrade", "head")
        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            bound = {
                row["id"]: row["revision_id"]
                for row in await conn.fetch("SELECT id, revision_id FROM clauses")
            }
            assert bound[proven_1] == r1
            assert bound[proven_2] == r2
            for clause in (malformed, not_object, unknown, cross_doc, cross_tenant, no_source):
                assert bound[clause] is None, clause

            report = await conn.fetchrow(migration.BACKFILL_REPORT_SQL)
            assert dict(report) == {
                "total": 8,
                "bound": 2,
                "unbound": 6,
                "malformed_source": 2,
                "unknown_revision": 1,
                "cross_document_or_tenant": 2,
                "no_source": 1,
            }

            # FORCE row security is exactly as before the data step.
            for table, before in forced_before.items():
                forced = await conn.fetchval(
                    "SELECT relforcerowsecurity FROM pg_class WHERE oid = $1::regclass",
                    f"public.{table}",
                )
                assert forced == before, table
            assert forced_before["clauses"] is True

            # The database itself rejects a clause bound to another document's or tenant's revision.
            for revision, document, owner in (
                (r_other_doc, doc, tenant),
                (r_other_tenant, doc, tenant),
                (r1, other_doc, tenant),
            ):
                with pytest.raises(asyncpg.ForeignKeyViolationError):
                    await conn.execute(
                        "INSERT INTO clauses (id, tenant_id, project_id, document_id, clause_code, "
                        "revision_id) VALUES ($1, $2, $3, $4, 'C-2', $5)",
                        uuid4(), owner, uuid4(), document, revision,
                    )
            # ... and accepts the exact revision of the same document and tenant; NULL stays legal.
            await conn.execute(
                "INSERT INTO clauses (id, tenant_id, project_id, document_id, clause_code, revision_id) "
                "VALUES ($1, $2, $3, $4, 'C-2', $5)",
                uuid4(), tenant, uuid4(), doc, r2,
            )
            await conn.execute(
                "INSERT INTO clauses (id, tenant_id, project_id, document_id, clause_code) "
                "VALUES ($1, $2, $3, $4, 'C-3')",
                uuid4(), tenant, uuid4(), doc,
            )
            # The same clause_code may repeat across revisions (no clause_code uniqueness).
            await conn.execute(
                "INSERT INTO clauses (id, tenant_id, project_id, document_id, clause_code, revision_id) "
                "VALUES ($1, $2, $3, $4, 'C-1', $5)",
                uuid4(), tenant, uuid4(), doc, r1,
            )
        finally:
            await conn.close()

        # Round trip: downgrade removes the binding, upgrade re-derives the same proven set.
        _alembic("downgrade", BEFORE_BINDING)
        _alembic("upgrade", "head")
        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            again = await conn.fetchrow(
                "SELECT (SELECT revision_id FROM clauses WHERE id = $1) AS p1, "
                "(SELECT revision_id FROM clauses WHERE id = $2) AS m",
                proven_1, malformed,
            )
            assert again["p1"] == r1 and again["m"] is None
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()
