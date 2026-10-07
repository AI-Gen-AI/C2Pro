"""WBS intelligence runs, items, preview and human decisions (PC-2b.2 #921, ADR-030).

Minimal surface: request a deterministic run, read it, cancel it, list its items, preview a
selection (pure read) and decide items. There is NO generate, model, import, optimizer or
auto-apply endpoint. The actor is ALWAYS the authenticated session user (request bodies forbid
unknown fields); only a human ``user`` or ``admin`` requests, cancels or decides -- never ``api``,
AI or a service. A decision never approves anything: applying an item edits an EXISTING DRAFT
through the governed commands, and the baseline still needs submit + human admin approve.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import require_tenant_id
from src.wbs.adapters.http.governed_change_router import _actor
from src.wbs.adapters.persistence.intelligence_models import (
    WBSIntelligenceDecisionORM,
    WBSIntelligenceRunORM,
)
from src.wbs.intelligence.application.service import (
    DecideResult,
    Decision,
    DecisionInput,
    FreshnessView,
    HumanEdit,
    ItemView,
    PreviewResult,
    WBSIntelligenceService,
)
from src.wbs.intelligence.contracts.run import TargetKind

router = APIRouter(prefix="/projects", tags=["WBS intelligence"])

_PREFIX = "/{project_id}/wbs-intelligence/runs"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------- requests
class RequestWBSIntelligenceRunRequest(_Strict):
    """A deterministic qualification of a DRAFT candidate or of the current baseline (no LLM)."""

    target_kind: Literal["CANDIDATE", "BASELINE"]
    change_set_id: UUID | None = Field(default=None, description="the DRAFT change set (CANDIDATE)")
    baseline_id: UUID | None = Field(default=None, description="the current baseline (BASELINE)")
    rerun: bool = Field(default=False, description="always start a NEW run (the previous runs stay readable)")


class WBSIntelligenceHumanEdit(_Strict):
    """The human's command fields for the item's operation (the stored proposal is never edited)."""

    node: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    parent: dict[str, Any] | None = None
    position: int | None = Field(default=None, ge=1)
    creates_label: str | None = None
    spec: dict[str, Any] | None = None
    changes: dict[str, Any] | None = None
    code: str | None = None
    split_targets: list[dict[str, Any]] = Field(default_factory=list)
    child_targets: dict[str, int] = Field(default_factory=dict)

    def edit(self) -> HumanEdit:
        return HumanEdit.model_validate(self.model_dump(exclude_unset=True))


class WBSIntelligenceSelection(_Strict):
    item_id: UUID
    decision: Literal["APPLY_AS_PROPOSED", "APPLY_WITH_HUMAN_EDIT"]
    edit: WBSIntelligenceHumanEdit | None = None


class PreviewWBSIntelligenceRequest(_Strict):
    change_set_id: UUID = Field(description="the existing DRAFT the selection would be applied to")
    selections: list[WBSIntelligenceSelection] = Field(min_length=1)


class WBSIntelligenceDecisionRequest(_Strict):
    item_id: UUID
    decision: Literal["APPLY_AS_PROPOSED", "APPLY_WITH_HUMAN_EDIT", "REJECT", "ACKNOWLEDGE", "DISMISS", "NO_CHANGE"]
    reason: str | None = Field(default=None, min_length=1, max_length=4000)
    edit: WBSIntelligenceHumanEdit | None = None


class DecideWBSIntelligenceRequest(_Strict):
    """One all-or-nothing batch. Applying needs an EXISTING DRAFT and its expected revision."""

    change_set_id: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1)
    decisions: list[WBSIntelligenceDecisionRequest] = Field(min_length=1)


# ---------------------------------------------------------------------------- responses
class WBSIntelligenceFreshness(BaseModel):
    state: Literal["FRESH", "STALE"]
    reasons: list[str]


class WBSIntelligenceRunResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode: str
    execution_type: str
    target_kind: str
    target_id: UUID | None
    target_digest: str | None
    target_change_set_revision: int | None
    target_base_baseline_id: UUID | None
    evidence_set_digest: str
    profile_refs: list[dict[str, Any]]
    proposal_contract_version: str
    qualification_vocab_version: str
    orchestration_version: str
    idempotency_key: str
    model_provenance: dict[str, Any] | None
    status: str
    outcome: str | None
    qualification: dict[str, Any] | None
    qualification_digest: str | None
    failure_reason: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    freshness: WBSIntelligenceFreshness
    reused: bool = False


class WBSIntelligenceDecisionResponse(BaseModel):
    id: UUID
    decision: str
    batch_id: UUID
    decided_by: UUID
    reason: str | None
    change_set_id: UUID | None
    change_set_revision_before: int | None
    change_set_revision_after: int | None
    proposal_body_digest: str | None
    applied_commands: list[dict[str, Any]] | None
    applied_commands_digest: str | None
    label_node_ids: dict[str, str] | None
    created_at: datetime


class WBSIntelligenceItemResponse(BaseModel):
    id: UUID
    run_id: UUID
    kind: str
    ref: str
    ordinal: int
    contract_version: str
    operation: str | None
    body: dict[str, Any]
    body_digest: str
    created_at: datetime
    decision: WBSIntelligenceDecisionResponse | None


class WBSIntelligencePreviewItem(BaseModel):
    item_id: UUID
    applicability: Literal["APPLICABLE", "CONFLICT", "MISSING_PREREQUISITE", "BLOCKED_BY_REJECTED", "DECIDED"]
    reasons: list[str]


class WBSIntelligencePreviewNode(BaseModel):
    key: str = Field(description="a candidate node id, or label:<local label> for a node the selection would create")
    parent: str | None
    sort_order: int
    code: str | None
    name: str
    decomposition_kind: str | None
    control_level: str


class WBSIntelligencePreviewResponse(BaseModel):
    """A simulated read model: nothing was written, decided or approved."""

    freshness: WBSIntelligenceFreshness
    applicable: bool
    reasons: list[str]
    items: list[WBSIntelligencePreviewItem]
    ordered_item_ids: list[UUID]
    resulting_nodes: list[WBSIntelligencePreviewNode]


class WBSIntelligenceDecidedItem(BaseModel):
    decision_id: UUID
    item_id: UUID
    decision: str
    change_set_revision_after: int | None
    label_node_ids: dict[str, str]


class DecideWBSIntelligenceResponse(BaseModel):
    batch_id: UUID
    decisions: list[WBSIntelligenceDecidedItem]
    change_set_id: UUID | None
    change_set_revision: int | None


# ---------------------------------------------------------------------------- plumbing
async def get_wbs_intelligence_service(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[WBSIntelligenceService]:
    """One tenant-scoped transaction per request (committed on success, rolled back on error)."""
    async with get_session_with_tenant(current_user.tenant_id) as db:
        yield WBSIntelligenceService(db)


def _freshness(view: FreshnessView) -> WBSIntelligenceFreshness:
    return WBSIntelligenceFreshness(state=view.state.value, reasons=list(view.reasons))


def _run(run: WBSIntelligenceRunORM, freshness: FreshnessView, *, reused: bool = False) -> WBSIntelligenceRunResponse:
    return WBSIntelligenceRunResponse(
        id=run.id, project_id=run.project_id, mode=run.mode, execution_type=run.execution_type,
        target_kind=run.target_kind, target_id=run.target_change_set_id or run.target_baseline_id or run.target_import_id,
        target_digest=run.target_digest, target_change_set_revision=run.target_change_set_revision,
        target_base_baseline_id=run.target_base_baseline_id, evidence_set_digest=run.evidence_set_digest,
        profile_refs=list(run.profile_refs or []), proposal_contract_version=run.proposal_contract_version,
        qualification_vocab_version=run.qualification_vocab_version, orchestration_version=run.orchestration_version,
        idempotency_key=run.idempotency_key, model_provenance=run.model_provenance, status=run.status,
        outcome=run.outcome, qualification=run.qualification, qualification_digest=run.qualification_digest,
        failure_reason=run.failure_reason, created_at=run.created_at, started_at=run.started_at,
        completed_at=run.completed_at, freshness=_freshness(freshness), reused=reused,
    )


def _decision(row: WBSIntelligenceDecisionORM) -> WBSIntelligenceDecisionResponse:
    return WBSIntelligenceDecisionResponse(
        id=row.id, decision=row.decision, batch_id=row.batch_id, decided_by=row.decided_by, reason=row.reason,
        change_set_id=row.change_set_id, change_set_revision_before=row.change_set_revision_before,
        change_set_revision_after=row.change_set_revision_after, proposal_body_digest=row.proposal_body_digest,
        applied_commands=row.applied_commands, applied_commands_digest=row.applied_commands_digest,
        label_node_ids=row.label_node_ids, created_at=row.created_at,
    )


def _item(view: ItemView) -> WBSIntelligenceItemResponse:
    item = view.item
    return WBSIntelligenceItemResponse(
        id=item.id, run_id=item.run_id, kind=item.kind, ref=item.ref, ordinal=item.ordinal,
        contract_version=item.contract_version, operation=item.operation, body=item.body, body_digest=item.body_digest,
        created_at=item.created_at, decision=None if view.decision is None else _decision(view.decision),
    )


def _preview(result: PreviewResult) -> WBSIntelligencePreviewResponse:
    return WBSIntelligencePreviewResponse(
        freshness=_freshness(result.freshness), applicable=result.applicable, reasons=list(result.reasons),
        items=[WBSIntelligencePreviewItem(item_id=i.item_id, applicability=i.applicability.value, reasons=list(i.reasons))
               for i in result.items],
        ordered_item_ids=list(result.ordered_item_ids),
        resulting_nodes=[WBSIntelligencePreviewNode(**n.__dict__) for n in result.resulting_nodes],
    )


def _decided(result: DecideResult) -> DecideWBSIntelligenceResponse:
    return DecideWBSIntelligenceResponse(
        batch_id=result.batch_id, change_set_id=result.change_set_id, change_set_revision=result.change_set_revision,
        decisions=[WBSIntelligenceDecidedItem(decision_id=d.decision_id, item_id=d.item_id, decision=d.decision.value,
                                              change_set_revision_after=d.change_set_revision_after,
                                              label_node_ids=dict(d.label_node_ids)) for d in result.decisions],
    )


# ---------------------------------------------------------------------------- endpoints
@router.post(_PREFIX, response_model=WBSIntelligenceRunResponse, status_code=status.HTTP_201_CREATED)
async def request_wbs_intelligence_run(
    project_id: UUID,
    body: RequestWBSIntelligenceRunRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    service: WBSIntelligenceService = Depends(get_wbs_intelligence_service),
) -> WBSIntelligenceRunResponse:
    """Request a deterministic qualification run; the same request reuses the tenant's completed run (200)."""
    result = await service.request_deterministic_run(
        project_id=project_id, tenant_id=require_tenant_id(current_user.tenant_id), actor=_actor(current_user),
        target_kind=TargetKind(body.target_kind), change_set_id=body.change_set_id, baseline_id=body.baseline_id,
        rerun=body.rerun,
    )
    if result.reused:
        response.status_code = status.HTTP_200_OK
    return _run(result.run, await service.freshness(result.run), reused=result.reused)


@router.get(f"{_PREFIX}/{{run_id}}", response_model=WBSIntelligenceRunResponse)
async def get_wbs_intelligence_run(
    project_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WBSIntelligenceService = Depends(get_wbs_intelligence_service),
) -> WBSIntelligenceRunResponse:
    """The run with its qualification report and its DERIVED freshness (STALE is never stored)."""
    run = await service.run(run_id, project_id, require_tenant_id(current_user.tenant_id))
    return _run(run, await service.freshness(run))


@router.post(f"{_PREFIX}/{{run_id}}/cancel", response_model=WBSIntelligenceRunResponse)
async def cancel_wbs_intelligence_run(
    project_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WBSIntelligenceService = Depends(get_wbs_intelligence_service),
) -> WBSIntelligenceRunResponse:
    """Cancel a REQUESTED or RUNNING run (terminal runs are immutable)."""
    run = await service.cancel_run(project_id=project_id, run_id=run_id,
                                   tenant_id=require_tenant_id(current_user.tenant_id), actor=_actor(current_user))
    return _run(run, await service.freshness(run))


@router.get(f"{_PREFIX}/{{run_id}}/items", response_model=list[WBSIntelligenceItemResponse])
async def list_wbs_intelligence_items(
    project_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WBSIntelligenceService = Depends(get_wbs_intelligence_service),
) -> list[WBSIntelligenceItemResponse]:
    """The run's immutable findings and proposals with their decisions (decided items stay readable)."""
    run = await service.run(run_id, project_id, require_tenant_id(current_user.tenant_id))
    return [_item(view) for view in await service.items(run)]


@router.post(f"{_PREFIX}/{{run_id}}/preview", response_model=WBSIntelligencePreviewResponse)
async def preview_wbs_intelligence_selection(
    project_id: UUID,
    run_id: UUID,
    body: PreviewWBSIntelligenceRequest,
    current_user: User = Depends(get_current_user),
    service: WBSIntelligenceService = Depends(get_wbs_intelligence_service),
) -> WBSIntelligencePreviewResponse:
    """Simulate applying the selection to the DRAFT. Pure read: no write, no decision, no approval."""
    result = await service.preview(
        project_id=project_id, run_id=run_id, tenant_id=require_tenant_id(current_user.tenant_id),
        change_set_id=body.change_set_id,
        selections=[DecisionInput(item_id=s.item_id, decision=Decision(s.decision),
                                  edit=None if s.edit is None else s.edit.edit()) for s in body.selections],
    )
    await service.session.rollback()  # belt and braces: a preview never commits anything
    return _preview(result)


@router.post(f"{_PREFIX}/{{run_id}}/decisions", response_model=DecideWBSIntelligenceResponse)
async def decide_wbs_intelligence_items(
    project_id: UUID,
    run_id: UUID,
    body: DecideWBSIntelligenceRequest,
    current_user: User = Depends(get_current_user),
    service: WBSIntelligenceService = Depends(get_wbs_intelligence_service),
) -> DecideWBSIntelligenceResponse:
    """Record the human's decisions; applied items edit the EXISTING DRAFT via the governed commands.

    All or nothing: one invalid item and nothing is applied, decided or emitted. A decision never
    approves a baseline -- the DRAFT still goes through submit and human admin approve = apply.
    """
    result = await service.decide(
        project_id=project_id, run_id=run_id, tenant_id=require_tenant_id(current_user.tenant_id),
        actor=_actor(current_user), change_set_id=body.change_set_id, expected_revision=body.expected_revision,
        decisions=[DecisionInput(item_id=d.item_id, decision=Decision(d.decision), reason=d.reason,
                                 edit=None if d.edit is None else d.edit.edit()) for d in body.decisions],
    )
    return _decided(result)


__all__ = ["get_wbs_intelligence_service", "router"]
