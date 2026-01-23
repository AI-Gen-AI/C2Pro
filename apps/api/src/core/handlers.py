"""
C2Pro - Global Exception Handlers

Exception handlers globales para garantizar respuestas de error consistentes
en toda la API.

Esquema de error unificado:
{
    "status_code": 400,
    "error_code": "INVALID_INPUT",
    "message": "Descripción legible para humanos",
    "details": {...},  // Opcional
    "timestamp": "ISO-8601",
    "path": "/api/v1/..."
}

Características:
- Transforma errores de Pydantic a formato amigable para el frontend
- Loggea errores 500 con stack trace sin exponerlo al usuario
- Incluye timestamp y path en todas las respuestas
- Maneja HTTPException, RequestValidationError y Exception genérica

Version: 1.0.0
Date: 2026-01-13
"""

import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.config import settings
from src.core.exceptions import C2ProException

logger = structlog.get_logger()


# ===========================================
# HELPER FUNCTIONS
# ===========================================


def _create_error_response(
    status_code: int,
    error_code: str,
    message: str,
    path: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Crea una respuesta de error con formato estándar.

    Args:
        status_code: Código HTTP (400, 404, 500, etc.)
        error_code: Código de error (ej: "VALIDATION_ERROR", "RESOURCE_NOT_FOUND")
        message: Mensaje legible para humanos
        path: Ruta del endpoint (ej: "/api/v1/projects")
        details: Detalles adicionales del error (opcional)

    Returns:
        Diccionario con formato de error unificado
    """
    error_response = {
        "status_code": status_code,
        "error_code": error_code,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": path,
    }

    if details:
        error_response["details"] = details

    return error_response


def _transform_pydantic_errors(errors: list[dict[str, Any]]) -> dict[str, str]:
    """
    Transforma errores de Pydantic en un diccionario campo -> mensaje.

    Esta transformación es CRÍTICA para el frontend. En lugar de devolver
    la estructura compleja de Pydantic, devolvemos un diccionario simple
    que el frontend puede usar para marcar campos en rojo.

    Ejemplo:
        Input (Pydantic):
        [
            {"loc": ["body", "email"], "msg": "field required"},
            {"loc": ["body", "password"], "msg": "string too short"}
        ]

        Output (Frontend-friendly):
        {
            "email": "field required",
            "password": "string too short"
        }

    Args:
        errors: Lista de errores de Pydantic

    Returns:
        Diccionario {campo: mensaje_error}
    """
    field_errors: dict[str, str] = {}

    for error in errors:
        # Extraer el campo del path (ej: ["body", "email"] -> "email")
        loc = error.get("loc", [])
        field_name = ".".join(str(x) for x in loc if x not in ["body", "query", "path"])

        # Si no hay campo, usar "general"
        if not field_name:
            field_name = "general"

        # Mensaje del error
        msg = error.get("msg", "Invalid value")

        # Si ya existe un error para este campo, agregar al mensaje
        if field_name in field_errors:
            field_errors[field_name] += f"; {msg}"
        else:
            field_errors[field_name] = msg

    return field_errors


# ===========================================
# EXCEPTION HANDLERS
# ===========================================


async def c2pro_exception_handler(request: Request, exc: C2ProException) -> JSONResponse:
    """
    Handler para excepciones personalizadas de C2Pro.

    Todas las excepciones que heredan de C2ProException se manejan aquí.
    Estas excepciones ya tienen el formato correcto en to_dict().

    Args:
        request: Request de FastAPI
        exc: Excepción de C2Pro

    Returns:
        JSONResponse con formato de error unificado
    """
    # Loggear según severidad
    if exc.status_code >= 500:
        logger.error(
            "c2pro_exception",
            path=str(request.url.path),
            method=request.method,
            error_code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
        )
    else:
        logger.warning(
            "c2pro_exception",
            path=str(request.url.path),
            method=request.method,
            error_code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
        )

    # Convertir a diccionario con path
    error_dict = exc.to_dict(path=str(request.url.path))

    return JSONResponse(
        status_code=exc.status_code,
        content=error_dict,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handler para HTTPException de FastAPI.

    Transforma las HTTPException estándar de FastAPI al formato unificado.

    Args:
        request: Request de FastAPI
        exc: HTTPException

    Returns:
        JSONResponse con formato de error unificado
    """
    # Determinar error_code basado en status_code
    error_code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }

    error_code = error_code_map.get(exc.status_code, "HTTP_ERROR")

    # Loggear
    logger.warning(
        "http_exception",
        path=str(request.url.path),
        method=request.method,
        status_code=exc.status_code,
        detail=exc.detail,
    )

    # Crear respuesta de error
    error_response = _create_error_response(
        status_code=exc.status_code,
        error_code=error_code,
        message=str(exc.detail) if exc.detail else "HTTP error",
        path=str(request.url.path),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response,
        headers=exc.headers,
    )


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handler para errores de validación de Pydantic (RequestValidationError).

    Este handler es CRÍTICO para la experiencia del frontend. Transforma
    la estructura compleja de errores de Pydantic en un diccionario simple
    {campo: mensaje} que el frontend puede usar directamente.

    Ejemplo de transformación:
        Antes (Pydantic):
        {
            "detail": [
                {"loc": ["body", "email"], "msg": "field required"},
                {"loc": ["body", "password"], "msg": "string too short"}
            ]
        }

        Después (Frontend-friendly):
        {
            "status_code": 422,
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {
                "field_errors": {
                    "email": "field required",
                    "password": "string too short"
                }
            },
            "timestamp": "2026-01-13T12:34:56.789Z",
            "path": "/api/v1/auth/register"
        }

    Args:
        request: Request de FastAPI
        exc: RequestValidationError de Pydantic

    Returns:
        JSONResponse con formato de error unificado
    """
    # Transformar errores de Pydantic a formato amigable
    pydantic_errors = exc.errors()
    field_errors = _transform_pydantic_errors(pydantic_errors)

    # Loggear
    logger.warning(
        "validation_error",
        path=str(request.url.path),
        method=request.method,
        field_errors=field_errors,
        error_count=len(pydantic_errors),
    )

    # Crear respuesta de error
    error_response = _create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        path=str(request.url.path),
        details={
            "field_errors": field_errors,
            # También incluir los errores originales para debugging (solo en desarrollo)
            **({"raw_errors": jsonable_encoder(pydantic_errors)} if settings.is_development else {}),
        },
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response,
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler para excepciones no manejadas (Internal Server Error).

    Este handler captura todas las excepciones no esperadas y:
    1. Loggea el stack trace completo en el servidor (para debugging)
    2. Devuelve al usuario solo un mensaje genérico con un reference_id
    3. NUNCA expone el stack trace al usuario (seguridad)

    En desarrollo, incluye más detalles para facilitar debugging.

    Args:
        request: Request de FastAPI
        exc: Excepción genérica

    Returns:
        JSONResponse con formato de error unificado (500)
    """
    # Generar un ID de referencia único para rastrear este error
    error_reference_id = str(uuid.uuid4())

    # Capturar stack trace
    stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    # Loggear con stack trace completo
    logger.error(
        "unhandled_exception",
        path=str(request.url.path),
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc),
        reference_id=error_reference_id,
        stack_trace=stack_trace,  # Stack trace completo en logs
        exc_info=True,  # Para Sentry/CloudWatch
    )

    # Mensaje para el usuario (genérico en producción)
    if settings.is_production:
        user_message = "An internal error occurred. Please contact support with the reference ID."
        details = {
            "reference_id": error_reference_id,
            "support_email": "support@c2pro.app",
        }
    else:
        # En desarrollo, incluir más detalles para debugging
        user_message = f"Internal error: {type(exc).__name__}: {str(exc)}"
        details = {
            "reference_id": error_reference_id,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            # NO incluir stack trace completo, solo las primeras líneas
            "stack_trace_preview": stack_trace.split("\n")[:5],
        }

    # Crear respuesta de error
    error_response = _create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_SERVER_ERROR",
        message=user_message,
        path=str(request.url.path),
        details=details,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response,
    )


# ===========================================
# REGISTRATION HELPER
# ===========================================


def register_exception_handlers(app) -> None:
    """
    Registra todos los exception handlers en la aplicación FastAPI.

    Este helper function debe ser llamado desde main.py para registrar
    todos los handlers de forma centralizada.

    Args:
        app: Instancia de FastAPI

    Example:
        from src.core.handlers import register_exception_handlers

        app = FastAPI(...)
        register_exception_handlers(app)
    """
    # Handler para excepciones personalizadas de C2Pro
    app.add_exception_handler(C2ProException, c2pro_exception_handler)

    # Handler para HTTPException de FastAPI
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Handler para errores de validación de Pydantic
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)

    # Handler para excepciones genéricas (catch-all)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("exception_handlers_registered", handlers=4)
