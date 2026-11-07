"""Unit tests for the P0-E authenticated, read-only planner boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.historical_risk_alert_reconciliation_reader import (
    SqlAlchemyHistoricalRiskAlertReconciliationReader,
)
from src.analysis.application.historical_risk_alert_reconciliation import (
    HistoricalAlertSnapshot,
    HistoricalAnalysisSnapshot,
    MatchStatus,
    PlanStatus,
    ReconciliationInput,
    TrustedArtifactSnapshot,
)
from src.analysis.application.historical_risk_alert_reconciliation_reader import (
    HistoricalRiskAlertReconciliationService,
    ReconciliationReadScope,
    ReconciliationScopeNotAuthorized,
)
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.trust import artifact_digest


def _risk(title: str, severity: str, quote_status: str = "VERIFIED") -> dict[str, object]:
    return {
        "title": title,
        "description": f"{title} from the original EPC contract",
        "category": "LEGAL",
        "severity": severity,
        "source": "EPC contract",
        "source_quote": f"EPC contract: {title}",
        "source_quote_status": quote_status,
    }


def _input(*, trusted: bool = True, duplicate: bool = False, dismissed: bool = False) -> ReconciliationInput:
    tenant, project, document, revision, artifact, analysis = (uuid4() for _ in range(6))
    approved = (_risk("Completion deadline", "HIGH"), _risk("Delay penalty", "CRITICAL"))
    payload = DocumentArtifact(
        document_id=str(document),
        document_revision_id=str(revision),
        doc_type="CONTRACT",
        extracted_risks=list(approved),
    ).model_dump(mode="json")
    payload.pop("structured_source")
    payload.pop("decision_snapshot")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()

    historical = list(approved) + [_risk("Written change approval", "MEDIUM")]
    if duplicate:
        historical = [approved[0], approved[0], approved[1]]
    alerts = tuple(
        HistoricalAlertSnapshot(
            alert_id=uuid4(),
            tenant_id=tenant,
            project_id=project,
            analysis_id=analysis,
            severity="LOW",
            alert_type="risk",
            source_clause_id=None,
            affected_document_ids=(document,),
            alert_metadata={"raw": risk},
            status="dismissed" if dismissed and index == 0 else "open",
            approval_status="pending",
            reviewed_by=None,
            reviewed_at=None,
            review_comment=None,
            resolved_at=None,
            resolved_by=None,
            resolution_notes=None,
        )
        for index, risk in enumerate(historical)
    )
    return ReconciliationInput(
        approved_artifact=TrustedArtifactSnapshot(
            tenant_id=tenant,
            project_id=project,
            document_id=document,
            revision_id=revision,
            artifact_id=artifact,
            artifact_hash=artifact_digest(payload),
            trusted_artifact_payload=encoded,
            is_trusted_active=trusted,
        ),
        v2_extracted_risks=approved,
        historical_analyses=(
            HistoricalAnalysisSnapshot(
                analysis_id=analysis,
                tenant_id=tenant,
                project_id=project,
                document_id=document,
                revision_id=revision,
                source_artifact_id=artifact,
                analysis_type="risk",
                status="completed",
                alerts=alerts,
            ),
        ),
    )


@dataclass
class _Repository:
    input_data: ReconciliationInput | None = None
    error: Exception | None = None

    async def assemble(self, scope: ReconciliationReadScope) -> ReconciliationInput:
        if self.error:
            raise self.error
        assert self.input_data is not None
        assert scope.tenant_id == self.input_data.approved_artifact.tenant_id
        return self.input_data


def _scope(input_data: ReconciliationInput) -> ReconciliationReadScope:
    artifact = input_data.approved_artifact
    return ReconciliationReadScope(
        tenant_id=artifact.tenant_id,
        project_id=artifact.project_id,
        document_id=artifact.document_id,
        revision_id=artifact.revision_id,
        artifact_id=artifact.artifact_id,
    )


@pytest.mark.asyncio
async def test_service_returns_existing_planner_report_for_two_of_three_persisted_risks() -> None:
    input_data = _input()

    plan = await HistoricalRiskAlertReconciliationService(_Repository(input_data)).plan(_scope(input_data))

    assert plan.status is PlanStatus.READY
    assert [item.match_status for item in plan.items].count(MatchStatus.EXACT_APPROVED_RISK) == 2
    assert [item.match_status for item in plan.items].count(MatchStatus.NOT_PRESENT_IN_APPROVED_ARTIFACT) == 1


@pytest.mark.asyncio
async def test_service_preserves_read_boundary_tenant_refusal() -> None:
    input_data = _input()
    service = HistoricalRiskAlertReconciliationService(
        _Repository(error=ReconciliationScopeNotAuthorized("PROJECT_TENANT_MISMATCH"))
    )

    with pytest.raises(ReconciliationScopeNotAuthorized, match="PROJECT_TENANT_MISMATCH"):
        await service.plan(_scope(input_data))


@pytest.mark.asyncio
async def test_service_returns_planner_block_for_untrusted_or_stale_authority() -> None:
    input_data = _input(trusted=False)

    plan = await HistoricalRiskAlertReconciliationService(_Repository(input_data)).plan(_scope(input_data))

    assert plan.status is PlanStatus.PLAN_BLOCKED
    assert "ARTIFACT_NOT_TRUSTED_ACTIVE" in plan.blocked_reasons


@pytest.mark.asyncio
async def test_service_keeps_duplicate_and_human_disposition_for_operator_review() -> None:
    duplicate = _input(duplicate=True)
    dismissed = _input(dismissed=True)

    duplicate_plan = await HistoricalRiskAlertReconciliationService(_Repository(duplicate)).plan(_scope(duplicate))
    dismissed_plan = await HistoricalRiskAlertReconciliationService(_Repository(dismissed)).plan(_scope(dismissed))

    assert any(item.match_status is MatchStatus.AMBIGUOUS for item in duplicate_plan.items)
    assert any(item.match_status is MatchStatus.HUMAN_DISPOSITION_PRESERVED for item in dismissed_plan.items)


@pytest.mark.asyncio
async def test_persistence_reader_blocks_legacy_alerts_without_document_revision_provenance() -> None:
    input_data = _input()
    artifact = input_data.approved_artifact
    persisted_artifact = SimpleNamespace(
        tenant_id=artifact.tenant_id,
        project_id=artifact.project_id,
        document_id=artifact.document_id,
        artifact_id=artifact.artifact_id,
        artifact_hash=artifact.artifact_hash,
        payload=json.loads(artifact.trusted_artifact_payload),
        trust_state="trusted",
        lifecycle_status="active",
    )

    class _SelectOnlySession:
        def __init__(self) -> None:
            self._rows = iter((artifact.project_id, persisted_artifact))

        async def scalar(self, _statement: object) -> object:
            return next(self._rows)

    plan = await HistoricalRiskAlertReconciliationService(
        SqlAlchemyHistoricalRiskAlertReconciliationReader(_SelectOnlySession())  # type: ignore[arg-type]
    ).plan(_scope(input_data))

    assert plan.status is PlanStatus.PLAN_BLOCKED
    assert "NOT_ENOUGH_EVIDENCE" in plan.blocked_reasons
