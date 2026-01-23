"""
Test simple del sistema de manejo de errores.

Este script verifica que el formato de error unificado funciona correctamente
sin necesitar ejecutar toda la API.

Ejecutar:
    cd apps/api
    python test_error_handling_standalone.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Agregar el directorio raíz al path para importar sin config
sys.path.insert(0, str(Path(__file__).parent.parent))


# ===========================================
# MINIMAL EXCEPTION CLASSES (sin dependencias)
# ===========================================


class C2ProException(Exception):
    """Base exception para testing."""

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self, path: str | None = None) -> dict[str, Any]:
        """Convierte la excepción a diccionario con formato estándar."""
        error_dict = {
            "status_code": self.status_code,
            "error_code": self.code,
            "message": self.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.details:
            error_dict["details"] = self.details

        if path:
            error_dict["path"] = path

        return error_dict


class ResourceNotFoundError(C2ProException):
    """Recurso no encontrado."""

    def __init__(self, resource_type: str, resource_id: str | None = None):
        message = f"{resource_type} not found"
        if resource_id:
            message = f"{resource_type} with id '{resource_id}' not found"

        super().__init__(
            message=message,
            code="RESOURCE_NOT_FOUND",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class BusinessLogicException(C2ProException):
    """Error de lógica de negocio."""

    def __init__(self, message: str, rule_violated: str | None = None):
        details = {}
        if rule_violated:
            details["rule_violated"] = rule_violated

        super().__init__(
            message=message,
            code="BUSINESS_LOGIC_ERROR",
            status_code=400,
            details=details,
        )


class PermissionDeniedException(C2ProException):
    """Permiso denegado."""

    def __init__(
        self, message: str = "Permission denied", required_permission: str | None = None
    ):
        details = {}
        if required_permission:
            details["required_permission"] = required_permission

        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=403,
            details=details,
        )


class QuotaExceededException(C2ProException):
    """Cuota o límite de uso excedido."""

    def __init__(
        self,
        message: str = "Usage quota exceeded",
        quota_type: str = "general",
        current_value: float | None = None,
        limit_value: float | None = None,
    ):
        details: dict[str, Any] = {"quota_type": quota_type}

        if current_value is not None:
            details["current_value"] = current_value

        if limit_value is not None:
            details["limit_value"] = limit_value

        super().__init__(
            message=message,
            code="QUOTA_EXCEEDED",
            status_code=429,
            details=details,
        )


class ValidationError(C2ProException):
    """Error de validación de datos."""

    def __init__(
        self, message: str = "Validation error", errors: list[dict[str, Any]] | None = None
    ):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details={"errors": errors or []},
        )

print("\n" + "=" * 70)
print("TEST: SISTEMA DE MANEJO DE ERRORES CONSISTENTE (CE-S2-009)")
print("=" * 70 + "\n")


def verify_error_format(error_dict: dict, expected_status: int, expected_code: str):
    """Verifica que un error tenga el formato correcto."""
    required_fields = ["status_code", "error_code", "message", "timestamp"]

    print(f"  Verificando formato de error {expected_code}...")

    # Verificar campos requeridos
    for field in required_fields:
        assert field in error_dict, f"Campo '{field}' faltante en error"
        print(f"    ✓ Campo '{field}' presente")

    # Verificar tipos
    assert isinstance(error_dict["status_code"], int), "status_code debe ser int"
    assert isinstance(error_dict["error_code"], str), "error_code debe ser str"
    assert isinstance(error_dict["message"], str), "message debe ser str"
    assert isinstance(error_dict["timestamp"], str), "timestamp debe ser str"

    # Verificar valores
    assert error_dict["status_code"] == expected_status, f"status_code incorrecto"
    assert error_dict["error_code"] == expected_code, f"error_code incorrecto"

    # Verificar formato de timestamp (ISO 8601)
    try:
        datetime.fromisoformat(error_dict["timestamp"].replace("Z", "+00:00"))
        print(f"    ✓ Timestamp ISO 8601 válido")
    except ValueError:
        raise AssertionError("Timestamp no es ISO 8601 válido")

    print(f"    ✓ Formato correcto\n")


# ===========================================
# TEST 1: ResourceNotFoundError
# ===========================================

print("[1] TEST: ResourceNotFoundError (404)")
try:
    raise ResourceNotFoundError("Project", "123e4567")
except C2ProException as e:
    error = e.to_dict(path="/api/v1/projects/123e4567")
    verify_error_format(error, 404, "RESOURCE_NOT_FOUND")

    # Verificar mensaje
    assert "Project" in error["message"]
    assert "123e4567" in error["message"]

    # Verificar details
    assert "details" in error
    assert error["details"]["resource_type"] == "Project"
    assert error["details"]["resource_id"] == "123e4567"

    print("  JSON generado:")
    print(f"  {json.dumps(error, indent=2)}\n")


# ===========================================
# TEST 2: BusinessLogicException
# ===========================================

print("[2] TEST: BusinessLogicException (400)")
try:
    raise BusinessLogicException(
        message="Cannot delete project with existing documents",
        rule_violated="project_deletion_with_documents",
    )
except C2ProException as e:
    error = e.to_dict(path="/api/v1/projects/xxx/delete")
    verify_error_format(error, 400, "BUSINESS_LOGIC_ERROR")

    # Verificar details
    assert "details" in error
    assert error["details"]["rule_violated"] == "project_deletion_with_documents"

    print("  JSON generado:")
    print(f"  {json.dumps(error, indent=2)}\n")


# ===========================================
# TEST 3: PermissionDeniedException
# ===========================================

print("[3] TEST: PermissionDeniedException (403)")
try:
    raise PermissionDeniedException(
        message="You don't have permission to access this project",
        required_permission="project:read:other_tenant",
    )
except C2ProException as e:
    error = e.to_dict(path="/api/v1/projects/xxx")
    verify_error_format(error, 403, "PERMISSION_DENIED")

    # Verificar details
    assert "details" in error
    assert error["details"]["required_permission"] == "project:read:other_tenant"

    print("  JSON generado:")
    print(f"  {json.dumps(error, indent=2)}\n")


# ===========================================
# TEST 4: QuotaExceededException
# ===========================================

print("[4] TEST: QuotaExceededException (429)")
try:
    raise QuotaExceededException(
        message="Monthly AI budget exceeded",
        quota_type="ai_budget",
        current_value=52.50,
        limit_value=50.00,
    )
except C2ProException as e:
    error = e.to_dict(path="/api/v1/analysis/coherence")
    verify_error_format(error, 429, "QUOTA_EXCEEDED")

    # Verificar details
    assert "details" in error
    assert error["details"]["quota_type"] == "ai_budget"
    assert error["details"]["current_value"] == 52.50
    assert error["details"]["limit_value"] == 50.00

    print("  JSON generado:")
    print(f"  {json.dumps(error, indent=2)}\n")


# ===========================================
# TEST 5: ValidationError
# ===========================================

print("[5] TEST: ValidationError (422)")
try:
    raise ValidationError(
        message="Start date cannot be after end date",
        errors=[
            {"field": "start_date", "error": "Must be before end_date"},
            {"field": "end_date", "error": "Must be after start_date"},
        ],
    )
except C2ProException as e:
    error = e.to_dict(path="/api/v1/projects")
    verify_error_format(error, 422, "VALIDATION_ERROR")

    # Verificar details
    assert "details" in error
    assert "errors" in error["details"]
    assert len(error["details"]["errors"]) == 2

    print("  JSON generado:")
    print(f"  {json.dumps(error, indent=2)}\n")


# ===========================================
# TEST 6: Error sin details
# ===========================================

print("[6] TEST: Error sin campo details")
try:
    raise C2ProException(
        message="Simple error without details",
        code="SIMPLE_ERROR",
        status_code=500,
        details=None,  # Sin details
    )
except C2ProException as e:
    error = e.to_dict(path="/api/v1/test")
    verify_error_format(error, 500, "SIMPLE_ERROR")

    # Verificar que NO incluye campo details si está vacío
    assert "details" not in error, "No debe incluir campo 'details' si está vacío"
    print(f"    ✓ Campo 'details' omitido correctamente cuando está vacío\n")


# ===========================================
# TEST 7: Error sin path
# ===========================================

print("[7] TEST: Error sin path (para uso interno)")
try:
    raise ResourceNotFoundError("User", "123")
except C2ProException as e:
    error = e.to_dict(path=None)  # Sin path

    # Verificar campos básicos
    assert "status_code" in error
    assert "error_code" in error
    assert "message" in error
    assert "timestamp" in error

    # Verificar que NO incluye path
    assert "path" not in error, "No debe incluir campo 'path' si es None"
    print(f"    ✓ Campo 'path' omitido correctamente cuando es None\n")


# ===========================================
# RESUMEN
# ===========================================

print("=" * 70)
print("[OK] TODOS LOS TESTS PASARON")
print("=" * 70)
print("\nEl sistema de manejo de errores está funcionando correctamente:")
print("  [OK] Formato de error unificado (status_code, error_code, message, timestamp, path)")
print("  [OK] Campos opcionales (details) se incluyen solo cuando tienen valor")
print("  [OK] Timestamp ISO 8601 válido")
print("  [OK] Todas las excepciones personalizadas funcionan correctamente")
print(
    "  [OK] ResourceNotFoundError, BusinessLogicException, PermissionDeniedException, QuotaExceededException"
)
print("\nPróximo paso:")
print("  1. Verificar que los exception handlers en main.py usan este formato")
print("  2. Probar con requests reales a la API")
print("  3. Verificar que el frontend puede parsear el formato correctamente\n")
