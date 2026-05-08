"""
SQLAlchemy Tenant Repository.

Implements ITenantRepository port for the alerts module.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.alerts.application.ports.tenant_repository import ITenantRepository
from src.core.auth.models import Tenant


class SqlAlchemyTenantRepository(ITenantRepository):
    """SQLAlchemy implementation of ITenantRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        """Get tenant by ID."""
        return await self._session.get(Tenant, tenant_id)

    async def update_settings(self, tenant_id: UUID, settings: dict[str, Any]) -> Tenant | None:
        """Update tenant settings."""
        tenant = await self._session.get(Tenant, tenant_id)
        if tenant:
            tenant.settings = settings
            # We don't commit here, the use case calls commit()
        return tenant

    async def commit(self) -> None:
        """Commit changes."""
        await self._session.commit()
