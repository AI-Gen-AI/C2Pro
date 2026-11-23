"""One-shot A3@49870fdb + A5@6dd63bb9 compatibility (disposable only).

Synthetic wrapper: ZERO real LLM requests. This file is NOT part of either PR.
Requires private migrated PostgreSQL16 *_test pointed by C2PRO_N4_SCRATCH_DSN.
"""
from __future__ import annotations

import asyncio
import json
import os
from decimal import Decimal
from types import SimpleNamespace

import asyncpg
import pytest

from src.analysis.adapters.ai.n4_anthropic_window_provider import AnthropicN4WindowProvider
from src.analysis.adapters.persistence.n4_incremental_store import N4LedgerError
from src.analysis.domain.n4_clause_inventory import build_n4_clause_inventory
from src.analysis.domain.n4_compact_window_response import (
    N4_WINDOW_PROMPT_VERSION,
)
from src.core.ai.model_router import ModelTier
from src.core.processing_authority import ProcessingAuthorityLost
from tests.integration.analysis.test_n4_window_runner_pg import (
    _balances, _prepare, _runner,
)
from tests.integration.analysis.test_n4_ledger_retries_pg import _advance_generation

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")
assert _DSN.endswith("_test"), "NO tests without explicit *_test scratch DSN"
SOURCE_QUOTE = "9.6 The supplier shall deliver the synthetic equipment by 30 June."
SOURCE = SOURCE_QUOTE + "\nThis is test-only text, not a real contract or risk."


class SyntheticA5Wrapper:
    """Deterministic substitute for AnthropicWrapper.generate (never network)."""

    def __init__(self, modes=None):
        self.llm_client = SimpleNamespace(max_retries=0)
        self.enable_cache = False
        self.cache_service = None
        self.model_router = SimpleNamespace(configs={
            ModelTier.STANDARD: SimpleNamespace(name="unit-n4-synthetic-model"),
        })
        self.modes = list(modes or ["valid"])
        self.calls = []
        self.started = None
        self.release = None

    async def generate(self, request):
        self.calls.append(request)
        if self.started is not None:
            self.started.set()
        if self.release is not None:
            await self.release.wait()
        mode = self.modes.pop(0) if self.modes else "valid"
        assert request.tool_choice == {"type": "tool", "name": "record_window_findings"}
        assert request.metadata["prompt_version"] == N4_WINDOW_PROMPT_VERSION
        assert request.request_id
        assert request.use_cache is False
        assert request.bypass_anonymization is True
        # The entire synthetic N2 source, not a keyword subset, is supplied.
        assert SOURCE_QUOTE in request.prompt
        source = request.prompt.split(
            "--- BEGIN UNTRUSTED SOURCE WINDOW ---\n", 1,
        )[1].split("\n--- END UNTRUSTED SOURCE WINDOW ---", 1)[0]
        detected = build_n4_clause_inventory(source)
        payload = {
            "window_examined": True,
            "findings": [{
                "title": "Synthetic delivery exposure",
                "category": "LEGAL",
                "epc_control_id": "EPC-07",
                "severity_proposed": "HIGH",
                "risk_reason": "Candidate only: requires human verification.",
                "source_quote": SOURCE_QUOTE,
                "clause_ref": "9.6",
                "supporting_quotes": [],
            }],
            "examined_clauses": [
                {"clause_ref": c.clause_ref, "examined": True, "has_risk": True}
                for c in detected
            ],
            "outstanding_references": [],
        }
        raw = json.dumps(payload, ensure_ascii=False)
        if mode == "truncated_json":
            raw = '{"window_examined":true,"findings":['
        return SimpleNamespace(
            content=raw, model_used="unit-n4-synthetic-model",
            cost_usd=0.02, input_tokens=135, output_tokens=90,
            raw_response=SimpleNamespace(
                stop_reason="tool_use",
                content=[SimpleNamespace(
                    type="tool_use",
                    name=("untrusted_tool" if mode == "wrong_tool" else "record_window_findings"),
                    input=payload,
                )],
            ),
            request_id=request.request_id,
        )


@pytest.mark.asyncio
async def test_a3_a5_v2_tool_rejection_paid_retry_and_literal_n2_without_double_charge():
    authority, project, engine = await _prepare()
    wrapper = SyntheticA5Wrapper(modes=["wrong_tool", "valid"])
    provider = AnthropicN4WindowProvider(wrapper=wrapper)
    v2 = _runner(engine, provider)

    class V1:
        model_name = provider.model_name
        prompt_version = "n4-compact-window-v1"

    v1 = _runner(engine, V1())
    assert v1.config_sha256 != v2.config_sha256
    assert v2.prompt_version == N4_WINDOW_PROMPT_VERSION
    assert _runner(engine, provider).config_sha256 == v2.config_sha256
    try:
        first = await v2.run(
            authority=authority, project_id=project,
            model_safe_text=SOURCE, n2_projection_attested=True,
        )
        assert first.status == "PARTIAL"
        assert first.examined_windows == 0
        assert len(wrapper.calls) == 1

        resumed = await v2.run(
            authority=authority, project_id=project,
            model_safe_text=SOURCE, n2_projection_attested=True,
        )
        assert resumed.run_id == first.run_id
        assert resumed.status == "COMPLETE"
        assert resumed.examined_windows == 1
        assert len(wrapper.calls) == 2
        assert wrapper.calls[0].request_id != wrapper.calls[1].request_id
        assert wrapper.calls[0].max_tokens == 8192
        assert wrapper.calls[1].max_tokens == 16384

        conn = await asyncpg.connect(_DSN)
        try:
            receipts = await conn.fetch(
                """SELECT status, spent_usd, idempotency_key
                   FROM public.n4_usage_reservations
                   WHERE tenant_id=$1 AND run_id=$2 AND window_ordinal=0
                   ORDER BY created_at, reservation_id""",
                authority.tenant_id, first.run_id,
            )
            window_row = await conn.fetchrow(
                """SELECT status, committed_at, findings_sha256
                   FROM public.n4_extraction_windows
                   WHERE tenant_id=$1 AND run_id=$2 AND ordinal=0""",
                authority.tenant_id, first.run_id,
            )
            assert window_row["status"] == "EXAMINED"
            assert window_row["committed_at"] is not None
            assert window_row["findings_sha256"] is not None
            candidates = await conn.fetch(
                """SELECT claim, source_refs FROM public.n4_candidate_findings
                   WHERE tenant_id=$1 AND run_id=$2""",
                authority.tenant_id, first.run_id,
            )
            assert len(candidates) == 1
            claim = candidates[0]["claim"]
            refs = candidates[0]["source_refs"]
            claim = json.loads(claim) if isinstance(claim, str) else claim
            refs = json.loads(refs) if isinstance(refs, str) else refs
            assert claim["review_status"] == "PROPOSED"
            assert claim["source_quote"] == SOURCE_QUOTE
            assert claim["source_evidence_status"] == "EXACT_MODEL_SAFE_MATCH"
            assert claim["quote_omits_figures"] is False
            assert refs[0]["source_kind"] == "MODEL_SAFE_PROJECTION"
            assert refs[0]["analysis_span"] == [0, len(SOURCE_QUOTE)]
            assert len(receipts) == 2
            assert [row["status"] for row in receipts] == ["SETTLED", "SETTLED"]
            assert len({row["idempotency_key"] for row in receipts}) == 2
            assert [Decimal(row["spent_usd"]) for row in receipts] == [
                Decimal("0.02"), Decimal("0.02"),
            ]
            # Real DB-projected finding details are assessed separately by the
            # existing A3 PG tests. No contract semantics are approved here.
        finally:
            await conn.close()
        balance = await _balances(authority.tenant_id)
        assert Decimal(balance["reserved_usd"]) == 0
        assert Decimal(balance["spent_usd"]) == Decimal("0.04")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a3_a5_fencing_inflight_does_not_trigger_second_provider_call():
    authority, project, engine = await _prepare()
    wrapper = SyntheticA5Wrapper()
    wrapper.started = asyncio.Event()
    wrapper.release = asyncio.Event()
    provider = AnthropicN4WindowProvider(wrapper=wrapper)
    runner = _runner(engine, provider)
    task = asyncio.create_task(runner.run(
        authority=authority, project_id=project,
        model_safe_text=SOURCE, n2_projection_attested=True,
    ))
    try:
        await asyncio.wait_for(wrapper.started.wait(), timeout=12)
        upgraded = await _advance_generation(authority)
        wrapper.release.set()
        with pytest.raises((ProcessingAuthorityLost, N4LedgerError)):
            await asyncio.wait_for(task, timeout=20)
        assert len(wrapper.calls) == 1
        before = await _balances(authority.tenant_id)
        second = await _runner(engine, provider).run(
            authority=upgraded, project_id=project,
            model_safe_text=SOURCE, n2_projection_attested=True,
        )
        assert second.stopped_reason == "EXISTING_RESERVATION_REQUIRES_RECONCILIATION"
        assert len(wrapper.calls) == 1
        assert await _balances(authority.tenant_id) == before
    finally:
        wrapper.release.set()
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await engine.dispose()


@pytest.mark.asyncio
async def test_a3_a5_truncated_json_is_settled_and_never_certified_as_evidence():
    authority, project, engine = await _prepare()
    wrapper = SyntheticA5Wrapper(["truncated_json"])
    provider = AnthropicN4WindowProvider(wrapper=wrapper)
    try:
        outcome = await _runner(engine, provider).run(
            authority=authority, project_id=project,
            model_safe_text=SOURCE, n2_projection_attested=True,
        )
        assert outcome.status == "PARTIAL"
        assert outcome.examined_windows == 0
        assert len(wrapper.calls) == 1
        balance = await _balances(authority.tenant_id)
        assert Decimal(balance["spent_usd"]) == Decimal("0.02")
        assert Decimal(balance["reserved_usd"]) == 0
    finally:
        await engine.dispose()
