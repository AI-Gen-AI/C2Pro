"""
C2Pro - API Contract Middleware

Middleware para garantizar que todas las respuestas de la API cumplan
con los contratos establecidos (headers, formatos, etc.)
"""

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeAlias

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings

if TYPE_CHECKING:
    RequestType: TypeAlias = Request[Any]
else:
    RequestType = Request


class APIContractMiddleware(BaseHTTPMiddleware):
    """
    Middleware para cumplimiento de contrato de API.

    Agrega headers estandarizados a todas las respuestas:
    - X-API-Version: Versión de la API
    - X-Response-Time: Tiempo de respuesta en milisegundos
    """

    async def dispatch(
        self, request: RequestType, call_next: Callable[[RequestType], Awaitable[Response]]
    ) -> Response:
        # Record start time
        start_time = time.perf_counter()

        # Process request
        response = await call_next(request)

        # Calculate response time
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Add API contract headers
        response.headers["X-API-Version"] = f"v{settings.app_version}"
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        return response
