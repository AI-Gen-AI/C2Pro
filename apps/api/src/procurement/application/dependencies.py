"""
I9 Procurement dependency providers.
Test Suite ID: TS-I9-PROC-HTTP-001
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.procurement.adapters.persistence import SQLAlchemyBOMRepository, SQLAlchemyWBSRepository
from src.procurement.application.use_cases import (
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


def get_wbs_repository(
    db: AsyncSession = Depends(get_session),
) -> SQLAlchemyWBSRepository:
    return SQLAlchemyWBSRepository(session=db)


def get_bom_repository(
    db: AsyncSession = Depends(get_session),
) -> SQLAlchemyBOMRepository:
    return SQLAlchemyBOMRepository(session=db)


def get_create_wbs_item_use_case(
    repository: SQLAlchemyWBSRepository = Depends(get_wbs_repository),
) -> CreateWBSItemUseCase:
    return CreateWBSItemUseCase(repository)


def get_list_wbs_items_use_case(
    repository: SQLAlchemyWBSRepository = Depends(get_wbs_repository),
) -> ListWBSItemsUseCase:
    return ListWBSItemsUseCase(repository)


def get_wbs_tree_use_case(
    repository: SQLAlchemyWBSRepository = Depends(get_wbs_repository),
) -> GetWBSTreeUseCase:
    return GetWBSTreeUseCase(repository)


def get_wbs_item_use_case(
    repository: SQLAlchemyWBSRepository = Depends(get_wbs_repository),
) -> GetWBSItemUseCase:
    return GetWBSItemUseCase(repository)


def get_update_wbs_item_use_case(
    repository: SQLAlchemyWBSRepository = Depends(get_wbs_repository),
) -> UpdateWBSItemUseCase:
    return UpdateWBSItemUseCase(repository)


def get_delete_wbs_item_use_case(
    repository: SQLAlchemyWBSRepository = Depends(get_wbs_repository),
) -> DeleteWBSItemUseCase:
    return DeleteWBSItemUseCase(repository)


def get_create_bom_item_use_case(
    repository: SQLAlchemyBOMRepository = Depends(get_bom_repository),
) -> CreateBOMItemUseCase:
    return CreateBOMItemUseCase(repository)


def get_list_bom_items_use_case(
    repository: SQLAlchemyBOMRepository = Depends(get_bom_repository),
) -> ListBOMItemsUseCase:
    return ListBOMItemsUseCase(repository)


def get_bom_item_use_case(
    repository: SQLAlchemyBOMRepository = Depends(get_bom_repository),
) -> GetBOMItemUseCase:
    return GetBOMItemUseCase(repository)


def get_update_bom_item_use_case(
    repository: SQLAlchemyBOMRepository = Depends(get_bom_repository),
) -> UpdateBOMItemUseCase:
    return UpdateBOMItemUseCase(repository)


def get_update_bom_status_use_case(
    repository: SQLAlchemyBOMRepository = Depends(get_bom_repository),
) -> UpdateBOMStatusUseCase:
    return UpdateBOMStatusUseCase(repository)


def get_delete_bom_item_use_case(
    repository: SQLAlchemyBOMRepository = Depends(get_bom_repository),
) -> DeleteBOMItemUseCase:
    return DeleteBOMItemUseCase(repository)
