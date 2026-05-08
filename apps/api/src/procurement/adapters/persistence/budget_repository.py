"""
SQLAlchemy Budget Repository - TASK-BCK-021
Implements BudgetRepository port using existing procurement_budget_items table.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.procurement.adapters.persistence.models import BudgetItemORM, WBSItemORM
from src.projects.adapters.persistence.models import ProjectORM


class SQLAlchemyBudgetRepository:
    """SQLAlchemy implementation of BudgetRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_total_spent_by_project(self, project_id: UUID, tenant_id: UUID) -> Decimal:
        """Get the total spent amount for all WBS items in a project with tenant isolation."""
        stmt = (
            select(func.sum(WBSItemORM.budget_spent))
            .join(ProjectORM, ProjectORM.id == WBSItemORM.project_id)
            .where(WBSItemORM.project_id == project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        total_spent = result.scalar() or Decimal("0.00")
        return Decimal(str(total_spent))

    async def get_by_project(self, project_id: UUID, tenant_id: UUID) -> list[dict]:
        """Get all budget items for a project with tenant isolation."""
        stmt = (
            select(BudgetItemORM)
            .where(BudgetItemORM.project_id == project_id)
            .join(ProjectORM, ProjectORM.id == BudgetItemORM.project_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        items = result.scalars().all()

        return [
            {
                "id": item.id,
                "project_id": item.project_id,
                "name": item.name,
                "code": item.code,
                "amount": Decimal(str(item.amount)),
            }
            for item in items
        ]

    async def create(
        self,
        project_id: UUID,
        tenant_id: UUID,
        name: str,
        code: str,
        amount: Decimal,
    ) -> dict:
        """Create a new budget item with tenant isolation."""
        stmt = select(ProjectORM).where(ProjectORM.id == project_id).where(ProjectORM.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        project = result.scalar_one_or_none()

        if not project:
            raise ValueError(f"Project {project_id} not found or does not belong to tenant")

        item = BudgetItemORM(
            project_id=project_id,
            name=name,
            code=code,
            amount=amount,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)

        return {
            "id": item.id,
            "project_id": item.project_id,
            "name": item.name,
            "code": item.code,
            "amount": Decimal(str(item.amount)),
        }

    async def update(
        self,
        item_id: UUID,
        tenant_id: UUID,
        **updates,
    ) -> dict | None:
        """Update an existing budget item with tenant isolation."""
        stmt = (
            select(BudgetItemORM)
            .options(selectinload(BudgetItemORM.project))
            .where(BudgetItemORM.id == item_id)
        )
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()

        if not item or item.project.tenant_id != tenant_id:
            return None

        for key, value in updates.items():
            if hasattr(item, key):
                setattr(item, key, value)

        await self.session.commit()
        await self.session.refresh(item)

        return {
            "id": item.id,
            "project_id": item.project_id,
            "name": item.name,
            "code": item.code,
            "amount": Decimal(str(item.amount)),
        }

    async def delete(self, item_id: UUID, tenant_id: UUID) -> bool:
        """Delete a budget item with tenant isolation."""
        stmt = (
            select(BudgetItemORM)
            .join(ProjectORM, ProjectORM.id == BudgetItemORM.project_id)
            .where(BudgetItemORM.id == item_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            return False

        await self.session.delete(item)
        await self.session.commit()
        return True

    async def get_by_id(self, item_id: UUID, tenant_id: UUID) -> dict | None:
        """Get a budget item by ID with tenant isolation."""
        stmt = (
            select(BudgetItemORM)
            .join(ProjectORM, ProjectORM.id == BudgetItemORM.project_id)
            .where(BudgetItemORM.id == item_id)
            .where(ProjectORM.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            return None

        return {
            "id": item.id,
            "project_id": item.project_id,
            "name": item.name,
            "code": item.code,
            "amount": Decimal(str(item.amount)),
        }
