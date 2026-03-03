"""
C2Pro - Core Middleware Module

Infraestructura de middleware: tenant isolation, request logging, rate limiting, API contract.
Includes Clerk authentication middleware for JWT verification.

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
    "APIContractMiddleware":     ("src.core.middleware.api_contract", "APIContractMiddleware"),
    "ClerkAuthMiddleware":       ("src.core.middleware.clerk_auth", "ClerkAuthMiddleware"),
    "ClerkTokenVerificationError": ("src.core.middleware.clerk_auth", "ClerkTokenVerificationError"),
    "ClerkUser":                 ("src.core.middleware.clerk_auth", "ClerkUser"),
    "get_clerk_user":            ("src.core.middleware.clerk_auth", "get_clerk_user"),
    "get_current_tenant_id":     ("src.core.middleware.clerk_auth", "get_current_tenant_id"),
    "require_admin":             ("src.core.middleware.clerk_auth", "require_admin"),
    "require_organization":      ("src.core.middleware.clerk_auth", "require_organization"),
    "require_tenant":            ("src.core.middleware.clerk_auth", "require_tenant"),
    "require_feature":           ("src.core.middleware.feature_flags", "require_feature"),
    "logger":                    ("src.core.middleware.request_logging", "logger"),
    "settings":                  ("src.config", "settings"),
}

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
    "require_feature",
    "require_organization",
    "require_tenant",
    "settings",
]


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(module_path)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'src.core.middleware' has no attribute {name!r}")
