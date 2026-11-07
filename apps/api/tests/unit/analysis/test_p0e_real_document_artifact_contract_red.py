"""Regression for real #714 DocumentArtifact vs historical P0-E planner.

Expected RED on the author WIP before raw-document-artifact contract correction.
Only synthetic data; no database, LLM, HITL or production writes.
"""
from __future__ import annotations

import json
from hashlib import sha256
from uuid import uuid4

from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.trust import artifact_digest
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


def _risk(title: str, code: str, severity: str) -> dict[str, object]:
    return {
        "title": title,
        "description": title + " as stated by the EPC contract",
        "category": "LEGAL",
        "severity": severity,
        "clause_ref": code,
        "source": f"Contract section {code}",
        "source_quote": f"Contract section {code}: {title}",
        "source_quote_status": "VERIFIED",
    }


def test_actual_persisted_documentartifact_digest_v2_two_risks_against_three_alerts() -> None:
    tenant, project, document, revision, artifact_id, analysis_id = (uuid4() for _ in range(6))
    penalty = _risk("Delay penalty", "8.3", "CRITICAL")
    deadline = _risk("Completion deadline", "8.2", "HIGH")
    omitted = _risk("Written change approval", "8.4", "MEDIUM")

    # This is the canonical #714 model that the real artifact repository stores,
    # NOT a manufactured {"risks": [...]} projection with an unrelated hash.
    artifact = DocumentArtifact(
        document_id=str(document),
        document_revision_id=str(revision),
        doc_type="CONTRACT",
        extracted_risks=[penalty, deadline],
    )
    persisted_payload = artifact.model_dump(mode="json")
    if persisted_payload.get("structured_source") is None:
        persisted_payload.pop("structured_source", None)
    if persisted_payload.get("decision_snapshot") is None:
        persisted_payload.pop("decision_snapshot", None)

    # Match SqlAlchemyDocumentArtifactRepository._insert exactly:
    authoritative_digest = artifact_digest(persisted_payload)
    raw_bytes = json.dumps(
        persisted_payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    assert sha256(raw_bytes).hexdigest() == authoritative_digest

    snapshot = TrustedArtifactSnapshot(
        tenant_id=tenant,
        project_id=project,
        document_id=document,
        revision_id=revision,
        artifact_id=artifact_id,
        artifact_hash=authoritative_digest,
        trusted_artifact_payload=raw_bytes,
        is_trusted_active=True,
    )

    def _alert(risk: dict[str, object]) -> HistoricalAlertSnapshot:
        return HistoricalAlertSnapshot(
            alert_id=uuid4(),
            tenant_id=tenant,
            project_id=project,
            analysis_id=analysis_id,
            severity="LOW",
            alert_type="risk",
            source_clause_id=None,
            affected_document_ids=(document,),
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

    historical = HistoricalAnalysisSnapshot(
        analysis_id=analysis_id,
        tenant_id=tenant,
        project_id=project,
        document_id=document,
        revision_id=revision,
        source_artifact_id=artifact_id,
        analysis_type="risk",
        status="completed",
        alerts=(_alert(penalty), _alert(deadline), _alert(omitted)),
    )
    data = ReconciliationInput(
        approved_artifact=snapshot,
        v2_extracted_risks=(penalty, deadline),
        historical_analyses=(historical,),
    )
    plan = plan_historical_risk_alert_reconciliation(data)

    assert plan.status == PlanStatus.READY, f"blocked={plan.blocked_reasons}"
    assert len(plan.items) == 3
    assert sum(item.match_status == MatchStatus.EXACT_APPROVED_RISK for item in plan.items) == 2
    assert sum(item.recommendation == Recommendation.REQUIRES_OPERATOR_REVIEW for item in plan.items) == 1
    assert plan.advisory_only is True
