"""
SQLAlchemy implementation of the BOM repository.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tenants.types import TenantId
from src.procurement.adapters.persistence.models import BOMItemORM
from src.procurement.domain.models import BOMCategory, BOMItem, ProcurementStatus
from src.procurement.ports.bom_repository import IBOMRepository
from src.projects.adapters.persistence.models import ProjectORM


class SQLAlchemyBOMRepository(IBOMRepository):
    """SQLAlchemy implementation of BOM repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _orm_to_domain(self, orm: BOMItemORM) -> BOMItem:
        """Convert ORM model to domain entity."""
        return BOMItem(
            id=orm.id,
            project_id=orm.project_id,
            wbs_item_id=orm.wbs_item_id,
            item_code=orm.item_code,
            item_name=orm.item_name,
            description=orm.description,
            category=orm.category,
            quantity=orm.quantity,
            unit=orm.unit,
            unit_price=orm.unit_price,
            total_price=orm.total_price,
            currency=orm.currency,
            supplier=orm.supplier,
            lead_time_days=orm.lead_time_days,
            incoterm=orm.incoterm,
            contract_clause_id=orm.contract_clause_id,
            source_document_id=orm.source_document_id,
            procurement_status=orm.procurement_status,
            bom_metadata=orm.bom_metadata or {},
        )

    def _domain_to_orm(self, bom_item: BOMItem) -> BOMItemORM:
        """Convert domain entity to ORM model."""
        return BOMItemORM(
            id=bom_item.id,
            project_id=bom_item.project_id,
            wbs_item_id=bom_item.wbs_item_id,
            item_code=bom_item.item_code,
            item_name=bom_item.item_name,
            description=bom_item.description,
            category=bom_item.category,
            quantity=bom_item.quantity,
            unit=bom_item.unit,
            unit_price=bom_item.unit_price,
            total_price=bom_item.total_price,
            currency=bom_item.currency,
            supplier=bom_item.supplier,
            lead_time_days=bom_item.lead_time_days,
            incoterm=bom_item.incoterm,
            contract_clause_id=bom_item.contract_clause_id,
            source_document_id=bom_item.source_document_id,
            procurement_status=bom_item.procurement_status,
            bom_metadata=bom_item.bom_metadata or {},
        )

    async def _ensure_project_in_tenant(self, project_id: UUID, tenant_id: UUID) -> None:
        """Reject writes for projects outside the caller tenant."""
        result = await self.session.execute(
            select(ProjectORM.id)
            .where(ProjectORM.id == project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        if result.scalar_one_or_none() is None:
            raise PermissionError("Cannot create BOM items for project outside tenant")

    async def create(self, bom_item: BOMItem, tenant_id: UUID) -> BOMItem:
        """Create a new BOM item with tenant isolation."""
        await self._ensure_project_in_tenant(bom_item.project_id, tenant_id)
        orm = self._domain_to_orm(bom_item)
        self.session.add(orm)
        await self.session.flush()
        await self.session.refresh(orm)

        return self._orm_to_domain(orm)

    async def replace_for_source_document(
        self,
        *,
        project_id: UUID,
        source_document_id: UUID,
        bom_items: list[BOMItem],
        tenant_id: UUID,
    ) -> list[BOMItem]:
        """Replace all BOM rows produced by one parsed source document."""
        await self._ensure_project_in_tenant(project_id, tenant_id)
        await self.session.execute(
            delete(BOMItemORM).where(
                BOMItemORM.project_id == project_id,
                BOMItemORM.source_document_id == source_document_id,
            )
        )

        orms = []
        for item in bom_items:
            if item.project_id != project_id:
                raise ValueError("BOM item project_id must match replacement project_id")
            item.source_document_id = source_document_id
            orms.append(self._domain_to_orm(item))

        self.session.add_all(orms)
        await self.session.flush()

        created_items: list[BOMItem] = []
        for orm in orms:
            await self.session.refresh(orm)
            created_items.append(self._orm_to_domain(orm))
        return created_items

    async def get_by_id(self, bom_id: UUID, tenant_id: UUID) -> BOMItem | None:
        """Retrieve a BOM item by ID."""
        result = await self.session.execute(
            select(BOMItemORM)
            .where(BOMItemORM.id == bom_id)
            .join(ProjectORM, ProjectORM.id == BOMItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        orm = result.scalar_one_or_none()

        if not orm:
            return None

        return self._orm_to_domain(orm)

    async def get_by_project(self, project_id: UUID, tenant_id: UUID) -> list[BOMItem]:
        """Retrieve all BOM items for a project."""
        result = await self.session.execute(
            select(BOMItemORM)
            .where(BOMItemORM.project_id == project_id)
            .join(ProjectORM, ProjectORM.id == BOMItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
            .order_by(BOMItemORM.item_code)
        )
        orms = result.scalars().all()

        return [self._orm_to_domain(orm) for orm in orms]

    async def get_by_wbs_item(self, wbs_item_id: UUID, tenant_id: UUID) -> list[BOMItem]:
        """Retrieve all BOM items for a specific WBS item."""
        result = await self.session.execute(
            select(BOMItemORM)
            .where(BOMItemORM.wbs_item_id == wbs_item_id)
            .join(ProjectORM, ProjectORM.id == BOMItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
            .order_by(BOMItemORM.item_code)
        )
        orms = result.scalars().all()

        return [self._orm_to_domain(orm) for orm in orms]

    async def get_by_category(
        self, project_id: UUID, category: BOMCategory, tenant_id: UUID
    ) -> list[BOMItem]:
        """Retrieve all BOM items of a specific category in a project."""
        result = await self.session.execute(
            select(BOMItemORM)
            .where(and_(BOMItemORM.project_id == project_id, BOMItemORM.category == category))
            .join(ProjectORM, ProjectORM.id == BOMItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
            .order_by(BOMItemORM.item_code)
        )
        orms = result.scalars().all()

        return [self._orm_to_domain(orm) for orm in orms]

    async def get_by_status(
        self, project_id: UUID, status: ProcurementStatus, tenant_id: UUID
    ) -> list[BOMItem]:
        """Retrieve all BOM items with a specific procurement status in a project."""
        result = await self.session.execute(
            select(BOMItemORM)
            .where(
                and_(BOMItemORM.project_id == project_id, BOMItemORM.procurement_status == status)
            )
            .join(ProjectORM, ProjectORM.id == BOMItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
            .order_by(BOMItemORM.item_code)
        )
        orms = result.scalars().all()

        return [self._orm_to_domain(orm) for orm in orms]

    async def update(self, bom_id: UUID, bom_item: BOMItem, tenant_id: UUID) -> BOMItem | None:
        """Update an existing BOM item."""
        result = await self.session.execute(
            select(BOMItemORM)
            .where(BOMItemORM.id == bom_id)
            .join(ProjectORM, ProjectORM.id == BOMItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        orm = result.scalar_one_or_none()

        if not orm:
            return None

        # Update fields
        orm.item_code = bom_item.item_code  # type: ignore[assignment]
        orm.item_name = bom_item.item_name  # type: ignore[assignment]
        orm.description = bom_item.description  # type: ignore[assignment]
        orm.category = bom_item.category  # type: ignore[assignment]
        orm.quantity = bom_item.quantity  # type: ignore[assignment]
        orm.unit = bom_item.unit  # type: ignore[assignment]
        orm.unit_price = bom_item.unit_price  # type: ignore[assignment]
        orm.total_price = bom_item.total_price  # type: ignore[assignment]
        orm.currency = bom_item.currency  # type: ignore[assignment]
        orm.supplier = bom_item.supplier  # type: ignore[assignment]
        orm.lead_time_days = bom_item.lead_time_days  # type: ignore[assignment]
        orm.incoterm = bom_item.incoterm  # type: ignore[assignment]
        orm.source_document_id = bom_item.source_document_id  # type: ignore[assignment]
        orm.procurement_status = bom_item.procurement_status  # type: ignore[assignment]
        orm.bom_metadata = bom_item.bom_metadata or {}  # type: ignore[assignment]

        await self.session.flush()
        await self.session.refresh(orm)

        return self._orm_to_domain(orm)

    async def update_status(
        self, bom_id: UUID, status: ProcurementStatus, tenant_id: UUID
    ) -> BOMItem | None:
        """Update the procurement status of a BOM item."""
        result = await self.session.execute(
            select(BOMItemORM)
            .where(BOMItemORM.id == bom_id)
            .join(ProjectORM, ProjectORM.id == BOMItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        orm = result.scalar_one_or_none()

        if not orm:
            return None

        orm.procurement_status = status  # type: ignore[assignment]

        await self.session.flush()
        await self.session.refresh(orm)

        return self._orm_to_domain(orm)

    async def delete(self, bom_id: UUID, tenant_id: UUID) -> bool:
        """Delete a BOM item."""
        result = await self.session.execute(
            select(BOMItemORM)
            .where(BOMItemORM.id == bom_id)
            .join(ProjectORM, ProjectORM.id == BOMItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        orm = result.scalar_one_or_none()

        if not orm:
            return False

        await self.session.delete(orm)
        await self.session.flush()

        return True

    async def bulk_create(self, bom_items: list[BOMItem], tenant_id: UUID) -> list[BOMItem]:
        """Create multiple BOM items at once with tenant isolation."""
        for project_id in {bom_item.project_id for bom_item in bom_items}:
            await self._ensure_project_in_tenant(project_id, tenant_id)

        orms = [self._domain_to_orm(item) for item in bom_items]

        self.session.add_all(orms)
        await self.session.flush()

        # Refresh all and convert back to domain
        created_items = []
        for orm in orms:
            await self.session.refresh(orm)
            created_items.append(self._orm_to_domain(orm))

        return created_items
