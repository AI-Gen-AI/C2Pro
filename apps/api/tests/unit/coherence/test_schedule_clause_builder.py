"""TS-UD-COH-SCH-002: tenant-scoped WBS schedules become TIME clauses."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from src.coherence.alert_generator import AlertGenerator
from src.coherence.graph.nodes import deterministic_evaluate, scoring_arbiter
from src.coherence.graph.state import CoherenceGraphState, EvaluationConfig
from src.coherence.rules_engine.registry import get_evaluator
from src.coherence.schedule_clause_builder import build_schedule_clauses


class _Result:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def fetchall(self) -> list[object]:
        return self._rows


class _Session:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows
        self.params: list[dict[str, object]] = []

    async def execute(self, _stmt: object, params: dict[str, object]) -> _Result:
        self.params.append(params)
        limit = params.get("limit")
        rows = self._rows[: int(limit)] if isinstance(limit, int) else self._rows
        return _Result(rows)


class _FallbackSession:
    def __init__(self, rows: list[object]) -> None:
        self._results = [_Result([]), _Result(rows)]
        self.params: list[dict[str, object]] = []

    async def execute(self, _stmt: object, params: dict[str, object]) -> _Result:
        self.params.append(params)
        return self._results.pop(0)


def _row(
    *,
    node_id: UUID,
    code: str,
    name: str,
    start: datetime,
    end: datetime,
    status: str = "on_track",
    predecessor_id: str | None = None,
    source: str = "wbs_nodes",
) -> object:
    return SimpleNamespace(
        id=node_id,
        code=code,
        name=name,
        planned_start=start,
        planned_end=end,
        status=status,
        predecessor_id=predecessor_id,
        source=source,
    )


@pytest.mark.asyncio
async def test_build_schedule_clauses_preserves_tenant_scope_and_schedule_facts() -> None:
    """TS-UD-COH-SCH-002: WBS rows yield TIME facts without cross-tenant leakage."""
    project_id = uuid4()
    tenant_id = uuid4()
    predecessor = uuid4()
    successor = uuid4()
    session = _Session(
        [
            _row(
                node_id=predecessor,
                code="SCH-001",
                name="Foundation",
                start=datetime(2026, 1, 1, tzinfo=UTC),
                end=datetime(2026, 4, 15, tzinfo=UTC),
            ),
            _row(
                node_id=successor,
                code="SCH-002",
                name="Structure",
                start=datetime(2026, 4, 1, tzinfo=UTC),
                end=datetime(2026, 8, 1, tzinfo=UTC),
                status="delayed",
                predecessor_id="SCH-001",
            ),
        ]
    )

    clauses = await build_schedule_clauses(session, project_id, tenant_id)  # type: ignore[arg-type]

    assert len(clauses) == 3
    assert all(clause.data["document_type"] == "schedule" for clause in clauses)
    assert all(clause.data["category"] == "TIME" for clause in clauses)
    timeline = next(clause for clause in clauses if clause.id == f"schedule-timeline-{project_id}")
    assert timeline.data["schedule_items"] == [
        {
            "id": "SCH-001",
            "wbs_node_id": str(predecessor),
            "code": "SCH-001",
            "name": "Foundation",
            "start_date": "2026-01-01",
            "end_date": "2026-04-15",
            "status": "on_track",
            "predecessor_id": None,
        },
        {
            "id": "SCH-002",
            "wbs_node_id": str(successor),
            "code": "SCH-002",
            "name": "Structure",
            "start_date": "2026-04-01",
            "end_date": "2026-08-01",
            "status": "delayed",
            "predecessor_id": "SCH-001",
        },
    ]
    assert get_evaluator("DET-TIM-GAP") is not None
    assert get_evaluator("DET-TIM-GAP")().evaluate_v3(timeline) is not None
    assert get_evaluator("DET-TIM-PREDECESSOR") is not None
    assert get_evaluator("DET-TIM-PREDECESSOR")().evaluate_v3(timeline) is not None
    assert session.params == [{"project_id": str(project_id), "tenant_id": str(tenant_id), "limit": 50}]


@pytest.mark.asyncio
async def test_build_schedule_clauses_bounds_wbs_candidates() -> None:
    """TS-UD-COH-SCH-002: schedule evidence cannot bypass the retrieval limit."""
    session = _Session(
        [
            _row(
                node_id=uuid4(),
                code="SCH-001",
                name="Foundation",
                start=datetime(2026, 1, 1, tzinfo=UTC),
                end=datetime(2026, 4, 15, tzinfo=UTC),
            ),
            _row(
                node_id=uuid4(),
                code="SCH-002",
                name="Structure",
                start=datetime(2026, 4, 1, tzinfo=UTC),
                end=datetime(2026, 8, 1, tzinfo=UTC),
            ),
        ]
    )

    clauses = await build_schedule_clauses(session, uuid4(), uuid4(), max_items=1)  # type: ignore[arg-type]

    assert len(clauses) == 2
    assert session.params[0]["limit"] == 1


@pytest.mark.asyncio
async def test_build_schedule_clauses_uses_tenant_scoped_legacy_schedule_fallback() -> None:
    """TS-IA-COH-SCH-002: parsed legacy schedules remain visible only to their tenant."""
    project_id = uuid4()
    tenant_id = uuid4()
    session = _FallbackSession(
        [
            _row(
                node_id=uuid4(),
                code="SCH-001",
                name="Foundation",
                start=datetime(2026, 1, 1, tzinfo=UTC),
                end=datetime(2026, 4, 15, tzinfo=UTC),
                status="delayed",
                source="procurement_wbs_items",
            )
        ]
    )

    clauses = await build_schedule_clauses(session, project_id, tenant_id)  # type: ignore[arg-type]

    assert clauses[0].data["source"] == "procurement_wbs_items"
    assert clauses[0].data["status"] == "delayed"
    assert all(params["tenant_id"] == str(tenant_id) for params in session.params)


@pytest.mark.asyncio
async def test_build_schedule_clauses_returns_no_synthetic_facts_without_wbs_rows() -> None:
    """TS-UD-COH-SCH-002: absent WBS data stays honestly absent."""
    clauses = await build_schedule_clauses(_Session([]), uuid4(), uuid4())  # type: ignore[arg-type]

    assert clauses == []


@pytest.mark.asyncio
async def test_wbs_schedule_data_produces_an_assessed_time_dimension() -> None:
    """TS-IA-COH-SCH-002: WBS facts flow through live rules into TIME scoring."""
    project_id = uuid4()
    tenant_id = uuid4()
    predecessor = uuid4()
    session = _Session(
        [
            _row(
                node_id=predecessor,
                code="SCH-001",
                name="Foundation",
                start=datetime(2026, 1, 1, tzinfo=UTC),
                end=datetime(2026, 4, 15, tzinfo=UTC),
            ),
            _row(
                node_id=uuid4(),
                code="SCH-002",
                name="Structure",
                start=datetime(2026, 4, 1, tzinfo=UTC),
                end=datetime(2026, 8, 1, tzinfo=UTC),
                status="delayed",
                predecessor_id="SCH-001",
            ),
        ]
    )

    clauses = await build_schedule_clauses(session, project_id, tenant_id)  # type: ignore[arg-type]
    deterministic = deterministic_evaluate(
        CoherenceGraphState(
            project_id=str(project_id),
            clauses=clauses,
            config=EvaluationConfig(low_budget_mode=True),
        )
    )
    scored = scoring_arbiter(
        CoherenceGraphState(
            project_id=str(project_id),
            clauses=clauses,
            config=EvaluationConfig(low_budget_mode=True),
            deterministic_signals=deterministic["deterministic_signals"],
            coverage_map=deterministic["coverage_map"],
        )
    )

    rule_ids = {signal.rule_id for signal in deterministic["deterministic_signals"]}
    assert {"DET-TIM-GAP", "DET-TIM-PREDECESSOR"} <= rule_ids
    assert deterministic["coverage_map"]["TIME"] is True
    assert scored["diagnostics"]["category_scores"]["TIME"] is not None
    assert "TIME" not in scored["diagnostics"]["missing_dimensions"]
    predecessor_signal = next(
        signal for signal in deterministic["deterministic_signals"] if signal.rule_id == "DET-TIM-PREDECESSOR"
    )
    assert predecessor_signal.raw_data["predecessor_id"] == str(predecessor)
    affected = AlertGenerator(project_id)._affected_entities(
        "DET-TIM-PREDECESSOR", predecessor_signal.raw_data
    )
    assert set(affected["schedule_item_ids"]) == {
        str(predecessor),
        predecessor_signal.raw_data["successor_id"],
    }
