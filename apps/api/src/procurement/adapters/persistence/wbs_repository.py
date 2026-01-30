"""
SQLAlchemy implementation of the WBS repository.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.procurement.ports.wbs_repository import IWBSRepository
from src.procurement.domain.models import WBSItem
from src.procurement.adapters.persistence.models import WBSItemORM
from src.projects.adapters.persistence.models import ProjectORM


class SQLAlchemyWBSRepository(IWBSRepository):
    """SQLAlchemy implementation of WBS repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _orm_to_domain(self, orm: WBSItemORM, include_children: bool = False) -> WBSItem:
        """Convert ORM model to domain entity."""
        # Map parent_id to parent_code if needed
        parent_code = None
        if orm.parent_id and orm.parent:
            parent_code = orm.parent.wbs_code

        wbs_item = WBSItem(
            id=orm.id,
            project_id=orm.project_id,
            code=orm.wbs_code,
            name=orm.name,
            description=orm.description,
            level=orm.level,
            parent_code=parent_code,
            item_type=orm.item_type,
            budget_allocated=orm.budget_allocated,
            budget_spent=orm.budget_spent,
            planned_start=orm.planned_start,
            planned_end=orm.planned_end,
            actual_start=orm.actual_start,
            actual_end=orm.actual_end,
            source_clause_id=orm.funded_by_clause_id,
            wbs_metadata=orm.wbs_metadata or {},
            children=[]
        )

        if include_children and orm.children:
            wbs_item.children = [
                self._orm_to_domain(child, include_children=True)
                for child in orm.children
            ]

        return wbs_item

    def _domain_to_orm(self, wbs_item: WBSItem, parent_id: Optional[UUID] = None) -> WBSItemORM:
        """Convert domain entity to ORM model."""
        return WBSItemORM(
            id=wbs_item.id,
            project_id=wbs_item.project_id,
            parent_id=parent_id,
            wbs_code=wbs_item.code,
            name=wbs_item.name,
            description=wbs_item.description,
            level=wbs_item.level,
            item_type=wbs_item.item_type,
            budget_allocated=wbs_item.budget_allocated,
            budget_spent=wbs_item.budget_spent,
            planned_start=wbs_item.planned_start,
            planned_end=wbs_item.planned_end,
            actual_start=wbs_item.actual_start,
            actual_end=wbs_item.actual_end,
            funded_by_clause_id=wbs_item.source_clause_id,
            wbs_metadata=wbs_item.wbs_metadata or {}
        )

    async def create(self, wbs_item: WBSItem) -> WBSItem:
        """Create a new WBS item."""
        # Find parent by code if parent_code is set
        parent_id = None
        if wbs_item.parent_code:
            parent_result = await self.session.execute(
                select(WBSItemORM).where(
                    and_(
                        WBSItemORM.project_id == wbs_item.project_id,
                        WBSItemORM.wbs_code == wbs_item.parent_code
                    )
                )
            )
            parent_orm = parent_result.scalar_one_or_none()
            if parent_orm:
                parent_id = parent_orm.id

        orm = self._domain_to_orm(wbs_item, parent_id=parent_id)
        self.session.add(orm)
        await self.session.flush()
        await self.session.refresh(orm)

        return self._orm_to_domain(orm)

    async def get_by_id(self, wbs_id: UUID, tenant_id: UUID) -> Optional[WBSItem]:
        """Retrieve a WBS item by ID."""
        result = await self.session.execute(
            select(WBSItemORM)
            .options(selectinload(WBSItemORM.parent))
            .where(WBSItemORM.id == wbs_id)
            .join(ProjectORM, ProjectORM.id == WBSItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        orm = result.scalar_one_or_none()

        if not orm:
            return None

        return self._orm_to_domain(orm)

    async def get_by_project(self, project_id: UUID, tenant_id: UUID) -> List[WBSItem]:
        """Retrieve all WBS items for a project."""
        result = await self.session.execute(
            select(WBSItemORM)
            .options(selectinload(WBSItemORM.parent))
            .where(WBSItemORM.project_id == project_id)
            .join(ProjectORM, ProjectORM.id == WBSItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
            .order_by(WBSItemORM.wbs_code)
        )
        orms = result.scalars().all()

        return [self._orm_to_domain(orm) for orm in orms]

    async def get_by_code(self, project_id: UUID, wbs_code: str, tenant_id: UUID) -> Optional[WBSItem]:
        """Retrieve a WBS item by its code within a project."""
        result = await self.session.execute(
            select(WBSItemORM)
            .options(selectinload(WBSItemORM.parent))
            .where(
                and_(
                    WBSItemORM.project_id == project_id,
                    WBSItemORM.wbs_code == wbs_code
                )
            )
            .join(ProjectORM, ProjectORM.id == WBSItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        orm = result.scalar_one_or_none()

        if not orm:
            return None

        return self._orm_to_domain(orm)

    async def get_children(self, parent_id: UUID, tenant_id: UUID) -> List[WBSItem]:
        """Retrieve all children of a WBS item."""
        result = await self.session.execute(
            select(WBSItemORM)
            .where(WBSItemORM.parent_id == parent_id)
            .join(ProjectORM, ProjectORM.id == WBSItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
            .order_by(WBSItemORM.wbs_code)
        )
        orms = result.scalars().all()

        return [self._orm_to_domain(orm) for orm in orms]

    async def get_tree(self, project_id: UUID, tenant_id: UUID) -> List[WBSItem]:
        """Retrieve the complete WBS tree for a project with hierarchy."""
        # Get all WBS items for the project
        result = await self.session.execute(
            select(WBSItemORM)
            .options(selectinload(WBSItemORM.children))
            .where(WBSItemORM.project_id == project_id)
            .where(WBSItemORM.parent_id == None)  # Only root items
            .join(ProjectORM, ProjectORM.id == WBSItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
            .order_by(WBSItemORM.wbs_code)
        )
        root_orms = result.scalars().all()

        return [self._orm_to_domain(orm, include_children=True) for orm in root_orms]

    async def update(self, wbs_id: UUID, wbs_item: WBSItem, tenant_id: UUID) -> Optional[WBSItem]:
        """Update an existing WBS item."""
        result = await self.session.execute(
            select(WBSItemORM)
            .where(WBSItemORM.id == wbs_id)
            .join(ProjectORM, ProjectORM.id == WBSItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        orm = result.scalar_one_or_none()

        if not orm:
            return None

        # Update fields
        orm.name = wbs_item.name
        orm.description = wbs_item.description
        orm.item_type = wbs_item.item_type
        orm.budget_allocated = wbs_item.budget_allocated
        orm.budget_spent = wbs_item.budget_spent
        orm.planned_start = wbs_item.planned_start
        orm.planned_end = wbs_item.planned_end
        orm.actual_start = wbs_item.actual_start
        orm.actual_end = wbs_item.actual_end
        orm.wbs_metadata = wbs_item.wbs_metadata or {}

        # Handle parent_code update
        if wbs_item.parent_code:
            parent_result = await self.session.execute(
                select(WBSItemORM).where(
                    and_(
                        WBSItemORM.project_id == wbs_item.project_id,
                        WBSItemORM.wbs_code == wbs_item.parent_code
                    )
                )
            )
            parent_orm = parent_result.scalar_one_or_none()
            if parent_orm:
                orm.parent_id = parent_orm.id

        await self.session.flush()
        await self.session.refresh(orm)

        return self._orm_to_domain(orm)

    async def delete(self, wbs_id: UUID, tenant_id: UUID) -> bool:
        """Delete a WBS item and its children (cascade)."""
        result = await self.session.execute(
            select(WBSItemORM)
            .where(WBSItemORM.id == wbs_id)
            .join(ProjectORM, ProjectORM.id == WBSItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        orm = result.scalar_one_or_none()

        if not orm:
            return False

        await self.session.delete(orm)
        await self.session.flush()

        return True

    async def bulk_create(self, wbs_items: List[WBSItem]) -> List[WBSItem]:
        """Create multiple WBS items at once (used for AI generation)."""
        # Build a mapping of codes to items for resolving parent relationships
        code_to_item = {item.code: item for item in wbs_items}
        code_to_orm = {}

        # First pass: create all ORMs without parent relationships
        orms_to_add = []
        for wbs_item in wbs_items:
            orm = self._domain_to_orm(wbs_item)
            code_to_orm[wbs_item.code] = orm
            orms_to_add.append(orm)

        # Add all to session
        self.session.add_all(orms_to_add)
        await self.session.flush()

        # Second pass: resolve parent relationships by code
        for wbs_item in wbs_items:
            if wbs_item.parent_code and wbs_item.parent_code in code_to_orm:
                orm = code_to_orm[wbs_item.code]
                parent_orm = code_to_orm[wbs_item.parent_code]
                orm.parent_id = parent_orm.id

        await self.session.flush()

        # Refresh all and convert back to domain
        created_items = []
        for orm in orms_to_add:
            await self.session.refresh(orm)
            created_items.append(self._orm_to_domain(orm))

        return created_items

