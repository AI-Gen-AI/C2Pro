"""
Test Suite: TS-UAD-HTTP-ERR-001 - Error Handlers Validation
Component: Core - Global Exception Handlers
Priority: P1 (High)
Coverage Target: 95%

This test suite validates all four registered exception handlers:
1. HTTPException          → http_exception_handler        (unified format + backward-compat detail)
2. RequestValidationError → request_validation_error_handler (field_errors flattening)
3. C2ProException         → c2pro_exception_handler        (domain exceptions via to_dict)
4. Exception              → general_exception_handler      (500 catch-all; prod vs dev branching)

Methodology: TDD Strict (Red → Green → Refactor)
Testing Approach: Unit tests — minimal FastAPI app with handlers registered;
    purpose-built routes that raise each exception type. No middleware, no DB.
"""

import uuid

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from pydantic import BaseModel
from unittest.mock import MagicMock, patch

from src.core.handlers import register_exception_handlers
from src.core.exceptions import (
    AuthenticationError,
    BusinessLogicException,
    ResourceNotFoundError,
)


# ===========================================
# TEST APPLICATION SETUP
# ===========================================


class _Payload(BaseModel):
    """Minimal body model — used to trigger RequestValidationError."""

    name: str
    email: str


@pytest.fixture
def mock_settings():
    """
    Mock settings injected into src.core.handlers at request time.

    Defaults to production mode so that:
      - request_validation_error_handler omits raw_errors
      - general_exception_handler uses the production branch

    Tests that need the dev branch flip is_production = False directly.
    """
    s = MagicMock()
    s.is_production = True
    s.is_development = False
    return s


@pytest.fixture
def app(mock_settings):
    """
    Minimal FastAPI app: handlers registered + one route per exception type.

    The patch on src.core.handlers.settings stays active for the entire
    lifetime of the fixture (across all requests made by the client).
    """
    _app = FastAPI()
    register_exception_handlers(_app)

    # --- HTTPException routes (tested by TestHTTPExceptionHandler) ---

    @_app.get("/http-404")
    async def _http_404():
        raise HTTPException(status_code=404, detail="Resource not found")

    @_app.get("/http-400")
    async def _http_400():
        raise HTTPException(status_code=400, detail="Bad request")

    @_app.get("/http-409")
    async def _http_409():
        raise HTTPException(status_code=409, detail="Conflict detected")

    # --- Pydantic validation route (tested by TestValidationErrorHandler) ---

    @_app.post("/validate")
    async def _validate(payload: _Payload):
        return {"ok": True}

    # --- C2ProException routes (tested by TestC2ProExceptionHandler) ---

    @_app.get("/not-found")
    async def _not_found():
        raise ResourceNotFoundError("Project", "proj-abc-123")

    @_app.get("/auth-error")
    async def _auth_error():
        raise AuthenticationError()

    @_app.get("/biz-error")
    async def _biz_error():
        raise BusinessLogicException(
            "Cannot delete project with documents",
            rule_violated="BIZ-001",
        )

    # --- General (unhandled) exception route (tested by TestGeneralExceptionHandler) ---

    @_app.get("/crash")
    async def _crash():
        raise RuntimeError("Something went very wrong")

    with patch("src.core.handlers.settings", mock_settings):
        yield _app


@pytest.fixture
def client(app):
    """TestClient with server-exception suppression — handlers return responses."""
    return TestClient(app, raise_server_exceptions=False)


# ===========================================
# UAD-HTTP-007 — HTTPException Handler
# ===========================================


class TestHTTPExceptionHandler:
    """
    Test Suite for http_exception_handler.
    Tests: UAD-HTTP-007a, UAD-HTTP-007b, UAD-HTTP-007c

    Validates that standard FastAPI HTTPExceptions are transformed to the
    unified error schema and include the backward-compatible 'detail' field.
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_uad_http_007a_404_unified_format(self, client):
        """
        UAD-HTTP-007a — Full unified schema on 404

        Given: An endpoint that raises HTTPException(404, detail="Resource not found")
        When:  GET /http-404
        Then:  Response is 404 with status_code, error_code, message,
               timestamp, path, and backward-compat detail field.
        """
        response = client.get("/http-404")
        body = response.json()

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert body["status_code"] == 404
        assert body["error_code"] == "NOT_FOUND"
        assert body["message"] == "Resource not found"
        assert "timestamp" in body and body["timestamp"]
        assert body["path"] == "/http-404"
        # Backward-compat field preserved for existing clients
        assert body["detail"] == "Resource not found"

    @pytest.mark.unit
    def test_uad_http_007b_400_maps_bad_request(self, client):
        """
        UAD-HTTP-007b — 400 maps to BAD_REQUEST

        Given: An endpoint that raises HTTPException(400)
        When:  GET /http-400
        Then:  error_code is BAD_REQUEST, message is the detail string.
        """
        response = client.get("/http-400")
        body = response.json()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert body["error_code"] == "BAD_REQUEST"
        assert body["message"] == "Bad request"

    @pytest.mark.unit
    def test_uad_http_007c_409_maps_conflict(self, client):
        """
        UAD-HTTP-007c — 409 maps to CONFLICT

        Given: An endpoint that raises HTTPException(409)
        When:  GET /http-409
        Then:  error_code is CONFLICT, message is the detail string.
        """
        response = client.get("/http-409")
        body = response.json()

        assert response.status_code == 409
        assert body["error_code"] == "CONFLICT"
        assert body["message"] == "Conflict detected"


# ===========================================
# UAD-HTTP-008 — RequestValidationError Handler
# ===========================================


class TestValidationErrorHandler:
    """
    Test Suite for request_validation_error_handler.
    Tests: UAD-HTTP-008a, UAD-HTTP-008b, UAD-HTTP-008c

    Validates that Pydantic validation errors are flattened from the verbose
    [{loc, msg, type}] structure into a frontend-friendly {field: message} dict.
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_uad_http_008a_empty_body_returns_422(self, client):
        """
        UAD-HTTP-008a — Empty body yields 422 with full unified schema

        Given: POST /validate with empty JSON body {}
        When:  Pydantic rejects the request (name and email both missing)
        Then:  422, error_code=VALIDATION_ERROR, message matches,
               details.field_errors is present.
        """
        response = client.post("/validate", json={})
        body = response.json()

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert body["status_code"] == 422
        assert body["error_code"] == "VALIDATION_ERROR"
        assert body["message"] == "Request validation failed"
        assert "details" in body
        assert "field_errors" in body["details"]

    @pytest.mark.unit
    def test_uad_http_008b_both_missing_fields_reported(self, client):
        """
        UAD-HTTP-008b — Both missing required fields appear in field_errors

        Given: POST /validate with {} (name AND email missing)
        When:  Handler flattens Pydantic errors
        Then:  field_errors dict contains keys for both 'name' and 'email'.
        """
        response = client.post("/validate", json={})
        field_errors = response.json()["details"]["field_errors"]

        assert "name" in field_errors
        assert "email" in field_errors

    @pytest.mark.unit
    def test_uad_http_008c_partial_payload_reports_only_missing(self, client):
        """
        UAD-HTTP-008c — Partial payload only flags the missing field

        Given: POST /validate with {"name": "Alice"} (email missing, name present)
        When:  Handler flattens Pydantic errors
        Then:  field_errors contains 'email' but NOT 'name'.
        """
        response = client.post("/validate", json={"name": "Alice"})
        body = response.json()

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        field_errors = body["details"]["field_errors"]
        assert "email" in field_errors
        assert "name" not in field_errors


# ===========================================
# UAD-HTTP-012 — C2ProException Handler
# ===========================================


class TestC2ProExceptionHandler:
    """
    Test Suite for c2pro_exception_handler.
    Tests: UAD-HTTP-012a, UAD-HTTP-012b, UAD-HTTP-012c

    Validates domain exceptions are serialised correctly via to_dict() —
    status code, error_code, details payload, path injection.
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_uad_http_012a_resource_not_found_error(self, client):
        """
        UAD-HTTP-012a — ResourceNotFoundError → 404 with full details

        Given: An endpoint that raises ResourceNotFoundError("Project", "proj-abc-123")
        When:  GET /not-found
        Then:  404, error_code=RESOURCE_NOT_FOUND, message mentions both
               resource type and id, details carry resource_type & resource_id,
               path is injected by the handler.
        """
        response = client.get("/not-found")
        body = response.json()

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert body["error_code"] == "RESOURCE_NOT_FOUND"
        assert "Project" in body["message"]
        assert "proj-abc-123" in body["message"]
        assert body["details"]["resource_type"] == "Project"
        assert body["details"]["resource_id"] == "proj-abc-123"
        assert body["path"] == "/not-found"

    @pytest.mark.unit
    def test_uad_http_012b_authentication_error(self, client):
        """
        UAD-HTTP-012b — AuthenticationError → 401, no details key

        Given: An endpoint that raises AuthenticationError() (no extra details)
        When:  GET /auth-error
        Then:  401, error_code=AUTHENTICATION_ERROR, default message.
               details is empty → to_dict omits the key entirely.
        """
        response = client.get("/auth-error")
        body = response.json()

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert body["error_code"] == "AUTHENTICATION_ERROR"
        assert body["message"] == "Authentication failed"
        # Empty details dict is falsy → to_dict does not include "details"
        assert "details" not in body

    @pytest.mark.unit
    def test_uad_http_012c_business_logic_error_carries_rule(self, client):
        """
        UAD-HTTP-012c — BusinessLogicException carries rule_violated in details

        Given: An endpoint that raises BusinessLogicException with rule_violated="BIZ-001"
        When:  GET /biz-error
        Then:  400, error_code=BUSINESS_LOGIC_ERROR,
               details.rule_violated == "BIZ-001".
        """
        response = client.get("/biz-error")
        body = response.json()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert body["error_code"] == "BUSINESS_LOGIC_ERROR"
        assert body["message"] == "Cannot delete project with documents"
        assert body["details"]["rule_violated"] == "BIZ-001"


# ===========================================
# UAD-HTTP-013 — General Exception Handler (500 catch-all)
# ===========================================


class TestGeneralExceptionHandler:
    """
    Test Suite for general_exception_handler.
    Tests: UAD-HTTP-013a, UAD-HTTP-013b, UAD-HTTP-013c

    Validates the catch-all 500 handler:
      - reference_id is always generated as a valid UUID
      - dev mode exposes error_type, error_message, stack_trace_preview
      - prod mode suppresses internals and adds support_email
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_uad_http_013a_unhandled_returns_500_with_reference(self, client):
        """
        UAD-HTTP-013a — Unhandled exception → 500 + valid UUID reference_id

        Given: An endpoint that raises RuntimeError (not a C2ProException)
        When:  GET /crash
        Then:  500, error_code=INTERNAL_SERVER_ERROR,
               details.reference_id is a valid UUID4 string.
        """
        response = client.get("/crash")
        body = response.json()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert body["error_code"] == "INTERNAL_SERVER_ERROR"
        assert "details" in body
        # Validate reference_id is a well-formed UUID — raises ValueError otherwise
        uuid.UUID(body["details"]["reference_id"])

    @pytest.mark.unit
    def test_uad_http_013b_dev_mode_exposes_error_details(self, client, mock_settings):
        """
        UAD-HTTP-013b — Development mode includes error_type, message, stack preview

        Given: settings.is_production = False (development)
        When:  GET /crash
        Then:  details contains error_type == "RuntimeError",
               error_message == the exception string,
               stack_trace_preview is a list of strings.
        """
        mock_settings.is_production = False

        response = client.get("/crash")
        body = response.json()
        details = body["details"]

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert details["error_type"] == "RuntimeError"
        assert details["error_message"] == "Something went very wrong"
        assert "stack_trace_preview" in details
        assert isinstance(details["stack_trace_preview"], list)

    @pytest.mark.unit
    def test_uad_http_013c_production_mode_hides_details(self, client, mock_settings):
        """
        UAD-HTTP-013c — Production mode suppresses all internal details

        Given: settings.is_production = True
        When:  GET /crash
        Then:  message is generic ("contact support"),
               details has support_email but NOT error_type or stack_trace_preview.
        """
        mock_settings.is_production = True

        response = client.get("/crash")
        body = response.json()
        details = body["details"]

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "contact support" in body["message"].lower()
        assert details["support_email"] == "support@c2pro.app"
        assert "error_type" not in details
        assert "stack_trace_preview" not in details
