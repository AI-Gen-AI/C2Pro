"""Authenticated S7 explicit Budget/Schedule row approval against ONE canonical WBS.

Every request uses tenant RLS and actor from the Clerk-authenticated principal.
These routes cannot approve the budget, dates, Health, or a second WBS tree.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.application.canonical_structured_wbs_links import (
    ApproveStructuredWBSLinkService,
    ImmutableXLSXRowReader,
    ReadStructuredWBSLinksService,
    StructuredWBSLinkError,
)
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import require_tenant_id
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.storage.factory import build_storage_service

router = APIRouter(prefix="/projects", tags=["Structured WBS links"])
_PATH = "/{project_id}/structured-wbs/canonical-links"


class ApproveStructuredWBSLinkRequest(BaseModel):
    """Client cannot supply actor or tenant; project is the authenticated URL scope."""

    model_config = ConfigDict(extra="forbid")
    family: Literal["budget", "schedule"]
    source_document_id: UUID
    source_revision_id: UUID
    expected_blob_hash: str = Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
    source_locator: str = Field(min_length=1, max_length=500)
    expected_wbs_baseline_id: UUID
    expected_wbs_node_id: UUID
    approval: Literal["APPROVE_CANONICAL_LINK"]
    idempotency_key: str = Field(min_length=8, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)


class StructuredWBSLinkApprovalResponse(BaseModel):
    event_id: UUID
    replayed: bool
    family: Literal["budget", "schedule"]
    source_document_id: UUID
    source_revision_id: UUID
    source_locator: str
    source_blob_hash: str
    wbs_baseline_id: UUID
    wbs_node_id: UUID
    authority: Literal["EXPLICIT_HUMAN_CANONICAL_LINK"] = "EXPLICIT_HUMAN_CANONICAL_LINK"
    source_assessment: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"


class CurrentStructuredWBSLinkResponse(BaseModel):
    event_id: UUID
    family: Literal["budget", "schedule"]
    approved_at: datetime
    source_document_id: UUID | None
    source_revision_id: UUID | None
    source_locator: str
    source_blob_hash: str
    wbs_baseline_id: UUID | None
    wbs_node_id: UUID | None
    state: Literal["CURRENT", "STALE_SOURCE", "STALE_WBS", "STALE_BOTH", "UNVERIFIED"]
    authority: Literal["EXPLICIT_HUMAN_CANONICAL_LINK"] = "EXPLICIT_HUMAN_CANONICAL_LINK"
    source_assessment: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"


async def get_structured_link_session(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[AsyncSession]:
    tenant = require_tenant_id(current_user.tenant_id)
    async with get_session_with_tenant(tenant) as session:
        yield session


def _reader() -> ImmutableXLSXRowReader:
    return ImmutableXLSXRowReader(
        storage=build_storage_service(), parser=ExcelFileParser()
    )


@router.post(
    _PATH,
    status_code=status.HTTP_201_CREATED,
    response_model=StructuredWBSLinkApprovalResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Human approver denied"},
        404: {"description": "Project or document not found"},
        409: {"description": "Stale source, altered XLSX row or WBS authority"},
    },
    summary="Explicitly approve one immutable Budget row or Schedule activity WBS link",
)
async def approve_structured_wbs_link(
    project_id: UUID,
    body: ApproveStructuredWBSLinkRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_structured_link_session),
) -> StructuredWBSLinkApprovalResponse:
    service = ApproveStructuredWBSLinkService(session, _reader())
    try:
        record = await service.execute(
            tenant_id=require_tenant_id(current_user.tenant_id),
            project_id=project_id, actor_user_id=current_user.id,
            family=body.family, source_document_id=body.source_document_id,
            source_revision_id=body.source_revision_id,
            expected_blob_hash=body.expected_blob_hash,
            source_locator=body.source_locator,
            expected_wbs_baseline_id=body.expected_wbs_baseline_id,
            expected_wbs_node_id=body.expected_wbs_node_id,
            approval=body.approval, idempotency_key=body.idempotency_key,
            reason=body.reason,
        )
    except StructuredWBSLinkError as exc:
        if str(exc) in {"project unavailable to tenant", "source document/revision/hash unavailable"}:
            raise HTTPException(status_code=404, detail="Project or source not found") from exc
        if str(exc) == "authenticated human approver required":
            raise HTTPException(status_code=403, detail="Human approver denied") from exc
        raise HTTPException(status_code=409, detail="Canonical source or WBS authority changed") from exc
    return StructuredWBSLinkApprovalResponse(
        event_id=record.event_id, replayed=record.replayed,
        family=record.family, source_document_id=record.source_document_id,
        source_revision_id=record.source_revision_id,
        source_locator=record.source_locator, source_blob_hash=record.source_blob_hash,
        wbs_baseline_id=record.wbs_baseline_id, wbs_node_id=record.wbs_node_id,
    )


@router.get(
    _PATH,
    response_model=list[CurrentStructuredWBSLinkResponse],
    responses={401: {"description": "Authentication required"}, 404: {"description": "Project not found"}},
    summary="Read durable approved Budget and Schedule WBS links with current authority",
)
async def list_structured_wbs_links(
    project_id: UUID,
    limit: int = Query(default=30, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_structured_link_session),
) -> list[CurrentStructuredWBSLinkResponse]:
    service = ReadStructuredWBSLinksService(session, _reader())
    try:
        entries = await service.list(
            tenant_id=require_tenant_id(current_user.tenant_id),
            project_id=project_id, limit=limit,
        )
    except StructuredWBSLinkError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    return [
        CurrentStructuredWBSLinkResponse(
            event_id=e.event_id, family=e.family, approved_at=e.approved_at,
            source_document_id=e.source_document_id,
            source_revision_id=e.source_revision_id,
            source_locator=e.source_locator, source_blob_hash=e.source_blob_hash,
            wbs_baseline_id=e.wbs_baseline_id, wbs_node_id=e.wbs_node_id,
            state=e.state,
        )
        for e in entries
    ]


__all__ = ["router", "ApproveStructuredWBSLinkRequest", "CurrentStructuredWBSLinkResponse"]
