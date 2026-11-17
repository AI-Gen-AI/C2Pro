"""Non-billable identity/adapter guards for staged Coherence escrow."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.coherence.adapters.ai.coherence_governed_wrapper import (
    BudgetedCoherenceWrapper,
    CoherenceCallIdentity,
    CoherenceEscrowIdentityError,
)
from src.coherence.adapters.ai.coherence_llm_gate import CoherenceLlmGate
from src.coherence.models import Clause
from src.core.ai.anthropic_wrapper import AIRequest
from src.core.ai.model_router import AITaskType

SHA = "a" * 64


def _identity(**changes):
    identity = CoherenceCallIdentity(
        tenant_id=uuid4(), project_id=uuid4(), document_id=uuid4(),
        revision_id=uuid4(), run_id=uuid4(), source_sha256=SHA,
    )
    return replace(identity, **changes)


@pytest.mark.parametrize("field", [
    "tenant_id", "project_id", "document_id", "revision_id", "run_id",
])
def test_identity_rejects_non_uuid_context(field):
    with pytest.raises(CoherenceEscrowIdentityError, match="UUID"):
        _identity(**{field: str(uuid4())})


@pytest.mark.parametrize("bad", ["", "ABCDEF", "a" * 63, "Z" * 64])
def test_identity_rejects_unknown_source_digest(bad):
    with pytest.raises(CoherenceEscrowIdentityError, match="SHA"):
        _identity(source_sha256=bad)


@pytest.mark.parametrize("bad", [-1, 16, True, "0"])
def test_identity_rejects_untrusted_attempt_index(bad):
    with pytest.raises(CoherenceEscrowIdentityError, match="attempt"):
        _identity(attempt_index=bad)


def test_request_id_binding_and_no_plain_source():
    identity = _identity()
    args = {
        "rule_id": "R-SCOPE-CLARITY-01", "clause_id": "2.1",
        "clause_text": "Provider performs time-sensitive service.",
        "rule_input_hash": "f" * 64,
    }
    key = identity.request_key(**args)
    assert key == identity.request_key(**args)
    assert len(key) == 68 and key.startswith("coh-")
    assert "Provider" not in key
    assert key != identity.request_key(**{**args, "clause_text": "different"})
    assert key != replace(identity, attempt_index=1).request_key(**args)
    assert key != replace(identity, revision_id=uuid4()).request_key(**args)


class NoRetryProvider:
    enable_cache = False
    cache_service = None
    llm_client = SimpleNamespace(max_retries=0)
    async def generate(self, request):
        raise AssertionError("no network before reserve")


def test_budgeted_wrapper_rejects_bad_escrow_settings():
    identity = _identity()
    key = identity.request_key(
        rule_id="A", clause_id="B", clause_text="C",
        rule_input_hash="f" * 64,
    )
    for amount in ("", "0", "-1", "Infinity", "NaN"):
        with pytest.raises(CoherenceEscrowIdentityError):
            BudgetedCoherenceWrapper(
                identity=identity, governed_request_id=key,
                max_charge_usd=amount, max_output_tokens=2048,
                underlying=NoRetryProvider(),
            )


def test_budgeted_wrapper_rejects_caching_or_retrying_provider():
    identity = _identity()
    key = identity.request_key(
        rule_id="A", clause_id="B", clause_text="C",
        rule_input_hash="f" * 64,
    )
    for override in (
        {"enable_cache": True},
        {"cache_service": object()},
        {"llm_client": SimpleNamespace(max_retries=3)},
    ):
        unsafe = SimpleNamespace(
            enable_cache=False, cache_service=None,
            llm_client=SimpleNamespace(max_retries=0),
            **{},
        )
        for name, value in override.items():
            setattr(unsafe, name, value)
        with pytest.raises(CoherenceEscrowIdentityError, match="retry or cache"):
            BudgetedCoherenceWrapper(
                identity=identity, governed_request_id=key,
                max_charge_usd="0.3", max_output_tokens=2048, underlying=unsafe,
            )


@pytest.mark.asyncio
async def test_coherence_flag_without_trusted_context_refuses_before_provider(monkeypatch):
    monkeypatch.setenv("C2PRO_COHERENCE_ESCROW", "1")
    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "100")
    class MissCache:
        async def get(self, _key): return None

    gate = CoherenceLlmGate()
    gate._cache = MissCache()
    with pytest.raises(RuntimeError, match="trusted run"):
        await gate.evaluate_rule(
            str(uuid4()), "R-SCOPE-CLARITY-01",
            Clause(id="1", text="Provider may revise the deliverable.", data={}),
        )


@pytest.mark.asyncio
async def test_budgeted_wrapper_rejects_wrong_tenant_or_pii_bypass(monkeypatch):
    identity = _identity()
    key = identity.request_key(
        rule_id="A", clause_id="B", clause_text="C", rule_input_hash="f" * 64,
    )
    wrapper = BudgetedCoherenceWrapper(
        identity=identity, governed_request_id=key,
        max_charge_usd="0.3", max_output_tokens=2048,
        underlying=NoRetryProvider(),
    )
    request = AIRequest(
        prompt="C", task_type=AITaskType.COHERENCE_CHECK,
        tenant_id=uuid4(),
    )
    with pytest.raises(CoherenceEscrowIdentityError, match="tenant"):
        await wrapper.generate(request)
    request.tenant_id = identity.tenant_id
    request.bypass_anonymization = True
    with pytest.raises(CoherenceEscrowIdentityError, match="PII"):
        await wrapper.generate(request)
