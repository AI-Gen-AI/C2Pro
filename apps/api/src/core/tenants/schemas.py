"""
Tenant Schemas.

Pydantic models for tenant API requests/responses.
Refers to TASK-REV-009.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TenantBase(BaseModel):
    """Base tenant schema."""
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)


class TenantCreate(TenantBase):
    """Schema for creating a tenant."""
    pass


class TenantUpdate(BaseModel):
    """Schema for updating a tenant."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    settings: Optional[dict] = None
    is_active: Optional[bool] = None


class TenantResponse(TenantBase):
    """Schema for tenant response."""
    id: UUID
    subscription_plan: str
    subscription_status: str
    ai_budget_monthly: float
    ai_spend_current: float
    max_projects: int
    max_users: int
    max_storage_gb: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TenantListResponse(BaseModel):
    """Schema for tenant list response."""
    tenants: list[TenantResponse]
    total: int
    limit: int
    offset: int


class BudgetStatusResponse(BaseModel):
    """Schema for budget status response."""
    tenant_id: str
    monthly_budget: float
    current_spend: float
    remaining: float
    usage_percentage: float
    is_over_budget: bool
    last_reset: Optional[str] = None


class AiSpendUpdate(BaseModel):
    """Schema for updating AI spend."""
    amount: float = Field(..., description="Amount to add to current spend")
