"""
Tenant Repository Port.

Interface for tenant operations needed by alerts module.
"""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from src.core.auth.models import Tenant


class ITenantRepository(Protocol):
    """Repository interface for Tenant operations."""

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        """Get tenant by ID."""
        ...

    async def update_settings(self, tenant_id: UUID, settings: dict[str, Any]) -> Tenant | None:
        """Update tenant settings."""
        ...

    async def commit(self) -> None:
        """Commit changes."""
        ...
