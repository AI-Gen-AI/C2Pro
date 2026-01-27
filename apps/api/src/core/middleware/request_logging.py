"""
C2Pro - Request Logging Middleware

Middleware para logging estructurado de todas las requests HTTP.
"""

import time
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para logging estructurado de todas las requests.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generar request ID
        request_id = request.headers.get("X-Request-ID", str(time.time_ns()))
        request.state.request_id = request_id

        # Bind to logging context
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Log request start
        start_time = time.perf_counter()

        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            query=str(request.query_params) if request.query_params else None,
            client_ip=self._get_client_ip(request),
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                error=str(e),
            )
            raise

        # Log request completion
        duration_ms = (time.perf_counter() - start_time) * 1000

        log_method = logger.info if response.status_code < 400 else logger.warning
        log_method(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Obtiene IP del cliente, considerando proxies."""
        # Check common proxy headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct connection
        if request.client:
            return request.client.host

        return "unknown"
