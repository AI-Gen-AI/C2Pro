"""Focused contract tests for the pure historical RISK-alert planner."""

from __future__ import annotations

import copy
import inspect
import json
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

import pytest

from src.analysis.application import historical_risk_alert_reconciliation as planner
from src.analysis.application.historical_risk_alert_reconciliation import (
    HistoricalAlertSnapshot,
    HistoricalAnalysisSnapshot,
    MatchStatus,
    PlanStatus,
    Recommendation,
    ReconciliationInput,
    SourceVerificationStatus,
    TrustedArtifactSnapshot,
    WriteAuthority,
    plan_historical_risk_alert_reconciliation,
)
from src.analysis.domain.contracts import DocumentArtifact


def _ids() -> dict[str, UUID]:
    return {
        key: UUID(f"00000000-0000-0000-0000-0000000000{value:02d}")
        for key, value in {
            "tenant": 1,
            "project": 2,
            "document": 3,
            "revision": 4,
            "artifact": 5,
            "analysis": 6,
            "one": 7,
            "two": 8,
            "three": 9,
            "reviewer": 10,
        }.items()
    }


def _risk(title: str, severity: str = "HIGH", **overrides: object) -> dict[str, object]:
    return {
        "title": title,
        "description": f"{title} description",
        "category": "LEGAL",
        "severity": severity,
        "clause_ref": "8.2",
        "source": "original contract text",
        "source_quote": "original contract text",
        "source_quote_status": "VERIFIED",
        **overrides,
    }


def _payload(risks: tuple[dict[str, object], ...], ids: dict[str, UUID]) -> bytes:
    artifact = DocumentArtifact(
        document_id=str(ids["document"]),
        document_revision_id=str(ids["revision"]),
        doc_type="CONTRACT",
        extracted_risks=list(risks),
    )
    persisted = artifact.model_dump(mode="json")
    # Same two optional-field exclusions as real DocumentArtifactRepository._insert.
    if persisted.get("structured_source") is None:
        persisted.pop("structured_source", None)
    if persisted.get("decision_snapshot") is None:
        persisted.pop("decision_snapshot", None)
    return json.dumps(persisted, sort_keys=True, separators=(",", ":"), default=str).encode()


def _artifact(
    ids: dict[str, UUID], risks: tuple[dict[str, object], ...]
) -> TrustedArtifactSnapshot:
    payload = _payload(risks, ids)
    return TrustedArtifactSnapshot(
        ids["tenant"],
        ids["project"],
        ids["document"],
        ids["revision"],
        ids["artifact"],
        sha256(payload).hexdigest(),
        payload,
        True,
    )


def _alert(
    ids: dict[str, UUID], risk: dict[str, object], alert_id: UUID
) -> HistoricalAlertSnapshot:
    return HistoricalAlertSnapshot(
        alert_id,
        ids["tenant"],
        ids["project"],
        ids["analysis"],
        "LOW",
        "risk",
        None,
        (ids["document"],),
        {"raw": risk},
        "open",
        "pending",
        None,
        None,
        None,
        None,
        None,
        None,
    )


def _input(
    ids: dict[str, UUID],
    risks: tuple[dict[str, object], ...],
    alerts: tuple[HistoricalAlertSnapshot, ...],
) -> ReconciliationInput:
    analysis = HistoricalAnalysisSnapshot(
        ids["analysis"],
        ids["tenant"],
        ids["project"],
        ids["document"],
        ids["revision"],
        ids["artifact"],
        "risk",
        "completed",
        alerts,
    )
    return ReconciliationInput(_artifact(ids, risks), risks, (analysis,))


def test_valid_v2_two_risks_retain_exact_and_preserve_dismissed() -> None:
    ids = _ids()
    first, second, old = _risk("Penalty", "CRITICAL"), _risk("Deadline"), _risk("V1 old")
    dismissed = replace(
        _alert(ids, old, ids["three"]),
        status="dismissed",
        approval_status="rejected",
        reviewed_by=ids["reviewer"],
        review_comment="Human rejected",
    )
    plan = plan_historical_risk_alert_reconciliation(
        _input(
            ids,
            (first, second),
            (_alert(ids, first, ids["one"]), _alert(ids, second, ids["two"]), dismissed),
        )
    )
    assert plan.status is PlanStatus.READY
    assert plan.advisory_only is True and plan.write_authority is WriteAuthority.NONE
    assert len(plan.scope_fingerprint) == 64
    assert [item.match_status for item in plan.items].count(MatchStatus.EXACT_APPROVED_RISK) == 2
    assert all(item.recommendation is Recommendation.RETAIN for item in plan.items[:2])
    assert plan.items[2].recommendation is Recommendation.REQUIRES_OPERATOR_REVIEW
    assert not plan.items[2].advisory_diff.proposed_severity_correction
    assert plan.items[2].human_review.review_comment == "Human rejected"


@pytest.mark.parametrize("tamper", ["list", "payload", "hash"])
def test_v2_risks_are_cryptographically_bound_to_exact_payload(tamper: str) -> None:
    ids = _ids()
    first, second = _risk("First"), _risk("Second")
    data = _input(ids, (first, second), (_alert(ids, first, ids["one"]),))
    if tamper == "list":
        data = replace(data, v2_extracted_risks=(first, _risk("Injected")))
        code = "V2_RISKS_NOT_BOUND_TO_ARTIFACT"
    elif tamper == "payload":
        data = replace(
            data,
            approved_artifact=replace(
                data.approved_artifact,
                trusted_artifact_payload=_payload((first, _risk("Injected")), ids),
            ),
        )
        code = "ARTIFACT_DIGEST_MISMATCH"
    else:
        data = replace(
            data, approved_artifact=replace(data.approved_artifact, artifact_hash="f" * 64)
        )
        code = "ARTIFACT_DIGEST_MISMATCH"
    plan = plan_historical_risk_alert_reconciliation(data)
    assert (
        plan.status is PlanStatus.PLAN_BLOCKED and code in plan.blocked_reasons and not plan.items
    )


@pytest.mark.parametrize("empty", ["risks", "analyses"])
def test_empty_evidence_blocks_instead_of_mass_excluding(empty: str) -> None:
    ids = _ids()
    risk = _risk("Approved")
    data = _input(ids, (risk,), (_alert(ids, risk, ids["one"]),))
    if empty == "risks":
        data = replace(data, v2_extracted_risks=(), approved_artifact=_artifact(ids, ()))
    else:
        data = replace(data, historical_analyses=())
    plan = plan_historical_risk_alert_reconciliation(data)
    assert (
        plan.status is PlanStatus.PLAN_BLOCKED
        and "NOT_ENOUGH_EVIDENCE" in plan.blocked_reasons
        and not plan.items
    )


@pytest.mark.parametrize(
    "change", [{"source_quote": ""}, {"source_quote_status": "UNVERIFIED"}, {"source": ""}]
)
def test_source_evidence_missing_or_unverified_never_retains(change: dict[str, object]) -> None:
    ids = _ids()
    risk = _risk("Approved")
    [item] = plan_historical_risk_alert_reconciliation(
        _input(ids, (risk,), (_alert(ids, _risk("Approved", **change), ids["one"]),))
    ).items
    assert item.match_status is MatchStatus.SOURCE_EVIDENCE_INSUFFICIENT
    assert item.recommendation is Recommendation.REQUIRES_OPERATOR_REVIEW
    assert item.advisory_diff.source_verification_status is SourceVerificationStatus.NOT_VERIFIED


def test_duplicate_historical_alerts_are_all_ambiguous() -> None:
    ids = _ids()
    risk = _risk("Approved")
    plan = plan_historical_risk_alert_reconciliation(
        _input(ids, (risk,), (_alert(ids, risk, ids["one"]), _alert(ids, risk, ids["two"])))
    )
    assert [item.match_status for item in plan.items] == [
        MatchStatus.AMBIGUOUS,
        MatchStatus.AMBIGUOUS,
    ]
    assert all(
        item.recommendation is Recommendation.REQUIRES_OPERATOR_REVIEW for item in plan.items
    )


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ("foreign_tenant", "ANALYSIS_SCOPE_OR_REVISION_MISMATCH"),
        ("foreign_revision", "ANALYSIS_SCOPE_OR_REVISION_MISMATCH"),
        ("v1", "ANALYSIS_ARTIFACT_PIN_MISMATCH"),
        ("status", "ANALYSIS_NOT_CANONICAL_RISK_COMPLETED"),
        ("alert_type", "ALERT_NOT_RISK"),
    ],
)
def test_scope_revision_canonical_status_and_risk_type_are_required(change: str, code: str) -> None:
    ids = _ids()
    risk = _risk("Approved")
    data = _input(ids, (risk,), (_alert(ids, risk, ids["one"]),))
    analysis = data.historical_analyses[0]
    foreign = UUID("00000000-0000-0000-0000-000000000099")
    if change == "foreign_tenant":
        analysis = replace(analysis, tenant_id=foreign)
    elif change == "foreign_revision":
        analysis = replace(analysis, revision_id=foreign)
    elif change == "v1":
        analysis = replace(analysis, source_artifact_id=foreign)
    elif change == "status":
        analysis = replace(analysis, status="running")
    else:
        analysis = replace(analysis, alerts=(replace(analysis.alerts[0], alert_type="coherence"),))
    plan = plan_historical_risk_alert_reconciliation(replace(data, historical_analyses=(analysis,)))
    assert plan.status is PlanStatus.PLAN_BLOCKED and code in plan.blocked_reasons


@pytest.mark.parametrize("unsafe", [Decimal("1"), datetime(2026, 1, 1), {"set"}, float("nan")])
def test_type_unsafe_input_blocks_without_raising(unsafe: object) -> None:
    ids = _ids()
    risk = _risk("Approved")
    alert = replace(_alert(ids, risk, ids["one"]), alert_metadata={"raw": risk, "unsafe": unsafe})
    plan = plan_historical_risk_alert_reconciliation(_input(ids, (risk,), (alert,)))
    assert (
        plan.status is PlanStatus.PLAN_BLOCKED and "INVALID_SNAPSHOT_VALUE" in plan.blocked_reasons
    )


def test_unknown_raw_fields_downgrade_and_input_is_not_mutated() -> None:
    ids = _ids()
    risk = _risk("Approved")
    data = _input(ids, (risk,), (_alert(ids, _risk("Approved", unexpected="x"), ids["one"]),))
    before = copy.deepcopy(data)
    [item] = plan_historical_risk_alert_reconciliation(data).items
    assert data == before and item.match_status is MatchStatus.UNMATCHABLE_RAW_PAYLOAD


def test_repeated_reordered_plan_is_deterministic() -> None:
    ids = _ids()
    first, second = _risk("First"), _risk("Second", "CRITICAL")
    data = _input(
        ids, (first, second), (_alert(ids, first, ids["one"]), _alert(ids, second, ids["two"]))
    )
    payload = _payload((second, first), ids)
    other = replace(
        data,
        v2_extracted_risks=(second, first),
        approved_artifact=replace(
            data.approved_artifact,
            trusted_artifact_payload=payload,
            artifact_hash=sha256(payload).hexdigest(),
        ),
        historical_analyses=(
            replace(
                data.historical_analyses[0],
                alerts=tuple(reversed(data.historical_analyses[0].alerts)),
            ),
        ),
    )
    first_plan, second_plan = (
        plan_historical_risk_alert_reconciliation(data),
        plan_historical_risk_alert_reconciliation(other),
    )
    assert first_plan.status is PlanStatus.READY
    assert second_plan.status is PlanStatus.READY
    assert first_plan.scope_fingerprint == second_plan.scope_fingerprint
    assert first_plan.source_snapshot_digest != second_plan.source_snapshot_digest
    assert sorted(item.match_status for item in first_plan.items) == sorted(
        item.match_status for item in second_plan.items
    )


def test_planner_has_no_database_import_or_write_api() -> None:
    source = inspect.getsource(planner)
    assert "sqlalchemy" not in source and "src.core.database" not in source
    assert "def apply" not in source and "async def" not in source


@pytest.mark.parametrize("identity_field", ["document_id", "revision_id"])
def test_hash_valid_but_wrong_artifact_document_revision_fails_closed(
    identity_field: str,
) -> None:
    """A valid SHA256 cannot authenticate a mismatched document or revision."""
    ids = _ids()
    risk = _risk("Approved")
    data = _input(ids, (risk,), (_alert(ids, risk, ids["one"]),))
    foreign = UUID("00000000-0000-0000-0000-000000000099")
    wrong_binding = replace(data.approved_artifact, **{identity_field: foreign})

    plan = plan_historical_risk_alert_reconciliation(replace(data, approved_artifact=wrong_binding))

    assert plan.status is PlanStatus.PLAN_BLOCKED
    assert "ARTIFACT_DOCUMENT_REVISION_MISMATCH" in plan.blocked_reasons
    assert not plan.items


def test_not_trusted_active_artifact_is_blocked_even_when_digest_matches() -> None:
    ids = _ids()
    risk = _risk("Approved")
    data = _input(ids, (risk,), (_alert(ids, risk, ids["one"]),))

    plan = plan_historical_risk_alert_reconciliation(
        replace(
            data,
            approved_artifact=replace(data.approved_artifact, is_trusted_active=False),
        )
    )

    assert plan.status is PlanStatus.PLAN_BLOCKED
    assert "ARTIFACT_NOT_TRUSTED_ACTIVE" in plan.blocked_reasons
    assert not plan.items


def test_one_historical_alert_against_two_identical_approved_risks_is_ambiguous() -> None:
    ids = _ids()
    risk = _risk("Approved")
    data = _input(ids, (risk, risk), (_alert(ids, risk, ids["one"]),))

    plan = plan_historical_risk_alert_reconciliation(data)

    assert plan.status is PlanStatus.READY
    assert len(plan.items) == 1
    assert plan.items[0].match_status is MatchStatus.AMBIGUOUS
    assert plan.items[0].recommendation is Recommendation.REQUIRES_OPERATOR_REVIEW
    assert plan.advisory_only and plan.write_authority is WriteAuthority.NONE
