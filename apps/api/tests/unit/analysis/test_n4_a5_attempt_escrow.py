"""A13 budget regression; only synthetic documents and fake transactional IO."""
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from src.analysis.adapters.ai.n4_anthropic_window_provider import AnthropicN4WindowProvider
from src.analysis.application import n4_incremental_runner as runner_module
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.core.ai.model_router import ModelTier

D = Decimal
CALL = D("0.30")
RUN = D("6")
SAMPLES = {
    "en": "The contractor shall deliver equipment, report delays and maintain a 24 month warranty. ",
    "es": "El contratista debera entregar equipos, informar retrasos y mantener una garantia de 24 meses. ",
    "pt": "A contratada devera entregar equipamentos, comunicar atrasos e manter garantia de 24 meses. ",
}
SAMPLES["es"] = SAMPLES["es"].replace("debera", "deberá").replace("garantia", "garantía")
SAMPLES["pt"] = SAMPLES["pt"].replace("devera", "deverá")


def document(lang="en"):
    text = "".join(
        f"\nClause {n}.\n" + SAMPLES[lang] * 5 for n in range(1, 35)
    )
    return text[:12000]


def make_provider(source, revision, *, ceiling=CALL):
    cfg = yaml.safe_load(Path("src/core/ai/model_routing.yaml").read_text())["models"]["standard"]
    calls = []

    async def generate(req):
        calls.append(req)
        return SimpleNamespace(
            content="{}", raw_response=None, model_used=cfg["name"],
            cost_usd=0.06, input_tokens=2000, output_tokens=100,
            request_id=req.request_id,
        )

    wrapper = SimpleNamespace(
        model_router=SimpleNamespace(configs={ModelTier.STANDARD: SimpleNamespace(**cfg)}),
        llm_client=SimpleNamespace(max_retries=0), enable_cache=False, cache_service=None,
        generate=generate,
    )
    windows = plan_n4_source_windows(source, revision_id=str(revision),
                                     max_context_chars=12000, overlap_chars=400)
    return AnthropicN4WindowProvider(
        wrapper=wrapper, escrow_preflight=(ceiling, windows),
    ), windows, calls


@pytest.mark.parametrize("lang", ["en", "es", "pt"])
def test_a13_first_attempt_representative_12k(lang):
    source = document(lang)
    assert len(source) == 12000
    provider, windows, calls = make_provider(source, uuid4())
    assert max(len(w.context_text) for w in windows) >= 11000
    for w in windows:
        tokens, cap, amount = provider.estimate_attempt(w, attempt=1)
        assert tokens >= len(w.context_text.encode("utf-8"))
        assert cap == 8192 and D("0") < amount <= CALL
        assert provider.reservation_for_attempt(w, attempt=1, ceiling=CALL) == amount
        tokens2, cap2, amount2 = provider.estimate_attempt(w, attempt=2)
        assert tokens2 >= tokens and cap2 == 16384 and amount2 > CALL
        with pytest.raises(ValueError, match="worst-case"):
            provider.reservation_for_attempt(w, attempt=2, ceiling=CALL)
        print(lang, "chars", len(w.context_text), "input_bound", tokens,
              "first", amount, "retry", amount2)
    assert not calls


@pytest.mark.asyncio
async def test_exact_committed_attempt_amount_required_and_policy_drift():
    provider, windows, calls = make_provider(document(), uuid4())
    window = windows[0]
    quote = provider.reservation_for_attempt(window, attempt=1, ceiling=CALL)
    with pytest.raises(ValueError, match="exact committed"):
        await provider.generate(window=window, tenant_id=uuid4(), request_id=str(uuid4()),
                                reservation_usd=quote - D("0.000001"))
    with pytest.raises(ValueError, match="worst-case"):
        await provider.generate(window=window, tenant_id=uuid4(), request_id=str(uuid4()),
                                reservation_usd=CALL, attempt=2)
    assert not calls
    await provider.generate(window=window, tenant_id=uuid4(), request_id=str(uuid4()),
                            reservation_usd=quote)
    assert len(calls) == 1 and calls[0].max_tokens == 8192
    provider.wrapper.model_router.configs[ModelTier.STANDARD].cost_per_1m_output = 16
    with pytest.raises(ValueError, match="configuration changed"):
        provider.reservation_for_attempt(window, attempt=1, ceiling=CALL)


class FakeLedger:
    """Test runner orchestration, not actual PostgreSQL locking or balances."""
    def __init__(self, monkeypatch, *, remaining=RUN):
        self.remaining = remaining
        self.statuses = {}
        self.prior = {}
        self.reserves = []
        self.accounts = []
        self.run_id = uuid4()
        self.in_tx = False

        async def create_run(session, **kw):
            for w in kw["windows"]:
                self.statuses.setdefault(w.ordinal, "PENDING")
                self.prior.setdefault(w.ordinal, [])
            return self.run_id

        async def statuses(session, **kw):
            return dict(self.statuses)

        async def retryable(session, **kw):
            return {o for o, state in self.statuses.items() if state == "BLOCKED"}

        async def reserve(session, **kw):
            assert self.in_tx
            amount = kw["estimated_max_usd"]
            self.reserves.append((kw["idempotency_key"], amount))
            if self.remaining < amount:
                raise runner_module.N4BudgetError("fake remaining balance insufficient")
            self.remaining -= amount
            self.prior[kw["window_ordinal"]].append("RESERVED")
            self.statuses[kw["window_ordinal"]] = "PENDING"
            return SimpleNamespace(reservation_id=uuid4(), replay=False)

        async def account(session, **kw):
            assert self.in_tx
            self.accounts.append(kw)
            self.prior[0][-1] = "SETTLED"
            self.remaining += self.reserves[-1][1] - kw["billed_usd"]

        async def block(session, **kw):
            self.statuses[kw["window_ordinal"]] = "BLOCKED"

        async def outcome(self_runner, authority, run_id, reason=None):
            return SimpleNamespace(run_id=run_id, stopped_reason=reason)

        async def tenant(session, tenant_id):
            pass

        monkeypatch.setattr(runner_module, "create_run", create_run)
        monkeypatch.setattr(runner_module, "window_statuses", statuses)
        monkeypatch.setattr(runner_module, "retryable_windows", retryable)
        monkeypatch.setattr(runner_module, "reserve_call", reserve)
        monkeypatch.setattr(runner_module, "account_call", account)
        monkeypatch.setattr(runner_module, "block_window", block)
        monkeypatch.setattr(runner_module.N4IncrementalRunner, "_outcome", outcome)
        monkeypatch.setattr(runner_module.N4IncrementalRunner, "_tenant_context", staticmethod(tenant))

    @asynccontextmanager
    async def session(self):
        yield self

    @asynccontextmanager
    async def begin(self):
        assert not self.in_tx
        self.in_tx = True
        try:
            yield
        finally:
            self.in_tx = False

    async def execute(self, query, params):
        assert "FROM public.n4_usage_reservations" in str(query)
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: list(self.prior[params["ordinal"]])))


def setup_run(monkeypatch, *, remaining=RUN):
    source = document()
    authority = SimpleNamespace(tenant_id=uuid4(), revision_id=uuid4())
    provider, windows, calls = make_provider(source, authority.revision_id)
    ledger = FakeLedger(monkeypatch, remaining=remaining)
    original_generate = provider.wrapper.generate

    async def after_commit(req):
        assert not ledger.in_tx
        return await original_generate(req)

    provider.wrapper.generate = after_commit
    runner = runner_module.N4IncrementalRunner(
        session_factory=ledger.session, provider=provider, run_cap_usd=RUN,
        per_window_reservation_usd=CALL, period_key="2026-11", enabled=True,
        max_context_chars=12000, overlap_chars=400,
    )
    kw = {"authority": authority, "project_id": uuid4(), "model_safe_text": source,
          "n2_projection_attested": True}
    return runner, kw, ledger, provider, windows, calls


@pytest.mark.asyncio
async def test_runner_reserves_initial_then_denies_unfunded_retry(monkeypatch):
    runner, kw, ledger, provider, windows, calls = setup_run(monkeypatch)
    first = await runner.run(**kw)
    assert first.stopped_reason == "INVALID_PROVIDER_ENVELOPE"
    assert len(ledger.reserves) == len(ledger.accounts) == len(calls) == 1
    assert ledger.reserves[0][1] == provider.reservation_for_attempt(windows[0], attempt=1, ceiling=CALL)
    assert ledger.remaining == RUN - D("0.06")
    retry = await runner.run(**kw)
    assert retry.stopped_reason == "N4BudgetError"
    assert len(ledger.reserves) == len(ledger.accounts) == len(calls) == 1
    assert ledger.remaining == RUN - D("0.06")


@pytest.mark.asyncio
async def test_runner_remaining_budget_denied_before_transport(monkeypatch):
    runner, kw, ledger, provider, windows, calls = setup_run(monkeypatch, remaining=D("0.10"))
    out = await runner.run(**kw)
    assert out.stopped_reason == "N4BudgetError"
    assert len(ledger.reserves) == 1 and ledger.reserves[0][1] <= CALL
    assert not calls and not ledger.accounts and ledger.remaining == D("0.10")


@pytest.mark.asyncio
@pytest.mark.parametrize("remaining,expected_calls", [(D("0.27"), 1), (D("0.29"), 2)])
async def test_independently_financed_retry_uses_fresh_balance(monkeypatch, remaining, expected_calls):
    """Mock-only affordable retry quote: not an actual A13 16384 price."""
    runner, kw, ledger, provider, windows, calls = setup_run(monkeypatch)
    quotes = {1: D("0.20"), 2: D("0.28")}

    def quote(window, *, attempt, ceiling):
        assert ceiling == CALL
        return quotes[attempt]

    monkeypatch.setattr(provider, "reservation_for_attempt", quote)
    first = await runner.run(**kw)
    assert first.stopped_reason == "INVALID_PROVIDER_ENVELOPE"
    assert ledger.reserves[0][1] == D("0.20")
    ledger.remaining = remaining
    second = await runner.run(**kw)
    assert len(ledger.reserves) == 2
    assert ledger.reserves[1][1] == D("0.28")
    assert ledger.reserves[1][0] != ledger.reserves[0][0]
    assert len(calls) == expected_calls
    if expected_calls == 2:
        assert calls[-1].max_tokens == 16384
        assert second.stopped_reason == "INVALID_PROVIDER_ENVELOPE"
        assert ledger.remaining == remaining - D("0.06")
    else:
        assert second.stopped_reason == "N4BudgetError"
        assert ledger.remaining == remaining
