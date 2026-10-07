"""PC-2b.2 (#921) -- WBS intelligence store + human decision loop on a real PostgreSQL.

TS-INT-PC2B2-WBS-INTELLIGENCE-001. Numbered tests follow the #921 acceptance matrix (1-46):
A authority, B immutability, C human modification, D freshness, E dependency / atomicity,
F idempotency, G qualification (with tests/unit/wbs/intelligence/test_pc2b2_deterministic_qualifier.py),
H tenancy (RLS itself is proven under a NOBYPASSRLS role on a migrated database in
tests/integration/product_control/test_pc2b2_wbs_intelligence_store_migration_db.py) and I audit.

Proposal items come from the PC-2b.1 validator fed a fixed model response (a test cassette): no
model is called anywhere. The schema is the ORM-built test schema with the same guard triggers as
the migration.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.auth.models import UserRole
from src.temporal.adapters.persistence.models import ProjectEventORM
from src.wbs.adapters.persistence.governance_models import (
    WBSBaselineORM,
    WBSChangeSetNodeORM,
    WBSChangeSetORM,
)
from src.wbs.adapters.persistence.governance_repository import Actor, WBSGovernanceRepository
from src.wbs.adapters.persistence.intelligence_models import (
    WBSIntelligenceDecisionORM,
    WBSIntelligenceItemORM,
    WBSIntelligenceRunORM,
)
from src.wbs.application.governed_change_service import (
    AddNode,
    NodeSpec,
    UpdateNode,
    WBSGovernedChangeService,
)
from src.wbs.domain.governance import ActorKind
from src.wbs.intelligence.application.commands import command_json, to_command
from src.wbs.intelligence.application.service import (
    EVENT_ITEM_DECIDED,
    EVENT_RUN_COMPLETED,
    Decision,
    DecisionInput,
    HumanEdit,
    ItemApplicability,
    RunFreshness,
    WBSIntelligenceForbiddenError,
    WBSIntelligenceInvalidError,
    WBSIntelligenceNotFoundError,
    WBSIntelligenceSelectionRefusedError,
    WBSIntelligenceService,
    WBSIntelligenceStateError,
    _candidate_snapshot,
)
from src.wbs.intelligence.contracts.evidence import EvidenceManifest
from src.wbs.intelligence.contracts.proposal import ProposalItem, ProposalOperation
from src.wbs.intelligence.contracts.qualification import (
    SCHEDULE_EVIDENCE_UNAVAILABLE,
    AvailabilityContext,
    QualificationDimension,
)
from src.wbs.intelligence.contracts.run import (
    ExecutionType,
    IntelligenceMode,
    ModelFingerprint,
    RunScope,
    RunStatus,
    RunTarget,
    TargetKind,
    idempotency_key,
)
from src.wbs.intelligence.profiles.catalog import default_catalog
from src.wbs.intelligence.validation.output_validator import (
    ValidationContext,
    validate_model_output,
)
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import (
    Scope,
    _rejected,
    _scope,
    _user,
)
from tests.modules.integration.test_pc2a2_wbs_governed_apply import (
    _approve,
    _cmd,
    _cs,
    _events,
    _new,
    _rev,
    _submit,
    _tree,
)

pytestmark = pytest.mark.asyncio

CASSETTE_MODEL = ModelFingerprint(provider="test-fixture", model="pc2b2-cassette", temperature_milli=0, max_tokens=1)


# =========================================================================== helpers
def _svc(db: AsyncSession) -> WBSIntelligenceService:
    return WBSIntelligenceService(db)


def _add(ref: str, label: str, name: str, *, parent: dict[str, str], code: str) -> dict[str, Any]:
    return {"ref": ref, "operation": "ADD_NODE", "creates_label": label, "spec": {"name": name, "code": code},
            "parent": parent, "rationale": "the contract names it", "confidence_pct": 70}


def _rename(ref: str, node_id: UUID, name: str) -> dict[str, Any]:
    return {"ref": ref, "operation": "UPDATE_NODE", "node": {"node_id": str(node_id)}, "changes": {"name": name},
            "rationale": "clearer scope", "confidence_pct": 60}


async def _ai_run(db: AsyncSession, s: Scope, change_set_id: UUID, proposals: list[dict[str, Any]],
                  findings: list[dict[str, Any]] | None = None) -> WBSIntelligenceRunORM:
    """An AI-execution run persisted from a FIXED validated response (no model call)."""
    svc = _svc(db)
    change_set = await _cs(db, change_set_id)
    snapshot = _candidate_snapshot(s.project, await svc._candidate_nodes(change_set))
    profiles = default_catalog().resolve(list(change_set.profile_refs or []))
    scope = RunScope(tenant_id=s.tenant, project_id=s.project)
    manifest = EvidenceManifest(tenant_id=s.tenant, project_id=s.project, items=())
    ctx = ValidationContext(scope=scope, target=snapshot, manifest=manifest, profiles=profiles,
                            availability=AvailabilityContext(has_trusted_contract=False, has_trusted_scope_evidence=False,
                                                             ai_qualification_run=True))
    raw = "```json\n" + json.dumps({"contract_version": "wbs-proposal/v1", "outcome": "COMPLETE", "qualification": [],
                                    "findings": findings or [], "proposals": proposals, "uncovered": []}) + "\n```"
    output = validate_model_output(raw, ctx)
    assert not output.report.rejected and not output.report.envelope_error, output.report
    target = RunTarget(kind=TargetKind.CANDIDATE, target_id=change_set.id, digest=snapshot.digest,
                       change_set_revision=change_set.revision, base_baseline_id=change_set.base_baseline_id)
    key = idempotency_key(scope=scope, mode=IntelligenceMode.REVIEW_OPTIMIZE, target=target,
                          evidence_set_digest=manifest.evidence_set_digest, profile_digests=[], model=CASSETTE_MODEL,
                          orchestration_version="wbs-test-cassette/v1", rerun_nonce=uuid4().hex)
    opened = await svc.open_run(scope=scope, mode=IntelligenceMode.REVIEW_OPTIMIZE, execution_type=ExecutionType.AI,
                                target=target, evidence_set_digest=manifest.evidence_set_digest,
                                profile_refs=profiles.pins(), orchestration_version="wbs-test-cassette/v1", key=key,
                                requested_by=s.author.user_id, model_provenance=CASSETTE_MODEL.model_dump())
    run = await svc.record_validated_output(opened.run, output, actor=f"user:{s.author.user_id}")
    await db.commit()
    return run


class Item:
    """Plain values of a stored item (ORM objects expire on rollback)."""

    def __init__(self, row: WBSIntelligenceItemORM) -> None:
        self.id, self.body, self.body_digest = row.id, dict(row.body), row.body_digest


class World:
    def __init__(self, s: Scope, change_set_id: UUID, ids: dict[str, UUID], run_id: UUID, items: dict[str, Item]) -> None:
        self.s, self.change_set_id, self.ids, self.run_id, self.items = s, change_set_id, ids, run_id, items

    def item(self, ref: str) -> UUID:
        return self.items[ref].id


async def _items(db: AsyncSession, run: WBSIntelligenceRunORM) -> dict[str, Item]:
    return {view.item.ref: Item(view.item) for view in await _svc(db).items(run)}


async def _world(db: AsyncSession, *, evidence_refs: list[str] | None = None) -> World:
    """DRAFT: Civil(1) > Earthworks(1.1), Foundations(1.2); Electrical(2). Run: p-mv, p-cables (needs mv),
    p-found (rename Foundations) and one finding f-gran."""
    s = await _scope(db)
    change_set = await WBSGovernedChangeService(db).create_change_set(
        project_id=s.project, tenant_id=s.tenant, actor=s.author, title="WBS", evidence_refs=evidence_refs or [])
    change_set_id = change_set.id
    await db.commit()
    ids = await _tree(db, s, change_set_id)
    run = await _ai_run(db, s, change_set_id, [
        _add("p-mv", "mv", "MV system", parent={"node_id": str(ids["2"])}, code="2.1"),
        _add("p-cables", "cables", "MV cables", parent={"label": "mv"}, code="2.1.1"),
        _rename("p-found", ids["1.2"], "Foundations and piling"),
    ], findings=[{"ref": "f-gran", "dimension": "GRANULARITY", "status": "WARNING", "summary": "Electrical is thin",
                  "node_ids": [str(ids["2"])]}])
    return World(s, change_set_id, ids, run.id, await _items(db, run))


async def _decide(db: AsyncSession, w: World, *decisions: DecisionInput, actor: Actor | None = None,
                  change_set_id: UUID | None = None, apply: bool = True) -> Any:
    target = change_set_id or (w.change_set_id if apply else None)
    result = await _svc(db).decide(
        project_id=w.s.project, run_id=w.run_id, tenant_id=w.s.tenant, actor=actor or w.s.author,
        decisions=list(decisions), change_set_id=target,
        expected_revision=await _rev(db, target) if target else None)
    await db.commit()
    return result


async def _fails(db: AsyncSession, awaitable: Awaitable[Any], error: type[BaseException]) -> BaseException:
    with pytest.raises(error) as caught:
        await awaitable
    await db.rollback()
    return caught.value


def _apply(item_id: UUID, decision: Decision = Decision.APPLY_AS_PROPOSED, **kw: Any) -> DecisionInput:
    return DecisionInput(item_id=item_id, decision=decision, **kw)


async def _count(db: AsyncSession, model: Any, **where: Any) -> int:
    query = select(func.count()).select_from(model)
    for name, value in where.items():
        query = query.where(getattr(model, name) == value)
    return int(await db.scalar(query))


async def _nodes_by_name(db: AsyncSession, change_set_id: UUID) -> dict[str, WBSChangeSetNodeORM]:
    rows = await db.execute(select(WBSChangeSetNodeORM).where(WBSChangeSetNodeORM.change_set_id == change_set_id)
                            .execution_options(populate_existing=True))
    return {row.name: row for row in rows.scalars()}


async def _decision(db: AsyncSession, item_id: UUID) -> WBSIntelligenceDecisionORM | None:
    return await db.scalar(select(WBSIntelligenceDecisionORM).where(WBSIntelligenceDecisionORM.item_id == item_id)
                           .execution_options(populate_existing=True))


async def _deterministic(db: AsyncSession, s: Scope, change_set_id: UUID, *, rerun: bool = False) -> Any:
    result = await _svc(db).request_deterministic_run(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                      target_kind=TargetKind.CANDIDATE, change_set_id=change_set_id,
                                                      rerun=rerun)
    await db.commit()
    return result


# =========================================================================== A. authority
async def test_01_02_ai_service_and_api_principals_never_decide(db: AsyncSession) -> None:
    w = await _world(db)
    api_user = await _user(db, w.s.tenant, UserRole.API)
    for actor in (Actor(user_id=uuid4(), kind=ActorKind.AI, role=None),
                  Actor(user_id=uuid4(), kind=ActorKind.SERVICE, role="admin"), api_user):
        await _fails(db, _decide(db, w, _apply(w.item("p-mv")), actor=actor), WBSIntelligenceForbiddenError)
        await _fails(db, _svc(db).request_deterministic_run(
            project_id=w.s.project, tenant_id=w.s.tenant, actor=actor, target_kind=TargetKind.CANDIDATE,
            change_set_id=w.change_set_id), WBSIntelligenceForbiddenError)
    assert await _count(db, WBSIntelligenceDecisionORM, run_id=w.run_id) == 0
    # the database refuses them too: a decision is an active human admin/user choice
    for decided_by, kind, fragment in ((api_user.user_id, "human", "requires an active human"),
                                       (w.s.author.user_id, "ai", "ck_wbs_intelligence_decisions_human")):
        with _rejected(fragment):
            await db.execute(text(
                "INSERT INTO wbs_intelligence_decisions (id, tenant_id, project_id, run_id, item_id, item_kind, decision, "
                "batch_id, decided_by, decided_by_kind) VALUES (:id, :t, :p, :r, :i, 'FINDING', 'ACKNOWLEDGE', :b, :u, :k)"),
                {"id": uuid4(), "t": w.s.tenant, "p": w.s.project, "r": w.run_id, "i": w.item("f-gran"), "b": uuid4(),
                 "u": decided_by, "k": kind})
            await db.commit()
        await db.rollback()


async def test_03_a_human_applies_into_an_existing_authorized_draft_with_provenance(db: AsyncSession) -> None:
    w = await _world(db)
    before = await _rev(db, w.change_set_id)
    result = await _decide(db, w, _apply(w.item("p-mv")))
    assert result.change_set_revision == before + 1
    node = (await _nodes_by_name(db, w.change_set_id))["MV system"]
    assert node.origin_kind == "minted" and node.parent_id == w.ids["2"]
    [entry] = node.provenance["intelligence"]
    decision = await _decision(db, w.item("p-mv"))
    assert decision is not None
    assert entry == {"intelligence_run_id": str(w.run_id), "intelligence_item_id": str(w.item("p-mv")),
                     "decision_id": str(decision.id), "application_mode": "APPLY_AS_PROPOSED"}
    assert decision.decided_by == w.s.author.user_id and decision.decided_by_kind == "human"


async def test_04_a_decision_never_approves_a_baseline(db: AsyncSession) -> None:
    w = await _world(db)
    await _decide(db, w, _apply(w.item("p-mv")), _apply(w.item("p-found")))
    change_set = await _cs(db, w.change_set_id)
    assert change_set.status == "DRAFT" and change_set.submitted_digest is None
    assert await _count(db, WBSBaselineORM, project_id=w.s.project) == 0
    with pytest.raises(ValueError):
        Decision("APPROVE")
    with _rejected("ck_wbs_intelligence_decisions_vocabulary"):
        await db.execute(text(
            "INSERT INTO wbs_intelligence_decisions (id, tenant_id, project_id, run_id, item_id, item_kind, decision, "
            "batch_id, decided_by, decided_by_kind) VALUES (:id, :t, :p, :r, :i, 'PROPOSAL', 'APPROVE', :b, :u, 'human')"),
            {"id": uuid4(), "t": w.s.tenant, "p": w.s.project, "r": w.run_id, "i": w.item("p-cables"), "b": uuid4(),
             "u": w.s.admin.user_id})
        await db.commit()
    await db.rollback()
    # the governed path is unchanged: a human submits, a human admin approves
    await _submit(db, w.s, w.change_set_id)
    applied = await _approve(db, w.s, w.change_set_id)
    assert applied.baseline_no == 1


async def test_05_the_decision_api_never_creates_a_draft(db: AsyncSession) -> None:
    w = await _world(db)
    count = await _count(db, WBSChangeSetORM, project_id=w.s.project)
    await _fails(db, _svc(db).decide(project_id=w.s.project, run_id=w.run_id, tenant_id=w.s.tenant, actor=w.s.author,
                                     decisions=[_apply(w.item("p-mv"))]), WBSIntelligenceInvalidError)
    await _fails(db, _svc(db).decide(project_id=w.s.project, run_id=w.run_id, tenant_id=w.s.tenant, actor=w.s.author,
                                     decisions=[_apply(w.item("p-mv"))], change_set_id=uuid4(), expected_revision=1),
                 WBSIntelligenceNotFoundError)
    await _submit(db, w.s, w.change_set_id)  # no longer a DRAFT: the run goes STALE, nothing is created
    error = await _fails(db, _decide(db, w, _apply(w.item("p-mv"))), WBSIntelligenceStateError)
    assert getattr(error, "code", "") == "WBS_INTELLIGENCE_RUN_STALE"
    assert await _count(db, WBSChangeSetORM, project_id=w.s.project) == count
    assert await _count(db, WBSIntelligenceDecisionORM, run_id=w.run_id) == 0


# =========================================================================== B. immutability
async def test_06_07_proposal_and_finding_bodies_never_update(db: AsyncSession) -> None:
    w = await _world(db)
    for ref in ("p-mv", "f-gran"):
        with _rejected("WBS intelligence items are immutable"):
            await db.execute(text("UPDATE wbs_intelligence_items SET body = body || '{\"rationale\": \"x\"}'::jsonb "
                                  "WHERE id = :id"), {"id": w.item(ref)})
            await db.commit()
        await db.rollback()


async def test_08_a_decided_item_is_never_rewritten(db: AsyncSession) -> None:
    w = await _world(db)
    await _decide(db, w, _apply(w.item("p-mv")))
    error = await _fails(db, _decide(db, w, DecisionInput(w.item("p-mv"), Decision.REJECT), apply=False),
                         WBSIntelligenceStateError)
    assert getattr(error, "code", "") == "WBS_INTELLIGENCE_ITEM_ALREADY_DECIDED"
    for sql in ("UPDATE wbs_intelligence_decisions SET decision = 'REJECT' WHERE item_id = :id",
                "DELETE FROM wbs_intelligence_decisions WHERE item_id = :id"):
        with _rejected("WBS intelligence decisions are append-only"):
            await db.execute(text(sql), {"id": w.item("p-mv")})
            await db.commit()
        await db.rollback()
    decision = await _decision(db, w.item("p-mv"))
    assert decision is not None and decision.decision == "APPLY_AS_PROPOSED"


async def test_09_a_terminal_run_is_frozen(db: AsyncSession) -> None:
    w = await _world(db)
    for sql in ("UPDATE wbs_intelligence_runs SET outcome = 'PARTIAL_PROPOSAL' WHERE id = :id",
                "UPDATE wbs_intelligence_runs SET status = 'CANCELLED', outcome = 'CANCELLED' WHERE id = :id",
                "DELETE FROM wbs_intelligence_runs WHERE id = :id"):
        with _rejected("WBS intelligence run is COMPLETED and immutable", "audit history"):
            await db.execute(text(sql), {"id": w.run_id})
            await db.commit()
        await db.rollback()
    with _rejected("recorded only while their run is RUNNING"):
        await db.execute(text(
            "INSERT INTO wbs_intelligence_items (id, tenant_id, project_id, run_id, kind, ref, ordinal, contract_version, "
            "body, body_digest) VALUES (:id, :t, :p, :r, 'FINDING', 'late', 99, 'wbs-qualification/v1', "
            "jsonb_build_object('finding_id', CAST(:sid AS text), 'dimension', 'GRANULARITY', 'status', 'WARNING', 'method', "
            "'DETERMINISTIC', 'summary', 'late'), :d)"),
            {"id": (late := uuid4()), "sid": str(late), "t": w.s.tenant, "p": w.s.project, "r": w.run_id,
             "d": "sha256:" + "0" * 64})
        await db.commit()
    await db.rollback()
    await _fails(db, _svc(db).cancel_run(project_id=w.s.project, run_id=w.run_id, tenant_id=w.s.tenant,
                                         actor=w.s.author), WBSIntelligenceStateError)


async def test_10_a_rejected_item_stays_readable(db: AsyncSession) -> None:
    w = await _world(db)
    body, digest = dict(w.items["p-found"].body), w.items["p-found"].body_digest
    await _decide(db, w, DecisionInput(w.item("p-found"), Decision.REJECT, reason="not now"), apply=False)
    view = next(v for v in await _svc(db).items(await _svc(db).run(w.run_id, w.s.project, w.s.tenant))
                if v.item.id == w.item("p-found"))
    assert view.decision is not None and view.decision.decision == "REJECT" and view.decision.reason == "not now"
    assert view.item.body == body and view.item.body_digest == digest
    with _rejected("WBS intelligence items are immutable"):
        await db.execute(text("DELETE FROM wbs_intelligence_items WHERE id = :id"), {"id": w.item("p-found")})
        await db.commit()
    await db.rollback()


# =========================================================================== C. human modification
async def test_11_apply_as_proposed_uses_the_stored_payload_exactly(db: AsyncSession) -> None:
    w = await _world(db)
    stored = ProposalItem.model_validate(w.items["p-mv"].body)
    await _decide(db, w, _apply(w.item("p-mv")))
    decision = await _decision(db, w.item("p-mv"))
    assert decision is not None
    assert decision.applied_commands == [command_json(to_command(ProposalOperation.ADD_NODE, stored.payload, {}))]
    assert decision.applied_commands[0]["spec"]["name"] == stored.payload["spec"]["name"] == "MV system"
    assert decision.proposal_body_digest == w.items["p-mv"].body_digest
    assert (await _nodes_by_name(db, w.change_set_id))["MV system"].code == "2.1"


async def test_12_13_a_human_edit_is_recorded_separately_and_the_proposal_is_untouched(db: AsyncSession) -> None:
    w = await _world(db)
    body, digest = dict(w.items["p-mv"].body), w.items["p-mv"].body_digest
    edit = HumanEdit(creates_label="mv", spec={"name": "MV collection system", "code": "2.1"},
                     parent={"node_id": str(w.ids["2"])})
    await _decide(db, w, _apply(w.item("p-mv"), Decision.APPLY_WITH_HUMAN_EDIT, edit=edit), _apply(w.item("p-cables")))
    item = await db.scalar(select(WBSIntelligenceItemORM).where(WBSIntelligenceItemORM.id == w.item("p-mv"))
                           .execution_options(populate_existing=True))
    assert item is not None and item.body == body and item.body_digest == digest  # byte-for-byte the proposal
    decision = await _decision(db, w.item("p-mv"))
    assert decision is not None and decision.decision == "APPLY_WITH_HUMAN_EDIT"
    assert decision.proposal_body_digest == digest  # the original stays referenced
    assert decision.applied_commands[0]["spec"]["name"] == "MV collection system"  # what the HUMAN applied
    nodes = await _nodes_by_name(db, w.change_set_id)
    assert "MV system" not in nodes and nodes["MV cables"].parent_id == nodes["MV collection system"].node_id
    # an edit that drops a label its dependants rely on is refused
    w2 = await _world(db)
    bad = HumanEdit(creates_label="other", spec={"name": "X", "code": "2.1"}, parent={"node_id": str(w2.ids["2"])})
    await _fails(db, _decide(db, w2, _apply(w2.item("p-mv"), Decision.APPLY_WITH_HUMAN_EDIT, edit=bad)),
                 WBSIntelligenceInvalidError)


async def test_14_15_provenance_never_changes_the_digest_and_decisions_never_touch_evidence_refs(db: AsyncSession) -> None:
    w = await _world(db, evidence_refs=["doc:contract-1"])
    await _decide(db, w, _apply(w.item("p-mv")), DecisionInput(w.item("p-found"), Decision.REJECT, reason="no"))
    repo = WBSGovernanceRepository(db)
    revision = await _rev(db, w.change_set_id)
    detail = await repo.get_change_set(w.change_set_id, w.s.project, w.s.tenant)
    assert detail is not None
    with_provenance = repo.compute_change_set_digest(detail, revision)
    assert any("intelligence" in n.provenance for n in detail.nodes)
    for node in detail.nodes:  # strip every provenance entry: same content, same digest
        node.provenance = {}
    await db.flush()
    detail = await repo.get_change_set(w.change_set_id, w.s.project, w.s.tenant)
    assert detail is not None and repo.compute_change_set_digest(detail, revision) == with_provenance
    await db.rollback()
    change_set = await _cs(db, w.change_set_id)
    assert change_set.evidence_refs == ["doc:contract-1"]
    digest = await _submit(db, w.s, w.change_set_id)
    assert (await _cs(db, w.change_set_id)).evidence_refs == ["doc:contract-1"] and digest.startswith("sha256:")


# =========================================================================== D. freshness
async def test_16_a_moved_baseline_makes_a_baseline_run_stale(db: AsyncSession) -> None:
    s = await _scope(db)
    first = await _new(db, s, "Baseline 1")
    await _tree(db, s, first)
    await _submit(db, s, first)
    applied = await _approve(db, s, first)
    run = (await _svc(db).request_deterministic_run(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                    target_kind=TargetKind.BASELINE,
                                                    baseline_id=applied.baseline_id)).run
    await db.commit()
    assert (await _svc(db).freshness(run)).state is RunFreshness.FRESH
    second = await _new(db, s, "Baseline 2")
    civil = next(n for n in (await _nodes_by_name(db, second)).values() if n.code == "1")
    await _cmd(db, s, second, UpdateNode(civil.node_id, {"name": "Civil works"}))
    await _submit(db, s, second)
    await _approve(db, s, second)
    freshness = await _svc(db).freshness(await _svc(db).run(run.id, s.project, s.tenant))
    assert freshness.state is RunFreshness.STALE and "baseline moved" in freshness.reasons[0]


async def test_17_a_target_that_is_no_longer_a_draft_makes_the_run_stale(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    run = (await _deterministic(db, s, change_set_id)).run
    assert (await _svc(db).freshness(run)).state is RunFreshness.FRESH
    await _cmd(db, s, change_set_id, AddNode(NodeSpec("Mechanical", "3")))  # an ordinary DRAFT edit: still FRESH
    assert (await _svc(db).freshness(run)).state is RunFreshness.FRESH
    await _submit(db, s, change_set_id)
    freshness = await _svc(db).freshness(run)
    assert freshness.state is RunFreshness.STALE and "SUBMITTED" in freshness.reasons[0]


async def test_18_19_a_touched_item_conflicts_while_an_untouched_one_still_applies(db: AsyncSession) -> None:
    w = await _world(db)
    await _cmd(db, w.s, w.change_set_id, UpdateNode(w.ids["1.2"], {"name": "Foundations (human edit)"}))
    preview = await _svc(db).preview(project_id=w.s.project, run_id=w.run_id, tenant_id=w.s.tenant,
                                     change_set_id=w.change_set_id,
                                     selections=[_apply(w.item("p-found")), _apply(w.item("p-mv"))])
    status = {i.item_id: i.applicability for i in preview.items}
    assert status[w.item("p-found")] is ItemApplicability.CONFLICT
    assert status[w.item("p-mv")] is ItemApplicability.APPLICABLE
    assert preview.freshness.state is RunFreshness.FRESH and not preview.applicable  # the run itself is not stale
    refused = await _fails(db, _decide(db, w, _apply(w.item("p-found"))), WBSIntelligenceSelectionRefusedError)
    assert str(w.item("p-found")) in refused.details["conflicts"]  # type: ignore[attr-defined]
    await _decide(db, w, _apply(w.item("p-mv")))  # one conflict never invalidates unrelated items
    assert "MV system" in await _nodes_by_name(db, w.change_set_id)


async def test_20_a_stale_run_cannot_apply(db: AsyncSession) -> None:
    w = await _world(db)
    await WBSGovernedChangeService(db).withdraw(project_id=w.s.project, change_set_id=w.change_set_id,
                                                tenant_id=w.s.tenant, actor=w.s.author)
    await db.commit()
    error = await _fails(db, _svc(db).decide(project_id=w.s.project, run_id=w.run_id, tenant_id=w.s.tenant,
                                             actor=w.s.author, decisions=[_apply(w.item("p-mv"))],
                                             change_set_id=w.change_set_id, expected_revision=99),
                         WBSIntelligenceStateError)
    assert getattr(error, "code", "") == "WBS_INTELLIGENCE_RUN_STALE"
    # rejecting a stale suggestion stays possible (it changes nothing)
    await _decide(db, w, DecisionInput(w.item("p-mv"), Decision.REJECT), apply=False)


# =========================================================================== E. dependency / atomicity
async def test_21_a_missing_selected_prerequisite_refuses_the_batch(db: AsyncSession) -> None:
    w = await _world(db)
    refused = await _fails(db, _decide(db, w, _apply(w.item("p-cables"))), WBSIntelligenceSelectionRefusedError)
    assert refused.details["required_missing"] == [str(w.item("p-mv"))]  # type: ignore[attr-defined]
    assert await _count(db, WBSIntelligenceDecisionORM, run_id=w.run_id) == 0


async def test_22_a_rejected_prerequisite_blocks_its_dependant(db: AsyncSession) -> None:
    w = await _world(db)
    await _fails(db, _decide(db, w, DecisionInput(w.item("p-mv"), Decision.REJECT), _apply(w.item("p-cables"))),
                 WBSIntelligenceSelectionRefusedError)  # same batch
    await _decide(db, w, DecisionInput(w.item("p-mv"), Decision.REJECT), apply=False)
    refused = await _fails(db, _decide(db, w, _apply(w.item("p-cables"))), WBSIntelligenceSelectionRefusedError)
    assert refused.details["blocked_by_rejected"] == [str(w.item("p-mv"))]  # type: ignore[attr-defined]
    preview = await _svc(db).preview(project_id=w.s.project, run_id=w.run_id, tenant_id=w.s.tenant,
                                     change_set_id=w.change_set_id, selections=[_apply(w.item("p-cables"))])
    assert preview.items[0].applicability is ItemApplicability.BLOCKED_BY_REJECTED


async def test_23_45_one_invalid_item_rolls_back_the_whole_batch_and_emits_nothing(db: AsyncSession) -> None:
    w = await _world(db)
    revision = await _rev(db, w.change_set_id)
    nodes = await _nodes_by_name(db, w.change_set_id)
    # the governed commands run first; the batch then fails on the last decision row (reason too long)
    await _fails(db, _decide(db, w, _apply(w.item("p-mv")), _apply(w.item("p-found")),
                             DecisionInput(w.item("f-gran"), Decision.ACKNOWLEDGE, reason="x" * 5000)), DBAPIError)
    assert await _rev(db, w.change_set_id) == revision
    after = await _nodes_by_name(db, w.change_set_id)
    assert set(after) == set(nodes) and "Foundations and piling" not in after
    assert await _count(db, WBSIntelligenceDecisionORM, run_id=w.run_id) == 0
    assert not await _events(db, w.s.project, EVENT_ITEM_DECIDED)
    # a plan-time refusal (a conflict in the batch) applies nothing either
    await _cmd(db, w.s, w.change_set_id, UpdateNode(w.ids["1.2"], {"name": "Foundations (human)"}))
    revision = await _rev(db, w.change_set_id)
    await _fails(db, _decide(db, w, _apply(w.item("p-mv")), _apply(w.item("p-found"))),
                 WBSIntelligenceSelectionRefusedError)
    assert await _rev(db, w.change_set_id) == revision and "MV system" not in await _nodes_by_name(db, w.change_set_id)


async def test_24_an_applied_item_never_applies_twice(db: AsyncSession) -> None:
    w = await _world(db)
    await _decide(db, w, _apply(w.item("p-mv")))
    error = await _fails(db, _decide(db, w, _apply(w.item("p-mv"))), WBSIntelligenceStateError)
    assert getattr(error, "code", "") == "WBS_INTELLIGENCE_ITEM_ALREADY_DECIDED"
    assert [n for n in await _nodes_by_name(db, w.change_set_id) if n == "MV system"] == ["MV system"]
    # its dependant applies later on the id it minted (never re-applying it)
    await _decide(db, w, _apply(w.item("p-cables")))
    nodes = await _nodes_by_name(db, w.change_set_id)
    assert nodes["MV cables"].parent_id == nodes["MV system"].node_id


async def test_25_a_batch_advances_the_draft_revision_exactly_once_per_item_in_dependency_order(db: AsyncSession) -> None:
    w = await _world(db)
    start = await _rev(db, w.change_set_id)
    result = await _decide(db, w, _apply(w.item("p-cables")), _apply(w.item("p-found")), _apply(w.item("p-mv")))
    assert result.change_set_revision == start + 3 == await _rev(db, w.change_set_id)
    rows = {ref: await _decision(db, w.item(ref)) for ref in ("p-mv", "p-cables", "p-found")}
    spans = sorted((r.change_set_revision_before, r.change_set_revision_after) for r in rows.values() if r)
    assert spans == [(start, start + 1), (start + 1, start + 2), (start + 2, start + 3)]
    mv, cables = rows["p-mv"], rows["p-cables"]
    assert mv and cables and mv.change_set_revision_after <= cables.change_set_revision_before  # type: ignore[operator]
    nodes = await _nodes_by_name(db, w.change_set_id)
    assert mv.label_node_ids == {"mv": str(nodes["MV system"].node_id)}
    assert nodes["MV cables"].parent_id == nodes["MV system"].node_id
    assert {r.batch_id for r in rows.values() if r} == {result.batch_id}


# =========================================================================== F. idempotency
async def test_26_concurrent_identical_requests_create_one_run(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://"))
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def request(session: AsyncSession) -> Any:
        return await WBSIntelligenceService(session).request_deterministic_run(
            project_id=s.project, tenant_id=s.tenant, actor=s.author, target_kind=TargetKind.CANDIDATE,
            change_set_id=change_set_id)

    try:
        async with sessions() as first_session, sessions() as second_session:
            first = await request(first_session)  # holds the key, uncommitted
            racing = asyncio.create_task(request(second_session))
            await asyncio.sleep(0.5)
            assert not racing.done()  # serialized on the partial unique index
            await first_session.commit()
            second = await asyncio.wait_for(racing, timeout=20)
            await second_session.commit()
    finally:
        await engine.dispose()
    assert not first.reused and second.reused and second.run.id == first.run.id
    assert await _count(db, WBSIntelligenceRunORM, project_id=s.project) == 1


async def test_27_a_completed_run_is_reused(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    first = await _deterministic(db, s, change_set_id)
    again = await _deterministic(db, s, change_set_id)
    assert not first.reused and again.reused and again.run.id == first.run.id
    assert again.run.status == "COMPLETED"


async def _open(db: AsyncSession, s: Scope, key: str, status: RunStatus = RunStatus.RUNNING) -> Any:
    result = await _svc(db).open_run(
        scope=RunScope(tenant_id=s.tenant, project_id=s.project), mode=IntelligenceMode.REVIEW_OPTIMIZE,
        execution_type=ExecutionType.DETERMINISTIC, target=RunTarget(kind=TargetKind.NONE),
        evidence_set_digest="sha256:" + "e" * 64, profile_refs=[], orchestration_version="wbs-test/v1", key=key,
        requested_by=s.author.user_id, status=status)
    await db.commit()
    return result


async def test_28_29_failed_and_cancelled_runs_are_never_reused(db: AsyncSession) -> None:
    s = await _scope(db)
    key = "sha256:" + uuid4().hex * 2
    failed = await _open(db, s, key)
    await _svc(db).fail_run(failed.run, reason="engine crashed", actor="system:test")
    await db.commit()
    retry = await _open(db, s, key, RunStatus.REQUESTED)
    assert not retry.reused and retry.run.id != failed.run.id
    await _svc(db).cancel_run(project_id=s.project, run_id=retry.run.id, tenant_id=s.tenant, actor=s.author)
    await db.commit()
    third = await _open(db, s, key)
    assert not third.reused and third.run.id not in (failed.run.id, retry.run.id)
    assert (await _open(db, s, key)).reused  # the active one is reused


async def test_30_tenant_b_never_sees_or_reuses_tenant_a(db: AsyncSession) -> None:
    a, b = await _scope(db), await _scope(db)
    key = "sha256:" + uuid4().hex * 2
    run_a = (await _open(db, a, key)).run.id
    run_b = await _open(db, b, key)  # the very same key string
    assert not run_b.reused and run_b.run.id != run_a and run_b.run.tenant_id == b.tenant
    for project, tenant in ((a.project, b.tenant), (b.project, b.tenant)):
        await _fails(db, _svc(db).run(run_a, project, tenant), WBSIntelligenceNotFoundError)


# =========================================================================== G. qualification (persisted)
async def test_31_32_34_36_the_stored_report_is_one_coherent_result(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    run = (await _deterministic(db, s, change_set_id)).run
    assert run.execution_type == "DETERMINISTIC" and run.model_provenance is None  # never fabricated
    assert run.status == "COMPLETED" and run.outcome == "COMPLETE"
    results = run.qualification["results"]  # type: ignore[index]
    assert sorted(r["dimension"] for r in results) == sorted(QualificationDimension)
    by_dim = {r["dimension"]: r for r in results}
    assert by_dim["SCHEDULE_MAPPING_COVERAGE"]["summary"] == SCHEDULE_EVIDENCE_UNAVAILABLE
    for dim in ("SCOPE_COVERAGE", "MISSING_CONTRACT_SCOPE"):
        assert by_dim[dim]["reason_code"] == "AI_QUALIFICATION_NOT_RUN"
    items = [v.item for v in await _svc(db).items(run)]
    assert all(i.kind == "FINDING" for i in items)  # a deterministic run proposes nothing
    assert all(i.body["status"] in ("GAP", "WARNING", "AMBIGUOUS") for i in items)
    assert len(items) < len(results)  # the 19 results live on the run, not as fake findings


# =========================================================================== H. tenancy
async def test_40_cross_project_references_are_rejected(db: AsyncSession) -> None:
    w = await _world(db)
    other_project = (await _scope(db)).project
    other = await _scope(db)
    other_change_set = await _new(db, other)
    # the guard refuses it first (the run is not of that project); the composite FK backs it up
    with _rejected("fk_wbs_intelligence_items_run", "recorded only while their run is RUNNING"):
        await db.execute(text(
            "INSERT INTO wbs_intelligence_items (id, tenant_id, project_id, run_id, kind, ref, ordinal, contract_version, "
            "body, body_digest) VALUES (:id, :t, :p, :r, 'FINDING', 'x', 50, 'wbs-qualification/v1', '{}'::jsonb, :d)"),
            {"id": uuid4(), "t": w.s.tenant, "p": other_project, "r": w.run_id, "d": "sha256:" + "0" * 64})
        await db.commit()
    await db.rollback()
    with _rejected("fk_wbs_intelligence_runs_target_change_set"):
        await db.execute(text(
            "INSERT INTO wbs_intelligence_runs (id, tenant_id, project_id, mode, execution_type, target_kind, "
            "target_change_set_id, target_digest, target_change_set_revision, evidence_set_digest, "
            "proposal_contract_version, qualification_vocab_version, orchestration_version, idempotency_key, status, "
            "requested_by, requested_by_kind, started_at) VALUES (:id, :t, :p, 'REVIEW_OPTIMIZE', 'DETERMINISTIC', "
            "'CANDIDATE', :cs, :d, 1, :d, 'v', 'v', 'v', :d, 'RUNNING', :u, 'human', now())"),
            {"id": uuid4(), "t": w.s.tenant, "p": w.s.project, "cs": other_change_set, "d": "sha256:" + "1" * 64,
             "u": w.s.author.user_id})
        await db.commit()
    await db.rollback()
    await _fails(db, _svc(db).decide(project_id=w.s.project, run_id=w.run_id, tenant_id=w.s.tenant, actor=w.s.author,
                                     decisions=[_apply(w.item("p-mv"))], change_set_id=other_change_set,
                                     expected_revision=1), WBSIntelligenceNotFoundError)


async def test_42_privileged_service_queries_scope_tenant_and_project_explicitly(db: AsyncSession) -> None:
    """The test session bypasses RLS like a privileged application session: scoping must still hold."""
    w = await _world(db)
    stranger = await _scope(db)
    for project, tenant in ((stranger.project, w.s.tenant), (w.s.project, stranger.tenant),
                            (stranger.project, stranger.tenant)):
        await _fails(db, _svc(db).run(w.run_id, project, tenant), WBSIntelligenceNotFoundError)
        await _fails(db, _svc(db).preview(project_id=project, run_id=w.run_id, tenant_id=tenant,
                                          change_set_id=w.change_set_id, selections=[_apply(w.item("p-mv"))]),
                     WBSIntelligenceNotFoundError)
    await _fails(db, _svc(db).decide(project_id=stranger.project, run_id=w.run_id, tenant_id=stranger.tenant,
                                     actor=stranger.author, decisions=[_apply(w.item("p-mv"))],
                                     change_set_id=w.change_set_id, expected_revision=1),
                 WBSIntelligenceNotFoundError)
    assert await _count(db, WBSIntelligenceDecisionORM, run_id=w.run_id) == 0


# =========================================================================== I. audit
async def test_43_run_completed_is_emitted_once(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    run = (await _deterministic(db, s, change_set_id)).run
    await _deterministic(db, s, change_set_id)  # reused: no second event
    events = await _events(db, s.project, EVENT_RUN_COMPLETED)
    assert [e.payload["run_id"] for e in events] == [str(run.id)]
    payload = events[0].payload
    assert payload["status"] == "COMPLETED" and payload["outcome"] == "COMPLETE"
    assert payload["qualification_digest"] == run.qualification_digest
    assert "summary" not in json.dumps(payload)  # no model-visible or document text in the ledger


async def test_44_item_decided_once_per_successful_decision(db: AsyncSession) -> None:
    w = await _world(db)
    result = await _decide(db, w, _apply(w.item("p-mv")), DecisionInput(w.item("p-found"), Decision.REJECT),
                           DecisionInput(w.item("f-gran"), Decision.NO_CHANGE))
    events = await _events(db, w.s.project, EVENT_ITEM_DECIDED)
    assert sorted(e.payload["decision_id"] for e in events) == sorted(str(d.decision_id) for d in result.decisions)
    applied = next(e.payload for e in events if e.payload["decision"] == "APPLY_AS_PROPOSED")
    assert applied["change_set_id"] == str(w.change_set_id) and applied["change_set_revision_after"] is not None


async def test_46_a_rerun_is_a_new_run_and_never_touches_the_candidate_or_the_old_run(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _new(db, s)
    await _tree(db, s, change_set_id)
    first = (await _deterministic(db, s, change_set_id)).run
    old_items = [(v.item.id, v.item.body_digest) for v in await _svc(db).items(first)]
    revision = await _rev(db, change_set_id)
    second = await _deterministic(db, s, change_set_id, rerun=True)
    assert not second.reused and second.run.id != first.id
    assert await _rev(db, change_set_id) == revision  # the candidate is untouched
    reread = await _svc(db).run(first.id, s.project, s.tenant)
    assert reread.status == "COMPLETED" and reread.qualification_digest == first.qualification_digest
    assert [(v.item.id, v.item.body_digest) for v in await _svc(db).items(reread)] == old_items


async def test_preview_performs_zero_writes(db: AsyncSession) -> None:
    w = await _world(db)

    async def state() -> tuple[int, ...]:
        await db.commit()
        return (await _count(db, WBSIntelligenceRunORM, project_id=w.s.project),
                await _count(db, WBSIntelligenceItemORM, project_id=w.s.project),
                await _count(db, WBSIntelligenceDecisionORM, project_id=w.s.project),
                await _count(db, WBSChangeSetNodeORM, change_set_id=w.change_set_id),
                await _count(db, ProjectEventORM, project_id=w.s.project),
                await _rev(db, w.change_set_id))

    before = await state()
    preview = await _svc(db).preview(project_id=w.s.project, run_id=w.run_id, tenant_id=w.s.tenant,
                                     change_set_id=w.change_set_id,
                                     selections=[_apply(w.item("p-mv")), _apply(w.item("p-cables"))])
    assert not db.new and not db.dirty  # nothing staged either
    assert preview.applicable and [n.name for n in preview.resulting_nodes if n.key.startswith("label:")] == [
        "MV system", "MV cables"]
    assert await state() == before
