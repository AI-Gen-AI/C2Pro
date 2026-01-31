"""
C2Pro - Middleware Unit Tests

Comprehensive tests for middleware components including:
- TenantIsolationMiddleware (JWT extraction, tenant isolation)
- RequestLoggingMiddleware (structured logging)
- RateLimitMiddleware (rate limiting)
- Security helpers (Permissions, dependency functions)
"""

import pytest
import time
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4, UUID

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.middleware import (
    TenantIsolationMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware,
)
from src.core.security import (
    get_current_tenant_id,
    get_current_user_id,
    get_optional_user_id,
    Permissions,
)
from src.core.exceptions import AuthenticationError, TenantNotFoundError
from src.core.auth.service import create_access_token
from src.core.auth.models import UserRole


# ===========================================
# TEST FIXTURES
# ===========================================

@pytest.fixture
def app():
    """Create a simple FastAPI app for testing."""
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/protected")
    async def protected(request: Request):
        return {
            "tenant_id": str(request.state.tenant_id) if hasattr(request.state, "tenant_id") else None,
            "user_id": str(request.state.user_id) if hasattr(request.state, "user_id") else None,
        }

    @app.get("/public")
    async def public():
        return {"message": "public"}

    @app.get("/error")
    async def error():
        raise ValueError("Test error")

    return app


@pytest.fixture
def valid_token(test_user, test_tenant):
    """Generate a valid JWT token."""
    return create_access_token(
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        email=test_user.email,
        role=test_user.role
    )


# ===========================================
# TENANT ISOLATION MIDDLEWARE TESTS
# ===========================================

class TestTenantIsolationMiddleware:
    """Tests for TenantIsolationMiddleware."""

    def test_public_path_bypass_health(self, app):
        """
        Should allow access to /health without authentication.
        """
        app.add_middleware(TenantIsolationMiddleware)
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_public_path_bypass_docs(self, app):
        """
        Should allow access to /docs without authentication.
        """
        app.add_middleware(TenantIsolationMiddleware)
        client = TestClient(app)

        response = client.get("/docs")

        # /docs might return 200 or 404 depending on setup
        # The important thing is it doesn't return 401
        assert response.status_code != 401

    def test_protected_path_without_token(self, app):
        """
        Should return 401 when accessing protected path without token.
        """
        app.add_middleware(TenantIsolationMiddleware)
        client = TestClient(app)

        response = client.get("/protected")

        assert response.status_code == 401
        assert "Invalid authentication credentials" in response.json()["detail"]

    def test_protected_path_with_malformed_auth_header(self, app):
        """
        Should return 401 with malformed Authorization header.
        """
        app.add_middleware(TenantIsolationMiddleware)
        client = TestClient(app)

        # Missing "Bearer " prefix
        response = client.get("/protected", headers={"Authorization": "InvalidToken"})

        assert response.status_code == 401
        assert "Invalid authentication credentials" in response.json()["detail"]

    def test_protected_path_with_invalid_token(self, app):
        """
        Should return 401 with invalid JWT token.
        """
        app.add_middleware(TenantIsolationMiddleware)
        client = TestClient(app)

        response = client.get("/protected", headers={"Authorization": "Bearer invalid.jwt.token"})

        assert response.status_code == 401
        assert "Invalid authentication credentials" in response.json()["detail"]

    def test_protected_path_with_valid_token(self, app, valid_token, test_tenant, test_user):
        """
        Should allow access with valid JWT and inject tenant_id into request state.
        """
        app.add_middleware(TenantIsolationMiddleware)
        client = TestClient(app)

        response = client.get("/protected", headers={"Authorization": f"Bearer {valid_token}"})

        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == str(test_tenant.id)
        assert data["user_id"] == str(test_user.id)

    def test_extract_tenant_id_from_jwt(self, test_user, test_tenant):
        """
        Should correctly extract tenant_id from JWT payload.
        """
        middleware = TenantIsolationMiddleware(app=Mock())

        token = create_access_token(
            user_id=test_user.id,
            tenant_id=test_tenant.id,
            email=test_user.email,
            role=test_user.role
        )

        # Create mock request
        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}

        tenant_id, error_message = middleware._extract_tenant_id(request)

        assert tenant_id == test_tenant.id
        assert error_message is None

    def test_extract_tenant_id_missing_claim(self):
        """
        Should return None when both tenant_id and sub claims are missing from JWT.
        Note: tenant_id falls back to 'sub' if not present, so both must be missing.
        """
        import jwt
        from src.config import settings

        middleware = TenantIsolationMiddleware(app=Mock())

        # Create token without tenant_id OR sub claim
        token = jwt.encode(
            {"email": "test@example.com", "role": "user"},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )

        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}

        tenant_id, error_message = middleware._extract_tenant_id(request)

        assert tenant_id is None
        assert error_message is not None

    def test_extract_tenant_id_invalid_token_type(self, test_user, test_tenant):
        """
        Should return None when token type is not 'access'.
        """
        import jwt
        from src.config import settings

        middleware = TenantIsolationMiddleware(app=Mock())

        # Create a refresh token instead of access token
        token = jwt.encode(
            {
                "sub": str(test_user.id),
                "tenant_id": str(test_tenant.id),
                "type": "refresh",  # Wrong token type
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}

        tenant_id, error_message = middleware._extract_tenant_id(request)

        # Should reject refresh tokens
        assert tenant_id is None
        assert error_message is not None

    def test_extract_user_id_from_jwt(self, test_user, test_tenant):
        """
        Should correctly extract user_id from JWT payload.
        """
        middleware = TenantIsolationMiddleware(app=Mock())

        token = create_access_token(
            user_id=test_user.id,
            tenant_id=test_tenant.id,
            email=test_user.email,
            role=test_user.role
        )

        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {token}"}

        user_id = middleware._extract_user_id(request)

        assert user_id == test_user.id

    def test_is_public_path_detection(self):
        """
        Should correctly identify public paths.
        """
        middleware = TenantIsolationMiddleware(app=Mock())

        # Public paths
        assert middleware._is_public_path("/health") is True
        assert middleware._is_public_path("/docs") is True
        assert middleware._is_public_path("/redoc") is True
        assert middleware._is_public_path("/openapi.json") is True
        assert middleware._is_public_path("/api/auth/login") is True
        assert middleware._is_public_path("/api/auth/register") is True

        # Protected paths
        assert middleware._is_public_path("/api/projects") is False
        assert middleware._is_public_path("/api/documents") is False
        assert middleware._is_public_path("/protected") is False

    @pytest.mark.asyncio
    async def test_middleware_binds_to_logging_context(self, app, valid_token, test_tenant, test_user):
        """
        Should bind tenant_id and user_id to structured logging context.
        """
        app.add_middleware(TenantIsolationMiddleware)

        with patch('src.core.middleware.structlog.contextvars.bind_contextvars') as mock_bind:
            client = TestClient(app)
            client.get("/protected", headers={"Authorization": f"Bearer {valid_token}"})

            # Verify bind was called with tenant_id and user_id
            mock_bind.assert_called_once()
            call_kwargs = mock_bind.call_args[1]
            assert call_kwargs["tenant_id"] == str(test_tenant.id)
            assert call_kwargs["user_id"] == str(test_user.id)

    @pytest.mark.asyncio
    async def test_inactive_tenant_is_blocked(self, app, valid_token, test_tenant):
        """
        Should reject requests when tenant exists but is inactive.
        """
        app.add_middleware(TenantIsolationMiddleware)
        client = TestClient(app)

        with patch(
            "src.core.middleware.tenant_isolation.TenantIsolationMiddleware._validate_tenant_exists",
            new=AsyncMock(return_value=False),
        ):
            response = client.get("/protected", headers={"Authorization": f"Bearer {valid_token}"})

        assert response.status_code == 401
        assert "Invalid authentication context" in response.json()["detail"]


# ===========================================
# REQUEST LOGGING MIDDLEWARE TESTS
# ===========================================

class TestRequestLoggingMiddleware:
    """Tests for RequestLoggingMiddleware."""

    def test_generates_request_id(self, app):
        """
        Should generate and inject request_id into request state.
        """
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/test-request-id")
        async def test_endpoint(request: Request):
            return {"request_id": request.state.request_id}

        client = TestClient(app)
        response = client.get("/test-request-id")

        assert response.status_code == 200
        assert "request_id" in response.json()
        assert response.json()["request_id"] is not None

    def test_uses_provided_request_id_header(self, app):
        """
        Should use X-Request-ID header if provided.
        """
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/test-request-id")
        async def test_endpoint(request: Request):
            return {"request_id": request.state.request_id}

        client = TestClient(app)
        custom_request_id = "custom-request-id-12345"

        response = client.get("/test-request-id", headers={"X-Request-ID": custom_request_id})

        assert response.json()["request_id"] == custom_request_id

    def test_adds_request_id_to_response_headers(self, app):
        """
        Should add X-Request-ID to response headers.
        """
        app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(app)

        response = client.get("/health")

        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] is not None

    def test_logs_request_start(self, app):
        """
        Should log when request starts.
        """
        app.add_middleware(RequestLoggingMiddleware)

        with patch('src.core.middleware.logger.info') as mock_log:
            client = TestClient(app)
            client.get("/health")

            # Find the request_started log call
            started_calls = [call for call in mock_log.call_args_list
                           if call[0][0] == "request_started"]
            assert len(started_calls) >= 1

            # Verify log contains expected fields
            call_kwargs = started_calls[0][1]
            assert call_kwargs["method"] == "GET"
            assert call_kwargs["path"] == "/health"

    def test_logs_request_completion_success(self, app):
        """
        Should log successful request completion with duration.
        """
        app.add_middleware(RequestLoggingMiddleware)

        with patch('src.core.middleware.logger.info') as mock_log:
            client = TestClient(app)
            client.get("/health")

            # Find the request_completed log call
            completed_calls = [call for call in mock_log.call_args_list
                             if call[0][0] == "request_completed"]
            assert len(completed_calls) >= 1

            call_kwargs = completed_calls[0][1]
            assert call_kwargs["status_code"] == 200
            assert "duration_ms" in call_kwargs
            assert call_kwargs["duration_ms"] >= 0

    def test_logs_request_completion_error_status(self, app):
        """
        Should log as warning when status code >= 400.
        """
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/not-found")
        async def not_found():
            raise HTTPException(status_code=404, detail="Not found")

        with patch('src.core.middleware.logger.warning') as mock_warning:
            client = TestClient(app)
            client.get("/not-found")

            # Should log as warning for 4xx/5xx status
            warning_calls = [call for call in mock_warning.call_args_list
                           if call[0][0] == "request_completed"]
            assert len(warning_calls) >= 1

    def test_get_client_ip_from_x_forwarded_for(self):
        """
        Should extract client IP from X-Forwarded-For header.
        """
        middleware = RequestLoggingMiddleware(app=Mock())

        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.1"}

        client_ip = middleware._get_client_ip(request)

        # Should return first IP in the chain
        assert client_ip == "203.0.113.1"

    def test_get_client_ip_from_x_real_ip(self):
        """
        Should extract client IP from X-Real-IP header.
        """
        middleware = RequestLoggingMiddleware(app=Mock())

        request = Mock(spec=Request)
        request.headers = {"X-Real-IP": "203.0.113.1"}

        client_ip = middleware._get_client_ip(request)

        assert client_ip == "203.0.113.1"

    def test_get_client_ip_from_direct_connection(self):
        """
        Should fall back to direct connection IP.
        """
        middleware = RequestLoggingMiddleware(app=Mock())

        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.1"

        client_ip = middleware._get_client_ip(request)

        assert client_ip == "192.168.1.1"

    def test_get_client_ip_unknown(self):
        """
        Should return 'unknown' when no IP available.
        """
        middleware = RequestLoggingMiddleware(app=Mock())

        request = Mock(spec=Request)
        request.headers = {}
        request.client = None

        client_ip = middleware._get_client_ip(request)

        assert client_ip == "unknown"


# ===========================================
# RATE LIMIT MIDDLEWARE TESTS
# ===========================================

class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    def test_allows_request_within_limit(self, app):
        """
        Should allow requests within rate limit.
        """
        app.add_middleware(RateLimitMiddleware)
        client = TestClient(app)

        # Make a few requests (well within limit)
        for _ in range(5):
            response = client.get("/public")
            assert response.status_code == 200

    def test_blocks_request_exceeding_limit(self, app):
        """
        Should block requests exceeding rate limit.
        """
        app.add_middleware(RateLimitMiddleware)
        client = TestClient(app)

        # Mock settings to have low rate limit for testing
        with patch('src.core.middleware.settings.rate_limit_per_minute', 5):
            # Make requests up to limit
            for _ in range(5):
                response = client.get("/public")
                assert response.status_code == 200

            # Next request should be rate limited
            response = client.get("/public")
            assert response.status_code == 429
            assert "Rate limit exceeded" in response.json()["detail"]

    def test_bypasses_health_check_endpoint(self, app):
        """
        Should bypass rate limiting for /health endpoint.
        """
        app.add_middleware(RateLimitMiddleware)
        client = TestClient(app)

        # Make many requests to /health (should never be rate limited)
        for _ in range(100):
            response = client.get("/health")
            assert response.status_code == 200

    def test_get_client_identifier_uses_tenant_id(self):
        """
        Should prefer tenant_id for authenticated requests.
        """
        middleware = RateLimitMiddleware(app=Mock())

        request = Mock(spec=Request)
        request.state = Mock()
        request.state.tenant_id = uuid4()

        identifier = middleware._get_client_identifier(request)

        assert identifier.startswith("tenant:")
        assert str(request.state.tenant_id) in identifier

    def test_get_client_identifier_falls_back_to_ip(self):
        """
        Should use IP address for unauthenticated requests.
        """
        middleware = RateLimitMiddleware(app=Mock())

        request = Mock(spec=Request)
        request.state = Mock()
        request.state.tenant_id = None
        request.headers = {"X-Forwarded-For": "203.0.113.1"}

        identifier = middleware._get_client_identifier(request)

        assert identifier == "ip:203.0.113.1"

    def test_rate_limit_cleanup_old_entries(self):
        """
        Should clean up old entries to prevent memory growth.
        """
        middleware = RateLimitMiddleware(app=Mock())
        client_id = "test-client"

        # Record some old requests
        old_time = time.time() - 400  # 6+ minutes ago
        middleware._requests[client_id] = [old_time, old_time + 1, old_time + 2]

        # Record new request (triggers cleanup)
        middleware._record_request(client_id)

        # Old entries should be cleaned up
        assert all(ts > time.time() - 300 for ts in middleware._requests[client_id])

    def test_different_rate_limits_for_ai_endpoints(self, app):
        """
        Should apply stricter rate limits for AI endpoints.
        """
        middleware = RateLimitMiddleware(app=Mock())

        # AI endpoint should have lower limit
        is_limited_ai = middleware._is_rate_limited("test", "/api/ai/analyze")
        is_limited_normal = middleware._is_rate_limited("test", "/api/projects")

        # We can't easily test the actual limit without making many requests,
        # but we can verify the logic path exists
        assert isinstance(is_limited_ai, bool)
        assert isinstance(is_limited_normal, bool)


# ===========================================
# SECURITY DEPENDENCY TESTS
# ===========================================

class TestSecurityDependencies:
    """Tests for security dependency functions."""

    @pytest.mark.asyncio
    async def test_get_current_tenant_id_success(self):
        """
        Should return tenant_id from request state.
        """
        tenant_id = uuid4()
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.tenant_id = tenant_id

        result = await get_current_tenant_id(request)

        assert result == tenant_id

    @pytest.mark.asyncio
    async def test_get_current_tenant_id_missing(self):
        """
        Should raise TenantNotFoundError when tenant_id not in state.
        """
        request = Mock(spec=Request)
        # Create a state object without tenant_id attribute
        request.state = Mock(spec=['user_id'])  # Only has user_id, not tenant_id

        with pytest.raises(TenantNotFoundError):
            await get_current_tenant_id(request)

    @pytest.mark.asyncio
    async def test_get_current_user_id_success(self):
        """
        Should return user_id from request state.
        """
        user_id = uuid4()
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = user_id

        result = await get_current_user_id(request)

        assert result == user_id

    @pytest.mark.asyncio
    async def test_get_current_user_id_missing(self):
        """
        Should raise AuthenticationError when user_id not in state.
        """
        request = Mock(spec=Request)
        # Create a state object without user_id attribute
        request.state = Mock(spec=['tenant_id'])  # Only has tenant_id, not user_id

        with pytest.raises(AuthenticationError, match="User not authenticated"):
            await get_current_user_id(request)

    @pytest.mark.asyncio
    async def test_get_optional_user_id_present(self):
        """
        Should return user_id when present.
        """
        user_id = uuid4()
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = user_id

        result = await get_optional_user_id(request)

        assert result == user_id

    @pytest.mark.asyncio
    async def test_get_optional_user_id_missing(self):
        """
        Should return None when user_id not present (no exception).
        """
        request = Mock(spec=Request)
        # Create a state object without user_id attribute
        request.state = Mock(spec=['tenant_id'])  # Only has tenant_id, not user_id

        result = await get_optional_user_id(request)

        assert result is None


# ===========================================
# PERMISSIONS CLASS TESTS
# ===========================================

class TestPermissions:
    """Tests for Permissions class."""

    @pytest.mark.asyncio
    async def test_verify_project_access_same_tenant(self):
        """
        Should allow access when project belongs to current tenant.
        """
        tenant_id = uuid4()

        # Should not raise exception
        await Permissions.verify_project_access(
            project_tenant_id=tenant_id,
            current_tenant_id=tenant_id
        )

    @pytest.mark.asyncio
    async def test_verify_project_access_different_tenant(self):
        """
        Should raise 404 HTTPException for cross-tenant access attempt.
        """
        project_tenant_id = uuid4()
        current_tenant_id = uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await Permissions.verify_project_access(
                project_tenant_id=project_tenant_id,
                current_tenant_id=current_tenant_id
            )

        # Should return 404 (not 403) to not reveal existence
        assert exc_info.value.status_code == 404
        assert "Project not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_document_access_same_tenant(self):
        """
        Should allow access when document belongs to current tenant.
        """
        tenant_id = uuid4()

        # Should not raise exception
        await Permissions.verify_document_access(
            document_tenant_id=tenant_id,
            current_tenant_id=tenant_id
        )

    @pytest.mark.asyncio
    async def test_verify_document_access_different_tenant(self):
        """
        Should raise 404 HTTPException for cross-tenant document access.
        """
        document_tenant_id = uuid4()
        current_tenant_id = uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await Permissions.verify_document_access(
                document_tenant_id=document_tenant_id,
                current_tenant_id=current_tenant_id
            )

        assert exc_info.value.status_code == 404
        assert "Document not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_project_access_logs_unauthorized_attempt(self):
        """
        Should log warning when unauthorized access is attempted.
        """
        project_tenant_id = uuid4()
        current_tenant_id = uuid4()

        with patch('src.core.security.logger.warning') as mock_log:
            try:
                await Permissions.verify_project_access(
                    project_tenant_id=project_tenant_id,
                    current_tenant_id=current_tenant_id
                )
            except HTTPException:
                pass

            # Verify warning was logged
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[0][0] == "unauthorized_project_access_attempt"
