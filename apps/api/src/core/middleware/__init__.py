"""
C2Pro - Core Middleware Module

Infraestructura de middleware: tenant isolation, request logging, rate limiting.
"""

import structlog

from src.config import settings
from src.core.middleware.rate_limiter import RateLimitMiddleware
from src.core.middleware.request_logging import RequestLoggingMiddleware, logger
from src.core.middleware.tenant_isolation import TenantIsolationMiddleware

__all__ = [
    "TenantIsolationMiddleware",
    "RequestLoggingMiddleware",
    "RateLimitMiddleware",
    "logger",
    "settings",
    "structlog",
]
