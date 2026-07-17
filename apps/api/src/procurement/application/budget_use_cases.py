"""
Budget Use Cases - TASK-BCK-021
Application layer use cases for Budget API.
"""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from src.core.tenants.types import TenantId
from src.procurement.ports.budget_repository import BudgetRepository


class BudgetItemCreate(BaseModel):
    """DTO for creating a budget item."""

    name: str = Field(..., min_length=1)
    code: str = Field(..., pattern=r"^[A-Z0-9-]+$")
    amount: Decimal = Field(..., ge=0)


class BudgetItemUpdate(BaseModel):
    """DTO for updating a budget item."""

    name: str | None = Field(None, min_length=1)
    code: str | None = Field(None, pattern=r"^[A-Z0-9-]+$")
    amount: Decimal | None = Field(None, ge=0)


class BudgetItemResponse(BaseModel):
    """DTO for budget item response."""

    id: UUID
    project_id: UUID
    name: str
    code: str
    amount: Decimal

    class Config:
        from_attributes = True


class BudgetResponse(BaseModel):
    """DTO for project budget summary."""

    project_id: UUID
    items: list[BudgetItemResponse]
    total_budget: Decimal = Decimal(0)
    spent_amount: Decimal = Decimal(0)
    remaining_budget: Decimal = Decimal(0)
    currency: str = "EUR"


class GetBudgetUseCase:
    """Use case for getting project budget."""

    def __init__(self, repository: BudgetRepository) -> None:
        self.repository: BudgetRepository = repository

    async def execute(self, project_id: UUID, tenant_id: TenantId) -> BudgetResponse:
        """Get budget for a project."""
        items = await self.repository.get_by_project(project_id, tenant_id)
        total_budget = sum((Decimal(str(item["amount"])) for item in items), Decimal(0))
        spent_amount = await self.repository.get_total_spent_by_project(project_id, tenant_id)
        remaining_budget = total_budget - spent_amount

        return BudgetResponse(
            project_id=project_id,
            items=[BudgetItemResponse(**item) for item in items],
            total_budget=total_budget,
            spent_amount=spent_amount,
            remaining_budget=remaining_budget,
        )


class CreateBudgetItemUseCase:
    """Use case for creating a budget item."""

    def __init__(self, repository: BudgetRepository) -> None:
        self.repository: BudgetRepository = repository

    async def execute(
        self,
        project_id: UUID,
        tenant_id: TenantId,
        data: BudgetItemCreate,
    ) -> BudgetItemResponse:
        """Create a new budget item."""
        item = await self.repository.create(
            project_id=project_id,
            tenant_id=tenant_id,
            name=data.name,
            code=data.code,
            amount=data.amount,
        )
        return BudgetItemResponse(**item)


class UpdateBudgetItemUseCase:
    """Use case for updating a budget item."""

    def __init__(self, repository: BudgetRepository) -> None:
        self.repository: BudgetRepository = repository

    async def execute(
        self,
        item_id: UUID,
        tenant_id: TenantId,
        data: BudgetItemUpdate,
    ) -> BudgetItemResponse:
        """Update an existing budget item."""
        updates = data.model_dump(exclude_unset=True)
        item = await self.repository.update(item_id, tenant_id, **updates)
        if not item:
            raise ValueError(f"Budget item {item_id} not found")
        return BudgetItemResponse(**item)


class DeleteBudgetItemUseCase:
    """Use case for deleting a budget item."""

    def __init__(self, repository: BudgetRepository) -> None:
        self.repository: BudgetRepository = repository

    async def execute(self, item_id: UUID, tenant_id: TenantId) -> bool:
        """Delete a budget item."""
        return await self.repository.delete(item_id, tenant_id)
