import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest
from fastapi import Response
from starlette.requests import Request

from src.config import settings
from src.core.auth.bootstrap_lookup import BootstrapFallbackBlockedError
from src.core.middleware.tenant_isolation import TenantIsolationMiddleware

# ===========================================
# HELPERS
# ===========================================

def create_mock_request(path: str, method: str = "GET", headers: dict = None, query_params: dict = None) -> Request:
    if headers is None:
        headers = {}
    if query_params is None:
        query_params = {}

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": "&".join(f"{k}={v}" for k, v in query_params.items()).encode(),
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
        "state": {},  # Required for request.state
    }
    return Request(scope)

# ===========================================
# TESTS
# ===========================================

@pytest.mark.asyncio
async def test_tenant_isolation_middleware_public_path():
    """Rutas públicas deben permitirse sin autenticación."""
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock(return_value=Response(content="ok", status_code=200))
    request = create_mock_request("/health")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    call_next.assert_called_once_with(request)

@pytest.mark.asyncio
async def test_tenant_isolation_middleware_options_request():
    """Peticiones OPTIONS deben permitirse sin autenticación."""
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock(return_value=Response(content="ok", status_code=200))
    request = create_mock_request("/api/v1/projects", method="OPTIONS")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    call_next.assert_called_once_with(request)

@pytest.mark.asyncio
async def test_tenant_isolation_middleware_missing_token():
    """Rutas protegidas sin token deben devolver 401."""
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock()
    request = create_mock_request("/api/v1/projects")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    content = json.loads(response.body)
    assert content["detail"] == "Not authenticated"
    call_next.assert_not_called()


@pytest.mark.asyncio
async def test_tenant_isolation_middleware_missing_token_sentry_call():
    """Rutas protegidas sin token deben llamar a record_auth_failure."""
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock()
    request = create_mock_request("/api/v1/projects")

    with patch("src.core.middleware.tenant_isolation.record_auth_failure") as mock_record_auth:
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 401
        mock_record_auth.assert_called_once_with(
            reason_code="missing_or_invalid_token",
            tenant_id=None,
            path="/api/v1/projects",
            ip="127.0.0.1",
        )


@pytest.mark.asyncio
async def test_tenant_isolation_middleware_valid_local_jwt():
    """JWT local válido debe inyectar tenant_id en request state."""
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock(return_value=Response(content="ok", status_code=200))

    tenant_id = uuid4()
    user_id = uuid4()
    token = jwt.encode(
        {"sub": str(user_id), "tenant_id": str(tenant_id), "type": "access"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})

    with patch("src.core.middleware.tenant_isolation.is_token_revoked_async", AsyncMock(return_value=False)):
        with patch.object(middleware, "_validate_tenant_exists", AsyncMock(return_value=True)):
            with patch("structlog.contextvars.bind_contextvars"):
                response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    assert request.state.tenant_id == tenant_id
    assert request.state.user_id == user_id
    call_next.assert_called_once_with(request)

@pytest.mark.asyncio
async def test_tenant_isolation_middleware_expired_jwt():
    """JWT expirado debe devolver 401."""
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock()

    tenant_id = uuid4()
    token = jwt.encode(
        {"sub": str(uuid4()), "tenant_id": str(tenant_id), "type": "access", "exp": 1},  # Expired
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})

    with patch("src.core.middleware.tenant_isolation.is_token_revoked_async", AsyncMock(return_value=False)):
        response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    content = json.loads(response.body)
    assert "expired" in content["detail"].lower()

@pytest.mark.asyncio
async def test_tenant_isolation_middleware_revoked_token():
    """Token revocado debe devolver 401."""
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock()

    token = "some-revoked-token"
    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})

    with patch("src.core.middleware.tenant_isolation.is_token_revoked_async", AsyncMock(return_value=True)):
        response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    content = json.loads(response.body)
    assert content["reason_code"] == "token_revoked"

@pytest.mark.asyncio
async def test_tenant_isolation_middleware_clerk_fallback():
    """Fallback a Clerk cuando JWT local es inválido."""
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock(return_value=Response(content="ok", status_code=200))

    clerk_user_id = "user_2testclerk"
    tenant_id = uuid4()
    token = "some-clerk-token"

    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})

    with patch("src.core.middleware.tenant_isolation.is_token_revoked_async", AsyncMock(return_value=False)):
        with patch("src.core.middleware.tenant_isolation.verify_clerk_token", AsyncMock(return_value={"sub": clerk_user_id})):
            with patch.object(middleware, "_get_tenant_for_clerk_user", AsyncMock(return_value=tenant_id)):
                with patch.object(middleware, "_validate_tenant_exists", AsyncMock(return_value=True)):
                    with patch("structlog.contextvars.bind_contextvars"):
                        response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    assert request.state.tenant_id == tenant_id
    assert request.state.user_id == clerk_user_id

@pytest.mark.asyncio
async def test_tenant_isolation_middleware_clerk_fallback_blocked():
    """Fallback a Clerk bloqueado por política de bootstrap."""
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock()

    token = "some-clerk-token"
    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})

    with patch("src.core.middleware.tenant_isolation.is_token_revoked_async", AsyncMock(return_value=False)):
        # Local JWT fails (it's not a valid JWT)
        with patch("src.core.middleware.tenant_isolation.verify_clerk_token", AsyncMock(side_effect=BootstrapFallbackBlockedError())):
            response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    content = json.loads(response.body)
    assert content["reason_code"] == "auth_bootstrap_fallback_blocked"

@pytest.mark.asyncio
async def test_tenant_isolation_middleware_inactive_tenant():
    """Tenant inactivo debe devolver 401."""
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock()

    tenant_id = uuid4()
    token = jwt.encode(
        {"sub": str(uuid4()), "tenant_id": str(tenant_id), "type": "access"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})

    with patch("src.core.middleware.tenant_isolation.is_token_revoked_async", AsyncMock(return_value=False)):
        with patch.object(middleware, "_validate_tenant_exists", AsyncMock(return_value=False)):
            response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    content = json.loads(response.body)
    assert content["reason_code"] == "tenant_inactive_or_missing"

@pytest.mark.asyncio
async def test_tenant_isolation_middleware_sse_stream_token_in_query():
    """SSE streams pueden enviar token en query params."""
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock(return_value=Response(content="ok", status_code=200))

    tenant_id = uuid4()
    user_id = uuid4()
    token = jwt.encode(
        {"sub": str(user_id), "tenant_id": str(tenant_id), "type": "access"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    request = create_mock_request(
        "/api/v1/process/stream",
        query_params={"access_token": token}
    )

    with patch("src.core.middleware.tenant_isolation.is_token_revoked_async", AsyncMock(return_value=False)):
        with patch.object(middleware, "_validate_tenant_exists", AsyncMock(return_value=True)):
            with patch("structlog.contextvars.bind_contextvars"):
                response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    assert request.state.tenant_id == tenant_id
    assert request.state.user_id == user_id

@pytest.mark.asyncio
async def test_tenant_isolation_middleware_sse_stream_missing_token():
    """SSE stream sin token debe devolver 401."""
    middleware = TenantIsolationMiddleware(None)
    call_next = AsyncMock()

    request = create_mock_request("/api/v1/process/stream")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    content = json.loads(response.body)
    assert content["reason_code"] == "authenticated_sse_session_required"

# ===========================================
# HELPER METHOD TESTS
# ===========================================

@pytest.mark.asyncio
async def test_extract_tenant_id():
    """Prueba el método privado _extract_tenant_id."""
    middleware = TenantIsolationMiddleware(None)
    tenant_id = uuid4()
    token = jwt.encode(
        {"sub": str(uuid4()), "tenant_id": str(tenant_id), "type": "access"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})

    extracted_id, error = middleware._extract_tenant_id(request)
    assert extracted_id == tenant_id
    assert error is None

@pytest.mark.asyncio
async def test_extract_tenant_id_invalid_type():
    """_extract_tenant_id debe fallar si no es un access token."""
    middleware = TenantIsolationMiddleware(None)
    token = jwt.encode(
        {"sub": str(uuid4()), "tenant_id": str(uuid4()), "type": "refresh"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})

    extracted_id, error = middleware._extract_tenant_id(request)
    assert extracted_id is None
    assert "Invalid token type" in error

@pytest.mark.asyncio
async def test_extract_user_id():
    """Prueba el método privado _extract_user_id."""
    middleware = TenantIsolationMiddleware(None)
    user_id = uuid4()
    token = jwt.encode(
        {"sub": str(user_id)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})

    extracted_id = middleware._extract_user_id(request)
    assert extracted_id == user_id

@pytest.mark.asyncio
async def test_validate_tenant_exists_inactive():
    """_validate_tenant_exists debe devolver False para tenants inactivos."""
    middleware = TenantIsolationMiddleware(None)
    tenant_id = uuid4()

    # Mocking database response
    mock_tenant = MagicMock()
    mock_tenant.is_active = False

    with patch("src.core.middleware.tenant_isolation.get_raw_session", return_value=AsyncMock()):
        with patch("src.core.middleware.tenant_isolation.lookup_tenant_by_id", AsyncMock(return_value=mock_tenant)):
            result = await middleware._validate_tenant_exists(tenant_id)
            assert result is False

@pytest.mark.asyncio
async def test_validate_tenant_exists_not_found():
    """_validate_tenant_exists debe devolver False si el tenant no existe."""
    middleware = TenantIsolationMiddleware(None)
    tenant_id = uuid4()

    with patch("src.core.middleware.tenant_isolation.get_raw_session", return_value=AsyncMock()):
        with patch("src.core.middleware.tenant_isolation.lookup_tenant_by_id", AsyncMock(return_value=None)):
            result = await middleware._validate_tenant_exists(tenant_id)
            assert result is False

@pytest.mark.asyncio
async def test_get_tenant_for_clerk_user():
    """_get_tenant_for_clerk_user debe devolver el tenant_id del usuario."""
    middleware = TenantIsolationMiddleware(None)
    clerk_user_id = "user_2clerk"
    tenant_id = uuid4()

    mock_user = MagicMock()
    mock_user.tenant_id = tenant_id

    with patch("src.core.middleware.tenant_isolation.get_raw_session", return_value=AsyncMock()):
        with patch("src.core.middleware.tenant_isolation.lookup_user_by_clerk_user_id", AsyncMock(return_value=mock_user)):
            result = await middleware._get_tenant_for_clerk_user(clerk_user_id)
            assert result == tenant_id

@pytest.mark.asyncio
async def test_extract_tenant_id_no_bearer():
    """_extract_tenant_id debe devolver None si no hay Bearer."""
    middleware = TenantIsolationMiddleware(None)
    request = create_mock_request("/api/v1/projects", headers={"Authorization": "InvalidHeader"})
    extracted_id, error = middleware._extract_tenant_id(request)
    assert extracted_id is None
    assert error is None

@pytest.mark.asyncio
async def test_extract_tenant_id_expired():
    """_extract_tenant_id debe detectar JWT expirado."""
    middleware = TenantIsolationMiddleware(None)
    token = jwt.encode(
        {"sub": str(uuid4()), "tenant_id": str(uuid4()), "type": "access", "exp": 1},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})
    extracted_id, error = middleware._extract_tenant_id(request)
    assert extracted_id is None
    assert "expired" in error.lower()

@pytest.mark.asyncio
async def test_extract_tenant_id_invalid_jwt():
    """_extract_tenant_id debe detectar JWT inválido."""
    middleware = TenantIsolationMiddleware(None)
    request = create_mock_request("/api/v1/projects", headers={"Authorization": "Bearer invalid-token"})
    extracted_id, error = middleware._extract_tenant_id(request)
    assert extracted_id is None
    assert "Invalid authentication credentials" in error

@pytest.mark.asyncio
async def test_extract_user_id_invalid():
    """_extract_user_id debe devolver None para tokens inválidos."""
    middleware = TenantIsolationMiddleware(None)
    request = create_mock_request("/api/v1/projects", headers={"Authorization": "Bearer invalid"})
    assert middleware._extract_user_id(request) is None

@pytest.mark.asyncio
async def test_get_tenant_for_clerk_user_not_found():
    """_get_tenant_for_clerk_user debe devolver None si el usuario no existe."""
    middleware = TenantIsolationMiddleware(None)
    with patch("src.core.middleware.tenant_isolation.get_raw_session", return_value=AsyncMock()):
        with patch("src.core.middleware.tenant_isolation.lookup_user_by_clerk_user_id", AsyncMock(return_value=None)):
            assert await middleware._get_tenant_for_clerk_user("unknown") is None

@pytest.mark.asyncio
async def test_get_tenant_for_clerk_user_exception():
    """_get_tenant_for_clerk_user debe manejar excepciones."""
    middleware = TenantIsolationMiddleware(None)
    with patch("src.core.middleware.tenant_isolation.get_raw_session", side_effect=Exception("DB Error")):
        assert await middleware._get_tenant_for_clerk_user("any") is None

@pytest.mark.asyncio
async def test_validate_tenant_exists_test_bypass():
    """_validate_tenant_exists debe permitir bypass en tests si la DB no está inicializada."""
    middleware = TenantIsolationMiddleware(None)
    with patch("src.core.middleware.tenant_isolation.get_raw_session", side_effect=RuntimeError("Database not initialized")):
        with patch("src.config.settings.environment", "test"):
            assert await middleware._validate_tenant_exists(uuid4()) is True

@pytest.mark.asyncio
async def test_extract_auth_context_invalid_uuid():
    """_extract_auth_context debe manejar UUIDs inválidos en el token."""
    middleware = TenantIsolationMiddleware(None)
    token = jwt.encode(
        {"sub": "not-a-uuid", "tenant_id": "not-a-uuid", "type": "access"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})
    with patch("src.core.middleware.tenant_isolation.is_token_revoked_async", AsyncMock(return_value=False)):
        tenant_id, user_id, valid, error, code = await middleware._extract_auth_context(request)
        assert tenant_id is None
        assert "Invalid authentication credentials" in error

@pytest.mark.asyncio
async def test_extract_tenant_id_invalid_uuid():
    """_extract_tenant_id debe manejar UUIDs malformados."""
    middleware = TenantIsolationMiddleware(None)
    token = jwt.encode(
        {"sub": str(uuid4()), "tenant_id": "not-a-uuid", "type": "access"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})
    extracted_id, error = middleware._extract_tenant_id(request)
    assert extracted_id is None
    assert "Invalid authentication credentials" in error

@pytest.mark.asyncio
async def test_extract_auth_context_expired_jwt():
    """_extract_auth_context debe detectar JWT local expirado."""
    middleware = TenantIsolationMiddleware(None)
    token = jwt.encode(
        {"sub": str(uuid4()), "tenant_id": str(uuid4()), "type": "access", "exp": 1},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    request = create_mock_request("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})
    with patch("src.core.middleware.tenant_isolation.is_token_revoked_async", AsyncMock(return_value=False)):
        tenant_id, user_id, valid, error, code = await middleware._extract_auth_context(request)
        assert tenant_id is None
        assert "expired" in error.lower()

@pytest.mark.asyncio
async def test_validate_tenant_exists_exception():
    """_validate_tenant_exists debe devolver False ante errores de DB en prod."""
    middleware = TenantIsolationMiddleware(None)
    with patch("src.core.middleware.tenant_isolation.get_raw_session", side_effect=Exception("Fatal DB Error")):
        with patch("src.config.settings.environment", "production"):
            assert await middleware._validate_tenant_exists(uuid4()) is False
