"""PC-2a.2 (#896) -- governed WBS edit / submit / approve = apply on a real PostgreSQL.

TS-INT-PC2A2-WBS-001. Numbered tests follow the #896 approval (1-55): editing, submit, authority,
stale/rebase, reject, apply, first baseline, direct-write bypass and tenancy. RLS (55) is also
proven on a migrated scratch database under a NOBYPASSRLS probe role
(tests/integration/product_control/test_pc2a2_wbs_governed_apply_migration_db.py).
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.auth.models import UserRole
from src.procurement.adapters.persistence.wbs_repository import (
    SQLAlchemyWBSRepository,
    WBSGovernedByBaselineError,
)
from src.procurement.domain.models import WBSItem
from src.shared_kernel.enums import RACIRole
from src.stakeholders.adapters.persistence.models import StakeholderWBSRaciORM
from src.temporal.adapters.persistence.models import ProjectEventORM
from src.wbs.adapters.persistence.governance_models import (
    WBSBaselineNodeORM,
    WBSBaselineORM,
    WBSChangeSetLineageORM,
    WBSChangeSetNodeORM,
    WBSChangeSetORM,
    WBSChangeSetRetirementORM,
)
from src.wbs.adapters.persistence.governance_repository import Actor, WBSGovernanceRepository
from src.wbs.adapters.persistence.models import WBSNodeORM
from src.wbs.application.governed_change_service import (
    AddNode,
    AdoptLegacyNode,
    ChangeSetDigestMismatchError,
    ChangeSetRevisionConflictError,
    ChangeSetStaleError,
    ChangeSetStateError,
    CommandResult,
    EditCommand,
    LegacyWBSChangedError,
    MergeNodes,
    MoveNode,
    NodeSpec,
    RecodeNode,
    RemoveNode,
    ReorderNode,
    RetiredNodesLinkedError,
    SplitNode,
    UpdateNode,
    WBSChangeSetInvalidError,
    WBSChangeSetNotFoundError,
    WBSGovernanceForbiddenError,
    WBSGovernedChangeService,
    WBSProjectNotFoundError,
)
from src.wbs.domain.digest import DigestNode, tree_digest
from src.wbs.domain.governance import ActorKind, AuthorityState, LineageKind
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import (
    Scope,
    _expect_db_rejection,
    _legacy_nodes,
    _project,
    _rejected,
    _scope,
    _user,
)

pytestmark = pytest.mark.asyncio


# =========================================================================== helpers
def _svc(db: AsyncSession) -> WBSGovernedChangeService:
    return WBSGovernedChangeService(db)


async def _rev(db: AsyncSession, change_set_id: UUID) -> int:
    await db.commit()
    return int(await db.scalar(
        select(WBSChangeSetORM.revision).where(WBSChangeSetORM.id == change_set_id).execution_options(populate_existing=True)
    ))


async def _cs(db: AsyncSession, change_set_id: UUID) -> WBSChangeSetORM:
    row = await db.scalar(select(WBSChangeSetORM).where(WBSChangeSetORM.id == change_set_id)
                          .execution_options(populate_existing=True))
    assert row is not None
    return row


async def _cmd(db: AsyncSession, s: Scope, change_set_id: UUID, command: EditCommand,
               actor: Actor | None = None) -> CommandResult:
    result = await _svc(db).execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant,
                                    actor=actor or s.author, expected_revision=await _rev(db, change_set_id),
                                    command=command)
    await db.commit()
    return result


async def _new(db: AsyncSession, s: Scope, title: str = "WBS", actor: Actor | None = None) -> UUID:
    change_set = await _svc(db).create_change_set(project_id=s.project, tenant_id=s.tenant, actor=actor or s.author,
                                                  title=title)
    change_set_id = change_set.id
    await db.commit()
    return change_set_id


async def _tree(db: AsyncSession, s: Scope, change_set_id: UUID) -> dict[str, UUID]:
    """Civil(1) > Earthworks(1.1), Foundations(1.2); Electrical(2)."""
    civil = (await _cmd(db, s, change_set_id, AddNode(NodeSpec("Civil", "1", "control_account", "core:discipline")))).node_ids[0]
    earth = (await _cmd(db, s, change_set_id, AddNode(NodeSpec("Earthworks", "1.1", "work_package"), parent_id=civil))).node_ids[0]
    found = (await _cmd(db, s, change_set_id, AddNode(NodeSpec("Foundations", "1.2", "work_package"), parent_id=civil))).node_ids[0]
    elec = (await _cmd(db, s, change_set_id, AddNode(NodeSpec("Electrical", "2")))).node_ids[0]
    return {"1": civil, "1.1": earth, "1.2": found, "2": elec}


async def _submit(db: AsyncSession, s: Scope, change_set_id: UUID, actor: Actor | None = None) -> str:
    digest = await _svc(db).submit(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant,
                                   actor=actor or s.author, expected_revision=await _rev(db, change_set_id))
    await db.commit()
    return digest


async def _approve(db: AsyncSession, s: Scope, change_set_id: UUID, actor: Actor | None = None, *,
                   revision: int | None = None, digest: str | None = None) -> Any:
    change_set = await _cs(db, change_set_id)
    result = await _svc(db).approve(
        project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=actor or s.admin,
        expected_revision=revision if revision is not None else change_set.revision,
        expected_digest=digest if digest is not None else str(change_set.submitted_digest))
    await db.commit()
    return result


async def _baseline_one(db: AsyncSession, s: Scope) -> tuple[UUID, dict[str, UUID], Any]:
    change_set_id = await _new(db, s, "Baseline 1")
    ids = await _tree(db, s, change_set_id)
    await _submit(db, s, change_set_id)
    return change_set_id, ids, await _approve(db, s, change_set_id)


async def _live(db: AsyncSession, project_id: UUID) -> dict[UUID, WBSNodeORM]:
    rows = await db.execute(select(WBSNodeORM).where(WBSNodeORM.project_id == project_id)
                            .execution_options(populate_existing=True))
    return {row.id: row for row in rows.scalars()}


def _live_digest(project_id: UUID, live: dict[UUID, WBSNodeORM]) -> str:
    return tree_digest(project_id, [DigestNode(r.id, r.parent_id, r.sort_order, r.code, r.name, r.decomposition_kind,
                                               r.control_level, r.dictionary) for r in live.values()])


async def _events(db: AsyncSession, project_id: UUID, event_type: str) -> list[ProjectEventORM]:
    rows = await db.execute(select(ProjectEventORM).where(ProjectEventORM.project_id == project_id,
                                                          ProjectEventORM.event_type == event_type))
    return list(rows.scalars())


async def _candidate(db: AsyncSession, change_set_id: UUID) -> dict[UUID, WBSChangeSetNodeORM]:
    rows = await db.execute(select(WBSChangeSetNodeORM).where(WBSChangeSetNodeORM.change_set_id == change_set_id)
                            .execution_options(populate_existing=True))
    return {row.node_id: row for row in rows.scalars()}


# =========================================================================== EDITING 1-9
async def test_01_add_mints_the_id_and_bumps_the_revision(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    before = await _rev(db, change_set_id)
    result = await _cmd(db, s, change_set_id, AddNode(NodeSpec("Civil", "1")))
    assert result.revision == before + 1 and len(result.node_ids) == 1
    node = (await _candidate(db, change_set_id))[result.node_ids[0]]
    assert (node.origin_kind, node.sort_order, node.parent_id) == ("minted", 1, None)
    # append by default, explicit position shifts the siblings (dense 1..n)
    second = (await _cmd(db, s, change_set_id, AddNode(NodeSpec("Electrical", "2")))).node_ids[0]
    first = (await _cmd(db, s, change_set_id, AddNode(NodeSpec("Site prep", "0"), position=1))).node_ids[0]
    nodes = await _candidate(db, change_set_id)
    assert [nodes[i].sort_order for i in (first, result.node_ids[0], second)] == [1, 2, 3]


async def test_02_03_update_and_recode_keep_the_identity(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    ids = await _tree(db, s, change_set_id)
    await _cmd(db, s, change_set_id, UpdateNode(ids["1.1"], {
        "name": "Bulk earthworks", "control_level": "control_account", "decomposition_kind": "core:component",
        "dictionary": {"scope_statement": "Cut and fill", "deliverables": ["Platform"]}}))
    await _cmd(db, s, change_set_id, RecodeNode(ids["1.1"], "1.10"))
    node = (await _candidate(db, change_set_id))[ids["1.1"]]
    assert (node.node_id, node.name, node.code, node.control_level) == (ids["1.1"], "Bulk earthworks", "1.10", "control_account")
    assert node.dictionary is not None and node.dictionary["schema_version"] == "wbs-dictionary/v1"
    with pytest.raises(WBSChangeSetInvalidError):  # identity / structure are not UPDATE_NODE fields
        await _svc(db).execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author,
                               expected_revision=await _rev(db, change_set_id),
                               command=UpdateNode(ids["1.1"], {"parent_id": None}))
    await db.rollback()


async def test_04_05_move_and_reorder_keep_the_identity_and_dense_order(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    ids = await _tree(db, s, change_set_id)
    await _cmd(db, s, change_set_id, MoveNode(ids["1.2"], parent_id=None, position=1))
    await _cmd(db, s, change_set_id, ReorderNode(ids["2"], 1))
    nodes = await _candidate(db, change_set_id)
    top = sorted((n for n in nodes.values() if n.parent_id is None), key=lambda n: n.sort_order)
    assert [n.node_id for n in top] == [ids["2"], ids["1.2"], ids["1"]]
    assert [n.sort_order for n in top] == [1, 2, 3] and nodes[ids["1.1"]].sort_order == 1
    with pytest.raises(WBSChangeSetInvalidError, match="under itself"):
        await _svc(db).execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author,
                               expected_revision=await _rev(db, change_set_id),
                               command=MoveNode(ids["1"], parent_id=ids["1.1"]))
    await db.rollback()


async def test_06_split_retires_the_source_and_mints_targets(db: AsyncSession) -> None:
    s = await _scope(db)
    _, ids, _ = await _baseline_one(db, s)
    change_set_id = await _new(db, s, "Split civil")
    # ambiguous: Civil has two children, none assigned
    with pytest.raises(WBSChangeSetInvalidError, match="ambiguous split"):
        await _svc(db).execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author,
                               expected_revision=await _rev(db, change_set_id),
                               command=SplitNode(ids["1"], [NodeSpec("Civil A", "1A"), NodeSpec("Civil B", "1B")]))
    await db.rollback()
    result = await _cmd(db, s, change_set_id, SplitNode(
        ids["1"], [NodeSpec("Civil A", "1A"), NodeSpec("Civil B", "1B")], {ids["1.1"]: 0, ids["1.2"]: 1}))
    a, b = result.node_ids
    nodes = await _candidate(db, change_set_id)
    assert ids["1"] not in nodes and {a, b} <= set(nodes) and a != ids["1"] != b
    assert (nodes[a].origin_kind, nodes[a].sort_order, nodes[b].sort_order) == ("minted", 1, 2)
    assert nodes[ids["1.1"]].parent_id == a and nodes[ids["1.2"]].parent_id == b
    lineage = (await db.execute(select(WBSChangeSetLineageORM).where(WBSChangeSetLineageORM.change_set_id == change_set_id))).scalars().all()
    assert {(e.kind, e.source_node_id, e.target_node_id) for e in lineage} == {("SPLIT", ids["1"], a), ("SPLIT", ids["1"], b)}
    retired = (await db.execute(select(WBSChangeSetRetirementORM).where(WBSChangeSetRetirementORM.change_set_id == change_set_id))).scalars().all()
    assert [(r.node_id, r.disposition, r.source, r.snapshot["code"]) for r in retired] == [(ids["1"], "SPLIT", "baseline", "1")]


async def test_07_merge_retires_the_sources_and_mints_one_target(db: AsyncSession) -> None:
    s = await _scope(db)
    _, ids, _ = await _baseline_one(db, s)
    change_set_id = await _new(db, s, "Merge")
    target = (await _cmd(db, s, change_set_id, MergeNodes([ids["1.1"], ids["1.2"]], NodeSpec("Groundworks", "1.1")))).node_ids[0]
    nodes = await _candidate(db, change_set_id)
    assert target not in (ids["1.1"], ids["1.2"]) and ids["1.1"] not in nodes and ids["1.2"] not in nodes
    assert (nodes[target].parent_id, nodes[target].sort_order, nodes[target].origin_kind) == (ids["1"], 1, "minted")
    lineage = (await db.execute(select(WBSChangeSetLineageORM).where(WBSChangeSetLineageORM.change_set_id == change_set_id))).scalars().all()
    assert {(e.kind, e.source_node_id, e.target_node_id) for e in lineage} == {("MERGE", ids["1.1"], target), ("MERGE", ids["1.2"], target)}
    retired = (await db.execute(select(WBSChangeSetRetirementORM).where(WBSChangeSetRetirementORM.change_set_id == change_set_id))).scalars().all()
    assert {(r.node_id, r.disposition) for r in retired} == {(ids["1.1"], "MERGED"), (ids["1.2"], "MERGED")}
    # a source id never becomes the merged identity: the database refuses re-adding a retired id
    with pytest.raises(WBSChangeSetInvalidError):
        await _svc(db).execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author,
                               expected_revision=await _rev(db, change_set_id),
                               command=MergeNodes([ids["1.1"], ids["2"]], NodeSpec("x", "x")))
    await db.rollback()


async def test_08_a_stale_draft_revision_is_a_conflict_not_last_write_wins(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    rev = await _rev(db, change_set_id)
    await _svc(db).execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author,
                           expected_revision=rev, command=AddNode(NodeSpec("A", "1")))
    await db.commit()
    with pytest.raises(ChangeSetRevisionConflictError) as caught:
        await _svc(db).execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author,
                               expected_revision=rev, command=AddNode(NodeSpec("B", "2")))
    assert caught.value.code == "CHANGE_SET_REVISION_CONFLICT" and caught.value.details["current_revision"] == rev + 1
    await db.rollback()
    assert len(await _candidate(db, change_set_id)) == 1


async def test_08b_concurrent_edits_at_the_same_revision_serialize(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    rev = await _rev(db, change_set_id)
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://"))
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def edit(name: str) -> str:
        async with sessions() as session:
            try:
                await WBSGovernedChangeService(session).execute(
                    project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author,
                    expected_revision=rev, command=AddNode(NodeSpec(name, name)))
                await session.commit()
                return "ok"
            except ChangeSetRevisionConflictError:
                await session.rollback()
                return "conflict"

    try:
        outcomes = await asyncio.gather(edit("A"), edit("B"))
    finally:
        await engine.dispose()
    assert sorted(outcomes) == ["conflict", "ok"]
    assert await _rev(db, change_set_id) == rev + 1 and len(await _candidate(db, change_set_id)) == 1


async def test_09_a_submitted_candidate_cannot_be_edited(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    await _submit(db, s, change_set_id)
    with pytest.raises(ChangeSetStateError):
        await _svc(db).execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author,
                               expected_revision=await _rev(db, change_set_id), command=AddNode(NodeSpec("x", "9")))
    await db.rollback()


# =========================================================================== SUBMIT 10-17
async def _submit_violations(db: AsyncSession, s: Scope, change_set_id: UUID) -> list[str]:
    with pytest.raises(WBSChangeSetInvalidError) as caught:
        await _svc(db).submit(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author,
                              expected_revision=await _rev(db, change_set_id))
    await db.rollback()
    assert (await _cs(db, change_set_id)).status == "DRAFT"
    return list(caught.value.details["violations"])


async def test_10_11_null_and_duplicate_codes_block_submit(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _cmd(db, s, change_set_id, AddNode(NodeSpec("No code yet")))
    await _cmd(db, s, change_set_id, AddNode(NodeSpec("A", "1")))
    await _cmd(db, s, change_set_id, AddNode(NodeSpec("B", "1")))
    violations = await _submit_violations(db, s, change_set_id)
    assert any("code is required" in v for v in violations) and any("duplicate code" in v for v in violations)


async def test_12_13_cycles_and_invalid_dictionaries_are_refused(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    ids = await _tree(db, s, change_set_id)
    with pytest.raises(WBSChangeSetInvalidError, match="under itself"):
        await _svc(db).execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author,
                               expected_revision=await _rev(db, change_set_id), command=MoveNode(ids["1"], ids["1.2"]))
    await db.rollback()
    for bad in ({"risk_ids": ["r1"]}, {"deliverables": False}, {"scope_statement": 3}):
        with pytest.raises(WBSChangeSetInvalidError):
            await _svc(db).execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant,
                                   actor=s.author, expected_revision=await _rev(db, change_set_id),
                                   command=UpdateNode(ids["1"], {"dictionary": bad}))
        await db.rollback()


async def test_14_bad_lineage_blocks_submit(db: AsyncSession) -> None:
    s = await _scope(db)
    _, ids, _ = await _baseline_one(db, s)
    change_set_id = await _new(db, s, "Bad lineage")
    target = (await _cmd(db, s, change_set_id, AddNode(NodeSpec("Replacement", "9")))).node_ids[0]
    # a SUPERSEDES edge whose source stays in the candidate and has no disposition
    await WBSGovernanceRepository(db).add_lineage(change_set_id, s.tenant, expected_revision=await _rev(db, change_set_id),
                                                  kind=LineageKind.SUPERSEDES, source_node_id=ids["2"], target_node_id=target)
    await db.commit()
    violations = await _submit_violations(db, s, change_set_id)
    assert any("must leave the candidate" in v for v in violations)
    assert any("needs a SUPERSEDED disposition" in v for v in violations)


async def test_15_a_retired_id_without_disposition_blocks_submit(db: AsyncSession) -> None:
    s = await _scope(db)
    _, ids, _ = await _baseline_one(db, s)
    change_set_id = await _new(db, s, "Silent drop")
    # the low-level PC-2a.1 primitive drops a base identity WITHOUT recording a disposition
    await WBSGovernanceRepository(db).remove_node(change_set_id, ids["2"], s.tenant,
                                                  expected_revision=await _rev(db, change_set_id))
    await db.commit()
    violations = await _submit_violations(db, s, change_set_id)
    assert f"{ids['2']}: retired id without disposition" in violations
    # the governed REMOVE_NODE command records it, so the same removal submits
    other = await _new(db, s, "Explicit removal")
    await _cmd(db, s, other, RemoveNode(ids["2"]))
    await _submit(db, s, other)


async def test_16_17_submit_freezes_the_exact_digest_and_the_session_submitter(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    digest = await _submit(db, s, change_set_id)
    change_set = await _cs(db, change_set_id)
    detail = await WBSGovernanceRepository(db).get_change_set(change_set_id, s.project, s.tenant)
    assert detail is not None
    assert digest == change_set.submitted_digest == WBSGovernanceRepository(db).compute_change_set_digest(detail, change_set.revision)
    assert (change_set.submitted_by, change_set.submitted_revision) == (s.author.user_id, change_set.revision)
    events = await _events(db, s.project, "wbs.change.submitted")
    assert [e.payload["change_set_digest"] for e in events] == [digest]


# =========================================================================== AUTHORITY 18-24
async def test_18_19_viewers_api_users_ai_and_services_cannot_submit(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    viewer = await _user(db, s.tenant, UserRole.VIEWER)
    api = await _user(db, s.tenant, UserRole.API)
    for actor in (viewer, api, Actor(s.author.user_id, ActorKind.AI, "user"), Actor(uuid4(), ActorKind.SERVICE, "admin")):
        with pytest.raises(WBSGovernanceForbiddenError):
            await _svc(db).submit(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=actor,
                                  expected_revision=await _rev(db, change_set_id))
        await db.rollback()
        with pytest.raises(WBSGovernanceForbiddenError):
            await _svc(db).execute(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=actor,
                                   expected_revision=await _rev(db, change_set_id), command=AddNode(NodeSpec("x", "x")))
        await db.rollback()
    assert (await _cs(db, change_set_id)).status == "DRAFT"


async def test_20_21_only_a_human_admin_approves(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    await _submit(db, s, change_set_id)
    colleague = await _user(db, s.tenant, UserRole.USER)
    for actor in (colleague, Actor(s.admin.user_id, ActorKind.AI, "admin"), Actor(s.admin.user_id, ActorKind.SERVICE, "admin"),
                  await _user(db, s.tenant, UserRole.API)):
        with pytest.raises(WBSGovernanceForbiddenError):
            await _approve(db, s, change_set_id, actor)
        await db.rollback()
    assert (await _cs(db, change_set_id)).status == "SUBMITTED"
    assert await db.scalar(select(func.count()).select_from(WBSBaselineORM).where(WBSBaselineORM.project_id == s.project)) == 0


async def test_23_distinct_approver_is_enforced_by_default(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s, actor=s.admin)
    await _tree(db, s, change_set_id)
    await _submit(db, s, change_set_id, actor=s.admin)
    with pytest.raises(WBSGovernanceForbiddenError, match="separation of duties"):
        await _approve(db, s, change_set_id, s.admin)
    await db.rollback()
    result = await _approve(db, s, change_set_id, s.admin2)
    assert result.self_approved is False


async def test_24_configured_self_approval_works_and_is_audited(db: AsyncSession) -> None:
    s = await _scope(db, {"wbs_governance": {"require_distinct_approver": False}})
    change_set_id = await _new(db, s, actor=s.admin)
    await _tree(db, s, change_set_id)
    await _submit(db, s, change_set_id, actor=s.admin)
    result = await _approve(db, s, change_set_id, s.admin)
    baseline = await db.get(WBSBaselineORM, result.baseline_id)
    change_set = await _cs(db, change_set_id)
    event = (await _events(db, s.project, "wbs.baseline.applied"))[0]
    assert baseline is not None and baseline.self_approved and change_set.decided_self_approval
    assert result.self_approved and event.payload["self_approved"] is True


# =========================================================================== STALE 25-27
async def test_25_26_27_a_newer_baseline_stales_competitors_and_rebase_starts_a_new_draft(db: AsyncSession) -> None:
    s = await _scope(db)
    _, ids, first = await _baseline_one(db, s)
    winner = await _new(db, s, "Winner")
    loser = await _new(db, s, "Loser")
    await _cmd(db, s, winner, RecodeNode(ids["2"], "2.0"))
    await _cmd(db, s, loser, UpdateNode(ids["2"], {"name": "Electrical & I&C"}))
    await _submit(db, s, winner)
    await _submit(db, s, loser)
    result = await _approve(db, s, winner)
    assert result.stale_change_set_ids == [loser] and (await _cs(db, loser)).status == "STALE"
    with pytest.raises(ChangeSetStaleError):
        await _approve(db, s, loser)
    await db.rollback()
    rebased = await _svc(db).rebase(project_id=s.project, change_set_id=loser, tenant_id=s.tenant, actor=s.author)
    rebased_id, rebased_base = rebased.id, rebased.base_baseline_id
    await db.commit()
    assert rebased_base == result.baseline_id != first.baseline_id
    assert (await _cs(db, loser)).status == "STALE"  # audit history untouched
    nodes = await _candidate(db, rebased_id)
    assert nodes[ids["2"]].code == "2.0" and nodes[ids["2"]].name == "Electrical"  # seeded from the NEW baseline
    assert f"wbs-change-set:{loser}" in (await _cs(db, rebased_id)).evidence_refs


# =========================================================================== REJECT 28-30
async def test_28_29_30_rejection_needs_a_reason_and_is_immutable_history(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    digest = await _submit(db, s, change_set_id)
    revision = await _rev(db, change_set_id)
    with pytest.raises(WBSChangeSetInvalidError, match="reason"):
        await _svc(db).reject(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.admin,
                              expected_revision=revision, expected_digest=digest, reason="  ")
    await db.rollback()
    await _svc(db).reject(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.admin,
                          expected_revision=revision, expected_digest=digest, reason="Scope split is wrong")
    await db.commit()
    change_set = await _cs(db, change_set_id)
    assert (change_set.status, change_set.decision_reason, change_set.decided_by) == ("REJECTED", "Scope split is wrong", s.admin.user_id)
    assert len(await _events(db, s.project, "wbs.change.rejected")) == 1
    with pytest.raises(ChangeSetStateError):
        await _approve(db, s, change_set_id, revision=revision, digest=digest)
    await db.rollback()
    await _expect_db_rejection(db, "UPDATE wbs_change_sets SET status = 'SUBMITTED' WHERE id = :c", {"c": change_set_id},
                               "REJECTED and immutable")


# =========================================================================== APPLY 31-42
async def test_31_32_digest_and_revision_compare_and_set(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    old_digest = await _submit(db, s, change_set_id)
    old_revision = await _rev(db, change_set_id)
    with pytest.raises(ChangeSetDigestMismatchError):  # digest A cannot apply tree B
        await _approve(db, s, change_set_id, digest="sha256:" + "0" * 64)
    await db.rollback()
    # reopen, edit, resubmit: the old reviewed revision/digest cannot apply the new tree
    await _svc(db).reopen(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author)
    await db.commit()
    await _cmd(db, s, change_set_id, AddNode(NodeSpec("Mechanical", "3")))
    new_digest = await _submit(db, s, change_set_id)
    assert new_digest != old_digest
    with pytest.raises(ChangeSetRevisionConflictError):
        await _approve(db, s, change_set_id, revision=old_revision, digest=old_digest)
    await db.rollback()
    with pytest.raises(ChangeSetDigestMismatchError):
        await _approve(db, s, change_set_id, digest=old_digest)
    await db.rollback()


async def test_31b_a_candidate_tampered_after_submit_never_applies(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    ids = await _tree(db, s, change_set_id)
    await _submit(db, s, change_set_id)
    # bypass the DRAFT-only guard as the table owner would: the recomputed digest catches it
    await db.execute(text("SET LOCAL session_replication_role = replica"))
    await db.execute(text("UPDATE wbs_change_set_nodes SET name = 'Tampered' WHERE node_id = :n"), {"n": ids["2"]})
    await db.commit()
    with pytest.raises(ChangeSetDigestMismatchError, match="no longer hashes"):
        await _approve(db, s, change_set_id)
    await db.rollback()
    assert await _live(db, s.project) == {}


async def test_33_34_base_must_be_current_and_apply_happens_once(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, _, _ = await _baseline_one(db, s)
    with pytest.raises(ChangeSetStateError):  # APPLIED: a second approval is impossible
        await _approve(db, s, change_set_id)
    await db.rollback()
    assert await db.scalar(select(func.count()).select_from(WBSBaselineORM).where(WBSBaselineORM.project_id == s.project)) == 1


async def test_34b_concurrent_approvals_produce_exactly_one_baseline(db: AsyncSession) -> None:
    s = await _scope(db)
    first = await _new(db, s, "A")
    second = await _new(db, s, "B")
    await _cmd(db, s, first, AddNode(NodeSpec("Civil", "1")))
    await _cmd(db, s, second, AddNode(NodeSpec("Mechanical", "1")))
    await _submit(db, s, first)
    await _submit(db, s, second)
    expected = {cs: (await _cs(db, cs)) for cs in (first, second)}
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://"))
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def approve(change_set_id: UUID, approver: Actor) -> str:
        async with sessions() as session:
            try:
                await WBSGovernedChangeService(session).approve(
                    project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=approver,
                    expected_revision=expected[change_set_id].revision,
                    expected_digest=str(expected[change_set_id].submitted_digest))
                await session.commit()
                return "applied"
            except (ChangeSetStaleError, ChangeSetStateError):
                await session.rollback()
                return "stale"

    try:
        outcomes = await asyncio.gather(approve(first, s.admin), approve(second, s.admin2))
    finally:
        await engine.dispose()
    assert sorted(outcomes) == ["applied", "stale"]
    assert await db.scalar(select(func.count()).select_from(WBSBaselineORM).where(WBSBaselineORM.project_id == s.project)) == 1
    assert sorted([(await _cs(db, first)).status, (await _cs(db, second)).status]) == ["APPLIED", "STALE"]


async def _while_an_approval_is_uncommitted(db: AsyncSession, s: Scope, racer: Any) -> tuple[UUID, Any]:
    """Approve a first baseline in one session and, before it commits, run ``racer(session)`` in another.

    The racer must WAIT for the apply transaction (not finish before it); returns (baseline id,
    the racer's outcome -- its return value or the exception it raised).
    """
    change_set_id = await _new(db, s, "Baseline 1")
    await _cmd(db, s, change_set_id, AddNode(NodeSpec("Civil", "1")))
    await _submit(db, s, change_set_id)
    submitted = await _cs(db, change_set_id)
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://"))
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def race() -> Any:
        async with sessions() as session:
            try:
                outcome = await racer(session)
                await session.commit()
                return outcome
            except Exception as exc:  # noqa: BLE001 - the outcome under test
                await session.rollback()
                return exc

    try:
        async with sessions() as approver:
            result = await WBSGovernedChangeService(approver).approve(
                project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.admin,
                expected_revision=submitted.revision, expected_digest=str(submitted.submitted_digest))
            task = asyncio.create_task(race())
            done, _ = await asyncio.wait({task}, timeout=1.0)
            assert not done, f"the racer did not wait for the apply transaction: {task.result()!r}"
            await approver.commit()
        outcome = await asyncio.wait_for(task, timeout=30)
    finally:
        await engine.dispose()
    return result.baseline_id, outcome


@pytest.mark.parametrize("writer", ["repository", "raw_sql"])
async def test_34c_a_live_writer_racing_a_first_baseline_waits_and_is_then_refused(db: AsyncSession, writer: str) -> None:
    s = await _scope(db)

    async def legacy_writer(session: AsyncSession) -> Any:
        if writer == "repository":
            return await SQLAlchemyWBSRepository(session).create(
                s.tenant, WBSItem(project_id=s.project, code="LATE-1", name="Late legacy row", level=1))
        # a writer outside the repository: no project lock taken before the row trigger runs
        return await session.execute(text(
            "INSERT INTO wbs_nodes (id, project_id, tenant_id, code, name, lft, rgt, depth, sort_order, node_type, "
            "metadata, created_at, updated_at) VALUES (:id, :project, :tenant, 'LATE-1', 'Late legacy row', 1000, 1001, "
            "0, 99, 'activity', '{}'::jsonb, now(), now())"), {"id": uuid4(), "project": s.project, "tenant": s.tenant})

    baseline_id, outcome = await _while_an_approval_is_uncommitted(db, s, legacy_writer)
    assert isinstance(outcome, Exception) and "governed by an approved baseline" in str(outcome), outcome
    live = await _live(db, s.project)
    assert [row.code for row in live.values()] == ["1"]
    baseline = await db.get(WBSBaselineORM, baseline_id)
    assert baseline is not None and _live_digest(s.project, live) == baseline.tree_digest


@pytest.mark.parametrize("writer", ["repository", "raw_sql"])
async def test_34e_an_approval_racing_an_uncommitted_live_write_waits_then_refuses_without_deadlock(
        db: AsyncSession, writer: str) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s, "Baseline 1")
    await _cmd(db, s, change_set_id, AddNode(NodeSpec("Civil", "1")))
    await _submit(db, s, change_set_id)
    submitted = await _cs(db, change_set_id)
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://"))
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def approve() -> Any:
        async with sessions() as session:
            try:
                return await WBSGovernedChangeService(session).approve(
                    project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.admin,
                    expected_revision=submitted.revision, expected_digest=str(submitted.submitted_digest))
            except Exception as exc:  # noqa: BLE001 - the outcome under test
                await session.rollback()
                return exc

    try:
        async with sessions() as live_writer:
            if writer == "repository":
                await SQLAlchemyWBSRepository(live_writer).create(
                    s.tenant, WBSItem(project_id=s.project, code="LATE-1", name="Late legacy row", level=1))
            else:
                await live_writer.execute(text(
                    "INSERT INTO wbs_nodes (id, project_id, tenant_id, code, name, lft, rgt, depth, sort_order, "
                    "node_type, metadata, created_at, updated_at) VALUES (:id, :project, :tenant, 'LATE-1', 'Late', "
                    "1000, 1001, 0, 99, 'activity', '{}'::jsonb, now(), now())"),
                    {"id": uuid4(), "project": s.project, "tenant": s.tenant})
            task = asyncio.create_task(approve())
            done, _ = await asyncio.wait({task}, timeout=1.0)
            assert not done, f"the approval did not wait for the live write: {task.result()!r}"
            await live_writer.commit()
        outcome = await asyncio.wait_for(task, timeout=30)
    finally:
        await engine.dispose()
    # the reviewed legacy set changed under the approval: refused, never a deadlock or a divergent baseline
    assert isinstance(outcome, LegacyWBSChangedError), outcome
    assert await db.scalar(select(func.count()).select_from(WBSBaselineORM).where(WBSBaselineORM.project_id == s.project)) == 0


async def test_34d_a_draft_opened_during_an_apply_is_based_on_the_new_baseline(db: AsyncSession) -> None:
    s = await _scope(db)

    async def open_draft(session: AsyncSession) -> UUID | None:
        change_set = await WBSGovernedChangeService(session).create_change_set(
            project_id=s.project, tenant_id=s.tenant, actor=s.author, title="Opened during the apply")
        return change_set.base_baseline_id

    baseline_id, outcome = await _while_an_approval_is_uncommitted(db, s, open_draft)
    assert outcome == baseline_id


async def test_35_a_failure_inside_apply_leaves_everything_unchanged(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    s = await _scope(db)
    _, ids, first = await _baseline_one(db, s)
    live_before = _live_digest(s.project, await _live(db, s.project))
    change_set_id = await _new(db, s, "Doomed")
    await _cmd(db, s, change_set_id, RemoveNode(ids["2"]))
    await _cmd(db, s, change_set_id, AddNode(NodeSpec("Mechanical", "3")))
    await _submit(db, s, change_set_id)

    async def boom(*_args: Any, **_kwargs: Any) -> UUID:
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr(WBSGovernedChangeService, "_event", boom)
    with pytest.raises(RuntimeError):
        await _approve(db, s, change_set_id)
    await db.rollback()
    monkeypatch.undo()
    assert _live_digest(s.project, await _live(db, s.project)) == live_before == first.tree_digest
    assert await db.scalar(select(func.count()).select_from(WBSBaselineORM).where(WBSBaselineORM.project_id == s.project)) == 1
    assert (await _cs(db, change_set_id)).status == "SUBMITTED"
    # and it still applies cleanly afterwards
    assert (await _approve(db, s, change_set_id)).baseline_no == 2


async def test_36_to_41_apply_materializes_exactly_the_approved_baseline(db: AsyncSession) -> None:
    s = await _scope(db)
    first_cs, ids, first = await _baseline_one(db, s)
    first_nodes = {n.node_id: (n.code, n.name, n.parent_id, n.sort_order) for n in (await db.execute(
        select(WBSBaselineNodeORM).where(WBSBaselineNodeORM.baseline_id == first.baseline_id))).scalars()}
    live = await _live(db, s.project)
    assert set(live) == set(ids.values()) and _live_digest(s.project, live) == first.tree_digest  # 39 (first)
    change_set_id = await _new(db, s, "Second")
    await _cmd(db, s, change_set_id, RecodeNode(ids["1.2"], "1.20"))
    await _cmd(db, s, change_set_id, MoveNode(ids["1.1"], None, position=1))
    mech = (await _cmd(db, s, change_set_id, AddNode(NodeSpec("Mechanical", "3")))).node_ids[0]
    await _cmd(db, s, change_set_id, RemoveNode(ids["2"]))
    digest = await _submit(db, s, change_set_id)
    second = await _approve(db, s, change_set_id)
    baseline = await db.get(WBSBaselineORM, second.baseline_id)
    assert baseline is not None
    # 37 / 38: monotonic number, linear parent, digests bound
    assert (baseline.baseline_no, baseline.parent_baseline_id, baseline.change_set_digest) == (2, first.baseline_id, digest)
    # 36: the snapshot is exactly the approved candidate
    snapshot = {n.node_id: (n.code, n.name, n.parent_id, n.sort_order) for n in (await db.execute(
        select(WBSBaselineNodeORM).where(WBSBaselineNodeORM.baseline_id == baseline.id))).scalars()}
    candidate = {n.node_id: (n.code, n.name, n.parent_id, n.sort_order) for n in (await _candidate(db, change_set_id)).values()}
    assert snapshot == candidate and baseline.node_count == len(candidate)
    # 39: live == approved baseline (ids preserved, minted id inserted, retired id gone)
    live = await _live(db, s.project)
    assert set(live) == set(candidate) and ids["2"] not in live and mech in live
    assert live[ids["1.2"]].code == "1.20" and live[ids["1.1"]].parent_id is None
    assert _live_digest(s.project, live) == baseline.tree_digest == second.tree_digest
    # 40: the previous baseline is untouched
    assert {n.node_id: (n.code, n.name, n.parent_id, n.sort_order) for n in (await db.execute(
        select(WBSBaselineNodeORM).where(WBSBaselineNodeORM.baseline_id == first.baseline_id))).scalars()} == first_nodes
    # 41: one applied event per baseline, binding change set AND baseline
    events = sorted(await _events(db, s.project, "wbs.baseline.applied"), key=lambda e: e.payload["baseline_no"])
    payload = events[-1].payload
    assert [e.payload["baseline_no"] for e in events] == [1, 2]
    assert (payload["change_set_id"], payload["baseline_id"], payload["base_baseline_id"]) == (
        str(change_set_id), str(baseline.id), str(first.baseline_id))
    assert (payload["tree_digest"], payload["change_set_digest"], payload["approved_by"]) == (
        baseline.tree_digest, digest, str(s.admin.user_id))
    assert payload["retired"] == [{"node_id": str(ids["2"]), "disposition": "REMOVED", "source": "baseline"}]
    assert {"evidence_refs", "profile_refs", "applied_at", "self_approved", "tenant_id", "project_id"} <= set(payload)
    assert first_cs != change_set_id
    authority = await WBSGovernanceRepository(db).authority(s.project, s.tenant)
    assert (authority.state, authority.baseline_no) == (AuthorityState.APPROVED_BASELINE, 2)


async def test_retired_nodes_with_downstream_links_never_apply(db: AsyncSession) -> None:
    s = await _scope(db)
    _, ids, _ = await _baseline_one(db, s)
    await db.execute(text("SET LOCAL session_replication_role = replica"))  # a RACI row without its stakeholder
    db.add(StakeholderWBSRaciORM(id=uuid4(), tenant_id=s.tenant, project_id=s.project, stakeholder_id=uuid4(),
                                 wbs_item_id=ids["2"], raci_role=RACIRole.RESPONSIBLE))
    await db.commit()
    change_set_id = await _new(db, s, "Drop linked")
    await _cmd(db, s, change_set_id, RemoveNode(ids["2"]))
    await _submit(db, s, change_set_id)
    with pytest.raises(RetiredNodesLinkedError) as caught:
        await _approve(db, s, change_set_id)
    assert caught.value.code == "WBS_NODE_HAS_LINKS"
    await db.rollback()
    assert ids["2"] in await _live(db, s.project)


# =========================================================================== FIRST BASELINE 43-47
async def test_43_to_47_first_baseline_over_legacy_rows(db: AsyncSession) -> None:
    s = await _scope(db)
    legacy = await _legacy_nodes(db, s.tenant, s.project, 23)
    authority = await WBSGovernanceRepository(db).authority(s.project, s.tenant)
    assert authority.state is AuthorityState.LEGACY_UNGOVERNED  # 47 before
    change_set_id = await _new(db, s, "Baseline 1 from schedule")
    # 44: two legacy rows are explicitly adopted (same canonical ids), one explicitly removed
    kept = (await _cmd(db, s, change_set_id, AdoptLegacyNode(legacy[0]))).node_ids[0]
    await _cmd(db, s, change_set_id, AdoptLegacyNode(legacy[1], parent_id=kept))
    await _cmd(db, s, change_set_id, RemoveNode(legacy[2]))
    new = (await _cmd(db, s, change_set_id, AddNode(NodeSpec("Commissioning", "C")))).node_ids[0]
    await _cmd(db, s, change_set_id, RecodeNode(legacy[1], "SCH-001.1"))
    nodes = await _candidate(db, change_set_id)
    assert {nodes[legacy[0]].origin_kind, nodes[legacy[1]].origin_kind} == {"adopted_legacy"}
    assert len(nodes) == 3  # 43: nothing else was auto-adopted
    authority = await WBSGovernanceRepository(db).authority(s.project, s.tenant)
    assert (authority.state, authority.draft_exists, authority.approved) == (AuthorityState.LEGACY_UNGOVERNED, True, False)
    await _submit(db, s, change_set_id)
    retired = {r.node_id: r for r in (await db.execute(select(WBSChangeSetRetirementORM)
                                                        .where(WBSChangeSetRetirementORM.change_set_id == change_set_id))).scalars()}
    # 45: every unselected legacy row is dispositioned, with a snapshot of what it was
    assert set(retired) == set(legacy[2:]) and retired[legacy[2]].disposition == "REMOVED"
    assert {r.disposition for i, r in retired.items() if i != legacy[2]} == {"RETIRED_ON_BASELINE"}
    assert retired[legacy[5]].snapshot["code"] == "SCH-006" and retired[legacy[5]].source == "legacy"
    assert (await WBSGovernanceRepository(db).authority(s.project, s.tenant)).approved is False  # 47 until apply
    result = await _approve(db, s, change_set_id)
    live = await _live(db, s.project)
    assert set(live) == {legacy[0], legacy[1], new}  # 46: the approved tree IS the live WBS
    assert live[legacy[1]].parent_id == legacy[0] and live[legacy[1]].code == "SCH-001.1"
    assert live[legacy[0]].planned_start is None and live[legacy[0]].name == "Schedule activity 1"
    authority = await WBSGovernanceRepository(db).authority(s.project, s.tenant)
    assert (authority.state, authority.baseline_id, authority.legacy_node_count) == (
        AuthorityState.APPROVED_BASELINE, result.baseline_id, 0)
    event = (await _events(db, s.project, "wbs.baseline.applied"))[0]
    assert {r["node_id"] for r in event.payload["retired"]} == {str(i) for i in legacy[2:]}


async def test_legacy_rows_changed_after_submission_fail_closed(db: AsyncSession) -> None:
    s = await _scope(db)
    legacy = await _legacy_nodes(db, s.tenant, s.project, 3)
    change_set_id = await _new(db, s)
    await _cmd(db, s, change_set_id, AdoptLegacyNode(legacy[0]))
    await _submit(db, s, change_set_id)
    # pre-baseline transitional writer still works, so a new legacy row can appear after submit
    await SQLAlchemyWBSRepository(db).create(s.tenant, WBSItem(project_id=s.project, code="LATE-1", name="Late", level=1))
    await db.commit()
    with pytest.raises(LegacyWBSChangedError):
        await _approve(db, s, change_set_id)
    await db.rollback()
    assert await db.scalar(select(func.count()).select_from(WBSBaselineORM).where(WBSBaselineORM.project_id == s.project)) == 0
    # reopen + resubmit re-dispositions the new row; then it applies
    await _svc(db).reopen(project_id=s.project, change_set_id=change_set_id, tenant_id=s.tenant, actor=s.author)
    await db.commit()
    await _submit(db, s, change_set_id)
    # an edit of a retired legacy row after submission is also caught
    await db.execute(update(WBSNodeORM).where(WBSNodeORM.id == legacy[1]).values(description="edited later"))
    await db.commit()
    with pytest.raises(LegacyWBSChangedError):
        await _approve(db, s, change_set_id)
    await db.rollback()


# =========================================================================== DIRECT BYPASS 48-52
async def test_48_to_51_direct_writes_are_closed_after_the_first_baseline(db: AsyncSession) -> None:
    s = await _scope(db)
    _, ids, _ = await _baseline_one(db, s)
    repo = SQLAlchemyWBSRepository(db)
    with pytest.raises(WBSGovernedByBaselineError):  # 48 create
        await repo.create(s.tenant, WBSItem(project_id=s.project, code="9", name="Sneaky", level=1))
    await db.rollback()
    with pytest.raises(WBSGovernedByBaselineError):  # bulk paths too
        await repo.bulk_create_from_dicts(s.project, [{"code": "9", "name": "Sneaky"}], s.tenant)
    await db.rollback()
    item = await repo.get_by_id(ids["2"], s.tenant)
    assert item is not None
    for change in ({"name": "Renamed"}, {"code": "2X"}, {"parent_id": ids["1"]}, {"sort_order": 1}):  # 49 / 50
        with pytest.raises(WBSGovernedByBaselineError):
            await repo.update(ids["2"], dataclasses.replace(item, **change), s.tenant)
        await db.rollback()
    with pytest.raises(WBSGovernedByBaselineError):  # 51 delete
        await repo.delete(ids["2"], s.tenant)
    await db.rollback()
    # non-governed attributes stay directly editable (schedule/cost data, PC-2a.3/PC-2b consumers)
    updated = await repo.update(ids["2"], dataclasses.replace(item, description="Cables", planned_start=datetime(2026, 1, 5, tzinfo=UTC)), s.tenant)
    await db.commit()
    assert updated is not None and updated.description == "Cables" and updated.code == "2"
    # the database refuses the same bypasses for any writer, even with a forged apply marker
    for sql in ("UPDATE wbs_nodes SET name = 'x' WHERE id = :n", "UPDATE wbs_nodes SET parent_id = NULL, sort_order = 9 WHERE id = :n",
                "DELETE FROM wbs_nodes WHERE id = :n"):
        await _expect_db_rejection(db, sql, {"n": ids["1.1"]}, "governed by an approved baseline")
    applied = (await db.execute(select(WBSChangeSetORM.id).where(WBSChangeSetORM.project_id == s.project))).scalar_one()
    await db.execute(text("SELECT set_config('c2pro.wbs_governed_apply', :c, true)"), {"c": str(applied)})
    with _rejected("governed by an approved baseline"):
        await db.execute(text("UPDATE wbs_nodes SET name = 'x' WHERE id = :n"), {"n": ids["1.1"]})
    await db.rollback()


async def test_52_candidate_editing_stays_open_after_the_baseline(db: AsyncSession) -> None:
    s = await _scope(db)
    _, ids, _ = await _baseline_one(db, s)
    change_set_id = await _new(db, s, "Change")
    assert (await _cs(db, change_set_id)).entry_mode == "CHANGE_BASELINE"
    assert set(await _candidate(db, change_set_id)) == set(ids.values())  # seeded from Baseline #1
    await _cmd(db, s, change_set_id, UpdateNode(ids["2"], {"name": "Electrical works"}))
    assert (await _live(db, s.project))[ids["2"]].name == "Electrical"  # live untouched until approve


# =========================================================================== TENANCY 53-55
async def test_53_54_cross_tenant_and_cross_project_are_refused(db: AsyncSession) -> None:
    owner = await _scope(db)
    change_set_id = await _new(db, owner)
    await _tree(db, owner, change_set_id)
    await _submit(db, owner, change_set_id)
    intruder = await _scope(db)
    revision, digest = await _rev(db, change_set_id), str((await _cs(db, change_set_id)).submitted_digest)
    with pytest.raises((WBSChangeSetNotFoundError, WBSProjectNotFoundError)):  # 53 other tenant
        await _svc(db).approve(project_id=owner.project, change_set_id=change_set_id, tenant_id=intruder.tenant,
                               actor=intruder.admin, expected_revision=revision, expected_digest=digest)
    await db.rollback()
    other_project = await _project(db, owner.tenant)
    with pytest.raises(WBSChangeSetNotFoundError):  # 54 same tenant, other project
        await _svc(db).approve(project_id=other_project, change_set_id=change_set_id, tenant_id=owner.tenant,
                               actor=owner.admin, expected_revision=revision, expected_digest=digest)
    await db.rollback()
    with pytest.raises(WBSChangeSetNotFoundError):
        await _svc(db).execute(project_id=other_project, change_set_id=change_set_id, tenant_id=owner.tenant,
                               actor=owner.author, expected_revision=revision, command=AddNode(NodeSpec("x", "x")))
    await db.rollback()
    assert (await _cs(db, change_set_id)).status == "SUBMITTED"
    assert await _live(db, owner.project) == {} and await _live(db, other_project) == {}


async def test_retirements_are_frozen_outside_draft(db: AsyncSession) -> None:
    s = await _scope(db)
    _, ids, _ = await _baseline_one(db, s)
    change_set_id = await _new(db, s, "Remove")
    await _cmd(db, s, change_set_id, RemoveNode(ids["2"]))
    await _submit(db, s, change_set_id)
    await _expect_db_rejection(db, "DELETE FROM wbs_change_set_retirements WHERE change_set_id = :c",
                               {"c": change_set_id}, "editable only while the change set is DRAFT")
    await _expect_db_rejection(db, "UPDATE wbs_change_set_retirements SET disposition = 'SPLIT' WHERE change_set_id = :c",
                               {"c": change_set_id}, "immutable")
