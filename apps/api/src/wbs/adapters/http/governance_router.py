"""WBS governance read API (PC-2a.1 #895, ADR-029).

Read-only inspection of the DERIVED WBS authority, change sets (with their candidate tree,
lineage and retirements) and the immutable baseline history, including "the approved WBS as
of T". There are deliberately NO mutations here: the governed commands and approve = apply
live in ``governed_change_router`` (PC-2a.2 #896); the live ``GET /projects/{id}/wbs`` reader
is unchanged until PC-2a.3 (#897).

A candidate tree is always served as a PROPOSAL of its change set, never as live WBS.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import require_tenant_id
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository
from src.wbs.adapters.persistence.governance_models import (
    WBSBaselineNodeORM,
    WBSBaselineORM,
    WBSChangeSetNodeORM,
    WBSChangeSetORM,
)
from src.wbs.adapters.persistence.governance_repository import (
    BaselineDetail,
    WBSGovernanceRepository,
)
from src.wbs.domain.governance import ChangeSetStatus

router = APIRouter(prefix="/projects", tags=["WBS governance"])


class WBSAuthorityResponse(BaseModel):
    """The single derived authority of a project's WBS (never a stored flag)."""

    state: str = Field(description="NO_WBS | LEGACY_UNGOVERNED | APPROVED_BASELINE")
    display_state: str = Field(description="state, or DRAFT_ONLY for NO_WBS with an open change set")
    approved: bool
    draft_exists: bool
    baseline_id: UUID | None
    baseline_no: int | None
    tree_digest: str | None
    applied_at: datetime | None
    open_change_sets: int
    legacy_node_count: int = Field(description="live WBS rows that no approved baseline governs")


class WBSChangeSetSummary(BaseModel):
    id: UUID
    status: str
    revision: int
    origin: str = Field(description="manual | ai | import -- provenance only, never authority")
    entry_mode: str = Field(description="GENERATE | IMPORT_REVIEW | CHANGE_BASELINE")
    base_baseline_id: UUID | None
    title: str
    description: str | None
    submitted_digest: str | None
    submitted_revision: int | None
    submitted_at: datetime | None
    decided_at: datetime | None
    decision_reason: str | None
    created_at: datetime
    updated_at: datetime


class WBSCandidateNodeResponse(BaseModel):
    """A PROPOSED node of a change set's candidate tree -- not live WBS."""

    node_id: UUID
    parent_id: UUID | None
    sort_order: int
    code: str | None
    name: str
    control_level: str
    decomposition_kind: str | None
    dictionary: dict[str, Any] | None
    origin_kind: str = Field(description="existing | minted | adopted_legacy")


class WBSLineageEdgeResponse(BaseModel):
    kind: str
    source_node_id: UUID
    target_node_id: UUID


class WBSRetirementResponse(BaseModel):
    """An identity that leaves the WBS through this change set, and what it was."""

    node_id: UUID
    disposition: str = Field(description="REMOVED | SPLIT | MERGED | SUPERSEDED | RETIRED_ON_BASELINE")
    source: str = Field(description="baseline | legacy")
    snapshot: dict[str, Any]


class WBSChangeSetDetailResponse(WBSChangeSetSummary):
    profile_refs: list[dict[str, Any]]
    evidence_refs: list[str]
    current_digest: str = Field(description="digest the change set would be signed with at its current revision")
    nodes: list[WBSCandidateNodeResponse]
    lineage: list[WBSLineageEdgeResponse]
    retirements: list[WBSRetirementResponse] = Field(default_factory=list)


class WBSBaselineSummary(BaseModel):
    id: UUID
    baseline_no: int
    parent_baseline_id: UUID | None
    source_change_set_id: UUID
    tree_digest: str
    change_set_digest: str
    node_count: int
    self_approved: bool
    applied_at: datetime


class WBSBaselineNodeResponse(BaseModel):
    node_id: UUID
    parent_id: UUID | None
    sort_order: int
    code: str
    name: str
    control_level: str
    decomposition_kind: str | None
    dictionary: dict[str, Any] | None


class WBSBaselineDetailResponse(WBSBaselineSummary):
    digest_verified: bool = Field(description="the snapshot recomputes to its recorded tree digest")
    nodes: list[WBSBaselineNodeResponse]


async def get_governance_repository(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[WBSGovernanceRepository]:
    """Open the governance reader with the caller's RLS tenant context."""
    async with get_session_with_tenant(current_user.tenant_id) as db:
        yield WBSGovernanceRepository(db)


async def _require_project(repository: WBSGovernanceRepository, project_id: UUID, tenant_id: UUID) -> None:
    if not await SQLAlchemyProjectRepository(repository.session).exists_by_id(project_id, tenant_id):
        raise HTTPException(status_code=404, detail="Project not found")


def change_set_summary(change_set: WBSChangeSetORM) -> dict[str, Any]:
    return {
        "id": change_set.id,
        "status": change_set.status,
        "revision": change_set.revision,
        "origin": change_set.origin,
        "entry_mode": change_set.entry_mode,
        "base_baseline_id": change_set.base_baseline_id,
        "title": change_set.title,
        "description": change_set.description,
        "submitted_digest": change_set.submitted_digest,
        "submitted_revision": change_set.submitted_revision,
        "submitted_at": change_set.submitted_at,
        "decided_at": change_set.decided_at,
        "decision_reason": change_set.decision_reason,
        "created_at": change_set.created_at,
        "updated_at": change_set.updated_at,
    }


def _candidate(node: WBSChangeSetNodeORM) -> WBSCandidateNodeResponse:
    return WBSCandidateNodeResponse(
        node_id=node.node_id, parent_id=node.parent_id, sort_order=node.sort_order, code=node.code, name=node.name,
        control_level=node.control_level, decomposition_kind=node.decomposition_kind, dictionary=node.dictionary,
        origin_kind=node.origin_kind,
    )


def _baseline_summary(baseline: WBSBaselineORM) -> dict[str, Any]:
    return {
        "id": baseline.id,
        "baseline_no": baseline.baseline_no,
        "parent_baseline_id": baseline.parent_baseline_id,
        "source_change_set_id": baseline.source_change_set_id,
        "tree_digest": baseline.tree_digest,
        "change_set_digest": baseline.change_set_digest,
        "node_count": baseline.node_count,
        "self_approved": baseline.self_approved,
        "applied_at": baseline.applied_at,
    }


def _baseline_node(node: WBSBaselineNodeORM) -> WBSBaselineNodeResponse:
    return WBSBaselineNodeResponse(
        node_id=node.node_id, parent_id=node.parent_id, sort_order=node.sort_order, code=node.code, name=node.name,
        control_level=node.control_level, decomposition_kind=node.decomposition_kind, dictionary=node.dictionary,
    )


def _baseline_detail(detail: BaselineDetail) -> WBSBaselineDetailResponse:
    return WBSBaselineDetailResponse(
        **_baseline_summary(detail.baseline),
        digest_verified=detail.recomputed_tree_digest == detail.baseline.tree_digest,
        nodes=[_baseline_node(node) for node in detail.nodes],
    )


@router.get("/{project_id}/wbs-governance/authority", response_model=WBSAuthorityResponse)
async def get_wbs_authority(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    repository: WBSGovernanceRepository = Depends(get_governance_repository),
) -> WBSAuthorityResponse:
    tenant_id = require_tenant_id(current_user.tenant_id)
    await _require_project(repository, project_id, tenant_id)
    authority = await repository.authority(project_id, tenant_id)
    return WBSAuthorityResponse(
        state=authority.state.value,
        display_state=authority.display_state,
        approved=authority.approved,
        draft_exists=authority.draft_exists,
        baseline_id=authority.baseline_id,
        baseline_no=authority.baseline_no,
        tree_digest=authority.tree_digest,
        applied_at=authority.applied_at,
        open_change_sets=authority.open_change_sets,
        legacy_node_count=authority.legacy_node_count,
    )


@router.get("/{project_id}/wbs-governance/change-sets", response_model=list[WBSChangeSetSummary])
async def list_wbs_change_sets(
    project_id: UUID,
    status: list[ChangeSetStatus] | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    repository: WBSGovernanceRepository = Depends(get_governance_repository),
) -> list[WBSChangeSetSummary]:
    tenant_id = require_tenant_id(current_user.tenant_id)
    await _require_project(repository, project_id, tenant_id)
    change_sets = await repository.list_change_sets(project_id, tenant_id, status)
    return [WBSChangeSetSummary(**change_set_summary(change_set)) for change_set in change_sets]


@router.get(
    "/{project_id}/wbs-governance/change-sets/{change_set_id}", response_model=WBSChangeSetDetailResponse
)
async def get_wbs_change_set(
    project_id: UUID,
    change_set_id: UUID,
    current_user: User = Depends(get_current_user),
    repository: WBSGovernanceRepository = Depends(get_governance_repository),
) -> WBSChangeSetDetailResponse:
    tenant_id = require_tenant_id(current_user.tenant_id)
    await _require_project(repository, project_id, tenant_id)
    detail = await repository.get_change_set(change_set_id, project_id, tenant_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="WBS change set not found")
    change_set = detail.change_set
    return WBSChangeSetDetailResponse(
        **change_set_summary(change_set),
        profile_refs=list(change_set.profile_refs or []),
        evidence_refs=list(change_set.evidence_refs or []),
        current_digest=repository.compute_change_set_digest(detail, change_set.revision),
        nodes=[_candidate(node) for node in detail.nodes],
        lineage=[
            WBSLineageEdgeResponse(kind=edge.kind, source_node_id=edge.source_node_id, target_node_id=edge.target_node_id)
            for edge in detail.lineage
        ],
        retirements=[
            WBSRetirementResponse(node_id=r.node_id, disposition=r.disposition, source=r.source, snapshot=r.snapshot)
            for r in detail.retirements
        ],
    )


@router.get("/{project_id}/wbs-governance/baselines", response_model=list[WBSBaselineSummary])
async def list_wbs_baselines(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    repository: WBSGovernanceRepository = Depends(get_governance_repository),
) -> list[WBSBaselineSummary]:
    tenant_id = require_tenant_id(current_user.tenant_id)
    await _require_project(repository, project_id, tenant_id)
    return [WBSBaselineSummary(**_baseline_summary(b)) for b in await repository.list_baselines(project_id, tenant_id)]


@router.get("/{project_id}/wbs-governance/baselines/as-of", response_model=WBSBaselineDetailResponse)
async def get_wbs_baseline_as_of(
    project_id: UUID,
    at: datetime = Query(description="Timezone-aware instant; the approved WBS in force at that time"),
    current_user: User = Depends(get_current_user),
    repository: WBSGovernanceRepository = Depends(get_governance_repository),
) -> WBSBaselineDetailResponse:
    if at.tzinfo is None:
        raise HTTPException(status_code=422, detail="'at' must include a timezone offset")
    tenant_id = require_tenant_id(current_user.tenant_id)
    await _require_project(repository, project_id, tenant_id)
    detail = await repository.baseline_as_of(project_id, tenant_id, at)
    if detail is None:
        raise HTTPException(status_code=404, detail="No approved WBS baseline at that time")
    return _baseline_detail(detail)


@router.get("/{project_id}/wbs-governance/baselines/{baseline_no}", response_model=WBSBaselineDetailResponse)
async def get_wbs_baseline(
    project_id: UUID,
    baseline_no: int,
    current_user: User = Depends(get_current_user),
    repository: WBSGovernanceRepository = Depends(get_governance_repository),
) -> WBSBaselineDetailResponse:
    tenant_id = require_tenant_id(current_user.tenant_id)
    await _require_project(repository, project_id, tenant_id)
    detail = await repository.get_baseline(project_id, tenant_id, baseline_no)
    if detail is None:
        raise HTTPException(status_code=404, detail="WBS baseline not found")
    return _baseline_detail(detail)


__all__ = ["WBSChangeSetSummary", "change_set_summary", "get_governance_repository", "router"]
