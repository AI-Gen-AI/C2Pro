"""
DTO Registry - Provides a registry of all DTOs for serialization testing.
"""

from typing import Any, Iterable

from pydantic import BaseModel

from src.core.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    TenantResponse,
)


def get_all_dtos() -> Iterable[tuple[type[BaseModel], dict[str, Any]]]:
    """
    Returns all DTO classes with sample data for roundtrip testing.
    """
    from uuid import uuid4

    user_id = str(uuid4())
    tenant_id = str(uuid4())

    return [
        (
            TokenResponse,
            {
                "access_token": "eyJhbGciOiJIUzI1NiJ9.test.sig",
                "token_type": "bearer",
                "expires_in": 3600,
                "refresh_token": "eyJhbGciOiJIUzI1NiJ9.refresh.sig",
            },
        ),
        (
            UserResponse,
            {
                "id": user_id,
                "tenant_id": tenant_id,
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "role": "admin",
                "is_active": True,
                "is_verified": False,
            },
        ),
    ]
