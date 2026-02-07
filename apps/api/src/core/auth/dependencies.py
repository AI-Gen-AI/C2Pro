"""
C2Pro - Authentication Dependencies

FastAPI dependencies for JWT authentication and authorization.
Minimal implementation for TS-E2E-SEC-TNT-001.
"""

from typing import Annotated
from uuid import UUID

import jwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.auth.models import Tenant, User
from src.core.database import get_session


logger = structlog.get_logger()
security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """
    Get current authenticated user from JWT token.

    Validates:
    1. JWT signature and expiration
    2. tenant_id exists in payload
    3. Tenant exists and is active
    4. User exists and is active

    Raises 401 if any validation fails.
    """
    token = credentials.credentials

    try:
        # Decode JWT
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        # Extract claims
        user_id: UUID | None = payload.get("sub")
        tenant_id: UUID | None = payload.get("tenant_id")
        email: str | None = payload.get("email")

        if not user_id or not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id or tenant_id",
            )

        # Convert to UUID
        user_id = UUID(str(user_id))
        tenant_id = UUID(str(tenant_id))

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
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
