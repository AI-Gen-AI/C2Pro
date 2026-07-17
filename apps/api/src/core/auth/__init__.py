"""
C2Pro - Core Authentication Module

Infraestructura transversal de autenticación y multi-tenancy.

Uses lazy imports (PEP 562) to avoid pulling in JWT, cryptography,
bcrypt, and database drivers at ``import src.core.auth`` time.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Models
    "User":             ("src.core.auth.models", "User"),
    "Tenant":           ("src.core.auth.models", "Tenant"),
    "UserRole":         ("src.core.auth.models", "UserRole"),
    "SubscriptionPlan": ("src.core.auth.models", "SubscriptionPlan"),
    # Schemas
    "LoginRequest":          ("src.core.auth.schemas", "LoginRequest"),
    "LoginResponse":         ("src.core.auth.schemas", "LoginResponse"),
    "RegisterRequest":       ("src.core.auth.schemas", "RegisterRequest"),
    "RegisterResponse":      ("src.core.auth.schemas", "RegisterResponse"),
    "TokenResponse":         ("src.core.auth.schemas", "TokenResponse"),
    "TokenPayload":          ("src.core.auth.schemas", "TokenPayload"),
    "RefreshTokenRequest":   ("src.core.auth.schemas", "RefreshTokenRequest"),
    "MeResponse":            ("src.core.auth.schemas", "MeResponse"),
    "UserResponse":          ("src.core.auth.schemas", "UserResponse"),
    "TenantResponse":        ("src.core.auth.schemas", "TenantResponse"),
    "UserUpdateRequest":     ("src.core.auth.schemas", "UserUpdateRequest"),
    "PasswordChangeRequest": ("src.core.auth.schemas", "PasswordChangeRequest"),
    # Service
    "AuthService":          ("src.core.auth.service", "AuthService"),
    "create_access_token":  ("src.core.auth.service", "create_access_token"),
    "create_refresh_token": ("src.core.auth.service", "create_refresh_token"),
    "decode_token":         ("src.core.auth.service", "decode_token"),
    "get_user_by_email":    ("src.core.auth.service", "get_user_by_email"),
    "get_user_by_id":       ("src.core.auth.service", "get_user_by_id"),
    "hash_password":        ("src.core.auth.service", "hash_password"),
    "verify_password":      ("src.core.auth.service", "verify_password"),
    # Router
    "router":               ("src.core.auth.router", "router"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(module_path)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'src.core.auth' has no attribute {name!r}")
