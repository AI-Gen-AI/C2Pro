"""
Tenant Router.

API endpoints for tenant management.
Refers to TASK-REV-009.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.tenants.schemas import (
    AiSpendUpdate,
    BudgetStatusResponse,
    TenantListResponse,
    TenantResponse,
)
from src.core.tenants.service import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])


def get_tenant_service(
    db: AsyncSession = Depends(get_session),
) -> TenantService:
    """Dependency for TenantService."""
    return TenantService(db)


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Get tenant by ID",
)
async def get_tenant(
    tenant_id: UUID,
    service: TenantService = Depends(get_tenant_service),
) -> TenantResponse:
    """
    Get tenant details by ID.
    """
    tenant = await service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return TenantResponse.model_validate(tenant)


@router.get(
    "/slug/{slug}",
    response_model=TenantResponse,
    summary="Get tenant by slug",
)
async def get_tenant_by_slug(
    slug: str,
    service: TenantService = Depends(get_tenant_service),
) -> TenantResponse:
    """
    Get tenant details by slug.
    """
    tenant = await service.get_tenant_by_slug(slug)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return TenantResponse.model_validate(tenant)


@router.get(
    "",
    response_model=TenantListResponse,
    summary="List tenants",
)
async def list_tenants(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    active_only: bool = Query(default=True),
    service: TenantService = Depends(get_tenant_service),
) -> TenantListResponse:
    """
    List tenants with pagination.
    """
    tenants = await service.list_tenants(limit, offset, active_only)
    return TenantListResponse(
        tenants=[TenantResponse.model_validate(t) for t in tenants],
        total=len(tenants),
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{tenant_id}/ai-spend",
    response_model=BudgetStatusResponse,
    summary="Update AI spend",
)
async def update_ai_spend(
    tenant_id: UUID,
    payload: AiSpendUpdate,
    service: TenantService = Depends(get_tenant_service),
) -> BudgetStatusResponse:
    """
    Add amount to tenant's AI spend.
    """
    tenant = await service.update_ai_spend(tenant_id, payload.amount)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return await service.get_budget_status(tenant_id)


@router.post(
    "/{tenant_id}/ai-spend/reset",
    response_model=BudgetStatusResponse,
    summary="Reset AI spend",
)
async def reset_ai_spend(
    tenant_id: UUID,
    service: TenantService = Depends(get_tenant_service),
) -> BudgetStatusResponse:
    """
    Reset tenant's AI spend to zero.
    """
    tenant = await service.reset_ai_spend(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return await service.get_budget_status(tenant_id)


@router.get(
    "/{tenant_id}/budget",
    response_model=BudgetStatusResponse,
    summary="Get budget status",
)
async def get_budget_status(
    tenant_id: UUID,
    service: TenantService = Depends(get_tenant_service),
) -> BudgetStatusResponse:
    """
    Get AI budget status for a tenant.
    """
    return await service.get_budget_status(tenant_id)


@router.get(
    "/{tenant_id}/user-limit",
    summary="Check user limit",
)
async def check_user_limit(
    tenant_id: UUID,
    service: TenantService = Depends(get_tenant_service),
) -> dict:
    """
    Check if tenant is at user limit.
    """
    is_at_limit = await service.check_user_limit(tenant_id)
    return {
        "tenant_id": str(tenant_id),
        "is_at_limit": is_at_limit,
    }
