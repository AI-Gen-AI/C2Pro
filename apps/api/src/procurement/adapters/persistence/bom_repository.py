"""
SQLAlchemy implementation of the BOM repository.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.procurement.ports.bom_repository import IBOMRepository
from src.procurement.domain.models import BOMItem, BOMCategory, ProcurementStatus
from src.procurement.adapters.persistence.models import BOMItemORM
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
            procurement_status=orm.procurement_status,
            bom_metadata=orm.bom_metadata or {}
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
            procurement_status=bom_item.procurement_status,
            bom_metadata=bom_item.bom_metadata or {}
        )

    async def create(self, bom_item: BOMItem) -> BOMItem:
        """Create a new BOM item."""
        orm = self._domain_to_orm(bom_item)
        self.session.add(orm)
        await self.session.flush()
        await self.session.refresh(orm)

        return self._orm_to_domain(orm)

    async def get_by_id(self, bom_id: UUID, tenant_id: UUID) -> Optional[BOMItem]:
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

    async def get_by_project(self, project_id: UUID, tenant_id: UUID) -> List[BOMItem]:
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

    async def get_by_wbs_item(self, wbs_item_id: UUID, tenant_id: UUID) -> List[BOMItem]:
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
    ) -> List[BOMItem]:
        """Retrieve all BOM items of a specific category in a project."""
        result = await self.session.execute(
            select(BOMItemORM)
            .where(
                and_(
                    BOMItemORM.project_id == project_id,
                    BOMItemORM.category == category
                )
            )
            .join(ProjectORM, ProjectORM.id == BOMItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
            .order_by(BOMItemORM.item_code)
        )
        orms = result.scalars().all()

        return [self._orm_to_domain(orm) for orm in orms]

    async def get_by_status(
        self, project_id: UUID, status: ProcurementStatus, tenant_id: UUID
    ) -> List[BOMItem]:
        """Retrieve all BOM items with a specific procurement status in a project."""
        result = await self.session.execute(
            select(BOMItemORM)
            .where(
                and_(
                    BOMItemORM.project_id == project_id,
                    BOMItemORM.procurement_status == status
                )
            )
            .join(ProjectORM, ProjectORM.id == BOMItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
            .order_by(BOMItemORM.item_code)
        )
        orms = result.scalars().all()

        return [self._orm_to_domain(orm) for orm in orms]

    async def update(self, bom_id: UUID, bom_item: BOMItem, tenant_id: UUID) -> Optional[BOMItem]:
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
        orm.item_code = bom_item.item_code
        orm.item_name = bom_item.item_name
        orm.description = bom_item.description
        orm.category = bom_item.category
        orm.quantity = bom_item.quantity
        orm.unit = bom_item.unit
        orm.unit_price = bom_item.unit_price
        orm.total_price = bom_item.total_price
        orm.currency = bom_item.currency
        orm.supplier = bom_item.supplier
        orm.lead_time_days = bom_item.lead_time_days
        orm.incoterm = bom_item.incoterm
        orm.procurement_status = bom_item.procurement_status
        orm.bom_metadata = bom_item.bom_metadata or {}

        await self.session.flush()
        await self.session.refresh(orm)

        return self._orm_to_domain(orm)

    async def update_status(
        self, bom_id: UUID, status: ProcurementStatus, tenant_id: UUID
    ) -> Optional[BOMItem]:
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

        orm.procurement_status = status

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

    async def bulk_create(self, bom_items: List[BOMItem]) -> List[BOMItem]:
        """Create multiple BOM items at once (used for AI generation)."""
        orms = [self._domain_to_orm(item) for item in bom_items]

        self.session.add_all(orms)
        await self.session.flush()

        # Refresh all and convert back to domain
        created_items = []
        for orm in orms:
            await self.session.refresh(orm)
            created_items.append(self._orm_to_domain(orm))

        return created_items
