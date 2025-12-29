"""
C2Pro - Middleware

Middlewares críticos para seguridad, logging y rate limiting.
"""

import time
from typing import Callable
from uuid import UUID

import structlog
from fastapi import Request, Response
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings

logger = structlog.get_logger()


# ===========================================
# TENANT ISOLATION MIDDLEWARE
# ===========================================

class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware que extrae y valida el tenant_id del JWT.
    
    CRÍTICO PARA SEGURIDAD:
    - Sin este middleware, no hay aislamiento entre tenants
    - Todas las rutas protegidas DEBEN pasar por aquí
    """
    
    # Rutas que no requieren autenticación
    PUBLIC_PATHS = [
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
    ]
    
    async def dispatch(
        self, 
        request: Request, 
        call_next: Callable
    ) -> Response:
        # Permitir rutas públicas
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        # Extraer y validar token
        tenant_id = self._extract_tenant_id(request)
        
        if tenant_id is None:
            logger.warning(
                "authentication_failed",
                path=request.url.path,
                reason="missing_or_invalid_token"
            )
            return Response(
                content='{"detail": "Not authenticated"}',
                status_code=401,
                media_type="application/json"
            )
        
        # Inyectar tenant_id en request state
        request.state.tenant_id = tenant_id
        request.state.user_id = self._extract_user_id(request)
        
        # Bind to structured logging context
        structlog.contextvars.bind_contextvars(
            tenant_id=str(tenant_id),
            user_id=str(request.state.user_id) if request.state.user_id else None,
        )
        
        return await call_next(request)
    
    def _is_public_path(self, path: str) -> bool:
        """Verifica si la ruta es pública."""
        return any(path.startswith(p) for p in self.PUBLIC_PATHS)
    
    def _extract_tenant_id(self, request: Request) -> UUID | None:
        """Extrae tenant_id del JWT en el header Authorization."""
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header[7:]
        
        try:
            # En producción, Supabase valida el JWT
            # Aquí solo extraemos el payload
            # Para validación completa, usar supabase.auth.get_user()
            
            if settings.is_development:
                # En desarrollo, decodificar sin verificar
                payload = jwt.decode(
                    token,
                    settings.jwt_secret,
                    algorithms=[settings.jwt_algorithm],
                    options={"verify_signature": settings.is_production}
                )
            else:
                # En producción, verificar firma
                payload = jwt.decode(
                    token,
                    settings.jwt_secret,
                    algorithms=[settings.jwt_algorithm],
                )
            
            # Supabase incluye el user_id como 'sub'
            # El tenant_id puede ser un claim custom o igual al user_id
            tenant_id = payload.get("tenant_id") or payload.get("sub")
            
            if tenant_id:
                return UUID(tenant_id)
            
            return None
            
        except (JWTError, ValueError) as e:
            logger.debug("jwt_decode_failed", error=str(e))
            return None
    
    def _extract_user_id(self, request: Request) -> UUID | None:
        """Extrae user_id del JWT."""
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header[7:]
        
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False}
            )
            user_id = payload.get("sub")
            return UUID(user_id) if user_id else None
        except (JWTError, ValueError):
            return None


# ===========================================
# REQUEST LOGGING MIDDLEWARE
# ===========================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para logging estructurado de todas las requests.
    """
    
    async def dispatch(
        self, 
        request: Request, 
        call_next: Callable
    ) -> Response:
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


# ===========================================
# RATE LIMIT MIDDLEWARE
# ===========================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware simple de rate limiting.
    
    Para producción, considerar usar Redis para estado distribuido.
    """
    
    def __init__(self, app):
        super().__init__(app)
        # Simple in-memory store (no distribuido)
        # Para producción, usar Redis
        self._requests: dict[str, list[float]] = {}
    
    async def dispatch(
        self, 
        request: Request, 
        call_next: Callable
    ) -> Response:
        # Skip rate limiting for health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_identifier(request)
        
        # Check rate limit
        if self._is_rate_limited(client_id, request.url.path):
            logger.warning(
                "rate_limit_exceeded",
                client_id=client_id,
                path=request.url.path,
            )
            return Response(
                content='{"detail": "Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"}
            )
        
        # Record request
        self._record_request(client_id)
        
        return await call_next(request)
    
    def _get_client_identifier(self, request: Request) -> str:
        """Genera identificador único para el cliente."""
        # Preferir tenant_id si está autenticado
        if hasattr(request.state, "tenant_id") and request.state.tenant_id:
            return f"tenant:{request.state.tenant_id}"
        
        # Fallback a IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return f"ip:{forwarded_for.split(',')[0].strip()}"
        
        if request.client:
            return f"ip:{request.client.host}"
        
        return "unknown"
    
    def _is_rate_limited(self, client_id: str, path: str) -> bool:
        """Verifica si el cliente ha excedido el rate limit."""
        now = time.time()
        window_start = now - 60  # Ventana de 1 minuto
        
        # Determinar límite según endpoint
        if "/ai" in path or "/analysis" in path:
            limit = settings.rate_limit_ai_requests_per_minute
        else:
            limit = settings.rate_limit_requests_per_minute
        
        # Get requests in window
        if client_id not in self._requests:
            return False
        
        recent_requests = [
            ts for ts in self._requests[client_id]
            if ts > window_start
        ]
        
        return len(recent_requests) >= limit
    
    def _record_request(self, client_id: str) -> None:
        """Registra una request para el cliente."""
        now = time.time()
        
        if client_id not in self._requests:
            self._requests[client_id] = []
        
        self._requests[client_id].append(now)
        
        # Cleanup old entries (keep last 5 minutes)
        cutoff = now - 300
        self._requests[client_id] = [
            ts for ts in self._requests[client_id]
            if ts > cutoff
        ]
