"""ProjectGraph canonical project evidence: provenance + PII gate."""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.coherence.models import Clause


@pytest.mark.asyncio
async def test_projectgraph_reads_canonical_sources_and_anonymizes(monkeypatch):
    from src.core.tasks.project_graph_tasks import _load_canonical_project_evidence
    from src.coherence import router
    from src.coherence import schedule_clause_builder

    contract_id = str(uuid4())
    budget_id = str(uuid4())
    schedule_id = str(uuid4())
    tenant_id, project_id = uuid4(), uuid4()
    calls = []

    async def clauses(db, pid, tid, max_chunks):
        assert db is sentinel
        assert pid == project_id and tid == tenant_id
        assert max_chunks == 60
        calls.append("clauses")
        return [
            Clause(
                id=str(uuid4()),
                text="Buyer director@example.com shall pay within 30 days.",
                data={"document_id": contract_id, "document_type": "contract"},
            )
        ]

    async def budget(current, db, pid, tid):
        calls.append("budget")
        return current + [
            Clause(
                id=f"budget-reconciliation-{pid}",
                text="Project budget vs contract reconciliation",
                data={
                    "document_id": budget_id,
                    "document_type": "budget",
                    "stated_total": 1_000_000,
                    "assessment_unavailable": {"BUDGET": "line items missing"},
                },
            ),
        ]

    async def schedule(current, db, pid, tid, max_chunks):
        calls.append("schedule")
        return current + [
            Clause(
                id=f"schedule-source-limitation-{pid}",
                text="WBS dates cannot serve as schedule authority",
                data={"non_evidence": True, "evidence_limitations": {"TIME": "no canonical schedule"}},
            )
        ]

    async def finish(db, pid, tid):
        calls.append("finish")
        return {
            "document_id": schedule_id,
            "revision_id": str(uuid4()),
            "planned_finish": "2027-09-30",
            "comment": "Contact director@example.com",
        }

    monkeypatch.setattr(router, "_get_persisted_clause_candidates", clauses)
    monkeypatch.setattr(router, "_with_budget_clause_candidates", budget)
    monkeypatch.setattr(router, "_with_schedule_clause_candidates", schedule)
    monkeypatch.setattr(schedule_clause_builder, "load_schedule_planned_finish", finish)

    sentinel = object()
    sourced, observed_finish = await _load_canonical_project_evidence(
        sentinel, project_id, tenant_id
    )

    assert calls == ["clauses", "budget", "schedule", "finish"]
    assert len(sourced) == 3
    assert "director@example.com" not in sourced[0].text
    assert sourced[0].data["document_id"] == contract_id
    assert sourced[1].data["stated_total"] == 1_000_000
    assert sourced[2].data["non_evidence"] is True
    assert observed_finish["document_id"] == schedule_id
    assert observed_finish["planned_finish"] == "2027-09-30"
    assert "director@example.com" not in observed_finish["comment"]
