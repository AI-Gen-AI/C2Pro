"""
C2Pro - Custom Exceptions

Excepciones de dominio para manejo consistente de errores.

Este módulo define la jerarquía de excepciones de C2Pro siguiendo el esquema
de error unificado para garantizar respuestas consistentes al frontend.

Formato de error estándar:
{
    "status_code": 400,
    "error_code": "INVALID_INPUT",
    "message": "Descripción legible para humanos",
    "details": {...},
    "timestamp": "ISO-8601",
    "path": "/api/v1/..."
}

Version: 1.0.0
Date: 2026-01-13
"""

from datetime import datetime, timezone
from typing import Any


class C2ProException(Exception):
    """
    Base exception para todas las excepciones de C2Pro.

    Esta clase proporciona el formato de error unificado que se usa
    en toda la aplicación. Los campos timestamp y path se agregan
    automáticamente en los exception handlers.

    Attributes:
        message: Mensaje legible para humanos
        code: Código de error (ej: "VALIDATION_ERROR", "RESOURCE_NOT_FOUND")
        status_code: Código HTTP (400, 404, 500, etc.)
        details: Detalles adicionales del error (opcional)
    """

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
        """
        Convierte la excepción a diccionario con formato estándar.

        Args:
            path: Ruta del endpoint donde ocurrió el error (ej: "/api/v1/projects")

        Returns:
            Diccionario con formato de error unificado
        """
        error_dict = {
            "status_code": self.status_code,
            "error_code": self.code,
            "message": self.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Solo incluir details si no está vacío
        if self.details:
            error_dict["details"] = self.details

        # Solo incluir path si se proporciona
        if path:
            error_dict["path"] = path

        return error_dict


# ===========================================
# AUTHENTICATION & AUTHORIZATION
# ===========================================


class AuthenticationError(C2ProException):
    """Error de autenticación."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, code="AUTHENTICATION_ERROR", status_code=401)


class AuthorizationError(C2ProException):
    """Error de autorización (permisos insuficientes)."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message=message, code="AUTHORIZATION_ERROR", status_code=403)


class PermissionDeniedException(C2ProException):
    """
    Permiso denegado.

    Alias más explícito de AuthorizationError para casos donde el usuario
    está autenticado pero no tiene permisos para realizar la acción.
    """

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


class TenantNotFoundError(C2ProException):
    """Tenant no encontrado en el contexto."""

    def __init__(self):
        super().__init__(
            message="Tenant context not found", code="TENANT_NOT_FOUND", status_code=401
        )


# ===========================================
# RESOURCES
# ===========================================


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


# Alias for backward compatibility
NotFoundError = ResourceNotFoundError


class ResourceAlreadyExistsError(C2ProException):
    """Recurso ya existe (conflicto)."""

    def __init__(self, resource_type: str, field: str | None = None, value: str | None = None):
        message = f"{resource_type} already exists"
        if field and value:
            message = f"{resource_type} with {field}='{value}' already exists"

        super().__init__(
            message=message,
            code="RESOURCE_ALREADY_EXISTS",
            status_code=409,
            details={"resource_type": resource_type, "field": field},
        )


# Alias for backward compatibility
ConflictError = ResourceAlreadyExistsError


# ===========================================
# VALIDATION & BUSINESS LOGIC
# ===========================================


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


class BusinessLogicException(C2ProException):
    """
    Error de lógica de negocio.

    Para violaciones de reglas de negocio que no son errores de validación
    de esquema pero sí son errores lógicos (ej: no se puede eliminar un
    proyecto con documentos, no se puede cambiar estado de un contrato cerrado).
    """

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


class FileValidationError(ValidationError):
    """Error de validación de archivo."""

    def __init__(self, message: str, filename: str | None = None):
        super().__init__(
            message=message, errors=[{"filename": filename, "error": message}] if filename else None
        )


# ===========================================
# AI / PROCESSING
# ===========================================


class AIServiceError(C2ProException):
    """Error en servicio de AI."""

    def __init__(self, message: str = "AI service error", provider: str = "anthropic"):
        super().__init__(
            message=message,
            code="AI_SERVICE_ERROR",
            status_code=503,
            details={"provider": provider},
        )


class AIBudgetExceededError(C2ProException):
    """Presupuesto de AI agotado."""

    def __init__(self, current_spend: float, budget: float):
        super().__init__(
            message=f"Monthly AI budget exceeded. Current: €{current_spend:.2f}, Limit: €{budget:.2f}",
            code="AI_BUDGET_EXCEEDED",
            status_code=429,
            details={"current_spend": current_spend, "budget": budget},
        )


class AIRateLimitError(C2ProException):
    """Rate limit de AI alcanzado."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message=f"AI rate limit exceeded. Retry after {retry_after} seconds.",
            code="AI_RATE_LIMIT",
            status_code=429,
            details={"retry_after": retry_after},
        )


class DocumentParsingError(C2ProException):
    """Error al parsear documento."""

    def __init__(self, message: str, document_type: str | None = None, filename: str | None = None):
        super().__init__(
            message=message,
            code="DOCUMENT_PARSING_ERROR",
            status_code=422,
            details={"document_type": document_type, "filename": filename},
        )


class DocumentEncryptedError(DocumentParsingError):
    """Error para PDFs encriptados."""

    def __init__(self, filename: str | None = None):
        super().__init__(
            message="Document is encrypted and cannot be processed.",
            document_type="pdf",
            filename=filename,
        )
        self.code = "DOCUMENT_ENCRYPTED"


class ScannedDocumentError(DocumentParsingError):
    """Error para PDFs sin capa de texto (escaneados)."""

    def __init__(self, filename: str | None = None):
        super().__init__(
            message="Document is a scanned image and requires OCR.",
            document_type="pdf",
            filename=filename,
        )
        self.code = "OCR_REQUIRED"


class InvalidFileFormatException(DocumentParsingError):
    """Error para archivos que no cumplen con el formato esperado."""

    def __init__(self, message: str, document_type: str, filename: str | None = None):
        super().__init__(
            message=message,
            document_type=document_type,
            filename=filename,
        )
        self.code = "INVALID_FILE_FORMAT"


# ===========================================
# RATE LIMITING
# ===========================================


class RateLimitExceededError(C2ProException):
    """Rate limit general excedido."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details={"retry_after": retry_after},
        )


class QuotaExceededException(C2ProException):
    """
    Cuota o límite de uso excedido.

    Para control de costes y límites de uso (ej: budget de IA, límite de
    documentos, límite de proyectos, etc.).
    """

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


# ===========================================
# SECURITY
# ===========================================


class SecurityException(C2ProException):
    """
    Error en un componente crítico de seguridad.

    Se usa para fallos en componentes como el anonimizador de PII.
    Implementa una política "fail-closed" por defecto (status 500).
    """

    def __init__(self, message: str, component: str | None = None):
        details = {}
        if component:
            details["component"] = component

        super().__init__(
            message=message,
            code="SECURITY_FAILURE",
            status_code=500,  # Internal Server Error, as it's a configuration/system issue
            details=details,
        )


# ===========================================
# EXTERNAL SERVICES
# ===========================================


class ExternalServiceError(C2ProException):
    """Error en servicio externo."""

    def __init__(self, service: str, message: str = "External service error"):
        super().__init__(
            message=f"{service}: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=503,
            details={"service": service},
        )


class StorageError(ExternalServiceError):
    """Error en servicio de almacenamiento."""

    def __init__(self, message: str = "Storage service error"):
        super().__init__(service="storage", message=message)


class DatabaseError(ExternalServiceError):
    """Error en base de datos."""

    def __init__(self, message: str = "Database error"):
        super().__init__(service="database", message=message)
