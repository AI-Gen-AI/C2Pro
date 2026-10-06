"""PC-2a.3 (#897) final review: WBS dates are not Schedule authority -- source-specific, not category-wide.

TS-UA-PC2A3-TIME-001. Two kinds of TIME evidence are kept apart:
- schedule-derived (milestones, activities, predecessors): WBS dates NEVER feed it, and while no
  governed Schedule source exists the rules that need it are not evaluated (no pass-by-absence);
- contract / obligation-derived (contract period, deadlines): still evaluated when present,
  dated WBS rows notwithstanding.
The WBS limitation travels as a non-evidence record; v1 decides once, v2 reuses that decision.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest

from src.coherence import schedule_clause_builder
from src.coherence.graph.graph import evaluate_coherence_async
from src.coherence.graph.state import EvaluationConfig
from src.coherence.models import Clause
from src.coherence.rules_engine.base import ApplicabilityState
from src.coherence.rules_engine.registry import get_evaluator
from src.coherence.schedule_clause_builder import build_schedule_clauses
from src.wbs.domain.governance import BaselineRef, resolve_authority

REASON = "WBS_DATES_NOT_SCHEDULE_AUTHORITY"


@pytest.fixture(autouse=True)
def _no_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setattr("langchain_core.tracers.context._get_tracer_project", lambda: "test")


class _Result:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _Session:
    async def execute(self, _stmt: object, _params: dict[str, object]) -> _Result:
        return _Result(3)  # the project's WBS carries dates


async def _wbs_marker(monkeypatch: pytest.MonkeyPatch, *, approved: bool) -> list[Clause]:
    """What the real builder emits for a project whose WBS rows carry dates."""
    baseline = BaselineRef(baseline_id=uuid4(), baseline_no=1, tree_digest="sha256:" + "0" * 64,
                           applied_at=datetime(2026, 10, 6, tzinfo=UTC))
    authority = resolve_authority(current_baseline=baseline if approved else None, live_node_count=3,
                                  open_change_sets=0)

    class _Repo:
        def __init__(self, _session: Any) -> None:
            pass

        async def authority(self, _project: UUID, _tenant: UUID) -> Any:
            return authority

    monkeypatch.setattr(schedule_clause_builder, "WBSGovernanceRepository", _Repo)
    return await build_schedule_clauses(_Session(), uuid4(), uuid4())  # type: ignore[arg-type]


def _contract_period() -> Clause:
    """Contract TIME evidence: a contractual period whose end precedes its start (DET-TIM-DURATION)."""
    return Clause(
        id="contract-period-1",
        text="The Works shall be carried out from 1 June 2026 and completed by 1 January 2026.",
        data={"document_type": "contract", "category": "TIME",
              "start_date": "2026-06-01", "end_date": "2026-01-01"},
    )


def _legal() -> Clause:
    return Clause(id="legal-1", text="The Contractor shall indemnify the Employer against third-party claims.",
                  data={"document_type": "contract", "category": "LEGAL"})


def _schedule(result: Any) -> Any:
    return next(item for item in result.category_breakdown if item.category == "schedule")


async def _evaluate(clauses: list[Clause]) -> Any:
    return await evaluate_coherence_async(clauses=clauses, project_id="p",
                                          config=EvaluationConfig(low_budget_mode=True))


# --------------------------------------------------------------------------- C
@pytest.mark.parametrize("approved", [False, True])
async def test_c_wbs_dates_generate_zero_schedule_evidence(monkeypatch: pytest.MonkeyPatch, approved: bool) -> None:
    [marker] = await _wbs_marker(monkeypatch, approved=approved)
    assert marker.data.get("non_evidence") is True
    assert marker.data["evidence_limitations"] == {"TIME": REASON}
    assert not {"schedule_items", "milestones", "start_date", "end_date", "status"} & set(marker.data)
    # and it is never a category-wide veto
    assert "assessment_unavailable" not in marker.data


# --------------------------------------------------------------------------- A / B / E / F
@pytest.mark.parametrize("approved", [False, True])
async def test_contract_time_evidence_still_evaluates_beside_dated_wbs(
        monkeypatch: pytest.MonkeyPatch, approved: bool) -> None:
    markers = await _wbs_marker(monkeypatch, approved=approved)
    result = await _evaluate([_contract_period(), _legal(), *markers])

    rule_ids = {s.rule_id for s in result.finding_signals}
    assert "DET-TIM-DURATION" in rule_ids  # the contractual TIME rule evaluated
    schedule = _schedule(result)
    assert schedule.state in {"assessed_findings", "assessed_clean"}
    assert schedule.limitations == [REASON]  # assessed, with the schedule-source limitation surfaced
    assert result.evidence_limitations == {"TIME": REASON}
    assert not rule_ids & {"DET-TIM-GAP", "DET-TIM-PREDECESSOR", "DET-TIM-STATUS"}


# --------------------------------------------------------------------------- D
@pytest.mark.parametrize("approved", [False, True])
async def test_d_wbs_dates_alone_leave_time_not_evaluated_with_the_reason(
        monkeypatch: pytest.MonkeyPatch, approved: bool) -> None:
    markers = await _wbs_marker(monkeypatch, approved=approved)
    result = await _evaluate([_legal(), *markers])

    schedule = _schedule(result)
    assert schedule.state == "unassessed" and schedule.score is None
    assert schedule.limitations == [REASON]
    assert result.evidence_limitations == {"TIME": REASON}
    assert not {s.rule_id for s in result.finding_signals if s.category == "TIME"}


# --------------------------------------------------------------------------- I
@pytest.mark.parametrize("rule_id", ["DET-TIM-GAP", "DET-TIM-PREDECESSOR"])
def test_i_schedule_rules_never_pass_by_absence(rule_id: str) -> None:
    evaluator_cls = get_evaluator(rule_id)
    assert evaluator_cls is not None
    evaluator = evaluator_cls()
    # contract TIME text with no schedule structure: the rule had nothing to assess
    assert evaluator.applicability(_contract_period()) is ApplicabilityState.SKIPPED_MISSING_INPUTS
    assert evaluator.applicability(Clause(id="t", text="Completion within 18 months.",
                                          data={"category": "TIME"})) is ApplicabilityState.SKIPPED_MISSING_INPUTS
    # a real schedule structure (from a governed Schedule source) is evaluated
    schedule = Clause(id="s", text="Programme", data={"category": "TIME", "schedule_items": [
        {"id": "A", "start_date": "2026-01-01", "end_date": "2026-03-01"},
        {"id": "B", "start_date": "2026-02-01", "end_date": "2026-06-01", "predecessor_id": "A"},
    ], "milestones": [{"id": "M1", "date": "2026-01-01"}, {"id": "M2", "date": "2026-12-01"}]})
    assert evaluator.applicability(schedule) is ApplicabilityState.EVALUATED


# --------------------------------------------------------------------------- H
def _db() -> Mock:
    db = Mock()
    db.execute = AsyncMock()
    db.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: []))
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


async def _v1_and_v2(clauses: list[Clause]) -> tuple[Any, Any]:
    """The real v1 evaluation, then the v2 shadow fed from that same v1 decision."""
    from src.coherence.router import CoherenceEvaluateRequest, evaluate_project_coherence
    from src.coherence.services.v2.shadow_runner import ShadowRunner

    v1 = await evaluate_coherence_async(clauses=clauses, project_id="p",
                                        config=EvaluationConfig(low_budget_mode=True))
    persisted: list[Any] = []

    async def _persist(self: ShadowRunner, *, db: object, tenant_id: object, v2: object) -> None:
        persisted.append(v2)

    docs = [SimpleNamespace(document_type=t) for t in ("contract", "schedule")]
    with (
        patch("src.coherence.router.evaluate_coherence_async", new_callable=AsyncMock, return_value=v1),
        patch("src.config.get_settings",
              return_value=SimpleNamespace(coherence_v2_enabled=True, coherence_v2_shadow_mode=True)),
        patch("src.coherence.services.v2.shadow_runner.ShadowRunner.emit", lambda *a, **k: None),
        patch("src.coherence.services.v2.shadow_runner.ShadowRunner.persist", _persist),
        patch("src.documents.adapters.persistence.sqlalchemy_document_repository."
              "SqlAlchemyDocumentRepository.list_for_project",
              new_callable=AsyncMock, return_value=(docs, len(docs))),
        patch("src.coherence.router._mirror_coherence_alerts_to_alerts_table", new_callable=AsyncMock),
    ):
        await evaluate_project_coherence(
            payload=CoherenceEvaluateRequest(project_id=uuid4(), clauses=clauses),
            include_diagnostics=False, db=_db(), current_user=SimpleNamespace(tenant_id=uuid4()))
    [v2] = persisted
    return v1, next(c for c in v2.categories if c.category == "TIME")


async def test_h_v1_and_v2_agree_when_contract_time_evidence_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    markers = await _wbs_marker(monkeypatch, approved=True)
    v1, v2_time = await _v1_and_v2([_contract_period(), _legal(), *markers])
    assert _schedule(v1).state != "unassessed"
    assert v2_time.rationale != REASON  # v2 does not withhold TIME that v1 assessed


async def test_h_v1_and_v2_agree_when_only_wbs_dates_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    markers = await _wbs_marker(monkeypatch, approved=False)
    v1, v2_time = await _v1_and_v2([_legal(), *markers])
    assert _schedule(v1).state == "unassessed"
    assert v2_time.coherence_score is None and v2_time.rationale == REASON
