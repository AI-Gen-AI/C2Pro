"""
Budget Use Cases - TASK-BCK-021
Application layer use cases for Budget API.
"""

from decimal import Decimal
from uuid import UUID

import structlog
from pydantic import BaseModel, Field

from src.core.tenants.types import TenantId
from src.procurement.ports.budget_repository import BudgetRepository
from src.temporal.application.project_snapshot_trigger import (
    record_project_event_and_enqueue_snapshot,
)
from src.temporal.domain.project_snapshot import SnapshotTrigger

logger = structlog.get_logger(__name__)


class BudgetItemCreate(BaseModel):
    """DTO for creating a budget item."""

    name: str = Field(..., min_length=1)
    code: str = Field(..., pattern=r"^[A-Z0-9-]+$")
    amount: Decimal = Field(..., ge=0)
    is_baseline_change: bool = False


class BudgetItemUpdate(BaseModel):
    """DTO for updating a budget item."""

    name: str | None = Field(None, min_length=1)
    code: str | None = Field(None, pattern=r"^[A-Z0-9-]+$")
    amount: Decimal | None = Field(None, ge=0)
    is_baseline_change: bool = False


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
            items=[BudgetItemResponse.model_validate(item) for item in items],
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
        response = BudgetItemResponse.model_validate(item)
        if data.is_baseline_change:
            await _record_baseline_change(
                project_id=project_id,
                tenant_id=tenant_id,
                action="created",
                budget_item_id=response.id,
            )
        return response


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
        updates = data.model_dump(exclude_unset=True, exclude={"is_baseline_change"})
        item = await self.repository.update(item_id, tenant_id, **updates)
        if not item:
            raise ValueError(f"Budget item {item_id} not found")
        response = BudgetItemResponse.model_validate(item)
        if data.is_baseline_change:
            await _record_baseline_change(
                project_id=response.project_id,
                tenant_id=tenant_id,
                action="updated",
                budget_item_id=response.id,
            )
        return response


class DeleteBudgetItemUseCase:
    """Use case for deleting a budget item."""

    def __init__(self, repository: BudgetRepository) -> None:
        self.repository: BudgetRepository = repository

    async def execute(
        self,
        item_id: UUID,
        tenant_id: TenantId,
        *,
        is_baseline_change: bool = False,
    ) -> bool:
        """Delete a budget item."""
        item = await self.repository.get_by_id(item_id, tenant_id) if is_baseline_change else None
        deleted = await self.repository.delete(item_id, tenant_id)
        if deleted and is_baseline_change and item is not None:
            project_id = item.get("project_id")
            if isinstance(project_id, UUID):
                await _record_baseline_change(
                    project_id=project_id,
                    tenant_id=tenant_id,
                    action="deleted",
                    budget_item_id=item_id,
                )
        return deleted


async def _record_baseline_change(
    *,
    project_id: UUID,
    tenant_id: TenantId,
    action: str,
    budget_item_id: UUID,
) -> None:
    """Record only explicit baseline changes; ordinary budget CRUD is not a baseline."""
    try:
        await record_project_event_and_enqueue_snapshot(
            project_id=project_id,
            tenant_id=tenant_id,
            event_type="baseline.changed",
            payload={"action": action, "budget_item_id": str(budget_item_id)},
            trigger=SnapshotTrigger.BASELINE_CHANGED,
            actor="procurement_budget",
        )
    except Exception:  # noqa: BLE001 - temporal observability must not block a budget mutation.
        logger.warning(
            "baseline_change_snapshot_trigger_failed",
            project_id=str(project_id),
            tenant_id=str(tenant_id),
            budget_item_id=str(budget_item_id),
            exc_info=True,
        )
