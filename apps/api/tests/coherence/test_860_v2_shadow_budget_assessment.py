"""#860 -- the v2 shadow evaluation marks BUDGET unassessed UPSTREAM, with a reason.

TS-UA-860-V2-SHADOW-BUDGET-001. The v2 shadow path builds category evidence from
project documents; a budget document existing must not make BUDGET
``assessed_clean`` (score 100) while no authoritative structured budget-line source
exists. The evaluation-assembly boundary (the router) therefore passes the generic
``assessment_by_category`` / ``assessment_reason_by_category`` inputs; the
orchestrator and ``CategoryAggregator`` stay category-agnostic.
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import CategoryStatus
from src.coherence.models import (
    CategoryBreakdown,
    Clause,
    EnrichedCoherenceResult,
    FindingSignal,
    SeverityCount,
)

_REPO_LIST_FOR_PROJECT = (
    "src.documents.adapters.persistence"
    ".sqlalchemy_document_repository.SqlAlchemyDocumentRepository.list_for_project"
)


def _v1_result(finding_signals: list | None = None) -> EnrichedCoherenceResult:
    from src.coherence.graph.nodes import _signal_to_alert

    return EnrichedCoherenceResult(
        overall_score=75.0,
        alerts=[_signal_to_alert(signal) for signal in finding_signals or []],
        category_breakdown=[
            CategoryBreakdown(
                category="financial", score=80.0, alert_count=0,
                severity_breakdown=SeverityCount(critical=0, high=0, medium=0, low=0),
                impact_percentage=15.0,
            )
        ],
        calculated_at=datetime.now(UTC),
        finding_signals=finding_signals or [],
        llm_cost_usd=0.0,
    )


def _db() -> Mock:
    db = Mock()
    db.execute = AsyncMock()
    db.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: []))
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


async def _run_shadow(finding_signals: list | None = None) -> object:
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence
    from src.coherence.services.v2.shadow_runner import ShadowRunner

    settings = SimpleNamespace(coherence_v2_enabled=True, coherence_v2_shadow_mode=True)
    docs = [SimpleNamespace(document_type="budget"), SimpleNamespace(document_type="contract")]
    persisted_v2: list = []

    def _spy_emit(self: object, delta: object, feature_flag_state: object = None) -> None:
        return None

    async def _spy_persist(self: ShadowRunner, *, db: object, tenant_id: object, v2: object):
        persisted_v2.append(v2)

    with (
        patch("src.coherence.router.evaluate_coherence_async", new_callable=AsyncMock,
              return_value=_v1_result(finding_signals)),
        patch("src.config.get_settings", return_value=settings),
        patch("src.coherence.services.v2.shadow_runner.ShadowRunner.emit", _spy_emit),
        patch("src.coherence.services.v2.shadow_runner.ShadowRunner.persist", _spy_persist),
        patch(_REPO_LIST_FOR_PROJECT, new_callable=AsyncMock, return_value=(docs, len(docs))),
        patch("src.coherence.router._mirror_coherence_alerts_to_alerts_table",
              new_callable=AsyncMock),
    ):
        await evaluate_project_coherence(
            payload=CoherenceEvaluateRequest(
                project_id=uuid4(), clauses=[Clause(id="B-1", text="Budget", data={})]
            ),
            include_diagnostics=False,
            db=_db(),
            current_user=SimpleNamespace(tenant_id=uuid4()),
        )

    [payload] = persisted_v2
    return payload


def _category(payload: object, name: str):  # type: ignore[no-untyped-def]
    return next(c for c in payload.categories if c.category == name)  # type: ignore[attr-defined]


def _signal(rule_id: str, category: str) -> FindingSignal:
    return FindingSignal(
        rule_id=rule_id,
        clause_id=f"{rule_id}-clause",
        impact_score=0.4,
        confidence=1.0,
        severity="medium",
        category=category,
        evidence_summary=f"{rule_id} finding",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_budget_document_does_not_make_v2_budget_assessed_clean() -> None:
    payload = await _run_shadow()

    budget = _category(payload, "BUDGET")
    assert budget.status is CategoryStatus.INSUFFICIENT_EVIDENCE
    assert budget.status is not CategoryStatus.SCORED
    assert budget.coherence_score is None
    assert budget.rationale == "structured_budget_source_unavailable"
    assert budget.budget_reconciliation is None
    contract = _category(payload, "LEGAL")
    assert contract.rationale != "structured_budget_source_unavailable"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_independent_v1_budget_findings_are_kept_on_the_unassessed_category() -> None:
    """Codex P2: RETENTION / ADVANCE produce no conflict candidate, so the shadow
    inputs must carry them as rule signals of the unassessed category -- without
    feeding rule signals into categories whose shadow scoring this change does
    not touch."""
    baseline = await _run_shadow()
    payload = await _run_shadow(
        [_signal("DET-BUD-RETENTION", "BUDGET"), _signal("DET-BUD-ADVANCE", "BUDGET"),
         _signal("DET-LEG-INDEMNITY", "LEGAL")]
    )

    budget = _category(payload, "BUDGET")
    assert budget.status is CategoryStatus.INSUFFICIENT_EVIDENCE
    assert budget.coherence_score is None
    assert budget.calculation_metadata["available_rule_signals"] == [
        "DET-BUD-RETENTION", "DET-BUD-ADVANCE",
    ]
    assert _category(payload, "LEGAL") == _category(baseline, "LEGAL")
