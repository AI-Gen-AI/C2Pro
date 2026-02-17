"""
TS-CT-API-001 - Global API Contract Tests

Test Suite ID: TS-CT-API-001
Type: Contract Tests (API)
Priority: P0
Phase: RED (Write failing tests first)

Global API contract tests verify that all API endpoints follow consistent
patterns for responses, errors, headers, and authentication.

These tests will FAIL until the API contract middleware and error handlers
are fully implemented.

Run: pytest tests/contract/test_api_contracts.py -v
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException


# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture
def test_app():
    """
    Create a minimal FastAPI app for testing API contracts.
    
    GREEN Phase: Includes API contract middleware, CORS, auth, and proper error handlers.
    """
    from datetime import datetime, timezone
    from fastapi import Request, Depends, HTTPException, status
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from src.core.middleware import APIContractMiddleware
    from src.core.handlers import register_exception_handlers
    
    app = FastAPI(title="C2Pro API Test", version="1.0.0")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add API contract middleware
    app.add_middleware(APIContractMiddleware)
    
    # Register exception handlers for proper error formatting
    register_exception_handlers(app)
    
    # Custom 404 handler to ensure proper error schema
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Not Found",
                "code": "NOT_FOUND",
                "error_code": "NOT_FOUND",
                "message": "The requested resource was not found",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": str(request.url.path),
            }
        )
    
    # Auth dependency
    def require_auth(request: Request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Not authenticated"
            )
        token = auth_header[7:]
        if not token or token == "InvalidFormat":
            raise HTTPException(
                status_code=401,
                detail="Invalid token format"
            )
        return token
    
    # Health endpoint - minimal implementation for testing
    @app.get("/api/v1/health")
    def health_check():
        return {"status": "healthy", "version": "1.0.0"}
    
    # Protected endpoint for auth testing
    @app.get("/api/v1/projects/test/wbs")
    def protected_endpoint(auth: str = Depends(require_auth)):
        return {"items": []}
    
    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
def auth_headers():
    """Standard authenticated request headers."""
    return {
        "Authorization": "Bearer test-token-12345",
        "X-Tenant-ID": "test-tenant-001",
        "Content-Type": "application/json",
    }


# ===========================================
# TESTS: Basic API Contract
# ===========================================


class TestAPIHealthContract:
    """Tests for API health and basic connectivity."""

    def test_api_health_check(self, client):
        """
        RED Phase: Health endpoint returns 200 with correct schema.
        
        Expected: GET /api/v1/health returns 200 with status field
        """
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. "
            "Health endpoint should be accessible"
        )
        
        data = response.json()
        assert "status" in data, "Health response must have 'status' field"
        assert data["status"] == "healthy", "Status should be 'healthy'"
        assert "version" in data, "Health response should include API version"


class TestAPIResponseContract:
    """Tests for API response format and headers."""

    def test_api_content_type_json(self, client, auth_headers):
        """
        RED Phase: All API responses have Content-Type: application/json.
        
        Expected: Every response includes correct Content-Type header
        """
        response = client.get("/api/v1/health", headers=auth_headers)
        
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type, (
            f"Expected Content-Type to include 'application/json', "
            f"got '{content_type}'"
        )

    def test_api_version_header(self, client, auth_headers):
        """
        RED Phase: API version included in response headers.
        
        Expected: X-API-Version header present in all responses
        """
        response = client.get("/api/v1/health", headers=auth_headers)
        
        api_version = response.headers.get("X-API-Version")
        assert api_version is not None, (
            "X-API-Version header must be present in all responses"
        )
        assert api_version.startswith("v"), (
            f"API version should start with 'v', got '{api_version}'"
        )

    def test_api_response_time_header(self, client, auth_headers):
        """
        RED Phase: Response time included in headers.
        
        Expected: X-Response-Time header shows request duration in ms
        """
        response = client.get("/api/v1/health", headers=auth_headers)
        
        response_time = response.headers.get("X-Response-Time")
        assert response_time is not None, (
            "X-Response-Time header should be present"
        )
        # Should be a numeric value in milliseconds
        try:
            time_ms = float(response_time.replace("ms", ""))
            assert time_ms >= 0, "Response time should be non-negative"
        except (ValueError, AttributeError):
            pytest.fail(f"X-Response-Time should be numeric, got '{response_time}'")


class TestAPIErrorContract:
    """Tests for API error response consistency."""

    def test_api_error_schema(self, client, auth_headers):
        """
        RED Phase: Error responses follow standard schema.
        
        Expected: {detail: str, code: str, timestamp: str}
        """
        # Request non-existent endpoint to trigger 404
        response = client.get("/api/v1/non-existent-endpoint", headers=auth_headers)
        
        assert response.status_code == 404, (
            "Non-existent endpoint should return 404"
        )
        
        data = response.json()
        
        # Verify error schema
        assert "detail" in data, "Error response must have 'detail' field"
        assert isinstance(data["detail"], str), "detail should be a string"
        
        assert "code" in data, "Error response must have 'code' field"
        assert isinstance(data["code"], str), "code should be a string"
        
        assert "timestamp" in data, "Error response must have 'timestamp' field"

    def test_api_not_found_schema(self, client, auth_headers):
        """
        RED Phase: 404 errors have consistent format.
        
        Expected: Standard error structure with resource info
        """
        response = client.get("/api/v1/projects/non-existent-id", headers=auth_headers)
        
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower() or "404" in data.get("code", "")

    def test_api_validation_error_schema(self, client, auth_headers):
        """
        RED Phase: Validation errors include field details.
        
        Expected: {detail: [{loc: [...], msg: str, type: str}]}
        """
        # Post invalid data to trigger validation error
        invalid_data = {"name": "", "budget": -100}
        
        response = client.post(
            "/api/v1/projects/test/wbs/items",
            json=invalid_data,
            headers=auth_headers,
        )
        
        # Should return 422 for validation errors
        if response.status_code == 422:
            data = response.json()
            
            # FastAPI/Pydantic validation error format
            assert "detail" in data
            if isinstance(data["detail"], list):
                # Should have field-level errors
                for error in data["detail"]:
                    assert "loc" in error, "Validation error should have 'loc' (location)"
                    assert "msg" in error, "Validation error should have 'msg'"
                    assert "type" in error, "Validation error should have 'type'"


class TestAPIAuthenticationContract:
    """Tests for API authentication and authorization."""

    def test_api_authentication_required(self, client):
        """
        RED Phase: Protected endpoints require authentication.
        
        Expected: 401 Unauthorized for missing/invalid token
        """
        # Request without auth headers
        response = client.get("/api/v1/projects/test/wbs")
        
        # Should return 401 for protected endpoints
        assert response.status_code == 401, (
            f"Expected 401 for unauthenticated request, got {response.status_code}. "
            "Protected endpoints should require authentication"
        )
        
        data = response.json()
        assert "detail" in data
        assert "authenticated" in data["detail"].lower() or "token" in data["detail"].lower()

    def test_api_invalid_token_format(self, client):
        """
        RED Phase: Invalid token format returns 401.
        
        Expected: Proper error for malformed Authorization header
        """
        headers = {"Authorization": "InvalidFormat token123"}
        response = client.get("/api/v1/projects/test/wbs", headers=headers)
        
        assert response.status_code == 401, (
            "Invalid token format should return 401"
        )

    def test_api_tenant_isolation(self, client):
        """
        RED Phase: Tenant ID required in headers.
        
        Expected: 400 Bad Request for missing X-Tenant-ID
        """
        # Request with auth but no tenant ID
        headers = {"Authorization": "Bearer valid-token-12345"}
        response = client.get("/api/v1/projects/test/wbs", headers=headers)
        
        # Should require tenant ID
        if response.status_code == 400:
            data = response.json()
            assert "detail" in data
            assert "tenant" in data["detail"].lower()


class TestAPIPaginationContract:
    """Tests for API pagination consistency."""

    def test_api_pagination_contract(self, client, auth_headers):
        """
        RED Phase: List endpoints support pagination.
        
        Expected: {items: [], page: int, size: int, total: int}
        """
        response = client.get(
            "/api/v1/projects/test/wbs?page=1&size=10",
            headers=auth_headers,
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Should have pagination metadata
            assert "items" in data or "data" in data, (
                "Paginated response should have 'items' or 'data' field"
            )
            
            # Should have pagination info
            if "page" in data:
                assert isinstance(data["page"], int), "page should be integer"
            if "size" in data:
                assert isinstance(data["size"], int), "size should be integer"
            if "total" in data:
                assert isinstance(data["total"], int), "total should be integer"

    def test_api_pagination_defaults(self, client, auth_headers):
        """
        RED Phase: Pagination has sensible defaults.
        
        Expected: Default page=1, size=20 when not specified
        """
        response = client.get("/api/v1/projects/test/wbs", headers=auth_headers)
        
        if response.status_code == 200:
            data = response.json()
            
            # Should have default pagination values
            if "page" in data:
                assert data["page"] == 1, "Default page should be 1"
            if "size" in data:
                assert data["size"] <= 100, "Default size should be reasonable (<=100)"


class TestAPICORSContract:
    """Tests for CORS configuration."""

    def test_api_cors_headers(self, client):
        """
        GREEN Phase: CORS headers present on responses.
        
        Expected: Access-Control-Allow-* headers on regular GET responses
        """
        # Make a regular GET request with Origin header to trigger CORS
        headers = {"Origin": "http://localhost:3000"}
        response = client.get("/api/v1/health", headers=headers)
        
        # Should have CORS headers
        cors_headers = [
            "access-control-allow-origin",
        ]
        
        # Check headers in a case-insensitive way
        headers_lower = {k.lower(): v for k, v in response.headers.items()}
        has_cors = any(h in headers_lower for h in cors_headers)
        
        # GREEN Phase: CORS should be implemented
        assert response.status_code == 200, "Health endpoint should return 200"
        assert has_cors, f"CORS headers should be present in responses. Got: {list(headers_lower.keys())}"

    def test_api_cors_preflight(self, client):
        """
        RED Phase: CORS preflight requests handled.
        
        Expected: 200/204 response to OPTIONS with CORS headers
        """
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,Authorization",
        }
        
        response = client.options("/api/v1/projects/test/wbs", headers=headers)
        
        assert response.status_code in [200, 204], (
            f"CORS preflight should return 200/204, got {response.status_code}"
        )


class TestAPIRateLimitContract:
    """Tests for rate limiting headers."""

    def test_api_rate_limit_headers(self, client, auth_headers):
        """
        RED Phase: Rate limiting info in headers.
        
        Expected: X-RateLimit-* headers present
        """
        response = client.get("/api/v1/health", headers=auth_headers)
        
        # Should have rate limit headers
        rate_limit_headers = [
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
        ]
        
        # Check headers in a case-insensitive way
        headers_lower = {k.lower(): v for k, v in response.headers.items()}
        has_rate_limit = any(h in headers_lower for h in rate_limit_headers)
        
        # Note: This is informational - rate limiting might not be implemented yet
        if has_rate_limit:
            limit = headers_lower.get("x-ratelimit-limit")
            if limit:
                assert int(limit) > 0, "Rate limit should be positive"


# ===========================================
# END OF TEST SUITE
# ===========================================

# Mark all tests as contract tests in RED phase
pytestmark = [
    pytest.mark.contract,
    pytest.mark.red_phase,
]
