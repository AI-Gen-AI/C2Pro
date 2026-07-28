"""TS-COH-BUD-RECON-001: budget clauses are wired into project coherence reads."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.coherence.models import Clause
from src.coherence.router import get_clauses_from_rag


class _Result:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class _Session:
    def __init__(self, results: list[_Result]) -> None:
        self._results = results

    async def execute(self, _stmt: object, _params: dict[str, object]) -> _Result:
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_get_clauses_from_rag_appends_budget_clauses_before_early_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-COH-BUD-RECON-001: structured BOM clauses are not bypassed by text hits."""
    project_id = uuid4()
    tenant_id = uuid4()
    persisted_row = (
        uuid4(),
        "Contract price is stated in the agreement.",
        {"category": "LEGAL"},
        uuid4(),
        "contract",
    )
    db = _Session(
        [
            _Result([persisted_row]),
            _Result([]),
            _Result([]),
            _Result([]),
            _Result([]),
            _Result([]),
            _Result([]),
        ]
    )
    budget_clause = Clause(
        id=f"budget-reconciliation-{project_id}",
        text="Project budget vs contract reconciliation",
        data={"category": "BUDGET", "affected_categories": ["BUDGET"]},
    )

    async def _fake_budget_builder(_db: object, _project_id: object, _tenant_id: object) -> list[Clause]:
        return [budget_clause]

    async def _fake_schedule_builder(
        _db: object,
        _project_id: object,
        _tenant_id: object,
        *,
        max_items: int,
    ) -> list[Clause]:
        assert max_items == 50
        return []

    monkeypatch.setattr("src.coherence.router.build_budget_clauses", _fake_budget_builder)
    monkeypatch.setattr("src.coherence.router.build_schedule_clauses", _fake_schedule_builder)

    clauses = await get_clauses_from_rag(db, project_id, tenant_id)  # type: ignore[arg-type]

    assert [clause.id for clause in clauses] == [str(persisted_row[0]), budget_clause.id]


@pytest.mark.asyncio
async def test_get_clauses_from_rag_appends_schedule_clauses_before_early_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TS-UD-COH-SCH-002: tenant-scoped WBS schedule facts reach coherence reads."""
    project_id = uuid4()
    tenant_id = uuid4()
    db = _Session([_Result([]) for _ in range(7)])
    schedule_clause = Clause(
        id=f"schedule-timeline-{project_id}",
        text="Project schedule timeline from WBS activities",
        data={"category": "TIME", "affected_categories": ["TIME"]},
    )

    async def _fake_budget_builder(_db: object, _project_id: object, _tenant_id: object) -> list[Clause]:
        return []

    async def _fake_schedule_builder(
        builder_db: object,
        builder_project_id: object,
        builder_tenant_id: object,
        *,
        max_items: int,
    ) -> list[Clause]:
        assert builder_db is db
        assert builder_project_id == project_id
        assert builder_tenant_id == tenant_id
        assert max_items == 50
        return [schedule_clause]

    monkeypatch.setattr("src.coherence.router.build_budget_clauses", _fake_budget_builder)
    monkeypatch.setattr("src.coherence.router.build_schedule_clauses", _fake_schedule_builder)

    clauses = await get_clauses_from_rag(db, project_id, tenant_id)  # type: ignore[arg-type]

    assert clauses == [schedule_clause]
