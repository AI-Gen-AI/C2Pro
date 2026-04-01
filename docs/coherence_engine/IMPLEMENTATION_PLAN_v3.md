# Coherence Engine v0.3 — Implementation Plan

## Overview

**Goal**: Replace the binary 0/100 scoring system with a production-grade multi-agent coherence engine using continuous scoring, tridimensional auditing, and LangGraph orchestration.

**Estimated Scope**: ~3,200 lines of new/modified code across 30+ files

**Design Documents**:
- `coherence_langgraph_subgraph_v3.md` — LangGraph architecture
- `deterministic_rules_v3_final.md` — Deterministic evaluators (27 rules, 6 categories)
- `coherence_score_restructuring_v3.md` — Scoring algorithm

---

## The 6 Categories + Cross-Dimensional Coverage

| Category | ID Prefix | Evaluators | What They Catch |
|----------|-----------|-----------|-----------------|
| **BUDGET** | `DET-BUD-` | 6 | Overrun, contingency, line items, retention, advance, sum mismatch |
| **TIME** | `DET-TIM-` | 5 | Status, overdue, milestone gaps, duration, predecessor overlap |
| **LEGAL** | `DET-LEG-` | 6 | Review overdue, penalties, notice, warranty, payment terms, insurance |
| **SCOPE** | `DET-SCP-` | 2 | Missing fields, deliverable completeness |
| **TECHNICAL** | `DET-TEC-` | 3 | BOM lead time, spec reference, material-budget linkage |
| **QUALITY** | `DET-QUA-` | 2 | Standard references, inspection frequency |
| **CROSS** | `DET-CRS-` | 3 | Budget vs contract total, schedule vs BOM delivery, scope vs budget coverage |
| | | **27 total** | |

---

## Current vs Proposed Architecture

```
CURRENT (v0.2)                      PROPOSED (v0.3)
────────────────                    ────────────────
3 binary rules (4 categories)   →   27 continuous-scored rules (6 categories + CROSS)
Linear deduction (0/100)        →   Exponential decay (5-97 range)
Single LLM call per clause×rule →   Batch mode + RAG pre-filter
No cross-document analysis      →   Tridimensional auditing (contract×budget×schedule)
No scope normalization          →   Scope-aware penalty density
Generic clause structure        →   calibration_dataset aligned (contract, budget_items, schedule_items, bom_items)
```

---

## Phase 1: Foundation Layer
**Deliverable**: Base models, config, and backward-compatible interfaces

| # | Task | File(s) | Dependencies |
|---|------|---------|--------------|
| 1.1 | Create `FindingSignal` dataclass with continuous scoring | `coherence/models.py` | None |
| 1.2 | Create `EvaluatorConfig` with all thresholds | `coherence/rules_engine/config.py` | None |
| 1.3 | Update `RuleEvaluator` base class with `evaluate_v3()` | `coherence/rules_engine/base.py` | 1.1 |
| 1.4 | Create `ScoringConfig` dataclass | `coherence/scoring.py` | None |
| 1.5 | Write unit tests for models and config | `tests/coherence/test_models_v3.py` | 1.1-1.4 |

**Checklist**:

- [x] `FindingSignal` has `impact_score: float [0.0-1.0]`, `confidence: float`, `severity: enum`, `category: str`
- [x] `EvaluatorConfig` covers all 6 categories: BUDGET, TIME, LEGAL, SCOPE, TECHNICAL, QUALITY thresholds
- [x] `RuleEvaluator.evaluate_v3()` returns `FindingSignal | None`
- [x] `impact_to_severity()` helper function implemented
- [x] Unit tests written in `tests/coherence/test_v3_models.py`

**Status: ✅ COMPLETE** (2026-03-28)

---

## Phase 2: Deterministic Rules Engine (Agent A)
**Deliverable**: 27 evaluators across 6 categories + CROSS, replacing the current 3

| # | Task | File(s) | Dependencies |
|---|------|---------|--------------|
| 2.1 | ✅ Implement BUDGET evaluators (6) | `coherence/rules_engine/deterministic.py` | Phase 1 |
| | - `BudgetOverrunEvaluator` (logarithmic curve) | | |
| | - `BudgetContingencyEvaluator` | | |
| | - `BudgetLineItemEvaluator` (unit×qty check) | | |
| | - `BudgetSumMismatchEvaluator` (items vs contract total) | | |
| | - `RetentionRateEvaluator` | | |
| | - `AdvancePaymentEvaluator` | | |
| 2.2 | ✅ Implement TIME evaluators (5) | `coherence/rules_engine/deterministic.py` | Phase 1 |
| | - `ScheduleStatusEvaluator` (multi-status impact map) | | |
| | - `DeadlineOverdueEvaluator` (progressive curve) | | |
| | - `MilestoneGapEvaluator` | | |
| | - `PredecessorOverlapEvaluator` (schedule_items predecessor check) | | |
| | - `ScheduleDurationEvaluator` | | |
| 2.3 | ✅ Implement LEGAL evaluators (6) | `coherence/rules_engine/deterministic.py` | Phase 1 |
| | - `ContractReviewOverdueEvaluator` | | |
| | - `PenaltyCapEvaluator` | | |
| | - `NoticePeriodEvaluator` | | |
| | - `WarrantyPeriodEvaluator` | | |
| | - `PaymentTermEvaluator` | | |
| | - `InsuranceExpiryEvaluator` | | |
| 2.4 | ✅ Implement TECHNICAL evaluators (3) | `coherence/rules_engine/deterministic.py` | Phase 1 |
| | - `BomLeadTimeEvaluator` (bom_items lead time feasibility) | | |
| | - `SpecReferenceEvaluator` (missing ISO/ASTM/EN references) | | |
| | - `BomBudgetLinkEvaluator` (bom_items without budget_item_id) | | |
| 2.5 | ✅ Implement QUALITY evaluators (2) | `coherence/rules_engine/deterministic.py` | Phase 1 |
| | - `QualityStandardEvaluator` (vague vs specific standards) | | |
| | - `InspectionFrequencyEvaluator` | | |
| 2.6 | ✅ Implement SCOPE evaluators (2) | `coherence/rules_engine/deterministic.py` | Phase 1 |
| | - `MissingRequiredFieldsEvaluator` | | |
| | - `ScopeDeliverablesEvaluator` | | |
| 2.7 | ✅ Implement CROSS-DIMENSIONAL evaluators (3) | `coherence/rules_engine/deterministic.py` | Phase 1 |
| | - `BudgetVsContractTotalEvaluator` (DET-CRS-BUDCON) | | |
| | - `ScheduleVsBomDeliveryEvaluator` (DET-CRS-SCHBOM) | | |
| | - `ScopeVsBudgetCoverageEvaluator` (DET-CRS-SCPBUD) | | |
| 2.8 | ✅ Create `get_all_deterministic_evaluators()` registry | `coherence/rules_engine/deterministic.py` | 2.1-2.7 |
| 2.9 | ✅ Write comprehensive test suite | `tests/coherence/test_deterministic_evaluators.py` | 2.1-2.8 |
| 2.10 | ✅ Add golden calibration test cases | `apps/api/tests/coherence/golden_deterministic.py`, `apps/api/tests/coherence/test_golden_deterministic.py` | 2.1-2.9 |

**Checklist**:

- [x] All 27 evaluators produce `FindingSignal` with continuous `impact_score`
- [x] Impact curves are logarithmic (diminishing returns)
- [x] Config thresholds are respected via `EvaluatorConfig`
- [x] Date parsing handles ISO, US, EU formats
- [x] Legacy `evaluate()` method still works (backward compat)
- [x] CROSS evaluators catch tridimensional mismatches (contract×budget×schedule)
- [x] Aligned with `calibration_dataset` structure (budget_items, schedule_items, bom_items)
- [x] Golden cases GOLD-DET-001 through GOLD-DET-004 pass
- [x] Test coverage ≥80% for evaluators (105/105 tests passing)

**Status: ✅ COMPLETE** (2026-03-28)

See `docs/coherence_engine/PHASE_2_VERIFICATION.md` for detailed verification report.

---

## Phase 3: Scoring Engine (Agent C)
**Deliverable**: Exponential decay scoring with scope normalization

| # | Task | File(s) | Dependencies |
|---|------|---------|--------------|
| 3.1 | ✅ Implement `ScoringService.calculate_from_signals()` | `coherence/scoring.py` | Phase 1 |
| 3.2 | ✅ Implement exponential decay formula | `coherence/scoring.py` | 3.1 |
| 3.3 | ✅ Add scope normalization logic | `coherence/scoring.py` | 3.2 |
| 3.4 | ✅ Add floor/ceiling bounds (5.0 / 97.0) | `coherence/scoring.py` | 3.3 |
| 3.5 | ✅ Implement `calculate_detailed()` with diagnostics | `coherence/scoring.py` | 3.1-3.4 |
| 3.6 | ✅ Update `calculate()` for backward compat with alerts | `coherence/scoring.py` | 3.1-3.5 |
| 3.7 | ✅ Write scoring curve validation tests | `tests/coherence/test_scoring_v3.py` | 3.1-3.6 |

**Checklist**:
- [x] Formula: `score = 100 × e^(-λ × penalty_density)`
- [x] Score never reaches 0 (floor = 5.0)
- [x] Score with findings never reaches 100 (ceiling = 97.0)
- [x] Larger scope (more clauses) absorbs findings better
- [x] Low confidence findings have reduced impact
- [x] Deterministic signals weighted higher than LLM
- [x] Diagnostic output includes: penalty density, scope factor, severity distribution

**Status: ✅ COMPLETE** (2026-04-01)

See `apps/api/tests/coherence/test_scoring_v3.py` for 39 scoring curve validation tests.

---

## Phase 4: LLM Evaluator Updates (Agent B)
**Deliverable**: Continuous-scored LLM evaluation with batch mode

| # | Task | File(s) | Dependencies |
|---|------|---------|--------------|
| 4.1 | ✅ Update `LlmRuleEvaluator` for continuous scoring | `coherence/rules_engine/llm_evaluator.py` | Phase 1 |
| 4.2 | ✅ Create optimized prompt templates | `coherence/graph/prompts.py` | None |
| | - `COHERENCE_SYSTEM_PROMPT` | | |
| | - `RULE_EVALUATION_PROMPT` | | |
| | - `BATCH_EVALUATION_PROMPT` | | |
| | - `CROSS_CLAUSE_PROMPT` | | |
| 4.3 | ✅ Add few-shot examples for calibration | `coherence/graph/prompts.py` | 4.2 |
| 4.4 | ✅ Implement JSON parsing with error handling | `coherence/rules_engine/llm_evaluator.py` | 4.1 |
| 4.5 | ✅ Add cost tracking (`total_cost_usd`, `llm_calls_count`) | `coherence/rules_engine/llm_evaluator.py` | 4.1 |
| 4.6 | ✅ Write tests for LLM response parsing | `tests/coherence/test_llm_evaluator_v3.py` | 4.1-4.5 |

**Checklist**:
- [x] LLM returns `impact_score` and `confidence` floats
- [x] Responses are validated and clamped to [0.0, 1.0]
- [x] Batch prompt reduces token usage
- [x] Cost tracking per evaluation
- [x] Graceful fallback on parse errors

**Status: ✅ COMPLETE** (2026-04-01)

See `apps/api/tests/coherence/test_llm_evaluator_v3.py` for 36 LLM evaluator tests.

---

## Phase 5: LangGraph Subgraph
**Deliverable**: Composable subgraph with parallel evaluation nodes

| # | Task | File(s) | Dependencies |
|---|------|---------|--------------|
| 5.1 | ✅ Create `CoherenceGraphState` dataclass | `coherence/graph/state.py` | Phase 1 |
| 5.2 | ✅ Create `ClauseWithEmbedding` dataclass | `coherence/graph/state.py` | 5.1 |
| 5.3 | ✅ Implement `prepare_context` node | `coherence/graph/nodes.py` | 5.1-5.2 |
| 5.4 | ✅ Implement `deterministic_evaluate` node | `coherence/graph/nodes.py` | Phase 2 |
| 5.5 | ✅ Implement `llm_semantic_evaluate` node | `coherence/graph/nodes.py` | Phase 4 |
| 5.6 | ✅ Implement `cross_clause_eval` node | `coherence/graph/nodes.py` | 5.5 |
| 5.7 | ✅ Implement `scoring_arbiter` node | `coherence/graph/nodes.py` | Phase 3 |
| 5.8 | ✅ Implement `format_output` node | `coherence/graph/nodes.py` | 5.7 |
| 5.9 | ✅ Build graph with `build_coherence_subgraph()` | `coherence/graph/graph.py` | 5.3-5.8 |
| 5.10 | ✅ Compile subgraph as `coherence_subgraph` | `coherence/graph/graph.py` | 5.9 |
| 5.11 | ✅ Write integration tests for subgraph | `tests/coherence/test_langgraph_v3.py` | 5.1-5.10 |

**Checklist**:
- [x] Graph topology: `prepare_context → [det, llm] → cross_clause → scoring → format`
- [x] Sequential flow in v0.3 (parallel evaluation planned for v0.4)
- [x] Signals accumulated via LangGraph reducers (`operator.add`)
- [x] Subgraph compiles without errors
- [x] Can be invoked standalone via `evaluate_coherence()`
- [x] Low budget mode skips LLM evaluation

**Status: ✅ COMPLETE** (2026-04-01)

See `apps/api/tests/coherence/test_langgraph_v3.py` for 30 LangGraph integration tests.

---

## Phase 6: RAG Integration (Agent A+)
**Deliverable**: Embedding similarity detection for cross-document analysis

| # | Task | File(s) | Dependencies |
|---|------|---------|--------------|
| 6.1 | ✅ Create `EmbeddingRepositoryPort` interface | `coherence/ports/embedding_repository.py` | None |
| 6.2 | ✅ Create `EmbeddingMatch` and `EmbeddingRecord` DTOs | `coherence/ports/embedding_repository.py` | 6.1 |
| 6.3 | ✅ Implement `PgvectorEmbeddingRepository` adapter | `coherence/adapters/persistence/pgvector_embedding_repository.py` | 6.1-6.2 |
| 6.4 | ✅ Implement `rag_similarity_check` node | `coherence/graph/nodes.py` | 6.1-6.3, Phase 5 |
| 6.5 | ✅ Add embedding enrichment to `prepare_context` | `coherence/graph/nodes.py` | 6.3 |
| 6.6 | ✅ Write tests for similarity detection | `tests/coherence/test_rag_similarity.py` | 6.1-6.5 |
| 6.7 | ✅ Create migration for `clause_embeddings` table | `alembic/versions/20260401_0001_add_clause_embeddings.py` | 6.3 |
| 6.8 | ✅ Update graph topology to include RAG node | `coherence/graph/graph.py` | 6.4 |

**Checklist**:
- [x] Port follows hexagonal architecture (interface, not implementation)
- [x] pgvector cosine similarity query: `1 - (embedding <=> target)`
- [x] Threshold configurable (default: 0.85)
- [x] Zero LLM cost (pure SQL)
- [x] Cross-document pairs detected and fed to cross_clause_eval
- [x] Migration creates HNSW index for fast similarity search
- [x] Test coverage ≥80% (21 tests covering all components)

**Status: ✅ COMPLETE** (2026-04-01)

See `docs/coherence_engine/PHASE_6_VERIFICATION.md` for detailed verification report.

---

## Phase 7: API Integration
**Deliverable**: Updated router with backward-compatible public API

| # | Task | File(s) | Dependencies |
|---|------|---------|--------------|
| 7.1 | Update router to use subgraph | `coherence/router.py` | Phase 5 |
| 7.2 | Add category inference helper | `coherence/router.py` | 7.1 |
| 7.3 | Ensure backward compat for `POST /v0/coherence/evaluate` | `coherence/router.py` | 7.1-7.2 |
| 7.4 | Add optional diagnostics endpoint | `coherence/router.py` | 7.1-7.3 |
| 7.5 | Write E2E API tests | `tests/coherence/test_api_v3.py` | 7.1-7.4 |

**Checklist**:
- [ ] `POST /v0/coherence/evaluate` returns `{"alerts": [...], "score": float}` (unchanged)
- [ ] Score is now a granular float (not 0/100)
- [ ] low_budget_mode defaults to True
- [ ] Diagnostics available via query param or separate endpoint

---

## Phase 8: Testing & Validation
**Deliverable**: Full test coverage and golden test validation

| # | Task | File(s) | Dependencies |
|---|------|---------|--------------|
| 8.1 | Create golden test cases for score curve | `tests/coherence/golden/` | All phases |
| 8.2 | Add parametrized tests for edge cases | `tests/coherence/` | All phases |
| 8.3 | Add cost tracking assertions | `tests/coherence/` | Phase 4 |
| 8.4 | Verify no regressions in existing API | `tests/coherence/` | Phase 7 |
| 8.5 | Run full test suite and verify ≥80% coverage | CI | 8.1-8.4 |

**Checklist**:
- [ ] Golden tests: 0 findings → 100, moderate → 50-80, severe → 10-30
- [ ] Edge cases: empty clauses, missing data, malformed dates
- [ ] Cost stays under $0.01/project in low_budget_mode
- [ ] All existing tests pass

---

## File Placement Map

```
apps/api/src/coherence/
├── __init__.py
├── models.py              # Add FindingSignal, EnrichedCoherenceResult
├── ports.py               # NEW: EmbeddingRepositoryPort
├── router.py              # UPDATED: routes through subgraph
├── scoring.py             # REPLACED: exponential decay ScoringService
├── graph/                 # NEW: LangGraph subgraph
│   ├── __init__.py
│   ├── graph.py           # build_coherence_subgraph()
│   ├── state.py           # CoherenceGraphState, ClauseWithEmbedding
│   ├── nodes.py           # All 7 node implementations
│   └── prompts.py         # Optimized LLM prompts (v2)
├── rules_engine/
│   ├── __init__.py
│   ├── base.py            # UPDATED: RuleEvaluator, Finding, FindingSignal, impact_to_severity
│   ├── config.py          # NEW: EvaluatorConfig (27 threshold params)
│   ├── deterministic.py   # REPLACED: 27 evaluators across 6 categories + CROSS
│   ├── llm_evaluator.py   # UPDATED: continuous scoring LlmRuleEvaluator
│   └── registry.py        # UPDATED: get_all_deterministic_evaluators()
├── adapters/
│   └── persistence/
│       └── pgvector_embedding_repo.py  # NEW: EmbeddingRepositoryPort implementation
└── config.py              # Add ScoringConfig

apps/api/tests/coherence/
├── test_models_v3.py           # Phase 1 tests
├── test_deterministic_v3.py    # Phase 2 tests (27 evaluators)
├── test_scoring_v3.py          # Phase 3 tests (curve validation)
├── test_llm_evaluator_v3.py    # Phase 4 tests
├── test_langgraph_v3.py        # Phase 5 tests
├── test_rag_similarity.py      # Phase 6 tests
├── test_api_v3.py              # Phase 7 tests
└── golden/
    ├── golden_deterministic.py # Golden calibration cases
    └── test_golden_deterministic.py
```

---

## Implementation Order Summary

| Week | Phase | Milestone |
|------|-------|-----------|
| 1 | Phase 1 + Phase 3 | Foundation + Scoring engine working |
| 2 | Phase 2 | All deterministic evaluators complete |
| 3 | Phase 4 + Phase 5.1-5.8 | LLM + Graph nodes ready |
| 4 | Phase 5.9-5.11 + Phase 6 | Subgraph compiles + RAG integration |
| 5 | Phase 7 + Phase 8 | API integration + Full validation |

---

## Success Criteria

1. **Score Granularity**: Scores distributed across 5-97 range (no 0/100 polarity)
2. **Deterministic Coverage**: 6 categories + CROSS with **27 evaluators**
3. **Cost Efficiency**: <$0.01/project in low_budget_mode
4. **Backward Compatibility**: Existing API contract unchanged
5. **Test Coverage**: ≥80% line coverage
6. **Performance**: <2s evaluation for typical 10-clause project
7. **Tridimensional Auditing**: CROSS evaluators catch contract×budget×schedule mismatches
8. **Golden Calibration**: All GOLD-DET-* cases score within expected human_score ±5 points

---

## Appendix A: Evaluator Reference

### BUDGET (6)

| Rule ID | Class | Detects |
|---------|-------|---------|
| DET-BUD-OVERRUN | BudgetOverrunEvaluator | current > planned (logarithmic curve) |
| DET-BUD-CONTINGENCY | BudgetContingencyEvaluator | contingency <5% or >20% |
| DET-BUD-LINEITEM | BudgetLineItemEvaluator | unit_price × qty ≠ line_total |
| DET-BUD-SUM | BudgetSumMismatchEvaluator | Σbudget_items ≠ contract_total |
| DET-BUD-RETENTION | RetentionRateEvaluator | retention outside 3-10% |
| DET-BUD-ADVANCE | AdvancePaymentEvaluator | advance >30% without guarantee |

### TIME (5)

| Rule ID | Class | Detects |
|---------|-------|---------|
| DET-TIM-STATUS | ScheduleStatusEvaluator | delayed/at_risk/critical statuses |
| DET-TIM-OVERDUE | DeadlineOverdueEvaluator | end_date in past (progressive) |
| DET-TIM-GAP | MilestoneGapEvaluator | >90 day gap between milestones |
| DET-TIM-PREDECESSOR | PredecessorOverlapEvaluator | task starts before predecessor ends |
| DET-TIM-DURATION | ScheduleDurationEvaluator | end ≤ start, buffer < min |

### LEGAL (6)

| Rule ID | Class | Detects |
|---------|-------|---------|
| DET-LEG-REVIEW | ContractReviewOverdueEvaluator | last_review_date > threshold |
| DET-LEG-PENALTY | PenaltyCapEvaluator | missing cap, excessive rate |
| DET-LEG-NOTICE | NoticePeriodEvaluator | <14d or >90d notice |
| DET-LEG-WARRANTY | WarrantyPeriodEvaluator | <6mo or >60mo warranty |
| DET-LEG-PAYMENT | PaymentTermEvaluator | payment_term_days >60 |
| DET-LEG-INSURANCE | InsuranceExpiryEvaluator | expiry before project end |

### TECHNICAL (3)

| Rule ID | Class | Detects |
|---------|-------|---------|
| DET-TEC-LEADTIME | BomLeadTimeEvaluator | BOM lead time vs required_on_site_date |
| DET-TEC-SPEC | SpecReferenceEvaluator | missing ISO/ASTM/EN references |
| DET-TEC-BOMBUDGET | BomBudgetLinkEvaluator | BOM items without budget_item_id |

### QUALITY (2)

| Rule ID | Class | Detects |
|---------|-------|---------|
| DET-QUA-STANDARD | QualityStandardEvaluator | vague "industry standards" |
| DET-QUA-INSPECT | InspectionFrequencyEvaluator | missing frequency/method |

### SCOPE (2)

| Rule ID | Class | Detects |
|---------|-------|---------|
| DET-SCP-MISSING | MissingRequiredFieldsEvaluator | category-specific required fields |
| DET-SCP-DELIVERABLES | ScopeDeliverablesEvaluator | text mentions deliverables without structure |

### CROSS-DIMENSIONAL (3)

| Rule ID | Class | Detects |
|---------|-------|---------|
| DET-CRS-BUDCON | BudgetVsContractTotalEvaluator | budget_items sum ≠ contract total |
| DET-CRS-SCHBOM | ScheduleVsBomDeliveryEvaluator | BOM required_on_site outside schedule window |
| DET-CRS-SCPBUD | ScopeVsBudgetCoverageEvaluator | deliverables without budget coverage |

---

*Document created: 2026-03-28*
*Last updated: 2026-04-01*
*Status: IN PROGRESS — Phases 1-6 complete, Phase 7 (API Integration) next*
