# Honest Coherence Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every coherence subcategory resolve to an honest state — UNASSESSED (`null` + global coverage penalty), ASSESSED_CLEAN (80–90 inherent-risk baseline), or ASSESSED_FINDINGS (baseline minus decay) — so a barely-analyzed contract can never report a fabricated 100 or 0.

**Architecture:** Open/Closed additive `applicability()` on `RuleEvaluator` (finding logic untouched). Graph nodes aggregate a per-category coverage map. `ScoringService` consumes the map: assessed categories decay from a context-aware `HeuristicBaselineProvider` (80–90), unassessed categories become `null` and apply a `assessed/6` global coverage penalty.

**Tech Stack:** Python 3.11, FastAPI, LangGraph, pytest. Backend runs in Docker container `c2pro-api` (uvicorn, **no `--reload`** — restart required to load changes).

**Spec:** `docs/superpowers/specs/2026-05-17-honest-coherence-scoring-design.md`

**Live registry (verified):** 12 deterministic evaluators (2 per category) + 6 LLM rules. Categories: SCOPE, BUDGET, TIME, TECHNICAL, LEGAL, QUALITY.

---

## Pre-flight

- [ ] **Step 0: Branch + baseline test run**

Run:
```bash
cd /c/Users/esus_/Documents/AI/ZTWQ/c2pro && git checkout -b feat/honest-coherence-scoring
cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/ -q 2>&1 | tail -5
```
Expected: 61 passed (current green baseline). Record the number.

---

## Task 1: ApplicabilityState enum + conservative base default

**Files:**
- Modify: `apps/api/src/coherence/rules_engine/base.py`
- Test: `apps/api/tests/unit/coherence/rules_engine/test_applicability.py` (create)

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/unit/coherence/rules_engine/test_applicability.py`:

```python
from src.coherence.models import Clause
from src.coherence.rules_engine.base import ApplicabilityState, RuleEvaluator
from src.coherence.rules_engine.deterministic import SpecReferenceEvaluator


def test_applicability_state_enum_values():
    assert ApplicabilityState.EVALUATED.value == "EVALUATED"
    assert ApplicabilityState.SKIPPED_MISSING_INPUTS.value == "SKIPPED_MISSING_INPUTS"
    assert ApplicabilityState.SKIPPED_DISABLED.value == "SKIPPED_DISABLED"


def test_base_default_evaluated_when_category_matches():
    # SpecReferenceEvaluator.category == "TECHNICAL"; text infers TECHNICAL
    c = Clause(id="t1", text="BOM material standard specification required.", data={})
    # base default is overridden by SpecReference (Task 3); here assert the
    # base contract via a bare evaluator subclass:
    class _Bare(RuleEvaluator):
        rule_id = "X"
        category = "TECHNICAL"
        def evaluate(self, clause):  # noqa: D401
            return None
    assert _Bare().applicability(c) == ApplicabilityState.EVALUATED


def test_base_default_skips_when_category_mismatch():
    c = Clause(id="t2", text="Insurance policy certificate.", data={})  # infers LEGAL

    class _Bare(RuleEvaluator):
        rule_id = "X"
        category = "TECHNICAL"
        def evaluate(self, clause):
            return None
    assert _Bare().applicability(c) == ApplicabilityState.SKIPPED_MISSING_INPUTS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/rules_engine/test_applicability.py -q`
Expected: FAIL — `ImportError: cannot import name 'ApplicabilityState'`.

- [ ] **Step 3: Implement enum + base method**

In `apps/api/src/coherence/rules_engine/base.py`, after the imports block (after line `from ..models import Clause, CoherenceCategory, FindingSignal, impact_to_severity`) add:

```python
from enum import Enum

from .category_utils import infer_category


class ApplicabilityState(Enum):
    """Whether a rule could meaningfully run against a clause."""

    EVALUATED = "EVALUATED"
    SKIPPED_MISSING_INPUTS = "SKIPPED_MISSING_INPUTS"
    SKIPPED_DISABLED = "SKIPPED_DISABLED"
```

Inside `class RuleEvaluator(ABC):`, immediately before `@abstractmethod def evaluate`, add:

```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        """
        Whether this rule can meaningfully evaluate `clause`.

        Conservative default: EVALUATED only if the clause's inferred
        category matches this rule's category; otherwise the rule had no
        real evidence to assess, so SKIPPED_MISSING_INPUTS. Field-dependent
        rules override this to also require their structured inputs.
        """
        if infer_category(clause) == self.category:
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/rules_engine/test_applicability.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/coherence/rules_engine/base.py apps/api/tests/unit/coherence/rules_engine/test_applicability.py
git commit -m "feat(coherence): ApplicabilityState enum + conservative base applicability default"
```

---

## Task 2: LLM evaluator reports SKIPPED_DISABLED in low_budget_mode

**Files:**
- Modify: `apps/api/src/coherence/rules_engine/llm_evaluator.py`
- Test: `apps/api/tests/unit/coherence/rules_engine/test_applicability.py`

- [ ] **Step 1: Add failing test**

Append to `test_applicability.py`:

```python
def test_llm_evaluator_skipped_disabled_in_low_budget():
    from src.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator
    ev = LlmRuleEvaluator(
        rule_id="R-RESPONSIBILITY-01", rule_name="Resp", rule_description="d",
        detection_logic="l", category="legal", low_budget_mode=True,
    )
    c = Clause(id="l1", text="The contractor shall be liable.", data={})
    assert ev.applicability(c) == ApplicabilityState.SKIPPED_DISABLED


def test_llm_evaluator_evaluated_when_enabled():
    from src.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator
    ev = LlmRuleEvaluator(
        rule_id="R-RESPONSIBILITY-01", rule_name="Resp", rule_description="d",
        detection_logic="l", category="legal", low_budget_mode=False,
    )
    c = Clause(id="l1", text="The contractor shall be liable.", data={})
    assert ev.applicability(c) == ApplicabilityState.EVALUATED
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/rules_engine/test_applicability.py -q`
Expected: FAIL — base default returns SKIPPED_MISSING_INPUTS (category mismatch), not SKIPPED_DISABLED.

- [ ] **Step 3: Override applicability on LlmRuleEvaluator**

In `apps/api/src/coherence/rules_engine/llm_evaluator.py`, add this method to `class LlmRuleEvaluator(RuleEvaluator):` (after `__init__`, before the evaluate methods). Add `ApplicabilityState` to the existing `from .base import ...` line:

```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        """LLM rules are disabled wholesale under low_budget_mode."""
        if self.low_budget_mode:
            return ApplicabilityState.SKIPPED_DISABLED
        return ApplicabilityState.EVALUATED
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/rules_engine/test_applicability.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/coherence/rules_engine/llm_evaluator.py apps/api/tests/unit/coherence/rules_engine/test_applicability.py
git commit -m "feat(coherence): LLM evaluators report SKIPPED_DISABLED under low_budget_mode"
```

---

## Task 3: Applicability overrides for all 12 deterministic evaluators

Each rule's input contract derived from its `evaluate_v3()` in `deterministic.py`. `_num` and `infer_category` are already imported there.

**Files:**
- Modify: `apps/api/src/coherence/rules_engine/deterministic.py`
- Test: `apps/api/tests/unit/coherence/rules_engine/test_applicability.py`

- [ ] **Step 1: Add failing tests**

Append to `test_applicability.py`:

```python
import pytest
from src.coherence.rules_engine import deterministic as D
from src.coherence.rules_engine.base import ApplicabilityState as A


@pytest.mark.parametrize("evaluator_cls,data,text,expected", [
    (D.BudgetOverrunEvaluator, {"current": 110.0, "planned": 100.0}, "cost", A.EVALUATED),
    (D.BudgetOverrunEvaluator, {}, "cost overrun", A.SKIPPED_MISSING_INPUTS),
    (D.BudgetLineItemEvaluator, {"unit_price": 2.0, "quantity": 3.0, "line_total": 6.0}, "x", A.EVALUATED),
    (D.BudgetLineItemEvaluator, {"unit_price": 2.0}, "x", A.SKIPPED_MISSING_INPUTS),
    (D.BomBudgetLinkEvaluator, {"bom_items": [{"item_name": "pump"}]}, "x", A.EVALUATED),
    (D.BomBudgetLinkEvaluator, {"bom_items": []}, "x", A.SKIPPED_MISSING_INPUTS),
    (D.SpecReferenceEvaluator, {"material": "concrete"}, "x", A.EVALUATED),
    (D.SpecReferenceEvaluator, {}, "party name", A.SKIPPED_MISSING_INPUTS),
    (D.NoticePeriodEvaluator, {"notice_period_days": 30}, "x", A.EVALUATED),
    (D.NoticePeriodEvaluator, {}, "x", A.SKIPPED_MISSING_INPUTS),
    (D.PenaltyCapEvaluator, {"has_penalty_cap": False}, "x", A.EVALUATED),
    (D.PenaltyCapEvaluator, {}, "x", A.SKIPPED_MISSING_INPUTS),
    (D.ScheduleStatusEvaluator, {"status": "delayed"}, "schedule milestone delay", A.EVALUATED),
    (D.ScheduleStatusEvaluator, {"status": "delayed"}, "payment price invoice", A.SKIPPED_MISSING_INPUTS),
    (D.ScheduleDurationEvaluator, {"start_date": "2026-01-01", "end_date": "2026-02-01"}, "x", A.EVALUATED),
    (D.ScheduleDurationEvaluator, {}, "x", A.SKIPPED_MISSING_INPUTS),
    (D.ScopeVsBudgetCoverageEvaluator, {"deliverables": [{"name": "a"}], "budget_items": [{"id": "b"}]}, "x", A.EVALUATED),
    (D.ScopeVsBudgetCoverageEvaluator, {"deliverables": []}, "x", A.SKIPPED_MISSING_INPUTS),
    (D.ScopeDeliverablesEvaluator, {}, "scope of work deliverable", A.EVALUATED),
    (D.ScopeDeliverablesEvaluator, {}, "insurance policy", A.SKIPPED_MISSING_INPUTS),
    (D.QualityStandardEvaluator, {}, "quality inspection standard", A.EVALUATED),
    (D.QualityStandardEvaluator, {}, "payment terms price", A.SKIPPED_MISSING_INPUTS),
    (D.InspectionFrequencyEvaluator, {}, "quality control inspection", A.EVALUATED),
    (D.InspectionFrequencyEvaluator, {}, "payment advance guarantee", A.SKIPPED_MISSING_INPUTS),
])
def test_deterministic_applicability(evaluator_cls, data, text, expected):
    from src.coherence.models import Clause
    c = Clause(id="c", text=text, data=data)
    assert evaluator_cls().applicability(c) == expected
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/rules_engine/test_applicability.py -k deterministic_applicability -q`
Expected: FAIL — several cases fail (base default keys only on category, ignoring required structured fields).

- [ ] **Step 3: Add `applicability()` to each evaluator class in `deterministic.py`**

`BudgetOverrunEvaluator`:
```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        if _num(clause.data.get("current")) and _num(clause.data.get("planned")):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

`BudgetLineItemEvaluator`:
```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        up, qty = clause.data.get("unit_price"), clause.data.get("quantity")
        total = clause.data.get("line_total") or clause.data.get("total")
        if _num(up) and _num(qty) and _num(total):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

`ScheduleStatusEvaluator`:
```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        if infer_category(clause) in ("TIME", "SCHEDULE") and str(
            clause.data.get("status", "")
        ).strip():
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

`ScheduleDurationEvaluator`:
```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        has_dates = clause.data.get("start_date") and clause.data.get("end_date")
        has_buf = _num(clause.data.get("buffer_days")) or _num(clause.data.get("float_days"))
        if has_dates or has_buf:
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

`SpecReferenceEvaluator`:
```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        if any(
            clause.data.get(k) not in (None, [], "")
            for k in ("material", "bom_items", "item_name", "lead_time_days")
        ):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

`BomBudgetLinkEvaluator`:
```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        bom = clause.data.get("bom_items")
        if isinstance(bom, list) and len(bom) > 0:
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

`PenaltyCapEvaluator`:
```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        d = clause.data
        if (
            d.get("has_penalty_cap") is not None
            or _num(d.get("penalty_cap_pct"))
            or _num(d.get("daily_penalty_pct"))
        ):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

`NoticePeriodEvaluator`:
```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        if _num(clause.data.get("notice_period_days")):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

`ScopeVsBudgetCoverageEvaluator`:
```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        d = clause.data
        deliverables, budget_items = d.get("deliverables"), d.get("budget_items")
        if (
            isinstance(deliverables, list) and deliverables
            and isinstance(budget_items, list) and budget_items
        ):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

`ScopeDeliverablesEvaluator` (text-based — applicable when clause reads as SCOPE):
```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        if infer_category(clause) == "SCOPE":
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

`QualityStandardEvaluator` (text-based — quality/technical prose):
```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        if infer_category(clause) in ("QUALITY", "TECHNICAL"):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

`InspectionFrequencyEvaluator` (text-based — quality/technical prose):
```python
    def applicability(self, clause: Clause) -> ApplicabilityState:
        if infer_category(clause) in ("QUALITY", "TECHNICAL"):
            return ApplicabilityState.EVALUATED
        return ApplicabilityState.SKIPPED_MISSING_INPUTS
```

Add `ApplicabilityState` to the existing `from .base import Finding, RuleEvaluator` import line in `deterministic.py`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/rules_engine/test_applicability.py -q`
Expected: PASS (all parametrized cases green).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/coherence/rules_engine/deterministic.py apps/api/tests/unit/coherence/rules_engine/test_applicability.py
git commit -m "feat(coherence): applicability overrides for all 12 deterministic evaluators"
```

---

## Task 4: coverage_map on graph state with OR-merge reducer

The deterministic and LLM nodes run in parallel; both write `coverage_map`. LangGraph needs a reducer. A category is assessed if **any** evaluator on **any** clause was EVALUATED → boolean OR per category.

**Files:**
- Modify: `apps/api/src/coherence/graph/state.py`
- Test: `apps/api/tests/unit/coherence/graph/test_coverage_reducer.py` (create)

- [ ] **Step 1: Failing test**

Create `apps/api/tests/unit/coherence/graph/test_coverage_reducer.py`:

```python
from src.coherence.graph.state import merge_coverage


def test_merge_coverage_or_semantics():
    a = {"LEGAL": False, "SCOPE": True}
    b = {"LEGAL": True, "BUDGET": False}
    merged = merge_coverage(a, b)
    assert merged["LEGAL"] is True   # any True wins
    assert merged["SCOPE"] is True
    assert merged["BUDGET"] is False


def test_merge_coverage_handles_empty():
    assert merge_coverage({}, {"TIME": True}) == {"TIME": True}
    assert merge_coverage({"TIME": True}, {}) == {"TIME": True}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/graph/test_coverage_reducer.py -q`
Expected: FAIL — `ImportError: cannot import name 'merge_coverage'`.

- [ ] **Step 3: Implement reducer + state field**

In `apps/api/src/coherence/graph/state.py`, near the top-level helpers (before `class CoherenceGraphState`) add:

```python
def merge_coverage(
    left: dict[str, bool], right: dict[str, bool]
) -> dict[str, bool]:
    """LangGraph reducer: a category is assessed if assessed in EITHER branch."""
    merged = dict(left)
    for category, assessed in right.items():
        merged[category] = merged.get(category, False) or assessed
    return merged
```

Inside `class CoherenceGraphState:`, in the "Findings from evaluators" group (next to `cross_signals`), add:

```python
    coverage_map: Annotated[dict[str, bool], merge_coverage] = field(
        default_factory=dict
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/graph/test_coverage_reducer.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/coherence/graph/state.py apps/api/tests/unit/coherence/graph/test_coverage_reducer.py
git commit -m "feat(coherence): coverage_map state field + OR-merge reducer"
```

---

## Task 5: deterministic_evaluate emits coverage_map

**Files:**
- Modify: `apps/api/src/coherence/graph/nodes.py` (`deterministic_evaluate`, ~line 256–300)
- Test: `apps/api/tests/unit/coherence/graph/test_coverage_nodes.py` (create)

- [ ] **Step 1: Failing test**

Create `apps/api/tests/unit/coherence/graph/test_coverage_nodes.py`:

```python
from src.coherence.graph.nodes import deterministic_evaluate
from src.coherence.graph.state import CoherenceGraphState
from src.coherence.models import Clause


def test_deterministic_node_marks_assessed_and_unassessed():
    # A clearly TECHNICAL clause with material → TECHNICAL assessed.
    # No budget numbers anywhere → BUDGET stays unassessed.
    state = CoherenceGraphState(
        project_id="p",
        clauses=[Clause(id="c1", text="BOM material standard", data={"material": "steel"})],
    )
    out = deterministic_evaluate(state)
    cov = out["coverage_map"]
    assert cov.get("TECHNICAL") is True
    assert cov.get("BUDGET", False) is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/graph/test_coverage_nodes.py::test_deterministic_node_marks_assessed_and_unassessed -q`
Expected: FAIL — `KeyError: 'coverage_map'` (node doesn't return it yet).

- [ ] **Step 3: Update the node**

In `apps/api/src/coherence/graph/nodes.py`, add to imports near the other rules_engine imports:

```python
from ..rules_engine.base import ApplicabilityState
```

Replace the body of `deterministic_evaluate` (the loop + return) with:

```python
    signals: list[FindingSignal] = []
    errors: list[str] = []
    coverage: dict[str, bool] = {}
    clauses_to_eval = state.clauses

    for clause in clauses_to_eval:
        for evaluator in evaluators:
            category = evaluator.category
            try:
                app_state = evaluator.applicability(clause)
            except Exception as e:  # noqa: BLE001 — applicability must never crash eval
                logger.warning(f"applicability {evaluator.rule_id} failed: {e}")
                app_state = ApplicabilityState.SKIPPED_MISSING_INPUTS

            if app_state == ApplicabilityState.EVALUATED:
                coverage[category] = True
                try:
                    signal = evaluator.evaluate_v3(clause)
                    if signal is not None:
                        signals.append(signal)
                except Exception as e:
                    error_msg = (
                        f"Evaluator {evaluator.rule_id} failed on clause {clause.id}: {e}"
                    )
                    logger.warning(error_msg)
                    errors.append(error_msg)
            else:
                coverage.setdefault(category, False)

    logger.info(
        f"deterministic_evaluate: {len(signals)} findings, "
        f"coverage={coverage}"
    )

    return {
        "deterministic_signals": signals,
        "coverage_map": coverage,
        "errors": errors,
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/graph/test_coverage_nodes.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/coherence/graph/nodes.py apps/api/tests/unit/coherence/graph/test_coverage_nodes.py
git commit -m "feat(coherence): deterministic_evaluate emits per-category coverage_map"
```

---

## Task 6: llm_semantic_evaluate emits coverage_map (incl. disabled path)

Under `low_budget_mode` the node early-returns. It must still record that the 6 LLM categories were **not** assessed by the LLM layer (they may still be assessed by deterministic rules — the OR-reducer handles that).

**Files:**
- Modify: `apps/api/src/coherence/graph/nodes.py` (`llm_semantic_evaluate_async`, ~line 325–378)
- Test: `apps/api/tests/unit/coherence/graph/test_coverage_nodes.py`

- [ ] **Step 1: Failing test**

Append to `test_coverage_nodes.py`:

```python
from src.coherence.graph.nodes import llm_semantic_evaluate


def test_llm_node_low_budget_marks_categories_not_llm_assessed():
    state = CoherenceGraphState(
        project_id="p",
        clauses=[Clause(id="c1", text="The contractor shall be liable.", data={})],
    )
    # default config.low_budget_mode is True
    out = llm_semantic_evaluate(state)
    cov = out["coverage_map"]
    # LLM disabled → it contributes False for its categories (OR-reducer
    # lets deterministic rules still flip them True elsewhere)
    assert cov.get("LEGAL") is False
    assert out["llm_signals"] == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/graph/test_coverage_nodes.py::test_llm_node_low_budget_marks_categories_not_llm_assessed -q`
Expected: FAIL — early-return dict has no `coverage_map`.

- [ ] **Step 3: Update the low_budget early-return and the main path**

In `llm_semantic_evaluate_async`, replace the `if state.config.low_budget_mode:` block (nodes.py ~326-332) with:

```python
    # Six canonical LLM categories (registry V1_LLM_RULE_IDS map)
    _LLM_CATEGORIES = ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")

    if state.config.low_budget_mode:
        logger.info("llm_semantic_evaluate: skipped (low_budget_mode=True)")
        return {
            "llm_signals": [],
            "llm_cost_usd": 0.0,
            "llm_calls_count": 0,
            "coverage_map": {cat: False for cat in _LLM_CATEGORIES},
        }
```

In the same function's success path, build coverage from applicability and add it to the return dict. Replace the inner evaluation loop and final `return` with:

```python
        coverage: dict[str, bool] = {}
        for clause in state.clauses:
            for evaluator in evaluators:
                category = evaluator.category
                try:
                    app_state = evaluator.applicability(clause)
                except Exception:  # noqa: BLE001
                    app_state = ApplicabilityState.SKIPPED_DISABLED
                if app_state == ApplicabilityState.EVALUATED:
                    coverage[category] = True
                    try:
                        signal = await evaluator.evaluate_v3_async(clause)
                        if signal is not None:
                            signals.append(signal)
                    except Exception as e:
                        msg = f"LLM evaluator {evaluator.rule_id} failed for clause {clause.id}: {e}"
                        logger.warning(msg)
                        errors.append(msg)
                else:
                    coverage.setdefault(category, False)

        total_cost = sum(getattr(e, "total_cost_usd", 0.0) for e in evaluators)
        total_calls = sum(getattr(e, "llm_calls_count", 0) for e in evaluators)
```

And change the final `return {...}` of the async function to include:

```python
    return {
        "llm_signals": signals,
        "llm_cost_usd": total_cost,
        "llm_calls_count": total_calls,
        "coverage_map": coverage,
        "errors": errors,
    }
```

(`ApplicabilityState` is already imported from Task 5.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/graph/test_coverage_nodes.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/coherence/graph/nodes.py apps/api/tests/unit/coherence/graph/test_coverage_nodes.py
git commit -m "feat(coherence): llm_semantic_evaluate emits coverage_map incl. disabled path"
```

---

## Task 7: HeuristicBaselineProvider + BaselineContext

**Files:**
- Modify: `apps/api/src/coherence/scoring.py`
- Test: `apps/api/tests/unit/coherence/test_baseline_provider.py` (create)

- [ ] **Step 1: Failing test**

Create `apps/api/tests/unit/coherence/test_baseline_provider.py`:

```python
from src.coherence.scoring import BaselineContext, HeuristicBaselineProvider


def test_single_assessed_category_gets_high():
    p = HeuristicBaselineProvider()
    ctx = BaselineContext(total_findings_other_categories=0,
                           total_assessed_categories=1,
                           avg_impact_other_categories=0.0, num_clauses=10)
    assert p.baseline_for("LEGAL", ctx) == 90.0


def test_clean_elsewhere_pushes_toward_high():
    p = HeuristicBaselineProvider()
    ctx = BaselineContext(total_findings_other_categories=0,
                           total_assessed_categories=3,
                           avg_impact_other_categories=0.0, num_clauses=10)
    assert p.baseline_for("LEGAL", ctx) == 90.0


def test_high_risk_elsewhere_drops_toward_low():
    p = HeuristicBaselineProvider()
    ctx = BaselineContext(total_findings_other_categories=8,
                           total_assessed_categories=3,
                           avg_impact_other_categories=0.8, num_clauses=10)
    b = p.baseline_for("LEGAL", ctx)
    assert b == 80.0  # min(1.0, 0.8*1.5)=1.0 → HIGH-(HIGH-LOW)*1.0 = 80


def test_baseline_stays_in_band():
    p = HeuristicBaselineProvider()
    for impact in (0.0, 0.1, 0.3, 0.5, 0.9, 5.0):
        ctx = BaselineContext(1, 4, impact, 10)
        assert 80.0 <= p.baseline_for("BUDGET", ctx) <= 90.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/test_baseline_provider.py -q`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement provider**

In `apps/api/src/coherence/scoring.py`, after the `ScoringDiagnostics` dataclass (before `class ScoringService:`) add (`dataclass` and `math` are already imported at top of file):

```python
@dataclass
class BaselineContext:
    """Signals about the rest of the document used to flex the baseline."""

    total_findings_other_categories: int
    total_assessed_categories: int
    avg_impact_other_categories: float
    num_clauses: int


class HeuristicBaselineProvider:
    """
    Inherent-risk baseline for an assessed-but-clean category.

    Band [80, 90]. Clean elsewhere → 90; heavily alerted elsewhere → 80.
    Interface-isolated so a trained regression model can replace it later.
    """

    LOW = 80.0
    HIGH = 90.0
    _RISK_GAIN = 1.5

    def baseline_for(self, category: str, ctx: BaselineContext) -> float:
        if ctx.total_assessed_categories <= 1:
            return self.HIGH
        global_risk = min(1.0, max(0.0, ctx.avg_impact_other_categories * self._RISK_GAIN))
        return self.HIGH - (self.HIGH - self.LOW) * global_risk
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/test_baseline_provider.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/coherence/scoring.py apps/api/tests/unit/coherence/test_baseline_provider.py
git commit -m "feat(coherence): HeuristicBaselineProvider (80-90 risk-flexed band)"
```

---

## Task 8: ScoringDiagnostics extension + coverage-aware calculate_detailed

**Files:**
- Modify: `apps/api/src/coherence/scoring.py` (`ScoringDiagnostics`, `calculate_detailed`)
- Test: `apps/api/tests/unit/coherence/test_honest_scoring.py` (create)

- [ ] **Step 1: Failing test**

Create `apps/api/tests/unit/coherence/test_honest_scoring.py`:

```python
from src.coherence.models import FindingSignal
from src.coherence.scoring import ScoringService


def _sig(cat, impact=0.5):
    return FindingSignal(rule_id="R", clause_id="c", impact_score=impact,
                         confidence=1.0, severity="medium", category=cat,
                         evidence_summary="e", quote="q", raw_data={})


def test_unassessed_categories_are_null_and_penalize_global():
    svc = ScoringService()
    cov = {"SCOPE": True, "TECHNICAL": True, "BUDGET": False,
           "TIME": False, "LEGAL": False, "QUALITY": False}
    d = svc.calculate_detailed(signals=[_sig("TECHNICAL")], num_clauses=20,
                               coverage_map=cov)
    assert d.category_scores["BUDGET"] is None
    assert d.category_scores["LEGAL"] is None
    assert "BUDGET" in d.missing_dimensions
    # 2/6 assessed → global heavily coverage-penalized
    assert d.score is not None and d.score < 40


def test_assessed_clean_lands_in_baseline_band():
    svc = ScoringService()
    cov = {c: True for c in ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")}
    # only TECHNICAL has a finding; LEGAL is assessed & clean
    d = svc.calculate_detailed(signals=[_sig("TECHNICAL", 0.4)], num_clauses=20,
                               coverage_map=cov)
    assert 80.0 <= d.category_scores["LEGAL"] <= 90.0
    assert d.category_scores["TECHNICAL"] < d.category_scores["LEGAL"]  # finding pulls below baseline


def test_no_coverage_returns_none():
    svc = ScoringService()
    d = svc.calculate_detailed(signals=[], num_clauses=5, coverage_map={})
    assert d.score is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/test_honest_scoring.py -q`
Expected: FAIL — `calculate_detailed` has no `coverage_map` param / `category_scores` attr.

- [ ] **Step 3: Extend ScoringDiagnostics**

In `scoring.py`, add two fields to `class ScoringDiagnostics:` (after `missing_dimensions`):

```python
    category_scores: dict[str, float | None] | None = None
    audit_coverage: dict[str, float] | None = None
```

- [ ] **Step 4: Add coverage-aware branch to `calculate_detailed`**

In `scoring.py`, at the very start of `calculate_detailed` (before the existing `_ = num_rules` line), insert a coverage-aware path that runs only when a `coverage_map` is supplied. Change the signature to add the parameter:

```python
    def calculate_detailed(
        self,
        signals: list[FindingSignal],
        num_clauses: int = 1,
        num_rules: int = 5,  # noqa: ARG002
        poor_extraction_quality: bool = False,
        missing_dimensions: list[str] | None = None,
        coverage_map: dict[str, bool] | None = None,
    ) -> ScoringDiagnostics:
        _ = num_rules
        if coverage_map is not None:
            return self._calculate_detailed_with_coverage(
                signals, num_clauses, coverage_map, poor_extraction_quality
            )
        # ---- legacy path below (unchanged) ----
```

Then add the new method to `ScoringService` (after `calculate_detailed`):

```python
    _ALL_CATEGORIES = ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")

    def _calculate_detailed_with_coverage(
        self,
        signals: list[FindingSignal],
        num_clauses: int,
        coverage_map: dict[str, bool],
        poor_extraction_quality: bool,
    ) -> ScoringDiagnostics:
        assessed = [c for c in self._ALL_CATEGORIES if coverage_map.get(c, False)]
        unassessed = [c for c in self._ALL_CATEGORIES if not coverage_map.get(c, False)]

        if not assessed or poor_extraction_quality:
            return ScoringDiagnostics(
                score=None, total_findings=0, deterministic_findings=0,
                llm_findings=0,
                severity_distribution={"critical": 0, "high": 0, "medium": 0, "low": 0},
                avg_impact=0.0, avg_confidence=0.0, scope_factor=1.0,
                penalty_density=0.0, raw_penalty_sum=0.0,
                category_contributions={}, reason="insufficient_evidence",
                missing_dimensions=unassessed,
                category_scores={c: None for c in self._ALL_CATEGORIES},
                audit_coverage={"assessed": len(assessed), "total": 6,
                                "pct": round(len(assessed) / 6 * 100, 1)},
            )

        provider = HeuristicBaselineProvider()
        scope_factor = self.config.compute_scope_factor(num_clauses)

        cat_penalty: dict[str, float] = defaultdict(float)
        for s in signals:
            cat_penalty[s.category] += self._compute_signal_contribution(s)

        total_findings = len(signals)
        category_scores: dict[str, float | None] = {c: None for c in self._ALL_CATEGORIES}

        for category in assessed:
            cat_signals = [s for s in signals if s.category == category]
            other = [s for s in signals if s.category != category]
            other_cnt = max(1, len(other))
            ctx = BaselineContext(
                total_findings_other_categories=len(other),
                total_assessed_categories=len(assessed),
                avg_impact_other_categories=(
                    sum(o.impact_score for o in other) / other_cnt if other else 0.0
                ),
                num_clauses=num_clauses,
            )
            baseline = provider.baseline_for(category, ctx)
            density = cat_penalty[category] / scope_factor
            raw = baseline * math.exp(-self.config.decay_lambda * density)
            category_scores[category] = round(
                max(self.config.min_score, min(raw, baseline)), 1
            )

        assessed_vals = [category_scores[c] for c in assessed]
        mean_assessed = sum(assessed_vals) / len(assessed_vals)
        coverage_ratio = len(assessed) / 6.0
        global_score = round(mean_assessed * coverage_ratio, 1)

        sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for s in signals:
            if s.severity in sev:
                sev[s.severity] += 1

        return ScoringDiagnostics(
            score=global_score,
            total_findings=total_findings,
            deterministic_findings=sum(1 for s in signals if s.source == "deterministic"),
            llm_findings=sum(1 for s in signals if s.source == "llm"),
            severity_distribution=sev,
            avg_impact=round(
                sum(s.impact_score for s in signals) / total_findings, 3
            ) if total_findings else 0.0,
            avg_confidence=round(
                sum(s.confidence for s in signals) / total_findings, 3
            ) if total_findings else 0.0,
            scope_factor=round(scope_factor, 3),
            penalty_density=round(sum(cat_penalty.values()) / scope_factor, 4),
            raw_penalty_sum=round(sum(cat_penalty.values()), 4),
            category_contributions=dict(cat_penalty),
            reason=None if total_findings else "assessed_clean",
            missing_dimensions=unassessed,
            category_scores=category_scores,
            audit_coverage={"assessed": len(assessed), "total": 6,
                            "pct": round(len(assessed) / 6 * 100, 1)},
        )
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/test_honest_scoring.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/coherence/scoring.py apps/api/tests/unit/coherence/test_honest_scoring.py
git commit -m "feat(coherence): coverage-aware calculate_detailed with baseline + coverage penalty"
```

---

## Task 9: scoring_arbiter passes coverage_map and surfaces category_scores

**Files:**
- Modify: `apps/api/src/coherence/graph/nodes.py` (`scoring_arbiter`, ~line 656–714)

- [ ] **Step 1: Failing test**

Create `apps/api/tests/unit/coherence/graph/test_scoring_arbiter_coverage.py`:

```python
from src.coherence.graph.nodes import scoring_arbiter
from src.coherence.graph.state import CoherenceGraphState
from src.coherence.models import FindingSignal


def test_arbiter_threads_coverage_and_category_scores():
    state = CoherenceGraphState(project_id="p")
    state.deterministic_signals = [
        FindingSignal(rule_id="DET-TEC-SPEC", clause_id="c", impact_score=0.45,
                      confidence=1.0, severity="medium", category="TECHNICAL",
                      evidence_summary="e", quote="q", raw_data={})
    ]
    state.coverage_map = {"TECHNICAL": True, "SCOPE": True, "BUDGET": False,
                          "TIME": False, "LEGAL": False, "QUALITY": False}
    out = scoring_arbiter(state)
    assert out["diagnostics"]["category_scores"]["BUDGET"] is None
    assert out["diagnostics"]["category_scores"]["TECHNICAL"] is not None
    assert "BUDGET" in out["diagnostics"]["missing_dimensions"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/graph/test_scoring_arbiter_coverage.py -q`
Expected: FAIL — `category_scores` not in diagnostics dict.

- [ ] **Step 3: Update `scoring_arbiter`**

In `nodes.py`, in `scoring_arbiter`, change the `calculate_detailed(...)` call to pass coverage and drop the legacy `missing_dimensions=` arg:

```python
    diagnostics = scoring_service.calculate_detailed(
        signals=all_signals,
        num_clauses=len(state.clauses),
        num_rules=12,
        poor_extraction_quality=state.config.poor_extraction_quality,
        coverage_map=state.coverage_map,
    )
```

In the returned `"diagnostics": { ... }` dict literal, add these two keys:

```python
            "category_scores": diagnostics.category_scores,
            "audit_coverage": diagnostics.audit_coverage,
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/graph/test_scoring_arbiter_coverage.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/coherence/graph/nodes.py apps/api/tests/unit/coherence/graph/test_scoring_arbiter_coverage.py
git commit -m "feat(coherence): scoring_arbiter threads coverage_map + surfaces category_scores"
```

---

## Task 10: CategoryBreakdown model — nullable score + state + baseline_estimated

**Files:**
- Modify: `apps/api/src/coherence/models.py` (`CategoryBreakdown`, ~line 196)
- Test: `apps/api/tests/unit/coherence/test_category_breakdown_model.py` (create)

- [ ] **Step 1: Failing test**

Create `apps/api/tests/unit/coherence/test_category_breakdown_model.py`:

```python
from src.coherence.models import CategoryBreakdown, SeverityCount


def test_category_breakdown_accepts_null_score_and_state():
    cb = CategoryBreakdown(
        category="legal", score=None, alert_count=0,
        severity_breakdown=SeverityCount(critical=0, high=0, medium=0, low=0, info=0),
        impact_percentage=0.0, state="unassessed", baseline_estimated=False,
    )
    assert cb.score is None
    assert cb.state == "unassessed"
    assert cb.baseline_estimated is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/test_category_breakdown_model.py -q`
Expected: FAIL — `score` is non-nullable; `state`/`baseline_estimated` unknown fields.

- [ ] **Step 3: Update the model**

In `apps/api/src/coherence/models.py`, replace the `score` field of `class CategoryBreakdown(BaseModel):` and add two fields:

```python
    score: float | None = Field(
        None, description="Category score (null when UNASSESSED)."
    )
    alert_count: int = Field(..., description="Total number of alerts in this category.")
    severity_breakdown: SeverityCount = Field(
        ..., description="Breakdown of alerts by severity within this category."
    )
    impact_percentage: float = Field(
        ..., description="Percentage of impact this category has on the overall score."
    )
    state: str = Field(
        "assessed_findings",
        description="unassessed | assessed_clean | assessed_findings",
    )
    baseline_estimated: bool = Field(
        False, description="True when score is the inherent-risk baseline (clean)."
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/test_category_breakdown_model.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/coherence/models.py apps/api/tests/unit/coherence/test_category_breakdown_model.py
git commit -m "feat(coherence): CategoryBreakdown supports null score + state + baseline_estimated"
```

---

## Task 11: Rewrite _build_category_breakdown + wire format_output

**Files:**
- Modify: `apps/api/src/coherence/graph/nodes.py` (`_build_category_breakdown` ~831-909; `format_output` call site ~750)
- Test: `apps/api/tests/unit/coherence/graph/test_category_breakdown_states.py` (create)

- [ ] **Step 1: Failing test**

Create `apps/api/tests/unit/coherence/graph/test_category_breakdown_states.py`:

```python
from src.coherence.graph.nodes import _build_category_breakdown
from src.coherence.models import FindingSignal


def _sig(cat):
    return FindingSignal(rule_id="R", clause_id="c", impact_score=0.45,
                         confidence=1.0, severity="medium", category=cat,
                         evidence_summary="e", quote="q", raw_data={})


def test_three_states_present():
    signals = [_sig("TECHNICAL")]
    coverage = {"TECHNICAL": True, "SCOPE": True, "BUDGET": False,
                "TIME": False, "LEGAL": False, "QUALITY": False}
    cat_scores = {"TECHNICAL": 71.0, "SCOPE": 88.0, "BUDGET": None,
                  "TIME": None, "LEGAL": None, "QUALITY": None}
    bd = _build_category_breakdown(signals, coverage, cat_scores)
    by = {b.category: b for b in bd}
    assert by["technical"].state == "assessed_findings" and by["technical"].score == 71.0
    assert by["scope"].state == "assessed_clean" and by["scope"].baseline_estimated is True
    assert by["budget"].state == "unassessed" and by["budget"].score is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/graph/test_category_breakdown_states.py -q`
Expected: FAIL — current `_build_category_breakdown(signals, overall_score)` signature/behaviour.

- [ ] **Step 3: Replace `_build_category_breakdown`**

In `nodes.py`, replace the entire `_build_category_breakdown` function (and delete the now-unused `_missing_dimensions` if no other caller — verify with `grep -n _missing_dimensions src/coherence/graph/nodes.py`; keep if referenced elsewhere) with:

```python
_CAT_LEGACY = {
    "SCOPE": "scope", "BUDGET": "financial", "TIME": "schedule",
    "TECHNICAL": "technical", "LEGAL": "legal", "QUALITY": "quality",
}


def _build_category_breakdown(
    signals: list[FindingSignal],
    coverage_map: dict[str, bool],
    category_scores: dict[str, float | None],
) -> list[CategoryBreakdown]:
    """Honest per-category breakdown: unassessed / assessed_clean / assessed_findings."""
    breakdown: list[CategoryBreakdown] = []
    for canonical, legacy in _CAT_LEGACY.items():
        cat_signals = [s for s in signals if s.category == canonical]
        sev = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for s in cat_signals:
            if s.severity in sev:
                sev[s.severity] += 1
        assessed = coverage_map.get(canonical, False)
        score = category_scores.get(canonical)
        if not assessed:
            state, baseline_estimated, score = "unassessed", False, None
        elif not cat_signals:
            state, baseline_estimated = "assessed_clean", True
        else:
            state, baseline_estimated = "assessed_findings", False
        total_impact = sum(s.impact_score for s in signals) or 1.0
        cat_impact = sum(s.impact_score for s in cat_signals)
        breakdown.append(
            CategoryBreakdown(
                category=legacy,
                score=score,
                alert_count=len(cat_signals),
                severity_breakdown=SeverityCount(**sev),
                impact_percentage=round(cat_impact / total_impact * 100, 2),
                state=state,
                baseline_estimated=baseline_estimated,
            )
        )
    breakdown.sort(key=lambda b: b.impact_percentage, reverse=True)
    return breakdown
```

- [ ] **Step 4: Update the `format_output` call site**

In `nodes.py` `format_output` (~line 750) replace:

```python
    category_breakdown = _build_category_breakdown(state.all_signals, state.score)
```

with:

```python
    category_breakdown = _build_category_breakdown(
        state.all_signals,
        state.coverage_map,
        state.diagnostics.get("category_scores") or {},
    )
```

Also in `format_output`, update the `score_missing_dimensions=` kwarg of `EnrichedCoherenceResult(...)` to prefer the coverage-derived list:

```python
        score_missing_dimensions=state.diagnostics.get("missing_dimensions"),
```

(leave as-is if already that value — confirm via grep; the value now originates from the coverage path).

- [ ] **Step 5: Run to verify it passes**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/graph/test_category_breakdown_states.py -q`
Expected: PASS (1 passed).

- [ ] **Step 6: Full coherence regression**

Run: `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/ -q 2>&1 | tail -8`
Expected: all green. If any legacy test asserts old `_build_category_breakdown(signals, score)` signature or `score==100.0` fabrication, update that test to the new three-state contract (the old behaviour was the bug). Document each such change in the commit message.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/coherence/graph/nodes.py apps/api/tests/unit/coherence/graph/test_category_breakdown_states.py
git commit -m "feat(coherence): honest three-state category breakdown; remove fabricated 100s"
```

---

## Task 12: End-to-end validation + backlog

**Files:**
- Modify: `backlogs/BCK_BACKEND.md`, `C2PRO_MASTER_BACKLOG.md`

- [ ] **Step 1: Rebuild-free reload + full suite**

```bash
cd /c/Users/esus_/Documents/AI/ZTWQ/c2pro/apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/unit/coherence/ -q 2>&1 | tail -8
```
Expected: ≥ the Step 0 baseline count, all green.

- [ ] **Step 2: Restart container (uvicorn has no --reload)**

```bash
docker restart c2pro-api && sleep 25 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health
```
Expected: `200`.

- [ ] **Step 3: Live diagnostics check**

```bash
TOKEN="<paste current bearer from Swagger>"
curl -s -X POST 'http://localhost:8000/api/v1/coherence/evaluate/diagnostics' \
 -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
 -d '{"project_id":"25916ab2-03a3-4df5-bf5f-1f8dde07fb8c","include_clause_details":true}' \
 -o cov.json -w "HTTP %{http_code}\n"
python -c "import json;d=json.load(open('cov.json',encoding='utf-8'));print('score',d['overall_score']);[print(c['category'],c.get('state'),c['score']) for c in d['category_breakdown']]"
rm cov.json
```
Expected: no category shows exactly `100` or `0`; BUDGET/TIME show `state=unassessed`, `score=null` when contract-only; an assessed-clean category sits in 80–90; `score_missing_dimensions` non-empty; global score reflects the coverage penalty.

- [ ] **Step 4: Backlog (delegate markdown edit per memory [[feedback-master-no-backlog-edits]] if applicable; otherwise edit directly)**

Add to `backlogs/BCK_BACKEND.md` active table and completed summary, and to `C2PRO_MASTER_BACKLOG.md` Change Log:

```
| [x] | P0 | `TASK-BCK-060` | BCK-055 | Honest coherence scoring: ApplicabilityState (Open/Closed), per-category coverage_map, HeuristicBaselineProvider (80-90 risk-flexed band), coverage-penalized global score. Eliminates fabricated 100/0 subcategory scores; unassessed dimensions return null + drag global via assessed/6 penalty. | Design 2026-05-17 |
```

- [ ] **Step 5: Commit + push**

```bash
git add backlogs/BCK_BACKEND.md C2PRO_MASTER_BACKLOG.md
git commit -m "docs(backlog): TASK-BCK-060 honest coherence scoring complete"
git push -u origin feat/honest-coherence-scoring
```

---

## Self-Review Notes

- **Spec coverage:** three states (Tasks 8/11), `applicability()` Open/Closed (Tasks 1–3), coverage map + reducer (Tasks 4–6), `HeuristicBaselineProvider` 80–90 (Task 7), decay-from-baseline + `assessed/6` penalty (Task 8), API `state`/`baseline_estimated`/null score/`audit_coverage` (Tasks 8/10/11), LLM `SKIPPED_DISABLED` surfaced (Tasks 2/6), `low_budget_mode` default unchanged (no task touches `state.py:115`). All spec sections mapped.
- **Deliberate YAGNI deviation from spec:** coverage_map is `dict[str,bool]` (assessed?) not the full per-evaluator enum. The enum still exists and is unit-tested per evaluator (Tasks 1–3); only the category-level aggregate needs the bool. Documented here intentionally.
- **Type consistency:** `coverage_map: dict[str,bool]`, `category_scores: dict[str,float|None]`, `merge_coverage`, `BaselineContext`, `HeuristicBaselineProvider.baseline_for` names consistent across Tasks 4–11.
- **Risk:** legacy tests asserting the old fabricated-100 behaviour will fail at Task 11 Step 6 — that is expected and the instruction is to update them to the corrected contract, not to preserve the bug.
