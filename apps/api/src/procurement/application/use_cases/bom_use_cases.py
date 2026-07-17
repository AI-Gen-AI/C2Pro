"""
Use cases for BOM operations.
"""

from __future__ import annotations

from uuid import UUID

from src.core.tenants.types import TenantId
from src.procurement.application.dtos import BOMItemCreate, BOMItemUpdate
from src.procurement.domain.models import BOMItem, ProcurementStatus
from src.procurement.ports.bom_repository import IBOMRepository


def _source_document_id_from_payload(bom_create: BOMItemCreate) -> UUID | None:
    if bom_create.source_document_id is not None:
        return bom_create.source_document_id

    raw_source = bom_create.bom_metadata.get("source_document_id")
    if raw_source is None:
        return None
    try:
        return UUID(str(raw_source))
    except (TypeError, ValueError):
        return None


class CreateBOMItemUseCase:
    """Use case for creating a new BOM item."""

    def __init__(self, bom_repository: IBOMRepository):
        self.bom_repository = bom_repository

    async def execute(self, bom_create: BOMItemCreate, tenant_id: TenantId) -> BOMItem:
        """
        Create a new BOM item.

        Args:
            bom_create: The BOM item creation data
            tenant_id: The tenant ID for isolation

        Returns:
            The created BOM item
        """
        # Convert DTO to domain entity
        bom_item = BOMItem(
            project_id=bom_create.project_id,
            wbs_item_id=bom_create.wbs_item_id,
            item_code=bom_create.item_code,
            item_name=bom_create.item_name,
            description=bom_create.description,
            category=bom_create.category,
            quantity=bom_create.quantity,
            unit=bom_create.unit,
            unit_price=bom_create.unit_price,
            total_price=bom_create.total_price,
            currency=bom_create.currency,
            supplier=bom_create.supplier,
            lead_time_days=bom_create.lead_time_days,
            incoterm=bom_create.incoterm,
            contract_clause_id=bom_create.contract_clause_id,
            source_document_id=_source_document_id_from_payload(bom_create),
            procurement_status=bom_create.procurement_status,
            bom_metadata=bom_create.bom_metadata,
        )

        return await self.bom_repository.create(bom_item, tenant_id)

    async def replace_for_source_document(
        self,
        *,
        project_id: UUID,
        source_document_id: UUID,
        bom_items: list[BOMItemCreate],
        tenant_id: TenantId,
    ) -> list[BOMItem]:
        """Replace parsed BOM rows for one source document in a single repository operation."""
        domain_items = [
            BOMItem(
                project_id=item.project_id,
                wbs_item_id=item.wbs_item_id,
                item_code=item.item_code,
                item_name=item.item_name,
                description=item.description,
                category=item.category,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                total_price=item.total_price,
                currency=item.currency,
                supplier=item.supplier,
                lead_time_days=item.lead_time_days,
                incoterm=item.incoterm,
                contract_clause_id=item.contract_clause_id,
                source_document_id=source_document_id,
                procurement_status=item.procurement_status,
                bom_metadata={
                    **item.bom_metadata,
                    "source_document_id": str(source_document_id),
                },
            )
            for item in bom_items
        ]
        return await self.bom_repository.replace_for_source_document(
            project_id=project_id,
            source_document_id=source_document_id,
            bom_items=domain_items,
            tenant_id=tenant_id,
        )


class ListBOMItemsUseCase:
    """Use case for listing BOM items for a project."""

    def __init__(self, bom_repository: IBOMRepository):
        self.bom_repository = bom_repository

    async def execute(self, project_id: UUID, tenant_id: TenantId) -> list[BOMItem]:
        """
        List all BOM items for a project.

        Args:
            project_id: The project ID
            tenant_id: The tenant ID for isolation

        Returns:
            List of BOM items
        """
        return await self.bom_repository.get_by_project(project_id, tenant_id)


class GetBOMItemUseCase:
    """Use case for retrieving a single BOM item."""

    def __init__(self, bom_repository: IBOMRepository):
        self.bom_repository = bom_repository

    async def execute(self, bom_id: UUID, tenant_id: TenantId) -> BOMItem | None:
        """
        Get a BOM item by ID.

        Args:
            bom_id: The BOM item ID
            tenant_id: The tenant ID for isolation

        Returns:
            The BOM item if found, None otherwise
        """
        return await self.bom_repository.get_by_id(bom_id, tenant_id)


class UpdateBOMItemUseCase:
    """Use case for updating a BOM item."""

    def __init__(self, bom_repository: IBOMRepository):
        self.bom_repository = bom_repository

    async def execute(
        self, bom_id: UUID, bom_update: BOMItemUpdate, tenant_id: TenantId
    ) -> BOMItem | None:
        """
        Update a BOM item.

        Args:
            bom_id: The BOM item ID to update
            bom_update: The update data
            tenant_id: The tenant ID for isolation

        Returns:
            The updated BOM item if found, None otherwise
        """
        # Get existing BOM item
        existing = await self.bom_repository.get_by_id(bom_id, tenant_id)
        if not existing:
            return None

        # Update only provided fields
        if bom_update.item_name is not None:
            existing.item_name = bom_update.item_name
        if bom_update.description is not None:
            existing.description = bom_update.description
        if bom_update.quantity is not None:
            existing.quantity = bom_update.quantity
        if bom_update.unit is not None:
            existing.unit = bom_update.unit
        if bom_update.unit_price is not None:
            existing.unit_price = bom_update.unit_price
        if bom_update.total_price is not None:
            existing.total_price = bom_update.total_price
        if bom_update.supplier is not None:
            existing.supplier = bom_update.supplier
        if bom_update.lead_time_days is not None:
            existing.lead_time_days = bom_update.lead_time_days
        if bom_update.procurement_status is not None:
            existing.procurement_status = bom_update.procurement_status
        if bom_update.bom_metadata is not None:
            existing.bom_metadata = bom_update.bom_metadata

        return await self.bom_repository.update(bom_id, existing, tenant_id)


class DeleteBOMItemUseCase:
    """Use case for deleting a BOM item."""

    def __init__(self, bom_repository: IBOMRepository):
        self.bom_repository = bom_repository

    async def execute(self, bom_id: UUID, tenant_id: TenantId) -> bool:
        """
        Delete a BOM item.

        Args:
            bom_id: The BOM item ID to delete
            tenant_id: The tenant ID for isolation

        Returns:
            True if deleted, False if not found
        """
        return await self.bom_repository.delete(bom_id, tenant_id)


class UpdateBOMStatusUseCase:
    """Use case for updating the procurement status of a BOM item."""

    def __init__(self, bom_repository: IBOMRepository):
        self.bom_repository = bom_repository

    async def execute(
        self, bom_id: UUID, status: ProcurementStatus, tenant_id: TenantId
    ) -> BOMItem | None:
        """
        Update the procurement status of a BOM item.

        Args:
            bom_id: The BOM item ID to update
            status: The new procurement status
            tenant_id: The tenant ID for isolation

        Returns:
            The updated BOM item if found, None otherwise
        """
        return await self.bom_repository.update_status(bom_id, status, tenant_id)
