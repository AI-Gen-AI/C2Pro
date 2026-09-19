"""ADR-025 on a MIGRATED PostgreSQL: one canonical hierarchical WBS per project.

Runs against a database built by ``alembic upgrade head`` named by ``C2PRO_MIGRATED_TEST_DSN``.
When ``C2PRO_REQUIRE_MIGRATED_TEST_DSN=1`` (CI migrations job) a missing DSN is a failure, so these
guards cannot silently disappear.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

DSN = os.environ.get("C2PRO_MIGRATED_TEST_DSN")
REQUIRED = os.environ.get("C2PRO_REQUIRE_MIGRATED_TEST_DSN") == "1"

if REQUIRED and not DSN:
    pytest.fail("C2PRO_REQUIRE_MIGRATED_TEST_DSN=1 but C2PRO_MIGRATED_TEST_DSN is not set", pytrace=False)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not DSN, reason="requires C2PRO_MIGRATED_TEST_DSN (a database migrated with alembic)"),
]


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    assert DSN is not None
    engine = create_async_engine(DSN.replace("postgresql://", "postgresql+asyncpg://", 1))
    async with AsyncSession(engine, expire_on_commit=False) as db:
        transaction = await db.begin()
        try:
            yield db
        finally:
            await transaction.rollback()
    await engine.dispose()


async def _project(db: AsyncSession) -> tuple[UUID, UUID]:
    tenant_id, project_id = uuid4(), uuid4()
    await db.execute(
        sa.text("INSERT INTO tenants (id, name, slug, subscription_plan) VALUES (:id, 'ADR025', :slug, 'free')"),
        {"id": tenant_id, "slug": f"adr025-{tenant_id}"},
    )
    await db.execute(
        sa.text(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency) "
            "VALUES (:id, :tid, 'ADR025 project', :code, 'construction', 'active', 'EUR')"
        ),
        {"id": project_id, "tid": tenant_id, "code": f"A25-{str(project_id)[:8]}"},
    )
    await db.execute(sa.text("SELECT set_config('app.current_tenant', :tid, true)"), {"tid": str(tenant_id)})
    return tenant_id, project_id


async def _count(db: AsyncSession, table: str, project_id: UUID) -> int:
    return int((await db.execute(sa.text(f"SELECT count(*) FROM {table} WHERE project_id = :pid"), {"pid": project_id})).scalar_one())


WBS_DICTS = [
    {"code": "1", "name": "Harbour Extension", "item_type": "deliverable"},
    {"code": "1.1", "name": "Quay wall", "parent_code": "1", "item_type": "work_package",
     "planned_start": "2026-10-01T00:00:00+00:00", "planned_end": "2027-06-30T00:00:00+00:00", "budget_allocated": 900000.5},
    {"code": "1.2", "name": "Dredging", "parent_code": "1"},
    {"code": "1.1.1", "name": "Piling", "parent_code": "1.1"},
]


async def test_wbs_written_by_the_application_lands_only_in_the_canonical_hierarchy(session: AsyncSession) -> None:
    from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository

    tenant_id, project_id = await _project(session)
    await SQLAlchemyWBSRepository(session).bulk_create_from_dicts(project_id, WBS_DICTS, tenant_id)
    await session.flush()

    assert await _count(session, "wbs_nodes", project_id) == 4
    assert await _count(session, "procurement_wbs_items", project_id) == 0
    assert await _count(session, "wbs_items", project_id) == 0

    rows = (
        await session.execute(
            sa.text(
                "SELECT n.code, p.code AS parent_code, n.depth, n.lft, n.rgt, n.tenant_id "
                "FROM wbs_nodes n LEFT JOIN wbs_nodes p ON p.id = n.parent_id "
                "WHERE n.project_id = :pid ORDER BY n.lft"
            ),
            {"pid": project_id},
        )
    ).all()
    assert [(r.code, r.parent_code, r.depth) for r in rows] == [
        ("1", None, 0),
        ("1.1", "1", 1),
        ("1.1.1", "1.1", 2),
        ("1.2", "1", 1),
    ]
    assert all(r.tenant_id == tenant_id for r in rows)
    by_code = {r.code: r for r in rows}
    assert by_code["1"].lft < by_code["1.1"].lft < by_code["1.1.1"].lft < by_code["1.1.1"].rgt < by_code["1.1"].rgt
    assert by_code["1.2"].rgt < by_code["1"].rgt

    tree = await SQLAlchemyWBSRepository(session).get_tree(project_id, tenant_id)
    assert [item.code for item in tree] == ["1"]
    assert sorted(child.code for child in tree[0].children) == ["1.1", "1.2"]


async def test_parallel_wbs_tables_are_not_writable(session: AsyncSession) -> None:
    _tenant_id, project_id = await _project(session)
    for statement in (
        "INSERT INTO procurement_wbs_items (id, project_id, code, name, level, budget_spent, version, wbs_metadata) "
        "VALUES (gen_random_uuid(), :pid, 'X', 'Shadow', 1, 0, 1, '{}'::jsonb)",
        "INSERT INTO wbs_items (id, project_id, code, name, level) VALUES (gen_random_uuid(), :pid, 'X', 'Shadow', 1)",
    ):
        nested = await session.begin_nested()
        with pytest.raises(sa.exc.DBAPIError, match="ADR-025"):
            await session.execute(sa.text(statement), {"pid": project_id})
        await nested.rollback()


async def test_raci_and_procurement_reference_canonical_nodes_with_integrity(session: AsyncSession) -> None:
    from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository

    tenant_id, project_id = await _project(session)
    await SQLAlchemyWBSRepository(session).bulk_create_from_dicts(project_id, WBS_DICTS, tenant_id)
    node_id = (
        await session.execute(sa.text("SELECT id FROM wbs_nodes WHERE project_id = :pid AND code = '1.1'"), {"pid": project_id})
    ).scalar_one()
    stakeholder_id = uuid4()
    await session.execute(
        sa.text(
            "INSERT INTO stakeholders (id, project_id, tenant_id, name, power_level, interest_level) "
            "VALUES (:id, :pid, :tid, 'Owner Rep', 'high', 'high')"
        ),
        {"id": stakeholder_id, "pid": project_id, "tid": tenant_id},
    )
    raci = (
        "INSERT INTO stakeholder_wbs_raci (id, tenant_id, project_id, stakeholder_id, wbs_item_id, raci_role, "
        "generated_automatically, manually_verified, created_at) "
        "VALUES (gen_random_uuid(), :tid, :pid, :sid, :wid, 'A', false, true, now())"
    )
    await session.execute(sa.text(raci), {"tid": tenant_id, "pid": project_id, "sid": stakeholder_id, "wid": node_id})

    nested = await session.begin_nested()
    with pytest.raises(sa.exc.IntegrityError):
        await session.execute(sa.text(raci), {"tid": tenant_id, "pid": project_id, "sid": stakeholder_id, "wid": uuid4()})
    await nested.rollback()

    await session.execute(
        sa.text(
            "INSERT INTO procurement_bom_items (id, project_id, item_name, quantity, wbs_item_id) "
            "VALUES (gen_random_uuid(), :pid, 'Sheet piles', 10, :wid)"
        ),
        {"pid": project_id, "wid": node_id},
    )
    fks = (
        await session.execute(
            sa.text(
                "SELECT conrelid::regclass::text AS src, confrelid::regclass::text AS target, convalidated "
                "FROM pg_constraint WHERE contype = 'f' AND conrelid IN "
                "('stakeholder_wbs_raci'::regclass, 'procurement_bom_items'::regclass) "
                "AND conkey = ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid = conrelid AND attname = 'wbs_item_id')]"
            )
        )
    ).all()
    assert sorted((fk.src, fk.target, fk.convalidated) for fk in fks) == [
        ("procurement_bom_items", "wbs_nodes", True),
        ("stakeholder_wbs_raci", "wbs_nodes", True),
    ]


async def test_schedule_and_spend_are_derived_from_the_canonical_wbs(session: AsyncSession) -> None:
    from src.coherence.schedule_clause_builder import build_schedule_clauses
    from src.procurement.adapters.persistence.budget_repository import SQLAlchemyBudgetRepository
    from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository

    tenant_id, project_id = await _project(session)
    await SQLAlchemyWBSRepository(session).bulk_create_from_dicts(project_id, WBS_DICTS, tenant_id)
    await session.execute(
        sa.text("UPDATE wbs_nodes SET budget_spent = 125.25 WHERE project_id = :pid AND code = '1.1'"), {"pid": project_id}
    )

    node_id = (
        await session.execute(sa.text("SELECT id FROM wbs_nodes WHERE project_id = :pid AND code = '1.1'"), {"pid": project_id})
    ).scalar_one()
    clauses = await build_schedule_clauses(session, project_id, tenant_id)
    assert "Quay wall: 2026-10-01 to 2027-06-30" in [clause.text for clause in clauses]
    timeline = next(clause for clause in clauses if clause.id == f"schedule-timeline-{project_id}")
    assert [item["wbs_node_id"] for item in timeline.data["schedule_items"]] == [str(node_id)]
    spent = await SQLAlchemyBudgetRepository(session).get_total_spent_by_project(project_id, tenant_id)
    assert float(spent) == 125.25


async def test_mcp_views_expose_only_the_canonical_wbs(session: AsyncSession) -> None:
    from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository

    tenant_id, project_id = await _project(session)
    await SQLAlchemyWBSRepository(session).bulk_create_from_dicts(project_id, WBS_DICTS, tenant_id)
    rows = (await session.execute(sa.text("SELECT wbs_code, title, parent_id FROM v_project_wbs ORDER BY wbs_code"))).all()
    assert [r.wbs_code for r in rows] == ["1", "1.1", "1.1.1", "1.2"]
    dependencies = (
        await session.execute(
            sa.text(
                "SELECT DISTINCT v.relname, t.relname AS reads FROM pg_depend d JOIN pg_rewrite r ON r.oid = d.objid "
                "JOIN pg_class v ON v.oid = r.ev_class JOIN pg_class t ON t.oid = d.refobjid "
                "WHERE v.relname IN ('v_project_wbs', 'v_raci_matrix') "
                "AND t.relname IN ('wbs_nodes', 'procurement_wbs_items', 'wbs_items')"
            )
        )
    ).all()
    assert sorted((d.relname, d.reads) for d in dependencies) == [("v_project_wbs", "wbs_nodes"), ("v_raci_matrix", "wbs_nodes")]
