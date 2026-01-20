"""
Tests para verificar el error handling consistente de la API.

Verifica que todos los errores devuelven el formato unificado:
{
    "status_code": 400,
    "error_code": "INVALID_INPUT",
    "message": "Descripción legible",
    "details": {...},
    "timestamp": "ISO-8601",
    "path": "/api/v1/..."
}
"""

import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from src.core.exceptions import (
    BusinessLogicException,
    PermissionDeniedException,
    QuotaExceededException,
    ResourceNotFoundError,
    ValidationError,
)
from src.core.handlers import register_exception_handlers


# ===========================================
# TEST FIXTURES
# ===========================================


@pytest.fixture
def app() -> FastAPI:
    """Crea una aplicación FastAPI con los handlers registrados."""
    app = FastAPI()
    register_exception_handlers(app)

    # Endpoint de prueba para errores de validación de Pydantic
    class UserCreate(BaseModel):
        email: str = Field(..., min_length=5)
        password: str = Field(..., min_length=8)
        age: int = Field(..., ge=18, le=120)

    @app.post("/test/pydantic-validation")
    async def test_pydantic_validation(user: UserCreate):
        return {"success": True}

    # Endpoint de prueba para excepciones personalizadas
    @app.get("/test/resource-not-found")
    async def test_resource_not_found():
        raise ResourceNotFoundError("Project", "123")

    @app.get("/test/business-logic")
    async def test_business_logic():
        raise BusinessLogicException(
            "Cannot delete project with active documents", rule_violated="active_documents_check"
        )

    @app.get("/test/permission-denied")
    async def test_permission_denied():
        raise PermissionDeniedException("Access denied", required_permission="project:delete")

    @app.get("/test/quota-exceeded")
    async def test_quota_exceeded():
        raise QuotaExceededException(
            message="Monthly AI budget exceeded",
            quota_type="ai_budget",
            current_value=55.0,
            limit_value=50.0,
        )

    @app.get("/test/unhandled-exception")
    async def test_unhandled_exception():
        # Simular un error no esperado
        raise ValueError("This is an unexpected error")

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Cliente de prueba."""
    # raise_server_exceptions=False permite que los exception handlers funcionen
    return TestClient(app, raise_server_exceptions=False)


# ===========================================
# TESTS
# ===========================================


def test_pydantic_validation_error_format(client: TestClient):
    """
    Test que los errores de validación de Pydantic se transforman correctamente.

    El formato debe ser amigable para el frontend: {campo: mensaje}
    """
    response = client.post(
        "/test/pydantic-validation",
        json={
            "email": "a",  # Demasiado corto
            "password": "123",  # Demasiado corto
            # age falta (required)
        },
    )

    assert response.status_code == 422

    data = response.json()

    # Verificar esquema de error unificado
    assert "status_code" in data
    assert "error_code" in data
    assert "message" in data
    assert "timestamp" in data
    assert "path" in data

    # Verificar valores
    assert data["status_code"] == 422
    assert data["error_code"] == "VALIDATION_ERROR"
    assert data["message"] == "Request validation failed"
    assert data["path"] == "/test/pydantic-validation"

    # Verificar que timestamp es ISO-8601
    assert "T" in data["timestamp"]
    assert "Z" in data["timestamp"] or "+" in data["timestamp"]

    # Verificar detalles de validación
    assert "details" in data
    assert "field_errors" in data["details"]

    field_errors = data["details"]["field_errors"]

    # Verificar que los errores están en formato {campo: mensaje}
    assert "email" in field_errors
    assert "password" in field_errors
    assert "age" in field_errors

    # Verificar mensajes
    assert "at least 5 characters" in field_errors["email"].lower()
    assert "at least 8 characters" in field_errors["password"].lower()
    assert "required" in field_errors["age"].lower() or "missing" in field_errors["age"].lower()


def test_resource_not_found_error_format(client: TestClient):
    """Test que ResourceNotFoundError devuelve formato correcto."""
    response = client.get("/test/resource-not-found")

    assert response.status_code == 404

    data = response.json()

    # Verificar esquema
    assert data["status_code"] == 404
    assert data["error_code"] == "RESOURCE_NOT_FOUND"
    assert "Project with id '123' not found" in data["message"]
    assert data["path"] == "/test/resource-not-found"

    # Verificar detalles
    assert "details" in data
    assert data["details"]["resource_type"] == "Project"
    assert data["details"]["resource_id"] == "123"


def test_business_logic_error_format(client: TestClient):
    """Test que BusinessLogicException devuelve formato correcto."""
    response = client.get("/test/business-logic")

    assert response.status_code == 400

    data = response.json()

    # Verificar esquema
    assert data["status_code"] == 400
    assert data["error_code"] == "BUSINESS_LOGIC_ERROR"
    assert "Cannot delete project" in data["message"]

    # Verificar detalles
    assert "details" in data
    assert data["details"]["rule_violated"] == "active_documents_check"


def test_permission_denied_error_format(client: TestClient):
    """Test que PermissionDeniedException devuelve formato correcto."""
    response = client.get("/test/permission-denied")

    assert response.status_code == 403

    data = response.json()

    # Verificar esquema
    assert data["status_code"] == 403
    assert data["error_code"] == "PERMISSION_DENIED"
    assert "Access denied" in data["message"]

    # Verificar detalles
    assert "details" in data
    assert data["details"]["required_permission"] == "project:delete"


def test_quota_exceeded_error_format(client: TestClient):
    """Test que QuotaExceededException devuelve formato correcto."""
    response = client.get("/test/quota-exceeded")

    assert response.status_code == 429

    data = response.json()

    # Verificar esquema
    assert data["status_code"] == 429
    assert data["error_code"] == "QUOTA_EXCEEDED"
    assert "budget exceeded" in data["message"].lower()

    # Verificar detalles
    assert "details" in data
    assert data["details"]["quota_type"] == "ai_budget"
    assert data["details"]["current_value"] == 55.0
    assert data["details"]["limit_value"] == 50.0


def test_unhandled_exception_format(client: TestClient):
    """
    Test que las excepciones no manejadas devuelven formato seguro.

    NO debe exponer stack trace al usuario.
    Debe incluir reference_id para soporte.
    """
    response = client.get("/test/unhandled-exception")

    assert response.status_code == 500

    data = response.json()

    # Verificar esquema
    assert data["status_code"] == 500
    assert data["error_code"] == "INTERNAL_SERVER_ERROR"

    # Verificar detalles
    assert "details" in data
    assert "reference_id" in data["details"]

    # Verificar que NO se expone stack trace completo (seguridad)
    # En desarrollo puede haber un preview, pero no el stack completo
    data_str = json.dumps(data)
    assert "Traceback (most recent call last)" not in data_str

    # Verificar que reference_id es UUID válido
    reference_id = data["details"]["reference_id"]
    assert len(reference_id) == 36  # Formato UUID
    assert reference_id.count("-") == 4


def test_all_errors_have_timestamp(client: TestClient):
    """Verifica que todos los errores incluyen timestamp ISO-8601."""
    endpoints = [
        "/test/resource-not-found",
        "/test/business-logic",
        "/test/permission-denied",
        "/test/quota-exceeded",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        data = response.json()

        assert "timestamp" in data, f"Missing timestamp in {endpoint}"

        # Verificar formato ISO-8601
        timestamp = data["timestamp"]
        assert "T" in timestamp, f"Invalid timestamp format in {endpoint}"
        assert (
            "Z" in timestamp or "+" in timestamp or "-" in timestamp[10:]
        ), f"Missing timezone in {endpoint}"


def test_all_errors_have_path(client: TestClient):
    """Verifica que todos los errores incluyen el path del endpoint."""
    tests = [
        ("/test/resource-not-found", "/test/resource-not-found"),
        ("/test/business-logic", "/test/business-logic"),
        ("/test/permission-denied", "/test/permission-denied"),
    ]

    for endpoint, expected_path in tests:
        response = client.get(endpoint)
        data = response.json()

        assert "path" in data, f"Missing path in {endpoint}"
        assert data["path"] == expected_path, f"Incorrect path in {endpoint}"


def test_consistent_error_schema_across_all_errors(client: TestClient):
    """
    Verifica que TODOS los errores siguen el mismo esquema base.

    Campos obligatorios:
    - status_code
    - error_code
    - message
    - timestamp
    - path

    Campos opcionales:
    - details
    """
    endpoints = [
        "/test/resource-not-found",
        "/test/business-logic",
        "/test/permission-denied",
        "/test/quota-exceeded",
        "/test/unhandled-exception",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        data = response.json()

        # Verificar campos obligatorios
        required_fields = ["status_code", "error_code", "message", "timestamp", "path"]
        for field in required_fields:
            assert field in data, f"Missing required field '{field}' in {endpoint}"

        # Verificar tipos
        assert isinstance(data["status_code"], int), f"Invalid status_code type in {endpoint}"
        assert isinstance(data["error_code"], str), f"Invalid error_code type in {endpoint}"
        assert isinstance(data["message"], str), f"Invalid message type in {endpoint}"
        assert isinstance(data["timestamp"], str), f"Invalid timestamp type in {endpoint}"
        assert isinstance(data["path"], str), f"Invalid path type in {endpoint}"
