"""TS-UD-COH-SCH-002 / PC-2a.3 (#897): WBS dates are never TIME (schedule) evidence.

SCHEDULE ACTIVITY != WBS NODE. Dated WBS rows yield no schedule item, milestone or predecessor;
they yield one fail-closed marker that keeps TIME unassessed -- ``WBS_NOT_APPROVED`` without an
approved baseline, ``WBS_DATES_NOT_SCHEDULE_AUTHORITY`` with one (approved scope is not schedule
authority). The database-backed authority states are proven in
tests/modules/integration/test_pc2a3_wbs_authority_enforcement.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.coherence import schedule_clause_builder
from src.coherence.graph.nodes import deterministic_evaluate, scoring_arbiter
from src.coherence.graph.state import CoherenceGraphState, EvaluationConfig
from src.coherence.schedule_clause_builder import build_schedule_clauses
from src.wbs.domain.governance import BaselineRef, resolve_authority


class _Result:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _Session:
    """Answers the dated-row count; records every statement's parameters."""

    def __init__(self, dated_rows: int) -> None:
        self._dated_rows = dated_rows
        self.params: list[dict[str, object]] = []

    async def execute(self, _stmt: object, params: dict[str, object]) -> _Result:
        self.params.append(params)
        return _Result(self._dated_rows)


def _authority(monkeypatch: pytest.MonkeyPatch, *, approved: bool) -> list[tuple[UUID, UUID]]:
    calls: list[tuple[UUID, UUID]] = []
    baseline = BaselineRef(baseline_id=uuid4(), baseline_no=1, tree_digest="sha256:" + "0" * 64,
                           applied_at=datetime(2026, 10, 6, tzinfo=UTC))
    authority = resolve_authority(current_baseline=baseline if approved else None, live_node_count=2,
                                  open_change_sets=0)

    class _Repo:
        def __init__(self, _session: Any) -> None:
            pass

        async def authority(self, project_id: UUID, tenant_id: UUID) -> Any:
            calls.append((project_id, tenant_id))
            return authority

    monkeypatch.setattr(schedule_clause_builder, "WBSGovernanceRepository", _Repo)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize(("approved", "reason"), [
    (False, "WBS_NOT_APPROVED"),
    (True, "WBS_DATES_NOT_SCHEDULE_AUTHORITY"),
])
async def test_dated_wbs_rows_yield_only_a_time_withheld_marker(
        monkeypatch: pytest.MonkeyPatch, approved: bool, reason: str) -> None:
    project_id, tenant_id = uuid4(), uuid4()
    calls = _authority(monkeypatch, approved=approved)
    session = _Session(dated_rows=2)

    clauses = await build_schedule_clauses(session, project_id, tenant_id)  # type: ignore[arg-type]

    assert len(clauses) == 1
    data = clauses[0].data
    assert data["category"] == "TIME" and data["assessment_unavailable"] == {"TIME": reason}
    assert not {"schedule_items", "milestones", "wbs_node_id", "start_date", "end_date"} & set(data)
    # tenant scope on the read and one authority resolution for the project
    assert session.params == [{"project_id": str(project_id), "tenant_id": str(tenant_id)}]
    assert calls == [(project_id, tenant_id)]


@pytest.mark.asyncio
async def test_no_dated_wbs_rows_yield_nothing_and_skip_the_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _authority(monkeypatch, approved=True)
    assert await build_schedule_clauses(_Session(dated_rows=0), uuid4(), uuid4()) == []  # type: ignore[arg-type]
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("approved", [False, True])
async def test_wbs_dates_never_make_time_an_assessed_dimension(
        monkeypatch: pytest.MonkeyPatch, approved: bool) -> None:
    project_id = uuid4()
    _authority(monkeypatch, approved=approved)
    clauses = await build_schedule_clauses(_Session(dated_rows=3), project_id, uuid4())  # type: ignore[arg-type]
    config = EvaluationConfig(low_budget_mode=True)
    deterministic = deterministic_evaluate(
        CoherenceGraphState(project_id=str(project_id), clauses=clauses, config=config))
    scored = scoring_arbiter(CoherenceGraphState(
        project_id=str(project_id), clauses=clauses, config=config,
        deterministic_signals=deterministic["deterministic_signals"], coverage_map=deterministic["coverage_map"]))

    assert not {s.rule_id for s in deterministic["deterministic_signals"]} & {"DET-TIM-GAP", "DET-TIM-PREDECESSOR"}
    assert scored["diagnostics"]["category_scores"].get("TIME") is None
