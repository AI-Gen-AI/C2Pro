"""
Clerk JWT Verification Middleware for FastAPI

Verifies Clerk JWT tokens and extracts user/organization context.
Maps Clerk org_id to internal tenant_id for Supabase RLS.

CRITICAL FOR SECURITY:
- Verifies JWT signature using Clerk's JWKS
- Extracts and validates organization context
- Maps clerk org_id -> Supabase tenant_id
- Circuit breaker protection for JWKS fetch
"""

import contextlib
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Any, cast
from uuid import UUID

import httpx
import jwt
import structlog
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from fastapi import Depends, HTTPException, Request, Response, status
from jwt.algorithms import RSAAlgorithm
from jwt.types import Options
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings
from src.core.observability.sentry_alerts import record_auth_failure
from src.core.resilience import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerRegistry
from src.core.resilience.config import get_circuit_breaker_settings

logger = structlog.get_logger()

# Initialize circuit breaker for Clerk JWKS fetch
_clerk_circuit_breaker = None


def _get_clerk_circuit_breaker() -> CircuitBreaker | None:
    """Get or initialize the Clerk JWKS circuit breaker."""
    global _clerk_circuit_breaker
    if _clerk_circuit_breaker is None:
        cb_settings = get_circuit_breaker_settings()
        if cb_settings.enable_circuit_breakers:
            _clerk_circuit_breaker = CircuitBreakerRegistry.register(
                CircuitBreakerConfig(
                    service_name="clerk_jwks",
                    failure_threshold=cb_settings.clerk_failure_threshold,
                    recovery_timeout=cb_settings.clerk_recovery_timeout,
                )
            )
    return _clerk_circuit_breaker


class ClerkTokenVerificationError(HTTPException):
    """Custom exception for Clerk token verification failures."""

    def __init__(self, detail: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(status_code=status_code, detail=detail)


@lru_cache(maxsize=1)
def get_clerk_jwks() -> dict[str, Any] | None:
    """
    Fetch and cache Clerk JWKS (JSON Web Key Set).

    The JWKS is cached for performance to avoid repeated API calls.
    Cache invalidates on application restart.

    Protected by circuit breaker to prevent cascading failures
    when Clerk API is unavailable.
    """
    cb = _get_clerk_circuit_breaker()

    # Check circuit breaker before making request
    if cb and not cb.can_execute_sync():
        logger.warning("clerk_jwks_circuit_open", action="returning_cached_or_none")
        # Circuit is open - return None and rely on cached keys in verify_clerk_token
        return None

    try:
        jwks_url = settings.clerk_jwks_url
        if not jwks_url:
            # Construct from Clerk issuer if not explicitly provided
            issuer = settings.clerk_issuer
            if issuer:
                jwks_url = f"{issuer}/.well-known/jwks.json"
            else:
                logger.error("clerk_jwks_url_not_configured")
                return None

        response = httpx.get(jwks_url, timeout=10)
        response.raise_for_status()

        if cb:
            cb.record_success_sync()

        logger.debug("clerk_jwks_fetched", url=jwks_url)
        return cast(dict[str, Any], response.json())

    except Exception as e:
        if cb:
            cb.record_failure_sync(e)
        logger.error("clerk_jwks_fetch_failed", error=str(e))
        return None


def clear_jwks_cache() -> None:
    """Clear the JWKS cache (useful for key rotation)."""
    get_clerk_jwks.cache_clear()


async def verify_clerk_token(token: str) -> dict[str, Any]:
    """
    Verify Clerk JWT token and extract claims.

    Args:
        token: JWT token from Authorization header

    Returns:
        Decoded token claims

    Raises:
        ClerkTokenVerificationError: If token is invalid
    """
    if not token:
        raise ClerkTokenVerificationError("No token provided")

    try:
        # Decode header to get 'kid' (key ID)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise ClerkTokenVerificationError("Token missing kid header")

        # Get JWKS
        jwks = get_clerk_jwks()
        if not jwks:
            raise ClerkTokenVerificationError(
                "Failed to fetch Clerk JWKS",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Find the key matching kid
        key = None
        for k in jwks.get("keys", []):
            if k.get("kid") == kid:
                key = k
                break

        if not key:
            # Key not found - might be rotated, clear cache and retry once
            clear_jwks_cache()
            jwks = get_clerk_jwks()
            if jwks:
                for k in jwks.get("keys", []):
                    if k.get("kid") == kid:
                        key = k
                        break

            if not key:
                raise ClerkTokenVerificationError(f"Key {kid} not found in JWKS")

        # Convert JWKS key to RSA public key. JWKS entries are always public
        # keys (that is the purpose of a JWKS); from_jwk()'s return type is a
        # union with the private-key case because the same helper handles both.
        rsa_key = cast(RSAPublicKey, RSAAlgorithm.from_jwk(key))

        # Verify and decode token
        decode_options: Options = {
            "verify_exp": True,
            "verify_aud": False,  # Clerk doesn't always set audience
        }

        # Add issuer verification if configured
        if settings.clerk_issuer:
            decode_options["verify_iss"] = True

        decoded = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer if settings.clerk_issuer else None,
            options=decode_options,
        )

        return decoded

    except jwt.ExpiredSignatureError:
        raise ClerkTokenVerificationError("Token has expired")
    except jwt.InvalidIssuerError:
        raise ClerkTokenVerificationError("Invalid token issuer")
    except jwt.InvalidTokenError as e:
        logger.warning("clerk_token_invalid", error=str(e))
        raise ClerkTokenVerificationError(f"Invalid token: {str(e)}")
    except ClerkTokenVerificationError:
        raise
    except Exception as e:
        logger.error("clerk_token_verification_error", error=str(e))
        raise ClerkTokenVerificationError(
            "Token verification failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ClerkUser:
    """Represents a verified Clerk user with extracted claims."""

    def __init__(self, claims: dict[str, Any]):
        self.claims = claims
        self.user_id = claims.get("sub")
        self.email = claims.get("email")
        self.first_name = claims.get("first_name")
        self.last_name = claims.get("last_name")
        self.org_id = claims.get("org_id") or claims.get("organization_id")
        self.org_role = claims.get("org_role") or claims.get("organization_role")
        self.org_slug = claims.get("org_slug") or claims.get("organization_slug")
        self.email_verified = claims.get("email_verified", False)

        # Organization metadata (if present in token)
        org_metadata = claims.get("org_public_metadata", {})
        self.tenant_id = org_metadata.get("tenant_id")
        self.is_demo = org_metadata.get("is_demo", False)
        self.service_tier = org_metadata.get("tier", "free")

    @property
    def is_authenticated(self) -> bool:
        """Check if user is properly authenticated."""
        return bool(self.user_id)

    @property
    def is_org_admin(self) -> bool:
        """Check if user is admin of their organization."""
        return self.org_role in ("admin", "org:admin")

    def has_org(self) -> bool:
        """Check if user has selected an organization."""
        return bool(self.org_id)

    def has_tenant(self) -> bool:
        """Check if organization has a mapped tenant_id."""
        return bool(self.tenant_id)


async def extract_clerk_claims(request: Request[Any]) -> dict[str, Any]:
    """
    Extract Clerk JWT from request and verify it.

    This is a dependency that can be used in route handlers.
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        raise ClerkTokenVerificationError("Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]
    return await verify_clerk_token(token)


async def get_clerk_user(
    claims: dict[str, Any] = Depends(extract_clerk_claims),
) -> ClerkUser:
    """
    Dependency to get authenticated Clerk user.

    Usage:
        @app.get("/api/projects")
        async def list_projects(user: ClerkUser = Depends(get_clerk_user)):
            return {"user_id": user.user_id}
    """
    user = ClerkUser(claims)

    if not user.is_authenticated:
        raise ClerkTokenVerificationError("User not authenticated")

    return user


async def require_organization(
    user: ClerkUser = Depends(get_clerk_user),
) -> ClerkUser:
    """Dependency that requires user to have selected an organization."""
    if not user.has_org():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must select an organization to access this resource",
        )
    return user


async def require_tenant(
    user: ClerkUser = Depends(require_organization),
) -> ClerkUser:
    """Dependency that requires organization to have a mapped tenant_id."""
    if not user.has_tenant():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization is not properly configured (missing tenant_id)",
        )
    return user


async def require_admin(
    user: ClerkUser = Depends(get_clerk_user),
) -> ClerkUser:
    """Dependency that requires user to be organization admin."""
    if not user.is_org_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires admin role",
        )
    return user


async def get_current_tenant_id(
    user: ClerkUser = Depends(require_tenant),
) -> UUID:
    """
    Get the current tenant_id for the authenticated user.

    Maps from Clerk organization's public_metadata.tenant_id to UUID.

    Usage:
        @app.get("/api/projects")
        async def list_projects(tenant_id: UUID = Depends(get_current_tenant_id)):
            return await projects_service.list_by_tenant(tenant_id)
    """
    try:
        return UUID(user.tenant_id)
    except (ValueError, TypeError) as e:
        logger.error(
            "invalid_tenant_id_format",
            tenant_id=user.tenant_id,
            org_id=user.org_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant_id format in organization metadata",
        )


class ClerkAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that verifies Clerk JWT and injects tenant context.

    Similar to TenantIsolationMiddleware but uses Clerk JWTs.
    """

    PUBLIC_PATHS = [
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/openapi.json",
        "/",
        "/api/webhooks/clerk",
        "/api/v1/webhooks/clerk",
    ]

    async def dispatch(
        self, request: Request[Any], call_next: Callable[[Request[Any]], Awaitable[Response]]
    ) -> Response:
        # Allow public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Extract and verify Clerk token
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            logger.warning(
                "clerk_auth_missing",
                path=request.url.path,
            )
            record_auth_failure(
                reason_code="clerk_auth_missing",
                tenant_id=None,
                path=request.url.path,
                ip=request.client.host if request.client else None,
            )
            return Response(
                content='{"detail": "Missing or invalid Authorization header"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header.split(" ")[1]

        try:
            claims = await verify_clerk_token(token)
            user = ClerkUser(claims)

            # Inject user context into request state
            request.state.clerk_user = user
            request.state.user_id = user.user_id

            # If user has organization with tenant_id, inject it
            if user.has_tenant():
                with contextlib.suppress(ValueError):
                    request.state.tenant_id = UUID(user.tenant_id)

            # Bind to structured logging context
            structlog.contextvars.bind_contextvars(
                user_id=user.user_id,
                org_id=user.org_id,
                tenant_id=user.tenant_id,
            )

            return await call_next(request)

        except ClerkTokenVerificationError as e:
            logger.warning(
                "clerk_auth_failed",
                path=request.url.path,
                error=e.detail,
            )

            # Generate a snake_case reason_code from the exception detail
            reason_code = e.detail.lower().replace(" ", "_")

            record_auth_failure(
                reason_code=f"clerk_{reason_code}",
                tenant_id=None,  # Tenant ID is not available at this stage
                path=request.url.path,
                ip=request.client.host if request.client else None,
            )

            return Response(
                content=f'{{"detail": "{e.detail}"}}',
                status_code=e.status_code,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        if path == "/":
            return True
        return any(path.startswith(p) for p in self.PUBLIC_PATHS if p != "/")


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ClerkAuthMiddleware",
    "ClerkTokenVerificationError",
    "ClerkUser",
    "clear_jwks_cache",
    "extract_clerk_claims",
    "get_clerk_jwks",
    "get_clerk_user",
    "get_current_tenant_id",
    "require_admin",
    "require_organization",
    "require_tenant",
    "verify_clerk_token",
]
