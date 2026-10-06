"""PC-1R (#886, ADR-029) -- canonical WBS structural integrity on a REAL PostgreSQL.

TS-INT-PC1R-WBS-001. The project is the implicit root: top-level branches are
``parent_id IS NULL`` and there may be many of them. Hierarchy authority is
``(parent_id, sort_order)``; ``depth``/``lft``/``rgt`` are derived caches and the
visible ``code`` is display data, never identity. This suite proves:

* parenting is same-tenant AND same-project, in the repository and in the database;
* deleting a document, a parent row, or a node with RACI/BOM links never silently
  deletes or re-roots governed scope or downstream relationships;
* sibling order is ``sort_order`` (not code); recode keeps id, links and position;
* reorder / code swaps work inside one transaction (deferred uniqueness);
* corrupting the derived depth cache or forming a cycle cannot commit;
* node ids are minted by the repository, never taken from the caller;
* structural writes on one project serialize on the project row lock.

No baseline / change-set / approval semantics are exercised here (PC-2a).
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.auth.models import SubscriptionPlan, Tenant
from src.core.exceptions import ConflictError
from src.procurement.adapters.persistence.models import BOMItemORM
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.application.dtos import WBSItemCreate
from src.procurement.application.use_cases.wbs_use_cases import CreateWBSItemUseCase
from src.procurement.domain.models import WBSItem
from src.shared_kernel.enums import RACIRole
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM
from src.wbs.adapters.persistence.models import WBSNodeORM

pytestmark = pytest.mark.asyncio

DB_ERRORS = (IntegrityError, DBAPIError)


# --------------------------------------------------------------------------- helpers
async def _tenant(db: AsyncSession) -> UUID:
    tenant_id = uuid4()
    db.add(Tenant(id=tenant_id, name="t", slug=f"t-{tenant_id.hex[:8]}",
                  subscription_plan=SubscriptionPlan.PROFESSIONAL, ai_budget_monthly=100.0))
    await db.commit()
    return tenant_id


async def _project(db: AsyncSession, tenant_id: UUID) -> UUID:
    project_id = uuid4()
    await db.execute(
        text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, "
             "updated_at) VALUES (:id, :tid, 'pc1r', :code, 'construction', 'active', 'EUR', now(), now())"),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return project_id


async def _document(db: AsyncSession, tenant_id: UUID, project_id: UUID) -> UUID:
    document_id = uuid4()
    await db.execute(
        text("INSERT INTO documents (id, tenant_id, project_id, document_type, filename, upload_status, version, "
             "storage_encrypted, document_metadata, created_at, updated_at) VALUES "
             "(:id, :tid, :pid, 'contract', 'c.pdf', 'uploaded', 1, true, '{}'::jsonb, now(), now())"),
        {"id": document_id, "tid": tenant_id, "pid": project_id},
    )
    await db.commit()
    return document_id


async def _node(db: AsyncSession, tenant_id: UUID, project_id: UUID, code: str, *,
                parent_id: UUID | None = None, source_document_id: UUID | None = None) -> WBSItem:
    created = await SQLAlchemyWBSRepository(db).create(
        tenant_id,
        WBSItem(project_id=project_id, code=code, name=f"Node {code}", level=1,
                parent_id=parent_id, source_document_id=source_document_id),
    )
    await db.commit()
    return created


async def _rows(db: AsyncSession, project_id: UUID) -> dict[UUID, dict[str, Any]]:
    await db.commit()
    result = await db.execute(
        select(WBSNodeORM.id, WBSNodeORM.code, WBSNodeORM.parent_id, WBSNodeORM.sort_order,
               WBSNodeORM.depth, WBSNodeORM.lft, WBSNodeORM.rgt)
        .where(WBSNodeORM.project_id == project_id)
        .execution_options(populate_existing=True)
    )
    return {row.id: dict(row._mapping) for row in result.all()}


def _assert_nested_set_consistent(rows: dict[UUID, dict[str, Any]]) -> None:
    """lft/rgt/depth are a valid nested set derived from (parent_id, sort_order)."""
    children: dict[UUID | None, list[dict[str, Any]]] = {}
    for row in rows.values():
        children.setdefault(row["parent_id"], []).append(row)
    counter = 0
    expected: dict[UUID, tuple[int, int, int]] = {}

    def visit(row: dict[str, Any], depth: int) -> None:
        nonlocal counter
        counter += 1
        left = counter
        for child in sorted(children.get(row["id"], []), key=lambda r: (r["sort_order"], str(r["id"]))):
            visit(child, depth + 1)
        counter += 1
        expected[row["id"]] = (left, counter, depth)

    for top in sorted(children.get(None, []), key=lambda r: (r["sort_order"], str(r["id"]))):
        visit(top, 0)
    assert len(expected) == len(rows), "every node must be reachable from a top-level branch"
    assert {node_id: (r["lft"], r["rgt"], r["depth"]) for node_id, r in rows.items()} == expected
    for siblings in children.values():
        assert sorted(r["sort_order"] for r in siblings) == list(range(1, len(siblings) + 1))


async def _raci(db: AsyncSession, tenant_id: UUID, project_id: UUID, node_id: UUID) -> UUID:
    stakeholder = StakeholderORM(id=uuid4(), tenant_id=tenant_id, project_id=project_id, name="PM")
    db.add(stakeholder)
    await db.flush()
    raci = StakeholderWBSRaciORM(
        tenant_id=tenant_id, project_id=project_id, stakeholder_id=stakeholder.id, wbs_item_id=node_id,
        raci_role=RACIRole.ACCOUNTABLE, generated_automatically=False, manually_verified=True,
    )
    db.add(raci)
    await db.commit()
    return raci.id


async def _bom(db: AsyncSession, project_id: UUID, node_id: UUID) -> UUID:
    bom = BOMItemORM(id=uuid4(), project_id=project_id, item_name="Concrete", quantity=Decimal("10"),
                     wbs_item_id=node_id)
    db.add(bom)
    await db.commit()
    return bom.id


async def _expect_db_rejection(db: AsyncSession, sql: str, params: dict[str, Any]) -> None:
    """The statement (or the commit that validates deferred checks) is rejected."""
    with pytest.raises(DB_ERRORS):
        await db.execute(text(sql), params)
        await db.commit()
    await db.rollback()


# --------------------------------------------------------------------------- R1 / R2 / R14
async def test_r1_create_rejects_parent_from_another_project_in_same_tenant(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project_a, project_b = await _project(db, tenant), await _project(db, tenant)
    foreign_parent = await _node(db, tenant, project_b, "1")

    with pytest.raises(ValueError):
        await SQLAlchemyWBSRepository(db).create(
            tenant, WBSItem(project_id=project_a, code="1.1", name="x", level=2, parent_id=foreign_parent.id)
        )
    await db.rollback()
    assert await _rows(db, project_a) == {}

    await _expect_db_rejection(
        db,
        "INSERT INTO wbs_nodes (id, project_id, tenant_id, parent_id, code, name, lft, rgt, depth, sort_order) "
        "VALUES (:id, :pid, :tid, :parent, 'X', 'x', 1, 2, 1, 1)",
        {"id": uuid4(), "pid": project_a, "tid": tenant, "parent": foreign_parent.id},
    )


async def test_r2_reparent_rejects_parent_from_another_project(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project_a, project_b = await _project(db, tenant), await _project(db, tenant)
    node = await _node(db, tenant, project_a, "1")
    foreign_parent = await _node(db, tenant, project_b, "9")
    repository = SQLAlchemyWBSRepository(db)

    existing = await repository.get_by_id(node.id, tenant)
    assert existing is not None
    existing.parent_id = foreign_parent.id
    with pytest.raises(ValueError):
        await repository.update(node.id, existing, tenant)
    await db.rollback()
    assert (await _rows(db, project_a))[node.id]["parent_id"] is None

    await _expect_db_rejection(
        db, "UPDATE wbs_nodes SET parent_id = :parent, depth = 1 WHERE id = :id",
        {"parent": foreign_parent.id, "id": node.id},
    )


async def test_r14_use_case_never_links_a_foreign_parent_through_its_code(db: AsyncSession) -> None:
    """The old use case resolved parent_id -> parent.code in ANY project, then re-resolved
    that code in the child's project: it silently linked an unrelated same-code node."""
    tenant = await _tenant(db)
    project_a, project_b = await _project(db, tenant), await _project(db, tenant)
    await _node(db, tenant, project_a, "1")  # same visible code as the foreign parent
    foreign_parent = await _node(db, tenant, project_b, "1")

    use_case = CreateWBSItemUseCase(SQLAlchemyWBSRepository(db))
    with pytest.raises(ValueError):
        await use_case.execute(
            WBSItemCreate(project_id=project_a, parent_id=foreign_parent.id, wbs_code="1.1", name="child",
                          level=2),
            tenant,
        )
    await db.rollback()
    assert {r["code"] for r in (await _rows(db, project_a)).values()} == {"1"}


async def test_r14_children_are_parented_by_id_not_code(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    parent = await _node(db, tenant, project, "A")
    child = await _node(db, tenant, project, "zz-unrelated-code", parent_id=parent.id)

    rows = await _rows(db, project)
    assert rows[child.id]["parent_id"] == parent.id
    assert rows[child.id]["depth"] == 1
    _assert_nested_set_consistent(rows)


# --------------------------------------------------------------------------- R3 / R4
async def test_r3_document_deletion_never_deletes_or_reroots_wbs(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    document = await _document(db, tenant, project)
    parent = await _node(db, tenant, project, "1", source_document_id=document)
    child = await _node(db, tenant, project, "1.1", parent_id=parent.id)

    await db.execute(text("DELETE FROM documents WHERE id = :id"), {"id": document})
    await db.commit()

    rows = await _rows(db, project)
    assert set(rows) == {parent.id, child.id}
    assert rows[child.id]["parent_id"] == parent.id
    source = (await db.execute(text("SELECT source_document_id FROM wbs_nodes WHERE id = :id"),
                               {"id": parent.id})).scalar_one()
    assert source is None
    _assert_nested_set_consistent(rows)


async def test_r4_raw_parent_delete_cannot_silently_reroot_children(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    parent = await _node(db, tenant, project, "1")
    child = await _node(db, tenant, project, "1.1", parent_id=parent.id)

    await _expect_db_rejection(db, "DELETE FROM wbs_nodes WHERE id = :id", {"id": parent.id})
    rows = await _rows(db, project)
    assert rows[child.id]["parent_id"] == parent.id


# --------------------------------------------------------------------------- R5 / R6 / R7
async def test_r5_deleting_a_node_with_raci_is_a_conflict_and_keeps_raci(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    parent = await _node(db, tenant, project, "1")
    child = await _node(db, tenant, project, "1.1", parent_id=parent.id)
    raci_id = await _raci(db, tenant, project, child.id)

    with pytest.raises(ConflictError):
        await SQLAlchemyWBSRepository(db).delete(parent.id, tenant)  # the subtree holds RACI
    await db.rollback()
    assert set(await _rows(db, project)) == {parent.id, child.id}
    assert await db.get(StakeholderWBSRaciORM, raci_id, populate_existing=True) is not None

    await _expect_db_rejection(db, "DELETE FROM wbs_nodes WHERE id = :id", {"id": child.id})
    assert await db.get(StakeholderWBSRaciORM, raci_id, populate_existing=True) is not None


async def test_r6_deleting_a_node_with_bom_links_is_a_conflict_and_keeps_the_link(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    node = await _node(db, tenant, project, "1")
    bom_id = await _bom(db, project, node.id)

    with pytest.raises(ConflictError):
        await SQLAlchemyWBSRepository(db).delete(node.id, tenant)
    await db.rollback()

    await _expect_db_rejection(db, "DELETE FROM wbs_nodes WHERE id = :id", {"id": node.id})
    bom = await db.get(BOMItemORM, bom_id, populate_existing=True)
    assert bom is not None and bom.wbs_item_id == node.id


async def test_r5_unlinked_subtree_delete_still_works_and_compacts_order(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    first = await _node(db, tenant, project, "1")
    second = await _node(db, tenant, project, "2")
    await _node(db, tenant, project, "2.1", parent_id=second.id)
    third = await _node(db, tenant, project, "3")

    assert await SQLAlchemyWBSRepository(db).delete(second.id, tenant) is True
    await db.commit()
    rows = await _rows(db, project)
    assert set(rows) == {first.id, third.id}
    assert (rows[first.id]["sort_order"], rows[third.id]["sort_order"]) == (1, 2)
    _assert_nested_set_consistent(rows)


async def test_r7_project_deletion_still_cascades_everything(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    parent = await _node(db, tenant, project, "1")
    child = await _node(db, tenant, project, "1.1", parent_id=parent.id)
    raci_id = await _raci(db, tenant, project, child.id)
    bom_id = await _bom(db, project, parent.id)

    await db.execute(text("DELETE FROM projects WHERE id = :id"), {"id": project})
    await db.commit()
    assert await _rows(db, project) == {}
    assert await db.get(StakeholderWBSRaciORM, raci_id, populate_existing=True) is None
    assert await db.get(BOMItemORM, bom_id, populate_existing=True) is None


# --------------------------------------------------------------------------- R8 / R9
async def test_r8_sibling_order_is_sort_order_not_code(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    later_lexically = await _node(db, tenant, project, "1.2")
    earlier_lexically = await _node(db, tenant, project, "1.10")

    tree = await SQLAlchemyWBSRepository(db).get_tree(project, tenant)
    assert [item.code for item in tree] == ["1.2", "1.10"]
    assert [item.sort_order for item in tree] == [1, 2]
    assert [item.id for item in tree] == [later_lexically.id, earlier_lexically.id]


async def test_r9_recode_keeps_identity_links_and_position(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    first = await _node(db, tenant, project, "A")
    second = await _node(db, tenant, project, "B")
    raci_id = await _raci(db, tenant, project, first.id)
    bom_id = await _bom(db, project, first.id)
    repository = SQLAlchemyWBSRepository(db)

    existing = await repository.get_by_id(first.id, tenant)
    assert existing is not None
    existing.code = "ZZZ"
    updated = await repository.update(first.id, existing, tenant)
    await db.commit()

    assert updated is not None and updated.id == first.id and updated.code == "ZZZ"
    rows = await _rows(db, project)
    assert (rows[first.id]["code"], rows[first.id]["sort_order"]) == ("ZZZ", 1)
    assert rows[second.id]["sort_order"] == 2
    raci = await db.get(StakeholderWBSRaciORM, raci_id, populate_existing=True)
    bom = await db.get(BOMItemORM, bom_id, populate_existing=True)
    assert raci is not None and raci.wbs_item_id == first.id
    assert bom is not None and bom.wbs_item_id == first.id


async def test_r8_explicit_position_reorders_siblings(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    a = await _node(db, tenant, project, "A")
    b = await _node(db, tenant, project, "B")
    c = await _node(db, tenant, project, "C")
    repository = SQLAlchemyWBSRepository(db)

    moved = await repository.get_by_id(c.id, tenant)
    assert moved is not None
    moved.sort_order = 1
    await repository.update(c.id, moved, tenant)
    await db.commit()

    rows = await _rows(db, project)
    assert [rows[x.id]["sort_order"] for x in (c, a, b)] == [1, 2, 3]
    _assert_nested_set_consistent(rows)


# --------------------------------------------------------------------------- R10 / R11
async def test_r10_sort_order_swap_in_one_transaction_and_duplicate_rejected(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    a = await _node(db, tenant, project, "A")
    b = await _node(db, tenant, project, "B")

    await db.execute(text("UPDATE wbs_nodes SET sort_order = 2 WHERE id = :id"), {"id": a.id})
    await db.execute(text("UPDATE wbs_nodes SET sort_order = 1 WHERE id = :id"), {"id": b.id})
    await db.commit()
    rows = await _rows(db, project)
    assert (rows[a.id]["sort_order"], rows[b.id]["sort_order"]) == (2, 1)

    # Two TOP-LEVEL siblings (parent_id NULL) may not share a position: NULLS NOT DISTINCT.
    await _expect_db_rejection(db, "UPDATE wbs_nodes SET sort_order = 1 WHERE id = :id", {"id": a.id})


async def test_r11_code_swap_in_one_transaction(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    a = await _node(db, tenant, project, "A")
    b = await _node(db, tenant, project, "B")

    await db.execute(text("UPDATE wbs_nodes SET code = 'B' WHERE id = :id"), {"id": a.id})
    await db.execute(text("UPDATE wbs_nodes SET code = 'A' WHERE id = :id"), {"id": b.id})
    await db.commit()
    rows = await _rows(db, project)
    assert (rows[a.id]["code"], rows[b.id]["code"]) == ("B", "A")

    await _expect_db_rejection(db, "UPDATE wbs_nodes SET code = 'A' WHERE id = :id", {"id": a.id})


# --------------------------------------------------------------------------- R12 / R13
async def test_r12_move_keeps_identity_and_subtree_and_recomputes_caches(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    a = await _node(db, tenant, project, "A")
    b = await _node(db, tenant, project, "B")
    b1 = await _node(db, tenant, project, "B.1", parent_id=b.id)
    repository = SQLAlchemyWBSRepository(db)

    moving = await repository.get_by_id(b.id, tenant)
    assert moving is not None
    moving.parent_id = a.id
    await repository.update(b.id, moving, tenant)
    await db.commit()

    rows = await _rows(db, project)
    assert rows[b.id]["parent_id"] == a.id and rows[b1.id]["parent_id"] == b.id
    assert (rows[b.id]["depth"], rows[b1.id]["depth"]) == (1, 2)
    _assert_nested_set_consistent(rows)

    cyclic = await repository.get_by_id(a.id, tenant)
    assert cyclic is not None
    cyclic.parent_id = b1.id
    with pytest.raises(ValueError):
        await repository.update(a.id, cyclic, tenant)
    await db.rollback()


async def test_r12_reparent_without_a_new_position_appends_to_the_new_siblings(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    a = await _node(db, tenant, project, "A")
    a1 = await _node(db, tenant, project, "A.1", parent_id=a.id)
    a2 = await _node(db, tenant, project, "A.2", parent_id=a.id)
    b = await _node(db, tenant, project, "B")
    repository = SQLAlchemyWBSRepository(db)

    # The fetched item still carries its old position (2 among the top level); that is not a
    # request to land at position 2 under A.
    moving = await repository.get_by_id(b.id, tenant)
    assert moving is not None and moving.sort_order == 2
    moving.parent_id = a.id
    await repository.update(b.id, moving, tenant)
    await db.commit()

    rows = await _rows(db, project)
    assert [rows[x.id]["sort_order"] for x in (a1, a2, b)] == [1, 2, 3]
    _assert_nested_set_consistent(rows)


async def test_r13_corrupt_depth_cache_cannot_commit(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    parent = await _node(db, tenant, project, "1")
    child = await _node(db, tenant, project, "1.1", parent_id=parent.id)

    await _expect_db_rejection(db, "UPDATE wbs_nodes SET depth = 5 WHERE id = :id", {"id": child.id})
    await _expect_db_rejection(db, "UPDATE wbs_nodes SET depth = 3 WHERE id = :id", {"id": parent.id})


async def test_r13_raw_sql_cycle_cannot_commit(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    a = await _node(db, tenant, project, "A")
    b = await _node(db, tenant, project, "B", parent_id=a.id)

    await _expect_db_rejection(
        db, "UPDATE wbs_nodes SET parent_id = :b, depth = 2 WHERE id = :a", {"a": a.id, "b": b.id}
    )


# --------------------------------------------------------------------------- R15 / R18
async def test_r15_node_ids_are_minted_by_the_repository(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    existing = await _node(db, tenant, project, "1")

    created = await SQLAlchemyWBSRepository(db).create(
        tenant, WBSItem(id=existing.id, project_id=project, code="2", name="caller id", level=1)
    )
    await db.commit()
    assert created.id != existing.id
    rows = await _rows(db, project)
    assert rows[existing.id]["code"] == "1" and rows[created.id]["code"] == "2"


async def test_r18_project_is_the_implicit_root(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    for code in ("Civil", "Electrical", "Mechanical", "Commissioning"):
        await _node(db, tenant, project, code)

    rows = await _rows(db, project)
    assert len(rows) == 4 and all(r["parent_id"] is None and r["depth"] == 0 for r in rows.values())
    _assert_nested_set_consistent(rows)
    single_root_indexes = (
        await db.execute(text(
            "SELECT indexdef FROM pg_indexes WHERE tablename = 'wbs_nodes' "
            "AND indexdef ILIKE '%WHERE%parent_id IS NULL%'"
        ))
    ).scalars().all()
    assert single_root_indexes == []


async def test_bulk_create_mints_ids_and_keeps_batch_hierarchy(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    parent = WBSItem(project_id=project, code="1", name="Parent", level=1)
    child = WBSItem(project_id=project, code="1.1", name="Child", level=2, parent_id=parent.id)
    by_code = WBSItem(project_id=project, code="1.2", name="By code", level=2, parent_code="1")

    created = await SQLAlchemyWBSRepository(db).bulk_create([parent, child, by_code], tenant)
    await db.commit()
    assert [item.code for item in created] == ["1", "1.1", "1.2"]
    assert created[0].id != parent.id
    rows = await _rows(db, project)
    assert rows[created[1].id]["parent_id"] == created[0].id
    assert rows[created[2].id]["parent_id"] == created[0].id
    assert [rows[c.id]["sort_order"] for c in created] == [1, 1, 2]
    _assert_nested_set_consistent(rows)


# --------------------------------------------------------------------------- C1 / C2 / C3 (real concurrency)
async def _hold_then_release(first: AsyncSession, operation: Any, second_operation: Any) -> list[Any]:
    """Run ``operation`` in ``first`` (uncommitted), start ``second_operation`` concurrently,
    let it block on the project lock, then commit ``first``."""
    first_result = await operation()
    second_task = asyncio.create_task(second_operation())
    await asyncio.sleep(0.5)
    assert not second_task.done(), "the second structural write must wait for the project lock"
    await first.commit()
    second_result = await second_task
    return [first_result, second_result]


async def test_c1_concurrent_top_level_inserts_serialize(test_session_factory: async_sessionmaker) -> None:
    async with test_session_factory() as setup:
        tenant = await _tenant(setup)
        project = await _project(setup, tenant)

    async with test_session_factory() as s1, test_session_factory() as s2:
        async def first() -> WBSItem:
            return await SQLAlchemyWBSRepository(s1).create(
                tenant, WBSItem(project_id=project, code="A", name="a", level=1))

        async def second() -> WBSItem:
            created = await SQLAlchemyWBSRepository(s2).create(
                tenant, WBSItem(project_id=project, code="B", name="b", level=1))
            await s2.commit()
            return created

        await _hold_then_release(s1, first, second)

    async with test_session_factory() as check:
        rows = await _rows(check, project)
        assert sorted(r["sort_order"] for r in rows.values()) == [1, 2]
        _assert_nested_set_consistent(rows)


async def test_c2_concurrent_move_and_delete_serialize(test_session_factory: async_sessionmaker) -> None:
    async with test_session_factory() as setup:
        tenant = await _tenant(setup)
        project = await _project(setup, tenant)
        a = await _node(setup, tenant, project, "A")
        b = await _node(setup, tenant, project, "B")
        c = await _node(setup, tenant, project, "C")

    async with test_session_factory() as s1, test_session_factory() as s2:
        async def move() -> Any:
            repository = SQLAlchemyWBSRepository(s1)
            moving = await repository.get_by_id(c.id, tenant)
            assert moving is not None
            moving.parent_id = a.id
            return await repository.update(c.id, moving, tenant)

        async def delete() -> bool:
            deleted = await SQLAlchemyWBSRepository(s2).delete(b.id, tenant)
            await s2.commit()
            return deleted

        await _hold_then_release(s1, move, delete)

    async with test_session_factory() as check:
        rows = await _rows(check, project)
        assert set(rows) == {a.id, c.id} and rows[c.id]["parent_id"] == a.id
        _assert_nested_set_consistent(rows)


async def test_c3_concurrent_reparents_cannot_form_a_cycle(test_session_factory: async_sessionmaker) -> None:
    async with test_session_factory() as setup:
        tenant = await _tenant(setup)
        project = await _project(setup, tenant)
        a = await _node(setup, tenant, project, "A")
        b = await _node(setup, tenant, project, "B")

    async with test_session_factory() as s1, test_session_factory() as s2:
        async def a_under_b() -> Any:
            repository = SQLAlchemyWBSRepository(s1)
            node = await repository.get_by_id(a.id, tenant)
            assert node is not None
            node.parent_id = b.id
            return await repository.update(a.id, node, tenant)

        async def b_under_a() -> str:
            repository = SQLAlchemyWBSRepository(s2)
            node = await repository.get_by_id(b.id, tenant)
            assert node is not None
            node.parent_id = a.id
            try:
                await repository.update(b.id, node, tenant)
                await s2.commit()
                return "committed"
            except (ValueError, *DB_ERRORS):
                await s2.rollback()
                return "rejected"

        _, outcome = await _hold_then_release(s1, a_under_b, b_under_a)
        assert outcome == "rejected"

    async with test_session_factory() as check:
        rows = await _rows(check, project)
        assert rows[a.id]["parent_id"] == b.id and rows[b.id]["parent_id"] is None
        _assert_nested_set_consistent(rows)
