"""
I9 Procurement Planning HTTP Router
Test Suite ID: TS-I9-PROC-HTTP-001
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from src.modules.procurement.application.ports import (
    PlanningDecision,
    ProcurementPlanningService,
)


router = APIRouter(prefix="/procurement", tags=["procurement"])


class ProcurementPlanningRequest(BaseModel):
    """Request DTO for procurement planning."""

    project_id: UUID
    required_on_site: date


def get_procurement_planning_service() -> ProcurementPlanningService:
    """Dependency provider for the procurement planning service."""
    return ProcurementPlanningService()


@router.post("/planning", response_model=PlanningDecision)
async def build_procurement_plan(
    payload: ProcurementPlanningRequest,
    service: Annotated[ProcurementPlanningService, Depends(get_procurement_planning_service)],
    tenant_id_header: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
) -> PlanningDecision:
    """Build a tenant-scoped procurement plan for a project snapshot."""
    if not tenant_id_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing tenant context",
        )

    try:
        tenant_id = UUID(tenant_id_header)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant context",
        ) from exc

    try:
        return await service.build_procurement_plan(
            project_id=payload.project_id,
            tenant_id=tenant_id,
            required_on_site=payload.required_on_site,
        )
    except ValueError as exc:
        if "cross-tenant" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            ) from exc
        raise
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Procurement planning service unavailable",
        ) from exc
