"""ADR-025 data migration on a real PostgreSQL: legacy WBS rows reach one canonical WBS per project.

Builds a scratch database at the revision before ADR-025, seeds representative legacy data (a
procurement-only project with an inferred type, a recomputed level, an 80-character code and a
parent cycle; a project that already owns canonical nodes; a wbs_items-only project; a project
with both legacy stores), then runs ``alembic upgrade head``, ``alembic downgrade`` and
``alembic upgrade head`` again.

Requires ``C2PRO_MIGRATION_SCRATCH_DSN``: a disposable database whose name ends with ``_test``
(it is DROPPED and recreated) on a server where that user may create databases. With
``C2PRO_REQUIRE_MIGRATED_TEST_DSN=1`` (CI migrations job) a missing DSN is a failure.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from uuid import UUID, uuid4

import pytest

asyncpg = pytest.importorskip("asyncpg")

SCRATCH_DSN = os.environ.get("C2PRO_MIGRATION_SCRATCH_DSN")
REQUIRED = os.environ.get("C2PRO_REQUIRE_MIGRATED_TEST_DSN") == "1"

if REQUIRED and not SCRATCH_DSN:
    pytest.fail("C2PRO_REQUIRE_MIGRATED_TEST_DSN=1 but C2PRO_MIGRATION_SCRATCH_DSN is not set", pytrace=False)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not SCRATCH_DSN, reason="requires C2PRO_MIGRATION_SCRATCH_DSN (a disposable *_test database)"),
]

API_ROOT = Path(__file__).resolve().parents[3]
BEFORE_ADR025 = "20260914_0003"
LONG_CODE = "L" * 80
RLS_TABLES = ("wbs_nodes", "procurement_wbs_items", "wbs_items", "stakeholder_wbs_raci", "procurement_bom_items", "projects")


def _database_name(dsn: str) -> str:
    return urlparse(dsn).path.lstrip("/")


def _maintenance_dsn(dsn: str) -> str:
    return urlunparse(urlparse(dsn)._replace(path="/postgres"))


def _alembic(command: str, revision: str) -> str:
    assert SCRATCH_DSN is not None
    env = {**os.environ, "DATABASE_URL": SCRATCH_DSN, "TEST_DATABASE_URL": SCRATCH_DSN}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", command, revision],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output[-6000:]
    return output


async def _recreate_scratch_database() -> None:
    assert SCRATCH_DSN is not None
    name = _database_name(SCRATCH_DSN)
    assert name.endswith("_test"), f"refusing to recreate {name!r}: scratch database names must end with _test"
    admin = await asyncpg.connect(_maintenance_dsn(SCRATCH_DSN))
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()


async def _drop_scratch_database() -> None:
    assert SCRATCH_DSN is not None
    admin = await asyncpg.connect(_maintenance_dsn(SCRATCH_DSN))
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{_database_name(SCRATCH_DSN)}" WITH (FORCE)')
    finally:
        await admin.close()


async def _security_snapshot(conn) -> dict[str, object]:
    tables = await conn.fetch(
        "SELECT relname, relrowsecurity, relforcerowsecurity, relacl::text AS acl, pg_get_userbyid(relowner) AS owner "
        "FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relname = ANY($1::text[]) ORDER BY relname",
        [*RLS_TABLES, "v_project_wbs", "v_raci_matrix"],
    )
    policies = await conn.fetch(
        "SELECT tablename, policyname, cmd, roles::text, qual, with_check FROM pg_policies "
        "WHERE schemaname = 'public' AND tablename = ANY($1::text[]) ORDER BY tablename, policyname",
        list(RLS_TABLES),
    )
    views = await conn.fetch(
        "SELECT relname, reloptions::text AS options FROM pg_class WHERE relname IN ('v_project_wbs', 'v_raci_matrix') ORDER BY relname"
    )
    return {"tables": [dict(r) for r in tables], "policies": [dict(r) for r in policies], "views": [dict(r) for r in views]}


async def _viewdefs(conn) -> dict[str, str]:
    rows = await conn.fetch(
        "SELECT relname, pg_get_viewdef(oid) AS definition FROM pg_class WHERE relname IN ('v_project_wbs', 'v_raci_matrix')"
    )
    return {r["relname"]: r["definition"] for r in rows}


async def _fk(conn, table: str) -> tuple[str, bool]:
    row = await conn.fetchrow(
        "SELECT confrelid::regclass::text AS target, convalidated FROM pg_constraint c "
        "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
        "WHERE c.conrelid = $1::regclass AND c.contype = 'f' AND a.attname = 'wbs_item_id'",
        table,
    )
    assert row is not None, f"{table}.wbs_item_id has no foreign key"
    return row["target"], row["convalidated"]


async def _assert_nested_set(conn, project_id: UUID) -> None:
    rows = await conn.fetch("SELECT id, parent_id, lft, rgt, depth FROM wbs_nodes WHERE project_id = $1", project_id)
    bounds = sorted([r["lft"] for r in rows] + [r["rgt"] for r in rows])
    assert bounds == list(range(1, 2 * len(rows) + 1))
    by_id = {r["id"]: r for r in rows}
    for row in rows:
        if row["parent_id"] is None:
            assert row["depth"] == 0
        else:
            parent = by_id[row["parent_id"]]
            assert parent["lft"] < row["lft"] < row["rgt"] < parent["rgt"]
            assert row["depth"] == parent["depth"] + 1


async def _seed(conn) -> dict[str, UUID]:
    ids: dict[str, UUID] = {}

    def new(name: str) -> UUID:
        ids[name] = uuid4()
        return ids[name]

    await conn.execute(
        "INSERT INTO tenants (id, name, slug, subscription_plan) VALUES ($1, 'ADR025 migration', $2, 'free')",
        new("tenant"),
        f"adr025-migration-{ids['tenant']}",
    )
    for project in ("A", "B", "C", "D"):
        await conn.execute(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency) "
            "VALUES ($1, $2, $3, $4, 'construction', 'active', 'EUR')",
            new(f"project_{project}"),
            ids["tenant"],
            f"ADR025 project {project}",
            f"M25{project}-{str(ids[f'project_{project}'])[:8]}",
        )
        await conn.execute(
            "INSERT INTO stakeholders (id, project_id, tenant_id, name, power_level, interest_level) "
            "VALUES ($1, $2, $3, 'Owner Rep', 'high', 'high')",
            new(f"stakeholder_{project}"),
            ids[f"project_{project}"],
            ids["tenant"],
        )

    procurement = (
        "INSERT INTO procurement_wbs_items (id, project_id, code, name, level, item_type, parent_code, "
        "budget_spent, version, wbs_metadata) VALUES ($1, $2, $3, $4, $5, $6::wbsitemtype, $7, 0, 1, $8::jsonb)"
    )
    async with conn.transaction():  # the parent-cycle rows need the deferred parent FK
        for key, code, name, level, item_type, parent, metadata in (
            ("A_1", "1", "Harbour", 1, "deliverable", None, {}),
            ("A_1_1", "1.1", "Quay wall", 2, "work_package", "1", {}),
            ("A_1_1_1", "1.1.1", "Piling", 3, "activity", "1.1", {"status": "in_progress"}),
            ("A_1_2", "1.2", "Dredging", 5, None, "1", {}),
            ("A_long", LONG_CODE, "Long code", 1, None, None, {}),
            ("A_5", "5", "Cycle head", 1, "activity", "6", {}),
            ("A_6", "6", "Cycle tail", 2, "activity", "5", {}),
        ):
            await conn.execute(procurement, new(key), ids["project_A"], code, name, level, item_type, parent, json.dumps(metadata))

    await conn.execute(
        "INSERT INTO wbs_nodes (id, project_id, tenant_id, code, name, lft, rgt, depth, created_at, updated_at) "
        "VALUES ($1, $2, $3, '1', 'Existing canonical root', 1, 2, 0, now(), now())",
        new("B_canonical"),
        ids["project_B"],
        ids["tenant"],
    )
    await conn.execute(procurement, ids["B_canonical"], ids["project_B"], "1", "Same node", 1, "deliverable", None, "{}")
    await conn.execute(procurement, new("B_2"), ids["project_B"], "2", "Parallel item", 1, "activity", None, "{}")

    legacy = "INSERT INTO wbs_items (id, project_id, code, name, level, item_type, parent_id) VALUES ($1, $2, $3, $4, $5, $6::wbsitemtype, $7)"
    await conn.execute(legacy, new("C_1"), ids["project_C"], "1", "Legacy root", 1, "deliverable", None)
    await conn.execute(legacy, new("C_1_1"), ids["project_C"], "1.1", "Legacy child", 2, None, ids["C_1"])

    await conn.execute(procurement, new("D_1"), ids["project_D"], "1", "Procurement root", 1, "work_package", None, "{}")
    await conn.execute(legacy, ids["D_1"], ids["project_D"], "1", "Twin", 1, "work_package", None)
    await conn.execute(legacy, new("D_9"), ids["project_D"], "9", "Legacy only", 1, None, None)

    raci = (
        "INSERT INTO stakeholder_wbs_raci (id, tenant_id, project_id, stakeholder_id, wbs_item_id, raci_role, "
        "generated_automatically, manually_verified, created_at) VALUES ($1, $2, $3, $4, $5, 'A', false, true, now())"
    )
    await conn.execute(raci, new("raci_C"), ids["tenant"], ids["project_C"], ids["stakeholder_C"], ids["C_1_1"])
    await conn.execute(raci, new("raci_D"), ids["tenant"], ids["project_D"], ids["stakeholder_D"], ids["D_9"])

    bom = "INSERT INTO procurement_bom_items (id, project_id, item_name, quantity, wbs_item_id) VALUES ($1, $2, $3, 1, $4)"
    await conn.execute(bom, new("bom_A"), ids["project_A"], "Sheet piles", ids["A_1_1"])
    await conn.execute(bom, new("bom_B"), ids["project_B"], "Parallel material", ids["B_2"])
    return ids


async def _legacy_rows(conn, table: str, columns: str) -> dict[UUID, dict[str, object]]:
    return {r["id"]: dict(r) for r in await conn.fetch(f"SELECT id, {columns} FROM {table}")}


PROCUREMENT_COLUMNS = "project_id, code, name, level, parent_code, item_type::text AS item_type, version, wbs_metadata::text AS wbs_metadata"


async def test_legacy_wbs_data_reaches_one_canonical_wbs_and_round_trips() -> None:
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", BEFORE_ADR025)
        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            ids = await _seed(conn)
            before_security = await _security_snapshot(conn)
            before_views = await _viewdefs(conn)
            before_procurement = await _legacy_rows(conn, "procurement_wbs_items", PROCUREMENT_COLUMNS)
            before_wbs_items = await _legacy_rows(conn, "wbs_items", "project_id, code, name, level, parent_id")
            before_counts = {
                table: await conn.fetchval(f"SELECT count(*) FROM {table}")
                for table in ("procurement_wbs_items", "wbs_items", "stakeholder_wbs_raci", "procurement_bom_items")
            }
        finally:
            await conn.close()

        _alembic("upgrade", "head")

        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            # --- no silent row loss, every legacy row classified ---------------------------------
            for table, count in before_counts.items():
                assert await conn.fetchval(f"SELECT count(*) FROM {table}") == count, table
            for table in ("procurement_wbs_items", "wbs_items"):
                assert await conn.fetchval(f"SELECT count(*) FROM {table} WHERE canonical_mapping IS NULL") == 0

            mapping = {
                r["id"]: (r["canonical_mapping"], r["canonical_mapping_reason"], r["canonical_wbs_node_id"])
                for table in ("procurement_wbs_items", "wbs_items")
                for r in await conn.fetch(
                    f"SELECT id, canonical_mapping, canonical_mapping_reason, canonical_wbs_node_id FROM {table}"
                )
            }

            # --- project A: procurement WBS becomes the canonical hierarchy -----------------------
            nodes = {
                r["code"]: r
                for r in await conn.fetch(
                    "SELECT n.id, n.code, n.depth, n.tenant_id, n.node_type::text AS node_type, n.status::text AS status, "
                    "p.code AS parent_code, n.metadata FROM wbs_nodes n LEFT JOIN wbs_nodes p ON p.id = n.parent_id "
                    "WHERE n.project_id = $1",
                    ids["project_A"],
                )
            }
            assert set(nodes) == {"1", "1.1", "1.1.1", "1.2", LONG_CODE, "5", "6"}
            assert nodes["1.1"]["id"] == ids["A_1_1"] and nodes["1.1"]["parent_code"] == "1"
            assert nodes["1.1.1"]["parent_code"] == "1.1" and nodes["1.1.1"]["status"] == "in_progress"
            assert nodes["1.2"]["depth"] == 1 and nodes["1.2"]["node_type"] == "work_package"
            assert nodes["5"]["parent_code"] is None and nodes["6"]["parent_code"] == "5"
            assert {node["tenant_id"] for node in nodes.values()} == {ids["tenant"]}
            await _assert_nested_set(conn, ids["project_A"])
            assert mapping[ids["A_1"]] == ("DIRECT_MAP", None, ids["A_1"])
            assert mapping[ids["A_1_1_1"]][0] == "DIRECT_MAP"
            assert mapping[ids["A_1_2"]] == ("DERIVED_MAP", "node_type_inferred,level_recomputed_from_hierarchy", ids["A_1_2"])
            assert mapping[ids["A_long"]] == ("DERIVED_MAP", "node_type_inferred", ids["A_long"])
            assert mapping[ids["A_5"]] == ("AMBIGUOUS", "parent_cycle_broken_here", ids["A_5"])
            assert mapping[ids["A_6"]][0] == "DIRECT_MAP"

            # --- project B: an existing canonical WBS is never merged with a parallel one --------
            assert await conn.fetchval("SELECT count(*) FROM wbs_nodes WHERE project_id = $1", ids["project_B"]) == 1
            assert mapping[ids["B_canonical"]] == ("DIRECT_MAP", "already_in_canonical_wbs", ids["B_canonical"])
            assert mapping[ids["B_2"]] == ("AMBIGUOUS", "project_already_has_canonical_wbs", None)

            # --- project C: wbs_items-only project; project D: procurement wins, twin maps --------
            assert await conn.fetchval("SELECT count(*) FROM wbs_nodes WHERE project_id = $1", ids["project_C"]) == 2
            await _assert_nested_set(conn, ids["project_C"])
            assert mapping[ids["C_1_1"]] == ("DERIVED_MAP", "node_type_inferred", ids["C_1_1"])
            assert await conn.fetchval("SELECT count(*) FROM wbs_nodes WHERE project_id = $1", ids["project_D"]) == 1
            assert mapping[ids["D_9"]] == ("AMBIGUOUS", "project_has_procurement_wbs", None)
            twin = await conn.fetchrow(
                "SELECT canonical_mapping, canonical_mapping_reason, canonical_wbs_node_id FROM wbs_items WHERE id = $1",
                ids["D_1"],
            )
            assert tuple(twin) == ("DIRECT_MAP", "same_node_as_procurement_wbs_item", ids["D_1"])

            # --- references: canonical targets, ambiguous legacy rows keep the FK NOT VALID ------
            assert await _fk(conn, "stakeholder_wbs_raci") == ("wbs_nodes", False)
            assert await _fk(conn, "procurement_bom_items") == ("wbs_nodes", False)
            new_raci = (
                "INSERT INTO stakeholder_wbs_raci (id, tenant_id, project_id, stakeholder_id, wbs_item_id, raci_role, "
                "generated_automatically, manually_verified, created_at) VALUES ($1, $2, $3, $4, $5, 'R', false, true, now())"
            )
            probe = conn.transaction()
            await probe.start()
            # A valid assignment on a canonical node is accepted even while the FK is NOT VALID...
            await conn.execute(new_raci, uuid4(), ids["tenant"], ids["project_A"], ids["stakeholder_A"], ids["A_1_1"])
            # ...and an unknown WBS id is rejected for every new write.
            with pytest.raises(asyncpg.exceptions.ForeignKeyViolationError):
                async with conn.transaction():
                    await conn.execute(new_raci, uuid4(), ids["tenant"], ids["project_A"], ids["stakeholder_A"], uuid4())
            await probe.rollback()

            # --- legacy stores are read-only, cascades still work --------------------------------
            for statement in (
                "INSERT INTO procurement_wbs_items (id, project_id, code, name, level, budget_spent, version, wbs_metadata) "
                "VALUES (gen_random_uuid(), $1, 'X', 'Shadow', 1, 0, 1, '{}'::jsonb)",
                "UPDATE wbs_items SET name = 'Shadow' WHERE project_id = $1",
            ):
                with pytest.raises(asyncpg.exceptions.RestrictViolationError, match="ADR-025"):
                    await conn.execute(statement, ids["project_A"] if "INSERT" in statement else ids["project_C"])
            tx = conn.transaction()
            await tx.start()
            await conn.execute("DELETE FROM projects WHERE id = $1", ids["project_C"])
            await tx.rollback()

            # --- views, grants, owners and row security are unchanged -----------------------------
            assert await _security_snapshot(conn) == before_security
            dependencies = await conn.fetch(
                "SELECT DISTINCT v.relname, t.relname AS reads FROM pg_depend d JOIN pg_rewrite r ON r.oid = d.objid "
                "JOIN pg_class v ON v.oid = r.ev_class JOIN pg_class t ON t.oid = d.refobjid "
                "WHERE v.relname IN ('v_project_wbs', 'v_raci_matrix') "
                "AND t.relname IN ('wbs_nodes', 'procurement_wbs_items', 'wbs_items')"
            )
            assert sorted((d["relname"], d["reads"]) for d in dependencies) == [
                ("v_project_wbs", "wbs_nodes"),
                ("v_raci_matrix", "wbs_nodes"),
            ]

            # --- application activity after the upgrade (repository semantics) -------------------
            await conn.execute(
                "UPDATE wbs_nodes SET name = 'Quay wall (rev. B)', version = version + 1 WHERE id = $1", ids["A_1_1"]
            )
            ids["A_7"] = uuid4()
            await conn.execute(
                "INSERT INTO wbs_nodes (id, project_id, tenant_id, parent_id, code, name, lft, rgt, depth, node_type, "
                "metadata, created_at, updated_at) VALUES ($1, $2, $3, $4, '7', 'Added after upgrade', 1000, 1001, 1, "
                "'activity', '{\"_adr025\": {\"node_type_inferred\": false}}'::jsonb, now(), now())",
                ids["A_7"], ids["project_A"], ids["tenant"], ids["A_1"],
            )
        finally:
            await conn.close()

        _alembic("downgrade", BEFORE_ADR025)

        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            assert await _viewdefs(conn) == before_views
            assert await _security_snapshot(conn) == before_security
            assert await _fk(conn, "stakeholder_wbs_raci") == ("wbs_items", True)
            assert await _fk(conn, "procurement_bom_items") == ("procurement_wbs_items", True)
            assert await conn.fetchval("SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_adr025_legacy_wbs_read_only'") == 0
            assert await conn.fetchval(
                "SELECT count(*) FROM information_schema.columns WHERE column_name = 'canonical_mapping'"
            ) == 0
            assert [r["id"] for r in await conn.fetch("SELECT id FROM wbs_nodes")] == [ids["B_canonical"]]

            after_procurement = await _legacy_rows(conn, "procurement_wbs_items", PROCUREMENT_COLUMNS)
            edited = after_procurement.pop(ids["A_1_1"])
            added = after_procurement.pop(ids["A_7"])
            expected = dict(before_procurement)
            expected.pop(ids["A_1_1"])
            assert after_procurement == expected
            assert (edited["name"], edited["version"], edited["parent_code"]) == ("Quay wall (rev. B)", 2, "1")
            assert (added["code"], added["level"], added["parent_code"], added["item_type"]) == ("7", 2, "1", "activity")
            assert await _legacy_rows(conn, "wbs_items", "project_id, code, name, level, parent_id") == before_wbs_items
        finally:
            await conn.close()

        _alembic("upgrade", "head")
        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == "20260914_0005"
            assert await conn.fetchval("SELECT count(*) FROM wbs_nodes WHERE project_id = $1", ids["project_A"]) == 8
            await _assert_nested_set(conn, ids["project_A"])
        finally:
            await conn.close()
    finally:
        await _drop_scratch_database()
