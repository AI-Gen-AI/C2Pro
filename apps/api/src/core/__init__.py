"""
C2Pro Core Module

Funcionalidades compartidas: database, security, middleware, MCP, etc.

Uses lazy imports (PEP 562) so that ``import src.core`` or
``from src.core import X`` only loads the submodule that provides *X*
on first access, instead of eagerly pulling in the entire infrastructure
stack (database, JWT, cryptography, Sentry, Redis, Anthropic …).
"""

from __future__ import annotations

import importlib
from typing import Any

# ── Mapping: attribute → (module_path, attribute_name) ──────────────────────

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Database
    "Base":                    ("src.core.database", "Base"),
    "get_session":             ("src.core.database", "get_session"),
    "get_session_with_tenant": ("src.core.database", "get_session_with_tenant"),
    "init_db":                 ("src.core.database", "init_db"),
    "close_db":                ("src.core.database", "close_db"),
    # Security
    "get_current_tenant_id":   ("src.core.security", "get_current_tenant_id"),
    "get_current_user_id":     ("src.core.security", "get_current_user_id"),
    "CurrentTenantId":         ("src.core.security", "CurrentTenantId"),
    "CurrentUserId":           ("src.core.security", "CurrentUserId"),
    "Permissions":             ("src.core.security", "Permissions"),
    # Exceptions (lightweight — still eager would be fine, but consistent)
    "C2ProException":          ("src.core.exceptions", "C2ProException"),
    "AuthenticationError":     ("src.core.exceptions", "AuthenticationError"),
    "AuthorizationError":      ("src.core.exceptions", "AuthorizationError"),
    "ResourceNotFoundError":   ("src.core.exceptions", "ResourceNotFoundError"),
    "ValidationError":         ("src.core.exceptions", "ValidationError"),
    "AIServiceError":          ("src.core.exceptions", "AIServiceError"),
    "AIBudgetExceededError":   ("src.core.exceptions", "AIBudgetExceededError"),
    # MCP
    "DatabaseMCPServer":       ("src.core.mcp.servers.database_server", "DatabaseMCPServer"),
    "get_mcp_server":          ("src.core.mcp.servers.database_server", "get_mcp_server"),
    # Auth
    "User":                    ("src.core.auth.models", "User"),
    "Tenant":                  ("src.core.auth.models", "Tenant"),
    "UserRole":                ("src.core.auth.models", "UserRole"),
    "SubscriptionPlan":        ("src.core.auth.models", "SubscriptionPlan"),
    "AuthService":             ("src.core.auth.service", "AuthService"),
    "LoginRequest":            ("src.core.auth.schemas", "LoginRequest"),
    "LoginResponse":           ("src.core.auth.schemas", "LoginResponse"),
    "RegisterRequest":         ("src.core.auth.schemas", "RegisterRequest"),
    "RegisterResponse":        ("src.core.auth.schemas", "RegisterResponse"),
    "TokenResponse":           ("src.core.auth.schemas", "TokenResponse"),
    "create_access_token":     ("src.core.auth.service", "create_access_token"),
    "decode_token":            ("src.core.auth.service", "decode_token"),
    "hash_password":           ("src.core.auth.service", "hash_password"),
    "verify_password":         ("src.core.auth.service", "verify_password"),
    # Observability
    "configure_logging":       ("src.core.observability", "configure_logging"),
    "init_sentry":             ("src.core.observability", "init_sentry"),
    "get_version":             ("src.core.observability", "get_version"),
    "record_request_metric":   ("src.core.observability", "record_request_metric"),
    "record_ai_metric":        ("src.core.observability", "record_ai_metric"),
    "record_cache_hit":        ("src.core.observability", "record_cache_hit"),
    "record_cache_miss":       ("src.core.observability", "record_cache_miss"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(module_path)
        value = getattr(mod, attr)
        # Cache on the module so subsequent access is fast (no __getattr__)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'src.core' has no attribute {name!r}")
