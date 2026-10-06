"""PC-2a.3 (#897) -- WBS authority enforcement across project consumers, on a real PostgreSQL.

TS-INT-PC2A3-WBS-001. Numbered tests follow the #897 RED matrix (1-25):
- candidate non-leakage (1-7);
- legacy (8-14);
- approved (15-20);
- date/cost honesty (21-22);
- link-write concurrency (23-25).

Every consumer asks the single authority resolver (``WBSGovernanceRepository.authority``). An
approved baseline confers authority on scope only (identity, hierarchy, order, code, name,
control level, decomposition, dictionary), never on the legacy date / cost fields.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.coherence.schedule_clause_builder import build_schedule_clauses
from src.core.exceptions import C2ProException
from src.procurement.adapters.persistence.bom_repository import SQLAlchemyBOMRepository
from src.procurement.adapters.persistence.budget_repository import SQLAlchemyBudgetRepository
from src.procurement.adapters.persistence.models import BOMItemORM
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.application.budget_use_cases import GetBudgetUseCase
from src.procurement.application.dtos import BOMItemCreate
from src.procurement.application.use_cases.bom_use_cases import CreateBOMItemUseCase
from src.procurement.domain.models import BOMItem, WBSItem
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository
from src.projects.application.project_wbs_view import build_project_wbs_view
from src.reporting.adapters.sources.sqlalchemy_current_state_sources import (
    SqlAlchemyCurrentStateSources,
)
from src.reporting.application.current_state_projection import project_budget, project_wbs
from src.reporting.application.ports import SourceOk
from src.shared_kernel.enums import RACIRole
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.application.dtos import RaciAssignmentUpsertRequest
from src.stakeholders.application.get_raci_matrix_use_case import GetRaciMatrixUseCase
from src.stakeholders.application.upsert_raci_assignment_use_case import UpsertRaciAssignmentUseCase
from src.stakeholders.domain.models import RaciAssignment
from src.temporal.adapters.persistence.clause_impact_resolver import SqlAlchemyClauseImpactResolver
from src.wbs.adapters.persistence.governance_models import WBSBaselineORM
from src.wbs.adapters.persistence.governance_repository import WBSGovernanceRepository
from src.wbs.adapters.persistence.link_authority import (
    CANDIDATE_NOT_CANONICAL,
    NODE_NOT_CURRENT_BASELINE,
    NOT_APPROVED,
)
from src.wbs.adapters.persistence.models import WBSNodeORM
from src.wbs.application.governed_change_service import (
    AddNode,
    NodeSpec,
    RemoveNode,
    RetiredNodesLinkedError,
    WBSGovernedChangeService,
)
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import Scope, _project, _scope
from tests.modules.integration.test_pc2a2_wbs_governed_apply import (
    _approve,
    _baseline_one,
    _cmd,
    _cs,
    _new,
    _submit,
)
from tests.support.legacy_wbs import legacy_wbs_writes, seed_legacy_wbs

pytestmark = pytest.mark.asyncio

LEGACY_LABEL = "Unapproved / Legacy WBS"


# =========================================================================== state builders
async def _legacy(db: AsyncSession, s: Scope, *, dated: bool = False, spent: bool = False) -> list[UUID]:
    """Two LEGACY_UNGOVERNED rows (the production shape: data loaded before governance)."""
    start, end = datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 3, 1, tzinfo=UTC)
    items = await seed_legacy_wbs(db, s.tenant, [
        WBSItem(project_id=s.project, code=f"L-{index}", name=f"Legacy {index}", level=1,
                planned_start=start if dated else None, planned_end=end if dated else None,
                budget_allocated=Decimal("100") if spent else None,
                budget_spent=Decimal("40") if spent else Decimal(0))
        for index in (1, 2)
    ])
    await db.commit()
    return [item.id for item in items]


async def _draft_only(db: AsyncSession, s: Scope) -> list[UUID]:
    """A DRAFT candidate on a project with no live WBS (DRAFT_ONLY); returns the candidate ids."""
    change_set_id = await _new(db, s, "Proposed WBS")
    first = (await _cmd(db, s, change_set_id, AddNode(NodeSpec("Civil", "1")))).node_ids[0]
    second = (await _cmd(db, s, change_set_id, AddNode(NodeSpec("Electrical", "2")))).node_ids[0]
    return [first, second]


async def _approved(db: AsyncSession, s: Scope) -> dict[str, UUID]:
    """Baseline #1: Civil(1) > Earthworks(1.1), Foundations(1.2); Electrical(2)."""
    _, ids, _ = await _baseline_one(db, s)
    return ids


async def _draft_on_baseline(db: AsyncSession, s: Scope, ids: dict[str, UUID], *, submit: bool = False) -> tuple[UUID, UUID]:
    """Draft #2 on Baseline #1: retires Electrical(2) and proposes a new node 3; returns (change set, candidate)."""
    change_set_id = await _new(db, s, "Baseline 2")
    await _cmd(db, s, change_set_id, RemoveNode(ids["2"]))
    candidate = (await _cmd(db, s, change_set_id, AddNode(NodeSpec("Mechanical", "3")))).node_ids[0]
    if submit:
        await _submit(db, s, change_set_id)
    return change_set_id, candidate


async def _baseline_two(db: AsyncSession, s: Scope, ids: dict[str, UUID]) -> UUID:
    """Baseline #2 retires Electrical(2); returns the new candidate's (now live) id."""
    change_set_id, candidate = await _draft_on_baseline(db, s, ids, submit=True)
    await _approve(db, s, change_set_id)
    return candidate


async def _stakeholder(db: AsyncSession, tenant_id: UUID, project_id: UUID) -> UUID:
    stakeholder = StakeholderORM(id=uuid4(), tenant_id=tenant_id, project_id=project_id, name="PM")
    db.add(stakeholder)
    await db.commit()
    return stakeholder.id


# =========================================================================== consumers
async def _read(db: AsyncSession, s: Scope) -> dict[str, Any]:
    return await build_project_wbs_view(db, s.project, s.tenant)


def _read_ids(view: dict[str, Any]) -> set[str]:
    found: set[str] = set()

    def walk(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            found.add(str(node["id"]))
            walk(node.get("children") or [])

    walk(view["items"])
    return found


def _sources(db: AsyncSession) -> SqlAlchemyCurrentStateSources:
    @asynccontextmanager
    async def scope(_tenant_id: UUID) -> AsyncIterator[AsyncSession]:
        yield db

    return SqlAlchemyCurrentStateSources(current_user=SimpleNamespace(), session_scope=scope)  # type: ignore[arg-type]


async def _report(db: AsyncSession, s: Scope) -> Any:
    return project_wbs(SourceOk(await _sources(db).load_wbs(s.project, s.tenant)))


async def _raci(db: AsyncSession, s: Scope, node_id: UUID, stakeholder_id: UUID) -> Any:
    use_case = UpsertRaciAssignmentUseCase(SqlAlchemyStakeholderRepository(db), SQLAlchemyWBSRepository(db))
    return await use_case.execute(tenant_id=s.tenant, user_id=s.author.user_id, payload=RaciAssignmentUpsertRequest(
        task_id=node_id, stakeholder_id=stakeholder_id, role="RESPONSIBLE"))


async def _bom(db: AsyncSession, s: Scope, node_id: UUID | None, project_id: UUID | None = None) -> BOMItem:
    created = await CreateBOMItemUseCase(SQLAlchemyBOMRepository(db)).execute(BOMItemCreate(
        project_id=project_id or s.project, wbs_item_id=node_id, item_name="Rebar", quantity=Decimal("10")), s.tenant)
    await db.commit()
    return created


async def _rejected(db: AsyncSession, code: str, call: Callable[[], Awaitable[Any]]) -> C2ProException:
    with pytest.raises(C2ProException) as caught:
        await call()
    await db.rollback()
    assert caught.value.code == code, caught.value
    assert caught.value.status_code == 409
    return caught.value


def _assignment(s: Scope, stakeholder_id: UUID, node_id: UUID) -> RaciAssignment:
    """An automated (AI-generated shape) assignment, written straight through the repository."""
    return RaciAssignment(id=uuid4(), project_id=s.project, tenant_id=s.tenant, stakeholder_id=stakeholder_id,
                          wbs_item_id=node_id, raci_role=RACIRole.RESPONSIBLE, created_at=datetime.now(UTC))


async def _raci_rows(db: AsyncSession, project_id: UUID) -> int:
    return int(await db.scalar(select(func.count()).select_from(StakeholderWBSRaciORM)
                               .where(StakeholderWBSRaciORM.project_id == project_id)) or 0)


async def _bom_links(db: AsyncSession, project_id: UUID) -> int:
    return int(await db.scalar(select(func.count()).select_from(BOMItemORM).where(
        BOMItemORM.project_id == project_id, BOMItemORM.wbs_item_id.is_not(None))) or 0)


async def _impact_wbs_targets(db: AsyncSession, s: Scope, clause_id: UUID) -> list[Any]:
    """The temporal resolver's WBS targets for a clause already proven to be the earlier revision's."""
    resolver = SqlAlchemyClauseImpactResolver(db, tenant_id=s.tenant)

    async def verified(_source: Any) -> tuple[Any, None]:
        return SimpleNamespace(id=clause_id, project_id=s.project), None

    resolver._verified_clause = verified  # type: ignore[method-assign]  # noqa: SLF001
    result = await resolver.resolve(SimpleNamespace())  # type: ignore[arg-type]
    return [link.target for link in result.links if link.target.entity_type == "wbs_node"]


async def _link_clause(db: AsyncSession, node_ids: list[UUID]) -> UUID:
    """Point live nodes at a clause (a non-governed traceability column; loaded out of band, no FK)."""
    clause_id = uuid4()
    async with legacy_wbs_writes(db):
        await db.execute(text("UPDATE wbs_nodes SET source_clause_id = :c WHERE id = ANY(:ids)"),
                         {"c": clause_id, "ids": node_ids})
    await db.commit()
    return clause_id


async def _time_marker(clauses: list[Any]) -> dict[str, Any]:
    """The schedule evidence the coherence assembly derives from the WBS: exactly one withheld marker."""
    assert len(clauses) == 1, [clause.id for clause in clauses]
    data = clauses[0].data
    assert "schedule_items" not in data and "milestones" not in data
    return data


# =========================================================================== CANDIDATE NON-LEAKAGE 1-7
async def test_01_candidate_absent_from_wbs_read(db: AsyncSession) -> None:
    s = await _scope(db)
    candidates = await _draft_only(db, s)
    view = await _read(db, s)
    assert view["items"] == [] and view["total_items"] == 0
    assert view["authority"]["state"] == "NO_WBS" and view["authority"]["display_state"] == "DRAFT_ONLY"
    assert view["authority"]["approved"] is False and view["authority"]["draft_exists"] is True
    assert not {str(c) for c in candidates} & _read_ids(view)

    t = await _scope(db)
    ids = await _approved(db, t)
    _, candidate = await _draft_on_baseline(db, t, ids)
    view = await _read(db, t)
    assert str(candidate) not in _read_ids(view)
    assert _read_ids(view) == {str(i) for i in ids.values()}


async def test_02_candidate_absent_from_reporting(db: AsyncSession) -> None:
    s = await _scope(db)
    await _draft_only(db, s)
    section = await _report(db, s)
    assert section.data is None or section.data.item_count == 0
    assert section.status.value in {"empty", "EMPTY"} or section.data is None

    t = await _scope(db)
    ids = await _approved(db, t)
    _, candidate = await _draft_on_baseline(db, t, ids)
    section = await _report(db, t)
    assert section.data is not None and section.data.item_count == len(ids)
    assert candidate not in {root.id for root in section.data.roots}
    assert section.data.approved_scope_item_count == len(ids)


async def test_03_candidate_absent_from_coherence(db: AsyncSession) -> None:
    s = await _scope(db)
    await _draft_only(db, s)
    assert await build_schedule_clauses(db, s.project, s.tenant) == []

    t = await _scope(db)
    ids = await _approved(db, t)
    _, candidate = await _draft_on_baseline(db, t, ids)
    await db.execute(text("UPDATE wbs_nodes SET planned_start = now(), planned_end = now() WHERE project_id = :p"),
                     {"p": t.project})
    await db.commit()
    clauses = await build_schedule_clauses(db, t.project, t.tenant)
    assert str(candidate) not in repr([clause.data for clause in clauses])


async def test_04_candidate_cannot_receive_raci(db: AsyncSession) -> None:
    s = await _scope(db)
    candidates = await _draft_only(db, s)
    stakeholder = await _stakeholder(db, s.tenant, s.project)
    # the project has no approved WBS at all
    await _rejected(db, NOT_APPROVED, lambda: _raci(db, s, candidates[0], stakeholder))

    t = await _scope(db)
    ids = await _approved(db, t)
    _, candidate = await _draft_on_baseline(db, t, ids)
    stakeholder = await _stakeholder(db, t.tenant, t.project)
    await _rejected(db, CANDIDATE_NOT_CANONICAL, lambda: _raci(db, t, candidate, stakeholder))
    assert await _raci_rows(db, s.project) == 0 and await _raci_rows(db, t.project) == 0


async def test_05_candidate_cannot_receive_bom(db: AsyncSession) -> None:
    s = await _scope(db)
    candidates = await _draft_only(db, s)
    await _rejected(db, NOT_APPROVED, lambda: _bom(db, s, candidates[0]))

    t = await _scope(db)
    ids = await _approved(db, t)
    _, candidate = await _draft_on_baseline(db, t, ids)
    await _rejected(db, CANDIDATE_NOT_CANONICAL, lambda: _bom(db, t, candidate))
    assert await _bom_links(db, s.project) == 0 and await _bom_links(db, t.project) == 0


async def test_06_candidate_absent_from_temporal_impact(db: AsyncSession) -> None:
    s = await _scope(db)
    ids = await _approved(db, s)
    _, candidate = await _draft_on_baseline(db, s, ids)
    clause_id = await _link_clause(db, [ids["1"], ids["2"]])
    targets = await _impact_wbs_targets(db, s, clause_id)
    assert {target.entity_id for target in targets} == {ids["1"], ids["2"]}
    assert candidate not in {target.entity_id for target in targets}
    assert all(target.wbs_unapproved is False for target in targets)


async def test_07_baseline_n_stays_canonical_while_n_plus_1_is_drafted(db: AsyncSession) -> None:
    s = await _scope(db)
    ids = await _approved(db, s)
    change_set_id, candidate = await _draft_on_baseline(db, s, ids, submit=True)  # SUBMITTED, not applied
    stakeholder = await _stakeholder(db, s.tenant, s.project)

    view = await _read(db, s)
    assert view["authority"]["baseline_no"] == 1 and view["authority"]["draft_exists"] is True
    assert str(ids["2"]) in _read_ids(view) and str(candidate) not in _read_ids(view)
    section = await _report(db, s)
    assert section.data is not None and section.data.baseline_no == 1 and section.data.item_count == 4
    # the node the draft retires is still a current-baseline node until #2 commits
    await _raci(db, s, ids["2"], stakeholder)
    await _bom(db, s, ids["2"])
    await _rejected(db, CANDIDATE_NOT_CANONICAL, lambda: _raci(db, s, candidate, stakeholder))
    await _rejected(db, CANDIDATE_NOT_CANONICAL, lambda: _bom(db, s, candidate))
    clause_id = await _link_clause(db, [ids["2"]])
    assert [t.entity_id for t in await _impact_wbs_targets(db, s, clause_id)] == [ids["2"]]
    await db.execute(text("UPDATE wbs_nodes SET planned_start = now() WHERE id = :n"), {"n": ids["2"]})
    await db.commit()
    marker = await _time_marker(await build_schedule_clauses(db, s.project, s.tenant))
    assert marker["assessment_unavailable"] == {"TIME": "WBS_DATES_NOT_SCHEDULE_AUTHORITY"}
    assert (await _cs(db, change_set_id)).status == "SUBMITTED"


# =========================================================================== LEGACY 8-14
async def test_08_legacy_wbs_stays_readable(db: AsyncSession) -> None:
    s = await _scope(db)
    legacy = await _legacy(db, s)
    view = await _read(db, s)
    assert _read_ids(view) == {str(i) for i in legacy} and view["total_items"] == 2
    section = await _report(db, s)
    assert section.data is not None and section.data.item_count == 2


async def test_09_legacy_wbs_is_explicitly_unapproved(db: AsyncSession) -> None:
    s = await _scope(db)
    await _legacy(db, s)
    authority = (await _read(db, s))["authority"]
    assert authority["state"] == "LEGACY_UNGOVERNED" and authority["approved"] is False
    assert authority["baseline_no"] is None and authority["scope_label"] == LEGACY_LABEL
    section = await _report(db, s)
    assert section.data is not None
    assert (section.data.authority_state, section.data.approved, section.data.scope_label) == (
        "LEGACY_UNGOVERNED", False, LEGACY_LABEL)
    assert LEGACY_LABEL in (section.evidence_note or "")


async def test_10_legacy_wbs_is_excluded_from_approved_kpis(db: AsyncSession) -> None:
    s = await _scope(db)
    await _legacy(db, s, dated=True, spent=True)
    coverage = (await _read(db, s))["coverage"]
    assert coverage["approved_scope_items"] == 0 and coverage["unapproved_legacy_items"] == 2
    section = await _report(db, s)
    assert section.data is not None
    assert section.data.approved_scope_item_count == 0 and section.data.unapproved_item_count == 2


async def test_11_legacy_wbs_rejects_new_raci(db: AsyncSession) -> None:
    s = await _scope(db)
    legacy = await _legacy(db, s)
    stakeholder = await _stakeholder(db, s.tenant, s.project)
    error = await _rejected(db, NOT_APPROVED, lambda: _raci(db, s, legacy[0], stakeholder))
    assert error.details.get("authority_state") == "LEGACY_UNGOVERNED"
    # the repository is the choke point for every writer (AI generation included)
    await _rejected(db, NOT_APPROVED, lambda: SqlAlchemyStakeholderRepository(db).add_raci_assignment(
        _assignment(s, stakeholder, legacy[0]), tenant_id=s.tenant))
    assert await _raci_rows(db, s.project) == 0
    # a historical link stays readable, qualified -- never deleted
    async with legacy_wbs_writes(db):
        db.add(StakeholderWBSRaciORM(id=uuid4(), tenant_id=s.tenant, project_id=s.project, stakeholder_id=stakeholder,
                                     wbs_item_id=legacy[0], raci_role=RACIRole.RESPONSIBLE))
    await db.commit()
    matrix = await GetRaciMatrixUseCase(
        stakeholder_repository=SqlAlchemyStakeholderRepository(db), wbs_repository=SQLAlchemyWBSRepository(db),
        project_repository=SQLAlchemyProjectRepository(db), wbs_authority_reader=WBSGovernanceRepository(db),
    ).execute(s.project, s.tenant)
    row = next(row for row in matrix.matrix if row.task_id == legacy[0])
    assert len(row.assignments) == 1
    assert (row.wbs_authority_state, row.wbs_unapproved) == ("LEGACY_UNGOVERNED", True)


async def test_12_legacy_wbs_rejects_new_bom_links(db: AsyncSession) -> None:
    s = await _scope(db)
    legacy = await _legacy(db, s)
    await _rejected(db, NOT_APPROVED, lambda: _bom(db, s, legacy[0]))
    await _rejected(db, NOT_APPROVED, lambda: SQLAlchemyBOMRepository(db).bulk_create(
        [BOMItem(project_id=s.project, wbs_item_id=legacy[1], item_name="Cable", quantity=Decimal("1"))], s.tenant))
    assert await _bom_links(db, s.project) == 0
    # a BOM row without a WBS link is not a WBS link: unaffected
    await _bom(db, s, None)
    # a historical link stays readable
    async with legacy_wbs_writes(db):
        db.add(BOMItemORM(id=uuid4(), project_id=s.project, wbs_item_id=legacy[0], item_name="Old",
                          quantity=Decimal("1"), currency="EUR"))
    await db.commit()
    assert await _bom_links(db, s.project) == 1
    assert len(await SQLAlchemyBOMRepository(db).get_by_wbs_item(legacy[0], s.tenant)) == 1


async def test_13_legacy_wbs_is_not_wbs_coherence_or_temporal_truth(db: AsyncSession) -> None:
    s = await _scope(db)
    legacy = await _legacy(db, s, dated=True)
    marker = await _time_marker(await build_schedule_clauses(db, s.project, s.tenant))
    assert marker["assessment_unavailable"] == {"TIME": "WBS_NOT_APPROVED"}
    assert marker["category"] == "TIME"
    clause_id = await _link_clause(db, legacy)
    targets = await _impact_wbs_targets(db, s, clause_id)
    assert {t.entity_id for t in targets} == set(legacy)
    assert all(t.wbs_unapproved is True for t in targets)
    # no WBS at all: nothing derived, nothing withheld
    t = await _scope(db)
    assert await build_schedule_clauses(db, t.project, t.tenant) == []


async def test_14_legacy_wbs_is_never_auto_approved(db: AsyncSession) -> None:
    s = await _scope(db)
    legacy = await _legacy(db, s, dated=True, spent=True)
    before = (await db.execute(text("SELECT id, code, name, parent_id, sort_order, updated_at FROM wbs_nodes "
                                    "WHERE project_id = :p ORDER BY id"), {"p": s.project})).all()
    stakeholder = await _stakeholder(db, s.tenant, s.project)
    await _read(db, s)
    await _report(db, s)
    await build_schedule_clauses(db, s.project, s.tenant)
    await _rejected(db, NOT_APPROVED, lambda: _raci(db, s, legacy[0], stakeholder))
    await _rejected(db, NOT_APPROVED, lambda: _bom(db, s, legacy[0]))
    assert await db.scalar(select(func.count()).select_from(WBSBaselineORM)
                           .where(WBSBaselineORM.project_id == s.project)) == 0
    after = (await db.execute(text("SELECT id, code, name, parent_id, sort_order, updated_at FROM wbs_nodes "
                                   "WHERE project_id = :p ORDER BY id"), {"p": s.project})).all()
    assert before == after
    assert (await WBSGovernanceRepository(db).authority(s.project, s.tenant)).state.value == "LEGACY_UNGOVERNED"


# =========================================================================== APPROVED 15-20
async def test_15_approved_baseline_is_authoritative(db: AsyncSession) -> None:
    s = await _scope(db)
    ids = await _approved(db, s)
    view = await _read(db, s)
    baseline = await db.scalar(select(WBSBaselineORM).where(WBSBaselineORM.project_id == s.project))
    assert baseline is not None
    authority = view["authority"]
    assert authority["state"] == "APPROVED_BASELINE" and authority["approved"] is True
    assert (authority["baseline_id"], authority["baseline_no"], authority["tree_digest"]) == (
        str(baseline.id), 1, baseline.tree_digest)
    assert authority["scope_label"] == "Approved WBS Baseline #1"
    assert view["coverage"]["approved_scope_items"] == len(ids) and view["coverage"]["unapproved_legacy_items"] == 0
    section = await _report(db, s)
    assert section.data is not None
    assert (section.data.approved, section.data.approved_scope_item_count, section.data.unapproved_item_count) == (
        True, len(ids), 0)


async def test_16_approved_baseline_accepts_raci(db: AsyncSession) -> None:
    s = await _scope(db)
    ids = await _approved(db, s)
    stakeholder = await _stakeholder(db, s.tenant, s.project)
    response = await _raci(db, s, ids["1.1"], stakeholder)
    assert response.task_id == ids["1.1"]
    assert await _raci_rows(db, s.project) == 1
    # updating the same current link stays allowed
    await _raci(db, s, ids["1.1"], stakeholder)
    assert await _raci_rows(db, s.project) == 1


async def test_17_approved_baseline_accepts_bom(db: AsyncSession) -> None:
    s = await _scope(db)
    ids = await _approved(db, s)
    created = await _bom(db, s, ids["1.2"])
    assert created.wbs_item_id == ids["1.2"]
    await SQLAlchemyBOMRepository(db).bulk_create(
        [BOMItem(project_id=s.project, wbs_item_id=ids["1.1"], item_name="Cable", quantity=Decimal("1"))], s.tenant)
    await db.commit()
    assert await _bom_links(db, s.project) == 2


async def test_18_retired_node_rejects_new_links(db: AsyncSession) -> None:
    s = await _scope(db)
    ids = await _approved(db, s)
    added = await _baseline_two(db, s, ids)
    stakeholder = await _stakeholder(db, s.tenant, s.project)
    await _rejected(db, NODE_NOT_CURRENT_BASELINE, lambda: _raci(db, s, ids["2"], stakeholder))
    await _rejected(db, NODE_NOT_CURRENT_BASELINE, lambda: _bom(db, s, ids["2"]))
    assert await _raci_rows(db, s.project) == 0 and await _bom_links(db, s.project) == 0
    # the node baseline #2 added is canonical now
    await _raci(db, s, added, stakeholder)
    await _bom(db, s, added)


async def test_19_cross_project_links_are_rejected(db: AsyncSession) -> None:
    s = await _scope(db)
    await _approved(db, s)
    other = Scope(s.tenant, await _project(db, s.tenant), s.author, s.admin, s.admin2)
    foreign = await _approved(db, other)
    stakeholder = await _stakeholder(db, s.tenant, s.project)
    # BOM of project A pointing at project B's (approved, current) node
    await _rejected(db, NODE_NOT_CURRENT_BASELINE, lambda: _bom(db, s, foreign["1"]))
    # a RACI link recorded under project A for project B's node
    await _rejected(db, NODE_NOT_CURRENT_BASELINE, lambda: SqlAlchemyStakeholderRepository(db).add_raci_assignment(
        _assignment(s, stakeholder, foreign["1"]), tenant_id=s.tenant))
    # through the use case the stakeholder must match the node's project
    with pytest.raises(ValueError, match="stakeholder_project_mismatch"):
        await _raci(db, s, foreign["1"], stakeholder)
    await db.rollback()
    assert await _raci_rows(db, s.project) == 0 and await _bom_links(db, s.project) == 0


async def test_20_cross_tenant_links_are_rejected_without_leaking(db: AsyncSession) -> None:
    s = await _scope(db)
    await _approved(db, s)
    foreign_tenant = await _scope(db)
    foreign = await _approved(db, foreign_tenant)
    stakeholder = await _stakeholder(db, s.tenant, s.project)
    with pytest.raises(ValueError, match="task_not_found"):  # same answer as an unknown id
        await _raci(db, s, foreign["1"], stakeholder)
    await db.rollback()
    with pytest.raises(ValueError, match="task_not_found"):
        await _raci(db, s, uuid4(), stakeholder)
    await db.rollback()
    unknown = await _rejected(db, NODE_NOT_CURRENT_BASELINE, lambda: _bom(db, s, uuid4()))
    cross = await _rejected(db, NODE_NOT_CURRENT_BASELINE, lambda: _bom(db, s, foreign["1"]))
    assert unknown.message == cross.message
    assert await _raci_rows(db, s.project) == 0 and await _bom_links(db, s.project) == 0
    assert await _raci_rows(db, foreign_tenant.project) == 0


# =========================================================================== HONESTY 21-22
async def test_21_an_approved_wbs_date_is_not_schedule_authority(db: AsyncSession) -> None:
    s = await _scope(db)
    await _approved(db, s)
    await db.execute(text("UPDATE wbs_nodes SET planned_start = '2026-01-01', planned_end = '2026-06-30' "
                          "WHERE project_id = :p"), {"p": s.project})
    await db.commit()
    marker = await _time_marker(await build_schedule_clauses(db, s.project, s.tenant))
    assert marker["assessment_unavailable"] == {"TIME": "WBS_DATES_NOT_SCHEDULE_AUTHORITY"}
    authority = (await _read(db, s))["authority"]
    assert authority["approved"] is True and authority["dates_schedule_authority"] is False
    section = await _report(db, s)
    assert section.data is not None and section.data.dates_schedule_authority is False


async def test_22_budget_spent_is_not_cost_authority(db: AsyncSession) -> None:
    s = await _scope(db)
    await _approved(db, s)
    await db.execute(text("UPDATE wbs_nodes SET budget_allocated = 100, budget_spent = 40 WHERE project_id = :p"),
                     {"p": s.project})
    await db.commit()
    budget = await GetBudgetUseCase(SQLAlchemyBudgetRepository(db)).execute(s.project, s.tenant)
    assert budget.spent_amount == Decimal("160")  # compatibility value kept ...
    assert budget.spent_amount_cost_authority is False  # ... and qualified
    assert budget.spent_amount_source == "LEGACY_WBS_BUDGET_SPENT"
    authority = (await _read(db, s))["authority"]
    assert authority["budget_cost_authority"] is False
    budget_section = project_budget(SourceOk(budget.model_copy(update={"items": [SimpleNamespace(
        id=uuid4(), name="Line", code="B1", amount=Decimal("500"))]})))
    assert budget_section.data is not None and budget_section.data.spent_amount_cost_authority is False
    section = await _report(db, s)
    assert section.data is not None and section.data.budget_cost_authority is False


# =========================================================================== CONCURRENCY 23-25
def _engine_sessions() -> tuple[Any, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://"))
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _link_in(session: AsyncSession, s: Scope, kind: str, node_id: UUID, stakeholder: UUID) -> None:
    if kind == "raci":
        await SqlAlchemyStakeholderRepository(session).add_raci_assignment(
            _assignment(s, stakeholder, node_id), tenant_id=s.tenant)
    else:
        await SQLAlchemyBOMRepository(session).create(
            BOMItem(project_id=s.project, wbs_item_id=node_id, item_name="Rebar", quantity=Decimal("1")), s.tenant)


@pytest.mark.parametrize("kind", ["raci", "bom"])
async def test_23a_a_link_writer_waits_for_an_apply_that_retires_its_node(db: AsyncSession, kind: str) -> None:
    """Apply #2 first: the writer blocks on the project row and then sees the node retired."""
    s = await _scope(db)
    ids = await _approved(db, s)
    stakeholder = await _stakeholder(db, s.tenant, s.project)
    change_set_id, _ = await _draft_on_baseline(db, s, ids, submit=True)
    submitted = await _cs(db, change_set_id)
    engine, sessions = _engine_sessions()

    async def write() -> Exception | None:
        async with sessions() as writer:
            try:
                await _link_in(writer, s, kind, ids["2"], stakeholder)
                await writer.commit()
                return None
            except Exception as exc:  # noqa: BLE001 - the outcome under test
                await writer.rollback()
                return exc

    try:
        async with sessions() as approver:
            await WBSGovernedChangeService(approver).approve(
                project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.admin,
                expected_revision=submitted.revision, expected_digest=str(submitted.submitted_digest))
            task = asyncio.create_task(write())
            done, _ = await asyncio.wait({task}, timeout=1.0)
            assert not done, f"the link writer did not wait for the apply: {task.result()!r}"
            await approver.commit()
        outcome = await asyncio.wait_for(task, timeout=30)
    finally:
        await engine.dispose()
    assert isinstance(outcome, C2ProException) and outcome.code == NODE_NOT_CURRENT_BASELINE, outcome
    assert await _raci_rows(db, s.project) == 0 and await _bom_links(db, s.project) == 0


@pytest.mark.parametrize("kind", ["raci", "bom"])
async def test_23b_an_apply_waits_for_a_link_writer_and_then_refuses_to_retire_a_linked_node(
        db: AsyncSession, kind: str) -> None:
    """Link first: the apply blocks on the project row and then refuses to retire a now-linked node."""
    s = await _scope(db)
    ids = await _approved(db, s)
    stakeholder = await _stakeholder(db, s.tenant, s.project)
    change_set_id, _ = await _draft_on_baseline(db, s, ids, submit=True)
    submitted = await _cs(db, change_set_id)
    engine, sessions = _engine_sessions()

    async def apply() -> Exception | None:
        async with sessions() as approver:
            try:
                await WBSGovernedChangeService(approver).approve(
                    project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.admin,
                    expected_revision=submitted.revision, expected_digest=str(submitted.submitted_digest))
                await approver.commit()
                return None
            except Exception as exc:  # noqa: BLE001 - the outcome under test
                await approver.rollback()
                return exc

    try:
        async with sessions() as writer:
            await _link_in(writer, s, kind, ids["2"], stakeholder)
            task = asyncio.create_task(apply())
            done, _ = await asyncio.wait({task}, timeout=1.0)
            assert not done, f"the apply did not wait for the link writer: {task.result()!r}"
            await writer.commit()
        outcome = await asyncio.wait_for(task, timeout=30)
    finally:
        await engine.dispose()
    assert isinstance(outcome, RetiredNodesLinkedError), outcome
    assert await db.scalar(select(func.max(WBSBaselineORM.baseline_no))
                           .where(WBSBaselineORM.project_id == s.project)) == 1
    assert ids["2"] in {row.id for row in (await db.execute(
        select(WBSNodeORM).where(WBSNodeORM.project_id == s.project))).scalars()}


async def test_24_many_link_writers_racing_an_apply_never_deadlock(db: AsyncSession) -> None:
    """Writers to kept and retired nodes interleave with an apply: every transaction finishes,
    nothing deadlocks, and no committed link targets a node that is not live."""
    s = await _scope(db)
    ids = await _approved(db, s)
    stakeholders = [await _stakeholder(db, s.tenant, s.project) for _ in range(4)]
    change_set_id, _ = await _draft_on_baseline(db, s, ids, submit=True)
    submitted = await _cs(db, change_set_id)
    engine, sessions = _engine_sessions()

    async def write(index: int) -> Exception | None:
        node = ids["2"] if index % 2 else ids["1.1"]
        async with sessions() as writer:
            try:
                await _link_in(writer, s, "raci" if index < 4 else "bom", node, stakeholders[index % 4])
                await asyncio.sleep(0.05)
                await writer.commit()
                return None
            except Exception as exc:  # noqa: BLE001
                await writer.rollback()
                return exc

    async def apply() -> Exception | None:
        async with sessions() as approver:
            try:
                await WBSGovernedChangeService(approver).approve(
                    project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.admin,
                    expected_revision=submitted.revision, expected_digest=str(submitted.submitted_digest))
                await asyncio.sleep(0.05)
                await approver.commit()
                return None
            except Exception as exc:  # noqa: BLE001
                await approver.rollback()
                return exc

    try:
        outcomes = await asyncio.wait_for(asyncio.gather(*(write(i) for i in range(8)), apply()), timeout=60)
    finally:
        await engine.dispose()
    for outcome in outcomes:
        assert outcome is None or isinstance(outcome, C2ProException | RetiredNodesLinkedError), outcome
        assert "deadlock" not in str(outcome).lower()
    dangling = await db.scalar(text(
        "SELECT count(*) FROM stakeholder_wbs_raci r WHERE r.project_id = :p AND NOT EXISTS "
        "(SELECT 1 FROM wbs_nodes w WHERE w.id = r.wbs_item_id)"), {"p": s.project})
    dangling_bom = await db.scalar(text(
        "SELECT count(*) FROM procurement_bom_items b WHERE b.project_id = :p AND b.wbs_item_id IS NOT NULL AND "
        "NOT EXISTS (SELECT 1 FROM wbs_nodes w WHERE w.id = b.wbs_item_id)"), {"p": s.project})
    assert dangling == 0 and dangling_bom == 0


async def test_25_link_gating_is_tenant_safe_under_concurrency(db: AsyncSession) -> None:
    """An apply in tenant A never blocks or authorizes a link writer in tenant B."""
    a = await _scope(db)
    a_ids = await _approved(db, a)
    change_set_id, _ = await _draft_on_baseline(db, a, a_ids, submit=True)
    submitted = await _cs(db, change_set_id)
    b = await _scope(db)
    b_ids = await _approved(db, b)
    b_stakeholder = await _stakeholder(db, b.tenant, b.project)
    engine, sessions = _engine_sessions()
    try:
        async with sessions() as approver, sessions() as writer:
            await WBSGovernedChangeService(approver).approve(
                project_id=a.project, change_set_id=change_set_id, tenant_id=a.tenant, actor=a.admin,
                expected_revision=submitted.revision, expected_digest=str(submitted.submitted_digest))
            # tenant B links immediately while tenant A's apply is uncommitted
            await asyncio.wait_for(_link_in(writer, b, "raci", b_ids["1"], b_stakeholder), timeout=5)
            # and tenant B can never link tenant A's node, whatever A's state
            with pytest.raises(C2ProException) as caught:
                async with writer.begin_nested():
                    await _link_in(writer, b, "bom", a_ids["1"], b_stakeholder)
            assert caught.value.code == NODE_NOT_CURRENT_BASELINE
            await writer.commit()
            await approver.commit()
    finally:
        await engine.dispose()
    assert await _raci_rows(db, b.project) == 1 and await _raci_rows(db, a.project) == 0


# =========================================================================== review follow-ups (#915)
@pytest.mark.parametrize("approved", [False, True])
async def test_21b_actual_only_wbs_dates_also_withhold_time(db: AsyncSession, approved: bool) -> None:
    """Codex P1: actual_start / actual_end are WBS dates too -- never schedule evidence."""
    s = await _scope(db)
    if approved:
        await _approved(db, s)
    else:
        await _legacy(db, s)
    await db.execute(text("UPDATE wbs_nodes SET planned_start = NULL, planned_end = NULL, "
                          "actual_end = '2026-02-01' WHERE project_id = :p"), {"p": s.project})
    await db.commit()
    marker = await _time_marker(await build_schedule_clauses(db, s.project, s.tenant))
    reason = "WBS_DATES_NOT_SCHEDULE_AUTHORITY" if approved else "WBS_NOT_APPROVED"
    assert marker["assessment_unavailable"] == {"TIME": reason}


@pytest.mark.parametrize("between", ["authority_and_tree", "tree_and_flat"])
async def test_26_wbs_read_never_mixes_baselines_across_a_concurrent_apply(
        db: AsyncSession, monkeypatch: pytest.MonkeyPatch, between: str) -> None:
    """Codex P2: an apply committing in the middle of GET /wbs never yields Baseline #N
    authority with #N+1 rows, nor a tree and a flat list from different baselines."""
    import src.projects.application.project_wbs_view as view

    s = await _scope(db)
    ids = await _approved(db, s)
    change_set_id, candidate = await _draft_on_baseline(db, s, ids, submit=True)
    submitted = await _cs(db, change_set_id)
    engine, sessions = _engine_sessions()
    fired: list[bool] = []

    async def apply_once() -> None:
        if fired:
            return
        fired.append(True)
        async with sessions() as approver:
            await WBSGovernedChangeService(approver).approve(
                project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.admin,
                expected_revision=submitted.revision, expected_digest=str(submitted.submitted_digest))
            await approver.commit()

    target = view.GetWBSTreeUseCase if between == "authority_and_tree" else view.ListWBSItemsUseCase
    original = target.execute

    async def racing_execute(self: Any, *args: Any, **kwargs: Any) -> Any:
        await apply_once()
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(target, "execute", racing_execute)
    try:
        result = await asyncio.wait_for(build_project_wbs_view(db, s.project, s.tenant), timeout=30)
    finally:
        await engine.dispose()
    assert fired, "the apply did not run during the read"
    tree_ids = _read_ids(result)
    authority = result["authority"]
    assert authority["baseline_no"] == 2, authority
    assert str(candidate) in tree_ids and str(ids["2"]) not in tree_ids
    assert result["total_items"] == len(tree_ids) == result["coverage"]["approved_scope_items"]
