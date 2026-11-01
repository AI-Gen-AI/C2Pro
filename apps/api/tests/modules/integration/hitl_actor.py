"""Test actors for the FINAL HITL decision (approve / reject / resume).

Production requires a server-authenticated human decider (``AuthorizedFinalDecider``) on every final decision: the
HTTP routes derive it from the signed-in user, ``ResumeWorkflowUseCase.execute`` refuses a request without one.
The legacy P0b / trusted-state suites exercise the *mechanics* of resume (leases, fences, N17, idempotency), not the
authorization, so they build their requests through ``decided_request`` and their users through ``human``. The
authorization itself is proven, with denials, in ``test_s5_project_authorization_evidence_pg.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from src.core.auth.models import UserRole
from src.modules.hitl.application.final_decision_authorization import AuthorizedFinalDecider
from src.modules.hitl.application.project_review_authorization import (
    AuthorizationMode,
    EffectiveCapabilities,
    ProjectAuthorization,
    ProjectCapability,
    ProjectReviewAuthorizer,
)
from src.modules.hitl.application.resume_workflow_use_case import ResumeWorkflowRequest

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
    kwargs.setdefault("decider", TEST_DECIDER)
    return ResumeWorkflowRequest(*args, **kwargs)


def human(
    tenant_id: UUID,
    *,
    role: UserRole = UserRole.USER,
    name: str = "Reviewer",
    active: bool = True,
) -> Any:
    """What ``get_current_user`` yields for a member of ``tenant_id`` (an active human ADMIN/USER by default)."""
    return SimpleNamespace(id=uuid4(), tenant_id=tenant_id, role=role, is_active=active, full_name=name)
