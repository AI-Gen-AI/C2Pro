"""
C2Pro - Custom Exceptions

Excepciones de dominio para manejo consistente de errores.
"""

from typing import Any


class C2ProException(Exception):
    """Base exception para todas las excepciones de C2Pro."""
    
    def __init__(
        self, 
        message: str, 
        code: str = "UNKNOWN_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# ===========================================
# AUTHENTICATION & AUTHORIZATION
# ===========================================

class AuthenticationError(C2ProException):
    """Error de autenticación."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401
        )


class AuthorizationError(C2ProException):
    """Error de autorización (permisos insuficientes)."""
    
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403
        )


class TenantNotFoundError(C2ProException):
    """Tenant no encontrado en el contexto."""
    
    def __init__(self):
        super().__init__(
            message="Tenant context not found",
            code="TENANT_NOT_FOUND",
            status_code=401
        )


# ===========================================
# RESOURCES
# ===========================================

class ResourceNotFoundError(C2ProException):
    """Recurso no encontrado."""
    
    def __init__(
        self, 
        resource_type: str, 
        resource_id: str | None = None
    ):
        message = f"{resource_type} not found"
        if resource_id:
            message = f"{resource_type} with id '{resource_id}' not found"
        
        super().__init__(
            message=message,
            code="RESOURCE_NOT_FOUND",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id}
        )


class ResourceAlreadyExistsError(C2ProException):
    """Recurso ya existe (conflicto)."""
    
    def __init__(
        self, 
        resource_type: str,
        field: str | None = None,
        value: str | None = None
    ):
        message = f"{resource_type} already exists"
        if field and value:
            message = f"{resource_type} with {field}='{value}' already exists"
        
        super().__init__(
            message=message,
            code="RESOURCE_ALREADY_EXISTS",
            status_code=409,
            details={"resource_type": resource_type, "field": field}
        )


# ===========================================
# VALIDATION
# ===========================================

class ValidationError(C2ProException):
    """Error de validación de datos."""
    
    def __init__(
        self, 
        message: str = "Validation error",
        errors: list[dict[str, Any]] | None = None
    ):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details={"errors": errors or []}
        )


class FileValidationError(ValidationError):
    """Error de validación de archivo."""
    
    def __init__(
        self,
        message: str,
        filename: str | None = None
    ):
        super().__init__(
            message=message,
            errors=[{"filename": filename, "error": message}] if filename else None
        )


# ===========================================
# AI / PROCESSING
# ===========================================

class AIServiceError(C2ProException):
    """Error en servicio de AI."""
    
    def __init__(
        self, 
        message: str = "AI service error",
        provider: str = "anthropic"
    ):
        super().__init__(
            message=message,
            code="AI_SERVICE_ERROR",
            status_code=503,
            details={"provider": provider}
        )


class AIBudgetExceededError(C2ProException):
    """Presupuesto de AI agotado."""
    
    def __init__(
        self,
        current_spend: float,
        budget: float
    ):
        super().__init__(
            message=f"Monthly AI budget exceeded. Current: €{current_spend:.2f}, Limit: €{budget:.2f}",
            code="AI_BUDGET_EXCEEDED",
            status_code=429,
            details={"current_spend": current_spend, "budget": budget}
        )


class AIRateLimitError(C2ProException):
    """Rate limit de AI alcanzado."""
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            message=f"AI rate limit exceeded. Retry after {retry_after} seconds.",
            code="AI_RATE_LIMIT",
            status_code=429,
            details={"retry_after": retry_after}
        )


class DocumentParsingError(C2ProException):
    """Error al parsear documento."""
    
    def __init__(
        self, 
        message: str,
        document_type: str | None = None,
        filename: str | None = None
    ):
        super().__init__(
            message=message,
            code="DOCUMENT_PARSING_ERROR",
            status_code=422,
            details={"document_type": document_type, "filename": filename}
        )


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
            details={"retry_after": retry_after}
        )


# ===========================================
# EXTERNAL SERVICES
# ===========================================

class ExternalServiceError(C2ProException):
    """Error en servicio externo."""
    
    def __init__(
        self, 
        service: str,
        message: str = "External service error"
    ):
        super().__init__(
            message=f"{service}: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=503,
            details={"service": service}
        )


class StorageError(ExternalServiceError):
    """Error en servicio de almacenamiento."""
    
    def __init__(self, message: str = "Storage service error"):
        super().__init__(service="storage", message=message)


class DatabaseError(ExternalServiceError):
    """Error en base de datos."""

    def __init__(self, message: str = "Database error"):
        super().__init__(service="database", message=message)


# ===========================================
# ALIASES FOR BACKWARD COMPATIBILITY
# ===========================================

# Alias for NotFoundError (commonly used in services)
NotFoundError = ResourceNotFoundError

# Alias for ConflictError (commonly used in services)
ConflictError = ResourceAlreadyExistsError
