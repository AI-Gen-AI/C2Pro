"""S5-01: writes of ``project_review_grants`` -- only through the governed SQL functions.

The functions validate the actors in the database (an active ADMIN of the tenant grants and revokes; the grantee is an
active member; no ordinary self-grant) and write the grant and its audit event in ONE transaction. This repository adds
no rule of its own and offers no way to touch the table directly. It opens no transaction: the caller owns it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.hitl.application.project_review_authorization import ProjectCapability


class ProjectGrantRefused(ValueError):
    """The database refused the grant / revocation (the message is the database's own, e.g. 'only an active ADMIN ...')."""


@dataclass(frozen=True)
class ActiveGrant:
    grant_id: UUID
    project_id: UUID
    user_id: UUID
    capability: ProjectCapability
    granted_by: UUID
    granted_at: datetime
    reason: str
    self_grant_exception: bool


def _refusal(exc: DBAPIError) -> ProjectGrantRefused:
    text_ = str(exc.orig)
    marker = "ERROR:"
    return ProjectGrantRefused(text_.split(marker, 1)[-1].strip() if marker in text_ else text_)


class ProjectReviewGrantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _tenant_context(self, tenant_id: UUID) -> None:
        await self._session.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(tenant_id)})

    async def grant(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        user_id: UUID,
        capability: ProjectCapability,
        granted_by: UUID,
        reason: str,
        exception_reason: str | None = None,
    ) -> UUID:
        await self._tenant_context(tenant_id)
        try:
            async with self._session.begin_nested():
                result = (
                    await self._session.execute(
                        text(
                            "SELECT public.project_review_grant_create(cast(:t as uuid), cast(:p as uuid), cast(:u as uuid), "
                            ":perm, cast(:by as uuid), :reason, :exc)"
                        ),
                        {
                            "t": str(tenant_id), "p": str(project_id), "u": str(user_id), "perm": capability.value,
                            "by": str(granted_by), "reason": reason, "exc": exception_reason,
                        },
                    )
                ).scalar_one()
            return UUID(str(result))
        except DBAPIError as exc:
            raise _refusal(exc) from exc

    async def revoke(self, *, tenant_id: UUID, grant_id: UUID, revoked_by: UUID, reason: str) -> None:
        await self._tenant_context(tenant_id)
        try:
            async with self._session.begin_nested():
                await self._session.execute(
                    text(
                        "SELECT public.project_review_grant_revoke(cast(:t as uuid), cast(:g as uuid), cast(:by as uuid), :reason)"
                    ),
                    {"t": str(tenant_id), "g": str(grant_id), "by": str(revoked_by), "reason": reason},
                )
        except DBAPIError as exc:
            raise _refusal(exc) from exc

    async def list_active(self, *, tenant_id: UUID, project_id: UUID | None = None) -> list[ActiveGrant]:
        await self._tenant_context(tenant_id)
        rows = (
            await self._session.execute(
                text(
                    "SELECT grant_id, project_id, user_id, permission, granted_by, granted_at, grant_reason, "
                    "self_grant_exception FROM public.project_review_grants "
                    "WHERE tenant_id = cast(:t as uuid) AND revoked_at IS NULL "
                    "AND (cast(:p as uuid) IS NULL OR project_id = cast(:p as uuid)) ORDER BY granted_at, grant_id"
                ),
                {"t": str(tenant_id), "p": str(project_id) if project_id else None},
            )
        ).mappings().all()
        return [
            ActiveGrant(
                row["grant_id"], row["project_id"], row["user_id"], ProjectCapability(row["permission"]),
                row["granted_by"], row["granted_at"], row["grant_reason"], bool(row["self_grant_exception"]),
            )
            for row in rows
        ]
