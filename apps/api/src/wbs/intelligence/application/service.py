"""WBS intelligence store, deterministic runs and the human decision loop (PC-2b.2 #921, ADR-030).

Intelligence is persisted; it is never authority. A decision records what a HUMAN chose to do with
one suggestion -- it never approves a baseline and never creates a change set:

* runs: a deterministic run qualifies the exact nodes of a DRAFT candidate or of the current
  baseline (no model, no model provenance). Status (REQUESTED / RUNNING / COMPLETED / FAILED /
  CANCELLED) and outcome (the PC-2b.1 vocabulary) are separate; a terminal run is frozen. The
  idempotency key reuses an active or completed run of the SAME tenant, never a FAILED or
  CANCELLED one, and concurrent identical requests serialize on the partial unique index;
* freshness is derived on read: a run is STALE when its baseline moved, or when its candidate is
  no longer a DRAFT on the current baseline. Ordinary edits to a still-valid DRAFT do not stale
  the run: each proposal is checked against its own fingerprints (CONFLICT), so one conflict never
  invalidates unrelated items;
* decisions: APPLY_AS_PROPOSED / APPLY_WITH_HUMAN_EDIT / REJECT for proposals, ACKNOWLEDGE /
  DISMISS / NO_CHANGE for findings, append-only, one per item. Applying requires an EXISTING DRAFT
  (never created here), an explicit selection (prerequisites are never auto-selected), a fresh run,
  unconflicted fingerprints and a clean simulation of the final command batch; the commands then
  run through ``WBSGovernedChangeService.execute`` as the human, under the expected revision, and
  the decisions and their ProjectEvents are written -- all in one transaction (a savepoint here):
  one invalid item and nothing is applied, decided or emitted;
* a stored proposal is never edited: a human edit is recorded on the decision (exact governed
  commands + digest) next to the untouched original proposal digest.

Every query is explicitly scoped to tenant AND project: RLS is a second wall, not the first.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Final
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import C2ProException
from src.core.json_types import JsonDict
from src.core.tenants.types import require_tenant_id
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.domain.project_event import ProjectEvent
from src.wbs.adapters.persistence.governance_models import (
    WBSBaselineNodeORM,
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
from src.wbs.application.governed_change_service import WBSGovernedChangeService
from src.wbs.domain.digest import canonical_json
from src.wbs.domain.governance import ActorKind, ChangeSetStatus, can_author
from src.wbs.intelligence.application.commands import (
    UnresolvedLabelError,
    command_json,
    digest_json,
    minted_labels,
    to_command,
)
from src.wbs.intelligence.contracts.evidence import EvidenceManifest
from src.wbs.intelligence.contracts.proposal import (
    PROPOSAL_CONTRACT_VERSION,
    ModelProposalItem,
    ProposalItem,
    ProposalOperation,
)
from src.wbs.intelligence.contracts.qualification import (
    QUALIFICATION_VOCAB_VERSION,
    NodeFinding,
    QualificationReport,
)
from src.wbs.intelligence.contracts.run import (
    ExecutionType,
    IntelligenceMode,
    RunOutcome,
    RunScope,
    RunStatus,
    RunTarget,
    TargetKind,
    idempotency_key,
)
from src.wbs.intelligence.profiles.catalog import (
    ProfileCompositionError,
    ResolvedProfileSet,
    default_catalog,
)
from src.wbs.intelligence.qualification.deterministic import (
    DETERMINISTIC_ENGINE_VERSION,
    QualifierNode,
    qualify,
)
from src.wbs.intelligence.validation.dependency import (
    SelectionPlan,
    SelectionRefusal,
    dependency_closure,
    plan_selection,
)
from src.wbs.intelligence.validation.output_validator import (
    ItemRejected,
    ValidatedOutput,
    check_proposal_shape,
    created_labels,
    item_guards,
    proposal_payload,
    used_labels,
)
from src.wbs.intelligence.validation.simulation import (
    SimulatedTree,
    SnapshotNode,
    TargetSnapshot,
)

EVENT_RUN_COMPLETED: Final = "wbs.intelligence.run_completed"
EVENT_ITEM_DECIDED: Final = "wbs.intelligence.item_decided"
_REUSABLE_STATUSES = (RunStatus.REQUESTED.value, RunStatus.RUNNING.value, RunStatus.COMPLETED.value)


class Decision(StrEnum):
    APPLY_AS_PROPOSED = "APPLY_AS_PROPOSED"
    APPLY_WITH_HUMAN_EDIT = "APPLY_WITH_HUMAN_EDIT"
    REJECT = "REJECT"
    ACKNOWLEDGE = "ACKNOWLEDGE"
    DISMISS = "DISMISS"
    NO_CHANGE = "NO_CHANGE"


APPLY_DECISIONS = frozenset({Decision.APPLY_AS_PROPOSED, Decision.APPLY_WITH_HUMAN_EDIT})
PROPOSAL_DECISIONS = APPLY_DECISIONS | {Decision.REJECT}
FINDING_DECISIONS = frozenset({Decision.ACKNOWLEDGE, Decision.DISMISS, Decision.NO_CHANGE})


class ItemKind(StrEnum):
    FINDING = "FINDING"
    PROPOSAL = "PROPOSAL"


class RunFreshness(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"


class ItemApplicability(StrEnum):
    APPLICABLE = "APPLICABLE"
    CONFLICT = "CONFLICT"
    MISSING_PREREQUISITE = "MISSING_PREREQUISITE"
    BLOCKED_BY_REJECTED = "BLOCKED_BY_REJECTED"
    DECIDED = "DECIDED"


# ============================================================================ errors (HTTP-shaped)
class WBSIntelligenceForbiddenError(C2ProException):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="WBS_INTELLIGENCE_FORBIDDEN", status_code=403)


class WBSIntelligenceNotFoundError(C2ProException):
    def __init__(self, what: str, identifier: UUID) -> None:
        super().__init__(message=f"{what} not found", code="WBS_INTELLIGENCE_NOT_FOUND", status_code=404,
                         details={"id": str(identifier)})


class WBSIntelligenceInvalidError(C2ProException):
    def __init__(self, message: str, reasons: Sequence[str] = ()) -> None:
        super().__init__(message=message, code="WBS_INTELLIGENCE_INVALID", status_code=422,
                         details={"reasons": list(reasons)})


class WBSIntelligenceStateError(C2ProException):
    def __init__(self, message: str, code: str = "WBS_INTELLIGENCE_INVALID_STATE", **details: Any) -> None:
        super().__init__(message=message, code=code, status_code=409, details=details)


class WBSIntelligenceSelectionRefusedError(C2ProException):
    def __init__(self, refusal: SelectionRefusal) -> None:
        super().__init__(
            message="The selection cannot be applied: nothing was applied or decided",
            code="WBS_INTELLIGENCE_SELECTION_REFUSED", status_code=409,
            details={"reasons": list(refusal.reasons),
                     "required_missing": sorted(map(str, refusal.required_missing)),
                     "blocked_by_rejected": sorted(map(str, refusal.blocked_by_rejected)),
                     "conflicts": sorted(map(str, refusal.conflicts))},
        )


# ============================================================================ inputs / views
class HumanEdit(BaseModel):
    """The human's replacement command fields for one proposal (same operation, same created labels)."""

    model_config = {"extra": "forbid", "frozen": True}

    node: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = []
    parent: dict[str, Any] | None = None
    position: int | None = None
    creates_label: str | None = None
    spec: dict[str, Any] | None = None
    changes: dict[str, Any] | None = None
    code: str | None = None
    split_targets: list[dict[str, Any]] = []
    child_targets: dict[str, int] = {}


@dataclass(frozen=True)
class DecisionInput:
    item_id: UUID
    decision: Decision
    reason: str | None = None
    edit: HumanEdit | None = None


@dataclass(frozen=True)
class FreshnessView:
    state: RunFreshness
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunRequestResult:
    run: WBSIntelligenceRunORM
    reused: bool


@dataclass(frozen=True)
class ItemView:
    item: WBSIntelligenceItemORM
    decision: WBSIntelligenceDecisionORM | None


@dataclass(frozen=True)
class PreviewItem:
    item_id: UUID
    applicability: ItemApplicability
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreviewNode:
    key: str
    parent: str | None
    sort_order: int
    code: str | None
    name: str
    decomposition_kind: str | None
    control_level: str


@dataclass(frozen=True)
class PreviewResult:
    freshness: FreshnessView
    items: tuple[PreviewItem, ...]
    applicable: bool
    reasons: tuple[str, ...]
    ordered_item_ids: tuple[UUID, ...] = ()
    resulting_nodes: tuple[PreviewNode, ...] = ()


@dataclass(frozen=True)
class DecidedItem:
    decision_id: UUID
    item_id: UUID
    decision: Decision
    change_set_revision_after: int | None
    label_node_ids: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DecideResult:
    batch_id: UUID
    decisions: tuple[DecidedItem, ...]
    change_set_id: UUID | None
    change_set_revision: int | None


# ============================================================================ helpers
def _now() -> datetime:
    return datetime.now(UTC)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def _candidate_snapshot(project_id: UUID, nodes: Sequence[WBSChangeSetNodeORM]) -> TargetSnapshot:
    return TargetSnapshot(project_id=project_id, nodes=tuple(
        SnapshotNode(node_id=n.node_id, parent_id=n.parent_id, sort_order=n.sort_order, code=n.code, name=n.name,
                     decomposition_kind=n.decomposition_kind, control_level=n.control_level, dictionary=n.dictionary,
                     minted=n.origin_kind == "minted")
        for n in nodes))


def _baseline_snapshot(project_id: UUID, nodes: Sequence[WBSBaselineNodeORM]) -> TargetSnapshot:
    return TargetSnapshot(project_id=project_id, nodes=tuple(
        SnapshotNode(node_id=n.node_id, parent_id=n.parent_id, sort_order=n.sort_order, code=n.code, name=n.name,
                     decomposition_kind=n.decomposition_kind, control_level=n.control_level, dictionary=n.dictionary)
        for n in nodes))


def _qualifier_nodes(snapshot: TargetSnapshot) -> list[QualifierNode]:
    return [QualifierNode(node_id=n.node_id, parent_id=n.parent_id, sort_order=n.sort_order, code=n.code, name=n.name,
                          decomposition_kind=n.decomposition_kind, control_level=n.control_level,
                          dictionary=n.dictionary) for n in snapshot.nodes]


def _resolve_profiles(pins: Sequence[Mapping[str, Any]]) -> ResolvedProfileSet:
    try:
        return default_catalog().resolve(list(pins))
    except ProfileCompositionError as exc:
        raise WBSIntelligenceInvalidError("the target's profile pins do not resolve", [str(exc)]) from exc


def _require_author(actor: Actor, action: str) -> None:
    if not can_author(actor.kind, actor.role):
        raise WBSIntelligenceForbiddenError(f"only a human user or admin can {action} (never AI, api or a service)")


def _target_id(run: WBSIntelligenceRunORM) -> UUID | None:
    return run.target_change_set_id or run.target_baseline_id or run.target_import_id


def _bind(payload: Any, labels: Mapping[str, UUID]) -> Any:
    """Replace references to labels already minted (by earlier applied items) with their node ids."""
    if isinstance(payload, dict):
        if set(payload) == {"label"} and payload["label"] in labels:
            return {"node_id": str(labels[payload["label"]])}
        bound = {key: _bind(value, labels) for key, value in payload.items()}
        if isinstance(bound.get("child_targets"), dict):
            bound["child_targets"] = {
                (str(labels[k.removeprefix("label:")]) if k.startswith("label:") and k.removeprefix("label:") in labels
                 else k): v for k, v in bound["child_targets"].items()}
        return bound
    if isinstance(payload, list):
        return [_bind(value, labels) for value in payload]
    return payload


def _model_item(item: ProposalItem, payload: Mapping[str, Any]) -> ModelProposalItem:
    return ModelProposalItem.model_validate({**payload, "ref": item.ref, "operation": item.operation,
                                             "rationale": item.rationale, "confidence_pct": item.confidence_pct})


class WBSIntelligenceService:
    """The intelligence store and decision loop over one transactional session (the caller commits)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WBSGovernanceRepository(session)

    # ------------------------------------------------------------------ scoping
    async def _require_project(self, project_id: UUID, tenant_id: UUID, *, lock: bool = False) -> None:
        query = select(ProjectORM.id).where(ProjectORM.id == project_id, ProjectORM.tenant_id == tenant_id)
        if lock:
            query = query.with_for_update()
        if await self.session.scalar(query) is None:
            raise WBSIntelligenceNotFoundError("Project", project_id)

    async def run(self, run_id: UUID, project_id: UUID, tenant_id: UUID, *, lock: bool = False) -> WBSIntelligenceRunORM:
        query = select(WBSIntelligenceRunORM).where(
            WBSIntelligenceRunORM.id == run_id, WBSIntelligenceRunORM.project_id == project_id,
            WBSIntelligenceRunORM.tenant_id == tenant_id,
        ).execution_options(populate_existing=True)
        if lock:
            query = query.with_for_update()
        run = await self.session.scalar(query)
        if run is None:
            raise WBSIntelligenceNotFoundError("WBS intelligence run", run_id)
        return run

    async def _change_set(self, change_set_id: UUID, project_id: UUID, tenant_id: UUID, *, lock: bool = False,
                          share: bool = False) -> WBSChangeSetORM:
        query = select(WBSChangeSetORM).where(
            WBSChangeSetORM.id == change_set_id, WBSChangeSetORM.project_id == project_id,
            WBSChangeSetORM.tenant_id == tenant_id,
        ).execution_options(populate_existing=True)
        if lock or share:
            query = query.with_for_update(read=share and not lock)
        change_set = await self.session.scalar(query)
        if change_set is None:
            raise WBSIntelligenceNotFoundError("WBS change set", change_set_id)
        return change_set

    async def _candidate_nodes(self, change_set: WBSChangeSetORM) -> list[WBSChangeSetNodeORM]:
        rows = await self.session.execute(
            select(WBSChangeSetNodeORM).where(
                WBSChangeSetNodeORM.change_set_id == change_set.id,
                WBSChangeSetNodeORM.tenant_id == change_set.tenant_id,
                WBSChangeSetNodeORM.project_id == change_set.project_id,
            ).execution_options(populate_existing=True)
        )
        return list(rows.scalars())

    async def _baseline_nodes(self, baseline: WBSBaselineORM) -> list[WBSBaselineNodeORM]:
        rows = await self.session.execute(
            select(WBSBaselineNodeORM).where(
                WBSBaselineNodeORM.baseline_id == baseline.id, WBSBaselineNodeORM.tenant_id == baseline.tenant_id,
                WBSBaselineNodeORM.project_id == baseline.project_id,
            )
        )
        return list(rows.scalars())

    async def _event(self, *, project_id: UUID, tenant_id: UUID, event_type: str, payload: JsonDict, actor: str) -> UUID:
        now = _now().replace(tzinfo=None)
        event = ProjectEvent(event_id=uuid4(), project_id=project_id, tenant_id=require_tenant_id(tenant_id),
                             event_type=event_type, payload=payload, actor=actor, occurred_at=now, created_at=now)
        await SqlAlchemyProjectEventRepository(self.session).append(event)
        return event.event_id

    # ------------------------------------------------------------------ run store (also the seam for later executors)
    async def open_run(
        self,
        *,
        scope: RunScope,
        mode: IntelligenceMode,
        execution_type: ExecutionType,
        target: RunTarget,
        evidence_set_digest: str,
        profile_refs: Sequence[Mapping[str, Any]],
        orchestration_version: str,
        key: str,
        requested_by: UUID,
        requested_by_kind: str = "human",
        rerun_nonce: str | None = None,
        model_provenance: Mapping[str, Any] | None = None,
        status: RunStatus = RunStatus.RUNNING,
    ) -> RunRequestResult:
        """Insert a run, or reuse the tenant's active / completed run with the same key (race-safe)."""
        if (execution_type is ExecutionType.AI) != (model_provenance is not None):
            raise WBSIntelligenceInvalidError("an AI run carries model provenance; a deterministic run never does")
        if status not in (RunStatus.REQUESTED, RunStatus.RUNNING):
            raise WBSIntelligenceInvalidError("a run starts REQUESTED or RUNNING")
        target_ids = {
            "target_change_set_id": target.target_id if target.kind is TargetKind.CANDIDATE else None,
            "target_baseline_id": target.target_id if target.kind is TargetKind.BASELINE else None,
            "target_import_id": target.target_id if target.kind is TargetKind.IMPORT else None,
        }
        run_id = uuid4()
        values = {
            "id": run_id, "tenant_id": scope.tenant_id, "project_id": scope.project_id, "mode": mode.value,
            "execution_type": execution_type.value, "target_kind": target.kind.value, **target_ids,
            "target_digest": target.digest, "target_change_set_revision": target.change_set_revision,
            "target_base_baseline_id": target.base_baseline_id, "evidence_set_digest": evidence_set_digest,
            "profile_refs": [dict(pin) for pin in profile_refs], "proposal_contract_version": PROPOSAL_CONTRACT_VERSION,
            "qualification_vocab_version": QUALIFICATION_VOCAB_VERSION,
            "orchestration_version": orchestration_version, "idempotency_key": key, "rerun_nonce": rerun_nonce,
            "model_provenance": None if model_provenance is None else dict(model_provenance),
            "status": status.value, "requested_by": requested_by, "requested_by_kind": requested_by_kind,
            "started_at": _now() if status is RunStatus.RUNNING else None,
        }
        inserted = await self.session.scalar(
            pg_insert(WBSIntelligenceRunORM).values(**values)
            .on_conflict_do_nothing(index_elements=["tenant_id", "idempotency_key"],
                                    index_where=WBSIntelligenceRunORM.status.in_(_REUSABLE_STATUSES))
            .returning(WBSIntelligenceRunORM.id)
        )
        if inserted is None:
            existing = await self.session.scalar(
                select(WBSIntelligenceRunORM).where(
                    WBSIntelligenceRunORM.tenant_id == scope.tenant_id,
                    WBSIntelligenceRunORM.project_id == scope.project_id,
                    WBSIntelligenceRunORM.idempotency_key == key,
                    WBSIntelligenceRunORM.status.in_(_REUSABLE_STATUSES),
                ).execution_options(populate_existing=True)
            )
            if existing is None:  # pragma: no cover - the conflicting run is of the same tenant and project
                raise WBSIntelligenceStateError("an equivalent run exists but is not visible")
            return RunRequestResult(run=existing, reused=True)
        return RunRequestResult(run=await self.run(run_id, scope.project_id, scope.tenant_id), reused=False)

    async def _record_items(self, run: WBSIntelligenceRunORM, findings: Sequence[NodeFinding],
                            proposals: Sequence[ProposalItem], finding_refs: Mapping[UUID, str]) -> None:
        if run.status != RunStatus.RUNNING.value:
            raise WBSIntelligenceStateError(f"items are recorded only while a run is RUNNING (it is {run.status})")
        ordinal = 0
        for finding in findings:
            ordinal += 1
            body = finding.model_dump(mode="json")
            self.session.add(WBSIntelligenceItemORM(
                id=finding.finding_id, tenant_id=run.tenant_id, project_id=run.project_id, run_id=run.id,
                kind=ItemKind.FINDING.value, ref=finding_refs.get(finding.finding_id, f"dq-{ordinal:03d}"),
                ordinal=ordinal, contract_version=QUALIFICATION_VOCAB_VERSION, operation=None, body=body,
                body_digest=_digest(body)))
        for proposal in proposals:
            ordinal += 1
            body = proposal.model_dump(mode="json")
            self.session.add(WBSIntelligenceItemORM(
                id=proposal.item_id, tenant_id=run.tenant_id, project_id=run.project_id, run_id=run.id,
                kind=ItemKind.PROPOSAL.value, ref=proposal.ref, ordinal=ordinal, contract_version=PROPOSAL_CONTRACT_VERSION,
                operation=proposal.operation.value, body=body, body_digest=_digest(body)))
        await self.session.flush()

    async def complete_run(self, run: WBSIntelligenceRunORM, *, outcome: RunOutcome, qualification: QualificationReport,
                           findings: Sequence[NodeFinding] = (), proposals: Sequence[ProposalItem] = (),
                           finding_refs: Mapping[UUID, str] | None = None, actor: str) -> WBSIntelligenceRunORM:
        """RUNNING -> COMPLETED with its items and its one qualification report; emits run_completed once."""
        if outcome not in (RunOutcome.COMPLETE, RunOutcome.PARTIAL_PROPOSAL, RunOutcome.INSUFFICIENT_EVIDENCE):
            raise WBSIntelligenceInvalidError(f"a completed run has a successful outcome, not {outcome.value}")
        await self._record_items(run, findings, proposals, finding_refs or {})
        report = qualification.model_dump(mode="json")
        run.status, run.outcome = RunStatus.COMPLETED.value, outcome.value
        run.qualification, run.qualification_digest = report, _digest(report)
        run.completed_at = _now()
        await self.session.flush()
        await self._run_event(run, actor=actor, finding_count=len(findings), proposal_count=len(proposals))
        return run

    async def record_validated_output(self, run: WBSIntelligenceRunORM, output: ValidatedOutput, *, actor: str
                                      ) -> WBSIntelligenceRunORM:
        """Persist a PC-2b.1 validated model response for an AI run (the executor's seam; no model call here)."""
        if run.execution_type != ExecutionType.AI.value:
            raise WBSIntelligenceInvalidError("only an AI run records a validated model output")
        if output.outcome is RunOutcome.FAILED:
            return await self.fail_run(run, reason=output.report.envelope_error or "the model output failed validation",
                                       actor=actor)
        return await self.complete_run(run, outcome=output.outcome, qualification=output.qualification,
                                       findings=output.findings, proposals=output.proposals,
                                       finding_refs=output.finding_refs, actor=actor)

    async def fail_run(self, run: WBSIntelligenceRunORM, *, reason: str, actor: str) -> WBSIntelligenceRunORM:
        if run.status not in (RunStatus.REQUESTED.value, RunStatus.RUNNING.value):
            raise WBSIntelligenceStateError(f"a {run.status} run cannot fail", status=run.status)
        run.status, run.outcome = RunStatus.FAILED.value, RunOutcome.FAILED.value
        run.failure_reason, run.completed_at = reason[:2000], _now()
        await self.session.flush()
        await self._run_event(run, actor=actor, finding_count=0, proposal_count=0)
        return run

    async def _run_event(self, run: WBSIntelligenceRunORM, *, actor: str, finding_count: int, proposal_count: int) -> None:
        target_id = _target_id(run)
        await self._event(
            project_id=run.project_id, tenant_id=run.tenant_id, event_type=EVENT_RUN_COMPLETED, actor=actor,
            payload={
                "tenant_id": str(run.tenant_id), "project_id": str(run.project_id), "run_id": str(run.id),
                "status": run.status, "outcome": run.outcome, "execution_type": run.execution_type,
                "mode": run.mode, "target_kind": run.target_kind, "target_id": None if target_id is None else str(target_id),
                "target_digest": run.target_digest, "target_change_set_revision": run.target_change_set_revision,
                "idempotency_key": run.idempotency_key, "evidence_set_digest": run.evidence_set_digest,
                "qualification_digest": run.qualification_digest, "finding_count": finding_count,
                "proposal_count": proposal_count,
            },
        )

    # ------------------------------------------------------------------ deterministic runs
    async def request_deterministic_run(
        self,
        *,
        project_id: UUID,
        tenant_id: UUID,
        actor: Actor,
        target_kind: TargetKind,
        change_set_id: UUID | None = None,
        baseline_id: UUID | None = None,
        rerun: bool = False,
    ) -> RunRequestResult:
        """Qualify a DRAFT candidate or the current baseline deterministically (no LLM), idempotently."""
        _require_author(actor, "request a WBS intelligence run")
        await self._require_project(project_id, tenant_id)
        scope = RunScope(tenant_id=tenant_id, project_id=project_id)
        if target_kind is TargetKind.CANDIDATE:
            if change_set_id is None or baseline_id is not None:
                raise WBSIntelligenceInvalidError("a candidate run names exactly its change set")
            # FOR SHARE until commit: an edit in flight finishes first, so the revision and the nodes
            # this run binds are one consistent state (an edit bumps the revision on this row).
            change_set = await self._change_set(change_set_id, project_id, tenant_id, share=True)
            if change_set.status != ChangeSetStatus.DRAFT.value:
                raise WBSIntelligenceStateError(f"only a DRAFT candidate is qualified (this one is {change_set.status})",
                                                code="WBS_INTELLIGENCE_TARGET_NOT_DRAFT", status=change_set.status)
            snapshot = _candidate_snapshot(project_id, await self._candidate_nodes(change_set))
            target = RunTarget(kind=TargetKind.CANDIDATE, target_id=change_set.id, digest=snapshot.digest,
                               change_set_revision=change_set.revision, base_baseline_id=change_set.base_baseline_id)
            pins, evidence_refs = list(change_set.profile_refs or []), list(change_set.evidence_refs or [])
        elif target_kind is TargetKind.BASELINE:
            if baseline_id is None or change_set_id is not None:
                raise WBSIntelligenceInvalidError("a baseline run names exactly its baseline")
            current = await self.repo.current_baseline(project_id, tenant_id)
            if current is None or current.id != baseline_id:
                raise WBSIntelligenceStateError("only the project's current baseline is qualified",
                                                code="WBS_INTELLIGENCE_TARGET_NOT_CURRENT")
            snapshot = _baseline_snapshot(project_id, await self._baseline_nodes(current))
            target = RunTarget(kind=TargetKind.BASELINE, target_id=current.id, digest=current.tree_digest,
                               base_baseline_id=current.parent_baseline_id)
            source = await self._change_set(current.source_change_set_id, project_id, tenant_id)
            pins, evidence_refs = list(current.profile_refs or []), list(source.evidence_refs or [])
        else:
            raise WBSIntelligenceInvalidError("deterministic qualification needs a DRAFT candidate or the current baseline")
        profiles = _resolve_profiles(pins)
        evidence_set_digest = EvidenceManifest(tenant_id=tenant_id, project_id=project_id, items=()).evidence_set_digest
        nonce = uuid4().hex if rerun else None
        key = idempotency_key(scope=scope, mode=IntelligenceMode.REVIEW_OPTIMIZE, target=target,
                              evidence_set_digest=evidence_set_digest,
                              profile_digests=[pin["profile_digest"] for pin in profiles.pins()], model=None,
                              orchestration_version=DETERMINISTIC_ENGINE_VERSION, rerun_nonce=nonce)
        opened = await self.open_run(
            scope=scope, mode=IntelligenceMode.REVIEW_OPTIMIZE, execution_type=ExecutionType.DETERMINISTIC,
            target=target, evidence_set_digest=evidence_set_digest, profile_refs=profiles.pins(),
            orchestration_version=DETERMINISTIC_ENGINE_VERSION, key=key, requested_by=actor.user_id, rerun_nonce=nonce)
        if opened.reused:
            return opened
        result = qualify(_qualifier_nodes(snapshot), profiles=profiles, evidence_ref_count=len(evidence_refs))
        run = await self.complete_run(opened.run, outcome=RunOutcome.COMPLETE, qualification=result.report,
                                      findings=result.findings, actor=f"user:{actor.user_id}")
        return RunRequestResult(run=run, reused=False)

    async def cancel_run(self, *, project_id: UUID, run_id: UUID, tenant_id: UUID, actor: Actor) -> WBSIntelligenceRunORM:
        _require_author(actor, "cancel a WBS intelligence run")
        run = await self.run(run_id, project_id, tenant_id, lock=True)
        if run.status not in (RunStatus.REQUESTED.value, RunStatus.RUNNING.value):
            raise WBSIntelligenceStateError(f"a {run.status} run cannot be cancelled", status=run.status)
        run.status, run.outcome, run.completed_at = RunStatus.CANCELLED.value, RunOutcome.CANCELLED.value, _now()
        await self.session.flush()
        await self._run_event(run, actor=f"user:{actor.user_id}", finding_count=0, proposal_count=0)
        return run

    # ------------------------------------------------------------------ reads
    async def freshness(self, run: WBSIntelligenceRunORM) -> FreshnessView:
        """Run-level STALE (derived, never stored); per-item CONFLICT is separate (fingerprints)."""
        current = await self.repo.current_baseline(run.project_id, run.tenant_id)
        current_id = current.id if current else None
        reasons: list[str] = []
        if run.target_kind == TargetKind.BASELINE.value and run.target_baseline_id != current_id:
            reasons.append("the project's current baseline moved since the run")
        elif run.target_kind == TargetKind.CANDIDATE.value and run.target_change_set_id is not None:
            change_set = await self._change_set(run.target_change_set_id, run.project_id, run.tenant_id)
            if change_set.status != ChangeSetStatus.DRAFT.value:
                reasons.append(f"the target change set is {change_set.status}, no longer a DRAFT")
            elif change_set.base_baseline_id != current_id:
                reasons.append("the target change set's base baseline is no longer current")
        elif run.target_kind == TargetKind.IMPORT.value:
            reasons.append("import runs are not applicable yet")
        return FreshnessView(state=RunFreshness.STALE if reasons else RunFreshness.FRESH, reasons=tuple(reasons))

    async def items(self, run: WBSIntelligenceRunORM) -> list[ItemView]:
        rows = (await self.session.execute(
            select(WBSIntelligenceItemORM).where(
                WBSIntelligenceItemORM.run_id == run.id, WBSIntelligenceItemORM.tenant_id == run.tenant_id,
                WBSIntelligenceItemORM.project_id == run.project_id,
            ).order_by(WBSIntelligenceItemORM.ordinal)
        )).scalars().all()
        decisions = {d.item_id: d for d in await self._decisions(run)}
        return [ItemView(item=row, decision=decisions.get(row.id)) for row in rows]

    async def _decisions(self, run: WBSIntelligenceRunORM) -> list[WBSIntelligenceDecisionORM]:
        rows = await self.session.execute(
            select(WBSIntelligenceDecisionORM).where(
                WBSIntelligenceDecisionORM.run_id == run.id, WBSIntelligenceDecisionORM.tenant_id == run.tenant_id,
                WBSIntelligenceDecisionORM.project_id == run.project_id,
            )
        )
        return list(rows.scalars())

    # ------------------------------------------------------------------ selection (shared by preview and apply)
    async def _plan(
        self,
        run: WBSIntelligenceRunORM,
        change_set: WBSChangeSetORM,
        inputs: Sequence[DecisionInput],
    ) -> tuple[SelectionPlan | SelectionRefusal, dict[UUID, ProposalItem], dict[UUID, str], dict[str, UUID],
               set[UUID], TargetSnapshot]:
        """Plan the apply decisions of ``inputs`` on the CURRENT candidate of ``change_set`` (no writes)."""
        views = await self.items(run)
        proposals = {v.item.id: ProposalItem.model_validate(v.item.body) for v in views
                     if v.item.kind == ItemKind.PROPOSAL.value}
        digests = {v.item.id: v.item.body_digest for v in views}
        applied = {v.item.id for v in views if v.decision and v.decision.decision in APPLY_DECISIONS}
        rejected = {v.item.id for v in views if v.decision and v.decision.decision == Decision.REJECT.value}
        rejected |= {i.item_id for i in inputs if i.decision is Decision.REJECT}
        minted: dict[str, UUID] = {}
        for view in views:
            if view.decision and view.decision.label_node_ids:
                minted |= {label: UUID(node_id) for label, node_id in view.decision.label_node_ids.items()}
        snapshot = _candidate_snapshot(change_set.project_id, await self._candidate_nodes(change_set))
        kind_terms = _resolve_profiles(list(change_set.profile_refs or [])).terms_by_namespace()
        effective: dict[UUID, ProposalItem] = {}
        for item_id, stored in proposals.items():
            if item_id in applied:
                effective[item_id] = stored
                continue
            payload = _bind(stored.payload, minted)
            effective[item_id] = stored.model_copy(update={"payload": payload})
        for decision in inputs:
            if decision.decision is Decision.APPLY_WITH_HUMAN_EDIT:
                effective[decision.item_id] = self._human_edit(
                    proposals[decision.item_id], decision.edit, minted, snapshot, kind_terms)
        plan = plan_selection(
            items=list(effective.values()), selected=[i.item_id for i in inputs if i.decision in APPLY_DECISIONS],
            rejected=rejected, current=snapshot, kind_terms=kind_terms, satisfied=applied)
        return plan, effective, digests, minted, rejected, snapshot

    @staticmethod
    def _human_edit(original: ProposalItem, edit: HumanEdit | None, minted: Mapping[str, UUID],
                    snapshot: TargetSnapshot, kind_terms: Mapping[str, frozenset[str]]) -> ProposalItem:
        """The human's command for this item, authored against the CURRENT candidate (the proposal is untouched)."""
        if edit is None:
            raise WBSIntelligenceInvalidError("APPLY_WITH_HUMAN_EDIT carries the human's edit")
        fields = edit.model_dump(exclude_unset=True)  # an explicit null (e.g. a root merge) is kept
        try:
            model = ModelProposalItem.model_validate({**_bind(fields, minted), "ref": original.ref,
                                                      "operation": original.operation, "rationale": original.rationale,
                                                      "confidence_pct": original.confidence_pct})
            check_proposal_shape(model)
        except (ValidationError, ItemRejected) as exc:
            raise WBSIntelligenceInvalidError("the human edit is not a valid command for this item", [str(exc)]) from exc
        if sorted(created_labels(model)) != sorted(original.creates_labels):
            raise WBSIntelligenceInvalidError(
                "a human edit keeps the labels the proposal creates (its dependants rely on them)",
                [f"expected {sorted(original.creates_labels)}"])
        allowed = set(original.uses_labels) | set(minted)
        stray = set(used_labels(model)) - allowed
        if stray:
            raise WBSIntelligenceInvalidError("a human edit cannot reference labels the proposal does not depend on",
                                              [f"unexpected labels {sorted(stray)}"])
        affected, guarded = item_guards(model, SimulatedTree.of(snapshot, kind_terms), snapshot)
        return original.model_copy(update={"payload": proposal_payload(model), "affected_node_ids": affected,
                                           "target_fingerprints": guarded})

    @staticmethod
    def _compatibility(run: WBSIntelligenceRunORM, change_set: WBSChangeSetORM) -> str | None:
        if change_set.status != ChangeSetStatus.DRAFT.value:
            return f"the change set is {change_set.status}: items are applied only into an existing DRAFT"
        if run.target_kind == TargetKind.CANDIDATE.value and change_set.id != run.target_change_set_id:
            return "the items of a candidate run apply to that candidate only"
        if run.target_kind == TargetKind.BASELINE.value and change_set.base_baseline_id != run.target_baseline_id:
            return "the items of a baseline run apply to a DRAFT based on that baseline"
        if run.target_kind == TargetKind.IMPORT.value:
            return "import runs are not applicable yet"
        return None

    # ------------------------------------------------------------------ preview (pure read)
    async def preview(self, *, project_id: UUID, run_id: UUID, tenant_id: UUID, change_set_id: UUID,
                      selections: Sequence[DecisionInput]) -> PreviewResult:
        """Simulate applying ``selections`` to the DRAFT: ZERO writes, not a decision, not an approval."""
        await self._require_project(project_id, tenant_id)
        run = await self.run(run_id, project_id, tenant_id)
        freshness = await self.freshness(run)
        change_set = await self._change_set(change_set_id, project_id, tenant_id)
        inputs = self._validated_inputs(selections, await self.items(run), apply_only=True)
        reasons: list[str] = []
        if run.status != RunStatus.COMPLETED.value:
            reasons.append(f"the run is {run.status}, not COMPLETED")
        if freshness.state is RunFreshness.STALE:
            reasons += [f"STALE: {reason}" for reason in freshness.reasons]
        incompatible = self._compatibility(run, change_set)
        if incompatible:
            reasons.append(incompatible)
        plan, effective, _, _, rejected, snapshot = await self._plan(run, change_set, inputs)
        views = await self.items(run)
        decided = {v.item.id for v in views if v.decision is not None}
        applied = {v.item.id for v in views if v.decision is not None and v.decision.decision in APPLY_DECISIONS}
        selected = {i.item_id for i in inputs}
        pending = {k: v for k, v in effective.items() if k not in applied}  # an applied prerequisite is satisfied
        items = []
        for decision in inputs:
            item = effective[decision.item_id]
            deps = dependency_closure(pending, [decision.item_id]) - applied
            if decision.item_id in decided:
                items.append(PreviewItem(decision.item_id, ItemApplicability.DECIDED))
            elif deps & rejected:
                items.append(PreviewItem(decision.item_id, ItemApplicability.BLOCKED_BY_REJECTED,
                                         tuple(sorted(map(str, deps & rejected)))))
            elif deps - selected:
                items.append(PreviewItem(decision.item_id, ItemApplicability.MISSING_PREREQUISITE,
                                         tuple(sorted(map(str, deps - selected)))))
            elif any(snapshot.fingerprint_of(key) != digest for key, digest in item.target_fingerprints.items()):
                items.append(PreviewItem(decision.item_id, ItemApplicability.CONFLICT))
            else:
                items.append(PreviewItem(decision.item_id, ItemApplicability.APPLICABLE))
        if isinstance(plan, SelectionRefusal):
            reasons += list(plan.reasons)
            return PreviewResult(freshness=freshness, items=tuple(items), applicable=False, reasons=tuple(reasons))
        nodes = () if plan.tree is None else tuple(
            PreviewNode(key=n.key, parent=n.parent, sort_order=n.sort_order, code=n.code, name=n.name,
                        decomposition_kind=n.kind, control_level=n.control_level)
            for n in sorted(plan.tree.nodes.values(), key=lambda n: (n.parent or "", n.sort_order, n.key)))
        return PreviewResult(freshness=freshness, items=tuple(items), applicable=not reasons, reasons=tuple(reasons),
                             ordered_item_ids=plan.ordered_item_ids, resulting_nodes=nodes)

    @staticmethod
    def _validated_inputs(inputs: Sequence[DecisionInput], views: Sequence[ItemView], *, apply_only: bool = False
                          ) -> list[DecisionInput]:
        by_id = {v.item.id: v for v in views}
        ids = [i.item_id for i in inputs]
        if not inputs:
            raise WBSIntelligenceInvalidError("select at least one item")
        if len(set(ids)) != len(ids):
            raise WBSIntelligenceInvalidError("an item appears twice in the selection")
        problems = []
        for decision in inputs:
            view = by_id.get(decision.item_id)
            if view is None:
                problems.append(f"{decision.item_id}: not an item of this run")
                continue
            vocabulary = PROPOSAL_DECISIONS if view.item.kind == ItemKind.PROPOSAL.value else FINDING_DECISIONS
            if decision.decision not in vocabulary:
                problems.append(f"{decision.item_id}: {decision.decision.value} is not a {view.item.kind} decision")
            if apply_only and decision.decision not in APPLY_DECISIONS:
                problems.append(f"{decision.item_id}: only applications are previewed")
            if (decision.edit is not None) != (decision.decision is Decision.APPLY_WITH_HUMAN_EDIT):
                problems.append(f"{decision.item_id}: an edit goes with APPLY_WITH_HUMAN_EDIT (and only with it)")
        if problems:
            raise WBSIntelligenceInvalidError("the selection is invalid", problems)
        return list(inputs)

    # ------------------------------------------------------------------ decide (one transaction)
    async def decide(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        tenant_id: UUID,
        actor: Actor,
        decisions: Sequence[DecisionInput],
        change_set_id: UUID | None = None,
        expected_revision: int | None = None,
    ) -> DecideResult:
        """Record the human's decisions; apply the selected proposals into the EXISTING DRAFT. All or nothing."""
        _require_author(actor, "decide WBS intelligence items")
        async with self.session.begin_nested():
            return await self._decide(project_id=project_id, run_id=run_id, tenant_id=tenant_id, actor=actor,
                                      decisions=decisions, change_set_id=change_set_id,
                                      expected_revision=expected_revision)

    async def _decide(
        self, *, project_id: UUID, run_id: UUID, tenant_id: UUID, actor: Actor, decisions: Sequence[DecisionInput],
        change_set_id: UUID | None, expected_revision: int | None,
    ) -> DecideResult:
        # Project before change set, as approve = apply: the base cannot move under this batch.
        await self._require_project(project_id, tenant_id, lock=True)
        run = await self.run(run_id, project_id, tenant_id, lock=True)
        if run.status != RunStatus.COMPLETED.value:
            raise WBSIntelligenceStateError(f"the items of a {run.status} run cannot be decided", status=run.status)
        views = await self.items(run)
        inputs = self._validated_inputs(decisions, views)
        already = [str(i.item_id) for i in inputs if next(v for v in views if v.item.id == i.item_id).decision]
        if already:
            raise WBSIntelligenceStateError("an item is decided once; its decision is history",
                                            code="WBS_INTELLIGENCE_ITEM_ALREADY_DECIDED", item_ids=already)
        batch_id = uuid4()
        applies = [i for i in inputs if i.decision in APPLY_DECISIONS]
        rows: list[WBSIntelligenceDecisionORM] = []
        decided: list[DecidedItem] = []
        change_set: WBSChangeSetORM | None = None
        revision: int | None = None
        if applies:
            if change_set_id is None or expected_revision is None:
                raise WBSIntelligenceInvalidError("applying needs the existing DRAFT change set and its expected revision")
            freshness = await self.freshness(run)
            if freshness.state is RunFreshness.STALE:
                raise WBSIntelligenceStateError("the run is STALE: re-run it", code="WBS_INTELLIGENCE_RUN_STALE",
                                                reasons=list(freshness.reasons))
            change_set = await self._change_set(change_set_id, project_id, tenant_id, lock=True)
            incompatible = self._compatibility(run, change_set)
            if incompatible:
                raise WBSIntelligenceStateError(incompatible, code="WBS_INTELLIGENCE_TARGET_MISMATCH")
            if change_set.revision != expected_revision:
                raise WBSIntelligenceStateError(f"the DRAFT is at revision {change_set.revision}",
                                                code="CHANGE_SET_REVISION_CONFLICT", current_revision=change_set.revision)
            plan, effective, digests, minted, _, _ = await self._plan(run, change_set, inputs)
            if isinstance(plan, SelectionRefusal):
                raise WBSIntelligenceSelectionRefusedError(plan)
            governed = WBSGovernedChangeService(self.session)
            revision = expected_revision
            labels = dict(minted)
            by_item = {i.item_id: i for i in applies}
            for item_id in plan.ordered_item_ids:
                decision_input = by_item[item_id]
                item = effective[item_id]
                decision_id = uuid4()
                provenance = {"intelligence_run_id": str(run.id), "intelligence_item_id": str(item_id),
                              "decision_id": str(decision_id), "application_mode": decision_input.decision.value}
                try:
                    command = to_command(ProposalOperation(item.operation), item.payload, labels)
                except (UnresolvedLabelError, KeyError, ValueError) as exc:
                    raise WBSIntelligenceInvalidError("the item does not resolve to a governed command", [str(exc)]) from exc
                before = revision
                result = await governed.execute(project_id=project_id, change_set_id=change_set.id, tenant_id=tenant_id,
                                                actor=actor, expected_revision=revision, command=command,
                                                provenance=provenance)
                revision = result.revision
                new_labels = minted_labels(ProposalOperation(item.operation), item.payload, result.node_ids)
                labels |= new_labels
                commands = [command_json(command)]
                label_ids = {label: str(node_id) for label, node_id in new_labels.items()}
                rows.append(WBSIntelligenceDecisionORM(
                    id=decision_id, tenant_id=tenant_id, project_id=project_id, run_id=run.id, item_id=item_id,
                    item_kind=ItemKind.PROPOSAL.value, decision=decision_input.decision.value, batch_id=batch_id,
                    decided_by=actor.user_id, decided_by_kind=ActorKind.HUMAN.value, reason=decision_input.reason,
                    change_set_id=change_set.id, change_set_revision_before=before, change_set_revision_after=revision,
                    proposal_body_digest=digests[item_id], applied_commands=commands,
                    applied_commands_digest=digest_json(commands), label_node_ids=label_ids))
                decided.append(DecidedItem(decision_id=decision_id, item_id=item_id, decision=decision_input.decision,
                                           change_set_revision_after=revision, label_node_ids=label_ids))
        kinds = {v.item.id: v.item.kind for v in views}
        for decision_input in inputs:
            if decision_input.decision in APPLY_DECISIONS:
                continue
            decision_id = uuid4()
            rows.append(WBSIntelligenceDecisionORM(
                id=decision_id, tenant_id=tenant_id, project_id=project_id, run_id=run.id,
                item_id=decision_input.item_id, item_kind=kinds[decision_input.item_id],
                decision=decision_input.decision.value, batch_id=batch_id, decided_by=actor.user_id,
                decided_by_kind=ActorKind.HUMAN.value, reason=decision_input.reason))
            decided.append(DecidedItem(decision_id=decision_id, item_id=decision_input.item_id,
                                       decision=decision_input.decision, change_set_revision_after=None))
        for row in rows:
            self.session.add(row)
        await self.session.flush()
        for row in rows:
            await self._event(
                project_id=project_id, tenant_id=tenant_id, event_type=EVENT_ITEM_DECIDED, actor=f"user:{actor.user_id}",
                payload={
                    "tenant_id": str(tenant_id), "project_id": str(project_id), "run_id": str(run.id),
                    "item_id": str(row.item_id), "item_kind": row.item_kind, "decision_id": str(row.id),
                    "decision": row.decision, "batch_id": str(batch_id),
                    "change_set_id": None if row.change_set_id is None else str(row.change_set_id),
                    "change_set_revision_before": row.change_set_revision_before,
                    "change_set_revision_after": row.change_set_revision_after,
                    "proposal_body_digest": row.proposal_body_digest,
                    "applied_commands_digest": row.applied_commands_digest,
                },
            )
        return DecideResult(batch_id=batch_id, decisions=tuple(decided),
                            change_set_id=None if change_set is None else change_set.id, change_set_revision=revision)


__all__ = [
    "APPLY_DECISIONS",
    "EVENT_ITEM_DECIDED",
    "EVENT_RUN_COMPLETED",
    "DecideResult",
    "DecidedItem",
    "Decision",
    "DecisionInput",
    "FreshnessView",
    "HumanEdit",
    "ItemApplicability",
    "ItemKind",
    "ItemView",
    "PreviewItem",
    "PreviewNode",
    "PreviewResult",
    "RunFreshness",
    "RunRequestResult",
    "WBSIntelligenceForbiddenError",
    "WBSIntelligenceInvalidError",
    "WBSIntelligenceNotFoundError",
    "WBSIntelligenceSelectionRefusedError",
    "WBSIntelligenceService",
    "WBSIntelligenceStateError",
]
