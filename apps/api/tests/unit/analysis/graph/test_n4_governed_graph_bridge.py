"""Graph-to-N4 ledger seam: tests never call paid model APIs."""
from __future__ import annotations

from hashlib import sha256
from unittest.mock import AsyncMock
from uuid import uuid4

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
        "n4_source_identity": {
            "tenant_id": str(tenant), "project_id": str(project),
            "document_id": str(document), "revision_id": str(revision),
            "parsed_text_sha256": sha256(original.encode("utf-8")).hexdigest(),
            "blob_hash": "a"*64,
            "source_kind": "REVISION_PINNED_PARSER_TEXT",
            "parser_coverage_status": "UNVERIFIED",
            "parser_origin": "docx_file_parser",
            "original_document_completeness_certified": False,
        },
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
        state["n4_source_identity"]["parsed_text_sha256"] = "0" * 64
        with pytest.raises(bridge.N4GraphBridgeBlocked, match="provenance"):
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


@pytest.mark.asyncio
async def test_n4_budget_not_configured_yields_machine_readable_blocker(monkeypatch):
    state, _ = _state()
    async def no_project_cap(_):
        raise bridge.N4GraphBridgeBlocked(
            "N4 durable source window run incomplete; reason=N4BudgetNotConfigured"
        )
    monkeypatch.setenv("C2PRO_N4_GRAPH_LEDGER_ENABLED", "1")
    monkeypatch.setattr(bridge, "run_governed_n4_in_graph", no_project_cap)
    from src.analysis.adapters.graph import nodes
    monkeypatch.setattr(nodes, "_persist_node_error", AsyncMock())
    out = await risk_extractor_node(state)
    assert out["analysis_blocker_code"] == "N4_BUDGET_NOT_CONFIGURED"
    assert out["workflow_terminated"] is True
    assert out["human_approval_required"] is False
    assert out["extracted_risks"] == []


# ── JV1-A7: COMPLETE_WITH_GAPS bridge, consolidation, reference register ─────

from src.analysis.application.n4_incremental_runner import N4RunOutcome  # noqa: E402
from src.analysis.domain.n4_failure_kinds import N4CoverageStatus  # noqa: E402

_SHA = "b" * 64


def _outcome(*, examined, total, persisted=None, status="FAILED"):
    return N4RunOutcome(
        run_id=uuid4(), status=status, examined_windows=examined,
        total_windows=total,
        persisted_result_windows=examined if persisted is None else persisted,
        stopped_reason="N4WindowGap",
    )


def _win(ordinal, status, reason=None, core=(0, 10)):
    return {"ordinal": ordinal, "status": status, "blocked_reason": reason,
            "core_start": core[0], "core_end": core[1]}


def test_all_terminal_windows_with_gap_yield_complete_with_gaps():
    outcome = _outcome(examined=2, total=3)
    cov = bridge.assess_n4_run(
        outcome=outcome,
        windows=[_win(0, "EXAMINED"), _win(1, "BLOCKED", "OUTPUT_TRUNCATED"),
                 _win(2, "EXAMINED")],
        reservations=[{"window_ordinal": 1, "status": "SETTLED"},
                      {"window_ordinal": 1, "status": "SETTLED"}],
        source_sha256=_SHA,
    )
    assert cov["status"] == N4CoverageStatus.COMPLETE_WITH_GAPS.value
    assert cov["run_id"] == str(outcome.run_id)
    assert cov["source_sha256"] == _SHA
    assert cov["gap_windows"] == [1]
    gap = cov["gaps"][0]
    assert gap["ordinal"] == 1
    assert gap["failure_kind"] == "OUTPUT_TRUNCATED"
    assert gap["attempts"] == 2
    assert gap["page_start"] is None and gap["page_end"] is None
    assert gap["resolution"] == "OPEN"


def test_gap_reason_is_sanitized_and_page_is_approximate_only_when_grounded():
    cov = bridge.assess_n4_run(
        outcome=_outcome(examined=1, total=2),
        windows=[_win(0, "EXAMINED", core=(0, 50)),
                 _win(1, "BLOCKED", "secret: ACME <b>Corp</b>\n sk-123", core=(60, 140))],
        reservations=[], source_sha256=_SHA,
        page_spans=[{"page": 1, "start_offset": 0, "end_offset": 100},
                    {"page": 2, "start_offset": 100, "end_offset": 200}],
    )
    gap = cov["gaps"][0]
    assert "<" not in gap["reason"] and "\n" not in gap["reason"] and len(gap["reason"]) <= 80
    assert gap["failure_kind"] == "UNCLASSIFIED"
    assert (gap["page_start"], gap["page_end"]) == (1, 2)


@pytest.mark.parametrize("windows,reservations", [
    # zero persisted result
    ([_win(0, "BLOCKED", "OUTPUT_TRUNCATED"), _win(1, "BLOCKED", "INVALID_ENVELOPE")], []),
    # non-terminal window
    ([_win(0, "EXAMINED"), _win(1, "PENDING")], []),
    # in-flight reservation
    ([_win(0, "EXAMINED"), _win(1, "BLOCKED", "OUTPUT_TRUNCATED")],
     [{"window_ordinal": 1, "status": "RESERVED"}]),
    # UNKNOWN (possibly billed) reservation
    ([_win(0, "EXAMINED"), _win(1, "BLOCKED", "PROVIDER_RESULT_UNCERTAIN")],
     [{"window_ordinal": 1, "status": "UNKNOWN"}]),
])
def test_unreviewable_runs_still_raise_run_incomplete(windows, reservations):
    examined = sum(1 for w in windows if w["status"] == "EXAMINED")
    with pytest.raises(bridge.N4RunIncomplete):
        bridge.assess_n4_run(
            outcome=_outcome(examined=examined, total=len(windows)),
            windows=windows, reservations=reservations, source_sha256=_SHA,
        )


def test_page_number_and_locator_are_optional_and_never_fabricated():
    from src.analysis.domain.contracts import RiskItem
    item = RiskItem(title="t", description="d")
    assert item.page_number is None and item.source_locator is None
    item = RiskItem(title="t", description="d", page_number=3, source_locator="p. 3")
    assert item.page_number == 3


def _claim_refs(quote):
    claim = {"title": "T", "risk_reason": "R", "category": "contractual",
             "source_quote": quote, "source_evidence_status": "EXACT_MODEL_SAFE_MATCH"}
    refs = [{"source_kind": "MODEL_SAFE_PROJECTION",
             "evidence_status": "EXACT_MODEL_SAFE_MATCH", "analysis_span": [0, len(quote)]}]
    return claim, refs


def test_candidate_payload_without_page_map_has_no_page_and_stays_verified():
    quote = "The contractor shall notify within 12 days."
    value = bridge._candidate_payload(*_claim_refs(quote), quote)
    assert value["page_number"] is None and value["source_locator"] is None
    # Exact N2-projection match only; explicitly not a page-verified citation.
    assert value["source_quote_status"] == "VERIFIED"
    assert value["page_verification_status"] == "PAGE_UNVERIFIED_NO_PAGE_MAP"


def test_candidate_payload_uses_page_locator_when_map_available(monkeypatch):
    from src.documents.domain import quote_page_locator as loc
    quote = "The contractor shall notify within 12 days."
    monkeypatch.setattr(loc, "locate_quote_page", lambda q, **kw: loc.QuotePageLocation(4, 5, 0, len(q)))
    spans = [loc.PageSpan(4, 0, 100)]
    value = bridge._candidate_payload(*_claim_refs(quote), quote, page_spans=spans)
    assert value["page_number"] == 4
    assert value["source_locator"] == "pp. 4–5"


def test_candidate_payload_locator_stub_unimplemented_is_not_verified():
    from src.documents.domain.quote_page_locator import PageSpan
    quote = "The contractor shall notify within 12 days."
    value = bridge._candidate_payload(
        *_claim_refs(quote), quote, page_spans=[PageSpan(1, 0, 100)],
    )
    assert value["page_number"] is None
    # Page map present but A9 locator unimplemented: no page => not VERIFIED.
    assert value["source_quote_status"] != "VERIFIED"
    assert value["source_quote"] is None
    assert value["page_verification_status"] == "PAGE_UNRESOLVED"


def test_candidate_payload_not_verified_when_map_available_but_page_missing(monkeypatch):
    from src.documents.domain import quote_page_locator as loc
    quote = "The contractor shall notify within 12 days."
    monkeypatch.setattr(loc, "locate_quote_page", lambda q, **kw: None)
    value = bridge._candidate_payload(
        *_claim_refs(quote), quote, page_spans=[loc.PageSpan(1, 0, 100)],
    )
    assert value["source_quote_status"] != "VERIFIED"
    assert value["source_quote"] is None
    assert value["page_number"] is None


@pytest.mark.asyncio
async def test_risk_node_degraded_with_coverage_gaps_requires_human(monkeypatch):
    state, _ = _state()
    gaps = [{"ordinal": 1, "failure_kind": "OUTPUT_TRUNCATED", "reason": "x",
             "attempts": 1, "page_start": None, "page_end": None, "resolution": "OPEN"}]
    cov = {"schema_version": "n4-coverage-v1", "status": "COMPLETE_WITH_GAPS",
           "run_id": str(uuid4()), "source_sha256": _SHA, "total_windows": 3,
           "examined_windows": 2, "gap_windows": [1], "gaps": gaps}

    async def fake_n4(_s):
        return {"extracted_risks": [{"title": "t", "description": "d"}],
                "risk_extraction_outcome": "PROPOSED_NOT_VERIFIED",
                "confidence_score": None, "human_approval_required": True,
                "n4_coverage": cov}
    monkeypatch.setenv("C2PRO_N4_GRAPH_LEDGER_ENABLED", "1")
    monkeypatch.setattr(bridge, "run_governed_n4_in_graph", fake_n4)
    out = await risk_extractor_node(state)
    result = out["node_results"][-1]
    assert result.status.value == "degraded"
    assert result.degradation_reason == "n4_complete_with_gaps"
    assert result.data["coverage_gaps"] == gaps
    assert out["human_approval_required"] is True
    assert out.get("workflow_terminated") is not True


@pytest.mark.asyncio
async def test_critique_off_mode_bypasses_llm_and_requires_human(monkeypatch):
    from src.analysis.adapters.graph import nodes
    state, _ = _state()
    state["extracted_risks"] = [{"title": "t", "description": "d"}]
    state["extracted_wbs"] = []
    state["retry_count"] = 0
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setenv("C2PRO_N12_MODE", "off")
    def boom(*a, **k):
        raise AssertionError("LLM service must not be constructed in N12 off mode")
    monkeypatch.setattr(nodes, "get_ai_service", boom)
    out = await nodes.critique_node(state)
    assert out["confidence_score"] is None
    assert out["human_approval_required"] is True


def test_review_summary_passes_coverage_and_reference_register():
    from src.analysis.adapters.graph import nodes
    state, _ = _state()
    state["doc_type"] = "contract"
    state["n4_coverage"] = {"status": "COMPLETE_WITH_GAPS", "gaps": []}
    state["n4_reference_register"] = [{"label": "Annex B", "status": "MISSING_EXTERNAL"}]
    summary = nodes._contract_risk_review_summary(state)
    assert summary["n4_coverage"]["status"] == "COMPLETE_WITH_GAPS"
    assert summary["n4_reference_register"][0]["status"] == "MISSING_EXTERNAL"


# consolidation -----------------------------------------------------------------

def _cand(key, quote, span, clause=None, category="TIME", ordinal=0):
    return {"finding_key": key, "window_ordinal": ordinal, "category": category,
            "clause_ref": clause, "source_quote": quote, "title": key,
            "source_refs": [{"analysis_span": list(span)}]}


def test_consolidation_merges_same_clause_and_keeps_all_keys_with_trace():
    from src.analysis.domain.n4_consolidation import consolidate_candidates
    a = _cand("k1", "notify within 12 days", (0, 100), clause="9.6")
    b = _cand("k2", "notify within 12 days", (5000, 5100), clause="9.6", ordinal=3)
    out = consolidate_candidates([a, b])
    assert len(out) == 1
    assert out[0]["source_keys"] == ["k1", "k2"]
    assert len(out[0]["source_refs"]) == 2
    assert out[0]["consolidation_trace"][0]["rule"] == "same_clause"


def test_consolidation_merges_on_half_span_overlap_same_category_only():
    from src.analysis.domain.n4_consolidation import consolidate_candidates
    a = _cand("k1", "x", (0, 100))
    b = _cand("k2", "x", (50, 150), ordinal=1)
    c = _cand("k3", "x", (50, 150), category="LEGAL", ordinal=1)
    out = consolidate_candidates([a, b, c])
    assert [o["source_keys"] for o in out] == [["k1", "k2"], ["k3"]]
    assert out[0]["consolidation_trace"][0]["rule"] == "span_overlap"
    # under 50 percent: separate
    d = _cand("k4", "x", (90, 400))
    assert len(consolidate_candidates([a, d])) == 2


def test_consolidation_never_merges_contradictory_facts():
    from src.analysis.domain.n4_consolidation import consolidate_candidates
    a = _cand("k1", "notify within 12 days", (0, 100), clause="9.6")
    b = _cand("k2", "notify within 15 days", (0, 100), clause="9.6")
    out = consolidate_candidates([a, b])
    assert len(out) == 2
    assert all(len(o["source_keys"]) == 1 for o in out)


# reference register ------------------------------------------------------------

_DOC = (
    "1. Scope\nThe works are as set out in Annex B.\n"
    "Annex A\nSpecification text.\n"
    "Liability is capped as per Annex A and the Pricing Schedule C.\n"
)


def test_reference_register_statuses_in_document_missing_external_unresolved():
    from src.analysis.domain.n4_reference_register import build_reference_register
    items = [
        {"finding_key": "k1", "source_quote": "The works are as set out in Annex B."},
        {"finding_key": "k2", "source_quote": "Liability is capped as per Annex A"},
        {"finding_key": "k3", "source_quote": "see Section 12.4 for details"},
    ]
    reg = {e["label"]: e for e in build_reference_register(_DOC, items)}
    assert reg["Annex B"]["status"] == "MISSING_EXTERNAL"
    assert reg["Annex B"]["proposal"] == "Referenced document not provided"
    assert reg["Annex B"]["source_quote"] == "The works are as set out in Annex B."
    assert reg["Annex B"]["source_quote"] in _DOC
    assert reg["Annex A"]["status"] == "IN_DOCUMENT"
    assert reg["Annex A"]["proposal"] is None
    assert reg["Section 12.4"]["status"] == "UNRESOLVED"


def test_reference_register_never_proposes_without_literal_quote_in_source():
    from src.analysis.domain.n4_reference_register import build_reference_register
    reg = build_reference_register(_DOC, [
        {"finding_key": "k9", "source_quote": "invented text mentioning Annex Z"},
    ])
    assert reg[0]["status"] == "UNRESOLVED"
    assert reg[0]["proposal"] is None


def test_register_scans_literal_remissions_even_without_risk_findings():
    from src.analysis.domain.n4_reference_register import build_reference_register

    register = {r["label"]: r for r in build_reference_register(_DOC, [])}
    assert register["Annex B"]["status"] == "MISSING_EXTERNAL"
    assert register["Annex B"]["source_quote"] in _DOC
    assert register["Annex A"]["status"] == "IN_DOCUMENT"


def test_missing_external_reference_becomes_proposed_risk_with_literal_evidence():
    from src.analysis.domain.n4_reference_register import build_reference_register

    register = build_reference_register(_DOC, [])
    risks, provenance = bridge._reference_proposals(
        register, source=_DOC, source_sha256=_SHA, revision_id="test-revision",
    )
    assert len(risks) >= 1
    candidate = next(r for r in risks if r["clause_ref"] == "Annex B")
    assert candidate["title"] == "Referenced document not provided"
    assert candidate["source_quote"] in _DOC
    assert candidate["severity"] is None
    assert candidate["confidence"] is None
    assert candidate["page_number"] is None
    assert candidate["page_verification_status"] == "PAGE_UNVERIFIED_NO_PAGE_MAP"
    assert any(p["source_refs"][0]["source_kind"] == "MODEL_SAFE_PROJECTION"
               for p in provenance)


def test_coverage_metadata_is_bound_to_exact_hitl_review():
    from src.analysis.adapters.graph import nodes

    state, _ = _state()
    cov = {"schema_version": "n4-coverage-v1",
           "status": "COMPLETE_WITH_GAPS", "run_id": str(uuid4()),
           "gap_windows": [2], "gaps": [{"ordinal": 2}]}
    state["n4_coverage"] = cov
    assert nodes._n4_coverage_review_metadata(state) == {
        "analysis_n4_coverage": cov
    }


def test_model_unresolved_refs_are_never_silently_discarded():
    from src.analysis.domain.n4_reference_register import build_reference_register

    register = build_reference_register(
        _DOC, [], unresolved_refs=["Annex B", "Unspecified vendor datasheet Q"]
    )
    assert any(x["label"] == "Annex B" and x["status"] == "MISSING_EXTERNAL"
               for x in register)
    unresolved = next(x for x in register if x["label"] == "Unspecified vendor datasheet Q")
    assert unresolved["status"] == "UNRESOLVED"
    assert unresolved["source_quote"] is None
    assert unresolved["proposal"] is None


def test_unanchored_model_reference_cannot_create_missing_external_proposal():
    from src.analysis.domain.n4_reference_register import build_reference_register

    register = build_reference_register(
        _DOC, [], unresolved_refs=["Annex Z"]
    )
    record = next(x for x in register if x["label"] == "Annex Z")
    assert record["status"] == "UNRESOLVED"
    assert record["proposal"] is None


def test_same_clause_distinct_obligations_are_never_consolidated():
    from src.analysis.domain.n4_consolidation import consolidate_candidates

    notice = _cand("notice", "The contractor shall notify the owner.", (0, 45), clause="9.6")
    report = _cand("report", "The contractor shall submit a report.", (500, 540), clause="9.6")
    assert len(consolidate_candidates([notice, report])) == 2


def test_overlapping_spans_do_not_override_distinct_quoted_obligations():
    from src.analysis.domain.n4_consolidation import consolidate_candidates

    notice = _cand("notice", "The contractor shall notify the owner.", (0, 90), clause="9.6")
    report = _cand("report", "The contractor shall submit a report.", (45, 135), clause="9.6")
    assert len(consolidate_candidates([notice, report])) == 2


def test_same_literal_clause_with_distinct_risk_reasons_stays_separate():
    from src.analysis.domain.n4_consolidation import consolidate_candidates

    a = _cand("k1", "If delayed, the contractor shall notify and report.", (0, 90), clause="9.6")
    b = _cand("k2", "If delayed, the contractor shall notify and report.", (0, 90), clause="9.6")
    a["description"] = "Late notification may void entitlement."
    b["description"] = "Failure to file a report may incur separate damages."
    assert len(consolidate_candidates([a, b])) == 2
