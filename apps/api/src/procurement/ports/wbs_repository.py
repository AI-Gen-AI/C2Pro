"""
Repository port (interface) for WBS operations.
"""
from abc import ABC, abstractmethod
from uuid import UUID

from src.core.tenants.types import TenantId
from src.procurement.domain.models import WBSItem


class IWBSRepository(ABC):
    """
    Repository interface for WBS Item operations.
    Implementations must be provided by adapters (e.g., SQLAlchemy).
    """

    @abstractmethod
    async def create(self, tenant_id: TenantId, wbs_item: WBSItem) -> WBSItem:
        """
        Create a new WBS item.

        Args:
            wbs_item: The WBS item to create

        Returns:
            The created WBS item with ID
        """
        pass

    @abstractmethod
    async def get_by_id(self, wbs_id: UUID, tenant_id: TenantId) -> WBSItem | None:
        """
        Retrieve a WBS item by ID.

        Args:
            wbs_id: The WBS item ID
            tenant_id: The tenant ID for isolation

        Returns:
            The WBS item if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_project(self, project_id: UUID, tenant_id: TenantId) -> list[WBSItem]:
        """
        Retrieve all WBS items for a project.

        Args:
            project_id: The project ID
            tenant_id: The tenant ID for isolation

        Returns:
            List of WBS items
        """
        pass

    @abstractmethod
    async def get_by_code(self, project_id: UUID, wbs_code: str, tenant_id: TenantId) -> WBSItem | None:
        """
        Retrieve a WBS item by its code within a project.

        Args:
            project_id: The project ID
            wbs_code: The WBS code (e.g., '1.2.3')
            tenant_id: The tenant ID for isolation

        Returns:
            The WBS item if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_children(self, parent_id: UUID, tenant_id: TenantId) -> list[WBSItem]:
        """
        Retrieve all children of a WBS item.

        Args:
            parent_id: The parent WBS item ID
            tenant_id: The tenant ID for isolation

        Returns:
            List of child WBS items
        """
        pass

    @abstractmethod
    async def get_tree(self, project_id: UUID, tenant_id: TenantId) -> list[WBSItem]:
        """
        Retrieve the complete WBS tree for a project with hierarchy.

        Args:
            project_id: The project ID
            tenant_id: The tenant ID for isolation

        Returns:
            List of root WBS items with children loaded recursively
        """
        pass

    @abstractmethod
    async def update(self, wbs_id: UUID, wbs_item: WBSItem, tenant_id: TenantId) -> WBSItem | None:
        """
        Update an existing WBS item.

        Args:
            wbs_id: The WBS item ID to update
            wbs_item: The WBS item data
            tenant_id: The tenant ID for isolation

        Returns:
            The updated WBS item if found, None otherwise
        """
        pass

    @abstractmethod
    async def delete(self, wbs_id: UUID, tenant_id: TenantId) -> bool:
        """
        Delete a WBS item and its children (cascade).

        Args:
            wbs_id: The WBS item ID to delete
            tenant_id: The tenant ID for isolation

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def bulk_create(self, wbs_items: list[WBSItem], tenant_id: TenantId) -> list[WBSItem]:
        """
        Create multiple WBS items at once (used for AI generation).

        Args:
            wbs_items: List of WBS items to create
            tenant_id: The tenant ID for isolation

        Returns:
            List of created WBS items with IDs
        """
        pass

    @abstractmethod
    async def replace_for_source_document(
        self,
        *,
        project_id: UUID,
        source_document_id: UUID,
        wbs_items: list[WBSItem],
        tenant_id: TenantId,
    ) -> list[WBSItem]:
        """
        Replace all WBS rows produced by one parsed source document.

        Idempotent per source document: deletes the rows previously produced by
        ``source_document_id`` for the project, then inserts the new set. Unlike
        the BOM equivalent this MUST NOT delete NULL-source rows, which may be
        manually created or AI-generated WBS items.

        Args:
            project_id: The project the WBS items belong to
            source_document_id: The parsed schedule document producing these rows
            wbs_items: The fresh WBS items to persist
            tenant_id: The tenant ID for isolation

        Returns:
            List of persisted WBS items
        """
        pass
