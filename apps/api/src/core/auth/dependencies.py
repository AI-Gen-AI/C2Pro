"""
C2Pro - Authentication Dependencies

FastAPI dependencies for JWT authentication and authorization.
Supports BOTH:
- Clerk JWTs (RS256, from frontend) - auto-provisions users/tenants
- Local JWTs (HS256, from Swagger/testing) - requires pre-existing users

Minimal implementation for TS-E2E-SEC-TNT-001.
"""

from typing import Annotated, Any
from uuid import UUID, uuid4

import jwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.auth.bootstrap_lookup import (
    BootstrapFallbackBlockedError,
    create_bootstrap_tenant,
    create_bootstrap_user,
    is_bootstrap_fallback_allowed,
    lookup_personal_tenant_by_name,
    lookup_tenant_by_clerk_org_id,
    lookup_user_by_clerk_user_id,
)
from src.core.auth.models import Tenant, User
from src.core.database import get_session


logger = structlog.get_logger()
security = HTTPBearer()


def _build_personal_tenant_name(clerk_user_id: str) -> str:
    """
    Build a collision-resistant personal tenant name from the full Clerk user id.
    """
    return f"Personal-{clerk_user_id}"


async def _try_clerk_jwt(token: str) -> dict[str, Any] | None:
    """
    Try to verify token as a Clerk JWT.
    Returns decoded claims if valid, None if not a Clerk token.
    """
    try:
        from src.core.middleware.clerk_auth import verify_clerk_token
        claims = await verify_clerk_token(token)
        return dict(claims)
    except Exception:
        # Not a valid Clerk token, will try local JWT
        return None


async def _try_local_jwt(token: str) -> dict[str, Any] | None:
    """
    Try to verify token as a local JWT (HS256).
    Returns decoded claims if valid, None if invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return dict(payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        return None


async def _provision_clerk_user(
    db: AsyncSession,
    clerk_user_id: str,
    clerk_org_id: str | None,
    email: str | None,
    first_name: str | None,
    last_name: str | None,
) -> User:
    """
    Auto-provision a user from Clerk claims.
    Creates tenant and user if they don't exist.
    """
    target_tenant_id: UUID
    logger.debug(
        "auth_bootstrap_policy",
        operation="provision_clerk_user",
        environment=settings.environment,
        fallback_allowed=is_bootstrap_fallback_allowed(),
    )

    # Use Clerk org_id as tenant identifier, or create a personal tenant
    if clerk_org_id:
        tenant_record = await lookup_tenant_by_clerk_org_id(db, clerk_org_id)
        tenant = None

        if tenant_record is None:
            # Create tenant for this Clerk organization
            tenant_record = await create_bootstrap_tenant(
                db,
                tenant_name=f"Org-{clerk_org_id[:8]}",
                tenant_slug=f"org-{clerk_org_id[:8]}",
                clerk_org_id=clerk_org_id,
            )
            target_tenant_id = tenant_record.tenant_id
            logger.info(
                "tenant_auto_provisioned",
                tenant_id=str(target_tenant_id),
                clerk_org_id=clerk_org_id,
            )
        else:
            target_tenant_id = tenant_record.tenant_id
    else:
        # No org - create personal tenant based on clerk_user_id
        personal_tenant_name = _build_personal_tenant_name(clerk_user_id)
        tenant_record = await lookup_personal_tenant_by_name(db, personal_tenant_name)

        if tenant_record is None:
            tenant_record = await create_bootstrap_tenant(
                db,
                tenant_name=personal_tenant_name,
                tenant_slug=personal_tenant_name.lower(),
            )
            target_tenant_id = tenant_record.tenant_id
            logger.info("personal_tenant_created", tenant_id=str(target_tenant_id))
        else:
            target_tenant_id = tenant_record.tenant_id

    # Check if user exists
    user_record = await lookup_user_by_clerk_user_id(db, clerk_user_id)
    user = None

    if not settings.database_url.startswith("sqlite"):
        context_tenant_id = user_record.tenant_id if user_record is not None else target_tenant_id
        await db.execute(text(f"SET LOCAL app.current_tenant = '{str(context_tenant_id)}'"))

    if user_record is not None:
        result = await db.execute(select(User).where(User.id == user_record.user_id))
        user = result.scalar_one_or_none()

    if not user:
        # Create user
        created_user = await create_bootstrap_user(
            db,
            tenant_id=target_tenant_id,
            email=email or f"{clerk_user_id}@clerk.local",
            hashed_password=None,
            first_name=first_name or "Clerk",
            last_name=last_name or "User",
            role="user",
            clerk_user_id=clerk_user_id,
        )
        result = await db.execute(select(User).where(User.id == created_user.user_id))
        user = result.scalar_one()
        logger.info("user_auto_provisioned", user_id=str(user.id), clerk_user_id=clerk_user_id)
    elif user.tenant_id != target_tenant_id:
        # User switched orgs - update tenant
        user.tenant_id = target_tenant_id
        await db.flush()

    await db.commit()
    return user


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """
    Get current authenticated user from JWT token.

    Supports two token types:
    1. Clerk JWT (RS256) - auto-provisions user/tenant from Clerk claims
    2. Local JWT (HS256) - requires user/tenant to exist in database

    Raises 401 if validation fails.
    """
    token = credentials.credentials

    # First, try Clerk JWT (RS256)
    clerk_claims = await _try_clerk_jwt(token)
    if clerk_claims:
        # Extract Clerk-specific claims
        clerk_user_id = clerk_claims.get("sub")
        clerk_org_id = clerk_claims.get("org_id") or clerk_claims.get("organization_id")
        email = clerk_claims.get("email")
        first_name = clerk_claims.get("first_name")
        last_name = clerk_claims.get("last_name")

        if not clerk_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Clerk token: missing user ID",
            )

        # Auto-provision user from Clerk
        try:
            user = await _provision_clerk_user(
                db, clerk_user_id, clerk_org_id, email, first_name, last_name
            )
        except BootstrapFallbackBlockedError:
            logger.warning(
                "authentication_failed",
                reason="auth_bootstrap_fallback_blocked",
                error_code="auth_bootstrap_fallback_blocked",
                clerk_user_id=clerk_user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication context",
            )

        logger.debug(
            "clerk_user_authenticated",
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            clerk_user_id=clerk_user_id,
        )
        return user

    # Fall back to local JWT (HS256)
    payload = await _try_local_jwt(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # Extract local JWT claims
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")

    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user_id or tenant_id",
        )

    try:
        user_id = UUID(str(user_id))
        tenant_id = UUID(str(tenant_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
        )

    # Validate tenant exists and is active
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        logger.warning("tenant_not_found", tenant_id=str(tenant_id))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant",
        )

    if not tenant.is_active:
        logger.warning("tenant_inactive", tenant_id=str(tenant_id))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant is inactive",
        )

    # Validate user exists and is active
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.warning("user_not_found", user_id=str(user_id))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user",
        )

    if not user.is_active:
        logger.warning("user_inactive", user_id=str(user_id))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
        )

    logger.debug(
        "user_authenticated",
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
    )

    return user
