"""
DTO Registry - Provides a registry of all DTOs for serialization testing.
"""

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from src.core.auth.schemas import (
    TokenResponse,
    UserResponse,
)


def get_all_dtos() -> Iterable[tuple[type[BaseModel], dict[str, Any]]]:
    """
    Returns all DTO classes with sample data for roundtrip testing.
    """
    from uuid import uuid4

    user_id = str(uuid4())

    return [
        (
            TokenResponse,
            {
                "access_token": "example-access-token",
                "token_type": "bearer",
                "expires_in": 3600,
                "refresh_token": "example-refresh-token",
            },
        ),
        (
            UserResponse,
            {
                "id": user_id,
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "full_name": "Test User",
                "avatar_url": None,
                "phone": None,
                "role": "admin",
                "is_active": True,
                "is_verified": False,
                "is_admin": True,
                "is_viewer": False,
                "can_edit": True,
                "can_manage_users": True,
                "last_login": None,
                "last_activity": None,
                "login_count": 0,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
        ),
    ]
