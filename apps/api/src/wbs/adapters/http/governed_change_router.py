"""Governed WBS change commands (PC-2a.2 #896, ADR-029).

Command-oriented, never a generic patch: open a change set, edit its DRAFT candidate with
typed commands under an expected revision, submit, reopen, withdraw, reject, approve (= apply)
and rebase. The actor is ALWAYS the authenticated session user -- request bodies forbid unknown
fields, so no reviewer, submitter or approver identity can be supplied by the client.

Approve commits the apply transaction first and only then enqueues the ProjectSnapshot
(``baseline_changed``); a dispatch failure never undoes a valid baseline.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import require_tenant_id
from src.wbs.adapters.http.governance_router import WBSChangeSetSummary, change_set_summary
from src.wbs.adapters.persistence.governance_repository import Actor
from src.wbs.application.governed_change_service import (
    AddNode,
    AdoptLegacyNode,
    EditCommand,
    MergeNodes,
    MoveNode,
    NodeSpec,
    RecodeNode,
    RemoveNode,
    ReorderNode,
    SplitNode,
    UpdateNode,
    WBSGovernedChangeService,
    enqueue_baseline_snapshot,
)
from src.wbs.domain.governance import ActorKind

router = APIRouter(prefix="/projects", tags=["WBS governance"])

_PREFIX = "/{project_id}/wbs-governance/change-sets"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------- requests
class WBSNodeSpecRequest(_Strict):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    control_level: str = "none"
    decomposition_kind: str | None = None
    dictionary: dict[str, Any] | None = None

    def spec(self) -> NodeSpec:
        return NodeSpec(name=self.name, code=self.code, control_level=self.control_level,
                        decomposition_kind=self.decomposition_kind, dictionary=self.dictionary)


class WBSAddNodeCommand(_Strict):
    type: Literal["ADD_NODE"]
    node: WBSNodeSpecRequest
    parent_id: UUID | None = Field(default=None, description="a candidate node id (null = top level)")
    position: int | None = Field(default=None, ge=1, description="1-based sibling position (default: append)")


class WBSUpdateNodeCommand(_Strict):
    """Rename / re-describe / reclassify. Only the fields present are changed; same identity."""

    type: Literal["UPDATE_NODE"]
    node_id: UUID
    name: str | None = Field(default=None, min_length=1, max_length=255)
    dictionary: dict[str, Any] | None = None
    decomposition_kind: str | None = None
    control_level: str | None = None


class WBSRecodeNodeCommand(_Strict):
    type: Literal["RECODE_NODE"]
    node_id: UUID
    code: str = Field(min_length=1, max_length=50)


class WBSMoveNodeCommand(_Strict):
    type: Literal["MOVE_NODE"]
    node_id: UUID
    parent_id: UUID | None
    position: int | None = Field(default=None, ge=1)


class WBSReorderNodeCommand(_Strict):
    type: Literal["REORDER_NODE"]
    node_id: UUID
    position: int = Field(ge=1)


class WBSRemoveNodeCommand(_Strict):
    type: Literal["REMOVE_NODE"]
    node_id: UUID


class WBSSplitNodeCommand(_Strict):
    type: Literal["SPLIT_NODE"]
    source_id: UUID
    targets: list[WBSNodeSpecRequest] = Field(min_length=2)
    child_targets: dict[UUID, int] = Field(default_factory=dict, description="every child of the source -> target index")


class WBSMergeNodesCommand(_Strict):
    type: Literal["MERGE_NODES"]
    source_ids: list[UUID] = Field(min_length=2)
    target: WBSNodeSpecRequest
    parent_id: UUID | None = Field(default=None, description="omit to place the result where the first source was")
    position: int | None = Field(default=None, ge=1)


class WBSAdoptLegacyNodeCommand(_Strict):
    type: Literal["ADOPT_LEGACY_NODE"]
    legacy_node_id: UUID
    parent_id: UUID | None = None
    position: int | None = Field(default=None, ge=1)


CommandBody = Annotated[
    WBSAddNodeCommand | WBSUpdateNodeCommand | WBSRecodeNodeCommand | WBSMoveNodeCommand | WBSReorderNodeCommand
    | WBSRemoveNodeCommand | WBSSplitNodeCommand | WBSMergeNodesCommand | WBSAdoptLegacyNodeCommand,
    Field(discriminator="type"),
]


class WBSChangeSetCommandRequest(_Strict):
    expected_revision: int = Field(ge=1, description="the DRAFT revision the edit is based on")
    command: CommandBody


class CreateWBSChangeSetRequest(_Strict):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    profile_refs: list[dict[str, str]] = Field(default_factory=list)


class WBSExpectedRevisionRequest(_Strict):
    expected_revision: int = Field(ge=1)


class WBSDecisionRequest(_Strict):
    expected_revision: int = Field(ge=1, description="the submitted revision the reviewer looked at")
    expected_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$", description="the submitted digest reviewed")


class WBSRejectRequest(WBSDecisionRequest):
    reason: str = Field(min_length=1, max_length=4000)


# ---------------------------------------------------------------------------- responses
class WBSChangeSetCommandResponse(BaseModel):
    revision: int
    node_ids: list[UUID] = Field(description="ids minted or affected by the command")


class WBSChangeSetSubmitResponse(BaseModel):
    change_set_id: UUID
    status: str
    submitted_revision: int
    submitted_digest: str


class WBSChangeSetRevisionResponse(BaseModel):
    change_set_id: UUID
    status: str
    revision: int


class WBSApplyResponse(BaseModel):
    change_set_id: UUID
    status: str = "APPLIED"
    baseline_id: UUID
    baseline_no: int
    tree_digest: str
    change_set_digest: str
    self_approved: bool
    applied_at: datetime
    event_id: UUID
    retired: list[dict[str, str]]
    stale_change_set_ids: list[UUID]
    snapshot_enqueued: bool


# ---------------------------------------------------------------------------- plumbing
async def get_governed_change_service(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[WBSGovernedChangeService]:
    """One tenant-scoped transaction per command (committed on success, rolled back on error)."""
    async with get_session_with_tenant(current_user.tenant_id) as db:
        yield WBSGovernedChangeService(db)


def _actor(user: User) -> Actor:
    """The authenticated session user is the only possible actor of a governed command."""
    role = getattr(user.role, "value", user.role)
    return Actor(user_id=user.id, kind=ActorKind.HUMAN, role=str(role) if role is not None else None)


def _command(body: CommandBody) -> EditCommand:
    if isinstance(body, WBSAddNodeCommand):
        return AddNode(spec=body.node.spec(), parent_id=body.parent_id, position=body.position)
    if isinstance(body, WBSUpdateNodeCommand):
        fields = body.model_fields_set - {"type", "node_id"}
        return UpdateNode(node_id=body.node_id, changes={name: getattr(body, name) for name in fields})
    if isinstance(body, WBSRecodeNodeCommand):
        return RecodeNode(node_id=body.node_id, code=body.code)
    if isinstance(body, WBSMoveNodeCommand):
        return MoveNode(node_id=body.node_id, parent_id=body.parent_id, position=body.position)
    if isinstance(body, WBSReorderNodeCommand):
        return ReorderNode(node_id=body.node_id, position=body.position)
    if isinstance(body, WBSRemoveNodeCommand):
        return RemoveNode(node_id=body.node_id)
    if isinstance(body, WBSSplitNodeCommand):
        return SplitNode(source_id=body.source_id, targets=[t.spec() for t in body.targets],
                         child_targets=dict(body.child_targets))
    if isinstance(body, WBSMergeNodesCommand):
        if "parent_id" in body.model_fields_set:
            return MergeNodes(source_ids=list(body.source_ids), target=body.target.spec(),
                              parent_id=body.parent_id, position=body.position)
        return MergeNodes(source_ids=list(body.source_ids), target=body.target.spec(), position=body.position)
    return AdoptLegacyNode(legacy_node_id=body.legacy_node_id, parent_id=body.parent_id, position=body.position)


# ---------------------------------------------------------------------------- endpoints
@router.post(_PREFIX, response_model=WBSChangeSetSummary, status_code=status.HTTP_201_CREATED)
async def create_wbs_change_set(
    project_id: UUID,
    body: CreateWBSChangeSetRequest,
    current_user: User = Depends(get_current_user),
    service: WBSGovernedChangeService = Depends(get_governed_change_service),
) -> WBSChangeSetSummary:
    """Open a DRAFT against the current baseline (a CHANGE_BASELINE draft starts as that baseline)."""
    change_set = await service.create_change_set(
        project_id=project_id, tenant_id=require_tenant_id(current_user.tenant_id), actor=_actor(current_user),
        title=body.title, description=body.description, evidence_refs=body.evidence_refs, profile_refs=body.profile_refs,
    )
    return WBSChangeSetSummary(**change_set_summary(change_set))


@router.post(f"{_PREFIX}/{{change_set_id}}/commands", response_model=WBSChangeSetCommandResponse)
async def execute_wbs_change_set_command(
    project_id: UUID,
    change_set_id: UUID,
    body: WBSChangeSetCommandRequest,
    current_user: User = Depends(get_current_user),
    service: WBSGovernedChangeService = Depends(get_governed_change_service),
) -> WBSChangeSetCommandResponse:
    """One typed edit of the DRAFT candidate; 409 CHANGE_SET_REVISION_CONFLICT when the revision moved."""
    result = await service.execute(
        project_id=project_id, change_set_id=change_set_id, tenant_id=require_tenant_id(current_user.tenant_id),
        actor=_actor(current_user), expected_revision=body.expected_revision, command=_command(body.command),
    )
    return WBSChangeSetCommandResponse(revision=result.revision, node_ids=result.node_ids)


@router.post(f"{_PREFIX}/{{change_set_id}}/submit", response_model=WBSChangeSetSubmitResponse)
async def submit_wbs_change_set(
    project_id: UUID,
    change_set_id: UUID,
    body: WBSExpectedRevisionRequest,
    current_user: User = Depends(get_current_user),
    service: WBSGovernedChangeService = Depends(get_governed_change_service),
) -> WBSChangeSetSubmitResponse:
    digest = await service.submit(
        project_id=project_id, change_set_id=change_set_id, tenant_id=require_tenant_id(current_user.tenant_id),
        actor=_actor(current_user), expected_revision=body.expected_revision,
    )
    return WBSChangeSetSubmitResponse(change_set_id=change_set_id, status="SUBMITTED",
                                      submitted_revision=body.expected_revision, submitted_digest=digest)


@router.post(f"{_PREFIX}/{{change_set_id}}/reopen", response_model=WBSChangeSetRevisionResponse)
async def reopen_wbs_change_set(
    project_id: UUID,
    change_set_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WBSGovernedChangeService = Depends(get_governed_change_service),
) -> WBSChangeSetRevisionResponse:
    revision = await service.reopen(project_id=project_id, change_set_id=change_set_id,
                                    tenant_id=require_tenant_id(current_user.tenant_id), actor=_actor(current_user))
    return WBSChangeSetRevisionResponse(change_set_id=change_set_id, status="DRAFT", revision=revision)


@router.post(f"{_PREFIX}/{{change_set_id}}/withdraw", response_model=WBSChangeSetRevisionResponse)
async def withdraw_wbs_change_set(
    project_id: UUID,
    change_set_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WBSGovernedChangeService = Depends(get_governed_change_service),
) -> WBSChangeSetRevisionResponse:
    tenant_id = require_tenant_id(current_user.tenant_id)
    await service.withdraw(project_id=project_id, change_set_id=change_set_id, tenant_id=tenant_id,
                           actor=_actor(current_user))
    change_set = await service.change_set(change_set_id, project_id, tenant_id)
    return WBSChangeSetRevisionResponse(change_set_id=change_set_id, status=change_set.status, revision=change_set.revision)


@router.post(f"{_PREFIX}/{{change_set_id}}/reject", response_model=WBSChangeSetRevisionResponse)
async def reject_wbs_change_set(
    project_id: UUID,
    change_set_id: UUID,
    body: WBSRejectRequest,
    current_user: User = Depends(get_current_user),
    service: WBSGovernedChangeService = Depends(get_governed_change_service),
) -> WBSChangeSetRevisionResponse:
    await service.reject(
        project_id=project_id, change_set_id=change_set_id, tenant_id=require_tenant_id(current_user.tenant_id),
        actor=_actor(current_user), expected_revision=body.expected_revision, expected_digest=body.expected_digest,
        reason=body.reason,
    )
    return WBSChangeSetRevisionResponse(change_set_id=change_set_id, status="REJECTED", revision=body.expected_revision)


@router.post(f"{_PREFIX}/{{change_set_id}}/approve", response_model=WBSApplyResponse)
async def approve_wbs_change_set(
    project_id: UUID,
    change_set_id: UUID,
    body: WBSDecisionRequest,
    current_user: User = Depends(get_current_user),
    service: WBSGovernedChangeService = Depends(get_governed_change_service),
) -> WBSApplyResponse:
    """Approve = apply in ONE transaction; the snapshot is enqueued only after it commits."""
    tenant_id = require_tenant_id(current_user.tenant_id)
    result = await service.approve(
        project_id=project_id, change_set_id=change_set_id, tenant_id=tenant_id, actor=_actor(current_user),
        expected_revision=body.expected_revision, expected_digest=body.expected_digest,
    )
    await service.session.commit()
    enqueued = enqueue_baseline_snapshot(project_id=project_id, tenant_id=tenant_id, result=result)
    return WBSApplyResponse(
        change_set_id=result.change_set_id, baseline_id=result.baseline_id, baseline_no=result.baseline_no,
        tree_digest=result.tree_digest, change_set_digest=result.change_set_digest,
        self_approved=result.self_approved, applied_at=result.applied_at, event_id=result.event_id,
        retired=result.retired, stale_change_set_ids=result.stale_change_set_ids, snapshot_enqueued=enqueued,
    )


@router.post(f"{_PREFIX}/{{change_set_id}}/rebase", response_model=WBSChangeSetSummary, status_code=status.HTTP_201_CREATED)
async def rebase_wbs_change_set(
    project_id: UUID,
    change_set_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WBSGovernedChangeService = Depends(get_governed_change_service),
) -> WBSChangeSetSummary:
    """A STALE change set stays as audit history; its proposal restarts as a NEW draft on the latest baseline."""
    change_set = await service.rebase(project_id=project_id, change_set_id=change_set_id,
                                      tenant_id=require_tenant_id(current_user.tenant_id), actor=_actor(current_user))
    return WBSChangeSetSummary(**change_set_summary(change_set))


__all__ = ["get_governed_change_service", "router"]
