"""Observation probe (scratch only, NOT repository code).

Drives the REAL runtime code of the checked-out worktree (N4 runner, ledger,
governed bridge, risk_extractor_node, workflow routing, document lifecycle and
status-detail functions, AlertGenerator) against a disposable PostgreSQL with
a zero-cost stub provider. Prints observations; asserts nothing about desired
behaviour. Synthetic text and synthetic references: no model quality claim.
"""
from __future__ import annotations

import json
import os
from hashlib import sha256
from uuid import uuid4

import asyncpg
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.analysis.adapters.graph import n4_governed_bridge as bridge
from src.analysis.application.n4_incremental_runner import N4ProviderReceipt
from src.core.processing_authority import ProcessingAuthority, bound_authority
from tests.integration.analysis.test_n4_window_runner_pg import _prepare, _source

DSN = os.environ["C2PRO_N4_SCRATCH_DSN"]
OUT = os.environ.get("PROBE_OUT", "probe_out.json")
REPORT: dict = {"code_sha": os.environ.get("PROBE_CODE_SHA")}


class Stub:
    """Per window: one verbatim quote, one paraphrase; refs on chosen windows."""
    model_name = "stub-zero-cost"
    fallback_reservation_usd = None
    approved_fallback_models = frozenset()
    fallback_routes = ()

    def __init__(self, ref_windows):
        self.calls: list[int] = []
        self.ref_windows = ref_windows

    async def generate(self, *, window, tenant_id, request_id):
        self.calls.append(window.ordinal)
        verbatim = window.context_text[10:80]
        return N4ProviderReceipt(
            content=json.dumps({
                "window_examined": True,
                "findings": [
                    {"title": f"Obligation w{window.ordinal}", "category": "contractual",
                     "risk_reason": "interpretation", "source_quote": verbatim,
                     "clause_ref": f"{window.ordinal}.1", "impact": "high"},
                    {"title": f"Paraphrased w{window.ordinal}", "category": "schedule",
                     "risk_reason": "interpretation",
                     "source_quote": "the contractor must deliver everything on time",
                     "clause_ref": None, "impact": "critical"},
                ],
                "outstanding_references": (
                    [f"Annex {window.ordinal} referenced but not provided"]
                    if window.ordinal in self.ref_windows else []
                ),
            }),
            model_used=self.model_name, reported_cost_usd="0.000000",
            input_tokens=10, output_tokens=10, provider_request_id=request_id,
        )


def _state(authority, project, text):
    digest = sha256(text.encode()).hexdigest()
    ident = {
        "tenant_id": str(authority.tenant_id), "project_id": str(project),
        "document_id": str(authority.document_id),
        "revision_id": str(authority.revision_id),
        "parsed_text_sha256": digest, "blob_hash": "a" * 64,
    }
    return {
        "tenant_id": str(authority.tenant_id), "project_id": str(project),
        "document_id": str(authority.document_id),
        "document_revision_id": str(authority.revision_id),
        "document_text": text, "anonymized_text": text,
        "pii_anonymization_complete": True, "doc_type": "contract",
        "messages": [], "node_results": [], "retry_count": 0,
        "extracted_wbs": [], "extracted_risks": [],
        "n4_source_identity": {**ident, "source_kind": "REVISION_PINNED_PARSER_TEXT",
                               "parser_coverage_status": "UNVERIFIED",
                               "parser_origin": "docx_file_parser",
                               "original_document_completeness_certified": False},
        "n12_source_attestation": ident,
    }


def _env(monkeypatch, engine, provider):
    for k, v in {
        "C2PRO_N4_GRAPH_LEDGER_ENABLED": "1", "C2PRO_N4_GRAPH_RUN_USD": "1.000000",
        "C2PRO_N4_GRAPH_WINDOW_USD": "0.040000", "C2PRO_N4_GRAPH_WINDOW_CHARS": "1000",
        "C2PRO_N4_GRAPH_OVERLAP_CHARS": "50", "C2PRO_DIRECT_FALLBACK_ENABLED": "0",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setattr(bridge, "AnthropicWrapper", lambda **kw: object())
    monkeypatch.setattr(bridge, "AnthropicN4WindowProvider", lambda **kw: provider)
    monkeypatch.setattr(bridge, "get_session_factory",
                        lambda: async_sessionmaker(engine, expire_on_commit=False))


async def _ledger(tenant, document):
    c = await asyncpg.connect(DSN)
    try:
        await c.execute("SELECT set_config('app.current_tenant',$1,false)", str(tenant))
        runs = [dict(r) for r in await c.fetch("""
            SELECT run_id::text, generation, status, total_windows FROM n4_extraction_runs
             WHERE tenant_id=$1 AND document_id=$2 ORDER BY created_at""", tenant, document)]
        wins = [dict(r) for r in await c.fetch("""
            SELECT w.run_id::text, w.ordinal, w.status, w.blocked_reason, w.unresolved_refs::text refs
              FROM n4_extraction_windows w JOIN n4_extraction_runs r
                ON r.tenant_id=w.tenant_id AND r.run_id=w.run_id
             WHERE r.tenant_id=$1 AND r.document_id=$2 ORDER BY w.run_id, w.ordinal""", tenant, document)]
        cands = await c.fetchval("""
            SELECT count(*) FROM n4_candidate_findings f JOIN n4_extraction_runs r
              ON r.tenant_id=f.tenant_id AND r.run_id=f.run_id
             WHERE r.tenant_id=$1 AND r.document_id=$2""", tenant, document)
        rec = [dict(r) for r in await c.fetch("""
            SELECT u.status, count(*) n FROM n4_usage_reservations u JOIN n4_extraction_runs r
              ON r.tenant_id=u.tenant_id AND r.run_id=u.run_id
             WHERE r.tenant_id=$1 AND r.document_id=$2 GROUP BY u.status""", tenant, document)]
        return {"runs": runs, "windows": wins, "candidates": cands, "receipts": rec}
    finally:
        await c.close()


async def test_probe(monkeypatch):
    from src.analysis.adapters.graph import nodes
    from src.analysis.adapters.graph.workflow import route_after_risk_extraction
    from src.coherence.alert_generator import AlertGenerator
    from src.documents.adapters.http.router import _document_status_detail
    from src.documents.application.dtos import (
        document_is_retryable, document_lifecycle_status,
    )
    from src.documents.domain.models import DocumentStatus

    # ── Scenario A: references open in windows 0 and 2 ──────────────────
    authority, project, engine = await _prepare()
    text = _source()
    stub = Stub(ref_windows={0, 2})
    _env(monkeypatch, engine, stub)
    st = _state(authority, project, text)
    with bound_authority(authority):
        try:
            await bridge.run_governed_n4_in_graph(st)
            REPORT["A_bridge"] = "returned"
        except Exception as exc:  # observation
            REPORT["A_bridge"] = f"{type(exc).__name__}: {exc}"
        REPORT["A_provider_calls_first"] = list(stub.calls)
        REPORT["A_ledger_after_bridge"] = await _ledger(authority.tenant_id, authority.document_id)
        node_state = await nodes.risk_extractor_node(dict(st, messages=[], node_results=[]))
    REPORT["A_provider_calls_total_after_node"] = len(stub.calls)
    REPORT["A_node"] = {
        "extracted_risks": len(node_state.get("extracted_risks") or []),
        "workflow_terminated": node_state.get("workflow_terminated"),
        "termination_reason": node_state.get("termination_reason"),
        "analysis_blocker_code": node_state.get("analysis_blocker_code"),
        "human_approval_required": node_state.get("human_approval_required"),
        "node_results": [(r.node, str(r.status)) for r in node_state.get("node_results", [])],
        "critique_notes": (node_state.get("critique_notes") or "")[:300],
    }
    REPORT["A_route"] = route_after_risk_extraction(node_state)
    # ingestion_tasks._run_analysis_graph_best_effort whitelist (lines 1163-1170)
    blocker = node_state.get("analysis_blocker_code")
    persisted_blocker = blocker if blocker in ("N4_BUDGET_NOT_CONFIGURED", "N4_BUDGET_EXCEEDED") else None
    lifecycle = document_lifecycle_status(
        DocumentStatus.PARSED_PENDING_ANALYSIS, has_pending_review=False,
        analysis_attempt_failed=True,
    )
    REPORT["A_user_sees"] = {
        "persisted_blocker_code": persisted_blocker,
        "lifecycle": str(lifecycle),
        "retryable": document_is_retryable(lifecycle),
        "status_detail": _document_status_detail(
            DocumentStatus.PARSED_PENDING_ANALYSIS, lifecycle, 0, persisted_blocker),
    }

    # ── Scenario B: "Retry" = next generation, same document/revision ───
    c = await asyncpg.connect(DSN)
    try:
        await c.execute("SELECT set_config('app.current_tenant',$1,false)", str(authority.tenant_id))
        a2 = ProcessingAuthority(
            tenant_id=authority.tenant_id, document_id=authority.document_id,
            revision_id=authority.revision_id, generation=2, stage=authority.stage,
            attempt_id=uuid4(), owner_token=uuid4(), fencing_token=2,
        )
        await c.execute("""
            UPDATE document_processing_operations
               SET generation=2, fencing_token=2, attempt_id=$2, owner_token=$3,
                   phase='RUNNING', lease_expires_at=clock_timestamp()+interval '1 hour'
             WHERE document_id=$1""", authority.document_id, a2.attempt_id, a2.owner_token)
    finally:
        await c.close()
    calls_before = len(stub.calls)
    with bound_authority(a2):
        try:
            await bridge.run_governed_n4_in_graph(_state(a2, project, text))
            REPORT["B_bridge"] = "returned"
        except Exception as exc:
            REPORT["B_bridge"] = f"{type(exc).__name__}: {exc}"
    REPORT["B_new_provider_calls_on_retry"] = len(stub.calls) - calls_before
    REPORT["B_ledger"] = await _ledger(authority.tenant_id, authority.document_id)
    REPORT["B_note"] = "generation advanced by direct UPDATE in scratch DB, emulating reprocess; not the HTTP path"

    # ── Scenario C: no references -> COMPLETE; what severity reaches alerts ──
    a3, p3, e3 = await _prepare()
    stub3 = Stub(ref_windows=set())
    _env(monkeypatch, e3, stub3)
    with bound_authority(a3):
        out = await bridge.run_governed_n4_in_graph(_state(a3, p3, _source()))
    risks = out["extracted_risks"]
    gen = AlertGenerator.__new__(AlertGenerator)
    REPORT["C_complete"] = {
        "outcome": out["risk_extraction_outcome"],
        "risks": len(risks),
        "verified_quotes": sum(1 for r in risks if r["source_quote_status"] == "VERIFIED"),
        "not_found_quotes": sum(1 for r in risks if r["source_quote_status"] != "VERIFIED"),
        "severity_values": sorted({str(r.get("severity")) for r in risks}),
        "model_impact_kept": any("impact" in r for r in risks),
        "alert_severity_for_first": str(gen._map_risk_severity(risks[0])),
        "coverage": out["n4_incremental_window_coverage"],
    }
    with open(OUT, "w") as fh:
        json.dump(REPORT, fh, indent=2, default=str)
