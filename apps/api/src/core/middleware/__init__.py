"""
C2Pro - Core Middleware Module

Infraestructura de middleware: tenant isolation, request logging, rate limiting.

Uses lazy imports (PEP 562) to avoid pulling in settings and
structlog at ``import src.core.middleware`` time.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "TenantIsolationMiddleware": ("src.core.middleware.tenant_isolation", "TenantIsolationMiddleware"),
    "RequestLoggingMiddleware":  ("src.core.middleware.request_logging", "RequestLoggingMiddleware"),
    "RateLimitMiddleware":       ("src.core.middleware.rate_limiter", "RateLimitMiddleware"),
    "require_feature":           ("src.core.middleware.feature_flags", "require_feature"),
    "logger":                    ("src.core.middleware.request_logging", "logger"),
    "settings":                  ("src.config", "settings"),
    "structlog":                 ("structlog", "structlog"),
}

__all__ = [
    "TenantIsolationMiddleware",
    "RequestLoggingMiddleware",
    "RateLimitMiddleware",
    "require_feature",
    "logger",
    "settings",
]


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(module_path)
        # For top-level modules (structlog), return the module itself
        value = mod if attr == module_path else getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'src.core.middleware' has no attribute {name!r}")
