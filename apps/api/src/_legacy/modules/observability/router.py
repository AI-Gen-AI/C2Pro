from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.modules.observability.schemas import RecentAnalysesResponse, SystemStatusResponse
from src.modules.observability.service import ObservabilityService

router = APIRouter()


@router.get("/status", response_model=SystemStatusResponse, summary="Get system health status")
async def get_system_status(db: AsyncSession = Depends(get_session)):
    """
    Retrieves the overall health status of the API and its dependencies, such as the database.
    """
    service = ObservabilityService(db_session=db)
    return await service.get_system_status()


@router.get(
    "/analyses", response_model=RecentAnalysesResponse, summary="Get recent coherence analyses"
)
async def get_recent_analyses(
    limit: int = 10, offset: int = 0, db: AsyncSession = Depends(get_session)
):
    """
    Retrieves a list of recent coherence analysis runs with their status and key metrics.
    """
    service = ObservabilityService(db_session=db)
    return await service.get_recent_analyses(limit=limit, offset=offset)
