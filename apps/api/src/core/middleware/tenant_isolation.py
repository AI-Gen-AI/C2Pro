"""
C2Pro - Tenant Isolation Middleware

CRITICAL FOR SECURITY:
- Ensures complete data isolation between tenants
- Validates JWT tokens and tenant_id presence
- All protected routes MUST pass through this middleware
"""

import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeAlias
from uuid import UUID

import jwt
import structlog
from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings
from src.core.auth.bootstrap_lookup import (
    BootstrapFallbackBlockedError,
    BootstrapUserRecord,
    lookup_tenant_by_id,
    lookup_user_by_clerk_user_id,
)
from src.core.auth.platform_operator import PlatformIdentity, require_platform_operator
from src.core.auth.token_revocation import is_token_revoked_async
from src.core.database import get_raw_session
from src.core.middleware.clerk_auth import verify_clerk_token
from src.core.observability.sentry_alerts import record_auth_failure

logger = structlog.get_logger()


# C2.6 uses only these reviewed method + normalized-template identities. This
# is deliberately not a router-prefix or endpoint-provenance decision.
PLATFORM_ROUTE_REGISTRY = frozenset(
    {
        ("GET", "/api/v1/admin/dlq"),
        ("POST", "/api/v1/admin/dlq/{dlq_id}/retry"),
    }
)


def normalize_platform_path(method: str, path: str) -> str:
    """Normalize a concrete request path only to a registered route template."""
    normalized_path = path.rstrip("/") or "/"
    if method == "POST":
        parts = normalized_path.split("/")
        if (
            len(parts) == 7
            and parts[:4] == ["", "api", "v1", "admin"]
            and parts[4] == "dlq"
            and parts[5]
            and parts[6] == "retry"
        ):
            return "/api/v1/admin/dlq/{dlq_id}/retry"
    return normalized_path


def is_platform_route(method: str, path: str) -> bool:
    """Classify only an explicit method + normalized route-template identity."""
    return (method, normalize_platform_path(method, path)) in PLATFORM_ROUTE_REGISTRY


def active_mounted_routes(app: Any) -> list[Any]:
    """Flatten FastAPI's mounted route table without using it at request time."""
    routes: list[Any] = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append(route)
            continue
        effective_route_contexts = getattr(route, "effective_route_contexts", None)
        if callable(effective_route_contexts):
            routes.extend(effective_route_contexts())
    return routes


def assert_platform_route_registry(app: Any) -> None:
    """CI-only active-mount invariant for the reviewed platform-route registry."""
    errors: list[str] = []
    active_routes = active_mounted_routes(app)

    for method, normalized_path in PLATFORM_ROUTE_REGISTRY:
        matches = [
            route
            for route in active_routes
            if route.path == normalized_path and method in route.methods
        ]
        if len(matches) != 1:
            errors.append(
                f"{method} {normalized_path} must resolve to exactly one mounted route; "
                f"found {len(matches)}"
            )
            continue
        if matches[0].endpoint.__module__ != "src.admin.adapters.http.router":
            errors.append(
                f"{method} {normalized_path} must resolve to the cross-tenant admin router"
            )

    for route in active_routes:
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        if require_platform_operator not in dependency_calls:
            continue
        for method in route.methods:
            if (method, route.path) not in PLATFORM_ROUTE_REGISTRY:
                errors.append(
                    f"platform-operator route {method} {route.path} is absent from the registry"
                )

    legacy_routes = [
        route
        for route in active_routes
        if route.endpoint.__module__ == "src.core.dlq.router"
    ]
    if legacy_routes:
        errors.append("legacy tenant DLQ router must remain unmounted")

    if errors:
        raise AssertionError("; ".join(errors))

if TYPE_CHECKING:
    RequestType: TypeAlias = Request[Any]
else:
    RequestType = Request


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
        "/api/v1/openapi.json",
        "/",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/health",
        "/api/v1/health",
        "/api/v1/projects/health",
    ]

    @staticmethod
    def _unauthorized_response(detail: str, reason_code: str) -> Response:
        return Response(
            content=json.dumps({"detail": detail, "reason_code": reason_code}),
            status_code=401,
            media_type="application/json",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async def dispatch(
        self,
        request: RequestType,
        call_next: Callable[[RequestType], Awaitable[Response]],
    ) -> Response:
        # Allow CORS preflight requests (OPTIONS)
        if request.method == "OPTIONS":
            return await call_next(request)

        if is_platform_route(request.method, request.url.path):
            return await self._dispatch_platform_route(request, call_next)

        # Permitir rutas públicas
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Extraer y validar token
        (
            tenant_id,
            user_id,
            require_tenant_validation,
            error_message,
            reason_code,
        ) = await self._extract_auth_context(request)

        if error_message:
            # Use specific error message if provided, otherwise generic one
            message = error_message or "Not authenticated"
            error_code = reason_code or "missing_or_invalid_token"
            logger.warning(
                "authentication_failed",
                path=request.url.path,
                reason=error_code,
                error_code=error_code,
                error=message,
            )
            record_auth_failure(
                reason_code=error_code,
                tenant_id=tenant_id,
                path=request.url.path,
                ip=request.client.host if request.client else None,
            )
            return self._unauthorized_response(message, error_code)

        if tenant_id is None and user_id is None:
            logger.warning(
                "authentication_failed",
                path=request.url.path,
                reason="missing_or_invalid_token",
                error="Not authenticated",
            )
            record_auth_failure(
                reason_code="missing_or_invalid_token",
                tenant_id=None,
                path=request.url.path,
                ip=request.client.host if request.client else None,
            )
            return self._unauthorized_response("Not authenticated", "missing_or_invalid_token")

        if tenant_id is not None and require_tenant_validation:
            tenant_active = await self._validate_tenant_exists(tenant_id)
            if not tenant_active:
                logger.warning(
                    "authentication_failed",
                    path=request.url.path,
                    reason="tenant_inactive_or_missing",
                    tenant_id=str(tenant_id),
                )
                record_auth_failure(
                    reason_code="tenant_inactive_or_missing",
                    tenant_id=tenant_id,
                    path=request.url.path,
                    ip=request.client.host if request.client else None,
                )
                return self._unauthorized_response(
                    "Invalid authentication context", "tenant_inactive_or_missing"
                )

        # Inyectar tenant_id en request state
        if tenant_id is not None:
            request.state.tenant_id = tenant_id
        request.state.user_id = user_id

        # Bind to structured logging context
        structlog.contextvars.bind_contextvars(
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(request.state.user_id) if request.state.user_id else None,
        )

        return await call_next(request)

    async def _dispatch_platform_route(
        self,
        request: RequestType,
        call_next: Callable[[RequestType], Awaitable[Response]],
    ) -> Response:
        """Authenticate the tenant-less C2.6 platform route mode exactly once."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer ") or not auth_header[7:].strip():
            return self._platform_unauthorized(request, "missing_or_invalid_token")

        token = auth_header[7:].strip()
        try:
            algorithm = jwt.get_unverified_header(token).get("alg")
        except jwt.PyJWTError:
            return self._platform_unauthorized(request, "invalid_platform_token")

        if algorithm == "HS256":
            logger.warning("platform_route_local_jwt_rejected", path=request.url.path)
            return self._platform_unauthorized(request, "local_jwt_not_accepted")

        try:
            claims = await verify_clerk_token(token)
        except Exception:
            logger.warning("platform_route_identity_unverified", path=request.url.path)
            return self._platform_unauthorized(request, "invalid_platform_identity")

        clerk_user_id = claims.get("sub")
        if not isinstance(clerk_user_id, str) or not clerk_user_id:
            return self._platform_unauthorized(request, "invalid_platform_identity")

        clerk_org_id = claims.get("org_id")
        if clerk_org_id is not None and not isinstance(clerk_org_id, str):
            return self._platform_unauthorized(request, "invalid_platform_identity")
        email = claims.get("email")
        if email is not None and not isinstance(email, str):
            return self._platform_unauthorized(request, "invalid_platform_identity")

        # A platform request must never inherit or establish tenant log context.
        structlog.contextvars.unbind_contextvars("tenant_id", "user_id")
        request.state.platform_identity = PlatformIdentity(
            user_id=clerk_user_id,
            org_id=clerk_org_id,
            email=email,
            email_verified=claims.get("email_verified") is True,
        )
        return await call_next(request)

    def _platform_unauthorized(self, request: RequestType, reason_code: str) -> Response:
        logger.warning("authentication_failed", path=request.url.path, reason=reason_code)
        record_auth_failure(
            reason_code=reason_code,
            tenant_id=None,
            path=request.url.path,
            ip=request.client.host if request.client else None,
        )
        return self._unauthorized_response("Not authenticated", reason_code)

    def _is_public_path(self, path: str) -> bool:
        """Verifica si la ruta es pública."""
        if path == "/":
            return True
        return any(path.startswith(p) for p in self.PUBLIC_PATHS if p != "/")

    def _extract_tenant_id(self, request: RequestType) -> tuple[UUID | None, str | None]:
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
        except jwt.PyJWTError as e:
            logger.debug("jwt_invalid", error=str(e))
            return None, "Invalid authentication credentials"
        except ValueError as e:
            logger.debug("invalid_uuid_format", error=str(e))
            return None, "Invalid authentication credentials"

    async def _extract_auth_context(
        self,
        request: RequestType,
    ) -> tuple[UUID | None, UUID | str | None, bool, str | None, str | None]:
        """
        Extract tenant/user context from either a local JWT or a Clerk JWT.

        Returns:
            tenant_id, user_id, require_tenant_validation, error_message
        """
        auth_header = request.headers.get("Authorization", "")
        token: str | None = None

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        elif request.url.path.endswith("/process/stream"):
            token = request.query_params.get("access_token")

        if not token:
            if request.url.path.endswith("/process/stream"):
                return (
                    None,
                    None,
                    False,
                    "Authenticated SSE session required",
                    "authenticated_sse_session_required",
                )
            return None, None, False, None, None

        if await is_token_revoked_async(token):
            logger.debug("token_revoked")
            return None, None, False, "Token has been revoked", "token_revoked"

        # First, try the local JWT flow used by Swagger/testing.
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_signature": True, "verify_exp": True},
            )

            token_type = payload.get("type")
            if token_type != "access":
                logger.debug("invalid_token_type", type=token_type)
                return None, None, False, "Invalid token type", "invalid_token_type"

            tenant_id_str = payload.get("tenant_id")
            if not tenant_id_str:
                logger.debug("missing_tenant_id")
                return None, None, False, "Missing tenant_id in token", "missing_tenant_id"

            user_id_str = payload.get("sub")
            tenant_id = UUID(tenant_id_str)
            user_id = UUID(user_id_str) if user_id_str else None
            return tenant_id, user_id, True, None, None
        except jwt.ExpiredSignatureError:
            logger.debug("jwt_expired")
            return None, None, False, "Token has expired", "token_expired"
        except jwt.PyJWTError as e:
            logger.debug("local_jwt_invalid", error=str(e))
        except ValueError as e:
            logger.debug("local_jwt_invalid_uuid_format", error=str(e))
            return (
                None,
                None,
                False,
                "Invalid authentication credentials",
                "invalid_authentication_credentials",
            )

        # Fall back to Clerk JWT verification for the Next.js frontend.
        try:
            claims = await verify_clerk_token(token)
            clerk_user_id = claims.get("sub")
            if not clerk_user_id:
                return (
                    None,
                    None,
                    False,
                    "Invalid Clerk token: missing user ID",
                    "invalid_clerk_token_missing_user_id",
                )

            # Resolve the internal user record (internal UUID + tenant) for this Clerk user.
            # CRITICAL: request.state.user_id must be the internal UUID, never the Clerk
            # "user_..." string. Downstream persistence writes it into UUID columns
            # (e.g. documents.created_by); a raw Clerk id fails the INSERT with a uuid
            # DataError -> 500. Fall back to the Clerk id only for a not-yet-provisioned
            # user, who has no tenant and is auto-provisioned by get_current_user before
            # any tenant-scoped write.
            record = await self._get_clerk_user_record(clerk_user_id)
            if record is not None:
                return record.tenant_id, record.user_id, True, None, None

            return None, clerk_user_id, False, None, None
        except BootstrapFallbackBlockedError:
            return (
                None,
                None,
                False,
                "Auth bootstrap fallback blocked by policy",
                "auth_bootstrap_fallback_blocked",
            )
        except ValueError as e:
            logger.debug("clerk_invalid_uuid_format", error=str(e))
            return (
                None,
                None,
                False,
                "Invalid authentication credentials",
                "invalid_authentication_credentials",
            )
        except Exception as e:
            logger.debug("clerk_jwt_invalid", error=str(e))
            return (
                None,
                None,
                False,
                "Invalid authentication credentials",
                "invalid_authentication_credentials",
            )

    def _extract_user_id(self, request: RequestType) -> UUID | None:
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
        except (jwt.PyJWTError, ValueError):
            return None

    async def _get_tenant_for_clerk_user(self, clerk_user_id: str) -> UUID | None:
        """
        Look up the tenant_id for a Clerk user from the database.
        Returns None if user not found (will be auto-provisioned by get_current_user).
        """
        try:
            async with get_raw_session() as session:
                record = await lookup_user_by_clerk_user_id(session, clerk_user_id)
                if record:
                    logger.debug(
                        "clerk_user_tenant_found",
                        clerk_user_id=clerk_user_id,
                        tenant_id=str(record.tenant_id),
                    )
                    return record.tenant_id
                return None
        except Exception as e:
            if isinstance(e, BootstrapFallbackBlockedError):
                raise
            logger.warning(
                "clerk_user_tenant_lookup_failed",
                clerk_user_id=clerk_user_id,
                error=str(e),
            )
            return None

    async def _get_clerk_user_record(self, clerk_user_id: str) -> BootstrapUserRecord | None:
        """
        Resolve the internal user record (internal UUID + tenant_id) for a Clerk user.

        Returns None if the user is not yet provisioned (auto-provisioned later by
        get_current_user). Used so request.state.user_id carries the internal UUID
        rather than the Clerk "user_..." string.
        """
        try:
            async with get_raw_session() as session:
                return await lookup_user_by_clerk_user_id(session, clerk_user_id)
        except Exception as e:
            if isinstance(e, BootstrapFallbackBlockedError):
                raise
            logger.warning(
                "clerk_user_record_lookup_failed",
                clerk_user_id=clerk_user_id,
                error=str(e),
            )
            return None

    async def _validate_tenant_exists(self, tenant_id: UUID) -> bool:
        """
        Valida que el tenant existe y está activo en la base de datos.

        Args:
            tenant_id: UUID del tenant a validar

        Returns:
            True si el tenant existe y está activo, False en caso contrario
        """
        try:
            async with get_raw_session() as session:
                record = await lookup_tenant_by_id(session, tenant_id)
                if record is None:
                    return False
                return bool(record.is_active)
        except Exception as e:
            if (
                settings.environment == "test"
                and isinstance(e, RuntimeError)
                and "Database not initialized" in str(e)
            ):
                logger.warning(
                    "tenant_validation_bypassed_for_tests",
                    tenant_id=str(tenant_id),
                )
                return True
            logger.error("tenant_validation_error", error=str(e), tenant_id=str(tenant_id))
            return False
