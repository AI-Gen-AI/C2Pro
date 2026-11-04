"""Source-only EPC comparisons: exact citations, no invented approved baselines."""
from __future__ import annotations

import hashlib
import json
from uuid import uuid4

import pytest

from src.analysis.adapters.graph.structured_source_comparison import compare_original_source_rows
from src.analysis.domain.contracts import DocumentArtifact, RiskItem


def _risk(quote: str, clause: str = "8.2", *, status: str = "VERIFIED") -> RiskItem:
    return RiskItem(
        title="Synthetic EPC commitment", description="Test-only original clause",
        source_quote=quote, source_quote_status=status, clause_ref=clause,
    )


def _artifact(kind: str, quote: str, *, status: str = "VERIFIED") -> DocumentArtifact:
    return DocumentArtifact(
        document_id=str(uuid4()), document_revision_id=str(uuid4()),
        doc_type=kind, extracted_risks=[_risk(quote, status=status)],
    )


def _unit(family: str, payload: dict, *, loc: str) -> dict:
    original = {"kind": "activity" if family == "schedule" else "declared_total",
                "source_locator": loc, **payload}
    encoded = json.dumps(original, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return {
        "family": family, "document_id": str(uuid4()),
        "revision_id": str(uuid4()), "source_locator": loc,
        "blob_hash": "b" * 64,
        "unit_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
        "payload": original,
    }


def _sources():
    contract = _artifact("contract", (
        "The contractual completion deadline is 2027-06-30. "
        "All EPC works shall achieve completion no later than that date."
    ))
    price = _artifact("contract", (
        "The total contract price is USD 1,000,000.00, subject to payment "
        "milestones defined in the agreement and the contract appendices."
    ))
    technical = _artifact("technical", (
        "Factory acceptance testing shall be completed no later than "
        "2027-06-10, before equipment is dispatched to site."
    ))
    schedule = _unit("schedule", {"task": "Project finish", "end_date": "2027-07-11 00:00:00"}, loc="Plan!5")
    acceptance = _unit("schedule", {"task": "Factory acceptance test", "end_date": "2027-07-01"}, loc="Plan!4")
    budget = _unit("budget", {"item": "TOTAL", "total": "1350000.00", "currency": "USD"}, loc="Budget!9")
    return [contract, price, technical], [schedule, acceptance, budget]


def test_three_provisional_discrepancies_have_both_exact_sources():
    artifacts, rows = _sources()
    result = compare_original_source_rows(artifacts, rows)
    findings = result["findings"]
    assert result["source_rows_verified"] == 3
    assert {x["rule_id"] for x in findings} == {
        "DET-CRS-SCHDEAD", "DET-CRS-NEGMARGIN", "SPEC-MILESTONE-VS-SCHEDULE"
    }
    for finding in findings:
        assert finding["state"] == "PROVISIONAL"
        assert finding["scored"] is False
        assert finding["requires_human_review"] is True
        quote, row = finding["sources"]
        assert quote["role"] == "verified_document_quote"
        assert quote["source_quote"] and quote["source_quote_sha256"]
        assert quote["document_id"] and quote["revision_id"] and quote["source_locator"]
        assert row["role"] == "original_source_row"
        assert row["document_id"] and row["revision_id"] and row["source_locator"]
        assert len(row["unit_sha256"]) == 64
        assert len(row["blob_sha256"]) == 64
    budget = next(x for x in findings if x["rule_id"] == "DET-CRS-NEGMARGIN")
    assert budget["compared_values"]["currency"] == "USD"
    assert budget["compared_values"]["difference"] == 350000.0
    schedule = next(x for x in findings if x["rule_id"] == "DET-CRS-SCHDEAD")
    assert schedule["compared_values"]["overrun_days"] == 11


def test_tampered_original_row_cannot_be_used_as_evidence():
    artifacts, rows = _sources()
    for row in rows:
        if row["family"] == "schedule":
            row["payload"]["end_date"] = "2030-01-01"
    result = compare_original_source_rows(artifacts, rows)
    assert result["source_rows_verified"] == 1
    assert {x["rule_id"] for x in result["findings"]} == {"DET-CRS-NEGMARGIN"}


def test_unverified_contract_quotes_and_ambiguous_dates_do_not_raise_conflicts():
    artifacts, rows = _sources()
    artifacts = [
        _artifact("contract", "Completion deadline 2027-06-30 or 2027-07-31 pending approval."),
        _artifact("contract", "The total contract price is USD 1,000,000.00.", status="REQUIRES_SOURCE_VALIDATION"),
        artifacts[2],
    ]
    result = compare_original_source_rows(artifacts, rows)
    assert {x["rule_id"] for x in result["findings"]} == {"SPEC-MILESTONE-VS-SCHEDULE"}
    assert "CONTRACT_COMPLETION_OR_SCHEDULE_NOT_UNAMBIGUOUS" in result["not_assessed_reasons"]


def test_missing_currency_does_not_invent_financial_contradiction():
    artifacts, rows = _sources()
    rows[-1]["payload"]["currency"] = None
    # Re-hash the changed original to represent a legitimately different file.
    original = rows[-1]["payload"]
    encoded = json.dumps(original, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    rows[-1]["unit_sha256"] = hashlib.sha256(encoded.encode()).hexdigest()
    result = compare_original_source_rows(artifacts, rows)
    assert "DET-CRS-NEGMARGIN" not in {x["rule_id"] for x in result["findings"]}
    assert "BUDGET_CURRENCY_OR_TOTAL_UNASSESSED" in result["not_assessed_reasons"]


@pytest.mark.asyncio
async def test_projectgraph_node_exposes_provisional_findings_without_scoring(monkeypatch):
    from types import SimpleNamespace
    from src.analysis.adapters.graph import project_graph
    artifacts, rows = _sources()
    project_id, tenant_id = uuid4(), uuid4()

    async def _off(_tenant_id):
        return False

    async def _fake_evaluate(artifacts, **kwargs):
        return SimpleNamespace(summary=SimpleNamespace(overall_score=None, signal_count=0))

    monkeypatch.setattr(project_graph, "is_coherence_llm_enabled", _off)
    monkeypatch.setattr(project_graph, "evaluate_artifact_set", _fake_evaluate)
    result = await project_graph.cross_doc_coherence({
        "project_id": project_id,
        "tenant_id": tenant_id,
        "artifacts": artifacts,
        "structured_source_units": rows,
    })
    assert len(result["structured_source_comparison"]["findings"]) == 3
    assert result["structured_source_comparison"]["scoring_policy"] == "provisional_only_not_scored"
    assert result["coherence_result"].overall_score is None


@pytest.mark.asyncio
async def test_projectgraph_persists_two_source_provisional_event_once():
    from src.core.tasks.project_graph_tasks import persist_provisional_source_discrepancies

    artifacts, rows = _sources()
    result = compare_original_source_rows(artifacts, rows)
    project_id, tenant_id = uuid4(), uuid4()

    class Result:
        def __init__(self, previous):
            self.previous = previous
        def scalar_one_or_none(self):
            return self.previous

    class Session:
        def __init__(self):
            self.added = []
            self.flushed = 0
        async def execute(self, statement):
            previous = self.added[-1].payload if self.added else None
            return Result(previous)
        def add(self, event):
            self.added.append(event)
        async def flush(self):
            self.flushed += 1

    db = Session()
    created = await persist_provisional_source_discrepancies(
        db, project_id=project_id, tenant_id=tenant_id, comparison=result
    )
    duplicate = await persist_provisional_source_discrepancies(
        db, project_id=project_id, tenant_id=tenant_id, comparison=result
    )
    assert created is True and duplicate is False
    assert len(db.added) == 1 and db.flushed == 1
    event = db.added[0]
    assert event.project_id == project_id and event.tenant_id == tenant_id
    assert event.event_type == "project_graph.source_discrepancies_observed"
    assert event.payload["state"] == "PROVISIONAL"
    assert event.payload["scoring_policy"] == "not_scored"
    assert event.payload["requires_human_review"] is True
    assert len(event.payload["findings"]) == 3
    assert len(event.evidence_refs) == 6
    assert all(x["document_id"] and x["revision_id"] and x["source_locator"] for x in event.evidence_refs)
    assert not await persist_provisional_source_discrepancies(
        db, project_id=project_id, tenant_id=tenant_id,
        comparison={"findings": []},
    )


@pytest.mark.asyncio
async def test_projectgraph_rejects_fake_scored_or_unbound_source_event():
    from src.core.tasks.project_graph_tasks import persist_provisional_source_discrepancies

    class NoWrite:
        async def execute(self, _):
            raise AssertionError("Invalid evidence must never touch PostgreSQL")

    for wrong in (
        {"findings": [{"state": "CONFIRMED", "scored": False, "sources": [{}, {}]}]},
        {"findings": [{"state": "PROVISIONAL", "scored": True, "sources": [{}, {}]}]},
        {"findings": [{"state": "PROVISIONAL", "scored": False, "sources": [{}]}]},
    ):
        with pytest.raises(ValueError, match="MUST_BE_PROVISIONAL"):
            await persist_provisional_source_discrepancies(
                NoWrite(), project_id=uuid4(), tenant_id=uuid4(), comparison=wrong
            )
