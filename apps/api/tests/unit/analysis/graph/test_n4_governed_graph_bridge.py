"""Graph-to-N4 ledger seam: tests never call paid model APIs."""
from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from src.analysis.adapters.graph import n4_governed_bridge as bridge
from src.analysis.adapters.graph.nodes import risk_extractor_node
from src.core.processing_authority import (
    ProcessingAuthority,
    ProcessingStage,
    bound_authority,
)


def _state():
    tenant, document, revision, project = uuid4(), uuid4(), uuid4(), uuid4()
    original = "Clause 9.6: The EPC contractor shall notify the owner of delay within 12 business days."
    state = {
        "tenant_id": str(tenant),
        "project_id": str(project),
        "document_id": str(document),
        "document_revision_id": str(revision),
        "document_text": original,
        "anonymized_text": original,
        "pii_anonymization_complete": True,
        "n12_source_attestation": {
            "tenant_id": str(tenant), "project_id": str(project),
            "document_id": str(document), "revision_id": str(revision),
            "parsed_text_sha256": sha256(original.encode("utf-8")).hexdigest(),
            "blob_hash": "a" * 64,
        },
        "messages": [],
        "node_results": [],
        "extracted_risks": [],
        "human_approval_required": False,
        "confidence_score": 0.98,
    }
    authority = ProcessingAuthority(
        tenant_id=tenant, document_id=document, revision_id=revision,
        generation=1, stage=ProcessingStage.ANALYSIS,
        attempt_id=uuid4(), owner_token=uuid4(), fencing_token=1,
    )
    return state, authority


def test_graph_ledger_refuses_unowned_documents_and_unattested_source():
    state, auth = _state()
    with pytest.raises(bridge.N4GraphBridgeBlocked, match="processing authority"):
        bridge._identity(state)
    with bound_authority(auth):
        result_auth, project, projection = bridge._identity(state)
        assert result_auth is auth
        assert str(project) == state["project_id"]
        assert projection == state["anonymized_text"]
        state["n12_source_attestation"]["parsed_text_sha256"] = "0" * 64
        with pytest.raises(bridge.N4GraphBridgeBlocked, match="attestation"):
            bridge._identity(state)


def test_graph_ledger_rejects_identity_drift_even_with_text_present():
    state, auth = _state()
    state["document_revision_id"] = str(uuid4())
    with bound_authority(auth):
        with pytest.raises(bridge.N4GraphBridgeBlocked, match="authority"):
            bridge._identity(state)


def test_graph_ledger_keeps_provisional_quote_and_unknown_severity():
    quote = "The contractor shall notify the employer within 12 business days."
    claim = {
        "title": "Delay notice",
        "risk_reason": "Potential loss of entitlement if notice deadline is missed",
        "category": "contractual",
        "clause_ref": "9.6",
        "source_quote": quote,
        "source_evidence_status": "EXACT_MODEL_SAFE_MATCH",
    }
    refs = [{
        "document_revision_id": str(uuid4()),
        "source_kind": "MODEL_SAFE_PROJECTION",
        "evidence_status": "EXACT_MODEL_SAFE_MATCH",
        "analysis_span": [0, len(quote)],
    }]
    value = bridge._candidate_payload(claim, refs, quote)
    assert value["source_quote"] == quote
    assert value["source_quote_status"] == "VERIFIED"
    assert value["severity"] is None
    assert value["likelihood"] is None
    refs[0]["evidence_status"] = "NOT_FOUND_IN_MODEL_SAFE_SOURCE"
    value = bridge._candidate_payload(claim, refs, quote)
    assert value["source_quote"] is None
    assert value["source_quote_status"] == "NOT_FOUND_IN_DOCUMENT"


@pytest.mark.parametrize("run,window,chars", [
    ("11", "0.02", "12000"),
    ("1", "0.25", "3000"),
])
def test_graph_ledger_accepts_explicit_bounded_cost_policy(monkeypatch, run, window, chars):
    monkeypatch.setenv("C2PRO_N4_GRAPH_RUN_USD", run)
    monkeypatch.setenv("C2PRO_N4_GRAPH_WINDOW_USD", window)
    monkeypatch.setenv("C2PRO_N4_GRAPH_WINDOW_CHARS", chars)
    with pytest.raises(bridge.N4GraphBridgeBlocked) if float(run) > 10 else _nullcontext():
        vals = bridge._limits()
        assert vals[0] > 0
        assert vals[1] > 0


class _nullcontext:
    def __enter__(self): return self
    def __exit__(self, *args): return False


@pytest.mark.asyncio
async def test_graph_switch_returns_persisted_proposed_risks_without_legacy_tool(monkeypatch):
    state, auth = _state()
    async def fake_n4(_state):
        return {
            "extracted_risks": [
                {"title": "Clause 9.6 notice", "description": "Needs legal review",
                 "category": "contractual", "severity": None, "likelihood": None,
                 "source_quote": "Clause 9.6: The EPC contractor shall notify the owner of delay within 12 business days.",
                 "source_quote_status": "VERIFIED"},
            ],
            "risk_extraction_outcome": "PROPOSED_NOT_VERIFIED",
            "confidence_score": None,
            "human_approval_required": True,
            "n4_incremental_run_id": str(uuid4()),
        }
    monkeypatch.setenv("C2PRO_N4_GRAPH_LEDGER_ENABLED", "1")
    monkeypatch.setattr(bridge, "run_governed_n4_in_graph", fake_n4)
    out = await risk_extractor_node(state)
    assert len(out["extracted_risks"]) == 1
    assert out["human_approval_required"] is True
    assert out["confidence_score"] is None
    assert out["risk_extraction_outcome"] == "PROPOSED_NOT_VERIFIED"
    assert out.get("workflow_terminated") is not True
    assert any(isinstance(m, AIMessage) for m in out["messages"])


@pytest.mark.asyncio
async def test_graph_unavailable_gate_fails_closed_without_fake_review(monkeypatch):
    state, _ = _state()
    async def fake_unavailable(_):
        raise bridge.N4GraphBridgeBlocked("budget buckets not configured")
    monkeypatch.setenv("C2PRO_N4_GRAPH_LEDGER_ENABLED", "1")
    monkeypatch.setattr(bridge, "run_governed_n4_in_graph", fake_unavailable)
    from src.analysis.adapters.graph import nodes
    monkeypatch.setattr(nodes, "_persist_node_error", AsyncMock())
    out = await risk_extractor_node(state)
    assert out["extracted_risks"] == []
    assert out["confidence_score"] is None
    assert out["human_approval_required"] is False
    assert out["workflow_terminated"] is True
    assert out["termination_reason"] == "risk_extraction_unassessed"


@pytest.mark.asyncio
async def test_mock_ledger_cannot_call_provider(monkeypatch):
    state, authority = _state()
    monkeypatch.setenv("C2PRO_N4_GRAPH_LEDGER_ENABLED", "1")
    monkeypatch.setenv("C2PRO_AI_MOCK", "1")
    with bound_authority(authority):
        with pytest.raises(bridge.N4GraphBridgeBlocked, match="mock"):
            await bridge.run_governed_n4_in_graph(state)
