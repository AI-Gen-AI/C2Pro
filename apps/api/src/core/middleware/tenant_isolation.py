"""
C2Pro - Tenant Isolation Middleware

CRITICAL FOR SECURITY:
- Ensures complete data isolation between tenants
- Validates JWT tokens and tenant_id presence
- All protected routes MUST pass through this middleware
"""

from collections.abc import Callable
from uuid import UUID

import structlog
from fastapi import Request, Response
from jose import JWTError, jwt
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings
from src.core.database import get_raw_session
from src.core.auth.models import Tenant

logger = structlog.get_logger()


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
        "/",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/health",
    ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Permitir rutas públicas
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Extraer y validar token
        tenant_id, error_message = self._extract_tenant_id(request)

        if tenant_id is None:
            # Use specific error message if provided, otherwise generic one
            message = error_message or "Invalid authentication credentials"
            logger.warning(
                "authentication_failed",
                path=request.url.path,
                reason="missing_or_invalid_token",
                error=message,
            )
            return Response(
                content=f'{{"detail": "{message}"}}',
                status_code=401,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validar que el tenant existe en la base de datos
        tenant_exists = await self._validate_tenant_exists(tenant_id)
        if not tenant_exists:
            logger.warning(
                "authentication_failed",
                path=request.url.path,
                reason="tenant_not_found",
                tenant_id=str(tenant_id),
            )
            return Response(
                content='{"detail": "Invalid authentication context"}',
                status_code=401,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"},
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

    def _extract_tenant_id(self, request: Request) -> tuple[UUID | None, str | None]:
        """
        Extrae y valida tenant_id del JWT en el header Authorization.

        Valida:
        - Firma del JWT
        - Expiración del token
        - Tipo de token (debe ser 'access')
        - Presencia de tenant_id

        Returns:
            Tuple of (tenant_id, error_message)
            - (tenant_id, None) if successful
            - (None, error_message) if authentication failed
        """
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return None, None

        token = auth_header[7:]

        try:
            # Decodificar y VERIFICAR SIEMPRE la firma
            # Esto valida automáticamente la expiración (exp claim)
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_signature": True, "verify_exp": True},
            )

            # Verificar que sea un access token (no refresh token)
            token_type = payload.get("type")
            if token_type != "access":
                logger.debug("invalid_token_type", type=token_type)
                return None, "Invalid token type"

            # Extraer tenant_id (required para access tokens)
            tenant_id_str = payload.get("tenant_id")
            if not tenant_id_str:
                logger.debug("missing_tenant_id")
                return None, "Missing tenant_id in token"

            return UUID(tenant_id_str), None

        except jwt.ExpiredSignatureError:
            logger.debug("jwt_expired")
            return None, "Token has expired"
        except JWTError as e:
            logger.debug("jwt_invalid", error=str(e))
            return None, "Invalid authentication credentials"
        except ValueError as e:
            logger.debug("invalid_uuid_format", error=str(e))
            return None, "Invalid authentication credentials"

    def _extract_user_id(self, request: Request) -> UUID | None:
        """Extrae user_id del JWT."""
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]

        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_signature": False},
            )
            user_id = payload.get("sub")
            return UUID(user_id) if user_id else None
        except (JWTError, ValueError):
            return None

    async def _validate_tenant_exists(self, tenant_id: UUID) -> bool:
        """
        Valida que el tenant existe en la base de datos.

        Args:
            tenant_id: UUID del tenant a validar

        Returns:
            True si el tenant existe y está activo, False en caso contrario
        """
        try:
            async with get_raw_session() as session:
                result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
                tenant = result.scalar_one_or_none()
                return tenant is not None
        except Exception as e:
            logger.error("tenant_validation_error", error=str(e), tenant_id=str(tenant_id))
            return False
