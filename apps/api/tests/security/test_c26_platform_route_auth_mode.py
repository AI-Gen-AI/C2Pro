from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt
import pytest
from fastapi import Response
from starlette.requests import Request

from src.config import settings
from src.core.middleware.tenant_isolation import (
    TenantIsolationMiddleware,
    is_platform_route,
)


def _request(path: str, method: str = "GET", token: str | None = None) -> Request:
    headers = [] if token is None else [(b"authorization", f"Bearer {token}".encode())]
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers,
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "state": {},
        }
    )


def test_platform_route_registry_is_exact_method_and_normalized_template() -> None:
    assert is_platform_route("GET", "/api/v1/admin/dlq")
    assert is_platform_route("POST", f"/api/v1/admin/dlq/{uuid4()}/retry")
    assert not is_platform_route("GET", "/api/v1/admin/dlq/extra")
    assert not is_platform_route("GET", "/api/v1/admin/dlq/not-a-platform-route")
    assert not is_platform_route("POST", "/api/v1/admin/dlq")
    assert not is_platform_route("POST", "/api/v1/admin/dlq/id/retry/extra")


@pytest.mark.asyncio
async def test_platform_route_uses_clerk_once_without_tenant_resolution_or_context() -> None:
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock(return_value=Response(content="ok", status_code=200))
    token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyX29wZXJhdG9yIn0.c2ln"
    request = _request("/api/v1/admin/dlq", token=token)

    with (
        patch(
            "src.core.middleware.tenant_isolation.verify_clerk_token",
            AsyncMock(
                return_value={
                    "sub": "user_operator",
                    "org_id": "org_platform",
                    "email": "operator@example.test",
                    "email_verified": True,
                }
            ),
        ) as verify,
        patch.object(middleware, "_get_clerk_user_record", AsyncMock()) as lookup,
        patch("src.core.middleware.tenant_isolation.structlog.contextvars.bind_contextvars") as bind,
    ):
        response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    verify.assert_awaited_once_with(token)
    lookup.assert_not_awaited()
    assert not hasattr(request.state, "tenant_id")
    assert request.state.platform_identity.user_id == "user_operator"
    assert all("tenant_id" not in call.kwargs for call in bind.call_args_list)


@pytest.mark.asyncio
async def test_local_hs256_token_is_401_not_tenant_authenticated_on_platform_route() -> None:
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock()
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "type": "access",
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    request = _request("/api/v1/admin/dlq", token=token)

    with patch(
        "src.core.middleware.tenant_isolation.verify_clerk_token", AsyncMock()
    ) as verify:
        response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert not hasattr(request.state, "tenant_id")
    verify.assert_not_awaited()
    call_next.assert_not_awaited()
