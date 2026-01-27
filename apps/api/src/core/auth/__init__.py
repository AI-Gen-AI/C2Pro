"""
C2Pro - Core Authentication Module

Infraestructura transversal de autenticación y multi-tenancy.
"""

# Models
from src.core.auth.models import (
    SubscriptionPlan,
    Tenant,
    User,
    UserRole,
)

# Schemas
from src.core.auth.schemas import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    PasswordChangeRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    TenantResponse,
    TokenPayload,
    TokenResponse,
    UserResponse,
    UserUpdateRequest,
)

# Service
from src.core.auth.service import (
    AuthService,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_email,
    get_user_by_id,
    hash_password,
    verify_password,
)

# Router
from src.core.auth.router import router

__all__ = [
    # Models
    "User",
    "Tenant",
    "UserRole",
    "SubscriptionPlan",
    # Schemas
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "RegisterResponse",
    "TokenResponse",
    "TokenPayload",
    "RefreshTokenRequest",
    "UserResponse",
    "TenantResponse",
    "MeResponse",
    "UserUpdateRequest",
    "PasswordChangeRequest",
    # Service
    "AuthService",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "verify_password",
    "get_user_by_email",
    "get_user_by_id",
    # Router
    "router",
]
