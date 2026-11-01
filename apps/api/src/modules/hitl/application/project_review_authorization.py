"""S5-02: the ONE authority that decides what an actor may do on the review of a project.

``ProjectReviewAuthorizer`` is the single place that turns an explicit, revocable ``project_review_grants`` row into a
capability. Three capabilities, none implying another (a REVIEWER is not an APPROVER, and an ADMIN of the tenant has no
implicit capability at all):

* ``READ_REVIEW``       read the findings of a review of the project;
* ``REVIEW_FINDING``    record a provisional decision on one finding;
* ``APPROVE_CANDIDATE`` take the FINAL decision (approve / reject / resume) on the candidate.

The project is ALWAYS the review row's own project (read from the database by the caller), never a client value. The
principal is ``(tenant_id, users.id)``: ``users.id`` is stable per Clerk user across organizations, and the tenant is
proved at check time by ``users.tenant_id`` -- so a grant of tenant A can never be used in tenant B (it is dormant while
the user is in B). Denials carry whether the actor already has legitimate access to the resource (any active grant on
the project): 403 when it does and lacks the capability, 404 when it does not (no existence leak).

Rollout (``tenants.settings.hitl_project_authorization.mode``): ``off`` and ``audit`` are TRANSITIONAL states, not a
secure state; ``enforce`` denies. A missing, unknown or unreadable mode is ``enforce`` (fail closed).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class ProjectCapability(StrEnum):
    READ_REVIEW = "READ_REVIEW"
    REVIEW_FINDING = "REVIEW_FINDING"
    APPROVE_CANDIDATE = "APPROVE_CANDIDATE"


class AuthorizationMode(StrEnum):
    OFF = "off"
    AUDIT = "audit"
    ENFORCE = "enforce"


class ProjectAuthorizationDenied(PermissionError):
    """No active grant of the capability. ``visible`` = the actor holds ANY active grant on the project."""

    def __init__(self, capability: ProjectCapability, *, visible: bool) -> None:
        super().__init__(f"{capability.value} on this review's project is not granted")
        self.capability = capability
        self.visible = visible


class ProjectAuthorizationUnavailable(RuntimeError):
    """The authorizer cannot be built (no database session): a final decision then fails closed."""


@dataclass(frozen=True)
class ProjectAuthorization:
    """Proof that ``user_id`` holds ``capability`` on ``project_id`` (S5-05 re-validates it before the first TRUSTED)."""

    tenant_id: UUID
    project_id: UUID | None
    user_id: UUID
    capability: ProjectCapability
    mode: AuthorizationMode
    grant_id: UUID | None  # None only in off / audit-without-grant
    enforced: bool


@dataclass(frozen=True)
class EffectiveCapabilities:
    mode: AuthorizationMode
    project_id: UUID | None
    read_review: bool
    review_finding: bool
    approve_candidate: bool


SETTINGS_KEY = "hitl_project_authorization"


def transitional_off_setting(reason: str) -> dict[str, Any]:
    """The explicit, attributable ``off`` marker for a tenant that must keep the legacy rule for now.

    ``off`` is a TRANSITIONAL state, never a secure one: the marker says so and carries its reason. A tenant WITHOUT the
    marker is ``enforce``. Retirement gate (no date invented): a tenant leaves ``off`` / ``audit`` only after its real
    grants were created, a ``audit`` period showed no unexpected ``would_deny``, and the negatives were verified.
    """
    return {"mode": AuthorizationMode.OFF.value, "transitional": True, "reason": reason}


_MODE_SQL = text("SELECT settings #>> '{hitl_project_authorization,mode}' FROM public.tenants WHERE id = cast(:t as uuid)")

_REVIEW_PROJECT_SQL = text(
    "SELECT project_id FROM public.review_items WHERE id = cast(:r as uuid) AND tenant_id = cast(:t as uuid)"
)

_ACTIVE_SQL = """
SELECT g.grant_id, g.permission
FROM public.project_review_grants g
JOIN public.users u ON u.id = g.user_id AND u.tenant_id = g.tenant_id AND u.is_active
WHERE g.tenant_id = cast(:t as uuid) AND g.project_id = cast(:p as uuid) AND g.user_id = cast(:u as uuid)
  AND g.revoked_at IS NULL
"""


class ProjectReviewAuthorizer:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    @classmethod
    def for_repository(cls, repository: Any) -> ProjectReviewAuthorizer:
        session = getattr(repository, "session", None)
        if not isinstance(session, AsyncSession):
            raise ProjectAuthorizationUnavailable("no database session to authorize the final decision against")
        return cls(session)

    async def mode(self, tenant_id: UUID) -> AuthorizationMode:
        raw = (await self._session.execute(_MODE_SQL, {"t": str(tenant_id)})).scalar_one_or_none()
        try:
            return AuthorizationMode(str(raw).lower()) if raw is not None else AuthorizationMode.ENFORCE
        except ValueError:
            return AuthorizationMode.ENFORCE  # unknown value: fail closed

    async def _active(
        self, tenant_id: UUID, user_id: UUID, project_id: UUID, *, lock: bool
    ) -> dict[str, UUID]:
        sql = text(_ACTIVE_SQL + (" FOR SHARE OF g" if lock else ""))
        rows = (
            await self._session.execute(sql, {"t": str(tenant_id), "p": str(project_id), "u": str(user_id)})
        ).all()
        return {str(permission): grant_id for grant_id, permission in rows}

    async def require(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        project_id: UUID | None,
        capability: ProjectCapability,
        lock: bool = False,
    ) -> ProjectAuthorization:
        """Raise ``ProjectAuthorizationDenied`` unless the capability is granted (``lock`` = read the grant FOR SHARE)."""
        mode = await self.mode(tenant_id)
        if mode is AuthorizationMode.OFF:
            return ProjectAuthorization(tenant_id, project_id, user_id, capability, mode, None, enforced=False)
        active = await self._active(tenant_id, user_id, project_id, lock=lock) if project_id is not None else {}
        grant_id = active.get(capability.value)
        if grant_id is not None:
            return ProjectAuthorization(tenant_id, project_id, user_id, capability, mode, grant_id, enforced=mode is AuthorizationMode.ENFORCE)
        if mode is AuthorizationMode.AUDIT:
            logger.warning(
                "hitl_project_authorization_would_deny",
                tenant_id=str(tenant_id), project_id=str(project_id) if project_id else None,
                user_id=str(user_id), capability=capability.value,
            )
            return ProjectAuthorization(tenant_id, project_id, user_id, capability, mode, None, enforced=False)
        logger.warning(
            "hitl_project_authorization_denied",
            tenant_id=str(tenant_id), project_id=str(project_id) if project_id else None,
            user_id=str(user_id), capability=capability.value, visible=bool(active),
        )
        raise ProjectAuthorizationDenied(capability, visible=bool(active))

    async def revalidate(self, proof: ProjectAuthorization) -> ProjectAuthorization:
        """The S5-05 contract: re-check the SAME capability, locking the grant row FOR SHARE.

        Called inside the transaction that will commit the first TRUSTED: a revocation (an UPDATE of that row) then
        waits for this transaction, or has already been committed and is seen here. The proof is valid only if the grant
        it was issued for is still the active one.
        """
        if proof.project_id is None:
            raise ProjectAuthorizationDenied(proof.capability, visible=False)
        fresh = await self.require(
            tenant_id=proof.tenant_id, user_id=proof.user_id, project_id=proof.project_id,
            capability=proof.capability, lock=True,
        )
        if fresh.enforced and fresh.grant_id != proof.grant_id:
            raise ProjectAuthorizationDenied(proof.capability, visible=True)
        return fresh

    async def capabilities(self, *, tenant_id: UUID, user_id: UUID, project_id: UUID | None) -> EffectiveCapabilities:
        """Read-only: what the actor may do on the review's project (for the UI; every action re-validates)."""
        mode = await self.mode(tenant_id)
        if mode is not AuthorizationMode.ENFORCE:
            # off / audit: the legacy rule (the human gate) applies, so the UI does not hide what is allowed today.
            return EffectiveCapabilities(mode, project_id, True, True, True)
        active = await self._active(tenant_id, user_id, project_id, lock=False) if project_id is not None else {}
        return EffectiveCapabilities(
            mode, project_id,
            ProjectCapability.READ_REVIEW.value in active,
            ProjectCapability.REVIEW_FINDING.value in active,
            ProjectCapability.APPROVE_CANDIDATE.value in active,
        )

    async def capabilities_for_review(
        self, *, tenant_id: UUID, user_id: UUID, review_row_id: UUID
    ) -> EffectiveCapabilities:
        """Capabilities on a review row's own project. Unknown row, or (enforce) no grant at all on its project => the
        review is NOT visible to the actor: ``ProjectAuthorizationDenied(visible=False)`` (404, no existence leak)."""
        project_id = (
            await self._session.execute(_REVIEW_PROJECT_SQL, {"r": str(review_row_id), "t": str(tenant_id)})
        ).scalar_one_or_none()
        if project_id is None:
            raise ProjectAuthorizationDenied(ProjectCapability.READ_REVIEW, visible=False)
        caps = await self.capabilities(tenant_id=tenant_id, user_id=user_id, project_id=project_id)
        if caps.mode is AuthorizationMode.ENFORCE and not (
            caps.read_review or caps.review_finding or caps.approve_candidate
        ):
            raise ProjectAuthorizationDenied(ProjectCapability.READ_REVIEW, visible=False)
        return caps


__all__ = [
    "SETTINGS_KEY",
    "transitional_off_setting",
    "AuthorizationMode",
    "EffectiveCapabilities",
    "ProjectAuthorization",
    "ProjectAuthorizationDenied",
    "ProjectAuthorizationUnavailable",
    "ProjectCapability",
    "ProjectReviewAuthorizer",
]
