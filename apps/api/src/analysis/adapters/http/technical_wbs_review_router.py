"""ACC-01 S7 authenticated technical-WBS human review (AUDIT ONLY).

This route records a review decision; it NEVER creates a canonical WBS link,
approves technical compliance, or grants document trust. An active Clerk-backed
user is bound from the authenticated principal, NOT from the request body.

This route is a separately gated draft integration of #1114 -> #1117 -> #1119.
No production deployment until those dependencies and tenant E2E have passed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from src.analysis.application.record_technical_wbs_review import (
    ImmutableDocxTechnicalTextReader,
    RecordTechnicalWBSReviewService,
    TechnicalMappingDecision,
    TechnicalMappingReviewError,
)
from src.analysis.domain.technical_wbs_link_candidate import (
    TechnicalWBSLinkCandidateError,
)
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import require_tenant_id
from src.documents.adapters.storage.factory import build_storage_service
from src.documents.application.document_source import RevisionSourceError

router = APIRouter(prefix="/projects", tags=["Technical WBS review"])

_PREFIX = "/{project_id}/technical-wbs/reviews"


class TechnicalWBSReviewRequest(BaseModel):
    """Never accept tenant, actor, project, or link-approval authority in JSON."""

    model_config = ConfigDict(extra="forbid")

    clause_id: UUID
    expected_revision_id: UUID
    expected_blob_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    expected_wbs_baseline_id: UUID
    proposed_wbs_node_id: UUID
    decision: TechnicalMappingDecision
    idempotency_key: str = Field(min_length=8, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)


class TechnicalWBSReviewResponse(BaseModel):
    event_id: UUID
    decision: TechnicalMappingDecision
    replayed: bool
    technical_document_id: UUID
    technical_revision_id: UUID
    source_clause_id: UUID
    source_section: str
    source_start_offset: int
    source_end_offset: int
    proposed_wbs_baseline_id: UUID
    proposed_wbs_node_id: UUID
    state: Literal["HUMAN_REVIEW_REQUIRED"] = "HUMAN_REVIEW_REQUIRED"
    authority: Literal["AUDIT_ONLY_NOT_CANONICAL_LINK"] = "AUDIT_ONLY_NOT_CANONICAL_LINK"
    technical_assessment: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"
    approved_canonical_link: Literal[False] = False


async def get_technical_wbs_review_service(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[RecordTechnicalWBSReviewService]:
    """One authenticated tenant-scoped transaction; rollback on any failure."""
    tenant = require_tenant_id(current_user.tenant_id)
    async with get_session_with_tenant(tenant) as session:
        yield RecordTechnicalWBSReviewService(
            session=session,
            source_reader=ImmutableDocxTechnicalTextReader(build_storage_service()),
        )


@router.post(
    _PREFIX,
    response_model=TechnicalWBSReviewResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Reviewer access denied"},
        404: {"description": "Project or source not found"},
        409: {"description": "Stale revision, WBS or conflicting review"},
    },
)
async def record_technical_wbs_review(
    project_id: UUID,
    body: TechnicalWBSReviewRequest,
    current_user: User = Depends(get_current_user),
    service: RecordTechnicalWBSReviewService = Depends(get_technical_wbs_review_service),
) -> TechnicalWBSReviewResponse:
    """Explicit human review only; source and WBS authority rechecked by service."""
    tenant = require_tenant_id(current_user.tenant_id)
    try:
        result = await service.execute(
            tenant_id=tenant,
            project_id=project_id,
            actor_user_id=current_user.id,
            clause_id=body.clause_id,
            expected_revision_id=body.expected_revision_id,
            expected_blob_hash=body.expected_blob_hash,
            expected_wbs_baseline_id=body.expected_wbs_baseline_id,
            proposed_wbs_node_id=body.proposed_wbs_node_id,
            decision=body.decision,
            idempotency_key=body.idempotency_key,
            reason=body.reason,
        )
    except TechnicalMappingReviewError as exc:
        message = str(exc)
        if message in {"project unavailable to this tenant", "technical clause or immutable revision not found"}:
            raise HTTPException(status_code=404, detail="Project or source not found") from exc
        if message == "authenticated human reviewer required":
            raise HTTPException(status_code=403, detail="Reviewer access denied") from exc
        raise HTTPException(status_code=409, detail="Review source or authority changed") from exc
    except (TechnicalWBSLinkCandidateError, RevisionSourceError) as exc:
        raise HTTPException(status_code=409, detail="Review source or authority changed") from exc

    c = result.candidate
    return TechnicalWBSReviewResponse(
        event_id=result.event_id,
        decision=result.decision,
        replayed=result.replayed,
        technical_document_id=c.technical_document_id,
        technical_revision_id=c.technical_revision_id,
        source_clause_id=c.source_clause_id,
        source_section=c.source_section,
        source_start_offset=c.source_start_offset,
        source_end_offset=c.source_end_offset,
        proposed_wbs_baseline_id=c.proposed_wbs_baseline_id,
        proposed_wbs_node_id=c.proposed_wbs_node_id,
    )
