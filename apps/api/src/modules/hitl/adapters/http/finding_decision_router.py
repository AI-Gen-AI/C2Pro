"""S5: finding-by-finding human decisions on a pending analysis review.

Both routes act on ONE review row of the signed-in tenant, in the request's own RLS transaction. The reviewer is the
authenticated human (never a body field) and a decision is PROVISIONAL: it appends to the ledger and never approves,
rejects or trusts the candidate -- the final approval stays a separate act through ``/hitl/queue/{id}/approve|reject``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.core.database import get_session_with_tenant
from src.core.tenants.types import require_tenant_id
from src.modules.hitl.adapters.persistence.finding_decision_writer import (
    FindingDecisionIdempotencyConflict,
    FindingDecisionIdentityError,
    FindingDecisionRevisionConflict,
)
from src.modules.hitl.application.finding_review_authorization import (
    FindingDecisionSubmission,
    FindingReviewerNotAuthorized,
    authorize_finding_reviewer,
)
from src.modules.hitl.application.project_review_authorization import (
    ProjectAuthorizationDenied,
    ProjectReviewAuthorizer,
)
from src.modules.hitl.application.record_finding_decision_use_case import (
    RecordFindingDecisionUseCase,
)
from src.modules.hitl.application.review_findings_view import (
    FindingDecisionRecord,
    ReviewFindingsUnavailable,
    ReviewFindingsViewService,
)

router = APIRouter(prefix="/hitl", tags=["HITL findings"])

_NO_REVIEW = ("no actionable review for tenant", "missing active tenant-scoped review row")


class FindingDecisionEntry(BaseModel):
    event_id: UUID
    ledger_revision: int
    action: Literal["CONFIRMED", "CORRECTION_PROPOSED", "DISMISSED", "NEEDS_INFO"]
    reason: str | None = None
    proposed_text: str | None = None
    reviewer_id: str
    recorded_at: datetime | None = None


class ReviewFindingResponse(BaseModel):
    ordinal: int
    source_item_id: str
    finding_id: str
    risk: dict[str, Any]
    current: FindingDecisionEntry | None = None
    history: list[FindingDecisionEntry]


class ReviewFindingsResponse(BaseModel):
    review_row_id: UUID
    artifact_id: UUID
    artifact_version: int
    artifact_hash: str
    document_revision_id: UUID
    generation: int
    fencing_token: int
    ledger_revision: int
    findings: list[ReviewFindingResponse]
    # Said by the API so no screen can imply more: the ledger records intent, nothing else.
    decision_scope: Literal["PROVISIONAL_REVIEWER_INTENT"] = "PROVISIONAL_REVIEWER_INTENT"
    final_approval: Literal["SEPARATE_ACT"] = "SEPARATE_ACT"


class ReviewCapabilitiesResponse(BaseModel):
    """What the CALLER may do on this review's project. Read-only and advisory: the server re-validates every action.

    Never lists other people's grants. ``mode`` is the tenant's rollout mode; ``off`` / ``audit`` are transitional and
    report the legacy rule (nothing is hidden from a human of the tenant), ``enforce`` reports explicit grants only.
    """

    review_row_id: UUID
    mode: Literal["off", "audit", "enforce"]
    read_review: bool
    review_finding: bool
    approve_candidate: bool


class FindingDecisionReceipt(BaseModel):
    event_id: UUID
    ledger_revision: int
    replayed: bool
    decision_scope: Literal["PROVISIONAL_REVIEWER_INTENT"] = "PROVISIONAL_REVIEWER_INTENT"


async def get_finding_session(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[AsyncSession]:
    async with get_session_with_tenant(require_tenant_id(current_user.tenant_id)) as session:
        yield session


def _entry(record: FindingDecisionRecord) -> FindingDecisionEntry:
    return FindingDecisionEntry(
        event_id=record.event_id,
        ledger_revision=record.ledger_revision,
        action=record.action,  # type: ignore[arg-type]
        reason=record.reason,
        proposed_text=record.proposed_text,
        reviewer_id=record.reviewer_id,
        recorded_at=record.recorded_at,
    )


def _refusal(code: str, message: str, http_status: int) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message})


def _project_denied(exc: ProjectAuthorizationDenied) -> HTTPException:
    """403 when the actor can already see the project's review (it lacks THIS capability); 404 when it cannot."""
    if exc.visible:
        return _refusal(
            "project_capability_required",
            f"{exc.capability.value} on this review's project is required",
            status.HTTP_403_FORBIDDEN,
        )
    return _refusal("review_unavailable", "no actionable review for tenant", status.HTTP_404_NOT_FOUND)


@router.get(
    "/reviews/{review_row_id}/findings",
    response_model=ReviewFindingsResponse,
    responses={
        403: {"description": "An active human reviewer of the tenant, holding the project capability, is required"},
        404: {"description": "No actionable analysis review of this tenant"},
    },
    summary="List the findings of a pending analysis review with their provisional decisions",
)
async def list_review_findings(
    review_row_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_finding_session),
) -> ReviewFindingsResponse:
    try:
        view = await ReviewFindingsViewService(session).execute(
            tenant_id=require_tenant_id(current_user.tenant_id),
            user=current_user,
            review_row_id=review_row_id,
        )
    except FindingReviewerNotAuthorized as exc:
        raise _refusal("reviewer_not_authorized", str(exc), status.HTTP_403_FORBIDDEN) from exc
    except ProjectAuthorizationDenied as exc:
        raise _project_denied(exc) from exc
    except ReviewFindingsUnavailable as exc:
        raise _refusal("review_unavailable", str(exc), status.HTTP_404_NOT_FOUND) from exc
    return ReviewFindingsResponse(
        review_row_id=view.review_row_id,
        artifact_id=view.artifact_id,
        artifact_version=view.artifact_version,
        artifact_hash=view.artifact_hash,
        document_revision_id=view.document_revision_id,
        generation=view.generation,
        fencing_token=view.fencing_token,
        ledger_revision=view.ledger_revision,
        findings=[
            ReviewFindingResponse(
                ordinal=f.ordinal,
                source_item_id=f.source_item_id,
                finding_id=f.finding_id,
                risk=f.risk,
                current=_entry(f.current) if f.current else None,
                history=[_entry(h) for h in f.history],
            )
            for f in view.findings
        ],
    )


@router.post(
    "/reviews/{review_row_id}/findings/decisions",
    response_model=FindingDecisionReceipt,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "An active human reviewer of the tenant, holding the project capability, is required"},
        404: {"description": "No actionable analysis review of this tenant"},
        409: {"description": "Stale candidate/authority/ledger revision, unbound finding or conflicting replay"},
    },
    summary="Record ONE provisional decision on ONE finding of a pending analysis review",
)
async def record_finding_decision(
    review_row_id: UUID,
    submission: FindingDecisionSubmission,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_finding_session),
) -> FindingDecisionReceipt:
    try:
        receipt = await RecordFindingDecisionUseCase(session).execute(
            tenant_id=require_tenant_id(current_user.tenant_id),
            user=current_user,
            review_row_id=review_row_id,
            submission=submission,
        )
    except FindingReviewerNotAuthorized as exc:
        raise _refusal("reviewer_not_authorized", str(exc), status.HTTP_403_FORBIDDEN) from exc
    except ProjectAuthorizationDenied as exc:
        raise _project_denied(exc) from exc
    except FindingDecisionIdentityError as exc:
        if str(exc) in _NO_REVIEW:
            raise _refusal("review_unavailable", str(exc), status.HTTP_404_NOT_FOUND) from exc
        raise _refusal("stale_or_unbound_candidate", str(exc), status.HTTP_409_CONFLICT) from exc
    except FindingDecisionRevisionConflict as exc:
        raise _refusal("stale_ledger_revision", str(exc), status.HTTP_409_CONFLICT) from exc
    except FindingDecisionIdempotencyConflict as exc:
        raise _refusal("idempotency_conflict", str(exc), status.HTTP_409_CONFLICT) from exc
    except DBAPIError as exc:
        # The ledger's own guard (exact pending review, live authority, ledger revision) refused the append.
        raise _refusal(
            "ledger_guard_refused",
            "The decision no longer matches the pending review; refresh and decide again.",
            status.HTTP_409_CONFLICT,
        ) from exc
    return FindingDecisionReceipt(
        event_id=receipt.event_id, ledger_revision=receipt.ledger_revision, replayed=receipt.replayed
    )


@router.get(
    "/reviews/{review_row_id}/capabilities",
    response_model=ReviewCapabilitiesResponse,
    responses={
        403: {"description": "An active human reviewer of the tenant is required"},
        404: {"description": "No review of this tenant visible to the caller"},
    },
    summary="What the signed-in user may do on the project of this review (advisory; every action re-validates)",
)
async def get_review_capabilities(
    review_row_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_finding_session),
) -> ReviewCapabilitiesResponse:
    tenant_id = require_tenant_id(current_user.tenant_id)
    try:
        actor = authorize_finding_reviewer(current_user, tenant_id=tenant_id)
        caps = await ProjectReviewAuthorizer(session).capabilities_for_review(
            tenant_id=actor.tenant_id, user_id=actor.reviewer_id, review_row_id=review_row_id
        )
    except FindingReviewerNotAuthorized as exc:
        raise _refusal("reviewer_not_authorized", str(exc), status.HTTP_403_FORBIDDEN) from exc
    except ProjectAuthorizationDenied as exc:
        raise _project_denied(exc) from exc
    return ReviewCapabilitiesResponse(
        review_row_id=review_row_id,
        mode=caps.mode.value,
        read_review=caps.read_review,
        review_finding=caps.review_finding,
        approve_candidate=caps.approve_candidate,
    )
