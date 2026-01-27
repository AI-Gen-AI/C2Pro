"""
Use cases for WBS operations.
"""
from typing import List, Optional
from uuid import UUID

from src.procurement.ports.wbs_repository import IWBSRepository
from src.procurement.domain.models import WBSItem
from src.procurement.application.dtos import WBSItemCreate, WBSItemUpdate


class CreateWBSItemUseCase:
    """Use case for creating a new WBS item."""

    def __init__(self, wbs_repository: IWBSRepository):
        self.wbs_repository = wbs_repository

    async def execute(self, wbs_create: WBSItemCreate, tenant_id: UUID) -> WBSItem:
        """
        Create a new WBS item.

        Args:
            wbs_create: The WBS item creation data
            tenant_id: The tenant ID for isolation

        Returns:
            The created WBS item
        """
        # Convert DTO to domain entity
        wbs_item = WBSItem(
            project_id=wbs_create.project_id,
            code=wbs_create.wbs_code,
            name=wbs_create.name,
            description=wbs_create.description,
            level=wbs_create.level,
            parent_code=None,  # Will be resolved from parent_id
            item_type=wbs_create.item_type,
            budget_allocated=wbs_create.budget_allocated,
            budget_spent=wbs_create.budget_spent,
            planned_start=wbs_create.planned_start,
            planned_end=wbs_create.planned_end,
            actual_start=wbs_create.actual_start,
            actual_end=wbs_create.actual_end,
            source_clause_id=wbs_create.funded_by_clause_id,
            wbs_metadata=wbs_create.wbs_metadata
        )

        # If parent_id is provided, resolve parent_code
        if wbs_create.parent_id:
            parent = await self.wbs_repository.get_by_id(wbs_create.parent_id, tenant_id)
            if parent:
                wbs_item.parent_code = parent.code

        return await self.wbs_repository.create(wbs_item)


class ListWBSItemsUseCase:
    """Use case for listing WBS items for a project."""

    def __init__(self, wbs_repository: IWBSRepository):
        self.wbs_repository = wbs_repository

    async def execute(self, project_id: UUID, tenant_id: UUID) -> List[WBSItem]:
        """
        List all WBS items for a project.

        Args:
            project_id: The project ID
            tenant_id: The tenant ID for isolation

        Returns:
            List of WBS items
        """
        return await self.wbs_repository.get_by_project(project_id, tenant_id)


class GetWBSItemUseCase:
    """Use case for retrieving a single WBS item."""

    def __init__(self, wbs_repository: IWBSRepository):
        self.wbs_repository = wbs_repository

    async def execute(self, wbs_id: UUID, tenant_id: UUID) -> Optional[WBSItem]:
        """
        Get a WBS item by ID.

        Args:
            wbs_id: The WBS item ID
            tenant_id: The tenant ID for isolation

        Returns:
            The WBS item if found, None otherwise
        """
        return await self.wbs_repository.get_by_id(wbs_id, tenant_id)


class UpdateWBSItemUseCase:
    """Use case for updating a WBS item."""

    def __init__(self, wbs_repository: IWBSRepository):
        self.wbs_repository = wbs_repository

    async def execute(
        self, wbs_id: UUID, wbs_update: WBSItemUpdate, tenant_id: UUID
    ) -> Optional[WBSItem]:
        """
        Update a WBS item.

        Args:
            wbs_id: The WBS item ID to update
            wbs_update: The update data
            tenant_id: The tenant ID for isolation

        Returns:
            The updated WBS item if found, None otherwise
        """
        # Get existing WBS item
        existing = await self.wbs_repository.get_by_id(wbs_id, tenant_id)
        if not existing:
            return None

        # Update only provided fields
        if wbs_update.name is not None:
            existing.name = wbs_update.name
        if wbs_update.description is not None:
            existing.description = wbs_update.description
        if wbs_update.budget_allocated is not None:
            existing.budget_allocated = wbs_update.budget_allocated
        if wbs_update.budget_spent is not None:
            existing.budget_spent = wbs_update.budget_spent
        if wbs_update.planned_start is not None:
            existing.planned_start = wbs_update.planned_start
        if wbs_update.planned_end is not None:
            existing.planned_end = wbs_update.planned_end
        if wbs_update.actual_start is not None:
            existing.actual_start = wbs_update.actual_start
        if wbs_update.actual_end is not None:
            existing.actual_end = wbs_update.actual_end
        if wbs_update.wbs_metadata is not None:
            existing.wbs_metadata = wbs_update.wbs_metadata

        # Handle parent update if parent_id is provided
        if wbs_update.parent_id is not None:
            parent = await self.wbs_repository.get_by_id(wbs_update.parent_id, tenant_id)
            if parent:
                existing.parent_code = parent.code

        return await self.wbs_repository.update(wbs_id, existing, tenant_id)


class DeleteWBSItemUseCase:
    """Use case for deleting a WBS item."""

    def __init__(self, wbs_repository: IWBSRepository):
        self.wbs_repository = wbs_repository

    async def execute(self, wbs_id: UUID, tenant_id: UUID) -> bool:
        """
        Delete a WBS item and its children.

        Args:
            wbs_id: The WBS item ID to delete
            tenant_id: The tenant ID for isolation

        Returns:
            True if deleted, False if not found
        """
        return await self.wbs_repository.delete(wbs_id, tenant_id)


class GetWBSTreeUseCase:
    """Use case for retrieving the complete WBS tree."""

    def __init__(self, wbs_repository: IWBSRepository):
        self.wbs_repository = wbs_repository

    async def execute(self, project_id: UUID, tenant_id: UUID) -> List[WBSItem]:
        """
        Get the complete WBS tree for a project with hierarchy.

        Args:
            project_id: The project ID
            tenant_id: The tenant ID for isolation

        Returns:
            List of root WBS items with children loaded recursively
        """
        return await self.wbs_repository.get_tree(project_id, tenant_id)
