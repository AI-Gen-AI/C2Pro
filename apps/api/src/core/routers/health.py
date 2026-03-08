"""
C2Pro - Health Check Router

Provides endpoints for monitoring application health, essential for container
orchestrators like Kubernetes and uptime monitoring services.

Note: Health endpoints use get_raw_session (no tenant context) since they
are typically called by load balancers without authentication.
"""

import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from redis.exceptions import RedisError
from sqlalchemy import text

from src.core.cache import get_cache_service
from src.core.database import get_raw_session
from src.core.resilience import CircuitBreakerRegistry, CircuitBreakerState

logger = structlog.get_logger()

# Critical services that affect readiness
CRITICAL_CIRCUIT_BREAKER_SERVICES = ["anthropic_llm", "openai_embeddings", "r2_storage"]

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
async def readiness_check():
    """
    Checks if the application is ready to handle requests.

    This endpoint verifies connectivity to essential services like the database
    and cache (Redis). A 503 Service Unavailable error will be returned if any
    dependency is not reachable, signaling to the load balancer to stop
    sending traffic to this instance.

    Also reports circuit breaker status for critical services.
    """
    db_status = "down"
    redis_status = "down"

    # Check Database (using raw session - no tenant context needed for health)
    try:
        async with get_raw_session() as db:
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
    cache = get_cache_service()
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

    # Check circuit breakers
    circuit_breakers = _get_circuit_breaker_summary()
    critical_circuits_ok = not any(
        cb.get("state") == "open"
        for name, cb in circuit_breakers.items()
        if name in CRITICAL_CIRCUIT_BREAKER_SERVICES
    )

    # Evaluate results
    is_healthy = (
        db_status == "up"
        and redis_status in ["up", "in_memory_fallback", "not_configured"]
    )

    # Determine overall status
    if is_healthy and critical_circuits_ok:
        overall_status = "healthy"
    elif is_healthy and not critical_circuits_ok:
        overall_status = "degraded"  # Core services up but external circuits tripped
    else:
        overall_status = "unhealthy"

    result = {
        "status": overall_status,
        "database": db_status,
        "redis": redis_status,
        "circuit_breakers": circuit_breakers,
    }

    if overall_status == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result,
        )

    return result


def _get_circuit_breaker_summary() -> dict[str, dict[str, Any]]:
    """Get summary of all circuit breakers for health check."""
    all_status = CircuitBreakerRegistry.get_all_health_status()

    # Return simplified view for readiness
    return {
        name: {
            "state": status["state"],
            "failure_count": status["failure_count"],
            "failure_threshold": status["failure_threshold"],
        }
        for name, status in all_status.items()
    }


# ===========================================
# CIRCUIT BREAKER STATUS
# ===========================================

@router.get(
    "/circuit-breakers",
    summary="Circuit Breaker Status",
    description="Detailed status of all circuit breakers for external services."
)
async def circuit_breaker_status():
    """
    Get detailed status of all circuit breakers.

    Returns full statistics for each registered circuit breaker including:
    - Current state (closed/open/half_open)
    - Failure counts and thresholds
    - Recovery timeout information
    - Request statistics (total, successful, failed, rejected)
    """
    all_status = CircuitBreakerRegistry.get_all_health_status()
    open_circuits = CircuitBreakerRegistry.get_open_circuits()

    return {
        "total_breakers": len(all_status),
        "open_circuits": open_circuits,
        "breakers": all_status,
    }


# ===========================================
# GENERIC HEALTH ALIAS
# ===========================================

@router.get(
    "",
    summary="Generic Health Check",
    description="Alias for the readiness probe. Useful for simple uptime monitors."
)
async def generic_health_check():
    """
    A simple alias for the /ready endpoint.
    """
    return await readiness_check()
