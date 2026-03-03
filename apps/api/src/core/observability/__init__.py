"""
C2Pro - Core Observability Module

Infraestructura de observabilidad: logging, métricas, error tracking, y endpoints de monitoreo.

Uses lazy imports (PEP 562) to avoid pulling in Sentry SDK,
prometheus_client, and structlog at ``import src.core.observability`` time.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Monitoring (logging, sentry, prometheus)
    "configure_logging":     ("src.core.observability.monitoring", "configure_logging"),
    "init_sentry":           ("src.core.observability.monitoring", "init_sentry"),
    "get_version":           ("src.core.observability.monitoring", "get_version"),
    "record_request_metric": ("src.core.observability.monitoring", "record_request_metric"),
    "record_ai_metric":      ("src.core.observability.monitoring", "record_ai_metric"),
    "record_cache_hit":      ("src.core.observability.monitoring", "record_cache_hit"),
    "record_cache_miss":     ("src.core.observability.monitoring", "record_cache_miss"),
    "METRICS_AVAILABLE":     ("src.core.observability.monitoring", "METRICS_AVAILABLE"),
    # Service
    "ObservabilityService":  ("src.core.observability.service", "ObservabilityService"),
    # Schemas
    "SystemStatusResponse":   ("src.core.observability.schemas", "SystemStatusResponse"),
    "RecentAnalysesResponse": ("src.core.observability.schemas", "RecentAnalysesResponse"),
    "AnalysisStatus":         ("src.core.observability.schemas", "AnalysisStatus"),
    # Router
    "router":                ("src.core.observability.router", "router"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(module_path)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'src.core.observability' has no attribute {name!r}")
