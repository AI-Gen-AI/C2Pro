"""Focused fail-closed tests for structured reconciliation review authority."""
from __future__ import annotations

import pytest

from core.reconciler import ValidationError, _validate_reconciliation_reviews
from core.result_parser import validate_review_result

HEAD = "7c3a8347a5bea0c28f2e540559bd515f9afd282a"
WORK_ID = "C2PRO-DEV-02"
PR = 597


def _routing() -> dict:
    return {
        "workers": {
            "claude_code": {
                "principal_gate_eligible": True,
                "eligible_roles": [
                    "implementation_lead",
                    "independent_reviewer",
                    "specialist",
                ],
            },
            "codex": {
                "principal_gate_eligible": True,
                "eligible_roles": [
                    "implementation_lead",
                    "independent_reviewer",
                    "specialist",
                ],
            },
            "gemini_cli": {
                "principal_gate_eligible": False,
                "eligible_roles": ["qa", "specialist"],
            },
        },
        "principal_gate": {
            "eligible_workers": ["claude_code", "codex"],
            "material_reviewer_must_differ_from_implementation_worker": True,
            "same_worker_dual_role_does_not_satisfy_independence": True,
        },
    }


def _review(*, role: str, worker_id: str, verdict: str = "PASS") -> dict:
    return {
        "schema": "c2pro-review-result-v1",
        "schema_version": 1,
        "work_id": WORK_ID,
        "role": role,
        "worker_id": worker_id,
        "reviewed_pr": PR,
        "reviewed_head_sha": HEAD,
        "verdict": verdict,
        "blocking": [],
        "non_blocking": [],
        "architecture_drift": False,
        "security_concern": False,
        "scope_deviation": False,
        "recommended_action": "approve",
    }


def test_principal_and_challenger_policy_accepts_trusted_independent_workers() -> None:
    _validate_reconciliation_reviews(
        [
            _review(role="independent_reviewer", worker_id="codex"),
            _review(role="specialist", worker_id="gemini_cli"),
        ],
        review_policy="principal_and_challenger",
        work_id=WORK_ID,
        expected_pr=PR,
        expected_head_sha=HEAD,
        implementation_worker_id="claude_code",
        routing=_routing(),
    )


def test_mandatory_review_policy_rejects_absent_review_evidence() -> None:
    with pytest.raises(ValidationError, match="requires structured review evidence"):
        _validate_reconciliation_reviews(
            None,
            review_policy="independent_principal",
            work_id=WORK_ID,
            expected_pr=PR,
            expected_head_sha=HEAD,
            implementation_worker_id="claude_code",
            routing=_routing(),
        )


def test_principal_reviewer_cannot_be_the_implementation_worker() -> None:
    with pytest.raises(ValidationError, match="must differ from implementation worker"):
        _validate_reconciliation_reviews(
            [_review(role="independent_reviewer", worker_id="claude_code")],
            review_policy="independent_principal",
            work_id=WORK_ID,
            expected_pr=PR,
            expected_head_sha=HEAD,
            implementation_worker_id="claude_code",
            routing=_routing(),
        )


def test_subordinate_cannot_self_declare_independent_principal_role() -> None:
    review = _review(role="independent_reviewer", worker_id="gemini_cli")
    with pytest.raises(ValidationError, match="not eligible for role"):
        _validate_reconciliation_reviews(
            [review],
            review_policy="independent_principal",
            work_id=WORK_ID,
            expected_pr=PR,
            expected_head_sha=HEAD,
            implementation_worker_id="claude_code",
            routing=_routing(),
        )


def test_unknown_implementation_worker_fails_closed() -> None:
    with pytest.raises(ValidationError, match="implementation_worker_id"):
        _validate_reconciliation_reviews(
            [_review(role="independent_reviewer", worker_id="codex")],
            review_policy="independent_principal",
            work_id=WORK_ID,
            expected_pr=PR,
            expected_head_sha=HEAD,
            implementation_worker_id="unknown_worker",
            routing=_routing(),
        )


def test_review_schema_is_complete_without_jsonschema_dependency() -> None:
    malformed = _review(role="independent_reviewer", worker_id="codex")
    del malformed["blocking"]
    with pytest.raises(ValueError, match="missing required fields"):
        validate_review_result(
            malformed,
            expected_pr=PR,
            expected_head_sha=HEAD,
        )


def test_review_schema_rejects_extra_fields_and_wrong_boolean_types() -> None:
    extra = _review(role="independent_reviewer", worker_id="codex")
    extra["self_asserted_authority"] = True
    with pytest.raises(ValueError, match="unsupported fields"):
        validate_review_result(extra, expected_pr=PR, expected_head_sha=HEAD)

    wrong_type = _review(role="independent_reviewer", worker_id="codex")
    wrong_type["security_concern"] = "false"
    with pytest.raises(TypeError, match="security_concern must be boolean"):
        validate_review_result(
            wrong_type,
            expected_pr=PR,
            expected_head_sha=HEAD,
        )
