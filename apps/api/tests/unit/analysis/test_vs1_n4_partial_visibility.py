"""VS-1 focal regressions: no approval, no unsafe retry, source-pin reads."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.analysis.adapters.graph import n4_governed_bridge as bridge
from src.analysis.adapters.graph import nodes
from src.documents.adapters.http.router import (
    read_n4_partial_findings,
    reprocess_document_endpoint,
)
from src.documents.domain.models import DocumentStatus, DocumentType


@pytest.mark.asyncio
async def test_partial_N4_keeps_source_and_run_without_promoting_to_hitl(monkeypatch):
    run_id = uuid4()
    error = bridge.N4RunIncomplete(
        run_id=run_id, status="PARTIAL", examined_windows=1, total_windows=2,
        persisted_result_windows=2, blocked_result_windows=1,
        stopped_reason="PARTIAL", source_sha256="a" * 64,
    )
    monkeypatch.setenv("C2PRO_N4_GRAPH_LEDGER_ENABLED", "1")
    monkeypatch.setattr(bridge, "run_governed_n4_in_graph", AsyncMock(side_effect=error))
    monkeypatch.setattr(nodes, "_persist_node_error", AsyncMock())
    state = {"messages": [], "node_results": [], "extracted_risks": []}
    outcome = await nodes.risk_extractor_node(state)
    assert outcome["analysis_blocker_code"] == "N4_PARTIAL_RESULTS"
    assert outcome["n4_incremental_run_id"] == str(run_id)
    assert outcome["n4_incremental_source_sha256"] == "a" * 64
    assert outcome["workflow_terminated"] is True
    assert outcome["human_approval_required"] is False
    assert outcome["extracted_risks"] == []


@pytest.mark.asyncio
async def test_prior_run_reconciliation_never_overwrites_persisted_run(monkeypatch):
    error = bridge.N4RunIncomplete(
        run_id=uuid4(), status="PARTIAL", examined_windows=0, total_windows=2,
        persisted_result_windows=0, blocked_result_windows=0,
        stopped_reason="N4PriorRunReconciliationRequired", source_sha256="a" * 64,
    )
    monkeypatch.setenv("C2PRO_N4_GRAPH_LEDGER_ENABLED", "1")
    monkeypatch.setattr(bridge, "run_governed_n4_in_graph", AsyncMock(side_effect=error))
    monkeypatch.setattr(nodes, "_persist_node_error", AsyncMock())
    outcome = await nodes.risk_extractor_node({
        "messages": [], "node_results": [], "extracted_risks": []
    })
    assert outcome["analysis_blocker_code"] == "N4_PRIOR_RUN_RECONCILIATION_REQUIRED"
    assert "n4_incremental_run_id" not in outcome
    assert outcome["workflow_terminated"] is True


@pytest.mark.asyncio
async def test_reprocess_post_rejects_partial_result_even_if_called_directly():
    tenant, project, document = uuid4(), uuid4(), uuid4()
    doc = SimpleNamespace(
        project_id=project, document_type=DocumentType.CONTRACT,
        document_metadata={"analysis_blocker_code": "N4_PARTIAL_RESULTS"},
        upload_status=DocumentStatus.PARSED_PENDING_ANALYSIS,
    )
    repo = SimpleNamespace(get_by_id=AsyncMock(return_value=doc))
    with pytest.raises(HTTPException) as exc:
        await reprocess_document_endpoint(
            project, document, uuid4(), tenant, repo=repo,
            pending_review_lookup=lambda *_: {},
        )
    assert exc.value.status_code == 409
    assert not hasattr(repo, "begin_processing_generation")


class _SqlResult:
    def __init__(self, *, row=None, rows=None, number=None):
        self.row = row
        self.rows = rows or []
        self.number = number

    def mappings(self):
        return self

    def one_or_none(self):
        return self.row

    def all(self):
        return self.rows

    def scalar_one(self):
        return self.number


class _ReadOnlySession:
    def __init__(self, run_id, revision, digest):
        self.run_id, self.revision, self.digest = run_id, revision, digest
        self.calls = []

    async def execute(self, query, params):
        sql = str(query)
        self.calls.append((sql, dict(params)))
        if "SELECT r.run_id" in sql:
            return _SqlResult(row={
                "run_id": self.run_id, "status": "PARTIAL", "total_windows": 2,
                "generation": 1,
            })
        if "SELECT w.ordinal" in sql:
            return _SqlResult(rows=[
                {"ordinal": 0, "status": "BLOCKED", "blocked_reason": "REFERENCES_UNRESOLVED",
                 "unresolved_refs": ["Annex not supplied"], "has_result": True},
                {"ordinal": 1, "status": "EXAMINED", "blocked_reason": None,
                 "unresolved_refs": [], "has_result": True},
            ])
        if "SELECT count(*)" in sql:
            return _SqlResult(number=4)
        if "SELECT f.finding_key" in sql:
            return _SqlResult(rows=[
                {"finding_key": str(uuid4()), "window_ordinal": 0,
                 "claim": {"title": "Proposed risk", "risk_reason": "Scope discrepancy",
                           "source_quote": "exact N2 quote",
                           "source_evidence_status": "EXACT_MODEL_SAFE_MATCH",
                           "clause_ref": "2.1"},
                 "source_refs": [{"source_kind": "MODEL_SAFE_PROJECTION",
                                  "document_revision_id": str(self.revision),
                                  "source_sha256": self.digest,
                                  "evidence_status": "EXACT_MODEL_SAFE_MATCH",
                                  "analysis_span": [0, 14]}]},
            ])
        raise AssertionError(f"Unexpected SQL: {sql[:120]}")


@pytest.mark.asyncio
async def test_partial_get_reads_pinned_run_and_discloses_real_coverage_only():
    tenant, project, document, run, revision = (uuid4() for _ in range(5))
    digest = "d" * 64
    session = _ReadOnlySession(run, revision, digest)
    doc = SimpleNamespace(
        project_id=project,
        document_metadata={
            "analysis_n4_run_id": str(run),
            "analysis_n4_revision_id": str(revision),
            "analysis_n4_source_sha256": digest,
        },
    )
    repo = SimpleNamespace(get_by_id=AsyncMock(return_value=doc), session=session)
    data = await read_n4_partial_findings(
        project, document, uuid4(), tenant, offset=0, limit=100, repo=repo,
    )
    assert data["status"] == "PARTIAL_UNASSESSED"
    assert data["total_findings"] == 4
    assert data["coverage"]["windows_with_result"] == 2
    assert data["coverage"]["examined"] == 1
    assert data["coverage"]["blocked"] == 1
    assert data["findings"][0]["n2_quote_status"] == "N2_EXACT_MATCH"
    assert data["findings"][0]["interpretation"] == "Scope discrepancy"
    assert data["findings"][0]["original_pdf_quote_status"] == "UNVERIFIED"
    assert data["approvable"] is False and data["trusted"] is False
    assert len(session.calls) == 4
    assert "dr.valid_to IS NULL" in session.calls[0][0]
    assert "r.source_sha256 = :digest" in session.calls[0][0]
    assert all(verb not in sql.upper() for sql, _ in session.calls
               for verb in ("INSERT INTO ", "UPDATE PUBLIC.", "DELETE FROM "))
    assert all(p["tenant"] == str(tenant) and p["run"] == str(run)
               for sql, p in session.calls if "SELECT r.run_id" not in sql)


@pytest.mark.asyncio
async def test_partial_get_rejects_foreign_project_without_querying_ledger():
    tenant, project, document = uuid4(), uuid4(), uuid4()
    session = SimpleNamespace(execute=AsyncMock())
    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(
            project_id=uuid4(), document_metadata={})),
        session=session,
    )
    with pytest.raises(HTTPException) as exc:
        await read_n4_partial_findings(
            project, document, uuid4(), tenant, offset=0, limit=100, repo=repo,
        )
    assert exc.value.status_code == 404
    session.execute.assert_not_awaited()
