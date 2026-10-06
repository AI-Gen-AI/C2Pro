"""PC-1R WBS structural-integrity migration on a real PostgreSQL (TS-INT-PC1R-MIGRATION-001).

Upgrades a disposable database to the revision BEFORE PC-1R, seeds WBS shapes, then
upgrades to head:

* M1-M4: the preflight fails closed -- with NO mutation -- on a missing parent, a
  cross-project parent, a parent cycle or a duplicate code;
* M5: ``sort_order`` is backfilled densely in the order users see today, including a
  23-row flat project shaped like production (2026-10-05 preflight);
* the new delete rules hold (document delete keeps WBS, parent delete fails, RACI/BOM
  links block node deletion, project delete still cascades);
* M7: downgrade restores the previous delete rules without rewriting WBS data, and
  upgrade re-applies;
* M8: RLS / FORCE RLS / policies / grants are unchanged.

Requires ``C2PRO_MIGRATION_SCRATCH_DSN`` (a disposable ``*_test`` database).
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any
from uuid import UUID, uuid4

import pytest

from tests.integration.product_control.test_adr025_wbs_legacy_data_migration import (
    API_ROOT,
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

BEFORE_PC1R = "20261005_0002"
PC1R = "20261005_0003"


def _alembic_fails(revision: str) -> str:
    assert SCRATCH_DSN is not None
    env = {**os.environ, "DATABASE_URL": SCRATCH_DSN, "TEST_DATABASE_URL": SCRATCH_DSN}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=API_ROOT, env=env, capture_output=True, text=True, timeout=900, check=False,
    )
    assert result.returncode != 0, "the PC-1R preflight must reject this data"
    return result.stdout + result.stderr


async def _connect() -> Any:
    assert SCRATCH_DSN is not None
    return await asyncpg.connect(SCRATCH_DSN)


async def _scope(conn: Any) -> tuple[UUID, UUID, UUID]:
    tenant, project_a, project_b = uuid4(), uuid4(), uuid4()
    await conn.execute(
        "INSERT INTO tenants (id, name, slug, subscription_plan) VALUES ($1, 'pc1r', $2, 'free')",
        tenant, f"pc1r-{tenant}",
    )
    for project in (project_a, project_b):
        await conn.execute(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency) "
            "VALUES ($1, $2, 'pc1r', $3, 'construction', 'active', 'EUR')",
            project, tenant, f"P-{project.hex[:8]}",
        )
    return tenant, project_a, project_b


async def _insert(conn: Any, *, tenant: UUID, project: UUID, code: str, lft: int, rgt: int, depth: int,
                  parent: UUID | None = None, node_id: UUID | None = None) -> UUID:
    node_id = node_id or uuid4()
    await conn.execute(
        "INSERT INTO wbs_nodes (id, project_id, tenant_id, parent_id, code, name, lft, rgt, depth, node_type, "
        "metadata, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'activity', '{}'::jsonb, "
        "now(), now())",
        node_id, project, tenant, parent, code, f"Node {code}", lft, rgt, depth,
    )
    return node_id


async def _wbs_snapshot(conn: Any) -> list[tuple[Any, ...]]:
    rows = await conn.fetch(
        "SELECT id, project_id, tenant_id, parent_id, code, name, lft, rgt, depth, node_type::text, updated_at "
        "FROM wbs_nodes ORDER BY id"
    )
    return [tuple(row) for row in rows]


async def _has_sort_order(conn: Any) -> bool:
    return bool(await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'wbs_nodes' "
        "AND column_name = 'sort_order')"
    ))


async def _delete_rule(conn: Any, name: str) -> str:
    value = await conn.fetchval("SELECT confdeltype::text FROM pg_constraint WHERE conname = $1", name)
    return str(value)


@pytest.mark.parametrize("violation", ["missing_parent", "cross_project_parent", "cycle", "duplicate_code"])
async def test_m1_m4_preflight_fails_closed_without_mutation(violation: str) -> None:
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", BEFORE_PC1R)
        conn = await _connect()
        try:
            tenant, project_a, project_b = await _scope(conn)
            if violation == "missing_parent":
                # The legacy SET NULL FK cannot express a missing parent, so drop it first, as a
                # half-applied manual repair could have done.
                await conn.execute("ALTER TABLE wbs_nodes DROP CONSTRAINT wbs_nodes_parent_id_fkey")
                await _insert(conn, tenant=tenant, project=project_a, code="1.1", lft=1, rgt=2, depth=1,
                              parent=uuid4())
            elif violation == "cross_project_parent":
                foreign = await _insert(conn, tenant=tenant, project=project_b, code="1", lft=1, rgt=4, depth=0)
                await _insert(conn, tenant=tenant, project=project_a, code="1.1", lft=2, rgt=3, depth=1,
                              parent=foreign)
            elif violation == "cycle":
                a, b = uuid4(), uuid4()
                await _insert(conn, tenant=tenant, project=project_a, code="A", lft=1, rgt=4, depth=0, node_id=a)
                await _insert(conn, tenant=tenant, project=project_a, code="B", lft=2, rgt=3, depth=1,
                              parent=a, node_id=b)
                await conn.execute("UPDATE wbs_nodes SET parent_id = $1 WHERE id = $2", b, a)
            else:
                await conn.execute("ALTER TABLE wbs_nodes DROP CONSTRAINT uq_wbs_nodes_project_code")
                await _insert(conn, tenant=tenant, project=project_a, code="1", lft=1, rgt=2, depth=0)
                await _insert(conn, tenant=tenant, project=project_a, code="1", lft=3, rgt=4, depth=0)
            before = await _wbs_snapshot(conn)
        finally:
            await conn.close()

        output = _alembic_fails(PC1R)
        assert "PC-1R preflight" in output

        conn = await _connect()
        try:
            assert await _wbs_snapshot(conn) == before
            assert not await _has_sort_order(conn)
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == BEFORE_PC1R
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()


async def test_m5_m7_m8_backfill_delete_rules_downgrade_and_rls() -> None:
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", BEFORE_PC1R)
        conn = await _connect()
        try:
            tenant, flat_project, tree_project = await _scope(conn)
            # Production shape: 23 flat top-level rows ordered by the legacy nested set.
            flat_ids = [
                await _insert(conn, tenant=tenant, project=flat_project, code=f"SCH-{i:03d}",
                              lft=2 * i - 1, rgt=2 * i, depth=0)
                for i in range(1, 24)
            ]
            # A small tree whose nested-set order differs from code order.
            root_b = await _insert(conn, tenant=tenant, project=tree_project, code="2", lft=1, rgt=6, depth=0)
            child_late = await _insert(conn, tenant=tenant, project=tree_project, code="2.10", lft=2, rgt=3,
                                       depth=1, parent=root_b)
            child_early = await _insert(conn, tenant=tenant, project=tree_project, code="2.2", lft=4, rgt=5,
                                        depth=1, parent=root_b)
            root_a = await _insert(conn, tenant=tenant, project=tree_project, code="1", lft=7, rgt=8, depth=0)
            security_before = await _security_snapshot(conn)
            data_before = await _wbs_snapshot(conn)
        finally:
            await conn.close()

        _alembic("upgrade", PC1R)

        conn = await _connect()
        try:
            order = {row["id"]: row["sort_order"] for row in await conn.fetch("SELECT id, sort_order FROM wbs_nodes")}
            assert [order[i] for i in flat_ids] == list(range(1, 24))
            assert (order[root_b], order[root_a]) == (1, 2)
            assert (order[child_late], order[child_early]) == (1, 2)
            assert await _security_snapshot(conn) == security_before
            # No other WBS column was rewritten.
            assert [row[:10] for row in await _wbs_snapshot(conn)] == [row[:10] for row in data_before]

            assert await _delete_rule(conn, "fk_wbs_nodes_parent_same_project") == "a"
            assert await _delete_rule(conn, "wbs_nodes_source_document_id_fkey") == "n"
            assert await _delete_rule(conn, "stakeholder_wbs_raci_wbs_item_id_fkey") == "a"
            assert await _delete_rule(conn, "procurement_bom_items_wbs_item_id_fkey") == "a"

            with pytest.raises(asyncpg.PostgresError):
                await conn.execute("DELETE FROM wbs_nodes WHERE id = $1", root_b)
            with pytest.raises(asyncpg.PostgresError):
                async with conn.transaction():
                    await conn.execute("UPDATE wbs_nodes SET depth = 4 WHERE id = $1", child_early)
            await conn.execute("DELETE FROM projects WHERE id = $1", tree_project)
            assert await conn.fetchval("SELECT count(*) FROM wbs_nodes WHERE project_id = $1", tree_project) == 0
            data_after_upgrade = await _wbs_snapshot(conn)
        finally:
            await conn.close()

        _alembic("downgrade", BEFORE_PC1R)
        conn = await _connect()
        try:
            assert not await _has_sort_order(conn)
            assert await _delete_rule(conn, "wbs_nodes_parent_id_fkey") == "n"
            assert await _delete_rule(conn, "wbs_nodes_source_document_id_fkey") == "c"
            assert await _delete_rule(conn, "stakeholder_wbs_raci_wbs_item_id_fkey") == "c"
            assert await _delete_rule(conn, "procurement_bom_items_wbs_item_id_fkey") == "n"
            assert await _wbs_snapshot(conn) == data_after_upgrade
            assert await _security_snapshot(conn) == security_before
        finally:
            await conn.close()

        _alembic("upgrade", "head")
        conn = await _connect()
        try:
            assert await _has_sort_order(conn)
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()
