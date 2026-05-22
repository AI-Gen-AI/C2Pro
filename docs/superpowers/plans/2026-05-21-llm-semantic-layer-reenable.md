# LLM Semantic Layer Re-enable Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the 6 `R-*-CLARITY` LLM rules run automatically on every coherence evaluation, gated by a per-tenant rolling budget with a content-hash cache that short-circuits before the budget check, gradually ramped via per-rule rollout percentages, and degrading honestly to a distinct `budget_throttled` state with one `ADV-BUDGET-EXHAUSTED` advisory alert when the cap is hit.

**Architecture:** `CoherenceLlmGatePort` (domain) + `CoherenceLlmGate` adapter (infrastructure) encapsulate the 5-step gate (cache → rollout → budget → LLM → persist+charge). The graph node calls the port; it never imports `cost_controller`/`rollout_router`/`usage_analytics`/`model_router`/`prompt_cache` directly. Honest-scoring contract from TASK-BCK-060 is extended with `budget_throttled` and a top-level `budget_exhausted_reset_date`.

**Tech Stack:** Python 3.11, FastAPI, pydantic v2, LangGraph, pytest + pytest-asyncio. Container `c2pro-api` (uvicorn, no `--reload`; bind-mounts working tree).

**Spec:** `docs/superpowers/specs/2026-05-21-llm-semantic-layer-reenable-design.md` (commit `f0809d9a`).

---

## REVISION NOTE 2 (2026-05-22) — Cache primitive corrected

Second discovery: neither `FlashCacheService` nor `PromptCacheService` exposes a generic `get(key)/set(key,value)` — both are LLM-call-shaped (model_id + messages + temperature derive their own key). The spec's SHA-256 content-hash model requires a thin wrapper. **User-approved correction:** introduce `apps/api/src/coherence/adapters/ai/content_hash_cache.py` (≈30 lines) backed by the existing `CacheService` (`apps/api/src/core/cache.py`) — which already provides `async get_json(key)` / `async set_json(key, value, ttl)` over Redis with automatic in-memory fallback. The wrapper exposes `async get(key) -> FindingSignal | None` and `async set(key, FindingSignal) -> None`. `CoherenceLlmGate._get_cache()` resolves the wrapper via a new `get_content_hash_cache()` factory. Tests inject a `FakeContentHashCache` with async `get`/`set` matching this surface.

## REVISION NOTE — Real-vs-assumed API mismatches (2026-05-21)

Mid-implementation discovery: the plan's original assumptions about three `core/ai/` services were wrong. Verified against source:

| Service | Original assumption | Reality (verified) |
|---|---|---|
| **prompt cache** | `prompt_cache.get(key)/set(key, v)` synchronous | `FlashCacheService.get(key)/set(key, value)` is **async** (and is the correct primitive for our SHA-256 key model — `PromptCacheService` is prompt-text-keyed and computes its own hash, wrong layer for us). Use `get_flash_cache_service()`. |
| **cost controller** | `cost_controller.can_spend(tenant_id, cost) -> bool` returning boolean | `CostControllerService.check_budget_availability(tenant_id: UUID, estimated_cost: float) -> None` — **async, raises `BudgetExceededException`**, takes UUID, **service constructor requires `db: AsyncSession`** (no free singleton). |
| **usage analytics** | `usage_analytics.charge(tenant, cost)`, `period_end(tenant) -> date` | `UsageAnalyticsService.record_usage(model, task_name, input_tokens, output_tokens, cost_usd, latency_ms, success, tenant_id, …)` with rich metadata. **No `period_end` method exists** — derive reset date from calendar (first of next month; cost_controller resets monthly on year/month rollover per its source). |

**User decisions (locked) for the corrections:**
1. **Cache primitive → `FlashCacheService`** (Option 1): keeps our SHA-256 / `PROMPT_VERSION` key model; smallest change to the adapter. Adapter cache calls become `async`.
2. **DB session wiring → per-request injection from the node** (recommended): node resolves the `AsyncSession` and passes it to `CoherenceLlmGate(db=...)`. Gate stays stateless across requests; testable with a fake session.
3. **Reset date** → computed manually in the adapter at budget-exhaustion time: first of next month.
4. **UUID coercion** at the gate boundary: incoming `tenant_id: str` is converted via `UUID(tenant_id)` before passing to cost-controller.

These corrections affect Tasks 4 (fix-up), 5, 6, 7, 10. Tasks 1, 2, 3, 8, 9, 11, 12 are unaffected.

---

## File structure

| File | Disposition | Responsibility |
|---|---|---|
| `apps/api/src/coherence/domain/ports/coherence_llm_gate_port.py` | DONE (Task 1, `b43597a3`) | `CoherenceLlmGatePort` + `GateDecision`. |
| `apps/api/src/coherence/adapters/ai/rollout_config.py` | DONE (Task 2, `a5962a32`) | Per-rule rollout %, env-overridable. |
| `apps/api/src/coherence/adapters/ai/coherence_llm_gate.py` | IN PROGRESS (scaffold landed Task 3 `0253e617`; cache step landed Task 4 `e498ada7` against FAKE shape — **needs rewrite per corrections**). | 5-step gate adapter. |
| `apps/api/src/coherence/graph/nodes.py` | MODIFY (Task 10) | Replace `low_budget_mode` early-return with gate calls; resolve DB session; pass to `CoherenceLlmGate(db=...)`. |
| `apps/api/src/coherence/graph/state.py` | MODIFY (Task 10) | `low_budget_mode: True → False`. |
| `apps/api/src/coherence/models.py` | MODIFY (Task 9) | `CategoryBreakdown.state` widens to include `"budget_throttled"`. |
| `apps/api/src/coherence/scoring.py` | MODIFY (Tasks 9, 11) | Add `ScoringDiagnostics.budget_exhausted_reset_date`; surface `budget_throttled` via `_calculate_detailed_with_coverage`. |
| `apps/api/src/coherence/alert_generator.py` | MODIFY (Task 8) | `ADV-BUDGET-EXHAUSTED` template entries (orphan check enforcement). |
| `apps/api/tests/unit/coherence/adapters/ai/test_coherence_llm_gate.py` | EXISTS — needs Task 4 rewrite + Tasks 5–7 appends. | Adapter unit tests. |
| `apps/api/tests/unit/coherence/graph/test_llm_semantic_evaluate_gate.py` | NEW (Task 10) | Node tests w/ `FakeCoherenceLlmGate`. |
| `apps/api/tests/unit/coherence/test_budget_throttled_state.py` | NEW (Tasks 9, 11) | Scoring contract: `budget_throttled` distinct from `unassessed`, reset_date surfaced. |
| `backlogs/BCK_BACKEND.md`, `C2PRO_MASTER_BACKLOG.md` | MODIFY (Task 12) | `TASK-BCK-061` entry. |

---

## Tasks 1–3: DONE (no changes needed)

- Task 1 (`b43597a3`): port + `GateDecision`. ✅
- Task 2 (`a5962a32`): `rollout_config`. ✅
- Task 3 (`0253e617`): adapter scaffold with lazy accessors. ✅

## Task 4 (REWRITE): Adapter step 1 — content-hash cache (async FlashCacheService)

**Currently landed (`e498ada7`)** against the wrong API shape (sync `.get/.set` against fakes). Must be rewritten to:
- Lazy accessor uses `get_flash_cache_service()` (NOT `get_prompt_cache_service`).
- `evaluate_rule` becomes `async` and **awaits** `cache.get(cache_key)`.
- Tests inject a `FakeFlashCache` with **async** `get`/`set` matching the real interface.

### Step 1: Rewrite tests in `apps/api/tests/unit/coherence/adapters/ai/test_coherence_llm_gate.py`

Replace the two `test_gate_returns_cache_hit...` and `test_content_hash_is_deterministic...` test bodies (and the FakeCache helper) with the async-fake version below. Other tests in the file (port shape, rollout_config, lazy-deps, NotImplementedError pin) stay.

```python
@pytest.mark.asyncio
async def test_gate_returns_cache_hit_without_consulting_budget_or_llm():
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause, FindingSignal

    cached_finding = FindingSignal(
        rule_id="R-SCOPE-CLARITY-01", clause_id="c1", impact_score=0.4,
        confidence=1.0, severity="medium", category="SCOPE",
        evidence_summary="cached", quote="q", raw_data={"source": "llm"},
    )

    class FakeFlashCache:
        def __init__(self):
            self.get_calls = 0
            self.set_calls = 0
        async def get(self, key):
            self.get_calls += 1
            return cached_finding
        async def set(self, key, value):  # pragma: no cover — hit path
            self.set_calls += 1

    cost_consulted = {"called": False}
    class FakeCost:
        async def check_budget_availability(self, *a, **kw):
            cost_consulted["called"] = True

    gate = g.CoherenceLlmGate()
    gate._cache = FakeFlashCache()
    gate._cost = FakeCost()

    decision = await gate.evaluate_rule(
        "00000000-0000-0000-0000-000000000001", "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="The scope is to design a substation.", data={}),
    )

    assert decision.state == "cache_hit"
    assert decision.finding is cached_finding
    assert decision.cost_charged_usd == 0.0
    assert decision.cache_key is not None and len(decision.cache_key) == 64
    assert cost_consulted["called"] is False  # critical
    assert gate._cache.get_calls == 1
    assert gate._cache.set_calls == 0


def test_content_hash_is_deterministic_and_canonicalized():
    from src.coherence.adapters.ai.coherence_llm_gate import _content_hash
    h1 = _content_hash("R-SCOPE-CLARITY-01", "  Some Text  ")
    h2 = _content_hash("R-SCOPE-CLARITY-01", "some text")
    assert h1 == h2
    h3 = _content_hash("R-PAYMENT-CLARITY-01", "some text")
    assert h1 != h3
```

### Step 2: Rewrite the adapter's cache step

In `apps/api/src/coherence/adapters/ai/coherence_llm_gate.py`:

- Change `_get_cache()` lazy accessor: `from src.core.ai.prompt_cache import get_flash_cache_service` (NOT `get_prompt_cache_service`); cache the returned instance.
- `evaluate_rule` is already `async`; ensure `cached = await cache.get(cache_key)`.

The rest of step 1 logic (compute `cache_key`, return `cache_hit` decision on non-None) is unchanged from the current `e498ada7` version.

### Step 3: Run, regression, lint, commit

```bash
cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/adapters/ai/test_coherence_llm_gate.py -q -p no:warnings
cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/ -q -p no:warnings 2>&1 | tail -2
cd apps/api && ruff check src/coherence/adapters/ai/coherence_llm_gate.py tests/unit/coherence/adapters/ai/test_coherence_llm_gate.py
cd /c/Users/esus_/c2pro-p3
git add apps/api/src/coherence/adapters/ai/coherence_llm_gate.py apps/api/tests/unit/coherence/adapters/ai/test_coherence_llm_gate.py
git commit -m "fix(coherence): gate step 1 - use async FlashCacheService (real API)"
```

---

## Task 5: Adapter step 2 — per-rule rollout (`should_trace_request`)

Unchanged from original plan, except the adapter's `evaluate_rule` is `async` throughout.

### Step 1: Append test

```python
@pytest.mark.asyncio
async def test_gate_rolled_out_off_when_rule_pct_is_zero(monkeypatch):
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause

    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "0")

    class EmptyCache:
        async def get(self, key): return None
        async def set(self, key, value): pass

    cost_consulted = {"called": False}
    class FakeCost:
        async def check_budget_availability(self, *a, **kw):
            cost_consulted["called"] = True

    gate = g.CoherenceLlmGate()
    gate._cache = EmptyCache()
    gate._cost = FakeCost()

    decision = await gate.evaluate_rule(
        "00000000-0000-0000-0000-000000000001", "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="any text", data={}),
    )

    assert decision.state == "rolled_out_off"
    assert decision.reason == "rule_rollout_disabled"
    assert decision.cost_charged_usd == 0.0
    assert cost_consulted["called"] is False
```

### Step 2: Implement

Replace the `raise NotImplementedError("rollout + budget + LLM land in Tasks 5-7")` line with:

```python
        # Step 2: per-rule rollout (existing % primitive).
        from src.core.ai.rollout_router import should_trace_request
        from src.coherence.adapters.ai.rollout_config import get_rollout_pct

        pct = get_rollout_pct(rule_id)
        if pct == 0 or not should_trace_request(tenant_id, pct):
            logger.info("coherence_llm_gate.rolled_out_off",
                        tenant_id=tenant_id, rule_id=rule_id, pct=pct)
            return GateDecision(
                state="rolled_out_off", finding=None,
                reason="rule_rollout_disabled", reset_date=None,
                cache_key=cache_key, cost_charged_usd=0.0,
            )

        raise NotImplementedError("budget + LLM land in Tasks 6-7")
```

### Step 3: Run, regression, lint, commit
Same shape as Task 4. Commit message: `feat(coherence): gate step 2 - per-rule rollout via should_trace_request`.

---

## Task 6: Adapter step 3 — budget check (REAL API — try/except, UUID, reset_date computed)

### Step 1: Append test

```python
@pytest.mark.asyncio
async def test_gate_budget_exhausted_returns_distinct_state_with_reset_date(monkeypatch):
    import datetime
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.core.ai.cost_controller import BudgetExceededException
    from src.coherence.models import Clause

    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "100")

    class EmptyCache:
        async def get(self, key): return None
        async def set(self, key, value): pass

    class FakeCost:
        async def check_budget_availability(self, tenant_uuid, estimated_cost):
            raise BudgetExceededException("test: budget exhausted")

    llm_consulted = {"called": False}
    class FakeLlm:
        async def call(self, *a, **kw):
            llm_consulted["called"] = True

    gate = g.CoherenceLlmGate()
    gate._cache = EmptyCache()
    gate._cost = FakeCost()
    gate._llm = FakeLlm()

    decision = await gate.evaluate_rule(
        "00000000-0000-0000-0000-000000000001", "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="any text", data={}),
    )

    assert decision.state == "budget_exhausted"
    assert decision.reason == "tenant_budget_exhausted"
    # Reset date: first of next calendar month
    today = datetime.date.today()
    expected = (
        datetime.date(today.year + 1, 1, 1) if today.month == 12
        else datetime.date(today.year, today.month + 1, 1)
    )
    assert decision.reset_date == expected
    assert decision.cost_charged_usd == 0.0
    assert llm_consulted["called"] is False
```

### Step 2: Implement

Add a module-level helper near the other helpers in the adapter file:

```python
def _next_month_first() -> "date":
    """Compute the first of next calendar month (matches cost_controller's monthly reset)."""
    import datetime
    today = datetime.date.today()
    if today.month == 12:
        return datetime.date(today.year + 1, 1, 1)
    return datetime.date(today.year, today.month + 1, 1)
```

Also add module-level: `ESTIMATED_HAIKU_COST_USD = 0.0008` (conservative per-call estimate; the user-locked value).

Replace the `raise NotImplementedError("budget + LLM land in Tasks 6-7")` with:

```python
        # Step 3: budget check (real API — async, raises BudgetExceededException, takes UUID).
        from uuid import UUID
        from src.core.ai.cost_controller import BudgetExceededException

        try:
            tenant_uuid = UUID(tenant_id)
        except (ValueError, AttributeError):
            # Defensive: if tenant_id isn't a UUID, treat as exhausted (fail-closed).
            logger.warning("coherence_llm_gate.invalid_tenant_id", tenant_id=tenant_id)
            return GateDecision(
                state="budget_exhausted", finding=None,
                reason="invalid_tenant_id", reset_date=None,
                cache_key=cache_key, cost_charged_usd=0.0,
            )

        cost = self._get_cost()
        try:
            await cost.check_budget_availability(tenant_uuid, ESTIMATED_HAIKU_COST_USD)
        except BudgetExceededException:
            logger.info("coherence_llm_gate.budget_exhausted",
                        tenant_id=tenant_id, rule_id=rule_id)
            return GateDecision(
                state="budget_exhausted", finding=None,
                reason="tenant_budget_exhausted",
                reset_date=_next_month_first(),
                cache_key=cache_key, cost_charged_usd=0.0,
            )

        raise NotImplementedError("LLM call lands in Task 7")
```

### Step 3: Run, regression, lint, commit

Commit message: `feat(coherence): gate step 3 - budget check via check_budget_availability (real API)`.

---

## Task 7: Adapter steps 4–5 — LLM call + persist + charge (with token metadata)

### Step 1: Append test

```python
@pytest.mark.asyncio
async def test_gate_evaluated_path_calls_llm_caches_result_and_charges(monkeypatch):
    from src.coherence.adapters.ai import coherence_llm_gate as g
    from src.coherence.models import Clause, FindingSignal

    monkeypatch.setenv("COHERENCE_LLM_ROLLOUT_R_SCOPE_CLARITY_01", "100")

    saved: dict[str, FindingSignal] = {}
    class FakeFlashCache:
        async def get(self, key): return None
        async def set(self, key, value): saved[key] = value

    class FakeCost:
        async def check_budget_availability(self, *a, **kw): pass  # ok

    recorded: list[dict] = []
    class FakeUsage:
        def record_usage(self, *, model, task_name, input_tokens, output_tokens,
                          cost_usd, latency_ms, success, tenant_id=None, **_kw):
            recorded.append({
                "model": model, "task_name": task_name,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "cost_usd": cost_usd, "tenant_id": tenant_id,
            })

    finding = FindingSignal(
        rule_id="R-SCOPE-CLARITY-01", clause_id="c1", impact_score=0.42,
        confidence=0.9, severity="medium", category="SCOPE",
        evidence_summary="ambiguous", quote="q", raw_data={},
    )

    # Fake the rule-call helper: returns (finding, input_tok, output_tok, cost, latency_ms, model)
    async def fake_call_rule(rule_id, clause):
        return finding, 120, 80, 0.0007, 250.0, "claude-3-haiku-20240307"

    gate = g.CoherenceLlmGate()
    gate._cache = FakeFlashCache()
    gate._cost = FakeCost()
    gate._usage = FakeUsage()
    monkeypatch.setattr(gate, "_call_rule_via_llm", fake_call_rule)

    decision = await gate.evaluate_rule(
        "00000000-0000-0000-0000-000000000001", "R-SCOPE-CLARITY-01",
        Clause(id="c1", text="ambiguous scope text", data={}),
    )

    assert decision.state == "evaluated"
    assert decision.finding is finding
    assert decision.cost_charged_usd == 0.0007
    assert decision.cache_key in saved and saved[decision.cache_key] is finding
    assert len(recorded) == 1
    r = recorded[0]
    assert r["model"] == "claude-3-haiku-20240307"
    assert r["task_name"] == "coherence_R-SCOPE-CLARITY-01"
    assert r["input_tokens"] == 120 and r["output_tokens"] == 80
    assert r["cost_usd"] == 0.0007
    assert r["tenant_id"] == "00000000-0000-0000-0000-000000000001"
```

### Step 2: Implement

Add method `_call_rule_via_llm` on `CoherenceLlmGate`:

```python
    async def _call_rule_via_llm(
        self,
        rule_id: str,
        clause: Clause,
    ) -> tuple[FindingSignal | None, int, int, float, float, str]:
        """
        Resolve the per-rule LLM evaluator from the v1 registry and run it for
        one clause. Returns (finding, input_tokens, output_tokens, cost_usd,
        latency_ms, model_name). Implementation reads tokens/cost/latency/model
        from the evaluator's metrics post-call (delta between before/after).
        """
        import time
        from src.coherence.rules_engine.registry import get_v1_evaluator

        evaluator = get_v1_evaluator(rule_id, low_budget_mode=False)
        # Snapshot metrics BEFORE the call.
        m_before = getattr(evaluator, "metrics", None)
        cost_before = float(getattr(m_before, "total_cost_usd", 0.0)) if m_before else 0.0
        # Some LlmRuleEvaluator implementations expose total_cost_usd directly.
        cost_before = float(getattr(evaluator, "total_cost_usd", cost_before))

        t0 = time.perf_counter()
        signal = await evaluator.evaluate_v3_async(clause)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        # Snapshot metrics AFTER.
        cost_after = float(getattr(evaluator, "total_cost_usd", cost_before))
        actual_cost = max(0.0, cost_after - cost_before)
        # Token counts: best-effort from the evaluator's last-call telemetry.
        last_call = getattr(evaluator, "_last_call_metrics", None) or {}
        input_tokens = int(last_call.get("input_tokens", 0))
        output_tokens = int(last_call.get("output_tokens", 0))
        model = str(last_call.get("model", "claude-3-haiku-20240307"))

        return signal, input_tokens, output_tokens, actual_cost, latency_ms, model
```

Replace the final `raise NotImplementedError("LLM call lands in Task 7")` with:

```python
        # Step 4: actual LLM call (via existing rule evaluator, Haiku-routed).
        try:
            finding, in_tok, out_tok, actual_cost, latency_ms, model = \
                await self._call_rule_via_llm(rule_id, clause)
        except Exception as exc:  # noqa: BLE001
            logger.warning("coherence_llm_gate.llm_error",
                           tenant_id=tenant_id, rule_id=rule_id, err=str(exc))
            raise  # node converts to errors[] + SKIPPED for the rule

        # Step 5a: cache write (async, FlashCacheService API).
        if finding is not None:
            try:
                await self._get_cache().set(cache_key, finding)
            except Exception as exc:  # noqa: BLE001
                logger.warning("coherence_llm_gate.cache_write_failed",
                               tenant_id=tenant_id, rule_id=rule_id, err=str(exc))

        # Step 5b: charge usage_analytics with rich metadata (real API).
        try:
            self._get_usage().record_usage(
                model=model,
                task_name=f"coherence_{rule_id}",
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=actual_cost,
                latency_ms=latency_ms,
                success=True,
                tenant_id=tenant_id,
                prompt_version=PROMPT_VERSION,
            )
        except Exception as exc:  # noqa: BLE001 — telemetry must never break scoring
            logger.warning("coherence_llm_gate.charge_failed",
                           tenant_id=tenant_id, rule_id=rule_id, err=str(exc))

        return GateDecision(
            state="evaluated", finding=finding, reason=None,
            reset_date=None, cache_key=cache_key, cost_charged_usd=actual_cost,
        )
```

### Step 3: Run, regression, lint, commit

Commit message: `feat(coherence): gate steps 4-5 - LLM call (Haiku) + cache write + record_usage (real API)`.

---

## Task 8: `ADV-BUDGET-EXHAUSTED` alert template entries

Unchanged from original. Add entries to `RULE_TITLES`, `RULE_SEVERITIES`, `TEMPLATES` in `apps/api/src/coherence/alert_generator.py`:

- Title: `"Deep semantic analysis paused"`
- Severity: `AlertSeverity.INFO` (or `"info"` — match the table's value type, grep first)
- Template: `"Deep semantic analysis paused: tenant analysis budget exhausted. Resets {reset_date}."`

Test exists: `assert "ADV-BUDGET-EXHAUSTED" in {RULE_TITLES, RULE_SEVERITIES, TEMPLATES}` + severity ends in "info" or "low". `assert_v1_rule_ids_have_alert_templates` orphan-check requires it.

Commit: `feat(coherence): ADV-BUDGET-EXHAUSTED alert template entries (registry orphan-check)`.

---

## Task 9: `CategoryBreakdown.budget_throttled` + `ScoringDiagnostics.budget_exhausted_reset_date`

Unchanged from original.

- `CategoryBreakdown.state` — if Literal-typed, widen to include `"budget_throttled"`; if free `str`, no model change needed (TASK-BCK-060 left it as `str = Field("assessed_findings", ...)`).
- `ScoringDiagnostics` — add `budget_exhausted_reset_date: date | None = None` (import `date` at top).

Tests pin both extensions.

Commit: `feat(coherence): budget_throttled CategoryBreakdown state + reset_date in ScoringDiagnostics`.

---

## Task 10: `llm_semantic_evaluate` uses gate; `low_budget_mode` default → False; **DB session passed to gate**

### Corrections from original plan

- Gate construction now requires the per-request `AsyncSession`: `CoherenceLlmGate(db=session)`. The node must resolve the session and pass it.
- Node tests inject a `FakeCoherenceLlmGate` (no DB needed) to keep test isolation.
- The `EvaluationConfig.tenant_id` is already a string; pass it through unchanged.

### Step 1: New test file `apps/api/tests/unit/coherence/graph/test_llm_semantic_evaluate_gate.py`

```python
from datetime import date

import pytest

from src.coherence.domain.ports.coherence_llm_gate_port import GateDecision
from src.coherence.graph.state import CoherenceGraphState, EvaluationConfig
from src.coherence.models import Clause, FindingSignal


class FakeGate:
    """Returns canned decisions keyed by (rule_id, clause_id). No DB needed."""
    def __init__(self, decisions):
        self.decisions = decisions
        self.calls = []
    async def evaluate_rule(self, tenant_id, rule_id, clause):
        self.calls.append((tenant_id, rule_id, clause.id))
        return self.decisions[(rule_id, clause.id)]


def _finding(rule_id, clause_id, category):
    return FindingSignal(
        rule_id=rule_id, clause_id=clause_id, impact_score=0.5,
        confidence=0.9, severity="medium", category=category,
        evidence_summary="e", quote="q", raw_data={},
    )


@pytest.mark.asyncio
async def test_node_uses_gate_findings_and_marks_coverage_evaluated():
    from src.coherence.graph.nodes import llm_semantic_evaluate_async
    clause = Clause(id="c1", text="ambiguous", data={})
    state = CoherenceGraphState(project_id="p", clauses=[clause],
                                 config=EvaluationConfig(
                                     tenant_id="00000000-0000-0000-0000-000000000001"))
    gate = FakeGate({
        ("R-SCOPE-CLARITY-01", "c1"): GateDecision(
            state="evaluated",
            finding=_finding("R-SCOPE-CLARITY-01", "c1", "SCOPE"),
            reason=None, reset_date=None, cache_key="k", cost_charged_usd=0.0007),
        ("R-PAYMENT-CLARITY-01", "c1"): GateDecision(
            state="rolled_out_off", finding=None, reason="rule_rollout_disabled",
            reset_date=None, cache_key="k2", cost_charged_usd=0.0),
        ("R-SCHEDULE-CLARITY-01", "c1"): GateDecision(
            state="rolled_out_off", finding=None, reason="rule_rollout_disabled",
            reset_date=None, cache_key="k3", cost_charged_usd=0.0),
        ("R-TECHNICAL-SPEC-CLARITY-01", "c1"): GateDecision(
            state="rolled_out_off", finding=None, reason="rule_rollout_disabled",
            reset_date=None, cache_key="k4", cost_charged_usd=0.0),
        ("R-RESPONSIBILITY-01", "c1"): GateDecision(
            state="rolled_out_off", finding=None, reason="rule_rollout_disabled",
            reset_date=None, cache_key="k5", cost_charged_usd=0.0),
        ("R-QUALITY-STANDARDS-01", "c1"): GateDecision(
            state="rolled_out_off", finding=None, reason="rule_rollout_disabled",
            reset_date=None, cache_key="k6", cost_charged_usd=0.0),
    })

    out = await llm_semantic_evaluate_async(state, gate=gate)

    assert any(s.rule_id == "R-SCOPE-CLARITY-01" for s in out["llm_signals"])
    assert out["coverage_map"]["SCOPE"] is True
    assert out["coverage_map"].get("BUDGET", False) is False  # rolled off


@pytest.mark.asyncio
async def test_node_emits_single_advisory_when_any_rule_budget_exhausted():
    from src.coherence.graph.nodes import llm_semantic_evaluate_async
    reset = date(2026, 6, 1)
    clause = Clause(id="c1", text="x", data={})
    state = CoherenceGraphState(project_id="p", clauses=[clause],
                                 config=EvaluationConfig(
                                     tenant_id="00000000-0000-0000-0000-000000000001"))
    gate = FakeGate({
        (rid, "c1"): GateDecision(
            state="budget_exhausted", finding=None,
            reason="tenant_budget_exhausted", reset_date=reset,
            cache_key=None, cost_charged_usd=0.0)
        for rid in ("R-SCOPE-CLARITY-01","R-PAYMENT-CLARITY-01","R-SCHEDULE-CLARITY-01",
                    "R-TECHNICAL-SPEC-CLARITY-01","R-RESPONSIBILITY-01","R-QUALITY-STANDARDS-01")
    })
    out = await llm_semantic_evaluate_async(state, gate=gate)

    adv = [a for a in out.get("alerts", []) if a.rule_id == "ADV-BUDGET-EXHAUSTED"]
    assert len(adv) == 1
    assert out.get("budget_exhausted_reset_date") == reset
    assert out["llm_signals"] == []
```

### Step 2: Implement

In `apps/api/src/coherence/graph/state.py` line ~115: `low_budget_mode: bool = True` → `False` (+ comment).

In `apps/api/src/coherence/graph/nodes.py`, replace the body of `llm_semantic_evaluate_async`:

```python
async def llm_semantic_evaluate_async(
    state: CoherenceGraphState,
    *,
    gate: "CoherenceLlmGatePort | None" = None,
) -> NodeOutput:
    """P3: always-on LLM semantic layer via CoherenceLlmGate."""
    from src.coherence.rules_engine.registry import V1_LLM_RULE_IDS

    _LLM_CATEGORIES = ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")

    if state.config.low_budget_mode:
        logger.info("llm_semantic_evaluate: skipped (low_budget_mode=True escape hatch)")
        return {
            "llm_signals": [], "llm_cost_usd": 0.0, "llm_calls_count": 0,
            "coverage_map": {cat: False for cat in _LLM_CATEGORIES},
        }

    if gate is None:
        # Resolve a DB session for the per-request CoherenceLlmGate.
        from src.coherence.adapters.ai.coherence_llm_gate import CoherenceLlmGate
        from src.core.database import get_async_session  # existing FastAPI/SQLAlchemy DI
        async for session in get_async_session():
            gate = CoherenceLlmGate(db=session)
            return await _run_gate(state, gate, _LLM_CATEGORIES)
        raise RuntimeError("could not acquire DB session for CoherenceLlmGate")

    return await _run_gate(state, gate, _LLM_CATEGORIES)


async def _run_gate(state, gate, _LLM_CATEGORIES):
    from datetime import date as _date
    from src.coherence.rules_engine.registry import V1_LLM_RULE_IDS

    signals: list[FindingSignal] = []
    errors: list[str] = []
    coverage: dict[str, bool] = {}
    total_cost = 0.0
    budget_reset: _date | None = None
    budget_exhausted_seen = False

    tenant_id = (state.config.tenant_id or "").strip() or "00000000-0000-0000-0000-000000000000"

    for clause in state.clauses:
        for rule_id in V1_LLM_RULE_IDS:
            try:
                decision = await gate.evaluate_rule(tenant_id, rule_id, clause)
            except Exception as e:  # noqa: BLE001
                msg = f"LLM gate {rule_id} failed for clause {clause.id}: {e}"
                logger.warning(msg); errors.append(msg)
                coverage.setdefault(_category_for_rule(rule_id), False)
                continue
            cat = _category_for_rule(rule_id)
            if decision.state in ("evaluated", "cache_hit"):
                if decision.finding is not None:
                    signals.append(decision.finding)
                coverage[cat] = True
                total_cost += decision.cost_charged_usd
            elif decision.state == "budget_exhausted":
                coverage.setdefault(cat, False)
                budget_exhausted_seen = True
                if budget_reset is None or (
                    decision.reset_date and decision.reset_date < budget_reset
                ):
                    budget_reset = decision.reset_date
            else:  # rolled_out_off
                coverage.setdefault(cat, False)

    out: dict[str, Any] = {
        "llm_signals": signals, "llm_cost_usd": total_cost,
        "llm_calls_count": len(state.clauses) * len(V1_LLM_RULE_IDS),
        "coverage_map": coverage, "errors": errors,
    }
    if budget_exhausted_seen:
        out["alerts"] = [_emit_budget_alert(budget_reset)]
        out["budget_exhausted_reset_date"] = budget_reset
    return out


def _category_for_rule(rule_id: str) -> str:
    return {
        "R-SCOPE-CLARITY-01": "SCOPE",
        "R-PAYMENT-CLARITY-01": "BUDGET",
        "R-SCHEDULE-CLARITY-01": "TIME",
        "R-TECHNICAL-SPEC-CLARITY-01": "TECHNICAL",
        "R-RESPONSIBILITY-01": "LEGAL",
        "R-QUALITY-STANDARDS-01": "QUALITY",
    }.get(rule_id, "SCOPE")


def _emit_budget_alert(reset_date):
    from src.coherence.models import Alert, Evidence
    return Alert(
        rule_id="ADV-BUDGET-EXHAUSTED", severity="info", category="general",
        message=(
            "Deep semantic analysis paused: tenant analysis budget exhausted."
            + (f" Resets {reset_date}." if reset_date else "")
        ),
        evidence=Evidence(claim="tenant_budget_exhausted",
                          source_clause_id=None, quote=None),
    )
```

The `CoherenceLlmGate` dataclass must accept `db` — update Task 3's scaffold post-hoc (move `_cost`/`_get_cost` to require the session). Specifically: change `CoherenceLlmGate` to `@dataclass` with `db: AsyncSession | None = None`, and `_get_cost()` constructs `CostControllerService(db=self.db)`. The node passes `db=session`.

### Step 3: Run, regression, lint, commit

If a pre-existing test asserted `llm_semantic_evaluate` returned exactly `{llm_signals, llm_cost_usd, llm_calls_count}`, update it to tolerate the new optional `alerts`/`budget_exhausted_reset_date` keys. Document each adjusted test in commit message.

Commit: `feat(coherence): llm_semantic_evaluate uses CoherenceLlmGatePort + DB session; low_budget_mode default→False`.

---

## Task 11: Surface `budget_throttled` in category breakdown

Unchanged from original. `_build_category_breakdown` gains an optional `budget_throttled_categories: set[str] | None = None`; when a category is unassessed AND in the set, state becomes `"budget_throttled"`. `scoring_arbiter` derives the set from the budget-exhausted signals in the LLM node output and threads via `state.diagnostics`.

Commit: `feat(coherence): surface budget_throttled state in category breakdown when LLM gate denied`.

---

## Task 12: E2E validation + backlog

Unchanged from original.

- Step 1: full coherence suite green (baseline 104 + ~18 new ≈ 122).
- Step 2: `docker restart c2pro-api && sleep 25 && curl /health` → 200.
- Step 3: authenticated `/evaluate/diagnostics`; expect LLM-only categories now have numeric scores (or `budget_throttled` if test tenant hit cap); deterministic findings unaffected.
- Step 4: per-rule kill-switch sanity — `COHERENCE_LLM_ROLLOUT_R_TECHNICAL_SPEC_CLARITY_01=0` → TECHNICAL falls back to deterministic-only.
- Step 5: backlog entry `TASK-BCK-061` (delegate Haiku per memory `feedback_master_no_backlog_edits`).
- Step 6: push branch + open PR.

---

## Self-Review Notes (post-correction)

- **Spec coverage:** all 8 decisions threaded; corrections preserve the spec contract (cache-before-budget invariant retained; honest degradation states unchanged).
- **Placeholder scan:** none. All API calls reference verified real signatures.
- **Type consistency:** `GateDecision`, `CoherenceLlmGatePort`, `_call_rule_via_llm` (now returns 6-tuple with tokens/latency/model), `_next_month_first`, `PROMPT_VERSION`, `ESTIMATED_HAIKU_COST_USD`, `_emit_budget_alert`, `_category_for_rule` consistent across Tasks 4–11.
- **Known correction risk:** the `_call_rule_via_llm` helper reads `_last_call_metrics` from the v1 evaluator — verify that attribute exists at implementation time; if absent, the implementer should fall back to deriving tokens from the LLM response object via the evaluator's wrapped `AnthropicWrapper`. Best-effort metadata; if missing, `record_usage` still receives cost+latency, just with zero token counts.
