"""Test actors for the FINAL HITL decision (approve / reject / resume).

Production requires a server-authenticated human decider (``AuthorizedFinalDecider``) on every final decision: the
HTTP routes derive it from the signed-in user, ``ResumeWorkflowUseCase.execute`` refuses a request without one.
The legacy P0b / trusted-state suites exercise the *mechanics* of resume (leases, fences, N17, idempotency), not the
authorization, so they build their requests through ``decided_request`` and their users through ``human``. The
authorization itself is proven, with denials, in ``test_s5_project_authorization_evidence_pg.py``.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from src.core.auth.models import UserRole
from src.modules.hitl.application.final_decision_authorization import (
    AuthorizedFinalDecider,
    authorize_final_decider,
)
from src.modules.hitl.application.project_review_authorization import (
    AuthorizationMode,
    EffectiveCapabilities,
    ProjectAuthorization,
    ProjectCapability,
    ProjectReviewAuthorizer,
)
from src.modules.hitl.application.resume_workflow_use_case import ResumeWorkflowRequest

_PERSISTED_REVIEWER: ContextVar[Any | None] = ContextVar("a0b_test_reviewer", default=None)


def bind_persisted_reviewer(user: Any) -> Token:
    """Per-test real database-backed user. Never valid outside the test scope."""
    return _PERSISTED_REVIEWER.set(user)


def unbind_persisted_reviewer(token: Token) -> None:
    _PERSISTED_REVIEWER.reset(token)



def persisted_reviewer() -> Any | None:
    """Return the real fixture user only while this exact pytest case runs."""
    return _PERSISTED_REVIEWER.get()


TEST_DECIDER = AuthorizedFinalDecider(
    tenant_id=UUID(int=0xA11CE), user_id=UUID(int=0xB0B), display_name="Test Reviewer"
)


class PermissiveProjectAuthorizer(ProjectReviewAuthorizer):
    """For suites whose session is a hand-written fake (no ``tenants`` / ``project_review_grants`` tables).

    These suites exercise the mechanics of the review/resume code, not the per-project authority; that is proven, with
    denials, against PostgreSQL in ``test_s5_project_review_authorization_pg.py``. Never use it where the real
    authorizer can run.
    """

    def __init__(self) -> None:  # no session on purpose
        pass

    async def require(  # type: ignore[override]
        self, *, tenant_id: UUID, user_id: UUID, project_id: UUID | None, capability: ProjectCapability, lock: bool = False
    ) -> ProjectAuthorization:
        return ProjectAuthorization(tenant_id, project_id, user_id, capability, AuthorizationMode.OFF, None, enforced=False)


    async def mode(self, tenant_id: UUID) -> AuthorizationMode:  # noqa: ARG002
        return AuthorizationMode.OFF

    async def capabilities(  # type: ignore[override]
        self, *, tenant_id: UUID, user_id: UUID, project_id: UUID | None
    ) -> EffectiveCapabilities:
        return EffectiveCapabilities(AuthorizationMode.OFF, project_id, True, True, True)


def decided_request(*args: Any, **kwargs: Any) -> ResumeWorkflowRequest:
    """A ``ResumeWorkflowRequest`` that carries an authenticated human decider (same signature as the real one)."""
    if "decider" not in kwargs:
        db_user = _PERSISTED_REVIEWER.get()
        kwargs["decider"] = (
            authorize_final_decider(db_user, tenant_id=db_user.tenant_id)
            if db_user is not None
            else TEST_DECIDER  # Pure fake-session tests only.
        )
    return ResumeWorkflowRequest(*args, **kwargs)


def human(
    tenant_id: UUID,
    *,
    role: UserRole = UserRole.USER,
    name: str = "Reviewer",
    active: bool = True,
) -> Any:
    """What ``get_current_user`` yields for a member of ``tenant_id`` (an active human ADMIN/USER by default)."""
    db_user = _PERSISTED_REVIEWER.get()
    if (
        db_user is not None
        and str(db_user.tenant_id) == str(tenant_id)
        and role in (UserRole.USER, UserRole.ADMIN)
        and active
    ):
        # Return a request-shaped identity with an actually persisted ID.
        # Authorization remains enforced by production code and real SQL.
        return SimpleNamespace(
            id=db_user.id, tenant_id=tenant_id, role=role,
            is_active=active, full_name=name,
        )
    return SimpleNamespace(id=uuid4(), tenant_id=tenant_id, role=role, is_active=active, full_name=name)
