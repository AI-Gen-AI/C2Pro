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
    SeverityCount,
)

_REPO_LIST_FOR_PROJECT = (
    "src.documents.adapters.persistence"
    ".sqlalchemy_document_repository.SqlAlchemyDocumentRepository.list_for_project"
)


def _v1_result() -> EnrichedCoherenceResult:
    return EnrichedCoherenceResult(
        overall_score=75.0,
        alerts=[],
        category_breakdown=[
            CategoryBreakdown(
                category="financial", score=80.0, alert_count=0,
                severity_breakdown=SeverityCount(critical=0, high=0, medium=0, low=0),
                impact_percentage=15.0,
            )
        ],
        calculated_at=datetime.now(UTC),
        finding_signals=[],
        llm_cost_usd=0.0,
    )


def _db() -> Mock:
    db = Mock()
    db.execute = AsyncMock()
    db.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: []))
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.mark.unit
@pytest.mark.asyncio
async def test_budget_document_does_not_make_v2_budget_assessed_clean() -> None:
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence

    emitted: list = []
    settings = SimpleNamespace(coherence_v2_enabled=True, coherence_v2_shadow_mode=True)
    docs = [SimpleNamespace(document_type="budget"), SimpleNamespace(document_type="contract")]

    def _spy_emit(self: object, delta: object, feature_flag_state: object = None) -> None:
        emitted.append(delta)

    persisted_v2: list = []
    from src.coherence.services.v2.shadow_runner import ShadowRunner

    async def _spy_persist(self: ShadowRunner, *, db: object, tenant_id: object, v2: object):
        persisted_v2.append(v2)

    with (
        patch("src.coherence.router.evaluate_coherence_async", new_callable=AsyncMock,
              return_value=_v1_result()),
        patch("src.config.get_settings", return_value=settings),
        patch("src.coherence.services.v2.shadow_runner.ShadowRunner.emit", _spy_emit),
        patch("src.coherence.services.v2.shadow_runner.ShadowRunner.persist", _spy_persist),
        patch(_REPO_LIST_FOR_PROJECT, new_callable=AsyncMock, return_value=(docs, len(docs))),
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
    budget = next(c for c in payload.categories if c.category == "BUDGET")
    assert budget.status is CategoryStatus.INSUFFICIENT_EVIDENCE
    assert budget.status is not CategoryStatus.SCORED
    assert budget.coherence_score is None
    assert budget.rationale == "structured_budget_source_unavailable"
    assert budget.budget_reconciliation is None
    contract = next(c for c in payload.categories if c.category == "LEGAL")
    assert contract.rationale != "structured_budget_source_unavailable"
