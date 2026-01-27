"""
C2Pro - Core Observability Module

Infraestructura de observabilidad: logging, métricas, error tracking, y endpoints de monitoreo.
"""

# Monitoring (logging, sentry, prometheus)
from src.core.observability.monitoring import (
    METRICS_AVAILABLE,
    configure_logging,
    get_version,
    init_sentry,
    record_ai_metric,
    record_cache_hit,
    record_cache_miss,
    record_request_metric,
)

# Service & Router (endpoints de monitoreo)
from src.core.observability.router import router
from src.core.observability.schemas import (
    AnalysisStatus,
    RecentAnalysesResponse,
    SystemStatusResponse,
)
from src.core.observability.service import ObservabilityService

__all__ = [
    # Monitoring
    "configure_logging",
    "init_sentry",
    "get_version",
    "record_request_metric",
    "record_ai_metric",
    "record_cache_hit",
    "record_cache_miss",
    "METRICS_AVAILABLE",
    # Service
    "ObservabilityService",
    # Schemas
    "SystemStatusResponse",
    "RecentAnalysesResponse",
    "AnalysisStatus",
    # Router
    "router",
]
