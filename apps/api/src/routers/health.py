"""
C2Pro - Health Check Router

Provides endpoints for monitoring application health, essential for container
orchestrators like Kubernetes and uptime monitoring services.
"""

import asyncio
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from redis.exceptions import RedisError

from src.core.database import get_session
from src.core.cache import get_cache_service, CacheService

logger = structlog.get_logger()

# ===========================================
# ROUTER SETUP
# ===========================================

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)

# Timeout for dependency checks in seconds
HEALTH_CHECK_TIMEOUT = 2

# ===========================================
# LIVENESS PROBE
# ===========================================

@router.get(
    "/live",
    summary="Liveness Probe",
    description="Checks if the application process is running. This should not have external dependencies."
)
async def liveness_check():
    """
    Checks if the application process is running (liveness).

    This endpoint is used by container orchestrators (like Kubernetes) to
    determine if the container needs to be restarted. It should be lightweight
    and not depend on external services like databases.
    """
    return {"status": "ok"}


# ===========================================
# READINESS PROBE
# ===========================================

@router.get(
    "/ready",
    summary="Readiness Probe",
    description="Checks if the application is ready to accept traffic by verifying connections to dependencies."
)
async def readiness_check(
    db: AsyncSession = Depends(get_session),
    cache: CacheService = Depends(get_cache_service)
):
    """
    Checks if the application is ready to handle requests.

    This endpoint verifies connectivity to essential services like the database
    and cache (Redis). A 503 Service Unavailable error will be returned if any
    dependency is not reachable, signaling to the load balancer to stop
    sending traffic to this instance.
    """
    db_status = "down"
    redis_status = "down"

    # Check Database
    try:
        # Execute a simple query with a timeout
        await asyncio.wait_for(
            db.execute(text("SELECT 1")),
            timeout=HEALTH_CHECK_TIMEOUT
        )
        db_status = "up"
    except asyncio.TimeoutError:
        logger.error("health_check_db_timeout")
    except Exception as e:
        logger.error("health_check_db_failed", error=str(e))

    # Check Redis Cache
    if cache and cache.enabled:
        try:
            # The service's ping method has its own internal timeout
            is_redis_ok = await asyncio.wait_for(
                cache.ping(),
                timeout=HEALTH_CHECK_TIMEOUT
            )
            if is_redis_ok:
                redis_status = "up"
        except asyncio.TimeoutError:
            logger.error("health_check_redis_timeout")
        except RedisError as e:
            logger.error("health_check_redis_failed", error=str(e))
    elif cache:
        # Cache is enabled but not using Redis (e.g., in-memory fallback)
        redis_status = "in_memory_fallback"
    else:
        # Cache is not configured for this environment
        redis_status = "not_configured"

    # Evaluate results
    if db_status == "up" and redis_status in ["up", "in_memory_fallback", "not_configured"]:
        return {"database": db_status, "redis": redis_status}
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"database": db_status, "redis": redis_status},
        )


# ===========================================
# GENERIC HEALTH ALIAS
# ===========================================

@router.get(
    "/",
    summary="Generic Health Check",
    description="Alias for the readiness probe. Useful for simple uptime monitors."
)
async def generic_health_check(
    db: AsyncSession = Depends(get_session),
    cache: CacheService = Depends(get_cache_service)
):
    """
    A simple alias for the /ready endpoint.
    """
    return await readiness_check(db, cache)
