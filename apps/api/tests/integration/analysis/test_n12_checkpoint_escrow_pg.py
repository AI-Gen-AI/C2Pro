"""N12 checkpoint → AIService → shared tenant escrow (REAL PG, fake model).

This proves the budget seam and replay semantics only; it does not validate
AI/N12 contractual findings or real provider pricing.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from src.analysis.adapters.ai.anthropic_client import AIService
from src.analysis.adapters.ai.n12_checkpoint_escrow_port import (
    bind_n12_checkpoint_escrow,
)
from src.analysis.domain.ai_extraction import CritiqueExtractionService
from tests.integration.analysis.test_legacy_ai_service_escrow_pg import (
    NoRetryFakeWrapper,
    _patch_sessions,
    _receipt,
)
from tests.integration.analysis.test_legacy_shared_reservations_pg import _seed

_DSN = os.environ.get("C2PRO_N4_SCRATCH_DSN", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="needs migrated real PostgreSQL *_test"),
]

SOURCE = (
    "Clause 9.6 Contractor shall deliver the goods in accordance with "
    "the specified date, subject to change orders and notice requirements."
)


class N12ResponseStub(NoRetryFakeWrapper):
    def __init__(self, *, invalid_json=False):
        super().__init__()
        self.invalid_json = invalid_json

    async def generate(self, request):
        self.calls.append(request)
        return SimpleNamespace(
            content='{"status":"OK","notes":"No issues found"}'
            if not self.invalid_json else '{"status":"OK"',
            cost_usd=0.16,
            input_tokens=450,
            output_tokens=70,
            model_used="n12-stub-model",
            cached=False,
            continuations=0,
            latency_ms=2.0,
        )


def _state(tenant, project, document, revision):
    return {
        "tenant_id": str(tenant),
        "project_id": str(project),
        "document_id": str(document),
        "document_revision_id": str(revision),
        "thread_id": "thread-" + str(uuid4()),
        "retry_count": 0,
        "doc_type": "contract",
        "extracted_risks": [
            {"title": "Delivery exception", "status": "PROPOSED"},
        ],
        "extracted_wbs": [],
    }


@pytest.mark.parametrize("invalid_json", [False, True])
@pytest.mark.parametrize("global_flag", [False, True])
async def test_n12_port_shared_escrow_replay_never_reissues_provider(
    monkeypatch, invalid_json, global_flag,
):
    authority, project = await _seed()
    engine = create_async_engine(
        _DSN.replace("postgresql://", "postgresql+asyncpg://", 1)
    )
    _patch_sessions(monkeypatch, engine)
    if global_flag:
        monkeypatch.setenv("C2PRO_LEGACY_AI_ESCROW", "1")
    else:
        # Critical: a supplied escrow ID authorizes the governed *single*
        # N12 call even while unrelated legacy graph calls remain unchanged.
        monkeypatch.delenv("C2PRO_LEGACY_AI_ESCROW", raising=False)
    monkeypatch.setenv("C2PRO_LEGACY_AI_FULLSOURCE_RESERVE_USD", "0.35")
    monkeypatch.setenv("C2PRO_LEGACY_AI_FULLSOURCE_MAX_OUTPUT_TOKENS", "2048")

    provider = N12ResponseStub(invalid_json=invalid_json)
    service = AIService(wrapper=provider, tenant_id=authority.tenant_id)
    checkpoint = _state(
        authority.tenant_id, project,
        authority.document_id, authority.revision_id,
    )
    port = bind_n12_checkpoint_escrow(
        state=checkpoint, model_safe_source=SOURCE,
        service=service, checkpoint_persisted=True,
    )
    critic = CritiqueExtractionService()
    try:
        first = await critic.extract(
            items=checkpoint["extracted_risks"],
            doc_type="contract", ai=port,
            source_text=SOURCE, source_complete=True,
        )
        assert first.status == ("UNASSESSED" if invalid_json else "OK")
        assert len(provider.calls) == 1
        assert provider.calls[0].metadata["full_source_analysis"] is True
        assert provider.calls[0].request_id

        row, tenant = await _receipt(authority.tenant_id)
        assert row["status"] == "SETTLED"
        assert tenant["ai_spend_current"] == pytest.approx(0.16)
        assert tenant["ai_spend_reserved_usd"] == 0
        assert row["input_tokens"] == 450
        assert row["output_tokens"] == 70

        # A resumed graph node will hit the very same billable attempt.
        # Domain criticism catches the transport error, returns UNASSESSED,
        # but never makes a duplicate charged provider request.
        resumed_port = bind_n12_checkpoint_escrow(
            state=dict(checkpoint), model_safe_source=SOURCE,
            service=service, checkpoint_persisted=True,
        )
        second = await critic.extract(
            items=checkpoint["extracted_risks"],
            doc_type="contract", ai=resumed_port,
            source_text=SOURCE, source_complete=True,
        )
        assert second.status == "UNASSESSED"
        assert len(provider.calls) == 1
    finally:
        await engine.dispose()
