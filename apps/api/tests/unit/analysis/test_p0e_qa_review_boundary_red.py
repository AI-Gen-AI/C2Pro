"""QA RED regressions from independent P0-E review; no production mutations.

Expected initial outcome on fd75fb05b: failures are intentional until Codex rework.
Keep these tests in the isolated QA branch and cherry-pick only after author review.
"""
from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from src.analysis.application.historical_risk_alert_reconciliation import (
    HistoricalAlertSnapshot,
    HistoricalAnalysisSnapshot,
    MatchStatus,
    PlanStatus,
    Recommendation,
    ReconciliationInput,
    TrustedArtifactSnapshot,
    plan_historical_risk_alert_reconciliation,
)


def _fixture(*, risks=1, alerts=1, quote_verified=True):
    tenant_id, project_id, document_id, revision_id, artifact_id, analysis_id = (uuid4() for _ in range(6))
    risk = {
        "title": "Hard contractual completion deadline",
        "description": "Completion date stated by contract",
        "category": "LEGAL",
        "severity": "HIGH",
        "clause_ref": "8.2",
        "source": "Clause 8.2 Completion",
        "source_quote": "The completion date is 30 June.",
        "source_quote_status": "VERIFIED",
    }
    if not quote_verified:
        risk = {**risk, "source_quote": "", "source_quote_status": "NOT_VERIFIED"}
    historical_alerts = tuple(
        HistoricalAlertSnapshot(
            alert_id=uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            analysis_id=analysis_id,
            severity="LOW",
            source_clause_id=None,
            affected_document_ids=(),
            alert_metadata={"raw": dict(risk)},
            status="open",
            approval_status="pending",
            reviewed_by=None,
            reviewed_at=None,
            review_comment=None,
            resolved_at=None,
            resolved_by=None,
            resolution_notes=None,
        )
        for _ in range(alerts)
    )
    analysis = HistoricalAnalysisSnapshot(
        analysis_id=analysis_id,
        tenant_id=tenant_id,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        source_artifact_id=artifact_id,
        alerts=historical_alerts,
    )
    artifact = TrustedArtifactSnapshot(
        tenant_id=tenant_id,
        project_id=project_id,
        document_id=document_id,
        revision_id=revision_id,
        artifact_id=artifact_id,
        artifact_hash="a" * 64,
        trusted_evidence_hash="a" * 64,
        trusted_evidence_verified=True,
        is_trusted_active=True,
    )
    return ReconciliationInput(
        approved_artifact=artifact,
        v2_extracted_risks=tuple(dict(risk) for _ in range(risks)),
        historical_analyses=(analysis,),
    )


def test_p0e_no_historical_analyses_must_not_report_ready_empty() -> None:
    data = _fixture()
    plan = plan_historical_risk_alert_reconciliation(replace(data, historical_analyses=()))
    assert plan.status == PlanStatus.PLAN_BLOCKED
    assert plan.items == ()


def test_p0e_empty_approved_risk_list_must_not_recommend_excluding_every_alert() -> None:
    plan = plan_historical_risk_alert_reconciliation(_fixture(risks=0))
    assert plan.status == PlanStatus.PLAN_BLOCKED
    assert plan.items == ()


def test_p0e_unverified_source_quote_never_counts_as_verified_retain() -> None:
    plan = plan_historical_risk_alert_reconciliation(_fixture(quote_verified=False))
    assert plan.status == PlanStatus.READY
    assert len(plan.items) == 1
    item = plan.items[0]
    assert item.recommendation == Recommendation.REQUIRES_OPERATOR_REVIEW
    assert item.match_status != MatchStatus.EXACT_APPROVED_RISK


def test_p0e_multiple_historical_alerts_for_same_approved_risk_not_both_retain() -> None:
    plan = plan_historical_risk_alert_reconciliation(_fixture(alerts=2))
    assert plan.status == PlanStatus.READY
    assert len(plan.items) == 2
    assert all(item.recommendation == Recommendation.REQUIRES_OPERATOR_REVIEW for item in plan.items)
