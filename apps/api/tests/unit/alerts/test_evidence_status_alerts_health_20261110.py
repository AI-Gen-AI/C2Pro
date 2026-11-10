"""Self-contained synthetic tests for the evidence-status fixes (A: alerts, B/C: risk health)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.alerts.application.mappers.alert_mapper import AlertMapper
from src.alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from src.alerts.domain.models import Alert
from src.analysis.adapters.graph.review_source_references import (
    bind_risk_alert_source_references,
)
from src.analysis.domain.contracts import RiskItem, Severity
from src.coherence.alert_generator import AlertGenerator
from src.health.application.risk_scorer import score_risk_dimension
from src.project_state.domain.entities import ProjectRisk

DOC, REV, CLAUSE, PROJECT, TENANT = (uuid4() for _ in range(5))
REF = {"document_id": str(DOC), "revision_id": str(REV), "clause_id": str(CLAUSE), "clause_code": "2.5.4"}


def _response(quote_status: str | None):
    risk = {"title": "t", "description": "d", "category": "SCHEDULE", "impact": "HIGH",
            "clause_ref": "2.5.4"}
    if quote_status is not None:
        risk["source_quote_status"] = quote_status
    bound = bind_risk_alert_source_references([risk], [REF])
    dto = AlertGenerator(project_id=PROJECT, analysis_id=uuid4()).generate_risk_alerts(bound)[0]
    alert = Alert(
        id=uuid4(), project_id=PROJECT, severity=AlertSeverity(dto.severity.value),
        category=dto.category or "OTHER", status=list(AlertStatus)[0],
        approval_status=list(ApprovalStatus)[0], rule_id=None, title=dto.title,
        description=dto.description, alert_metadata=dto.alert_metadata,
        source_clause_id=dto.source_clause_id, created_at=datetime.now(UTC),
    )
    return bound[0], AlertMapper.to_response(alert, TENANT)


def test_a_verified_quote_gets_verified_locator_and_status() -> None:
    bound, resp = _response("VERIFIED")
    assert bound["source_locator_status"] == "VERIFIED"
    assert resp.evidence_status == "VERIFIED" and resp.source_clause_id == CLAUSE
    assert resp.detection_evidence is not None


def test_a_unverified_or_missing_quote_status_is_not_verified() -> None:
    for status in ("NOT_FOUND_IN_DOCUMENT", "NOT_PROVIDED", None):
        bound, resp = _response(status)
        assert bound["source_locator_status"] == "NOT_VERIFIED"
        assert resp.evidence_status == "NOT_VERIFIED"
        assert resp.source_clause_id is None and resp.detection_evidence is None


def test_a_alert_without_provenance_has_no_evidence_status() -> None:
    alert = Alert(
        id=uuid4(), project_id=PROJECT, severity=AlertSeverity.HIGH, category="SCOPE",
        status=list(AlertStatus)[0], approval_status=list(ApprovalStatus)[0], rule_id="R",
        title="x", description="y", alert_metadata={}, created_at=datetime.now(UTC),
    )
    assert AlertMapper.to_response(alert, TENANT).evidence_status is None


def _risk() -> ProjectRisk:
    return ProjectRisk(
        entity_id=uuid4(),
        payload=RiskItem(title="r", description="d", severity=Severity.HIGH),
    )


def test_b_unassessed_critique_qualifies_risk_health() -> None:
    sig = score_risk_dimension([_risk()], assessment_ran=True, critique_assessed=False)
    assert sig.score is not None
    assert sig.missing_data and "critique not assessed" in sig.missing_data
    assert sig.confidence <= 0.3


def test_b_assessed_critique_is_unchanged() -> None:
    sig = score_risk_dimension([_risk()], assessment_ran=True, extraction_quality=0.9)
    assert sig.score is not None and sig.missing_data == [] and sig.confidence == 0.9


def test_c_withheld_risks_never_yield_clean_score() -> None:
    sig = score_risk_dimension([], assessment_ran=True, extraction_quality=0.9, withheld_risks=3)
    assert sig.score is None and sig.null_reason is not None
    assert any("withheld" in m for m in sig.missing_data)
    assert not sig.evidence


def test_c_truly_empty_assessment_still_clean() -> None:
    sig = score_risk_dimension([], assessment_ran=True, extraction_quality=0.9)
    assert sig.score == 90.0
