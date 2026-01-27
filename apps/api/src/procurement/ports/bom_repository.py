"""
Repository port (interface) for BOM operations.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.procurement.domain.models import BOMItem, BOMCategory, ProcurementStatus


class IBOMRepository(ABC):
    """
    Repository interface for BOM Item operations.
    Implementations must be provided by adapters (e.g., SQLAlchemy).
    """

    @abstractmethod
    async def create(self, bom_item: BOMItem) -> BOMItem:
        """
        Create a new BOM item.

        Args:
            bom_item: The BOM item to create

        Returns:
            The created BOM item with ID
        """
        pass

    @abstractmethod
    async def get_by_id(self, bom_id: UUID, tenant_id: UUID) -> Optional[BOMItem]:
        """
        Retrieve a BOM item by ID.

        Args:
            bom_id: The BOM item ID
            tenant_id: The tenant ID for isolation

        Returns:
            The BOM item if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_project(self, project_id: UUID, tenant_id: UUID) -> List[BOMItem]:
        """
        Retrieve all BOM items for a project.

        Args:
            project_id: The project ID
            tenant_id: The tenant ID for isolation

        Returns:
            List of BOM items
        """
        pass

    @abstractmethod
    async def get_by_wbs_item(self, wbs_item_id: UUID, tenant_id: UUID) -> List[BOMItem]:
        """
        Retrieve all BOM items for a specific WBS item.

        Args:
            wbs_item_id: The WBS item ID
            tenant_id: The tenant ID for isolation

        Returns:
            List of BOM items
        """
        pass

    @abstractmethod
    async def get_by_category(
        self, project_id: UUID, category: BOMCategory, tenant_id: UUID
    ) -> List[BOMItem]:
        """
        Retrieve all BOM items of a specific category in a project.

        Args:
            project_id: The project ID
            category: The BOM category
            tenant_id: The tenant ID for isolation

        Returns:
            List of BOM items
        """
        pass

    @abstractmethod
    async def get_by_status(
        self, project_id: UUID, status: ProcurementStatus, tenant_id: UUID
    ) -> List[BOMItem]:
        """
        Retrieve all BOM items with a specific procurement status in a project.

        Args:
            project_id: The project ID
            status: The procurement status
            tenant_id: The tenant ID for isolation

        Returns:
            List of BOM items
        """
        pass

    @abstractmethod
    async def update(self, bom_id: UUID, bom_item: BOMItem, tenant_id: UUID) -> Optional[BOMItem]:
        """
        Update an existing BOM item.

        Args:
            bom_id: The BOM item ID to update
            bom_item: The BOM item data
            tenant_id: The tenant ID for isolation

        Returns:
            The updated BOM item if found, None otherwise
        """
        pass

    @abstractmethod
    async def update_status(
        self, bom_id: UUID, status: ProcurementStatus, tenant_id: UUID
    ) -> Optional[BOMItem]:
        """
        Update the procurement status of a BOM item.

        Args:
            bom_id: The BOM item ID to update
            status: The new procurement status
            tenant_id: The tenant ID for isolation

        Returns:
            The updated BOM item if found, None otherwise
        """
        pass

    @abstractmethod
    async def delete(self, bom_id: UUID, tenant_id: UUID) -> bool:
        """
        Delete a BOM item.

        Args:
            bom_id: The BOM item ID to delete
            tenant_id: The tenant ID for isolation

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def bulk_create(self, bom_items: List[BOMItem]) -> List[BOMItem]:
        """
        Create multiple BOM items at once (used for AI generation).

        Args:
            bom_items: List of BOM items to create

        Returns:
            List of created BOM items with IDs
        """
        pass
