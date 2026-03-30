"""
C2Pro - Clerk Auth and Rate Limiter Tests
TS-E2E-SEC-TNT-001
"""

from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException, Request, status
from jwt import InvalidTokenError
from redis.exceptions import RedisError

from src.config import settings
from src.core.middleware.clerk_auth import (
    ClerkTokenVerificationError,
    ClerkUser,
    clear_jwks_cache,
    extract_clerk_claims,
    get_clerk_jwks,
    get_clerk_user,
    get_current_tenant_id,
    require_admin,
    require_organization,
    require_tenant,
    verify_clerk_token,
)
from src.core.middleware.rate_limiter import RateLimitMiddleware


def _request_with_auth_header(value: str | None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/secured",
        "headers": [],
    }
    if value is not None:
        scope["headers"] = [(b"authorization", value.encode())]
    return Request(scope)


class _CircuitOpen:
    def can_execute_sync(self) -> bool:
        return False


class _CircuitRecorder:
    def __init__(self) -> None:
        self.successes = 0
        self.failures = 0

    def can_execute_sync(self) -> bool:
        return True

    def record_success_sync(self) -> None:
        self.successes += 1

    def record_failure_sync(self, _exc: Exception) -> None:
        self.failures += 1


def test_clerk_user_properties_and_roles():
    """Should expose derived Clerk user state from claims."""
    tenant_id = str(uuid4())
    user = ClerkUser(
        {
            "sub": "user_123",
            "email": "clerk@example.com",
            "org_id": "org_123",
            "org_role": "org:admin",
            "org_public_metadata": {"tenant_id": tenant_id, "tier": "pro", "is_demo": True},
        }
    )

    assert user.is_authenticated is True
    assert user.is_org_admin is True
    assert user.has_org() is True
    assert user.has_tenant() is True
    assert user.tenant_id == tenant_id
    assert user.service_tier == "pro"
    assert user.is_demo is True


@pytest.mark.asyncio
async def test_extract_clerk_claims_rejects_missing_authorization_header():
    """Should reject requests without a Bearer token header."""
    with pytest.raises(ClerkTokenVerificationError, match="Missing or invalid Authorization header"):
        await extract_clerk_claims(_request_with_auth_header(None))


@pytest.mark.asyncio
async def test_get_clerk_user_requires_authenticated_subject():
    """Should reject Clerk users that do not have a subject claim."""
    with pytest.raises(ClerkTokenVerificationError, match="User not authenticated"):
        await get_clerk_user({"email": "missing-sub@example.com"})


@pytest.mark.asyncio
async def test_require_organization_rejects_users_without_org():
    """Should enforce organization selection before tenant access."""
    with pytest.raises(HTTPException, match="select an organization") as exc_info:
        await require_organization(ClerkUser({"sub": "user_123"}))

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_require_tenant_rejects_missing_tenant_mapping():
    """Should reject orgs that lack mapped tenant metadata."""
    user = ClerkUser({"sub": "user_123", "org_id": "org_123"})

    with pytest.raises(HTTPException, match="missing tenant_id") as exc_info:
        await require_tenant(user)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_require_admin_rejects_non_admin_users():
    """Should reject Clerk users without admin organization role."""
    user = ClerkUser({"sub": "user_123", "org_id": "org_123", "org_role": "org:member"})

    with pytest.raises(HTTPException, match="requires admin role") as exc_info:
        await require_admin(user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_get_current_tenant_id_rejects_invalid_uuid():
    """Should reject malformed tenant UUID metadata."""
    user = ClerkUser({"sub": "user_123", "org_id": "org_123", "org_public_metadata": {"tenant_id": "bad-uuid"}})

    with pytest.raises(HTTPException, match="Invalid tenant_id format") as exc_info:
        await get_current_tenant_id(user)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


def test_get_clerk_jwks_returns_none_when_not_configured(monkeypatch):
    """Should return None when no Clerk issuer or JWKS URL is configured."""
    clear_jwks_cache()
    monkeypatch.setattr("src.core.middleware.clerk_auth._clerk_circuit_breaker", None)
    monkeypatch.setattr(settings, "clerk_jwks_url", None)
    monkeypatch.setattr(settings, "clerk_issuer", None)

    jwks = get_clerk_jwks()

    assert jwks is None


def test_get_clerk_jwks_returns_none_when_circuit_open(monkeypatch):
    """Should skip JWKS fetches while the circuit breaker is open."""
    clear_jwks_cache()
    monkeypatch.setattr("src.core.middleware.clerk_auth._get_clerk_circuit_breaker", lambda: _CircuitOpen())

    jwks = get_clerk_jwks()

    assert jwks is None


def test_get_clerk_jwks_records_success_on_fetch(monkeypatch):
    """Should record a successful JWKS fetch on the circuit breaker."""
    clear_jwks_cache()
    cb = _CircuitRecorder()
    monkeypatch.setattr("src.core.middleware.clerk_auth._get_clerk_circuit_breaker", lambda: cb)
    monkeypatch.setattr(settings, "clerk_jwks_url", "https://clerk.test/jwks")

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"keys": []}

    monkeypatch.setattr("src.core.middleware.clerk_auth.httpx.get", lambda *_args, **_kwargs: _Response())

    jwks = get_clerk_jwks()

    assert jwks == {"keys": []}
    assert cb.successes == 1


@pytest.mark.asyncio
async def test_verify_clerk_token_rejects_empty_token():
    """Should reject empty Clerk tokens."""
    with pytest.raises(ClerkTokenVerificationError, match="No token provided") as exc_info:
        await verify_clerk_token("")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_verify_clerk_token_rejects_missing_kid(monkeypatch):
    """Should reject Clerk JWTs whose header omits the key id."""
    monkeypatch.setattr("src.core.middleware.clerk_auth.jwt.get_unverified_header", lambda _token: {})

    with pytest.raises(ClerkTokenVerificationError, match="missing kid header") as exc_info:
        await verify_clerk_token("header.payload.signature")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_verify_clerk_token_maps_invalid_jwt_errors(monkeypatch):
    """Should map PyJWT validation failures to 401 Clerk token errors."""
    monkeypatch.setattr("src.core.middleware.clerk_auth.jwt.get_unverified_header", lambda _token: {"kid": "kid-1"})
    monkeypatch.setattr("src.core.middleware.clerk_auth.get_clerk_jwks", lambda: {"keys": [{"kid": "kid-1"}]})
    monkeypatch.setattr("src.core.middleware.clerk_auth.RSAAlgorithm.from_jwk", lambda _key: "rsa-key")

    def _decode(*_args, **_kwargs):
        raise InvalidTokenError("bad signature")

    monkeypatch.setattr("src.core.middleware.clerk_auth.jwt.decode", _decode)

    with pytest.raises(ClerkTokenVerificationError, match="Invalid token: bad signature") as exc_info:
        await verify_clerk_token("header.payload.signature")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_rate_limiter_build_redis_returns_none_when_url_missing(monkeypatch):
    """Should disable Redis-backed rate limiting when no URL is configured."""
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "redis_url", None)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    middleware = RateLimitMiddleware(app=SimpleNamespace(), redis_url=None)

    assert middleware._redis is None


def test_rate_limiter_extract_ids_decodes_bearer_token():
    """Should decode tenant and user ids from a signed bearer token."""
    user_id = uuid4()
    tenant_id = uuid4()
    token = jwt.encode(
        {"sub": str(user_id), "tenant_id": str(tenant_id), "type": "access"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    request = _request_with_auth_header(f"Bearer {token}")
    request.state.user_id = None
    request.state.tenant_id = None

    middleware = RateLimitMiddleware(app=SimpleNamespace())

    extracted_user_id, extracted_tenant_id = middleware._extract_ids(request)

    assert extracted_user_id == user_id
    assert extracted_tenant_id == tenant_id


def test_rate_limiter_extract_ids_ignores_invalid_uuid_claims():
    """Should treat malformed identity claims as anonymous traffic."""
    token = jwt.encode(
        {"sub": "bad-user-id", "tenant_id": "bad-tenant-id", "type": "access"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    request = _request_with_auth_header(f"Bearer {token}")
    request.state.user_id = None
    request.state.tenant_id = None

    middleware = RateLimitMiddleware(app=SimpleNamespace())

    extracted_user_id, extracted_tenant_id = middleware._extract_ids(request)

    assert extracted_user_id is None
    assert extracted_tenant_id is None


@pytest.mark.asyncio
async def test_rate_limiter_increment_counters_returns_none_on_redis_error():
    """Should fall back cleanly when Redis counter increment fails."""
    middleware = RateLimitMiddleware(app=SimpleNamespace())

    class _Pipeline:
        def incr(self, *_args, **_kwargs) -> None:
            return None

        def expire(self, *_args, **_kwargs) -> None:
            return None

        async def execute(self) -> list[int]:
            raise RedisError("boom")

    middleware._redis = SimpleNamespace(pipeline=lambda: _Pipeline())

    user_count, tenant_count = await middleware._increment_counters(uuid4(), uuid4(), "2026-03-28T23:00")

    assert user_count is None
    assert tenant_count is None
