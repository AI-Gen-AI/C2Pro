"""
Bootstrap auth lookup helpers.

These helpers provide a narrow pre-tenant lookup path for authentication and
tenant resolution. They are intended to move auth bootstrap reads away from
direct table access once fail-closed RLS is enabled on `tenants` and `users`.

TASK-BCK-018: Added AUTH_BOOTSTRAP_ALLOW_FALLBACK_EMERGENCY config for explicit
emergency override. Normal production uses SQL-only; ORM fallback only when
AUTH_BOOTSTRAP_ALLOW_FALLBACK_EMERGENCY=true is explicitly set.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.auth.models import Tenant, User, UserRole

logger = structlog.get_logger()

ResolutionPath = Literal["bootstrap_sql", "orm_fallback", "blocked"]


class BootstrapFallbackBlockedError(RuntimeError):
    """Raised when ORM fallback is blocked by auth bootstrap policy."""


def is_bootstrap_fallback_allowed() -> bool:
    """
    Evaluate whether ORM fallback is allowed for bootstrap auth helpers.

    Returns True ONLY if AUTH_BOOTSTRAP_ALLOW_FALLBACK_EMERGENCY=true is explicitly set.
    This is intended for EMERGENCY USE ONLY during outages.

    Normal production operation: Always returns False (SQL-only).
    """
    return settings.auth_bootstrap_allow_fallback_emergency


def _emit_resolution_event(
    *,
    operation: str,
    resolution_path: ResolutionPath,
    fallback_allowed: bool,
    fallback_blocked: bool,
    error_code: str | None = None,
    error: str | None = None,
) -> None:
    if not settings.auth_bootstrap_emit_metrics:
        return

    logger.info(
        "auth_bootstrap_resolution",
        operation=operation,
        environment=settings.environment,
        resolution_path=resolution_path,
        fallback_allowed=fallback_allowed,
        fallback_blocked=fallback_blocked,
        fallback_blocked_by_policy=fallback_blocked,
        error_code=error_code,
        error=error,
    )


def _handle_sql_failure(*, operation: str, error: Exception) -> None:
    fallback_allowed = is_bootstrap_fallback_allowed()

    if not fallback_allowed:
        _emit_resolution_event(
            operation=operation,
            resolution_path="blocked",
            fallback_allowed=False,
            fallback_blocked=True,
            error_code="auth_bootstrap_fallback_blocked",
            error=str(error),
        )
        raise BootstrapFallbackBlockedError("Auth bootstrap fallback blocked by policy")

    _emit_resolution_event(
        operation=operation,
        resolution_path="orm_fallback",
        fallback_allowed=True,
        fallback_blocked=False,
        error_code="auth_bootstrap_sql_failed",
        error=str(error),
    )


def _log_fallback_warning(event: str, **kwargs: str) -> None:
    logger.warning(event, **kwargs)


@dataclass(slots=True)
class BootstrapTenantRecord:
    tenant_id: UUID
    is_active: bool
    clerk_org_id: str | None = None
    tenant_name: str | None = None


@dataclass(slots=True)
class BootstrapUserRecord:
    user_id: UUID
    tenant_id: UUID
    email: str
    is_active: bool
    hashed_password: str | None = None
    role: str | None = None
    clerk_user_id: str | None = None


async def lookup_tenant_by_id(
    db: AsyncSession,
    tenant_id: UUID,
) -> BootstrapTenantRecord | None:
    try:
        async with db.begin_nested():
            result = await db.execute(
                text(
                    """
                    SELECT tenant_id, is_active, clerk_org_id
                    FROM auth_bootstrap.lookup_tenant_by_id(:tenant_id)
                    """
                ),
                {"tenant_id": str(tenant_id)},
            )
            row = result.mappings().one_or_none()
            if row is not None:
                _emit_resolution_event(
                    operation="lookup_tenant_by_id",
                    resolution_path="bootstrap_sql",
                    fallback_allowed=is_bootstrap_fallback_allowed(),
                    fallback_blocked=False,
                )
                return BootstrapTenantRecord(
                    tenant_id=row["tenant_id"],
                    is_active=row["is_active"],
                    clerk_org_id=row["clerk_org_id"],
                )
    except SQLAlchemyError as exc:
        _handle_sql_failure(operation="lookup_tenant_by_id", error=exc)
        _log_fallback_warning(
            "bootstrap_lookup_tenant_by_id_fallback",
            tenant_id=str(tenant_id),
            error=str(exc),
        )

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        return None
    return BootstrapTenantRecord(
        tenant_id=tenant.id,
        is_active=bool(tenant.is_active),
        clerk_org_id=tenant.clerk_org_id,
        tenant_name=tenant.name,
    )


async def lookup_tenant_by_clerk_org_id(
    db: AsyncSession,
    clerk_org_id: str,
) -> BootstrapTenantRecord | None:
    try:
        async with db.begin_nested():
            result = await db.execute(
                text(
                    """
                    SELECT tenant_id, is_active, clerk_org_id, tenant_name
                    FROM auth_bootstrap.lookup_tenant_by_clerk_org_id(:clerk_org_id)
                    """
                ),
                {"clerk_org_id": clerk_org_id},
            )
            row = result.mappings().one_or_none()
            if row is not None:
                _emit_resolution_event(
                    operation="lookup_tenant_by_clerk_org_id",
                    resolution_path="bootstrap_sql",
                    fallback_allowed=is_bootstrap_fallback_allowed(),
                    fallback_blocked=False,
                )
                return BootstrapTenantRecord(
                    tenant_id=row["tenant_id"],
                    is_active=row["is_active"],
                    clerk_org_id=row["clerk_org_id"],
                    tenant_name=row["tenant_name"],
                )
    except SQLAlchemyError as exc:
        _handle_sql_failure(operation="lookup_tenant_by_clerk_org_id", error=exc)
        _log_fallback_warning(
            "bootstrap_lookup_tenant_by_clerk_org_id_fallback",
            clerk_org_id=clerk_org_id,
            error=str(exc),
        )

    result = await db.execute(select(Tenant).where(Tenant.clerk_org_id == clerk_org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        return None
    return BootstrapTenantRecord(
        tenant_id=tenant.id,
        is_active=bool(tenant.is_active),
        clerk_org_id=tenant.clerk_org_id,
        tenant_name=tenant.name,
    )


async def lookup_personal_tenant_by_name(
    db: AsyncSession,
    tenant_name: str,
) -> BootstrapTenantRecord | None:
    try:
        async with db.begin_nested():
            result = await db.execute(
                text(
                    """
                    SELECT tenant_id, is_active, clerk_org_id, tenant_name
                    FROM auth_bootstrap.lookup_personal_tenant_by_name(:tenant_name)
                    """
                ),
                {"tenant_name": tenant_name},
            )
            row = result.mappings().one_or_none()
            if row is not None:
                _emit_resolution_event(
                    operation="lookup_personal_tenant_by_name",
                    resolution_path="bootstrap_sql",
                    fallback_allowed=is_bootstrap_fallback_allowed(),
                    fallback_blocked=False,
                )
                return BootstrapTenantRecord(
                    tenant_id=row["tenant_id"],
                    is_active=row["is_active"],
                    clerk_org_id=row["clerk_org_id"],
                    tenant_name=row["tenant_name"],
                )
    except SQLAlchemyError as exc:
        _handle_sql_failure(operation="lookup_personal_tenant_by_name", error=exc)
        _log_fallback_warning(
            "bootstrap_lookup_personal_tenant_by_name_fallback",
            tenant_name=tenant_name,
            error=str(exc),
        )

    result = await db.execute(select(Tenant).where(Tenant.name == tenant_name))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        return None
    return BootstrapTenantRecord(
        tenant_id=tenant.id,
        is_active=bool(tenant.is_active),
        clerk_org_id=tenant.clerk_org_id,
        tenant_name=tenant.name,
    )


async def lookup_user_by_clerk_user_id(
    db: AsyncSession,
    clerk_user_id: str,
) -> BootstrapUserRecord | None:
    try:
        async with db.begin_nested():
            result = await db.execute(
                text(
                    """
                    SELECT user_id, tenant_id, email, is_active
                    FROM auth_bootstrap.lookup_user_by_clerk_user_id(:clerk_user_id)
                    """
                ),
                {"clerk_user_id": clerk_user_id},
            )
            row = result.mappings().one_or_none()
            if row is not None:
                _emit_resolution_event(
                    operation="lookup_user_by_clerk_user_id",
                    resolution_path="bootstrap_sql",
                    fallback_allowed=is_bootstrap_fallback_allowed(),
                    fallback_blocked=False,
                )
                return BootstrapUserRecord(
                    user_id=row["user_id"],
                    tenant_id=row["tenant_id"],
                    email=row["email"],
                    is_active=row["is_active"],
                    clerk_user_id=clerk_user_id,
                )
    except SQLAlchemyError as exc:
        _handle_sql_failure(operation="lookup_user_by_clerk_user_id", error=exc)
        _log_fallback_warning(
            "bootstrap_lookup_user_by_clerk_id_fallback",
            clerk_user_id=clerk_user_id,
            error=str(exc),
        )

    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    return BootstrapUserRecord(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        is_active=bool(user.is_active),
        hashed_password=user.hashed_password,
        role=user.role.value if user.role else None,
        clerk_user_id=user.clerk_user_id,
    )


async def lookup_user_by_email(
    db: AsyncSession,
    email: str,
) -> BootstrapUserRecord | None:
    try:
        async with db.begin_nested():
            result = await db.execute(
                text(
                    """
                    SELECT user_id, tenant_id, email, is_active, hashed_password, role
                    FROM auth_bootstrap.lookup_user_by_email(:email)
                    """
                ),
                {"email": email},
            )
            row = result.mappings().one_or_none()
            if row is not None:
                _emit_resolution_event(
                    operation="lookup_user_by_email",
                    resolution_path="bootstrap_sql",
                    fallback_allowed=is_bootstrap_fallback_allowed(),
                    fallback_blocked=False,
                )
                return BootstrapUserRecord(
                    user_id=row["user_id"],
                    tenant_id=row["tenant_id"],
                    email=row["email"],
                    is_active=row["is_active"],
                    hashed_password=row["hashed_password"],
                    role=row["role"],
                )
    except SQLAlchemyError as exc:
        _handle_sql_failure(operation="lookup_user_by_email", error=exc)
        _log_fallback_warning(
            "bootstrap_lookup_user_by_email_fallback",
            email=email,
            error=str(exc),
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    return BootstrapUserRecord(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        is_active=bool(user.is_active),
        hashed_password=user.hashed_password,
        role=user.role.value if user.role else None,
        clerk_user_id=user.clerk_user_id,
    )


async def create_bootstrap_tenant(
    db: AsyncSession,
    *,
    tenant_name: str,
    tenant_slug: str,
    clerk_org_id: str | None = None,
) -> BootstrapTenantRecord:
    try:
        async with db.begin_nested():
            result = await db.execute(
                text(
                    """
                    SELECT tenant_id, is_active, clerk_org_id, tenant_name
                    FROM auth_bootstrap.create_tenant(:tenant_name, :tenant_slug, :clerk_org_id)
                    """
                ),
                {
                    "tenant_name": tenant_name,
                    "tenant_slug": tenant_slug,
                    "clerk_org_id": clerk_org_id,
                },
            )
            row = result.mappings().one()
            _emit_resolution_event(
                operation="create_bootstrap_tenant",
                resolution_path="bootstrap_sql",
                fallback_allowed=is_bootstrap_fallback_allowed(),
                fallback_blocked=False,
            )
            return BootstrapTenantRecord(
                tenant_id=row["tenant_id"],
                is_active=row["is_active"],
                clerk_org_id=row["clerk_org_id"],
                tenant_name=row["tenant_name"],
            )
    except SQLAlchemyError as exc:
        _handle_sql_failure(operation="create_bootstrap_tenant", error=exc)
        _log_fallback_warning(
            "bootstrap_create_tenant_fallback",
            tenant_name=tenant_name,
            error=str(exc),
        )

    tenant = Tenant(
        name=tenant_name,
        slug=tenant_slug,
        clerk_org_id=clerk_org_id,
        is_active=True,
    )
    db.add(tenant)
    await db.flush()
    return BootstrapTenantRecord(
        tenant_id=tenant.id,
        is_active=bool(tenant.is_active),
        clerk_org_id=tenant.clerk_org_id,
        tenant_name=tenant.name,
    )


async def create_bootstrap_user(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    email: str,
    hashed_password: str | None,
    first_name: str | None,
    last_name: str | None,
    role: str,
    clerk_user_id: str | None = None,
) -> BootstrapUserRecord:
    try:
        async with db.begin_nested():
            result = await db.execute(
                text(
                    """
                    SELECT user_id, tenant_id, email, is_active, hashed_password, role
                    FROM auth_bootstrap.create_user(
                        :tenant_id,
                        :email,
                        :hashed_password,
                        :first_name,
                        :last_name,
                        :role,
                        :clerk_user_id
                    )
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "email": email,
                    "hashed_password": hashed_password,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": role,
                    "clerk_user_id": clerk_user_id,
                },
            )
            row = result.mappings().one()
            _emit_resolution_event(
                operation="create_bootstrap_user",
                resolution_path="bootstrap_sql",
                fallback_allowed=is_bootstrap_fallback_allowed(),
                fallback_blocked=False,
            )
            return BootstrapUserRecord(
                user_id=row["user_id"],
                tenant_id=row["tenant_id"],
                email=row["email"],
                is_active=row["is_active"],
                hashed_password=row["hashed_password"],
                role=row["role"],
                clerk_user_id=clerk_user_id,
            )
    except SQLAlchemyError as exc:
        _handle_sql_failure(operation="create_bootstrap_user", error=exc)
        _log_fallback_warning(
            "bootstrap_create_user_fallback",
            email=email,
            error=str(exc),
        )

    user = User(
        tenant_id=tenant_id,
        email=email,
        hashed_password=hashed_password,
        first_name=first_name,
        last_name=last_name,
        clerk_user_id=clerk_user_id,
        role=UserRole(role),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return BootstrapUserRecord(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        is_active=bool(user.is_active),
        hashed_password=user.hashed_password,
        role=user.role.value if user.role else None,
        clerk_user_id=user.clerk_user_id,
    )
