"""
Decision Intelligence HTTP router.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

import base64
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.modules.decision_intelligence.application.ports import DecisionOrchestrationService
from src.modules.decision_intelligence.domain.exceptions import FinalizationBlockedError


router = APIRouter(prefix="/decision-intelligence", tags=["decision-intelligence"])


class ReviewDecisionDTO(BaseModel):
    """Refers to Suite ID: TS-I13-E2E-REAL-001."""

    item_id: UUID
    reviewer_id: UUID
    reviewer_name: str
    action: Literal["approve", "reject"] = "approve"


class ExecuteDecisionRequestDTO(BaseModel):
    """Refers to Suite ID: TS-I13-E2E-REAL-001."""

    project_id: UUID
    document_bytes_b64: str = Field(min_length=1)
    force_profile: str | None = None
    review_decision: ReviewDecisionDTO | None = None
    require_sign_off: bool = False


class ExecuteDecisionResponseDTO(BaseModel):
    """Refers to Suite ID: TS-I13-E2E-REAL-001."""

    coherence_score: int
    risks: list[dict[str, str]]
    evidence_links: list[str]
    citations: list[str]
    approved_by: str | None = None
    approved_at: str | None = None


def get_decision_orchestration_service() -> DecisionOrchestrationService:
    """Refers to Suite ID: TS-I13-E2E-REAL-001.

    TODO: Wire real port implementations once they exist.
    """
    raise NotImplementedError(
        "DecisionOrchestrationService requires real port implementations. "
        "Wire IngestionPort, ExtractionPort, RetrievalPort, "
        "CoherenceScoringPort and HITLPort before enabling this endpoint."
    )


@router.post(
    "/execute",
    response_model=ExecuteDecisionResponseDTO,
    status_code=200,
    summary="Execute Decision Intelligence Flow",
    description=(
        "Runs I13 orchestration and returns a final decision package when gates pass. "
        "Returns 409 when finalization is blocked by HITL/citation/sign-off policy."
    ),
    responses={
        200: {"description": "Decision package generated"},
        409: {"description": "Finalization blocked by policy gates"},
        422: {"description": "Invalid request payload"},
    },
)
async def execute_decision_intelligence(
    payload: ExecuteDecisionRequestDTO,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[DecisionOrchestrationService, Depends(get_decision_orchestration_service)],
) -> ExecuteDecisionResponseDTO:
    """Run I13 decision orchestration and return final package or policy block."""
    try:
        document_bytes = base64.b64decode(payload.document_bytes_b64, validate=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid base64 payload",
        ) from exc

    try:
        result = await service.execute_full_decision_flow(
            document_bytes=document_bytes,
            tenant_id=current_user.tenant_id,
            project_id=payload.project_id,
            review_decision=payload.review_decision.model_dump() if payload.review_decision else None,
            require_sign_off=payload.require_sign_off,
            force_profile=payload.force_profile,
        )
    except FinalizationBlockedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return ExecuteDecisionResponseDTO(
        coherence_score=result.coherence_score,
        risks=result.risks,
        evidence_links=result.evidence_links,
        citations=result.citations,
        approved_by=result.approved_by,
        approved_at=result.approved_at,
    )
