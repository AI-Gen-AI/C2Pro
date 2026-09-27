"""Focused fail-closed tests for structured reconciliation review authority."""
from __future__ import annotations

import pytest

from core.reconciler import (
    ValidationError,
    _load_work_review_requirements,
    _validate_reconciliation_reviews,
)
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
                    "orchestrator",
                    "implementation_lead",
                    "independent_reviewer",
                    "specialist",
                ],
            },
            "codex": {
                "principal_gate_eligible": True,
                "eligible_roles": [
                    "orchestrator",
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


def _synthesis(
    *,
    orchestrator_worker_id: str = "codex",
    principal_worker_ids: list[str] | None = None,
    challenger_worker_ids: list[str] | None = None,
) -> dict:
    return {
        "schema": "c2pro-orchestrator-synthesis-v1",
        "work_id": WORK_ID,
        "risk_class": "architecture",
        "reviewed_pr": PR,
        "reviewed_head_sha": HEAD,
        "orchestrator_worker_id": orchestrator_worker_id,
        "principal_worker_ids": principal_worker_ids or ["codex"],
        "challenger_worker_ids": challenger_worker_ids or ["gemini_cli"],
        "unresolved_material_disagreement": False,
        "decision": "approve",
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


def test_challenger_cannot_be_the_implementation_worker() -> None:
    with pytest.raises(ValidationError, match="challenger .* must differ from implementation worker"):
        _validate_reconciliation_reviews(
            [
                _review(role="independent_reviewer", worker_id="codex"),
                _review(role="specialist", worker_id="gemini_cli"),
            ],
            review_policy="principal_and_challenger",
            work_id=WORK_ID,
            expected_pr=PR,
            expected_head_sha=HEAD,
            implementation_worker_id="gemini_cli",
            routing=_routing(),
        )


def test_high_risk_review_requires_bound_orchestrator_synthesis() -> None:
    reviews = [
        _review(role="independent_reviewer", worker_id="codex"),
        _review(role="specialist", worker_id="gemini_cli"),
    ]

    with pytest.raises(ValidationError, match="requires orchestrator synthesis evidence"):
        _validate_reconciliation_reviews(
            reviews,
            review_policy="principal_and_challenger",
            work_id=WORK_ID,
            expected_pr=PR,
            expected_head_sha=HEAD,
            implementation_worker_id="claude_code",
            routing=_routing(),
            risk_class="architecture",
            orchestrator_synthesis_required=True,
        )

    _validate_reconciliation_reviews(
        reviews,
        review_policy="principal_and_challenger",
        work_id=WORK_ID,
        expected_pr=PR,
        expected_head_sha=HEAD,
        implementation_worker_id="claude_code",
        routing=_routing(),
        risk_class="architecture",
        orchestrator_synthesis_required=True,
        orchestrator_synthesis=_synthesis(),
    )


def test_orchestrator_synthesis_cannot_be_approved_by_implementation_worker() -> None:
    reviews = [
        _review(role="independent_reviewer", worker_id="codex"),
        _review(role="specialist", worker_id="gemini_cli"),
    ]
    with pytest.raises(
        ValidationError,
        match="synthesis worker must differ from implementation worker",
    ):
        _validate_reconciliation_reviews(
            reviews,
            review_policy="principal_and_challenger",
            work_id=WORK_ID,
            expected_pr=PR,
            expected_head_sha=HEAD,
            implementation_worker_id="claude_code",
            routing=_routing(),
            risk_class="architecture",
            orchestrator_synthesis_required=True,
            orchestrator_synthesis=_synthesis(orchestrator_worker_id="claude_code"),
        )


def test_orchestrator_synthesis_is_bound_to_exact_review_workers_and_head() -> None:
    reviews = [
        _review(role="independent_reviewer", worker_id="codex"),
        _review(role="specialist", worker_id="gemini_cli"),
    ]
    stale = _synthesis()
    stale["reviewed_head_sha"] = "9" * 40
    with pytest.raises(ValidationError, match="reviewed_head_sha mismatch"):
        _validate_reconciliation_reviews(
            reviews,
            review_policy="principal_and_challenger",
            work_id=WORK_ID,
            expected_pr=PR,
            expected_head_sha=HEAD,
            implementation_worker_id="claude_code",
            routing=_routing(),
            risk_class="architecture",
            orchestrator_synthesis_required=True,
            orchestrator_synthesis=stale,
        )


def test_canonical_work_envelope_drives_high_risk_synthesis_policy(tmp_path) -> None:
    c2pro = tmp_path / ".c2pro"
    control = c2pro / "control"
    work = c2pro / "work"
    control.mkdir(parents=True)
    work.mkdir(parents=True)

    (work / f"{WORK_ID}.yaml").write_text(
        "\n".join(
            (
                "schema: c2pro-work-envelope-v1",
                "schema_version: 1",
                f"work_id: {WORK_ID}",
                "risk_class: architecture",
                "review_policy: principal_and_challenger",
                "",
            )
        ),
        encoding="utf-8",
    )
    (control / "review-policy.yaml").write_text(
        "\n".join(
            (
                "schema: c2pro-review-policy-v1",
                "schema_version: 1",
                "risk_classes:",
                "  architecture:",
                "    independent_principal_review: required",
                "    challenger: required",
                "    orchestrator_synthesis: true",
                "",
            )
        ),
        encoding="utf-8",
    )
    risk_class, synthesis_required = _load_work_review_requirements(
        control,
        {
            "work_id": WORK_ID,
            "work_ref": f".c2pro/work/{WORK_ID}.yaml",
            "review_policy": "principal_and_challenger",
        },
    )

    assert risk_class == "architecture"
    assert synthesis_required is True


def test_risk_policy_cannot_be_downgraded_to_optional_review(tmp_path) -> None:
    c2pro = tmp_path / ".c2pro"
    control = c2pro / "control"
    work = c2pro / "work"
    control.mkdir(parents=True)
    work.mkdir(parents=True)
    (work / f"{WORK_ID}.yaml").write_text(
        "\n".join(
            (
                "schema: c2pro-work-envelope-v1",
                "schema_version: 1",
                f"work_id: {WORK_ID}",
                "risk_class: architecture",
                "review_policy: optional",
                "",
            )
        ),
        encoding="utf-8",
    )
    (control / "review-policy.yaml").write_text(
        "\n".join(
            (
                "schema: c2pro-review-policy-v1",
                "schema_version: 1",
                "risk_classes:",
                "  architecture:",
                "    independent_principal_review: required",
                "    challenger: required",
                "    orchestrator_synthesis: true",
                "",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="requires independent principal review"):
        _load_work_review_requirements(
            control,
            {
                "work_id": WORK_ID,
                "work_ref": f".c2pro/work/{WORK_ID}.yaml",
                "review_policy": "optional",
            },
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
