"""PQ-HITL-04C3: only authenticated tenant humans can submit provisional intents."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.core.auth.models import UserRole
from src.modules.hitl.application.finding_review_authorization import (
    FindingDecisionSubmission,
    FindingReviewerNotAuthorized,
    authorize_finding_reviewer,
)


def _user(tenant, role=UserRole.USER, active=True):
    return SimpleNamespace(id=uuid4(), tenant_id=tenant, role=role, is_active=active)


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.USER])
def test_authenticated_active_human_tenant_role_allowed(role):
    tenant = uuid4()
    user = _user(tenant, role)
    actor = authorize_finding_reviewer(user, tenant_id=tenant)
    assert actor.tenant_id == tenant
    assert actor.reviewer_id == user.id


@pytest.mark.parametrize("role", [UserRole.VIEWER, UserRole.API])
def test_read_only_and_api_principals_cannot_create_human_decisions(role):
    tenant = uuid4()
    with pytest.raises(FindingReviewerNotAuthorized):
        authorize_finding_reviewer(_user(tenant, role), tenant_id=tenant)


def test_wrong_tenant_disabled_or_missing_user_fails_before_any_database_access():
    tenant = uuid4()
    for u in (
        _user(uuid4()),
        _user(tenant, active=False),
        SimpleNamespace(id=None, tenant_id=tenant, role=UserRole.USER, is_active=True),
        None,
    ):
        with pytest.raises(FindingReviewerNotAuthorized):
            authorize_finding_reviewer(u, tenant_id=tenant)


def _submission():
    return {
        "artifact_id": uuid4(),
        "artifact_version": 2,
        "artifact_hash": "a" * 64,
        "document_revision_id": uuid4(),
        "generation": 3,
        "fencing_token": 10,
        "source_item_id": "risk-sha256:" + "b" * 64,
        "ordinal": 0,
        "action": "CONFIRMED",
        "expected_ledger_revision": 0,
        "idempotency_key": "review-click-123456",
    }


def test_client_payload_never_accepts_reviewer_or_tenant_identity():
    data = _submission()
    for key, value in (("tenant_id", uuid4()), ("reviewer_id", str(uuid4())), ("review_row_id", uuid4())):
        with pytest.raises(ValidationError):
            FindingDecisionSubmission.model_validate({**data, key: value})


@pytest.mark.parametrize(
    "extra",
    [
        {"artifact_hash": "not-a-hash"},
        {"artifact_version": 0},
        {"ordinal": -1},
        {"generation": -1},
        {"fencing_token": -1},
        {"idempotency_key": "short"},
    ],
)
def test_client_requires_exact_candidate_and_stable_retry_key(extra):
    with pytest.raises(ValidationError):
        FindingDecisionSubmission.model_validate({**_submission(), **extra})


def test_proposed_correction_must_carry_reason_and_new_text():
    data = _submission()
    with pytest.raises(ValidationError):
        FindingDecisionSubmission.model_validate({**data, "action": "CORRECTION_PROPOSED"})
    validated = FindingDecisionSubmission.model_validate(
        {**data, "action": "CORRECTION_PROPOSED", "reason": "unsupported clause",
         "proposed_text": "request revised contractual wording"}
    )
    assert validated.action.value == "CORRECTION_PROPOSED"
    with pytest.raises(ValidationError):
        FindingDecisionSubmission.model_validate(
            {**data, "action": "CONFIRMED", "proposed_text": "silent alteration"}
        )
