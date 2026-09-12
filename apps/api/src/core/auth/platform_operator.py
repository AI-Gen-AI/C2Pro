"""C2.6 platform-operator authorization, isolated from tenant authentication."""

from dataclasses import dataclass

import structlog
from fastapi import HTTPException, Request, status

from src.config import settings
from src.core.auth.bootstrap_lookup import lookup_tenant_by_clerk_org_id
from src.core.database import get_raw_session

logger = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class PlatformIdentity:
    """Claims verified once by the platform-route Clerk authentication mode."""

    user_id: str
    org_id: str | None
    email: str | None
    email_verified: bool


@dataclass(frozen=True, slots=True)
class PlatformOperator:
    """Tenant-less principal for the intentionally narrow C2.6 platform surface."""

    clerk_user_id: str
    clerk_org_id: str
    email: str | None
    auth_tier: str = "platform_operator"


def _not_authorized(reason: str) -> HTTPException:
    logger.warning("platform_operator_denied", reason=reason)
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


async def operator_org_is_contaminated(clerk_org_id: str) -> bool:
    """Run G5's single lookup. A tenant mapping or lookup failure can only deny."""
    try:
        async with get_raw_session() as db:
            return await lookup_tenant_by_clerk_org_id(db, clerk_org_id) is not None
    except Exception:
        logger.warning("platform_operator_integrity_lookup_failed")
        return True


async def require_platform_operator(request: Request) -> PlatformOperator:
    """Authorize an already Clerk-verified identity without entering tenant context."""
    identity = getattr(request.state, "platform_identity", None)
    if not isinstance(identity, PlatformIdentity):
        raise _not_authorized("missing_platform_identity")

    configured_org_id = settings.platform_operator_org_id
    if configured_org_id is None or not configured_org_id.strip():
        logger.error("platform_operator_unconfigured")
        raise _not_authorized("platform_operator_org_unconfigured")
    if identity.org_id != configured_org_id:
        raise _not_authorized("organization_mismatch")
    if settings.platform_operator_user_ids and (
        identity.user_id not in settings.platform_operator_user_ids
    ):
        raise _not_authorized("allowlist_mismatch")
    if not identity.email_verified:
        raise _not_authorized("email_not_verified")
    if await operator_org_is_contaminated(configured_org_id):
        raise _not_authorized("operator_organization_contaminated")

    structlog.contextvars.bind_contextvars(
        platform_operator_id=identity.user_id,
        org_id=configured_org_id,
    )
    logger.info(
        "platform_operator_granted",
        clerk_user_id=identity.user_id,
        clerk_org_id=configured_org_id,
    )
    return PlatformOperator(
        clerk_user_id=identity.user_id,
        clerk_org_id=configured_org_id,
        email=identity.email,
    )
