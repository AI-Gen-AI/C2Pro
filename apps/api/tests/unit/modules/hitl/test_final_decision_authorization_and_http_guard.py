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


# JV1-A15: synthetic coverage contract, never private contract data.
def _synthetic_n4_coverage(*, resolution: str = "OPEN", status: str = "COMPLETE_WITH_GAPS") -> dict[str, Any]:
    return {
        "schema_version": "n4-coverage-v1",
        "status": status,
        "run_id": str(uuid4()),
        "source_sha256": "a" * 64,
        "total_windows": 3,
        "examined_windows": 2,
        "gap_windows": [2],
        "gaps": [{
            "ordinal": 2, "failure_kind": "INVALID_ENVELOPE", "reason": "synthetic failure",
            "attempts": 1, "page_start": 4, "page_end": 5, "resolution": resolution,
            **({"closed_reason": "Manually reviewed synthetic pages", "closed_by": "Ana",
                "closed_at": "2026-11-22T00:00:00Z"} if resolution == "CLOSED_MANUALLY" else {}),
        }],
    }


@pytest.mark.parametrize("field", ["metadata", "item_data"])
def test_a15_final_approval_refuses_open_n4_gaps_from_either_review_projection(field: str) -> None:
    from src.modules.hitl.application import resume_workflow_use_case as module

    review = SimpleNamespace(metadata={}, item_data={})
    getattr(review, field)["analysis_n4_coverage" if field == "metadata" else "n4_coverage"] = _synthetic_n4_coverage()
    with pytest.raises(module.N4CoverageGapsError) as blocked:
        module.require_n4_coverage_ready(review, approve=True)
    assert blocked.value.pending_windows == 1


def test_a15_manual_closure_of_every_gap_allows_final_approval_without_requiring_a_new_run() -> None:
    from src.modules.hitl.application import resume_workflow_use_case as module

    coverage = _synthetic_n4_coverage(resolution="CLOSED_MANUALLY")
    review = SimpleNamespace(metadata={"analysis_n4_coverage": coverage}, item_data={"n4_coverage": coverage})
    module.require_n4_coverage_ready(review, approve=True)


def test_a15_incomplete_unaccounted_window_fails_closed_even_without_a_gap_row() -> None:
    from src.modules.hitl.application import resume_workflow_use_case as module

    coverage = _synthetic_n4_coverage(status="INCOMPLETE")
    coverage["gap_windows"] = []
    coverage["gaps"] = []
    with pytest.raises(module.N4CoverageGapsError):
        module.require_n4_coverage_ready(
            SimpleNamespace(metadata={"analysis_n4_coverage": coverage}, item_data={}), approve=True
        )


def test_a15_rejection_and_legacy_reviews_remain_allowed() -> None:
    from src.modules.hitl.application import resume_workflow_use_case as module

    with_gap = SimpleNamespace(metadata={"analysis_n4_coverage": _synthetic_n4_coverage()}, item_data={})
    module.require_n4_coverage_ready(with_gap, approve=False)
    module.require_n4_coverage_ready(SimpleNamespace(metadata={}, item_data={}), approve=True)


def test_a15_malformed_or_conflicting_coverage_is_not_an_approval_bypass() -> None:
    from src.modules.hitl.application import resume_workflow_use_case as module

    with pytest.raises(module.N4CoverageGapsError):
        module.require_n4_coverage_ready(
            SimpleNamespace(metadata={"analysis_n4_coverage": {"status": "COMPLETE"}}, item_data={}), approve=True
        )
    complete = _synthetic_n4_coverage(resolution="CLOSED_MANUALLY")
    incomplete = _synthetic_n4_coverage()
    with pytest.raises(module.N4CoverageGapsError):
        module.require_n4_coverage_ready(
            SimpleNamespace(metadata={"analysis_n4_coverage": complete}, item_data={"n4_coverage": incomplete}),
            approve=True,
        )


@pytest.mark.asyncio
async def test_a15_approval_stops_before_acquiring_a_resume_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock

    from src.modules.hitl.application import resume_workflow_use_case as module
    from src.modules.hitl.domain.entities import ReviewStatus

    review_id, project_id, document_id = uuid4(), uuid4(), uuid4()
    review = SimpleNamespace(
        item_id=review_id, item_data={}, current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
        metadata={
            "row_id": str(review_id), "tenant_id": str(TENANT), "project_id": str(project_id),
            "document_id": str(document_id), "thread_id": "synthetic-a15-thread",
            "checkpoint_id": "synthetic-checkpoint",
            "analysis_n4_coverage": _synthetic_n4_coverage(),
        },
    )
    repo = SimpleNamespace(get_review_item=AsyncMock(return_value=review))
    checkpoint = SimpleNamespace(
        restore_checkpoint=AsyncMock(return_value=SimpleNamespace(checkpoint={}, checkpoint_id="synthetic-checkpoint")),
        extract_state=lambda _: {},
    )
    uc = ResumeWorkflowUseCase(
        review_queue_repo=repo,
        checkpoint_service=checkpoint,
        project_authorizer=SimpleNamespace(require=AsyncMock()),
    )
    trust_check = AsyncMock()
    monkeypatch.setattr(uc, "_require_trust_ready", trust_check)
    acquired = AsyncMock(side_effect=AssertionError("a blocked approval must not acquire a resume operation"))
    monkeypatch.setattr(module, "acquire", acquired)

    with pytest.raises(module.N4CoverageGapsError):
        await uc.execute(
            review_id,
            ResumeWorkflowRequest(
                decision=WorkflowDecision.APPROVE, feedback="", approved_by="Ana",
                decider=AuthorizedFinalDecider(tenant_id=TENANT, user_id=uuid4(), display_name="Ana"),
            ),
        )
    trust_check.assert_awaited_once()
    acquired.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["resume", "approve"])
async def test_a15_final_approval_routes_return_stable_409_without_resume(route: str) -> None:
    from unittest.mock import AsyncMock

    from src.modules.hitl.application import resume_workflow_use_case as module

    review_id = uuid4()
    spy = _SpyUseCase()

    async def blocked_execute(review_id: UUID, request: ResumeWorkflowRequest) -> ResumeWorkflowResponse:
        spy.requests.append(request)
        raise module.N4CoverageGapsError(pending_windows=1)

    spy.execute = blocked_execute  # type: ignore[method-assign]
    app = _app(_user(), TENANT, spy)
    if route == "approve":
        review = SimpleNamespace(
            item_id=review_id, metadata={"thread_id": "synthetic-thread", "row_id": str(review_id)},
        )
        app.dependency_overrides[get_hitl_service] = lambda: SimpleNamespace(
            review_queue_repo=SimpleNamespace(get_review_item=AsyncMock(return_value=review))
        )
        endpoint, body = f"/api/v1/hitl/queue/{review_id}/approve", {}
    else:
        endpoint, body = f"/api/v1/hitl/resume/{review_id}", {"decision": "approve", "feedback": "fine"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        result = await client.post(endpoint, json=body, headers=_HEADERS)
    assert result.status_code == 409, result.text
    assert result.json()["detail"]["code"] == "n4_coverage_gaps"
    assert result.json()["detail"]["pending_windows"] == 1


def test_a15_explicit_incomplete_status_must_block_even_when_counters_appear_complete() -> None:
    from src.modules.hitl.application import resume_workflow_use_case as module

    coverage = _synthetic_n4_coverage(status="INCOMPLETE")
    coverage["examined_windows"] = coverage["total_windows"]
    coverage["gap_windows"] = []
    coverage["gaps"] = []
    with pytest.raises(module.N4CoverageGapsError):
        module.require_n4_coverage_ready(
            SimpleNamespace(metadata={"analysis_n4_coverage": coverage}, item_data={}), approve=True
        )


@pytest.mark.parametrize("missing", ["closed_reason", "closed_by", "closed_at"])
def test_a15_manual_closure_without_an_audit_field_is_not_a_valid_resolution(missing: str) -> None:
    from src.modules.hitl.application import resume_workflow_use_case as module

    coverage = _synthetic_n4_coverage(resolution="CLOSED_MANUALLY")
    del coverage["gaps"][0][missing]
    with pytest.raises(module.N4CoverageGapsError):
        module.require_n4_coverage_ready(
            SimpleNamespace(metadata={"analysis_n4_coverage": coverage}, item_data={}), approve=True
        )


# JV1-A15 coverage hardening: exercise distinct fail-closed branches, never
# weaken existing assertions or rely on private contract fixtures.
@pytest.mark.parametrize(
    "broken",
    [
        pytest.param({"status": "UNKNOWN"}, id="unknown-status"),
        pytest.param({"run_id": ""}, id="missing-run"),
        pytest.param({"source_sha256": None}, id="missing-source"),
        pytest.param({"total_windows": 0}, id="zero-windows"),
        pytest.param({"total_windows": True}, id="boolean-total"),
        pytest.param({"examined_windows": -1}, id="negative-examined"),
        pytest.param({"examined_windows": 4}, id="overexamined"),
        pytest.param({"gap_windows": None}, id="non-list-ordinals"),
        pytest.param({"gaps": "invalid"}, id="non-list-gaps"),
        pytest.param({"gap_windows": [True]}, id="boolean-ordinal"),
        pytest.param({"gap_windows": [4]}, id="out-of-range-ordinal"),
        pytest.param({"gaps": [None]}, id="non-record-gap"),
        pytest.param({"gaps": [{"ordinal": 4, "resolution": "OPEN"}]}, id="out-of-range-gap"),
        pytest.param({"gaps": [{"ordinal": 2, "resolution": "INVALID"}]}, id="unknown-resolution"),
    ],
)
def test_a15_approval_fails_closed_on_each_malformed_coverage_shape(broken: dict[str, Any]) -> None:
    from src.modules.hitl.application import resume_workflow_use_case as module

    coverage = _synthetic_n4_coverage(resolution="CLOSED_MANUALLY")
    coverage.update(broken)
    review = SimpleNamespace(metadata={"analysis_n4_coverage": coverage}, item_data={})
    with pytest.raises(module.N4CoverageGapsError):
        module.require_n4_coverage_ready(review, approve=True)


def test_a15_open_resolution_wins_over_duplicate_manual_closure() -> None:
    from src.modules.hitl.application import resume_workflow_use_case as module

    coverage = _synthetic_n4_coverage(resolution="CLOSED_MANUALLY")
    coverage["gaps"].append({"ordinal": 2, "resolution": "OPEN"})
    with pytest.raises(module.N4CoverageGapsError) as blocked:
        module.require_n4_coverage_ready(
            SimpleNamespace(metadata={"analysis_n4_coverage": coverage}, item_data={}), approve=True
        )
    assert blocked.value.pending_windows == 1


def test_a15_same_identity_but_conflicting_projections_must_not_hide_open_gap() -> None:
    from src.modules.hitl.application import resume_workflow_use_case as module

    closed = _synthetic_n4_coverage(resolution="CLOSED_MANUALLY")
    opened = _synthetic_n4_coverage()
    opened["run_id"] = closed["run_id"]
    opened["source_sha256"] = closed["source_sha256"]
    with pytest.raises(module.N4CoverageGapsError) as blocked:
        module.require_n4_coverage_ready(
            SimpleNamespace(metadata={"analysis_n4_coverage": closed}, item_data={"n4_coverage": opened}),
            approve=True,
        )
    assert blocked.value.pending_windows == 1


def test_a15_nonmapping_second_projection_cannot_hide_valid_first_projection() -> None:
    from src.modules.hitl.application import resume_workflow_use_case as module

    coverage = _synthetic_n4_coverage(resolution="CLOSED_MANUALLY")
    with pytest.raises(module.N4CoverageGapsError):
        module.require_n4_coverage_ready(
            SimpleNamespace(metadata={"analysis_n4_coverage": coverage}, item_data={"n4_coverage": "bad"}),
            approve=True,
        )


def test_a15_manual_closure_not_in_original_gap_ledger_cannot_mark_incomplete_run_as_ready() -> None:
    from src.modules.hitl.application import resume_workflow_use_case as module

    coverage = _synthetic_n4_coverage(resolution="CLOSED_MANUALLY")
    coverage["gap_windows"] = []
    # A16 must close an *original* failed window; an unrelated closure
    # cannot reduce the missing-count derived from total versus examined.
    with pytest.raises(module.N4CoverageGapsError):
        module.require_n4_coverage_ready(
            SimpleNamespace(metadata={"analysis_n4_coverage": coverage}, item_data={}), approve=True
        )


@pytest.mark.asyncio
async def test_a15_legacy_approval_route_refuses_open_gap_before_service_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    review_id = uuid4()
    review = SimpleNamespace(
        item_id=review_id,
        metadata={"analysis_n4_coverage": _synthetic_n4_coverage()},
        item_data={},
    )
    service = SimpleNamespace(
        review_queue_repo=SimpleNamespace(get_review_item=AsyncMock(return_value=review)),
        approve_item=AsyncMock(side_effect=AssertionError("legacy approval must not mutate state")),
    )
    authorizer = AsyncMock()
    monkeypatch.setattr(hitl_router, "_require_project_approval_for_legacy_row", authorizer)
    app = _app(_user(), TENANT, _SpyUseCase())
    app.dependency_overrides[get_hitl_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/hitl/queue/{review_id}/approve", json={}, headers=_HEADERS)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "n4_coverage_gaps"
    assert response.json()["detail"]["pending_windows"] == 1
    authorizer.assert_awaited_once()
    service.approve_item.assert_not_awaited()
