# Design: Honest Coherence Scoring (Assessed vs. Unassessed)

**Date:** 2026-05-17
**Status:** Approved (design); pending implementation plan
**Owner:** Coherence Engine
**Related backlog:** TASK-BCK-060 (to be created)

## Problem

For a single-document project (one EPC contract, no schedule, no budget doc),
the Coherence Engine returns a perfect **100** for Legal, Scope, Budget, and
Time with zero alerts each, while Technical collapses. A 100/100 legal score on
a 37-crore turnkey contract the engine barely analyzed is not credibility — it
is the engine reporting "clean" for dimensions it never assessed.

Two compounding root causes (both confirmed in code, not hypothesised):

1. **`graph/state.py:115` — `low_budget_mode: bool = True` is the hardcoded
   default.** This skips the entire LLM semantic evaluation node
   (`nodes.py:326`). The 7 prose-reading semantic rules
   (`R-RESPONSIBILITY-01`, `R-TERMINATION-01`, `R-SCOPE-CLARITY-01`,
   `R-PAYMENT-CLARITY-01`, `R-QUALITY-STANDARDS-01`,
   `R-TECHNICAL-SPEC-CLARITY-01`, `R-SCHEDULE-CLARITY-01`) never run.
   Deterministic rules only fire on structured numeric fields a turnkey
   contract states in prose, not fields.
2. **`nodes.py:891-907` — explicit code fabricates `score=100.0`** for every
   category with no findings. `_missing_dimensions()` (`nodes.py:912`) only
   ever flags `schedule`/`budget` by document type, so Legal/Scope/Quality
   always receive the fabricated 100.

`evaluate_v3()` returning `None` is itself ambiguous: it means *both* "I ran,
nothing wrong" *and* "I could not run." That conflation is the core defect.

## Decision Summary

A subcategory score is **never** 0 or 100. Every subcategory resolves to one
of three states:

| State | Trigger | Score output | API surface |
|---|---|---|---|
| **UNASSESSED** | *All* evaluators for the category returned `SKIPPED_*` | `null` | In `score_missing_dimensions`; drives global coverage penalty |
| **ASSESSED_CLEAN** | ≥1 evaluator `EVALUATED`, 0 findings | `HeuristicBaselineProvider` value (80–90 band) | Normal score, `baseline_estimated: true` |
| **ASSESSED_FINDINGS** | ≥1 evaluator `EVALUATED`, ≥1 finding | `baseline − decay(findings)` | Normal score |

Clean ≠ perfect: a clean assessed category gets an inherent-risk baseline, not
100. Unassessed ≠ clean: it is an honest `null` that actively reduces the
global score so missing documents become the headline.

## Architecture

### 1. Approach A — additive `applicability()` (Open/Closed)

`evaluate_v3()` finding logic is **untouched** (protects the 16 findings
stabilised on 2026-05-17). `rules_engine/base.py` gains:

```python
class ApplicabilityState(Enum):
    EVALUATED              # ran against real evidence
    SKIPPED_MISSING_INPUTS # required fields/clauses absent
    SKIPPED_DISABLED       # e.g. LLM rule under low_budget_mode

class RuleEvaluator:
    def applicability(self, clause, context) -> ApplicabilityState:
        # default: EVALUATED if infer_category(clause) == self.category
        #          else SKIPPED_MISSING_INPUTS
        ...
```

- Deterministic rules whose finding logic needs specific fields (e.g.
  `BudgetOverrunEvaluator` needs `current` + `planned`) override
  `applicability()` to return `SKIPPED_MISSING_INPUTS` when those inputs are
  absent. Override only where the input contract is non-trivial; otherwise the
  base default applies.
- `LlmRuleEvaluator` base override returns `SKIPPED_DISABLED` when
  `low_budget_mode` is on.
- Conservative bias: a rule that cannot positively confirm it had evidence
  returns `SKIPPED_MISSING_INPUTS`, never silently "assessed".

### 2. Coverage aggregation in the graph nodes

The deterministic and LLM nodes in `nodes.py` call `applicability()` alongside
`evaluate_v3()` and emit a per-category coverage map, e.g.
`{LEGAL: EVALUATED, TIME: SKIPPED_MISSING_INPUTS, ...}`. A category is
**ASSESSED** iff ≥1 of its evaluators returned `EVALUATED`; otherwise
**UNASSESSED**.

`_build_category_breakdown` no longer fabricates `score=100.0` rows.
`_missing_dimensions()` is replaced by aggregation of the coverage map across
all 6 categories (not just doc-type schedule/budget).

### 3. `HeuristicBaselineProvider` (in `scoring.py`)

```python
class BaselineContext:
    total_findings_other_categories: int
    total_assessed_categories: int
    avg_impact_other_categories: float
    num_clauses: int

class HeuristicBaselineProvider:
    LOW, HIGH = 80.0, 90.0
    def baseline_for(self, category: str, ctx: BaselineContext) -> float:
        # global_risk in [0,1] from findings density + avg impact of
        # OTHER categories. Clean elsewhere -> 90; heavily alerted -> 80.
        return self.HIGH - (self.HIGH - self.LOW) * global_risk
```

Isolated behind an interface so a trained regression model can replace the
heuristic later with zero downstream change. No labelled corpus exists yet, so
the heuristic ships now; the regression is explicitly out of scope.

### 4. Scoring math

Per assessed category, `category_density` is that category's own penalty
contribution (sum of its findings' weighted impact) divided by the shared
scope factor — it is **not** the global penalty density:

```
category_density = sum(weighted_impact of THIS category's findings) / scope_factor
score = clamp(baseline · e^(−λ · category_density), min_score, baseline)
```

Decay starts from the **baseline**, not 100 — findings can only pull a
category *below* its inherent-risk baseline; a clean category (zero findings ⇒
`category_density = 0` ⇒ `e^0 = 1`) sits exactly at baseline.

Global score:

```
global = weighted_mean(score over ASSESSED categories only)
         × (assessed_count / total_categories)
```

The `(assessed_count / total_categories)` factor is the coverage penalty: a
contract-only audit with 2 of 6 dimensions assessed is structurally capped at
≈⅓, making missing documents the dominant signal.

### 5. API / response changes

- `category_breakdown[].score`: `float | null`
- New `category_breakdown[].state`: `"unassessed" | "assessed_clean" | "assessed_findings"`
- New `category_breakdown[].baseline_estimated`: `bool`
- `score_missing_dimensions`: populated from the coverage map (all 6
  categories eligible), not just doc-type schedule/budget
- New top-level `audit_coverage`: `{assessed: int, total: int, pct: float}`

## Scope

**In scope:** `rules_engine/base.py`, `rules_engine/deterministic.py`
(applicability overrides only — no finding-logic edits),
`rules_engine/llm_evaluator.py`, `scoring.py`, the deterministic + LLM nodes
and `_build_category_breakdown`/`_missing_dimensions` in `graph/nodes.py`,
coherence response models, unit + regression tests, backlog entry
TASK-BCK-060.

**Out of scope:** changing any `evaluate_v3()` finding logic; RAG retrieval;
the extraction layer; flipping the `low_budget_mode` default (separate,
already-deferred decision); training an actual regression baseline model.

## Risk & Testing

- Applicability defaults are conservative — unknown ⇒ `SKIPPED_MISSING_INPUTS`,
  never a false "assessed".
- `low_budget_mode` default stays `True`; LLM-only categories will correctly
  report `SKIPPED_DISABLED` ⇒ UNASSESSED, which honestly surfaces that the
  semantic layer is off instead of hiding it behind a 100.

Regression tests must assert:
1. Contract-only project ⇒ TIME and BUDGET are UNASSESSED with `score: null`
   and appear in `score_missing_dimensions`.
2. An assessed-clean category produces a score within the 80–90 band and
   `baseline_estimated: true`.
3. Global score reflects the coverage penalty (≈⅓ when 2/6 assessed).
4. The existing 61 coherence unit tests remain green.
5. A category with findings scores strictly below its baseline.

## Validation Procedure

After implementation: rebuild/restart the `c2pro-api` Docker container
(uvicorn runs without `--reload`; bind-mounted source requires a restart to
load), then call `POST /api/v1/coherence/evaluate/diagnostics` for project
`25916ab2-03a3-4df5-bf5f-1f8dde07fb8c` and confirm the three states behave per
the regression assertions above.
