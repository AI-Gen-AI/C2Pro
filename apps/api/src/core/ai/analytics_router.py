from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.ai.analytics_service import AIAnalyticsService
from src.core.cache import get_cache_service
from src.core.database import get_session
from src.core.security import CurrentTenantId

router = APIRouter(prefix="/ai/analytics", tags=["AI Analytics"])


def get_analytics_service(db: AsyncSession = Depends(get_session)) -> AIAnalyticsService:
    return AIAnalyticsService(db=db, cache=get_cache_service())


@router.get("/cost", summary="Cost and token analytics over time")
async def get_cost_analytics(
    tenant_id: CurrentTenantId,
    timeframe: str = Query(default="7d", examples=["24h", "7d", "30d"]),
    service: AIAnalyticsService = Depends(get_analytics_service),
) -> dict:
    try:
        return await service.cost_breakdown(tenant_id=tenant_id, timeframe=timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/versions", summary="Prompt version leaderboard and quality performance")
async def get_version_analytics(
    tenant_id: CurrentTenantId,
    timeframe: str = Query(default="30d", examples=["7d", "30d", "90d"]),
    service: AIAnalyticsService = Depends(get_analytics_service),
) -> dict:
    try:
        return await service.version_performance(tenant_id=tenant_id, timeframe=timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/comparison", summary="Compare two prompt versions")
async def compare_prompt_versions(
    tenant_id: CurrentTenantId,
    baseline_version: str = Query(min_length=1),
    candidate_version: str = Query(min_length=1),
    timeframe: str = Query(default="30d", examples=["7d", "30d", "90d"]),
    service: AIAnalyticsService = Depends(get_analytics_service),
) -> dict:
    try:
        return await service.compare_versions(
            tenant_id=tenant_id,
            timeframe=timeframe,
            baseline_version=baseline_version,
            candidate_version=candidate_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/quality-drift", summary="Detect quality and latency drift")
async def get_quality_drift(
    tenant_id: CurrentTenantId,
    timeframe: str = Query(default="30d", examples=["7d", "30d", "90d"]),
    service: AIAnalyticsService = Depends(get_analytics_service),
) -> dict:
    try:
        return await service.quality_drift(tenant_id=tenant_id, timeframe=timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
