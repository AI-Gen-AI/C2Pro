"""
C2Pro - Core Middleware Module

Infraestructura de middleware: tenant isolation, request logging, rate limiting, API contract.
Includes Clerk authentication middleware for JWT verification.
"""

import structlog

from src.config import settings
from src.core.middleware.api_contract import APIContractMiddleware
from src.core.middleware.clerk_auth import (
    ClerkAuthMiddleware,
    ClerkTokenVerificationError,
    ClerkUser,
    get_clerk_user,
    get_current_tenant_id,
    require_admin,
    require_organization,
    require_tenant,
)
from src.core.middleware.rate_limiter import RateLimitMiddleware
from src.core.middleware.request_logging import RequestLoggingMiddleware, logger
from src.core.middleware.tenant_isolation import TenantIsolationMiddleware

__all__ = [
    "APIContractMiddleware",
    "ClerkAuthMiddleware",
    "ClerkTokenVerificationError",
    "ClerkUser",
    "RateLimitMiddleware",
    "RequestLoggingMiddleware",
    "TenantIsolationMiddleware",
    "get_clerk_user",
    "get_current_tenant_id",
    "logger",
    "require_admin",
    "require_organization",
    "require_tenant",
    "settings",
    "structlog",
]
