"""
Tenant Service.

Business logic for tenant management.
Refers to TASK-REV-009 and Test Suite ID: TS-E2E-SEC-TNT-001.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import Tenant

logger = structlog.get_logger()


def _utcnow_naive() -> datetime:
    """Return UTC now normalized to a naive timestamp for legacy tenant columns."""
    return datetime.now(UTC).replace(tzinfo=None)


async def get_tenant_by_id(db: AsyncSession, tenant_id: UUID) -> Tenant | None:
    """
    Obtiene un tenant por ID.
    """
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    return result.scalar_one_or_none()


async def get_tenant_by_slug(db: AsyncSession, slug: str) -> Tenant | None:
    """
    Obtiene un tenant por slug.
    """
    result = await db.execute(
        select(Tenant).where(Tenant.slug == slug)
    )
    return result.scalar_one_or_none()


async def list_tenants(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    active_only: bool = True,
) -> list[Tenant]:
    """
    Lista tenants con paginación.
    """
    query = select(Tenant)
    if active_only:
        query = query.where(Tenant.is_active.is_(True))
    query = query.order_by(Tenant.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


class TenantService:
    """
    Service for tenant management operations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_tenant(self, tenant_id: UUID) -> Tenant | None:
        """Get tenant by ID."""
        return await get_tenant_by_id(self.db, tenant_id)

    async def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        """Get tenant by slug."""
        return await get_tenant_by_slug(self.db, slug)

    async def list_tenants(
        self,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True,
    ) -> list[Tenant]:
        """List tenants with pagination."""
        return await list_tenants(self.db, limit, offset, active_only)

    async def update_ai_spend(
        self,
        tenant_id: UUID,
        amount: float,
    ) -> Tenant | None:
        """
        Update AI spend for a tenant.

        Args:
            tenant_id: Tenant UUID
            amount: Amount to add to current spend

        Returns:
            Updated tenant or None if not found
        """
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None

        tenant.ai_spend_current += amount
        await self.db.flush()
        return tenant

    async def reset_ai_spend(self, tenant_id: UUID) -> Tenant | None:
        """
        Reset AI spend to zero.

        Args:
            tenant_id: Tenant UUID

        Returns:
            Updated tenant or None if not found
        """
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return None

        tenant.ai_spend_current = 0.0
        tenant.ai_spend_last_reset = _utcnow_naive()
        await self.db.flush()
        return tenant

    async def check_user_limit(self, tenant_id: UUID) -> bool:
        """
        Check if tenant is at user limit.

        Args:
            tenant_id: Tenant UUID

        Returns:
            True if at limit, False otherwise
        """
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return True
        return tenant.is_at_user_limit

    async def get_budget_status(self, tenant_id: UUID) -> dict:
        """
        Get budget status for a tenant.

        Args:
            tenant_id: Tenant UUID

        Returns:
            Dict with budget info
        """
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return {"error": "Tenant not found"}

        return {
            "tenant_id": str(tenant.id),
            "monthly_budget": tenant.ai_budget_monthly,
            "current_spend": tenant.ai_spend_current,
            "remaining": max(0, tenant.ai_budget_monthly - tenant.ai_spend_current),
            "usage_percentage": tenant.budget_usage_percentage,
            "is_over_budget": tenant.is_over_budget,
            "last_reset": tenant.ai_spend_last_reset.isoformat() if tenant.ai_spend_last_reset else None,
        }
