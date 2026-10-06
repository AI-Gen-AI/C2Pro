"""PC-2a.1 (#895, ADR-029) -- WBS governance foundation on a REAL PostgreSQL.

TS-INT-PC2A1-WBS-GOV-001. Change sets, candidate trees, lineage and immutable baselines,
their database-enforced invariants and the DERIVED authority resolver.

Baselines are created here by a CONTROLLED TEST FIXTURE (``_apply``) that writes the
persistence rows directly: the governed approve = apply command is PC-2a.2 (#896) and no
product code path creates a baseline yet. The fixture still has to satisfy every database
guard (submitted digest, base, admin approver, SoD, node count), which is what this proves.

RLS isolation of the new tables is proven on a migrated scratch database
(tests/integration/product_control/test_pc2a1_wbs_governance_migration_db.py).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import SubscriptionPlan, Tenant, User, UserRole
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.wbs.adapters.persistence.governance_models import (
    WBSBaselineNodeORM,
    WBSBaselineORM,
    WBSChangeSetLineageORM,
    WBSChangeSetNodeORM,
    WBSChangeSetORM,
)
from src.wbs.adapters.persistence.governance_repository import (
    Actor,
    RevisionConflictError,
    WBSGovernanceRepository,
    candidate_digest_node,
)
from src.wbs.adapters.persistence.models import WBSNodeORM
from src.wbs.domain.digest import LineageEdge, change_set_digest, tree_digest
from src.wbs.domain.governance import (
    ActorKind,
    AuthorityState,
    ChangeSetOrigin,
    ChangeSetStatus,
    EntryMode,
    GovernanceRuleError,
    LineageKind,
)
from tests.support.legacy_wbs import governed_apply_state, seed_legacy_rows

pytestmark = pytest.mark.asyncio

DB_ERRORS = (IntegrityError, DBAPIError)
TEST_PASSWORD_HASH = "$2b$12$abcdefghijklmnopqrstuuu1n8V0Yq9nE1u3Xc1qCq8m8pG7xF5yW"


# --------------------------------------------------------------------------- helpers
async def _tenant(db: AsyncSession, settings: dict[str, Any] | None = None) -> UUID:
    tenant_id = uuid4()
    db.add(Tenant(id=tenant_id, name="t", slug=f"t-{tenant_id.hex[:8]}",
                  subscription_plan=SubscriptionPlan.PROFESSIONAL, ai_budget_monthly=100.0,
                  settings=settings or {}))
    await db.commit()
    return tenant_id


async def _project(db: AsyncSession, tenant_id: UUID) -> UUID:
    project_id = uuid4()
    await db.execute(
        text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, "
             "updated_at) VALUES (:id, :tid, 'pc2a1', :code, 'construction', 'active', 'EUR', now(), now())"),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return project_id


async def _user(db: AsyncSession, tenant_id: UUID, role: UserRole) -> Actor:
    user = User(id=uuid4(), tenant_id=tenant_id, email=f"{role.value}-{uuid4().hex[:8]}@example.com",
                hashed_password=TEST_PASSWORD_HASH, first_name="T", last_name=role.value, role=role,
                is_active=True, is_verified=True)
    db.add(user)
    await db.commit()
    return Actor(user_id=user.id, kind=ActorKind.HUMAN, role=role.value)


async def _legacy_nodes(db: AsyncSession, tenant_id: UUID, project_id: UUID, count: int) -> list[UUID]:
    """LEGACY_UNGOVERNED rows (pre-governance data, loaded out of band: no app path writes them)."""
    ids = await seed_legacy_rows(db, tenant_id, project_id, count)
    await db.commit()
    return ids


def _check_reason(exc: BaseException, fragments: tuple[str, ...]) -> None:
    """A rejection only counts for the INTENDED reason -- never a typo in the probe SQL."""
    message = str(exc)
    orig = getattr(exc, "orig", None)
    state = getattr(orig, "sqlstate", None) or getattr(getattr(orig, "__cause__", None), "sqlstate", None)
    if os.environ.get("PC2A1_TRACE_REJECTIONS"):
        print(f"REJECTION sqlstate={state} :: {message.splitlines()[0][:220]}")
    # Class 42 is syntax / undefined object / datatype -- i.e. a broken probe -- except
    # 42501 insufficient_privilege, which is how the approver/submitter guards refuse.
    assert state == "42501" or not str(state or "").startswith("42"), f"rejected for a wrong reason: {message}"
    if fragments:
        assert any(fragment in message for fragment in fragments), message


@contextmanager
def _rejected(*fragments: str) -> Iterator[None]:
    with pytest.raises(DB_ERRORS) as info:
        yield
    _check_reason(info.value, fragments)


async def _expect_db_rejection(db: AsyncSession, sql: str, params: dict[str, Any], *fragments: str) -> None:
    """The statement (or the commit that runs deferred checks) is rejected for that reason."""
    with _rejected(*fragments):
        await db.execute(text(sql), params)
        await db.commit()
    await db.rollback()


async def _expect_live_rejection(db: AsyncSession, s: Scope, sql: str, params: dict[str, Any], *fragments: str) -> None:
    """Governed live columns are writable only inside an apply (PC-2a.2); even there, the
    database's own constraints still refuse a bad value."""
    with _rejected(*fragments):
        async with governed_apply_state(db, s.tenant, s.project):
            await db.execute(text(sql), params)
        await db.commit()
    await db.rollback()


class Scope:
    """A tenant + project + the usual human actors."""

    def __init__(self, tenant: UUID, project: UUID, author: Actor, admin: Actor, admin2: Actor) -> None:
        self.tenant, self.project, self.author, self.admin, self.admin2 = tenant, project, author, admin, admin2


async def _scope(db: AsyncSession, settings: dict[str, Any] | None = None) -> Scope:
    tenant = await _tenant(db, settings)
    project = await _project(db, tenant)
    return Scope(tenant, project, await _user(db, tenant, UserRole.USER), await _user(db, tenant, UserRole.ADMIN),
                 await _user(db, tenant, UserRole.ADMIN))


async def _draft_with_tree(db: AsyncSession, s: Scope, title: str = "First WBS") -> tuple[UUID, dict[str, UUID]]:
    """A DRAFT proposing Civil(1) > Earthworks(1.1), Foundations(1.2); returns (id, ids by code)."""
    repo = WBSGovernanceRepository(db)
    change_set = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title=title)
    rev = change_set.revision
    civil = await repo.add_node(change_set.id, s.tenant, expected_revision=rev, name="Civil", code="1", sort_order=1,
                                decomposition_kind="core:discipline", control_level="control_account")
    earth = await repo.add_node(change_set.id, s.tenant, expected_revision=rev + 1, name="Earthworks", code="1.1",
                                sort_order=1, parent_id=civil, control_level="work_package",
                                dictionary={"scope_statement": "Cut and fill", "deliverables": ["Platform"]})
    found = await repo.add_node(change_set.id, s.tenant, expected_revision=rev + 2, name="Foundations", code="1.2",
                                sort_order=2, parent_id=civil, control_level="work_package")
    await db.commit()
    return change_set.id, {"1": civil, "1.1": earth, "1.2": found}


async def _revision(db: AsyncSession, change_set_id: UUID) -> int:
    await db.commit()
    return int(await db.scalar(select(WBSChangeSetORM.revision).where(WBSChangeSetORM.id == change_set_id)))


async def _submit(db: AsyncSession, s: Scope, change_set_id: UUID, actor: Actor | None = None) -> str:
    repo = WBSGovernanceRepository(db)
    digest = await repo.submit(change_set_id, s.tenant, expected_revision=await _revision(db, change_set_id),
                               actor=actor or s.author)
    await db.commit()
    return digest


async def _apply(db: AsyncSession, s: Scope, change_set_id: UUID, approver: Actor, *,
                 applied_at: datetime | None = None, self_approved: bool = False) -> UUID:
    """CONTROLLED TEST FIXTURE (not product code): persist a baseline from a SUBMITTED change set."""
    repo = WBSGovernanceRepository(db)
    await db.commit()
    change_set = await db.get(WBSChangeSetORM, change_set_id, populate_existing=True)
    assert change_set is not None
    detail = await repo.get_change_set(change_set_id, change_set.project_id, s.tenant)
    assert detail is not None
    parent_no = 0
    if change_set.base_baseline_id is not None:
        parent = await db.get(WBSBaselineORM, change_set.base_baseline_id)
        assert parent is not None
        parent_no = parent.baseline_no
    baseline_id = uuid4()
    now = datetime.now(UTC)
    db.add(WBSBaselineORM(
        id=baseline_id, tenant_id=s.tenant, project_id=change_set.project_id, baseline_no=parent_no + 1,
        parent_baseline_id=change_set.base_baseline_id, source_change_set_id=change_set.id,
        tree_digest=tree_digest(change_set.project_id, [candidate_digest_node(n) for n in detail.nodes]),
        change_set_digest=change_set.submitted_digest, node_count=len(detail.nodes),
        approved_by=approver.user_id, approved_by_kind="human", self_approved=self_approved,
        profile_refs=list(change_set.profile_refs or []), applied_at=applied_at or now,
    ))
    await db.flush()
    for node in detail.nodes:
        db.add(WBSBaselineNodeORM(
            baseline_id=baseline_id, node_id=node.node_id, tenant_id=s.tenant, project_id=change_set.project_id,
            parent_id=node.parent_id, sort_order=node.sort_order, code=node.code, name=node.name,
            control_level=node.control_level, decomposition_kind=node.decomposition_kind, dictionary=node.dictionary,
        ))
    await db.flush()
    change_set.status = ChangeSetStatus.APPLIED.value
    change_set.decided_by = approver.user_id
    change_set.decided_at = now
    change_set.decided_self_approval = self_approved
    change_set.closed_at = now
    await db.commit()
    return baseline_id


async def _baseline_one(db: AsyncSession, s: Scope) -> tuple[UUID, dict[str, UUID]]:
    change_set_id, ids = await _draft_with_tree(db, s)
    await _submit(db, s, change_set_id)
    return await _apply(db, s, change_set_id, s.admin), ids


# =========================================================================== positive
async def test_p1_manual_empty_base_draft(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set = await WBSGovernanceRepository(db).create_change_set(
        project_id=s.project, tenant_id=s.tenant, actor=s.author, title="Initial WBS")
    await db.commit()
    assert (change_set.status, change_set.revision, change_set.base_baseline_id) == ("DRAFT", 1, None)
    assert (change_set.origin, change_set.entry_mode) == ("manual", "GENERATE")


async def test_p2_add_edit_move_and_reorder_candidate_nodes(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, ids = await _draft_with_tree(db, s)
    repo = WBSGovernanceRepository(db)
    rev = await _revision(db, change_set_id)
    # swap sibling order in one transaction (deferred uniqueness), rename and recode
    await repo.update_node(change_set_id, ids["1.1"], s.tenant, expected_revision=rev, sort_order=2)
    await repo.update_node(change_set_id, ids["1.2"], s.tenant, expected_revision=rev + 1, sort_order=1,
                           name="Foundations & piling", code="1.0")
    await db.commit()
    # move Earthworks to the top level (project is the implicit root)
    await repo.update_node(change_set_id, ids["1.1"], s.tenant, expected_revision=rev + 2, parent_id=None, sort_order=2)
    await db.commit()
    detail = await repo.get_change_set(change_set_id, s.project, s.tenant)
    assert detail is not None
    by_id = {n.node_id: n for n in detail.nodes}
    assert (by_id[ids["1.2"]].sort_order, by_id[ids["1.2"]].name, by_id[ids["1.2"]].code) == (
        1, "Foundations & piling", "1.0")
    assert (by_id[ids["1.1"]].parent_id, by_id[ids["1.1"]].sort_order) == (None, 2)
    assert detail.change_set.revision == rev + 3


async def test_p3_dictionary_is_persisted_and_digest_bound(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, ids = await _draft_with_tree(db, s)
    repo = WBSGovernanceRepository(db)
    detail = await repo.get_change_set(change_set_id, s.project, s.tenant)
    assert detail is not None
    stored = next(n for n in detail.nodes if n.node_id == ids["1.1"]).dictionary
    assert stored is not None and stored["schema_version"] == "wbs-dictionary/v1"
    assert stored["scope_statement"] == "Cut and fill" and stored["deliverables"] == ["Platform"]
    before = repo.compute_change_set_digest(detail, 1)
    await repo.update_node(change_set_id, ids["1.1"], s.tenant, expected_revision=await _revision(db, change_set_id),
                           dictionary={"scope_statement": "Cut and fill", "deliverables": ["Platform", "Drainage"]})
    await db.commit()
    after_detail = await repo.get_change_set(change_set_id, s.project, s.tenant)
    assert after_detail is not None
    assert repo.compute_change_set_digest(after_detail, 1) != before
    # relational links never live inside the dictionary
    with pytest.raises(ValueError):
        await repo.update_node(change_set_id, ids["1.1"], s.tenant,
                               expected_revision=await _revision(db, change_set_id),
                               dictionary={"risk_ids": ["r-1"]})
    await db.rollback()


async def test_p4_n5_existing_and_adopted_legacy_ids_are_preserved(db: AsyncSession) -> None:
    s = await _scope(db)
    legacy = await _legacy_nodes(db, s.tenant, s.project, 2)
    repo = WBSGovernanceRepository(db)
    first = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="B1")
    first_id = first.id
    kept = await repo.add_node(first_id, s.tenant, expected_revision=1, name="Kept legacy", code="1", sort_order=1,
                               keep_node_id=legacy[0])
    await db.commit()
    assert kept == legacy[0]
    node = await db.get(WBSChangeSetNodeORM, (first_id, kept))
    assert node is not None and node.origin_kind == "adopted_legacy"
    await _submit(db, s, first_id)
    await _apply(db, s, first_id, s.admin)
    second = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="B2")
    second_id = second.id
    assert second.entry_mode == EntryMode.CHANGE_BASELINE.value and second.base_baseline_id is not None
    again = await repo.add_node(second_id, s.tenant, expected_revision=1, name="Renamed", code="9", sort_order=1,
                                keep_node_id=legacy[0])
    await db.commit()
    reused = await db.get(WBSChangeSetNodeORM, (second_id, again))
    assert again == legacy[0] and reused is not None and reused.origin_kind == "existing"


async def test_p5_n4_new_candidate_ids_are_server_minted(db: AsyncSession) -> None:
    s = await _scope(db)
    legacy = await _legacy_nodes(db, s.tenant, s.project, 1)
    repo = WBSGovernanceRepository(db)
    change_set = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="x")
    change_set_id = change_set.id
    minted = await repo.add_node(change_set_id, s.tenant, expected_revision=1, name="New", code="1", sort_order=1)
    await db.commit()
    node = await db.get(WBSChangeSetNodeORM, (change_set_id, minted))
    assert node is not None and node.origin_kind == "minted" and minted not in legacy
    # A client cannot smuggle an id in: an unknown "kept" id is refused by the database...
    with _rejected("only a first baseline may adopt"):
        await repo.add_node(change_set_id, s.tenant, expected_revision=2, name="Fake", code="2", sort_order=2,
                            keep_node_id=uuid4())
    await db.rollback()
    # ...and a "minted" row may not collide with a live id.
    await _expect_db_rejection(
        db, "INSERT INTO wbs_change_set_nodes (change_set_id, node_id, tenant_id, project_id, sort_order, name, "
            "origin_kind) VALUES (:cs, :node, :t, :p, 5, 'collide', 'minted')",
        {"cs": change_set_id, "node": legacy[0], "t": s.tenant, "p": s.project}, "a minted WBS id must be new")


async def test_p6_lineage_is_persisted_and_digest_bound(db: AsyncSession) -> None:
    s = await _scope(db)
    _, ids = await _baseline_one(db, s)
    repo = WBSGovernanceRepository(db)
    change_set = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="Split")
    change_set_id = change_set.id
    rev = 1
    civil = await repo.add_node(change_set_id, s.tenant, expected_revision=rev, name="Civil", code="1", sort_order=1,
                                keep_node_id=ids["1"])
    cut = await repo.add_node(change_set_id, s.tenant, expected_revision=rev + 1, name="Cut", code="1.1",
                              sort_order=1, parent_id=civil, control_level="work_package")
    fill = await repo.add_node(change_set_id, s.tenant, expected_revision=rev + 2, name="Fill", code="1.3",
                               sort_order=3, parent_id=civil, control_level="work_package")
    await repo.add_node(change_set_id, s.tenant, expected_revision=rev + 3, name="Foundations", code="1.2",
                        sort_order=2, parent_id=civil, keep_node_id=ids["1.2"])
    for offset, target in enumerate((cut, fill)):
        await repo.add_lineage(change_set_id, s.tenant, expected_revision=rev + 4 + offset, kind=LineageKind.SPLIT,
                               source_node_id=ids["1.1"], target_node_id=target)
    await db.commit()
    detail = await repo.get_change_set(change_set_id, s.project, s.tenant)
    assert detail is not None
    assert {(e.kind, e.source_node_id, e.target_node_id) for e in detail.lineage} == {
        ("SPLIT", ids["1.1"], cut), ("SPLIT", ids["1.1"], fill)}
    with_lineage = repo.compute_change_set_digest(detail, 3)
    await repo.remove_lineage(change_set_id, s.tenant, expected_revision=await _revision(db, change_set_id),
                              kind=LineageKind.SPLIT, source_node_id=ids["1.1"], target_node_id=fill)
    await db.commit()
    trimmed = await repo.get_change_set(change_set_id, s.project, s.tenant)
    assert trimmed is not None and repo.compute_change_set_digest(trimmed, 3) != with_lineage
    # lineage targets must be NEW identities; sources must come from the base baseline
    await _expect_db_rejection(
        db, "INSERT INTO wbs_change_set_lineage (change_set_id, kind, source_node_id, target_node_id, tenant_id, "
            "project_id) VALUES (:cs, 'SPLIT', :src, :tgt, :t, :p)",
        {"cs": change_set_id, "src": ids["1.1"], "tgt": civil, "t": s.tenant, "p": s.project}, "a lineage target must be a minted identity")
    await _expect_db_rejection(
        db, "INSERT INTO wbs_change_set_lineage (change_set_id, kind, source_node_id, target_node_id, tenant_id, "
            "project_id) VALUES (:cs, 'MERGE', :src, :tgt, :t, :p)",
        {"cs": change_set_id, "src": uuid4(), "tgt": cut, "t": s.tenant, "p": s.project}, "a lineage source must be an identity")


async def test_p7_submit_freezes_the_digest(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, _ = await _draft_with_tree(db, s)
    digest = await _submit(db, s, change_set_id)
    change_set = await db.get(WBSChangeSetORM, change_set_id, populate_existing=True)
    assert change_set is not None
    assert (change_set.status, change_set.submitted_digest, change_set.submitted_revision) == (
        "SUBMITTED", digest, change_set.revision)
    detail = await WBSGovernanceRepository(db).get_change_set(change_set_id, s.project, s.tenant)
    assert detail is not None
    independent = change_set_digest(
        project_id=s.project, change_set_id=change_set_id, base_baseline_id=None,
        submitted_revision=change_set.revision, nodes=[candidate_digest_node(n) for n in detail.nodes],
        lineage=[LineageEdge(e.kind, e.source_node_id, e.target_node_id) for e in detail.lineage])
    assert independent == digest


async def test_p8_baseline_reconstructs_the_exact_tree(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, _ = await _draft_with_tree(db, s)
    await _submit(db, s, change_set_id)
    candidate = await WBSGovernanceRepository(db).get_change_set(change_set_id, s.project, s.tenant)
    assert candidate is not None
    await _apply(db, s, change_set_id, s.admin)
    baseline = await WBSGovernanceRepository(db).get_baseline(s.project, s.tenant, 1)
    assert baseline is not None
    assert baseline.recomputed_tree_digest == baseline.baseline.tree_digest == tree_digest(
        s.project, [candidate_digest_node(n) for n in candidate.nodes])
    assert {(n.node_id, n.parent_id, n.sort_order, n.code) for n in baseline.nodes} == {
        (n.node_id, n.parent_id, n.sort_order, n.code) for n in candidate.nodes}


async def test_p9_as_of_baseline_query(db: AsyncSession) -> None:
    s = await _scope(db)
    t1 = datetime(2026, 1, 10, tzinfo=UTC)
    t2 = datetime(2026, 3, 10, tzinfo=UTC)
    first_id, ids = await _draft_with_tree(db, s)
    await _submit(db, s, first_id)
    await _apply(db, s, first_id, s.admin, applied_at=t1)
    repo = WBSGovernanceRepository(db)
    second = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="v2")
    second_id = second.id
    await repo.add_node(second_id, s.tenant, expected_revision=1, name="Civil works", code="1", sort_order=1,
                        keep_node_id=ids["1"])
    await db.commit()
    await _submit(db, s, second_id)
    await _apply(db, s, second_id, s.admin, applied_at=t2)
    assert await repo.baseline_as_of(s.project, s.tenant, t1 - timedelta(days=1)) is None
    between = await repo.baseline_as_of(s.project, s.tenant, t1 + timedelta(days=1))
    latest = await repo.baseline_as_of(s.project, s.tenant, datetime.now(UTC))
    assert between is not None and between.baseline.baseline_no == 1 and len(between.nodes) == 3
    assert latest is not None and latest.baseline.baseline_no == 2 and [n.name for n in latest.nodes] == ["Civil works"]


async def test_p10_authority_is_honest_in_every_state(db: AsyncSession) -> None:
    s = await _scope(db)
    repo = WBSGovernanceRepository(db)
    assert (await repo.authority(s.project, s.tenant)).display_state == "NO_WBS"
    change_set_id, _ = await _draft_with_tree(db, s)
    draft = await repo.authority(s.project, s.tenant)
    assert draft.display_state == "DRAFT_ONLY" and draft.approved is False
    await _submit(db, s, change_set_id)
    submitted = await repo.authority(s.project, s.tenant)
    assert submitted.display_state == "DRAFT_ONLY" and submitted.approved is False
    baseline_id = await _apply(db, s, change_set_id, s.admin)
    approved = await repo.authority(s.project, s.tenant)
    assert (approved.state, approved.baseline_id, approved.baseline_no) == (
        AuthorityState.APPROVED_BASELINE, baseline_id, 1)
    assert approved.tree_digest is not None and approved.draft_exists is False
    await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="next")
    await db.commit()
    with_draft = await repo.authority(s.project, s.tenant)
    assert with_draft.approved is True and with_draft.draft_exists is True


# =========================================================================== negative
async def test_n1_cross_tenant_change_set_is_rejected(db: AsyncSession) -> None:
    a = await _scope(db)
    b = await _scope(db)
    with _rejected("fk_wbs_change_sets_project"):
        await WBSGovernanceRepository(db).create_change_set(project_id=a.project, tenant_id=b.tenant, actor=b.author,
                                                            title="foreign project")
        await db.commit()
    await db.rollback()


async def test_n2_cross_project_candidate_is_rejected(db: AsyncSession) -> None:
    s = await _scope(db)
    other_project = await _project(db, s.tenant)
    change_set_id, _ = await _draft_with_tree(db, s)
    await _expect_db_rejection(
        db, "INSERT INTO wbs_change_set_nodes (change_set_id, node_id, tenant_id, project_id, sort_order, name, "
            "origin_kind) VALUES (:cs, :node, :t, :p, 9, 'elsewhere', 'minted')",
        {"cs": change_set_id, "node": uuid4(), "t": s.tenant, "p": other_project}, "fk_wbs_change_set_nodes_change_set")


async def test_n3_candidate_parent_cannot_come_from_another_change_set(db: AsyncSession) -> None:
    s = await _scope(db)
    first, first_ids = await _draft_with_tree(db, s)
    second, _ = await _draft_with_tree(db, s, title="Competing draft")
    with _rejected("fk_wbs_change_set_nodes_parent"):
        await WBSGovernanceRepository(db).add_node(second, s.tenant, expected_revision=await _revision(db, second),
                                                   name="Orphan", code="9", sort_order=9, parent_id=first_ids["1"])
        await db.commit()
    await db.rollback()


async def test_n6_retired_ids_are_never_reused(db: AsyncSession) -> None:
    s = await _scope(db)
    _, ids = await _baseline_one(db, s)
    repo = WBSGovernanceRepository(db)
    # Baseline #2 retires Foundations (1.2).
    second = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="retire")
    second_id = second.id
    civil = await repo.add_node(second_id, s.tenant, expected_revision=1, name="Civil", code="1", sort_order=1,
                                keep_node_id=ids["1"])
    await repo.add_node(second_id, s.tenant, expected_revision=2, name="Earthworks", code="1.1", sort_order=1,
                        parent_id=civil, keep_node_id=ids["1.1"])
    await db.commit()
    await _submit(db, s, second_id)
    await _apply(db, s, second_id, s.admin)
    third = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="revive")
    third_id = third.id
    await db.commit()
    with _rejected("an existing candidate node must reuse an id of the base baseline"):  # not in the base (#2): cannot be "kept"
        await repo.add_node(third_id, s.tenant, expected_revision=1, name="Foundations", code="1.2", sort_order=2,
                            keep_node_id=ids["1.2"])
    await db.rollback()
    await _expect_db_rejection(  # and cannot be re-minted either
        db, "INSERT INTO wbs_change_set_nodes (change_set_id, node_id, tenant_id, project_id, sort_order, name, "
            "origin_kind) VALUES (:cs, :node, :t, :p, 2, 'revived', 'minted')",
        {"cs": third_id, "node": ids["1.2"], "t": s.tenant, "p": s.project}, "a minted WBS id must be new")


async def test_n7_n8_baselines_and_baseline_nodes_are_immutable(db: AsyncSession) -> None:
    s = await _scope(db)
    baseline_id, ids = await _baseline_one(db, s)
    await _expect_db_rejection(db, "UPDATE wbs_baselines SET node_count = node_count WHERE id = :b", {"b": baseline_id}, "WBS baselines are immutable")
    await _expect_db_rejection(db, "DELETE FROM wbs_baselines WHERE id = :b", {"b": baseline_id}, "WBS baselines are immutable")
    await _expect_db_rejection(db, "UPDATE wbs_baseline_nodes SET name = 'edited' WHERE baseline_id = :b",
                               {"b": baseline_id}, "WBS baseline nodes are immutable")
    await _expect_db_rejection(db, "DELETE FROM wbs_baseline_nodes WHERE baseline_id = :b", {"b": baseline_id}, "WBS baseline nodes are immutable")
    await _expect_db_rejection(
        db, "INSERT INTO wbs_baseline_nodes (baseline_id, node_id, tenant_id, project_id, sort_order, code, name) "
            "VALUES (:b, :n, :t, :p, 9, '9', 'late addition')",
        {"b": baseline_id, "n": uuid4(), "t": s.tenant, "p": s.project}, "cannot gain or lose nodes")
    still = await WBSGovernanceRepository(db).get_baseline(s.project, s.tenant, 1)
    assert still is not None and len(still.nodes) == 3 and still.recomputed_tree_digest == still.baseline.tree_digest


async def test_n9_applied_and_rejected_history_is_immutable(db: AsyncSession) -> None:
    s = await _scope(db)
    applied_id, _ = await _draft_with_tree(db, s)
    await _submit(db, s, applied_id)
    await _apply(db, s, applied_id, s.admin)
    await _expect_db_rejection(db, "UPDATE wbs_change_sets SET title = 'rewritten' WHERE id = :c", {"c": applied_id}, "APPLIED and immutable")
    await _expect_db_rejection(db, "DELETE FROM wbs_change_sets WHERE id = :c", {"c": applied_id}, "withdraw instead of deleting")
    await _expect_db_rejection(db, "DELETE FROM wbs_change_set_nodes WHERE change_set_id = :c", {"c": applied_id}, "editable only while the change set is DRAFT")
    rejected_id, _ = await _draft_with_tree(db, s, title="to reject")
    await _submit(db, s, rejected_id)
    await db.execute(
        update(WBSChangeSetORM).where(WBSChangeSetORM.id == rejected_id).values(
            status="REJECTED", decided_by=s.admin.user_id, decided_at=func.now(), decided_self_approval=False,
            decision_reason="Out of scope", closed_at=func.now()))
    await db.commit()
    await _expect_db_rejection(db, "UPDATE wbs_change_sets SET status = 'DRAFT', decided_by = NULL, decided_at = NULL, "
                                   "decided_self_approval = NULL, closed_at = NULL, submitted_digest = NULL, "
                                   "submitted_revision = NULL, submitted_by = NULL, submitted_at = NULL WHERE id = :c",
                               {"c": rejected_id}, "REJECTED and immutable")


async def test_n10_n12_baseline_numbers_are_monotonic_and_baseline_one_is_unique(db: AsyncSession) -> None:
    s = await _scope(db)
    first, _ = await _draft_with_tree(db, s)
    competitor, _ = await _draft_with_tree(db, s, title="competing first baseline")
    await _submit(db, s, first)
    await _submit(db, s, competitor)
    await _apply(db, s, first, s.admin)
    # A second "Baseline #1" for the project is impossible, whatever the fixture tries.
    with _rejected("already has an approved first baseline"):
        await _apply(db, s, competitor, s.admin)
    await db.rollback()
    # A skipped number (or a non-current parent) is refused too.
    repo = WBSGovernanceRepository(db)
    nxt = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="next")
    nxt_id = nxt.id
    await repo.add_node(nxt_id, s.tenant, expected_revision=1, name="X", code="1", sort_order=1)
    await db.commit()
    digest = await _submit(db, s, nxt_id)
    current = await repo.current_baseline(s.project, s.tenant)
    assert current is not None
    with _rejected("must directly follow the current baseline"):
        db.add(WBSBaselineORM(id=uuid4(), tenant_id=s.tenant, project_id=s.project, baseline_no=3,
                              parent_baseline_id=current.id, source_change_set_id=nxt_id,
                              tree_digest="sha256:" + "0" * 64, change_set_digest=digest, node_count=0,
                              approved_by=s.admin.user_id, approved_by_kind="human"))
        await db.flush()
    await db.rollback()
    assert [b.baseline_no for b in await repo.list_baselines(s.project, s.tenant)] == [1]


async def test_n11_source_change_set_is_one_to_one(db: AsyncSession) -> None:
    s = await _scope(db)
    baseline_id, _ = await _baseline_one(db, s)
    baseline = await db.get(WBSBaselineORM, baseline_id)
    assert baseline is not None
    with _rejected("only a SUBMITTED change set can become a baseline"):
        db.add(WBSBaselineORM(id=uuid4(), tenant_id=s.tenant, project_id=s.project, baseline_no=2,
                              parent_baseline_id=baseline_id, source_change_set_id=baseline.source_change_set_id,
                              tree_digest=baseline.tree_digest, change_set_digest=baseline.change_set_digest,
                              node_count=0, approved_by=s.admin.user_id, approved_by_kind="human"))
        await db.commit()
    await db.rollback()
    # And no reverse link exists: the change set carries no applied-baseline column.
    assert "applied_baseline_id" not in WBSChangeSetORM.__table__.c


async def test_n13_every_draft_edit_advances_the_revision_and_stale_edits_conflict(db: AsyncSession) -> None:
    s = await _scope(db)
    repo = WBSGovernanceRepository(db)
    change_set = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="rev")
    change_set_id = change_set.id
    node = await repo.add_node(change_set_id, s.tenant, expected_revision=1, name="A", code="1", sort_order=1)
    assert await _revision(db, change_set_id) == 2
    await repo.update_node(change_set_id, node, s.tenant, expected_revision=2, name="A1")
    assert await _revision(db, change_set_id) == 3
    with pytest.raises(RevisionConflictError):  # someone else's revision 2 is stale now
        await repo.update_node(change_set_id, node, s.tenant, expected_revision=2, name="lost update")
    await db.rollback()
    await repo.remove_node(change_set_id, node, s.tenant, expected_revision=3)
    assert await _revision(db, change_set_id) == 4
    await _expect_db_rejection(db, "UPDATE wbs_change_sets SET revision = revision + 2 WHERE id = :c",
                               {"c": change_set_id}, "revision only moves forward by one")


async def test_n14_a_submitted_candidate_cannot_be_silently_edited(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, ids = await _draft_with_tree(db, s)
    await _submit(db, s, change_set_id)
    repo = WBSGovernanceRepository(db)
    with pytest.raises(GovernanceRuleError):
        await repo.add_node(change_set_id, s.tenant, expected_revision=await _revision(db, change_set_id),
                            name="sneaky", code="9", sort_order=9)
    await db.rollback()
    await _expect_db_rejection(db, "UPDATE wbs_change_set_nodes SET name = 'sneaky' WHERE change_set_id = :c",
                               {"c": change_set_id}, "editable only while the change set is DRAFT")
    await _expect_db_rejection(db, "UPDATE wbs_change_sets SET title = 'sneaky' WHERE id = :c", {"c": change_set_id}, "frozen: reopen it to edit")
    await _expect_db_rejection(db, "UPDATE wbs_change_sets SET evidence_refs = '[\"x\"]'::jsonb WHERE id = :c",
                               {"c": change_set_id}, "frozen: reopen it to edit")


async def test_n15_reopening_invalidates_the_submitted_digest(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, _ = await _draft_with_tree(db, s)
    first = await _submit(db, s, change_set_id)
    revision = await WBSGovernanceRepository(db).reopen(change_set_id, s.tenant, actor=s.author)
    await db.commit()
    change_set = await db.get(WBSChangeSetORM, change_set_id, populate_existing=True)
    assert change_set is not None
    assert (change_set.status, change_set.submitted_digest, change_set.revision) == ("DRAFT", None, revision)
    second = await _submit(db, s, change_set_id)
    assert second != first  # the same content re-signed at a new revision is a new digest


async def test_n15b_only_the_proposer_or_an_admin_can_reopen_or_withdraw(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, _ = await _draft_with_tree(db, s)
    digest = await _submit(db, s, change_set_id)
    colleague = await _user(db, s.tenant, UserRole.USER)
    ai = Actor(user_id=s.author.user_id, kind=ActorKind.AI, role="user")
    repo = WBSGovernanceRepository(db)
    for actor in (colleague, ai):
        with pytest.raises(GovernanceRuleError, match="only the proposer or a human admin can reopen"):
            await repo.reopen(change_set_id, s.tenant, actor=actor)
        await db.rollback()
        with pytest.raises(GovernanceRuleError, match="only the proposer or a human admin can withdraw"):
            await repo.withdraw(change_set_id, s.tenant, actor=actor)
        await db.rollback()
    change_set = await db.get(WBSChangeSetORM, change_set_id, populate_existing=True)
    assert change_set is not None
    assert (change_set.status, change_set.submitted_digest) == ("SUBMITTED", digest)  # signature intact
    # An admin may reopen someone else's submission; the proposer may withdraw their own.
    await repo.reopen(change_set_id, s.tenant, actor=s.admin)
    await repo.withdraw(change_set_id, s.tenant, actor=s.author)
    await db.commit()
    change_set = await db.get(WBSChangeSetORM, change_set_id, populate_existing=True)
    assert change_set is not None and change_set.status == "WITHDRAWN"


async def test_n16_stale_base_is_represented(db: AsyncSession) -> None:
    s = await _scope(db)
    _, ids = await _baseline_one(db, s)
    repo = WBSGovernanceRepository(db)
    winner = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="winner")
    winner_id = winner.id
    loser = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="loser")
    loser_id = loser.id
    for change_set in (winner, loser):
        await repo.add_node(change_set.id, s.tenant, expected_revision=1, name="Civil", code="1", sort_order=1,
                            keep_node_id=ids["1"])
    await db.commit()
    with pytest.raises(GovernanceRuleError):  # base still current: not stale
        await repo.mark_stale(loser_id, s.tenant)
    await db.rollback()
    await _submit(db, s, winner_id)
    await _submit(db, s, loser_id)
    await _apply(db, s, winner_id, s.admin)
    # The loser was proposed against Baseline #1, which is no longer current: it cannot be applied...
    with _rejected("must directly follow the current baseline"):
        await _apply(db, s, loser_id, s.admin)
    await db.rollback()
    # ...and is represented honestly as STALE (rebase = a new draft, PC-2a.2).
    await repo.mark_stale(loser_id, s.tenant)
    await db.commit()
    stale = await db.get(WBSChangeSetORM, loser_id, populate_existing=True)
    assert stale is not None and stale.status == "STALE" and stale.closed_at is not None
    authority = await repo.authority(s.project, s.tenant)
    assert authority.baseline_no == 2 and authority.open_change_sets == 0


async def test_n17_resolver_no_wbs(db: AsyncSession) -> None:
    s = await _scope(db)
    authority = await WBSGovernanceRepository(db).authority(s.project, s.tenant)
    assert (authority.state, authority.legacy_node_count, authority.open_change_sets) == (AuthorityState.NO_WBS, 0, 0)


async def test_n18_resolver_legacy_ungoverned_for_the_production_shape(db: AsyncSession) -> None:
    s = await _scope(db)
    await _legacy_nodes(db, s.tenant, s.project, 23)  # 23 flat, parentless, never approved
    authority = await WBSGovernanceRepository(db).authority(s.project, s.tenant)
    assert authority.state is AuthorityState.LEGACY_UNGOVERNED
    assert (authority.legacy_node_count, authority.approved, authority.baseline_id) == (23, False, None)
    # Nothing seeded a change set or a baseline from them.
    assert await db.scalar(select(func.count()).select_from(WBSBaselineORM).where(
        WBSBaselineORM.project_id == s.project)) == 0
    assert await db.scalar(select(func.count()).select_from(WBSChangeSetORM).where(
        WBSChangeSetORM.project_id == s.project)) == 0


async def test_n19_n20_draft_only_and_approved_only_from_a_baseline(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, _ = await _draft_with_tree(db, s)
    await _submit(db, s, change_set_id)
    repo = WBSGovernanceRepository(db)
    pending = await repo.authority(s.project, s.tenant)
    assert pending.display_state == "DRAFT_ONLY" and pending.approved is False and pending.baseline_no is None
    # A SUBMITTED change set cannot be marked APPLIED without its baseline.
    await _expect_db_rejection(
        db, "UPDATE wbs_change_sets SET status = 'APPLIED', decided_by = :a, decided_at = now(), "
            "decided_self_approval = false, closed_at = now() WHERE id = :c",
        {"a": s.admin.user_id, "c": change_set_id}, "APPLIED requires the baseline")
    assert (await repo.authority(s.project, s.tenant)).approved is False
    await _apply(db, s, change_set_id, s.admin)
    assert (await repo.authority(s.project, s.tenant)).state is AuthorityState.APPROVED_BASELINE


async def test_n21_candidate_nodes_are_never_live_wbs(db: AsyncSession) -> None:
    s = await _scope(db)
    legacy = await _legacy_nodes(db, s.tenant, s.project, 2)
    change_set_id, ids = await _draft_with_tree(db, s)
    await _submit(db, s, change_set_id)
    await _apply(db, s, change_set_id, s.admin)
    live = await db.execute(select(WBSNodeORM.id).where(WBSNodeORM.project_id == s.project))
    assert set(live.scalars().all()) == set(legacy)  # nothing materialized (PC-2a.2 does that)
    served = await SQLAlchemyWBSRepository(db).get_by_project(s.project, s.tenant)
    assert not {item.id for item in served} & set(ids.values())


async def test_n24_ai_service_and_api_users_never_hold_approval_authority(db: AsyncSession) -> None:
    s = await _scope(db)
    api_user = await _user(db, s.tenant, UserRole.API)
    repo = WBSGovernanceRepository(db)
    ai = Actor(user_id=uuid4(), kind=ActorKind.AI, role=None)
    # AI may draft an origin=ai proposal, never a manual one, and never submit it.
    proposal = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=ai,
                                            title="AI proposal", origin=ChangeSetOrigin.AI)
    proposal_id = proposal.id
    await repo.add_node(proposal_id, s.tenant, expected_revision=1, name="Civil", code="1", sort_order=1)
    await db.commit()
    with pytest.raises(GovernanceRuleError):
        await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=ai, title="sneaky manual")
    with pytest.raises(GovernanceRuleError):
        await repo.submit(proposal_id, s.tenant, expected_revision=2, actor=ai)
    await db.rollback()
    # The database refuses an api-role submitter and non-admin deciders.
    await _expect_db_rejection(
        db, "UPDATE wbs_change_sets SET status = 'SUBMITTED', submitted_revision = revision, submitted_digest = :d, "
            "submitted_by = :u, submitted_at = now() WHERE id = :c",
        {"d": "sha256:" + "1" * 64, "u": api_user.user_id, "c": proposal_id}, "submit requires an active human")
    await _submit(db, s, proposal_id)  # a human reviews and submits the AI proposal
    for decider in (api_user, s.author):
        with _rejected("approval requires an active human admin"):
            await _apply(db, s, proposal_id, decider)
        await db.rollback()
    change_set = await db.get(WBSChangeSetORM, proposal_id, populate_existing=True)
    assert change_set is not None
    with _rejected("ck_wbs_baselines_human_approver"):  # approved_by_kind can only be 'human'
        db.add(WBSBaselineORM(id=uuid4(), tenant_id=s.tenant, project_id=s.project, baseline_no=1,
                              source_change_set_id=proposal_id, tree_digest="sha256:" + "0" * 64,
                              change_set_digest=change_set.submitted_digest, node_count=0,
                              approved_by=s.admin.user_id, approved_by_kind="ai"))
        await db.flush()
    await db.rollback()
    await _apply(db, s, proposal_id, s.admin)  # only a human admin can make it authoritative


async def test_separation_of_duties_is_fail_closed_by_default(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, _ = await _draft_with_tree(db, s)
    await _submit(db, s, change_set_id, actor=s.admin)
    with _rejected("must differ from the submitter"):
        await _apply(db, s, change_set_id, s.admin, self_approved=True)
    await db.rollback()
    with _rejected("self_approved must record"):  # nor can self-approval be hidden as "not self"
        await _apply(db, s, change_set_id, s.admin, self_approved=False)
    await db.rollback()
    await _apply(db, s, change_set_id, s.admin2)


async def test_self_approval_only_when_the_tenant_opts_out_and_it_is_recorded(db: AsyncSession) -> None:
    s = await _scope(db, settings={"wbs_governance": {"require_distinct_approver": False}})
    change_set_id, _ = await _draft_with_tree(db, s)
    await _submit(db, s, change_set_id, actor=s.admin)
    baseline_id = await _apply(db, s, change_set_id, s.admin, self_approved=True)
    baseline = await db.get(WBSBaselineORM, baseline_id)
    change_set = await db.get(WBSChangeSetORM, change_set_id, populate_existing=True)
    assert baseline is not None and baseline.self_approved is True
    assert change_set is not None and change_set.decided_self_approval is True


async def test_project_deletion_still_cascades_governance_history(db: AsyncSession) -> None:
    s = await _scope(db)
    await _baseline_one(db, s)
    await _draft_with_tree(db, s, title="open draft")
    await db.execute(text("DELETE FROM projects WHERE id = :p"), {"p": s.project})
    await db.commit()
    for model in (WBSChangeSetORM, WBSChangeSetNodeORM, WBSChangeSetLineageORM, WBSBaselineORM, WBSBaselineNodeORM):
        assert await db.scalar(select(func.count()).select_from(model).where(model.project_id == s.project)) == 0


async def test_candidate_cycles_cannot_commit(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, ids = await _draft_with_tree(db, s)
    await _expect_db_rejection(
        db, "UPDATE wbs_change_set_nodes SET parent_id = :child WHERE change_set_id = :c AND node_id = :root",
        {"child": ids["1.1"], "c": change_set_id, "root": ids["1"]}, "WBS parent cycle")


async def test_governed_vocabularies_are_enforced_by_the_database(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, ids = await _draft_with_tree(db, s)
    for column, value in (("control_level", "cost_account"), ("decomposition_kind", "core:unknown"),
                          ("decomposition_kind", "Discipline"), ("dictionary", '{"scope_statement": "no version"}')):
        cast = "jsonb" if column == "dictionary" else "text"
        await _expect_db_rejection(
            db, f"UPDATE wbs_change_set_nodes SET {column} = CAST(:v AS {cast}) WHERE change_set_id = :c AND node_id = :n",
            {"v": value, "c": change_set_id, "n": ids["1"]}, "ck_wbs_change_set_nodes_")
    legacy = await _legacy_nodes(db, s.tenant, s.project, 1)
    await _expect_live_rejection(db, s, "UPDATE wbs_nodes SET control_level = 'cost_account' WHERE id = :n",
                                 {"n": legacy[0]}, "ck_wbs_nodes_control_level")
    live = await db.get(WBSNodeORM, legacy[0])
    assert live is not None and (live.control_level, live.decomposition_kind, live.dictionary) == ("none", None, None)


# Direct writes cannot smuggle relational links or mistyped fields into wbs-dictionary/v1.
_BAD_DICTIONARIES = (
    '{"schema_version": "wbs-dictionary/v1", "risk_ids": ["r-1"]}',
    '{"schema_version": "wbs-dictionary/v1", "deliverables": "Platform"}',
    '{"schema_version": "wbs-dictionary/v1", "deliverables": false}',
    '{"schema_version": "wbs-dictionary/v1", "assumptions": ["ok", 1]}',
    '{"schema_version": "wbs-dictionary/v1", "interface_notes": ["ok", ["nested"]]}',
    '{"schema_version": "wbs-dictionary/v1", "scope_statement": 42}',
)


async def test_the_database_enforces_the_complete_dictionary_schema(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id, ids = await _draft_with_tree(db, s)
    legacy = await _legacy_nodes(db, s.tenant, s.project, 1)
    for value in _BAD_DICTIONARIES:
        await _expect_db_rejection(
            db, "UPDATE wbs_change_set_nodes SET dictionary = CAST(:v AS jsonb) WHERE change_set_id = :c AND node_id = :n",
            {"v": value, "c": change_set_id, "n": ids["1"]}, "ck_wbs_change_set_nodes_dictionary")
        await _expect_live_rejection(db, s, "UPDATE wbs_nodes SET dictionary = CAST(:v AS jsonb) WHERE id = :n",
                                     {"v": value, "n": legacy[0]}, "ck_wbs_nodes_dictionary")
    full = ('{"schema_version": "wbs-dictionary/v1", "scope_statement": null, "deliverables": ["Platform"], '
            '"assumptions": [], "interface_notes": null}')
    async with governed_apply_state(db, s.tenant, s.project):
        await db.execute(text("UPDATE wbs_nodes SET dictionary = CAST(:v AS jsonb) WHERE id = :n"),
                         {"v": full, "n": legacy[0]})
    await db.commit()


async def test_a_profile_pin_without_its_digest_is_refused_at_drafting(db: AsyncSession) -> None:
    s = await _scope(db)
    repo = WBSGovernanceRepository(db)
    with pytest.raises(ValueError, match="profile_digest"):
        await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author, title="unpinned",
                                     profile_refs=({"profile_id": "solar-pv-epc", "profile_version": "1.0.0"},))
    await db.rollback()
    pin = {"profile_id": "solar-pv-epc", "profile_version": "1.0.0", "profile_digest": "sha256:" + "0" * 64}
    change_set = await repo.create_change_set(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                              title="pinned", profile_refs=(pin,))
    assert change_set.profile_refs == [pin]
