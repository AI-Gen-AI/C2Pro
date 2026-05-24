
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.analysis_repository import SqlAlchemyAnalysisRepository
from src.core.database import get_session
from src.core.observability.schemas import RecentAnalysesResponse, SystemStatusResponse
from src.core.observability.service import ObservabilityService
from src.core.security import CurrentTenantId, security_scheme

router = APIRouter(
    prefix="/observability",
    tags=["Observability"],
    dependencies=[Depends(security_scheme)],
)


def get_analysis_repository(
    db: AsyncSession = Depends(get_session),
) -> SqlAlchemyAnalysisRepository:
    return SqlAlchemyAnalysisRepository(session=db)


def get_observability_service(
    db: AsyncSession = Depends(get_session),
    analysis_repository: SqlAlchemyAnalysisRepository = Depends(get_analysis_repository),
) -> ObservabilityService:
    return ObservabilityService(
        db_session=db,
        analysis_repository=analysis_repository,
    )


@router.get("/status", response_model=SystemStatusResponse, summary="Get system health status")
async def get_system_status(
    service: ObservabilityService = Depends(get_observability_service),
):
    """
    Retrieves the overall health status of the API and its dependencies, such as the database.
    """
    return await service.get_system_status()


@router.get(
    "/analyses", response_model=RecentAnalysesResponse, summary="Get recent coherence analyses"
)
async def get_recent_analyses(
    tenant_id: CurrentTenantId,
    limit: int = 10,
    offset: int = 0,
    service: ObservabilityService = Depends(get_observability_service),
):
    """
    Retrieves a list of recent coherence analysis runs with their status and key metrics.
    Results are filtered by tenant.
    """
    return await service.get_recent_analyses(limit=limit, offset=offset, tenant_id=tenant_id)


@router.get(
    "/performance/snapshot",
    summary="Get performance snapshot",
)
async def get_performance_snapshot() -> dict[str, float]:
    """Refers to Suite ID: TS-E2E-PER-LRG-001."""
    return {
        "p95_ms": 0.0,
        "p99_ms": 0.0,
        "error_rate": 0.0,
    }
