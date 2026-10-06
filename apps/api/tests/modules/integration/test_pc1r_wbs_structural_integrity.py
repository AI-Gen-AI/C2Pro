"""PC-1R (#886, ADR-029) -- canonical WBS structural integrity on a REAL PostgreSQL.

TS-INT-PC1R-WBS-001. The project is the implicit root: top-level branches are
``parent_id IS NULL`` and there may be many of them. Hierarchy authority is
``(parent_id, sort_order)``; ``depth``/``lft``/``rgt`` are derived caches and the
visible ``code`` is display data, never identity.

Since PC-2a.2 (#896) governed live content changes ONLY through the governed approve = apply
of a WBS change set, in every authority state: every direct repository write (create, bulk
create, reparent, recode, reposition, delete) is refused with ``WBS_GOVERNANCE_REQUIRED`` and
changes nothing (the governed equivalents -- minted ids, identity-preserving recode/move,
dense order, links failing closed, serialized concurrent applies -- are proven in
tests/modules/integration/test_pc2a2_wbs_governed_apply.py). The DATABASE structural invariants
below still guard the apply path itself, so they are exercised inside the database state of an
in-flight apply (``governed_apply_state``) and must fail for their OWN reason:

* parenting is same-tenant AND same-project;
* deleting a document, a parent row, or a node with RACI/BOM links never silently deletes or
  re-roots governed scope or downstream relationships;
* sibling order is ``sort_order`` (not code); reorder / code swaps work inside one
  transaction (deferred uniqueness);
* corrupting the derived depth cache or forming a cycle cannot commit.
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
from src.procurement.adapters.persistence.models import BOMItemORM
from src.procurement.adapters.persistence.wbs_repository import (
    SQLAlchemyWBSRepository,
    WBSGovernanceRequiredError,
)
from src.procurement.application.dtos import WBSItemCreate
from src.procurement.application.use_cases.wbs_use_cases import CreateWBSItemUseCase
from src.procurement.domain.models import WBSItem
from src.shared_kernel.enums import RACIRole
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM
from src.wbs.adapters.persistence.models import WBSNodeORM
from tests.support.legacy_wbs import governed_apply_state, seed_legacy_wbs

pytestmark = pytest.mark.asyncio

DB_ERRORS = (IntegrityError, DBAPIError)
GOVERNANCE_REQUIRED = "WBS_GOVERNANCE_REQUIRED"


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
    """A live row loaded out of band (LEGACY_UNGOVERNED data: no application path writes it)."""
    (created,) = await seed_legacy_wbs(db, tenant_id, [
        WBSItem(project_id=project_id, code=code, name=f"Node {code}", level=1,
                parent_id=parent_id, source_document_id=source_document_id)])
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


async def _expect_structural_rejection(db: AsyncSession, tenant_id: UUID, project_id: UUID, sql: str,
                                      params: dict[str, Any]) -> None:
    """Even inside an in-flight apply, the statement (or the commit running the deferred checks)
    is rejected -- by a structural constraint, never merely by the governance guard."""
    with pytest.raises(DB_ERRORS) as caught:
        async with governed_apply_state(db, tenant_id, project_id):
            await db.execute(text(sql), params)
        await db.commit()
    await db.rollback()
    assert GOVERNANCE_REQUIRED not in str(caught.value), "rejected by the governance guard, not the invariant"


async def _structural_write(db: AsyncSession, tenant_id: UUID, project_id: UUID, *statements: tuple[str, dict[str, Any]]) -> None:
    """Statements that the structural invariants accept, committed as an apply would."""
    async with governed_apply_state(db, tenant_id, project_id):
        for sql, params in statements:
            await db.execute(text(sql), params)
    await db.commit()


async def _expect_refused(db: AsyncSession, write: Any) -> None:
    with pytest.raises(WBSGovernanceRequiredError) as caught:
        await write()
    assert (caught.value.code, caught.value.status_code) == (GOVERNANCE_REQUIRED, 409)
    await db.rollback()


# --------------------------------------------------------------------------- direct writes are refused (PC-2a.2)
async def test_every_direct_repository_write_is_refused_and_changes_nothing(db: AsyncSession) -> None:
    """R1/R2/R5/R6/R8/R9/R12/R14/R15/bulk: what these writes used to do is now a governed apply."""
    tenant = await _tenant(db)
    project, other = await _project(db, tenant), await _project(db, tenant)
    a = await _node(db, tenant, project, "A")
    b = await _node(db, tenant, project, "B")
    b1 = await _node(db, tenant, project, "B.1", parent_id=b.id)
    foreign = await _node(db, tenant, other, "1")
    await _raci(db, tenant, project, b1.id)
    await _bom(db, project, a.id)
    before = await _rows(db, project)
    repository = SQLAlchemyWBSRepository(db)

    def changed(item: WBSItem, **values: Any) -> WBSItem:
        for key, value in values.items():
            setattr(item, key, value)
        return item

    async def fresh(node: WBSItem) -> WBSItem:
        item = await repository.get_by_id(node.id, tenant)
        assert item is not None
        return item

    writes = [
        lambda: repository.create(tenant, WBSItem(project_id=project, code="C", name="c", level=1)),
        lambda: repository.create(tenant, WBSItem(project_id=project, code="X", name="x", level=2, parent_id=foreign.id)),
        lambda: repository.create(tenant, WBSItem(id=a.id, project_id=project, code="2", name="caller id", level=1)),
        lambda: repository.bulk_create([WBSItem(project_id=project, code="1", name="P", level=1)], tenant),
        lambda: repository.bulk_create_from_dicts(project, [{"code": "1", "name": "P"}], tenant),
        lambda: repository.delete(a.id, tenant),   # BOM-linked
        lambda: repository.delete(b.id, tenant),   # RACI in its subtree
        lambda: repository.delete(b1.id, tenant),
    ]
    for write in writes:
        await _expect_refused(db, write)
    for node, values in ((a, {"code": "ZZZ"}), (a, {"name": "Renamed"}), (b, {"parent_id": a.id}),
                         (b, {"parent_id": foreign.id}), (b, {"sort_order": 1}), (a, {"parent_id": b1.id})):
        item = changed(await fresh(node), **values)
        await _expect_refused(db, lambda item=item, node=node: repository.update(node.id, item, tenant))
    use_case = CreateWBSItemUseCase(repository)
    with pytest.raises((ValueError, WBSGovernanceRequiredError)):  # R14: never a foreign parent via its code
        await use_case.execute(WBSItemCreate(project_id=project, parent_id=foreign.id, wbs_code="1.1", name="child",
                                             level=2), tenant)
    await db.rollback()
    assert await _rows(db, project) == before
    assert await repository.delete(uuid4(), tenant) is False  # an unknown node is still simply "not found"


async def test_concurrent_direct_writes_are_refused_without_waiting(test_session_factory: async_sessionmaker) -> None:
    """C1/C2/C3: direct structural writes no longer compete for the project lock -- they are refused."""
    async with test_session_factory() as setup:
        tenant = await _tenant(setup)
        project = await _project(setup, tenant)
        a = await _node(setup, tenant, project, "A")
        before = await _rows(setup, project)

    async def attempt(session: AsyncSession) -> str:
        try:
            await SQLAlchemyWBSRepository(session).create(tenant, WBSItem(project_id=project, code="N", name="n", level=1))
            await session.commit()
            return "committed"
        except WBSGovernanceRequiredError:
            await session.rollback()
            return "refused"

    async with test_session_factory() as s1, test_session_factory() as s2:
        outcomes = await asyncio.wait_for(asyncio.gather(attempt(s1), attempt(s2)), timeout=10)
    assert outcomes == ["refused", "refused"]
    async with test_session_factory() as check:
        assert await _rows(check, project) == before and a.id in before


# --------------------------------------------------------------------------- R1 / R2 (database)
async def test_r1_r2_the_database_rejects_a_parent_from_another_project(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project_a, project_b = await _project(db, tenant), await _project(db, tenant)
    node = await _node(db, tenant, project_a, "1")
    foreign_parent = await _node(db, tenant, project_b, "1")
    await _expect_structural_rejection(
        db, tenant, project_a,
        "INSERT INTO wbs_nodes (id, project_id, tenant_id, parent_id, code, name, lft, rgt, depth, sort_order) "
        "VALUES (:id, :pid, :tid, :parent, 'X', 'x', 1, 2, 1, 1)",
        {"id": uuid4(), "pid": project_a, "tid": tenant, "parent": foreign_parent.id},
    )
    await _expect_structural_rejection(
        db, tenant, project_a, "UPDATE wbs_nodes SET parent_id = :parent, depth = 1 WHERE id = :id",
        {"parent": foreign_parent.id, "id": node.id},
    )
    assert (await _rows(db, project_a))[node.id]["parent_id"] is None


async def test_r14_seeded_children_are_parented_by_id_not_code(db: AsyncSession) -> None:
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

    await _expect_structural_rejection(db, tenant, project, "DELETE FROM wbs_nodes WHERE id = :id", {"id": parent.id})
    rows = await _rows(db, project)
    assert rows[child.id]["parent_id"] == parent.id


# --------------------------------------------------------------------------- R5 / R6 / R7
async def test_r5_r6_the_database_never_deletes_a_node_with_raci_or_bom_links(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    raci_node = await _node(db, tenant, project, "1")
    bom_node = await _node(db, tenant, project, "2")
    raci_id = await _raci(db, tenant, project, raci_node.id)
    bom_id = await _bom(db, project, bom_node.id)

    for node in (raci_node, bom_node):
        await _expect_structural_rejection(db, tenant, project, "DELETE FROM wbs_nodes WHERE id = :id", {"id": node.id})
    assert await db.get(StakeholderWBSRaciORM, raci_id, populate_existing=True) is not None
    bom = await db.get(BOMItemORM, bom_id, populate_existing=True)
    assert bom is not None and bom.wbs_item_id == bom_node.id


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


# --------------------------------------------------------------------------- R8
async def test_r8_sibling_order_is_sort_order_not_code(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    later_lexically = await _node(db, tenant, project, "1.2")
    earlier_lexically = await _node(db, tenant, project, "1.10")

    tree = await SQLAlchemyWBSRepository(db).get_tree(project, tenant)
    assert [item.code for item in tree] == ["1.2", "1.10"]
    assert [item.sort_order for item in tree] == [1, 2]
    assert [item.id for item in tree] == [later_lexically.id, earlier_lexically.id]


# --------------------------------------------------------------------------- R10 / R11
async def test_r10_sort_order_swap_in_one_transaction_and_duplicate_rejected(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    a = await _node(db, tenant, project, "A")
    b = await _node(db, tenant, project, "B")

    await _structural_write(db, tenant, project,
                            ("UPDATE wbs_nodes SET sort_order = 2 WHERE id = :id", {"id": a.id}),
                            ("UPDATE wbs_nodes SET sort_order = 1 WHERE id = :id", {"id": b.id}))
    rows = await _rows(db, project)
    assert (rows[a.id]["sort_order"], rows[b.id]["sort_order"]) == (2, 1)

    # Two TOP-LEVEL siblings (parent_id NULL) may not share a position: NULLS NOT DISTINCT.
    await _expect_structural_rejection(db, tenant, project, "UPDATE wbs_nodes SET sort_order = 1 WHERE id = :id",
                                       {"id": a.id})


async def test_r11_code_swap_in_one_transaction(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    a = await _node(db, tenant, project, "A")
    b = await _node(db, tenant, project, "B")

    await _structural_write(db, tenant, project,
                            ("UPDATE wbs_nodes SET code = 'B' WHERE id = :id", {"id": a.id}),
                            ("UPDATE wbs_nodes SET code = 'A' WHERE id = :id", {"id": b.id}))
    rows = await _rows(db, project)
    assert (rows[a.id]["code"], rows[b.id]["code"]) == ("B", "A")

    await _expect_structural_rejection(db, tenant, project, "UPDATE wbs_nodes SET code = 'A' WHERE id = :id",
                                       {"id": a.id})


# --------------------------------------------------------------------------- R13
async def test_r13_corrupt_depth_cache_cannot_commit(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    parent = await _node(db, tenant, project, "1")
    child = await _node(db, tenant, project, "1.1", parent_id=parent.id)

    # depth is a cache outside the governance guard: rejected by its own check, apply or not
    with pytest.raises(DB_ERRORS):
        await db.execute(text("UPDATE wbs_nodes SET depth = 5 WHERE id = :id"), {"id": child.id})
        await db.commit()
    await db.rollback()
    await _expect_structural_rejection(db, tenant, project, "UPDATE wbs_nodes SET depth = 3 WHERE id = :id",
                                       {"id": parent.id})


async def test_r13_raw_sql_cycle_cannot_commit(db: AsyncSession) -> None:
    tenant = await _tenant(db)
    project = await _project(db, tenant)
    a = await _node(db, tenant, project, "A")
    b = await _node(db, tenant, project, "B", parent_id=a.id)

    await _expect_structural_rejection(
        db, tenant, project, "UPDATE wbs_nodes SET parent_id = :b, depth = 2 WHERE id = :a", {"a": a.id, "b": b.id}
    )


# --------------------------------------------------------------------------- R18
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
