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
)
from src.procurement.domain.models import ProcurementStatus

router = APIRouter(prefix="/procurement", tags=["procurement"])


# ==========================================
# WBS ENDPOINTS
# ==========================================


@router.post("/wbs", response_model=WBSItemResponse, status_code=status.HTTP_201_CREATED)
async def create_wbs_item(
    wbs_create: WBSItemCreate,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(CurrentTenantId),
):
    """
    Create a new WBS item.
    """
    repository = SQLAlchemyWBSRepository(session)
    use_case = CreateWBSItemUseCase(repository)

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
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(CurrentTenantId),
):
    """
    List all WBS items for a project.
    """
    repository = SQLAlchemyWBSRepository(session)
    use_case = ListWBSItemsUseCase(repository)

    wbs_items = await use_case.execute(project_id, tenant_id)
    return [WBSItemResponse.model_validate(item) for item in wbs_items]


@router.get("/wbs/project/{project_id}/tree", response_model=List[WBSItemResponse])
async def get_wbs_tree(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(CurrentTenantId),
):
    """
    Get the complete WBS tree for a project with hierarchy.
    """
    repository = SQLAlchemyWBSRepository(session)
    use_case = GetWBSTreeUseCase(repository)

    wbs_tree = await use_case.execute(project_id, tenant_id)
    return [WBSItemResponse.model_validate(item) for item in wbs_tree]


@router.get("/wbs/{wbs_id}", response_model=WBSItemResponse)
async def get_wbs_item(
    wbs_id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(CurrentTenantId),
):
    """
    Get a specific WBS item by ID.
    """
    repository = SQLAlchemyWBSRepository(session)
    use_case = GetWBSItemUseCase(repository)

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
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(CurrentTenantId),
):
    """
    Update a WBS item.
    """
    repository = SQLAlchemyWBSRepository(session)
    use_case = UpdateWBSItemUseCase(repository)

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
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(CurrentTenantId),
):
    """
    Delete a WBS item and its children (cascade).
    """
    repository = SQLAlchemyWBSRepository(session)
    use_case = DeleteWBSItemUseCase(repository)

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
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(CurrentTenantId),
):
    """
    Create a new BOM item.
    """
    repository = SQLAlchemyBOMRepository(session)
    use_case = CreateBOMItemUseCase(repository)

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
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(CurrentTenantId),
):
    """
    List all BOM items for a project.
    """
    repository = SQLAlchemyBOMRepository(session)
    use_case = ListBOMItemsUseCase(repository)

    bom_items = await use_case.execute(project_id, tenant_id)
    return [BOMItemResponse.model_validate(item) for item in bom_items]


@router.get("/bom/{bom_id}", response_model=BOMItemResponse)
async def get_bom_item(
    bom_id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(CurrentTenantId),
):
    """
    Get a specific BOM item by ID.
    """
    repository = SQLAlchemyBOMRepository(session)
    use_case = GetBOMItemUseCase(repository)

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
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(CurrentTenantId),
):
    """
    Update a BOM item.
    """
    repository = SQLAlchemyBOMRepository(session)
    use_case = UpdateBOMItemUseCase(repository)

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
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(CurrentTenantId),
):
    """
    Update the procurement status of a BOM item.
    """
    repository = SQLAlchemyBOMRepository(session)
    use_case = UpdateBOMStatusUseCase(repository)

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
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(CurrentTenantId),
):
    """
    Delete a BOM item.
    """
    repository = SQLAlchemyBOMRepository(session)
    use_case = DeleteBOMItemUseCase(repository)

    deleted = await use_case.execute(bom_id, tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BOM item not found"
        )

    return None
