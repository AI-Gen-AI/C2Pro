"""
FastAPI router for the Procurement module (WBS and BOM operations).
"""
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.security import CurrentTenantId

# Repositories
from src.procurement.application.dependencies import (
    get_bom_item_use_case,
    get_create_bom_item_use_case,
    get_create_wbs_item_use_case,
    get_delete_bom_item_use_case,
    get_delete_wbs_item_use_case,
    get_list_bom_items_use_case,
    get_list_wbs_items_use_case,
    get_update_bom_item_use_case,
    get_update_bom_status_use_case,
    get_update_wbs_item_use_case,
    get_wbs_item_use_case,
    get_wbs_tree_use_case,
)

# DTOs
from src.procurement.application.dtos import (
    BOMItemCreate,
    BOMItemResponse,
    BOMItemUpdate,
    PlanningDecision,
    ProcurementPlanningRequest,
    WBSItemCreate,
    WBSItemResponse,
    WBSItemUpdate,
)
from src.procurement.application.planning_service import (
    ProcurementDecisionRepository,
    ProcurementPlanningService,
    ProcurementSnapshotRepository,
    ProcurementUnitOfWork,
)

# Use cases
from src.procurement.application.use_cases import (
    BuildProcurementPlanUseCase,
    CreateBOMItemUseCase,
    CreateWBSItemUseCase,
    DeleteBOMItemUseCase,
    DeleteWBSItemUseCase,
    GetBOMItemUseCase,
    GetWBSItemUseCase,
    GetWBSTreeUseCase,
    ListBOMItemsUseCase,
    ListWBSItemsUseCase,
    UpdateBOMItemUseCase,
    UpdateBOMStatusUseCase,
    UpdateWBSItemUseCase,
)
from src.procurement.domain.models import (
    ProcurementConflict,
    ProcurementPlanItem,
    ProcurementStatus,
)

router = APIRouter(prefix="/procurement", tags=["procurement"])


# ==========================================
# PLANNING ENDPOINTS
# ==========================================


class UnconfiguredSnapshotRepo:
    async def get_snapshot_items(self, project_id: UUID, tenant_id: UUID, required_on_site: date | datetime) -> list[ProcurementPlanItem]:  # noqa: ARG002 - Placeholder repository keeps the production contract until planning persistence is wired
        raise RuntimeError("Unconfigured procurement snapshot repository")


class UnconfiguredDecisionRepo:
    async def save_plan_items(self, project_id: UUID, _tenant_id: UUID, items: list[ProcurementPlanItem]) -> None:  # noqa: ARG002 - Placeholder repository keeps the production contract until planning persistence is wired
        raise RuntimeError("Unconfigured procurement decision repository")

    async def save_conflicts(self, project_id: UUID, _tenant_id: UUID, conflicts: list[ProcurementConflict]) -> None:  # noqa: ARG002 - Placeholder repository keeps the production contract until planning persistence is wired
        raise RuntimeError("Unconfigured procurement decision repository")


class UnconfiguredUoW:
    async def commit(self) -> None:
        raise RuntimeError("Unconfigured procurement unit of work")

    async def rollback(self) -> None:
        raise RuntimeError("Unconfigured procurement unit of work")


def get_snapshot_repository() -> ProcurementSnapshotRepository:
    return UnconfiguredSnapshotRepo()


def get_decision_repository() -> ProcurementDecisionRepository:
    return UnconfiguredDecisionRepo()


def get_procurement_uow() -> ProcurementUnitOfWork:
    return UnconfiguredUoW()


def get_planning_service(
    repository: ProcurementSnapshotRepository = Depends(get_snapshot_repository),
    decision_repository: ProcurementDecisionRepository = Depends(get_decision_repository),
    uow: ProcurementUnitOfWork = Depends(get_procurement_uow),
) -> ProcurementPlanningService:
    return ProcurementPlanningService(
        repository=repository,
        decision_repository=decision_repository,
        uow=uow,
    )


def get_procurement_plan_use_case(
    planning_service: ProcurementPlanningService = Depends(get_planning_service),
) -> BuildProcurementPlanUseCase:
    return BuildProcurementPlanUseCase(planning_service=planning_service)


@router.post("/planning", response_model=PlanningDecision)
async def build_procurement_plan(
    payload: ProcurementPlanningRequest,
    tenant_id: CurrentTenantId,
    use_case: BuildProcurementPlanUseCase = Depends(get_procurement_plan_use_case),
) -> PlanningDecision:
    """
    Build a tenant-scoped procurement plan for a project snapshot.
    """
    try:
        return await use_case.execute(
            project_id=payload.project_id,
            tenant_id=tenant_id,
            required_on_site=payload.required_on_site,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Procurement planning failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Procurement planning failed: {str(e)}"
        )


# ==========================================
# WBS ENDPOINTS
# ==========================================


@router.post("/wbs", response_model=WBSItemResponse, status_code=http_status.HTTP_201_CREATED)
async def create_wbs_item(
    wbs_create: WBSItemCreate,
    tenant_id: CurrentTenantId,
    use_case: CreateWBSItemUseCase = Depends(get_create_wbs_item_use_case),
) -> WBSItemResponse:
    """
    Create a new WBS item.
    """
    try:
        wbs_item = await use_case.execute(wbs_create, tenant_id)
        return WBSItemResponse.model_validate(wbs_item)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create WBS item: {str(e)}"
        )


@router.get("/wbs/project/{project_id}", response_model=list[WBSItemResponse])
async def list_wbs_items(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: ListWBSItemsUseCase = Depends(get_list_wbs_items_use_case),
) -> list[WBSItemResponse]:
    """
    List all WBS items for a project.
    """
    wbs_items = await use_case.execute(project_id, tenant_id)
    return [WBSItemResponse.model_validate(item) for item in wbs_items]


@router.get("/wbs/project/{project_id}/tree", response_model=list[WBSItemResponse])
async def get_wbs_tree(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: GetWBSTreeUseCase = Depends(get_wbs_tree_use_case),
) -> list[WBSItemResponse]:
    """
    Get the complete WBS tree for a project with hierarchy.
    """
    wbs_tree = await use_case.execute(project_id, tenant_id)
    return [WBSItemResponse.model_validate(item) for item in wbs_tree]


@router.get("/wbs/{wbs_id}", response_model=WBSItemResponse)
async def get_wbs_item(
    wbs_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: GetWBSItemUseCase = Depends(get_wbs_item_use_case),
) -> WBSItemResponse:
    """
    Get a specific WBS item by ID.
    """
    wbs_item = await use_case.execute(wbs_id, tenant_id)
    if not wbs_item:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="WBS item not found"
        )

    return WBSItemResponse.model_validate(wbs_item)


@router.put("/wbs/{wbs_id}", response_model=WBSItemResponse)
async def update_wbs_item(
    wbs_id: UUID,
    wbs_update: WBSItemUpdate,
    tenant_id: CurrentTenantId,
    use_case: UpdateWBSItemUseCase = Depends(get_update_wbs_item_use_case),
) -> WBSItemResponse:
    """
    Update a WBS item.
    """
    wbs_item = await use_case.execute(wbs_id, wbs_update, tenant_id)
    if not wbs_item:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="WBS item not found"
        )

    return WBSItemResponse.model_validate(wbs_item)


@router.delete("/wbs/{wbs_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_wbs_item(
    wbs_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: DeleteWBSItemUseCase = Depends(get_delete_wbs_item_use_case),
) -> None:
    """
    Delete a WBS item and its children (cascade).
    """
    deleted = await use_case.execute(wbs_id, tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="WBS item not found"
        )

    return None


# ==========================================
# BOM ENDPOINTS
# ==========================================


@router.post("/bom", response_model=BOMItemResponse, status_code=http_status.HTTP_201_CREATED)
async def create_bom_item(
    bom_create: BOMItemCreate,
    tenant_id: CurrentTenantId,
    use_case: CreateBOMItemUseCase = Depends(get_create_bom_item_use_case),
) -> BOMItemResponse:
    """
    Create a new BOM item.
    """
    try:
        bom_item = await use_case.execute(bom_create, tenant_id)
        return BOMItemResponse.model_validate(bom_item)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create BOM item: {str(e)}"
        )


@router.get("/bom/project/{project_id}", response_model=list[BOMItemResponse])
async def list_bom_items(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: ListBOMItemsUseCase = Depends(get_list_bom_items_use_case),
) -> list[BOMItemResponse]:
    """
    List all BOM items for a project.
    """
    bom_items = await use_case.execute(project_id, tenant_id)
    return [BOMItemResponse.model_validate(item) for item in bom_items]


@router.get("/bom/{bom_id}", response_model=BOMItemResponse)
async def get_bom_item(
    bom_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: GetBOMItemUseCase = Depends(get_bom_item_use_case),
) -> BOMItemResponse:
    """
    Get a specific BOM item by ID.
    """
    bom_item = await use_case.execute(bom_id, tenant_id)
    if not bom_item:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="BOM item not found"
        )

    return BOMItemResponse.model_validate(bom_item)


@router.put("/bom/{bom_id}", response_model=BOMItemResponse)
async def update_bom_item(
    bom_id: UUID,
    bom_update: BOMItemUpdate,
    tenant_id: CurrentTenantId,
    use_case: UpdateBOMItemUseCase = Depends(get_update_bom_item_use_case),
) -> BOMItemResponse:
    """
    Update a BOM item.
    """
    bom_item = await use_case.execute(bom_id, bom_update, tenant_id)
    if not bom_item:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="BOM item not found"
        )

    return BOMItemResponse.model_validate(bom_item)


@router.patch("/bom/{bom_id}/status", response_model=BOMItemResponse)
async def update_bom_status(
    bom_id: UUID,
    status: ProcurementStatus,
    tenant_id: CurrentTenantId,
    use_case: UpdateBOMStatusUseCase = Depends(get_update_bom_status_use_case),
) -> BOMItemResponse:
    """
    Update the procurement status of a BOM item.
    """
    bom_item = await use_case.execute(bom_id, status, tenant_id)
    if not bom_item:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="BOM item not found"
        )

    return BOMItemResponse.model_validate(bom_item)


@router.delete("/bom/{bom_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_bom_item(
    bom_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: DeleteBOMItemUseCase = Depends(get_delete_bom_item_use_case),
) -> None:
    """
    Delete a BOM item.
    """
    deleted = await use_case.execute(bom_id, tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="BOM item not found"
        )

    return None


# ===========================================
# BUDGET ENDPOINTS - TASK-BCK-021
# ===========================================

from src.procurement.adapters.persistence.budget_repository import (  # noqa: E402
    SQLAlchemyBudgetRepository,
)
from src.procurement.application.budget_use_cases import (  # noqa: E402
    BudgetItemCreate,
    BudgetItemResponse,
    BudgetItemUpdate,
    BudgetResponse,
    CreateBudgetItemUseCase,
    DeleteBudgetItemUseCase,
    GetBudgetUseCase,
    UpdateBudgetItemUseCase,
)


def get_budget_repository(session: AsyncSession = Depends(get_session)) -> SQLAlchemyBudgetRepository:
    return SQLAlchemyBudgetRepository(session)


def get_budget_use_case(repository: SQLAlchemyBudgetRepository = Depends(get_budget_repository)) -> GetBudgetUseCase:
    return GetBudgetUseCase(repository)


def get_create_budget_item_use_case(repository: SQLAlchemyBudgetRepository = Depends(get_budget_repository)) -> CreateBudgetItemUseCase:
    return CreateBudgetItemUseCase(repository)


def get_update_budget_item_use_case(repository: SQLAlchemyBudgetRepository = Depends(get_budget_repository)) -> UpdateBudgetItemUseCase:
    return UpdateBudgetItemUseCase(repository)


def get_delete_budget_item_use_case(repository: SQLAlchemyBudgetRepository = Depends(get_budget_repository)) -> DeleteBudgetItemUseCase:
    return DeleteBudgetItemUseCase(repository)


@router.get("/projects/{project_id}/budget", response_model=BudgetResponse)
async def get_project_budget(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: GetBudgetUseCase = Depends(get_budget_use_case),
) -> BudgetResponse:
    """Get budget summary for a project."""
    return await use_case.execute(project_id, tenant_id)


@router.post("/projects/{project_id}/budget/items", response_model=BudgetItemResponse, status_code=http_status.HTTP_201_CREATED)
async def create_budget_item(
    project_id: UUID,
    item_create: BudgetItemCreate,
    tenant_id: CurrentTenantId,
    use_case: CreateBudgetItemUseCase = Depends(get_create_budget_item_use_case),
) -> BudgetItemResponse:
    """Create a new budget item for a project."""
    return await use_case.execute(project_id, tenant_id, item_create)


@router.patch("/budget/items/{item_id}", response_model=BudgetItemResponse)
async def update_budget_item(
    item_id: UUID,
    item_update: BudgetItemUpdate,
    tenant_id: CurrentTenantId,
    use_case: UpdateBudgetItemUseCase = Depends(get_update_budget_item_use_case),
) -> BudgetItemResponse:
    """Update an existing budget item."""
    try:
        return await use_case.execute(item_id, tenant_id, item_update)
    except ValueError as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/budget/items/{item_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_budget_item(
    item_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: DeleteBudgetItemUseCase = Depends(get_delete_budget_item_use_case),
) -> None:
    """Delete a budget item."""
    deleted = await use_case.execute(item_id, tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Budget item not found"
        )
    return None
