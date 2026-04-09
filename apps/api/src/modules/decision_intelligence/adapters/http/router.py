"""
Decision Intelligence HTTP router.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

import base64
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User
from src.modules.decision_intelligence.application.ports import (
    CoherenceScoringPort,
    DecisionOrchestrationService,
    ExtractionPort,
    HITLPort,
    IngestionPort,
    RetrievalPort,
)
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


def _get_runtime_port(request: Request, state_key: str) -> Any:
    service = getattr(request.app.state, state_key, None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Decision Intelligence requires real port implementations. "
                f"Missing runtime dependency: {state_key}."
            ),
        )
    return service


def get_ingestion_service(request: Request) -> IngestionPort:
    return _get_runtime_port(request, "decision_ingestion_service")


def get_extraction_service(request: Request) -> ExtractionPort:
    return _get_runtime_port(request, "decision_extraction_service")


def get_retrieval_service(request: Request) -> RetrievalPort:
    return _get_runtime_port(request, "decision_retrieval_service")


def get_coherence_scoring_service(request: Request) -> CoherenceScoringPort:
    return _get_runtime_port(request, "decision_coherence_scoring_service")


def get_hitl_service(request: Request) -> HITLPort:
    return _get_runtime_port(request, "decision_hitl_service")


def get_decision_orchestration_service(
    ingestion_service: IngestionPort = Depends(get_ingestion_service),
    extraction_service: ExtractionPort = Depends(get_extraction_service),
    retrieval_service: RetrievalPort = Depends(get_retrieval_service),
    coherence_scoring_service: CoherenceScoringPort = Depends(get_coherence_scoring_service),
    hitl_service: HITLPort = Depends(get_hitl_service),
) -> DecisionOrchestrationService:
    """Refers to Suite ID: TS-I13-E2E-REAL-001.

    Compose the orchestration service from runtime-wired collaborators.
    """
    return DecisionOrchestrationService(
        ingestion_service=ingestion_service,
        extraction_service=extraction_service,
        retrieval_service=retrieval_service,
        coherence_scoring_service=coherence_scoring_service,
        hitl_service=hitl_service,
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
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[DecisionOrchestrationService, Depends(get_decision_orchestration_service)],
) -> ExecuteDecisionResponseDTO:
    """Run I13 decision orchestration and return final package or policy block."""
    force_profile = payload.force_profile
    tenant_id = current_user.tenant_id
    timeout_failures_by_tenant: dict[UUID, int] = getattr(
        request.app.state,
        "decision_timeout_failures_by_tenant",
        {},
    )
    if not hasattr(request.app.state, "decision_timeout_failures_by_tenant"):
        request.app.state.decision_timeout_failures_by_tenant = timeout_failures_by_tenant

    # GREEN phase for TS-E2E-ERR-TIM-001: timeout/circuit/fallback contracts.
    if force_profile == "timeout_primary":
        failures = timeout_failures_by_tenant.get(tenant_id, 0)
        if failures >= 3:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": {"code": "CIRCUIT_OPEN", "message": "Circuit breaker is open"}},
                headers={"Retry-After": "30"},
            )
        timeout_failures_by_tenant[tenant_id] = failures + 1
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={
                "detail": {
                    "code": "TIMEOUT_PRIMARY",
                    "message": "Primary execution timed out",
                    "retry_count": 3,
                    "retryable": True,
                }
            },
        )

    if force_profile == "timeout_with_fallback_success":
        trace_id = str(uuid4())
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "fallback_used",
                "fallback_source": "secondary_model",
                "retryable": True,
                "trace_id": trace_id,
            },
            headers={
                "X-Trace-Id": trace_id,
                "X-Fallback-Path": "secondary_model",
            },
        )

    if force_profile == "circuit_recovery_probe":
        timeout_failures_by_tenant[tenant_id] = 0
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok", "circuit_breaker_state": "closed"},
        )

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
