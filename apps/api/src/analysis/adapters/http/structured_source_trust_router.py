"""ADR-032: authenticated request / human decision for a structured-source trust candidate.

Tenant RLS session and actor come from the Clerk-authenticated principal; the client supplies
neither. The decision binds the exact candidate (id + version + hash) shown to the reviewer.
These routes cannot approve costs, dates, a WBS baseline, Health or Coherence.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.application.structured_source_trust import (
    DecideStructuredSourceTrustService,
    ImmutableStructuredSourceVerifier,
    RequestStructuredSourceTrustService,
    StructuredTrustError,
)
from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import require_tenant_id
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.storage.factory import build_storage_service

router = APIRouter(tags=["Structured source trust"])


class RequestStructuredSourceTrustBody(BaseModel):
    """The client cannot supply tenant or actor; the revision is the URL scope."""

    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)


class StructuredSourceTrustRequestResponse(BaseModel):
    artifact_id: UUID
    artifact_version: int
    artifact_hash: str
    review_row_id: UUID
    document_id: UUID
    revision_id: UUID
    family: Literal["budget", "schedule"]
    trust_state: Literal["proposed", "trusted"]
    replayed: bool
    row_count: int
    content_digest: str
    source_assessment: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"


class DecideStructuredSourceTrustBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_row_id: UUID
    artifact_id: UUID
    artifact_version: int = Field(ge=1)
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
    decision: Literal["APPROVE", "REJECT"]
    idempotency_key: str = Field(min_length=8, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)


class StructuredSourceTrustDecisionResponse(BaseModel):
    artifact_id: UUID
    artifact_version: int
    decision: Literal["APPROVE", "REJECT"]
    trust_state: Literal["trusted", "rejected"]
    review_status: str
    self_approved: bool
    independent: bool
    replayed: bool
    event_id: UUID
    authority: Literal["EXPLICIT_HUMAN_STRUCTURED_SOURCE_TRUST"] = (
        "EXPLICIT_HUMAN_STRUCTURED_SOURCE_TRUST"
    )
    source_assessment: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"


async def get_structured_trust_session(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[AsyncSession]:
    tenant = require_tenant_id(current_user.tenant_id)
    async with get_session_with_tenant(tenant) as session:
        yield session


def _verifier() -> ImmutableStructuredSourceVerifier:
    return ImmutableStructuredSourceVerifier(
        storage=build_storage_service(), parser=ExcelFileParser()
    )


def _http(exc: StructuredTrustError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail={"code": exc.code, "message": str(exc)})


@router.post(
    "/documents/{document_id}/revisions/{revision_id}/trust-candidate",
    response_model=StructuredSourceTrustRequestResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Human requester denied"},
        404: {"description": "Document or revision not found"},
        409: {"description": "Not the current revision, or an analysis artifact owns the document"},
        422: {"description": "Immutable structured source unavailable or unreadable"},
    },
    summary="Explicitly request a human trust decision for the current Budget/Schedule revision",
)
async def request_structured_source_trust(
    document_id: UUID,
    revision_id: UUID,
    body: RequestStructuredSourceTrustBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_structured_trust_session),
) -> StructuredSourceTrustRequestResponse:
    service = RequestStructuredSourceTrustService(session, _verifier())
    try:
        receipt = await service.execute(
            tenant_id=require_tenant_id(current_user.tenant_id),
            document_id=document_id,
            revision_id=revision_id,
            actor_user_id=current_user.id,
            idempotency_key=body.idempotency_key,
            reason=body.reason,
        )
    except StructuredTrustError as exc:
        raise _http(exc) from exc
    return StructuredSourceTrustRequestResponse(
        artifact_id=receipt.artifact_id,
        artifact_version=receipt.artifact_version,
        artifact_hash=receipt.artifact_hash,
        review_row_id=receipt.review_row_id,
        document_id=receipt.document_id,
        revision_id=receipt.revision_id,
        family=receipt.family,
        trust_state=receipt.trust_state,  # type: ignore[arg-type]
        replayed=receipt.replayed,
        row_count=receipt.row_count,
        content_digest=receipt.content_digest,
    )


@router.post(
    "/structured-source-trust/decisions",
    response_model=StructuredSourceTrustDecisionResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Human approver denied or separation of duties"},
        404: {"description": "Review not found"},
        409: {"description": "Stale candidate, revision or source content"},
    },
    summary="Human approve/reject the exact bound structured-source trust candidate",
)
async def decide_structured_source_trust(
    body: DecideStructuredSourceTrustBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_structured_trust_session),
) -> StructuredSourceTrustDecisionResponse:
    service = DecideStructuredSourceTrustService(session, _verifier())
    try:
        receipt = await service.execute(
            tenant_id=require_tenant_id(current_user.tenant_id),
            review_row_id=body.review_row_id,
            artifact_id=body.artifact_id,
            artifact_version=body.artifact_version,
            artifact_hash=body.artifact_hash,
            decision=body.decision,
            actor_user_id=current_user.id,
            idempotency_key=body.idempotency_key,
            reason=body.reason,
        )
    except StructuredTrustError as exc:
        raise _http(exc) from exc
    return StructuredSourceTrustDecisionResponse(
        artifact_id=receipt.artifact_id,
        artifact_version=receipt.artifact_version,
        decision=receipt.decision,
        trust_state=receipt.trust_state,  # type: ignore[arg-type]
        review_status=receipt.review_status,
        self_approved=receipt.self_approved,
        independent=receipt.independent,
        replayed=receipt.replayed,
        event_id=receipt.event_id,
    )


__all__ = [
    "router",
    "DecideStructuredSourceTrustBody",
    "RequestStructuredSourceTrustBody",
    "StructuredSourceTrustDecisionResponse",
    "StructuredSourceTrustRequestResponse",
]
