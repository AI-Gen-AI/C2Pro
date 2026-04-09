"""
Budget Repository Port - TASK-BCK-021
Protocol interface for Budget item persistence operations.
"""

from abc import abstractmethod
from decimal import Decimal
from typing import Protocol
from uuid import UUID


class BudgetRepository(Protocol):
    """Port for Budget item CRUD operations."""

    @abstractmethod
    async def get_by_project(self, project_id: UUID, tenant_id: UUID) -> list[dict]:
        """Get all budget items for a project."""
        ...

    @abstractmethod
    async def create(
        self,
        project_id: UUID,
        tenant_id: UUID,
        name: str,
        code: str,
        amount: Decimal,
    ) -> dict:
        """Create a new budget item."""
        ...

    @abstractmethod
    async def update(
        self,
        item_id: UUID,
        tenant_id: UUID,
        **updates,
    ) -> dict | None:
        """Update an existing budget item."""
        ...

    @abstractmethod
    async def delete(self, item_id: UUID, tenant_id: UUID) -> bool:
        """Delete a budget item."""
        ...

    @abstractmethod
    async def get_by_id(self, item_id: UUID, tenant_id: UUID) -> dict | None:
        """Get a budget item by ID."""
        ...
