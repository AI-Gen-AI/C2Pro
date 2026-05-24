# Design: Re-enable LLM Semantic Layer (Always-On, Cost-Gated)

**Date:** 2026-05-21
**Status:** Approved (design); pending implementation plan
**Owner:** Coherence Engine
**Related:** TASK-BCK-060 (honest scoring, merged in #136/#138), follow-up to that feature
**Backlog ID (to create):** TASK-BCK-061

## Problem

`apps/api/src/coherence/graph/state.py:115` ships `low_budget_mode: bool = True` as the default for `EvaluationConfig`. `llm_semantic_evaluate` (nodes.py) early-returns under that flag, so the 6 LLM clarity rules never execute. Under the honest-scoring model (TASK-BCK-060), this is *truthful* — those LLM-only categories surface as `null` + `score_missing_dimensions` rather than fake 100s — but the categories themselves remain unassessed. Re-enabling the layer converts honest-null into actually-assessed scores for LEGAL/SCOPE/PAYMENT/SCHEDULE/TECHNICAL-SPEC/QUALITY clarity.

The infrastructure already exists in `core/ai/`:
`cost_controller.py`, `usage_analytics.py`, `usage_logger.py`, `model_router.py` + `model_routing.yaml`, `rollout_router.py`, `prompt_cache.py`. P3 is wiring + policy, not build-from-scratch.

## Decision Summary

Eight decisions locked through brainstorm:

| # | Decision | Choice |
|---|---|---|
| 1 | Trigger | Always-on, cost-gated |
| 2 | Budget policy | Per-tenant rolling budget (`usage_analytics`) |
| 3 | Model | Haiku for all 6 `R-*-CLARITY` rules (`model_router`) |
| 4 | Exhaustion signaling | Distinct `budget_exhausted` reason + actionable advisory alert (with reset date) |
| 5 | Rollout (cohort) | Gradual via `rollout_router`: 10% → 50% → 100% tenant ramp |
| 6 | Rollout (rule) | **Per-rule independent control** (turn one rule off without affecting the other five) |
| 7 | Caching | **Content-hash cache *before* cost-gate** — cache hits never decrement budget |
| 8 | Quality eval | Separate follow-up spec (out of scope here) |

Decisions 6 and 7 extend the Q&A choices; they're additive and consistent with the architecture.

## Architecture

### Hexagonal layering (critical — verified against existing module conventions)

`coherence/graph/nodes.py` is **orchestration**, not domain. Its only `core.*` import today is the observability tracing decorator (cross-cutting, acceptable). The `coherence/` module already enforces hexagonal layering via `coherence/domain/ports/` (e.g. existing `LLMRulePort`) + `coherence/adapters/` (concrete implementations that import infrastructure). The new P3 dependencies (`rollout_router`, `cost_controller`, `usage_analytics`, `model_router`, `prompt_cache`) are infrastructure — they live in the adapter, never in the node.

Concretely:

```
coherence/
├── domain/ports/
│   └── coherence_llm_gate_port.py     [NEW] interface + GateDecision value type
├── adapters/ai/
│   └── coherence_llm_gate.py          [NEW] concrete adapter (wires 5 infra deps)
└── graph/
    └── nodes.py                       [MODIFIED] node calls the port, never the routers
```

### `CoherenceLlmGatePort` (domain, no infra deps)

```python
class CoherenceLlmGatePort(Protocol):
    async def evaluate_rule(
        self,
        tenant_id: str,
        rule_id: str,
        clause: Clause,
    ) -> GateDecision: ...


@dataclass(frozen=True)
class GateDecision:
    """Outcome of consulting the gate for a single (tenant, rule, clause)."""
    state: Literal["evaluated", "cache_hit", "budget_exhausted", "rolled_out_off"]
    finding: FindingSignal | None        # populated on evaluated / cache_hit
    reason: str | None                   # human-readable for telemetry
    reset_date: date | None              # populated on budget_exhausted
    cache_key: str | None                # SHA-256 used (for debugging/observability)
    cost_charged_usd: float              # 0.0 for cache_hit / denied paths
```

The node depends only on this port type. Domain stays clean.

### `coherence_llm_gate.py` adapter — internal evaluation order

The adapter sequences five steps per `(tenant, rule, clause)` call. Order is load-bearing — cache before budget before rollout before LLM — because it controls cost semantics:

```
                ┌─────────────────────────────────────────────┐
                │ evaluate_rule(tenant_id, rule_id, clause)   │
                └────────────────────┬────────────────────────┘
                                     │
                  1. Content-hash    ▼
                 ┌───────────────────────────────────┐
                 │ key = sha256(rule_id || prompt_v  │
                 │         || canonical(clause.text))│
                 │ prompt_cache.get(key)?            │
                 └──────────┬────────────────────────┘
                            │ hit
                            ├──────► return GateDecision(cache_hit, finding=..., cost=0)
                            │
                            ▼ miss
                  2. Per-rule rollout
                 ┌───────────────────────────────────┐
                 │ rollout_router.is_enabled(        │
                 │   tenant_id, feature=rule_id      │
                 │ )                                 │
                 └──────────┬────────────────────────┘
                            │ off
                            ├──────► return GateDecision(rolled_out_off)
                            │
                            ▼ on
                  3. Budget check
                 ┌───────────────────────────────────┐
                 │ cost_controller.can_spend(        │
                 │   tenant_id, est_cost_haiku       │
                 │ )                                 │
                 └──────────┬────────────────────────┘
                            │ exhausted
                            ├──────► return GateDecision(
                            │           budget_exhausted,
                            │           reset_date=usage_analytics.period_end(tenant))
                            │
                            ▼ ok
                  4. LLM call (Haiku via model_router)
                 ┌───────────────────────────────────┐
                 │ model = model_router.select(      │
                 │   rule_id, "clarity"              │
                 │ )  → always Haiku in P3 (config)  │
                 │ finding = await llm_client.call(  │
                 │   model, prompt, clause)          │
                 └──────────┬────────────────────────┘
                            │ result
                            ▼
                  5. Persist + charge
                 ┌───────────────────────────────────┐
                 │ prompt_cache.set(key, finding)    │
                 │ usage_analytics.charge(           │
                 │   tenant_id, cost_actual)         │
                 └──────────┬────────────────────────┘
                            ▼
                  return GateDecision(evaluated, finding=..., cost=cost_actual)
```

**Cache before budget is deliberate**: identical re-evaluations of unchanged clauses never decrement the tenant's budget. The cost-saving compounds for unchanged contracts in re-analysis workflows.

**Failure modes inside step 4** (HTTP errors, timeouts, parse failures) propagate up as exceptions. The node converts them to `errors[]` + treats the rule as `SKIPPED_MISSING_INPUTS` for that clause (honest contract: the rule didn't actually run, so don't pretend it did). LLM errors do NOT degrade to `budget_exhausted`.

### Node wiring (`llm_semantic_evaluate`)

Two private helpers in the same file, keeping the policy seam testable through the node's existing test surface:

```python
async def _evaluate_via_gate(state, gate: CoherenceLlmGatePort) -> _GateResult:
    """Calls gate.evaluate_rule for each (clause × rule), aggregates findings,
       coverage map, and structured GateDecisions for downstream alert emission."""
    ...

def _emit_budget_alert(decisions: list[GateDecision]) -> Alert | None:
    """When ≥1 rule was denied with reason='budget_exhausted', emits ONE
       advisory alert per evaluation (not per rule) carrying the earliest
       reset_date, so the user sees one actionable signal not six."""
    ...
```

The current `if state.config.low_budget_mode:` early-return is **removed** — the gate now owns the on/off semantics (via rollout config). `low_budget_mode` remains on `EvaluationConfig` as a developer/test escape hatch (default flipped to `False` in P3; setting it `True` short-circuits the gate path entirely, useful for unit tests of unrelated nodes).

### Per-rule rollout configuration

`rollout_router` is consulted with the rule_id as the feature key. Config surface (existing convention, new entries):

```yaml
# config/rollout.yaml (or equivalent)
features:
  R-SCOPE-CLARITY-01:         { default: 100, overrides: {} }
  R-PAYMENT-CLARITY-01:       { default: 100, overrides: {} }
  R-SCHEDULE-CLARITY-01:      { default: 100, overrides: {} }
  R-TECHNICAL-SPEC-CLARITY-01:{ default: 100, overrides: {} }
  R-RESPONSIBILITY-01:        { default: 100, overrides: {} }
  R-QUALITY-STANDARDS-01:     { default: 100, overrides: {} }
```

`overrides` lets ops set a specific tenant to 0/100 for incident response. The initial cohort ramp (10→50→100) is implemented via the `default` field over the rollout window; no code change to bump it.

### Honest-scoring contract — extension

`ScoringDiagnostics` and the diagnostics response gain one new optional field:

- `budget_exhausted_reset_date: date | None` (top level, populated when ≥1 rule was denied with that reason).

`category_breakdown[]` entries already carry `state` (`unassessed | assessed_clean | assessed_findings`) from TASK-BCK-060. We extend the contract with:
- New `state` value `"budget_throttled"` — used only when a category's only assessable evaluator was the LLM rule, AND that rule was denied for `budget_exhausted`. Score still `null`. Distinct from `unassessed` (which means "no document / no evidence"); this means "we have the evidence and the budget would have let us, but the tenant's analysis allowance is currently spent."

Advisory alert shape (one per evaluation, not per rule):

```json
{
  "rule_id": "ADV-BUDGET-EXHAUSTED",
  "severity": "info",
  "category": "general",
  "message": "Deep semantic analysis paused: tenant analysis budget exhausted. Resets 2026-06-01.",
  "evidence": {
    "claim": "tenant_budget_exhausted",
    "source_clause_id": null,
    "quote": null
  }
}
```

## Scope

**In scope:**
- `coherence/domain/ports/coherence_llm_gate_port.py` (new): interface + `GateDecision`.
- `coherence/adapters/ai/coherence_llm_gate.py` (new): concrete adapter wiring `prompt_cache` + `rollout_router` + `cost_controller` + `model_router` + `usage_analytics` + LLM client.
- `coherence/graph/nodes.py`: replace `low_budget_mode` early-return with port-based gate consultation; add `_evaluate_via_gate`/`_emit_budget_alert`; update return to include the new advisory alert + reset date.
- `coherence/graph/state.py`: `EvaluationConfig.low_budget_mode` default `True → False`. Keep the field (escape hatch).
- `coherence/models.py`: extend `CategoryBreakdown.state` Literal to include `"budget_throttled"`; add `ScoringDiagnostics.budget_exhausted_reset_date`.
- `coherence/scoring.py`: surface `budget_throttled` state when a category's LLM coverage was denied; promote it through `_calculate_detailed_with_coverage`.
- Rollout config (`config/rollout.yaml` or equivalent existing path): six per-rule entries at 100% default.
- `coherence/alert_generator.py`: add `ADV-BUDGET-EXHAUSTED` entries to `RULE_TITLES`, `RULE_SEVERITIES`, and `TEMPLATES`. **Required**: `assert_v1_rule_ids_have_alert_templates` enforces no orphan rule_ids at import time; without the template entries the engine fails to load.
- Backlog: TASK-BCK-061 entry.

**Out of scope (deferred, explicit):**
- LangSmith eval/A-B harness with labeled golden corpus + precision/recall dashboards (filed as separate follow-up spec).
- Re-pricing per-tenant budget *values* (P3 reads existing limits; setting plan-level caps is a product decision).
- Changing the 6 LLM rule prompts (use as authored).
- Exposing `audit_coverage`/`category_scores` on `/diagnostics` (issue #140).
- Modifying the existing `LLMRulePort` / `LlmRuleEvaluator` — P3 introduces a *gate*, not a replacement for the per-rule evaluator.

## Risk & Testing

**Risks and mitigations:**
1. **LLM clarity-rule false positives at scale** (deterministic-FP saga playbook). Mitigated by per-rule rollout: a misbehaving rule is dialled to 0% without touching the other 5 or losing rollout state for them.
2. **Cache poisoning** (a bad finding gets cached and re-served indefinitely). Mitigated by including `prompt_version` in the cache key and by a documented "bump the version" remediation (no code-level invalidation API needed in P3).
3. **Budget calculation drift** (`usage_analytics.charge` and `cost_controller.can_spend` use different denominators). Mitigated by routing both through the adapter; the adapter is the only call site, so any drift is caught at the seam.
4. **Cache hit on a stale rule definition**: prompt_version inclusion above. Tests cover.

**Test plan (mandatory, will be enumerated in writing-plans):**
- **Router (per-rule rollout) tests** [user-requested]: rule-A at 0% / rule-B at 100% for the same tenant → only rule-B fires; tenant override forces a single tenant on/off without affecting cohort percentage.
- **Budget exhaustion flow tests** [user-requested]: tenant with budget=0 → all 6 rules return `GateDecision(budget_exhausted, reset_date=...)`; node emits exactly ONE `ADV-BUDGET-EXHAUSTED` advisory alert; affected categories show `state="budget_throttled"`, `score=null`; deterministic findings unaffected.
- **Cache flow tests**: identical clause re-evaluated → second call is `state="cache_hit"`, `cost_charged_usd=0.0`, `cost_controller.can_spend` NOT consulted; cache key changes when `prompt_version` bumps.
- **Failure-mode tests**: LLM raises → rule appears in `errors[]`, category does NOT degrade to `budget_throttled` (must remain `unassessed` / partial), budget NOT charged.
- **Hexagonal isolation tests**: node test using a `FakeCoherenceLlmGate` returning canned decisions verifies node behavior without touching real routers.
- **Existing coherence suite (104 tests) stays green.**

## Validation Procedure

After implementation, in a clean worktree off the branch:
1. `make test-api` — full backend suite green.
2. Container restart, then `POST /api/v1/coherence/evaluate/diagnostics` for project `25916ab2-…`:
   - LEGAL / SCOPE / PAYMENT / SCHEDULE / TECHNICAL-SPEC / QUALITY now return actual scores (not `null`), unless tenant has hit budget.
   - `score_missing_dimensions` shrinks proportionally.
   - If forced into `budget_exhausted` (e.g. test tenant with `budget=0`): one advisory alert appears, affected categories show `state="budget_throttled"`, deterministic findings unaffected, deterministic categories' scores unchanged.
3. Flip one rule (e.g. `R-TECHNICAL-SPEC-CLARITY-01`) to 0% in rollout config → re-evaluate → that rule's category falls back to its deterministic-only score, other 5 categories unaffected.

## Open Items at Spec Time

None. The eight decisions are locked; the architecture is verified against existing module conventions; the test plan is enumerated; non-goals are explicit.
