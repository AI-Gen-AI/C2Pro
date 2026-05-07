"""
TASK-QA-206: Auth/JWT fixtures extracted from conftest.py.

Provides token generation and authenticated-header factories used by unit,
integration, and contract tests. Loaded via conftest.py pytest_plugins.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
import pytest_asyncio

from src.config import settings
from src.core.auth.models import Tenant, User

# ---------------------------------------------------------------------------
# Simple ID fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def test_tenant_id() -> UUID:
    return uuid4()


@pytest.fixture(scope="function")
def test_user_id() -> UUID:
    return uuid4()


@pytest_asyncio.fixture(scope="function")
async def test_project_id() -> UUID:
    return uuid4()


@pytest_asyncio.fixture(scope="function")
async def test_document_id() -> UUID:
    return uuid4()


# ---------------------------------------------------------------------------
# JWT token factories
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def generate_token() -> Callable:
    """Factory fixture: generate JWT tokens with custom properties."""

    def _generate_token(
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
        email: str = "test@example.com",
        role: str = "admin",
        expires_delta_seconds: int | None = None,
        secret_key: str | None = None,
        algorithm: str | None = None,
        extra_claims: dict | None = None,
        token_type: str = "access",
    ) -> str:
        if user_id is None:
            user_id = uuid4()
        if tenant_id is None:
            tenant_id = uuid4()

        if expires_delta_seconds is None:
            expire = datetime.now(UTC) + (timedelta(hours=24) if token_type == "access" else timedelta(days=7))
        else:
            expire = datetime.now(UTC) + timedelta(seconds=expires_delta_seconds)

        payload: dict = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "email": email,
            "role": role,
            "exp": expire,
            "iat": datetime.now(UTC),
            "type": token_type,
        }
        if extra_claims:
            payload.update(extra_claims)

        key = secret_key if secret_key is not None else settings.jwt_secret_key
        algo = algorithm if algorithm is not None else settings.jwt_algorithm
        return jwt.encode(payload, key, algorithm=algo)

    return _generate_token


@pytest.fixture(scope="function")
def create_test_token(generate_token: Callable) -> Callable:
    """Alias for generate_token (backward compat)."""

    def _create_token(
        user_id: UUID,
        tenant_id: UUID,
        email: str = "test@example.com",
        role: str = "admin",
        secret_key: str | None = None,
        expires_delta: timedelta | None = None,
        token_type: str = "access",
    ) -> str:
        expires_seconds = int(expires_delta.total_seconds()) if expires_delta else None
        return generate_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            role=role,
            secret_key=secret_key,
            expires_delta_seconds=expires_seconds,
            token_type=token_type,
        )

    return _create_token


@pytest_asyncio.fixture(scope="function")
async def get_auth_headers(
    test_user: User,
    test_tenant: Tenant,
    generate_token: Callable,
) -> Callable:
    """Factory: build auth headers for any user/tenant combo."""

    def _get_headers(
        user: User | None = None,
        tenant: Tenant | None = None,
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
        email: str | None = None,
        role: str | None = None,
    ) -> dict[str, str]:
        u = user or test_user
        t = tenant or test_tenant
        token = generate_token(
            user_id=user_id or u.id,
            tenant_id=tenant_id or t.id,
            email=email or u.email,
            role=role or (u.role.value if hasattr(u.role, "value") else u.role),
        )
        return {"Authorization": f"Bearer {token}"}

    return _get_headers


@pytest.fixture(scope="function")
def get_auth_headers_simple(
    generate_token: Callable,
    test_user_id: UUID,
    test_tenant_id: UUID,
) -> Callable:
    """Sync factory for auth headers (unit tests)."""

    def _get_headers(
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
        email: str = "test@example.com",
        role: str = "admin",
    ) -> dict[str, str]:
        token = generate_token(
            user_id=user_id or test_user_id,
            tenant_id=tenant_id or test_tenant_id,
            email=email,
            role=role,
        )
        return {"Authorization": f"Bearer {token}"}

    return _get_headers
