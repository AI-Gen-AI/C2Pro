"""
Budget Repository Port - TASK-BCK-021
Protocol interface for Budget item persistence operations.
"""

from abc import abstractmethod
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from src.core.tenants.types import TenantId


class BudgetRepository(Protocol):
    """Port for Budget item CRUD operations."""

    @abstractmethod
    async def get_by_project(
        self, project_id: UUID, tenant_id: TenantId
    ) -> list[dict[str, object]]:
        """Get all budget items for a project."""
        ...

    @abstractmethod
    async def create(
        self,
        project_id: UUID,
        tenant_id: TenantId,
        name: str,
        code: str,
        amount: Decimal,
    ) -> dict[str, object]:
        """Create a new budget item."""
        ...

    @abstractmethod
    async def update(
        self,
        item_id: UUID,
        tenant_id: TenantId,
        **updates: object,
    ) -> dict[str, object] | None:
        """Update an existing budget item."""
        ...

    @abstractmethod
    async def delete(self, item_id: UUID, tenant_id: TenantId) -> bool:
        """Delete a budget item."""
        ...

    @abstractmethod
    async def get_by_id(self, item_id: UUID, tenant_id: TenantId) -> dict[str, object] | None:
        """Get a budget item by ID."""
        ...

    @abstractmethod
    async def get_total_spent_by_project(self, project_id: UUID, tenant_id: TenantId) -> Decimal:
        """Get the total spent amount for all WBS items in a project."""
        ...
