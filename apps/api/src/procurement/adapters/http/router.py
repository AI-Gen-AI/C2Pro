"""
FastAPI router for the Procurement module (WBS and BOM operations).
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.security import CurrentTenantId

# Repositories
from src.procurement.adapters.persistence import SQLAlchemyWBSRepository, SQLAlchemyBOMRepository

# Use cases
from src.procurement.application.use_cases import (
    CreateWBSItemUseCase,
    ListWBSItemsUseCase,
    GetWBSItemUseCase,
    UpdateWBSItemUseCase,
    DeleteWBSItemUseCase,
    GetWBSTreeUseCase,
    CreateBOMItemUseCase,
    ListBOMItemsUseCase,
    GetBOMItemUseCase,
    UpdateBOMItemUseCase,
    DeleteBOMItemUseCase,
    UpdateBOMStatusUseCase,
)

# DTOs
from src.procurement.application.dtos import (
    WBSItemCreate,
    WBSItemUpdate,
    WBSItemResponse,
    BOMItemCreate,
    BOMItemUpdate,
    BOMItemResponse,
    ProcurementPlanningRequest,
    PlanningDecision,
)
from src.procurement.domain.models import ProcurementStatus
from src.procurement.application.planning_service import (
    ProcurementPlanningService,
    ProcurementSnapshotRepository,
    ProcurementDecisionRepository,
    ProcurementUnitOfWork,
)
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

router = APIRouter(prefix="/procurement", tags=["procurement"])


# ==========================================
# PLANNING ENDPOINTS
# ==========================================


class UnconfiguredSnapshotRepo:
    async def get_snapshot_items(self, project_id, tenant_id, required_on_site):
        raise RuntimeError("Unconfigured procurement snapshot repository")


class UnconfiguredDecisionRepo:
    async def save_plan_items(self, project_id, tenant_id, items):
        raise RuntimeError("Unconfigured procurement decision repository")

    async def save_conflicts(self, project_id, tenant_id, conflicts):
        raise RuntimeError("Unconfigured procurement decision repository")


class UnconfiguredUoW:
    async def commit(self):
        raise RuntimeError("Unconfigured procurement unit of work")

    async def rollback(self):
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


@router.post("/planning", response_model=PlanningDecision)
async def build_procurement_plan(
    payload: ProcurementPlanningRequest,
    tenant_id: CurrentTenantId,
    service: ProcurementPlanningService = Depends(get_planning_service),
):
    """
    Build a tenant-scoped procurement plan for a project snapshot.
    """
    try:
        return await service.build_procurement_plan(
            project_id=payload.project_id,
            tenant_id=tenant_id,
            required_on_site=payload.required_on_site,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Procurement planning failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Procurement planning failed: {str(e)}"
        )


# ==========================================
# WBS ENDPOINTS
# ==========================================


@router.post("/wbs", response_model=WBSItemResponse, status_code=status.HTTP_201_CREATED)
async def create_wbs_item(
    wbs_create: WBSItemCreate,
    tenant_id: CurrentTenantId,
    use_case: CreateWBSItemUseCase = Depends(get_create_wbs_item_use_case),
):
    """
    Create a new WBS item.
    """
    try:
        wbs_item = await use_case.execute(wbs_create, tenant_id)
        return WBSItemResponse.model_validate(wbs_item)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create WBS item: {str(e)}"
        )


@router.get("/wbs/project/{project_id}", response_model=List[WBSItemResponse])
async def list_wbs_items(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: ListWBSItemsUseCase = Depends(get_list_wbs_items_use_case),
):
    """
    List all WBS items for a project.
    """
    wbs_items = await use_case.execute(project_id, tenant_id)
    return [WBSItemResponse.model_validate(item) for item in wbs_items]


@router.get("/wbs/project/{project_id}/tree", response_model=List[WBSItemResponse])
async def get_wbs_tree(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: GetWBSTreeUseCase = Depends(get_wbs_tree_use_case),
):
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
):
    """
    Get a specific WBS item by ID.
    """
    wbs_item = await use_case.execute(wbs_id, tenant_id)
    if not wbs_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WBS item not found"
        )

    return WBSItemResponse.model_validate(wbs_item)


@router.put("/wbs/{wbs_id}", response_model=WBSItemResponse)
async def update_wbs_item(
    wbs_id: UUID,
    wbs_update: WBSItemUpdate,
    tenant_id: CurrentTenantId,
    use_case: UpdateWBSItemUseCase = Depends(get_update_wbs_item_use_case),
):
    """
    Update a WBS item.
    """
    wbs_item = await use_case.execute(wbs_id, wbs_update, tenant_id)
    if not wbs_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WBS item not found"
        )

    return WBSItemResponse.model_validate(wbs_item)


@router.delete("/wbs/{wbs_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wbs_item(
    wbs_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: DeleteWBSItemUseCase = Depends(get_delete_wbs_item_use_case),
):
    """
    Delete a WBS item and its children (cascade).
    """
    deleted = await use_case.execute(wbs_id, tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WBS item not found"
        )

    return None


# ==========================================
# BOM ENDPOINTS
# ==========================================


@router.post("/bom", response_model=BOMItemResponse, status_code=status.HTTP_201_CREATED)
async def create_bom_item(
    bom_create: BOMItemCreate,
    tenant_id: CurrentTenantId,
    use_case: CreateBOMItemUseCase = Depends(get_create_bom_item_use_case),
):
    """
    Create a new BOM item.
    """
    try:
        bom_item = await use_case.execute(bom_create, tenant_id)
        return BOMItemResponse.model_validate(bom_item)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create BOM item: {str(e)}"
        )


@router.get("/bom/project/{project_id}", response_model=List[BOMItemResponse])
async def list_bom_items(
    project_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: ListBOMItemsUseCase = Depends(get_list_bom_items_use_case),
):
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
):
    """
    Get a specific BOM item by ID.
    """
    bom_item = await use_case.execute(bom_id, tenant_id)
    if not bom_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BOM item not found"
        )

    return BOMItemResponse.model_validate(bom_item)


@router.put("/bom/{bom_id}", response_model=BOMItemResponse)
async def update_bom_item(
    bom_id: UUID,
    bom_update: BOMItemUpdate,
    tenant_id: CurrentTenantId,
    use_case: UpdateBOMItemUseCase = Depends(get_update_bom_item_use_case),
):
    """
    Update a BOM item.
    """
    bom_item = await use_case.execute(bom_id, bom_update, tenant_id)
    if not bom_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BOM item not found"
        )

    return BOMItemResponse.model_validate(bom_item)


@router.patch("/bom/{bom_id}/status", response_model=BOMItemResponse)
async def update_bom_status(
    bom_id: UUID,
    status: ProcurementStatus,
    tenant_id: CurrentTenantId,
    use_case: UpdateBOMStatusUseCase = Depends(get_update_bom_status_use_case),
):
    """
    Update the procurement status of a BOM item.
    """
    bom_item = await use_case.execute(bom_id, status, tenant_id)
    if not bom_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BOM item not found"
        )

    return BOMItemResponse.model_validate(bom_item)


@router.delete("/bom/{bom_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bom_item(
    bom_id: UUID,
    tenant_id: CurrentTenantId,
    use_case: DeleteBOMItemUseCase = Depends(get_delete_bom_item_use_case),
):
    """
    Delete a BOM item.
    """
    deleted = await use_case.execute(bom_id, tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BOM item not found"
        )

    return None
