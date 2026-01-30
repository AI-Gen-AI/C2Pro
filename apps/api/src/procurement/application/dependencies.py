from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.procurement.adapters.persistence import SQLAlchemyWBSRepository, SQLAlchemyBOMRepository


def get_wbs_repository(
    db: AsyncSession = Depends(get_session),
) -> SQLAlchemyWBSRepository:
    return SQLAlchemyWBSRepository(session=db)


def get_bom_repository(
    db: AsyncSession = Depends(get_session),
) -> SQLAlchemyBOMRepository:
    return SQLAlchemyBOMRepository(session=db)
