"""Unit coverage for the P0-E historical RISK-alert dry-run planner."""

from __future__ import annotations

import copy
import inspect
from dataclasses import replace
from uuid import UUID, uuid4

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
    plan_historical_risk_alert_reconciliation,
)


def _ids() -> dict[str, UUID]:
    return {
        "tenant": uuid4(),
        "project": uuid4(),
        "document": uuid4(),
        "revision": uuid4(),
        "artifact": uuid4(),
        "analysis": uuid4(),
    }


def _risk(
    title: str,
    *,
    severity: str,
    clause_ref: str,
    source: str,
    quote: str,
) -> dict[str, object]:
    return {
        "title": title,
        "description": f"{title} description",
        "category": "LEGAL",
        "severity": severity,
        "clause_ref": clause_ref,
        "source": source,
        "source_quote": quote,
        "source_quote_status": "VERIFIED",
    }


def _artifact(ids: dict[str, UUID]) -> TrustedArtifactSnapshot:
    return TrustedArtifactSnapshot(
        tenant_id=ids["tenant"],
        project_id=ids["project"],
        document_id=ids["document"],
        revision_id=ids["revision"],
        artifact_id=ids["artifact"],
        artifact_hash="a" * 64,
        trusted_evidence_hash="a" * 64,
        trusted_evidence_verified=True,
        is_trusted_active=True,
    )


def _alert(
    ids: dict[str, UUID],
    risk: dict[str, object],
    *,
    severity: str = "LOW",
) -> HistoricalAlertSnapshot:
    return HistoricalAlertSnapshot(
        alert_id=uuid4(),
        tenant_id=ids["tenant"],
        project_id=ids["project"],
        analysis_id=ids["analysis"],
        severity=severity,
        source_clause_id=None,
        affected_document_ids=(),
        alert_metadata={"raw": risk},
        status="open",
        approval_status="pending",
        reviewed_by=None,
        reviewed_at=None,
        review_comment=None,
        resolved_at=None,
        resolved_by=None,
        resolution_notes=None,
    )


def _input(
    ids: dict[str, UUID],
    risks: tuple[dict[str, object], ...],
    alerts: tuple[HistoricalAlertSnapshot, ...],
) -> ReconciliationInput:
    analysis = HistoricalAnalysisSnapshot(
        analysis_id=ids["analysis"],
        tenant_id=ids["tenant"],
        project_id=ids["project"],
        document_id=ids["document"],
        revision_id=ids["revision"],
        source_artifact_id=ids["artifact"],
        alerts=alerts,
    )
    return ReconciliationInput(_artifact(ids), risks, (analysis,))


def test_three_alerts_tagged_to_v2_are_matched_by_raw_identity_not_artifact_id() -> None:
    ids = _ids()
    penalty = _risk(
        "Delay Penalties for Unapproved Late Completion §8.3",
        severity="CRITICAL",
        clause_ref="8.3",
        source="Late completion without written approval attracts penalties.",
        quote="Late completion without written approval attracts penalties.",
    )
    deadline = _risk(
        "Hard Contractual Completion Deadline §8.2",
        severity="HIGH",
        clause_ref="8.2",
        source="Completion is required by the contractual deadline.",
        quote="Completion is required by the contractual deadline.",
    )
    dismissed = _risk(
        "Written Approval Requirement for Schedule Changes §8.3",
        severity="HIGH",
        clause_ref="8.3",
        source="Schedule changes require written approval.",
        quote="Schedule changes require written approval.",
    )

    plan = plan_historical_risk_alert_reconciliation(
        _input(ids, (penalty, deadline), (_alert(ids, penalty), _alert(ids, deadline), _alert(ids, dismissed)))
    )

    assert plan.status == PlanStatus.READY
    assert [item.match_status for item in plan.items].count(MatchStatus.EXACT_APPROVED_RISK) == 2
    retained = [item for item in plan.items if item.match_status == MatchStatus.EXACT_APPROVED_RISK]
    assert {item.advisory_diff.approved_severity for item in retained} == {"HIGH", "CRITICAL"}
    assert all(item.advisory_diff.proposed_severity_correction for item in retained)
    assert all(item.advisory_diff.proposed_source_clause_id is None for item in retained)
    [old_risk] = [item for item in plan.items if item.match_status != MatchStatus.EXACT_APPROVED_RISK]
    assert old_risk.match_status == MatchStatus.NOT_PRESENT_IN_APPROVED_ARTIFACT
    assert old_risk.recommendation == Recommendation.REQUIRES_OPERATOR_REVIEW


def test_not_present_risk_is_never_auto_superseded_or_resolved() -> None:
    ids = _ids()
    approved = _risk("Approved", severity="HIGH", clause_ref="8.2", source="Source", quote="Quote")
    old = _risk("Old", severity="HIGH", clause_ref="8.3", source="Other", quote="Other quote")

    [item] = plan_historical_risk_alert_reconciliation(_input(ids, (approved,), (_alert(ids, old),))).items

    assert item.match_status == MatchStatus.NOT_PRESENT_IN_APPROVED_ARTIFACT
    assert item.recommendation == Recommendation.REQUIRES_OPERATOR_REVIEW
    assert "do not supersede" in item.reason.lower()
    assert item.human_review.status == "open"


def test_same_title_with_conflicting_source_or_quote_does_not_match() -> None:
    ids = _ids()
    approved = _risk("Same title", severity="HIGH", clause_ref="8.2", source="Approved source", quote="Approved quote")
    historical = _risk("Same title", severity="HIGH", clause_ref="8.2", source="Old source", quote="Old quote")

    [item] = plan_historical_risk_alert_reconciliation(_input(ids, (approved,), (_alert(ids, historical),))).items

    assert item.match_status == MatchStatus.NOT_PRESENT_IN_APPROVED_ARTIFACT


def test_duplicate_approved_risk_identity_is_ambiguous_and_fails_closed() -> None:
    ids = _ids()
    risk = _risk("Duplicate", severity="HIGH", clause_ref="8.2", source="Source", quote="Quote")

    [item] = plan_historical_risk_alert_reconciliation(_input(ids, (risk, dict(risk)), (_alert(ids, risk),))).items

    assert item.match_status == MatchStatus.AMBIGUOUS
    assert item.recommendation == Recommendation.REQUIRES_OPERATOR_REVIEW


@pytest.mark.parametrize("foreign_field", ["tenant", "project", "revision"])
def test_foreign_analysis_scope_or_revision_blocks_plan(foreign_field: str) -> None:
    ids = _ids()
    risk = _risk("Approved", severity="HIGH", clause_ref="8.2", source="Source", quote="Quote")
    input_data = _input(ids, (risk,), (_alert(ids, risk),))
    analysis = input_data.historical_analyses[0]
    replacement = uuid4()
    if foreign_field == "tenant":
        analysis = replace(analysis, tenant_id=replacement)
    elif foreign_field == "project":
        analysis = replace(analysis, project_id=replacement)
    else:
        analysis = replace(analysis, revision_id=replacement)

    plan = plan_historical_risk_alert_reconciliation(replace(input_data, historical_analyses=(analysis,)))

    assert plan.status == PlanStatus.PLAN_BLOCKED
    assert "ANALYSIS_SCOPE_OR_REVISION_MISMATCH" in plan.blocked_reasons
    assert plan.items == ()


@pytest.mark.parametrize(
    ("artifact_change", "reason"),
    [
        ({"is_trusted_active": False}, "ARTIFACT_NOT_TRUSTED_ACTIVE"),
        ({"artifact_hash": None}, "ARTIFACT_HASH_MISSING"),
        ({"trusted_evidence_verified": False}, "TRUSTED_EVIDENCE_NOT_EXPLICITLY_VERIFIED"),
    ],
)
def test_stale_or_unverified_artifact_evidence_blocks_plan(
    artifact_change: dict[str, object], reason: str
) -> None:
    ids = _ids()
    risk = _risk("Approved", severity="HIGH", clause_ref="8.2", source="Source", quote="Quote")
    input_data = _input(ids, (risk,), (_alert(ids, risk),))

    plan = plan_historical_risk_alert_reconciliation(
        replace(input_data, approved_artifact=replace(input_data.approved_artifact, **artifact_change))
    )

    assert plan.status == PlanStatus.PLAN_BLOCKED
    assert reason in plan.blocked_reasons


def test_plan_does_not_mutate_human_review_fields_and_never_verifies_missing_source() -> None:
    ids = _ids()
    risk = _risk("Approved", severity="CRITICAL", clause_ref="8.2", source="", quote="")
    risk["source_quote_status"] = None
    alert = replace(
        _alert(ids, risk),
        status="resolved",
        approval_status="approved",
        reviewed_by=uuid4(),
        reviewed_at="2026-11-07T00:00:00Z",
        review_comment="Human review",
        resolved_at="2026-11-07T01:00:00Z",
        resolved_by=uuid4(),
        resolution_notes="Do not change",
    )
    input_data = _input(ids, (risk,), (alert,))
    before = copy.deepcopy(input_data)

    [item] = plan_historical_risk_alert_reconciliation(input_data).items

    assert input_data == before
    assert item.human_review.review_comment == "Human review"
    assert item.advisory_diff.proposed_source_clause_id is None
    assert item.advisory_diff.source_verification_status == SourceVerificationStatus.NOT_VERIFIED


def test_plan_id_is_deterministic_when_input_collections_are_reordered() -> None:
    ids = _ids()
    first = _risk("First", severity="CRITICAL", clause_ref="8.2", source="A", quote="A")
    second = _risk("Second", severity="HIGH", clause_ref="8.3", source="B", quote="B")
    alert_one, alert_two = _alert(ids, first), _alert(ids, second)
    ordered = _input(ids, (first, second), (alert_one, alert_two))
    reversed_input = replace(
        ordered,
        v2_extracted_risks=(second, first),
        historical_analyses=(replace(ordered.historical_analyses[0], alerts=(alert_two, alert_one)),),
    )

    first_plan = plan_historical_risk_alert_reconciliation(ordered)
    second_plan = plan_historical_risk_alert_reconciliation(reversed_input)

    assert first_plan.plan_id == second_plan.plan_id
    assert first_plan.source_snapshot_digest == second_plan.source_snapshot_digest


def test_planner_has_no_database_import_or_write_api() -> None:
    source = inspect.getsource(planner)

    assert "sqlalchemy" not in source
    assert "src.core.database" not in source
    assert "def apply" not in source
    assert "async def" not in source
