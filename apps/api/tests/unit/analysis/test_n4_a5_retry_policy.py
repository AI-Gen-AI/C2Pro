"""Explicit candidate retry escrow, synthetic input/transport/ledger only."""
import json
from decimal import Decimal
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.adapters.ai.n4_anthropic_window_provider import AnthropicN4WindowProvider
from src.analysis.application import n4_incremental_runner as rm
from src.analysis.domain.n4_retry_policy import N4RetryPolicy
from src.core.ai import anthropic_wrapper as wm
from tests.unit.analysis.graph.test_n4_a5_bridge_limits import _MockTransportStop
from tests.unit.analysis.graph.test_n4_a5_bridge_limits import seam as seam
from tests.unit.analysis.test_n4_a5_attempt_escrow import FakeLedger, document, make_provider

D = Decimal
POLICY = N4RetryPolicy()
CALL = D("0.30")
RUN = D("6")


def candidate_provider(source, revision):
    base, windows, calls = make_provider(source, revision)
    wrapper = base.wrapper
    wrapper.enable_retry = False
    wrapper.max_tokens_limit = 16384
    wrapper.llm_client.timeout_seconds = 300
    provider = AnthropicN4WindowProvider(
        wrapper=wrapper, escrow_preflight=(CALL, windows), retry_policy=POLICY,
    )
    return provider, windows, calls


def runner(provider, *, session_factory=None, policy=POLICY, **overrides):
    options = {
        "session_factory": session_factory, "provider": provider,
        "run_cap_usd": RUN, "per_window_reservation_usd": CALL,
        "period_key": "2026-11", "enabled": True, "retry_policy": policy,
    }
    options.update(overrides)
    return rm.N4IncrementalRunner(**options)


def test_default_hash_unchanged_and_no_implicit_opt_in():
    provider, windows, _ = make_provider(document(), uuid4())
    r = runner(provider, policy=None)
    expected = {
        "prompt": provider.prompt_version, "model": provider.model_name,
        "window_chars": 12000, "overlap": 400,
        "attempt_escrow": provider.escrow_policy(),
    }
    assert "retry_policy" not in expected["attempt_escrow"]
    assert r.config_sha256 == sha256(json.dumps(
        expected, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    assert r._reservation_for_attempt(windows[0], 1) <= CALL
    with pytest.raises(rm.N4BudgetError):
        r._reservation_for_attempt(windows[0], 2)


def test_explicit_matching_policy_and_distinct_identity():
    revision = uuid4()
    provider, _, _ = candidate_provider(document(), revision)
    old, _, _ = make_provider(document(), revision)
    r = runner(provider)
    assert r.config_sha256 != runner(old, policy=None).config_sha256
    with pytest.raises(ValueError, match="explicit and identical"):
        runner(provider, policy=None)
    with pytest.raises(ValueError, match="explicit and identical"):
        runner(old)
    with pytest.raises(ValueError, match="Unsupported"):
        N4RetryPolicy(version="unapproved")


@pytest.mark.parametrize("override", [
    {"run_cap_usd": D("6.000001")}, {"per_window_reservation_usd": D("0.40")},
    {"max_attempts": 4}, {"max_context_chars": 12001},
])
def test_a13_limits_cannot_increase(override):
    provider, _, _ = candidate_provider(document(), uuid4())
    with pytest.raises(ValueError, match="violates A13"):
        runner(provider, **override)


@pytest.mark.parametrize("lang", ["en", "es", "pt"])
def test_representative_12k_first_and_retry_fundable(lang):
    source = document(lang)
    assert len(source) == 12000
    provider, windows, calls = candidate_provider(source, uuid4())
    r = runner(provider)
    assert max(len(w.context_text) for w in windows) >= 11000
    for w in windows:
        one = provider.estimate_attempt(w, attempt=1)
        two = provider.estimate_attempt(w, attempt=2)
        assert one[1] == 8192 and two[1] == 16384
        assert one[2] <= CALL < two[2] <= D("0.40")
        assert r._reservation_for_attempt(w, 1) == one[2]
        assert r._reservation_for_attempt(w, 2) == two[2]
        print(lang, len(w.context_text), one[0], one[2], two[0], two[2])
    assert not calls


@pytest.mark.parametrize("attempt,limit", [(1, CALL), (2, D("0.40")), (3, D("0.40"))])
def test_exact_policy_ceiling_no_rounding_escape(monkeypatch, attempt, limit):
    provider, windows, _ = candidate_provider(document(), uuid4())
    r = runner(provider)
    monkeypatch.setattr(provider, "estimate_attempt", lambda w, **kw: (1, 8192, limit))
    assert r._reservation_for_attempt(windows[0], attempt) == limit
    monkeypatch.setattr(provider, "estimate_attempt",
                        lambda w, **kw: (1, 8192, limit+D("0.000001")))
    with pytest.raises(rm.N4BudgetError):
        r._reservation_for_attempt(windows[0], attempt)
    monkeypatch.setattr(provider, "reservation_for_attempt", lambda *a, **kw: limit+D("0.000001"))
    with pytest.raises(rm.N4BudgetError):
        r._reservation_for_attempt(windows[0], attempt)


def test_adversarial_unicode_is_not_silently_truncated():
    from src.analysis.domain.n4_source_windows import plan_n4_source_windows
    provider, _, calls = candidate_provider(document(), uuid4())
    source = "Clause 1: " + chr(0x1F680)*11990
    windows = plan_n4_source_windows(source, revision_id=str(uuid4()), max_context_chars=12000,
                                     overlap_chars=400)
    w = windows[0]
    tokens, cap, amount = provider.estimate_attempt(w, attempt=1)
    assert tokens >= len(w.context_text.encode("utf-8")) and cap == 8192
    assert amount > CALL
    with pytest.raises(rm.N4BudgetError):
        runner(provider)._reservation_for_attempt(w, 1)
    assert not calls


@pytest.mark.asyncio
@pytest.mark.parametrize("attempt,cap", [(1, 8192), (2, 16384)])
async def test_real_wrapper_request_and_exact_escaped_envelope(seam, attempt, cap):
    _, authority, created, calls = seam
    source = document("es")
    from src.analysis.domain.n4_source_windows import plan_n4_source_windows
    windows = plan_n4_source_windows(source, revision_id=str(authority.revision_id),
                                     max_context_chars=12000, overlap_chars=400)
    wrapper = wm.AnthropicWrapper(
        enable_cache=False, enable_retry=False, max_tokens_limit=16384, timeout_seconds=300,
    )
    provider = AnthropicN4WindowProvider(
        wrapper=wrapper, escrow_preflight=(CALL, windows), retry_policy=POLICY,
    )
    window = windows[0]
    tokens, _, quote = provider.estimate_attempt(window, attempt=attempt)
    with pytest.raises(_MockTransportStop):
        await provider.generate(
            window=window, tenant_id=authority.tenant_id, request_id=str(uuid4()),
            attempt=attempt, reservation_usd=quote,
        )
    assert len(calls) == len(created) == 1
    assert created[0].max_retries == 0 and created[0].timeout_seconds == 300
    req = calls[0]
    assert req.max_tokens == cap
    assert window.context_text in req.messages[0]["content"]
    assert "n4_reserved_usd" not in req.metadata
    assert req.metadata["n4_disable_fallback"] is True
    assert req.metadata["n4_retry_policy_version"] == POLICY.version
    payload = {
        "model": req.model, "max_tokens": req.max_tokens, "temperature": req.temperature,
        "stop_sequences": req.stop_sequences or [], "system": req.system or "",
        "messages": req.messages, "tools": req.tools, "tool_choice": req.tool_choice,
    }
    assert tokens == len(json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode())+2048


def setup_retry_run(monkeypatch):
    source = document("es")
    authority = SimpleNamespace(tenant_id=uuid4(), revision_id=uuid4())
    provider, windows, calls = candidate_provider(source, authority.revision_id)
    ledger = FakeLedger(monkeypatch)
    original_generate = provider.wrapper.generate

    async def after_commit(req):
        assert not ledger.in_tx
        assert ledger.prior[0][-1] == "RESERVED"
        return await original_generate(req)

    async def retryable(session, **kwargs):
        return {
            o for o, state in ledger.statuses.items()
            if state == "BLOCKED" and len(ledger.prior[o]) < kwargs["max_attempts"]
            and not any(s in ("UNKNOWN", "RESERVED") for s in ledger.prior[o])
        }

    provider.wrapper.generate = after_commit
    monkeypatch.setattr(rm, "retryable_windows", retryable)
    r = runner(provider, session_factory=ledger.session)
    kw = {"authority": authority, "project_id": uuid4(), "model_safe_text": source,
          "n2_projection_attested": True}
    return r, kw, ledger, provider, windows, calls


@pytest.mark.asyncio
@pytest.mark.parametrize("sufficient", [False, True])
async def test_fresh_retry_reservation_checks_remaining_balance(monkeypatch, sufficient):
    r, kw, ledger, provider, windows, calls = setup_retry_run(monkeypatch)
    first = await r.run(**kw)
    assert first.stopped_reason == "INVALID_PROVIDER_ENVELOPE"
    assert len(calls) == len(ledger.reserves) == len(ledger.accounts) == 1
    initial = provider.estimate_attempt(windows[0], attempt=1)[2]
    retry = provider.estimate_attempt(windows[0], attempt=2)[2]
    assert ledger.reserves[0][1] == initial <= CALL
    assert ledger.remaining == RUN-D("0.06")
    remaining = retry if sufficient else retry-D("0.000001")
    ledger.remaining = remaining
    result = await r.run(**kw)
    assert len(ledger.reserves) == 2
    assert ledger.reserves[1][1] == retry > CALL
    assert ledger.reserves[1][0] != ledger.reserves[0][0]
    if sufficient:
        assert result.stopped_reason == "INVALID_PROVIDER_ENVELOPE"
        assert len(calls) == len(ledger.accounts) == 2
        assert calls[-1].max_tokens == 16384
        assert calls[-1].request_id != calls[0].request_id
        assert ledger.remaining == remaining-D("0.06")
    else:
        assert result.stopped_reason == "N4BudgetError"
        assert len(calls) == len(ledger.accounts) == 1
        assert ledger.remaining == remaining


@pytest.mark.asyncio
async def test_retry_policy_drift_before_db_or_transport(monkeypatch):
    r, kw, ledger, provider, _, calls = setup_retry_run(monkeypatch)
    r.run_cap = D("7")
    with pytest.raises(ValueError, match="pinned retry policy"):
        await r.run(**kw)
    assert not calls and not ledger.reserves
    r.run_cap = RUN
    provider.wrapper.llm_client.timeout_seconds = 75
    with pytest.raises(rm.N4BudgetError):
        r._reservation_for_attempt(rm.plan_n4_source_windows(
            kw["model_safe_text"], revision_id=str(kw["authority"].revision_id),
        )[0], 1)
    assert not calls and not ledger.reserves


@pytest.mark.asyncio
async def test_unknown_prior_never_funds_retry(monkeypatch):
    r, kw, ledger, _, _, calls = setup_retry_run(monkeypatch)
    await r.run(**kw)
    ledger.prior[0][-1] = "UNKNOWN"
    remaining = ledger.remaining
    result = await r.run(**kw)
    assert result.stopped_reason == "OPEN_LIABILITY_REQUIRES_RECONCILIATION"
    assert len(calls) == len(ledger.reserves) == 1 and ledger.remaining == remaining


@pytest.mark.asyncio
async def test_replayed_reservation_never_reissues_transport(monkeypatch):
    r, kw, ledger, _, _, calls = setup_retry_run(monkeypatch)
    await r.run(**kw)

    async def replay(session, **kwargs):
        return SimpleNamespace(reservation_id=uuid4(), replay=True)

    monkeypatch.setattr(rm, "reserve_call", replay)
    remaining = ledger.remaining
    result = await r.run(**kw)
    assert result.stopped_reason == "EXISTING_RESERVATION_REQUIRES_RECONCILIATION"
    assert len(calls) == len(ledger.accounts) == 1 and ledger.remaining == remaining


@pytest.mark.asyncio
async def test_known_retry_overage_is_settled_not_accepted(monkeypatch):
    r, kw, ledger, provider, _, calls = setup_retry_run(monkeypatch)
    await r.run(**kw)

    async def overage(req):
        assert not ledger.in_tx
        calls.append(req)
        return SimpleNamespace(
            content="{}", raw_response=None, model_used=provider.model_name,
            cost_usd=0.41, input_tokens=50000, output_tokens=16384,
            request_id=req.request_id,
        )

    monkeypatch.setattr(provider.wrapper, "generate", overage)
    result = await r.run(**kw)
    assert result.stopped_reason == "ATTEMPT_ESCROW_EXCEEDED"
    assert len(ledger.accounts) == len(calls) == 2
    assert ledger.accounts[-1]["billed_usd"] == D("0.41")
    assert ledger.remaining == RUN-D("0.06")-D("0.41")
    assert ledger.statuses[0] == "BLOCKED"


def test_a13_attempt_ceiling_even_with_canceled_reservation_count():
    provider, windows, _ = candidate_provider(document(), uuid4())
    r = runner(provider)
    with pytest.raises(rm.N4BudgetError):
        r._reservation_for_attempt(windows[0], 4)

@pytest.mark.asyncio
async def test_real_wrapper_preserves_measured_error_without_global_fallback(seam, monkeypatch):
    from src.analysis.domain.n4_source_windows import plan_n4_source_windows
    from src.core.ai import direct_provider_fallback as df
    from src.core.ai.llm_client import LLMPartialGenerationError

    _, authority, _, _ = seam
    windows = plan_n4_source_windows(document(), revision_id=str(authority.revision_id),
                                     max_context_chars=12000, overlap_chars=400)
    wrapper = wm.AnthropicWrapper(
        enable_cache=False, enable_retry=False, max_tokens_limit=16384, timeout_seconds=300,
    )
    provider = AnthropicN4WindowProvider(
        wrapper=wrapper, escrow_preflight=(CALL, windows), retry_policy=POLICY,
    )
    error = LLMPartialGenerationError(
        "synthetic partial", model=provider.model_name,
        input_tokens=1000, output_tokens=100, cost_usd=0.0045,
    )
    calls = []

    async def partial(request):
        calls.append(request)
        raise error

    async def forbidden(*args, **kwargs):
        pytest.fail("candidate must not enter fallback")

    monkeypatch.setenv("C2PRO_DIRECT_FALLBACK_ENABLED", "1")
    monkeypatch.setattr(wrapper.llm_client, "generate", partial)
    monkeypatch.setattr(df, "fallback_after_unbilled_rejection", forbidden)
    with pytest.raises(LLMPartialGenerationError) as caught:
        await provider.generate(
            window=windows[0], tenant_id=authority.tenant_id, request_id=str(uuid4()),
            attempt=2, reservation_usd=provider.reservation_for_attempt(windows[0], attempt=2, ceiling=CALL),
        )
    assert caught.value is error and caught.value.cost_usd == 0.0045 and len(calls) == 1


@pytest.mark.asyncio
async def test_measured_retry_exception_settles_preserves_identity(monkeypatch):
    from src.core.ai.llm_client import LLMPartialGenerationError
    r, kw, ledger, provider, _, calls = setup_retry_run(monkeypatch)
    await r.run(**kw)

    async def partial(req):
        calls.append(req)
        raise LLMPartialGenerationError(
            "synthetic partial", model=provider.model_name,
            input_tokens=1000, output_tokens=100, cost_usd=0.0045,
        )

    monkeypatch.setattr(provider.wrapper, "generate", partial)
    result = await r.run(**kw)
    assert result.stopped_reason == "PROVIDER_RESULT_UNCERTAIN"
    receipt = ledger.accounts[-1]
    assert receipt["billed_usd"] == D("0.0045")
    assert receipt["actual_provider"] == "anthropic" and receipt["actual_model_name"] == provider.model_name
    assert receipt["input_tokens"] == 1000 and receipt["output_tokens"] == 100
    assert len(calls) == len(ledger.accounts) == 2
