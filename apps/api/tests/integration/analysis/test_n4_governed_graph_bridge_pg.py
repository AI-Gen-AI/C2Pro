"""N4 production graph seam with disposable PostgreSQL and stub provider.

The test validates the actual state-to-ledger-to-risk mapping end-to-end; the
model output itself is synthetic and cannot establish semantic quality.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.analysis.adapters.graph import n4_governed_bridge as bridge
from src.analysis.application.n4_incremental_runner import N4ProviderReceipt
from src.core.processing_authority import bound_authority
from tests.integration.analysis.test_n4_window_runner_pg import (
    _prepare, _source,
)

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires migrated disposable *_test PostgreSQL"),
]


class MockSourceWindowProvider:
    model_name = "mock-source-window-model"
    fallback_reservation_usd = None
    approved_fallback_models = frozenset()
    fallback_routes = ()

    def __init__(self):
        self.calls: list[int] = []

    async def generate(self, *, window, tenant_id, request_id):
        self.calls.append(window.ordinal)
        quote = window.context_text[: min(65, len(window.context_text))]
        return N4ProviderReceipt(
            content=__import__("json").dumps({
                "window_examined": True,
                "findings": [{
                    "title": f"Contract obligation in window {window.ordinal}",
                    "category": "contractual",
                    "risk_reason": "Provisional obligation interpretation; needs human/legal verification",
                    "source_quote": quote,
                    "clause_ref": f"p.{window.ordinal}",
                    "impact": "Requires owner notice if delayed",
                }],
                "outstanding_references": [],
            }),
            model_used=self.model_name,
            reported_cost_usd="0.020000",
            input_tokens=140,
            output_tokens=80,
            provider_request_id=request_id,
        )


async def test_graph_bridge_persists_retrieves_exact_revision_candidates_without_duplication(
    monkeypatch,
):
    authority, project, engine = await _prepare()
    provider = MockSourceWindowProvider()
    original = _source()
    state = {
        "tenant_id": str(authority.tenant_id),
        "project_id": str(project),
        "document_id": str(authority.document_id),
        "document_revision_id": str(authority.revision_id),
        "document_text": original,
        "anonymized_text": original,
        "pii_anonymization_complete": True,
        "n12_source_attestation": {
            "tenant_id": str(authority.tenant_id),
            "project_id": str(project),
            "document_id": str(authority.document_id),
            "revision_id": str(authority.revision_id),
            "parsed_text_sha256": sha256(original.encode("utf-8")).hexdigest(),
            "blob_hash": "a" * 64,
        },
    }
    monkeypatch.setenv("C2PRO_N4_GRAPH_LEDGER_ENABLED", "1")
    monkeypatch.setenv("C2PRO_N4_GRAPH_RUN_USD", "1.000000")
    monkeypatch.setenv("C2PRO_N4_GRAPH_WINDOW_USD", "0.040000")
    monkeypatch.setenv("C2PRO_N4_GRAPH_WINDOW_CHARS", "1000")
    monkeypatch.setenv("C2PRO_N4_GRAPH_OVERLAP_CHARS", "50")
    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ENABLED", "0")
    monkeypatch.delenv("C2PRO_AI_MOCK", raising=False)
    monkeypatch.setattr(bridge, "AnthropicWrapper", lambda **kwargs: object())
    monkeypatch.setattr(bridge, "AnthropicN4WindowProvider", lambda **kwargs: provider)
    monkeypatch.setattr(
        bridge, "get_session_factory",
        lambda: async_sessionmaker(engine, expire_on_commit=False),
    )
    try:
        with bound_authority(authority):
            first = await bridge.run_governed_n4_in_graph(state)
            replay = await bridge.run_governed_n4_in_graph(state)

        assert first["risk_extraction_outcome"] == "PROPOSED_NOT_VERIFIED"
        assert len(first["extracted_risks"]) == len(first["n4_candidate_provenance"])
        assert len(first["extracted_risks"]) >= 2
        assert first["extracted_risks"] == replay["extracted_risks"]
        assert first["n4_incremental_run_id"] == replay["n4_incremental_run_id"]
        assert len(provider.calls) == len(first["extracted_risks"])
        assert all(r["source_quote"] for r in first["extracted_risks"])
        assert all(r["source_quote_status"] == "VERIFIED" for r in first["extracted_risks"])
        assert all(r["severity"] is None for r in first["extracted_risks"])
        assert all(r["confidence"] is None for r in first["extracted_risks"])
        assert first["n4_incremental_window_coverage"]["original_document_completeness_certified"] is False
        assert first["n4_incremental_window_coverage"]["semantic_recall_certified"] is False
        assert first["confidence_score"] is None
        assert first["human_approval_required"] is True

        conn = await asyncpg.connect(_DSN)
        try:
            await conn.execute(
                "SELECT set_config('app.current_tenant', $1, false)",
                str(authority.tenant_id),
            )
            result = await conn.fetchrow("""
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE status='SETTLED') AS settled
                  FROM public.n4_usage_reservations
                 WHERE tenant_id=$1
            """, authority.tenant_id)
            assert result["total"] == len(provider.calls)
            assert result["settled"] == result["total"]
        finally:
            await conn.close()
    finally:
        await engine.dispose()
