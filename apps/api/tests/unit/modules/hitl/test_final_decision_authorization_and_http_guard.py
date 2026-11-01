"""HIGH finding (S5): the FINAL decision (approve / reject / resume) belongs to an active human of the tenant only.

Before this guard a VIEWER or API principal could approve a candidate all the way to TRUSTED, and ``/hitl/resume/{id}``
carried no actor at all. Here: the rule itself, and the three HTTP routes through a real ASGI app with spies that FAIL
the test if any state-reading or state-changing collaborator is touched before the denial.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import UserRole
from src.core.security import get_current_tenant_id
from src.modules.hitl.adapters.http import router as hitl_router
from src.modules.hitl.adapters.http.dependencies import (
    get_hitl_service,
    get_resume_workflow_use_case,
)
from src.modules.hitl.application.final_decision_authorization import (
    AuthorizedFinalDecider,
    FinalDecisionNotAuthorized,
    authorize_final_decider,
)
from src.modules.hitl.application.resume_workflow_use_case import (
    ResumeWorkflowRequest,
    ResumeWorkflowResponse,
    ResumeWorkflowUseCase,
    WorkflowDecision,
)

TENANT = uuid4()


def _user(role: Any = UserRole.USER, *, tenant: UUID = TENANT, active: bool = True, name: str = "Ana Reviewer") -> Any:
    return SimpleNamespace(id=uuid4(), tenant_id=tenant, role=role, is_active=active, full_name=name)


# ── the rule ─────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.USER])
def test_an_active_admin_or_user_of_the_tenant_is_a_decider_and_gains_nothing_new(role: UserRole) -> None:
    user = _user(role)
    decider = authorize_final_decider(user, tenant_id=TENANT)
    assert decider == AuthorizedFinalDecider(tenant_id=TENANT, user_id=user.id, display_name="Ana Reviewer")


def test_the_display_name_falls_back_to_the_user_id_never_to_client_data() -> None:
    user = _user(name="  ")
    assert authorize_final_decider(user, tenant_id=TENANT).display_name == str(user.id)


@pytest.mark.parametrize(
    "principal",
    [
        pytest.param(_user(UserRole.VIEWER), id="viewer"),
        pytest.param(_user(UserRole.API), id="api"),
        pytest.param(_user(active=False), id="inactive"),
        pytest.param(_user(tenant=uuid4()), id="another-tenant"),
        pytest.param(_user(role="admin-ish"), id="unknown-role"),
        pytest.param(SimpleNamespace(id=uuid4(), full_name="no tenant/role"), id="no-claims"),
        pytest.param(None, id="no-principal"),
    ],
)
def test_every_other_principal_is_refused(principal: Any) -> None:
    with pytest.raises(FinalDecisionNotAuthorized):
        authorize_final_decider(principal, tenant_id=TENANT)


def test_a_denial_is_a_permission_error_never_a_value_error() -> None:
    """The HITL routes map ValueError to 400/404; a denial must never be answered as a bad request."""
    assert issubclass(FinalDecisionNotAuthorized, PermissionError)
    assert not issubclass(FinalDecisionNotAuthorized, ValueError)


# ── the application boundary: no decider, no decision ─────────────────────────────────────────────────────────
class _Untouchable:
    """A repository that fails the test if the use case reads or writes anything before refusing."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"state touched before the denial: {name}")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "decider",
    [None, SimpleNamespace(tenant_id=TENANT, user_id=uuid4(), display_name="forged"), "admin", object()],
    ids=["missing", "look-alike-object", "string", "bare-object"],
)
async def test_the_use_case_refuses_a_final_decision_without_a_proven_decider(decider: Any) -> None:
    use_case = ResumeWorkflowUseCase(review_queue_repo=_Untouchable())  # type: ignore[arg-type]
    for decision in (WorkflowDecision.APPROVE, WorkflowDecision.REJECT):
        request = ResumeWorkflowRequest(decision=decision, feedback="x", approved_by="forged", decider=decider)
        with pytest.raises(FinalDecisionNotAuthorized):
            await use_case.execute(uuid4(), request)


# ── the HTTP boundary, through a real ASGI app ────────────────────────────────────────────────────────────────
class _SpyUseCase:
    def __init__(self) -> None:
        self.requests: list[ResumeWorkflowRequest] = []

    async def execute(self, review_id: UUID, request: ResumeWorkflowRequest) -> ResumeWorkflowResponse:
        self.requests.append(request)
        return ResumeWorkflowResponse(review_id=review_id, status="resumed", message="ok")


def _app(user: Any, tenant: UUID, spy: _SpyUseCase) -> FastAPI:
    app = FastAPI()
    app.include_router(hitl_router.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant
    app.dependency_overrides[get_resume_workflow_use_case] = lambda: spy
    # approve/reject read the review through the service first: any touch before the denial fails the test.
    app.dependency_overrides[get_hitl_service] = lambda: _Untouchable()
    return app


_ROUTES = [
    ("approve", "POST", "/api/v1/hitl/queue/{id}/approve", {}),
    ("reject", "POST", "/api/v1/hitl/queue/{id}/reject", {"reason": "not acceptable"}),
    ("resume-approve", "POST", "/api/v1/hitl/resume/{id}", {"decision": "approve", "feedback": "fine"}),
    ("resume-reject", "POST", "/api/v1/hitl/resume/{id}", {"decision": "reject", "feedback": "no"}),
]
_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.mark.asyncio
@pytest.mark.parametrize("route", _ROUTES, ids=[r[0] for r in _ROUTES])
@pytest.mark.parametrize(
    "principal",
    [
        pytest.param(_user(UserRole.VIEWER), id="viewer"),
        pytest.param(_user(UserRole.API), id="api"),
        pytest.param(_user(active=False), id="inactive"),
        pytest.param(_user(tenant=uuid4()), id="foreign-tenant-user"),
    ],
)
async def test_every_final_decision_route_answers_403_before_touching_anything(route: Any, principal: Any) -> None:
    _name, method, path, body = route
    spy = _SpyUseCase()
    async with AsyncClient(transport=ASGITransport(app=_app(principal, TENANT, spy)), base_url="http://test") as client:
        for attempt in range(3):  # an unauthorized retry stays denied, every time
            answer = await client.request(method, path.format(id=uuid4()), json=body, headers=_HEADERS)
            assert answer.status_code == 403, (attempt, answer.text)
            assert answer.json()["detail"]["code"] == "final_decision_not_authorized"
    assert spy.requests == [], "the use case was never reached"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.USER])
async def test_resume_now_records_who_decided_and_hands_the_use_case_a_proven_decider(role: UserRole) -> None:
    user = _user(role, name="Ana Reviewer")
    spy = _SpyUseCase()
    async with AsyncClient(transport=ASGITransport(app=_app(user, TENANT, spy)), base_url="http://test") as client:
        answer = await client.post(
            f"/api/v1/hitl/resume/{uuid4()}", json={"decision": "approve", "feedback": "fine"}, headers=_HEADERS
        )
    assert answer.status_code == 200, answer.text
    [request] = spy.requests
    assert request.decider == AuthorizedFinalDecider(tenant_id=TENANT, user_id=user.id, display_name="Ana Reviewer")
    assert request.approved_by == "Ana Reviewer", "/resume used to carry no actor at all"


@pytest.mark.asyncio
async def test_a_client_cannot_name_the_decider_in_the_body() -> None:
    spy = _SpyUseCase()
    async with AsyncClient(transport=ASGITransport(app=_app(_user(), TENANT, spy)), base_url="http://test") as client:
        answer = await client.post(
            f"/api/v1/hitl/resume/{uuid4()}",
            json={"decision": "approve", "feedback": "fine", "approved_by": "the-admin", "decider": {"user_id": str(uuid4())}},
            headers=_HEADERS,
        )
    if answer.status_code == 200:  # extra keys are ignored: the actor is the authenticated one, never the body's
        [request] = spy.requests
        assert request.approved_by == "Ana Reviewer"
        assert request.decider is not None and request.decider.display_name == "Ana Reviewer"
    else:
        assert answer.status_code == 422 and spy.requests == []
