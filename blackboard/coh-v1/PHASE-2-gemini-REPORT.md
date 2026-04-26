# PHASE 2 — Pipeline Consolidation + InsufficientEvidence — REPORT

**Agent**: Codex (executing Gemini 3 Pro brief)
**Branch**: coh-v1/phase-2-gemini target; current workspace branch was `coh-v1/phase-4-codex`
**Status**: needs-review
**Date**: 2026-04-25

## Summary
N8 `coherence_scorer` now delegates to the canonical 7-node coherence subgraph through `evaluate_coherence_async`. Empty signals, poor extraction quality, and single-clause LLM analysis now withhold scores with explicit reasons and missing dimensions instead of defaulting to 100.

The workspace already contained uncommitted Phase 3-style LLM port edits before this task; I preserved them and fixed syntax/test-fixture issues needed for Phase 2 verification.

## Files changed
- `apps/api/src/coherence/scoring.py` — added `ScoringResult(score: float | None, reason, missing_dimensions)` and insufficient-evidence handling.
- `apps/api/src/coherence/graph/state.py` — added quality/missing-dimension config and nullable graph score.
- `apps/api/src/coherence/graph/nodes.py` — propagated scoring reason/missing dimensions into `EnrichedCoherenceResult`.
- `apps/api/src/coherence/graph/graph.py` — removed fallback score=100 in result construction.
- `apps/api/src/coherence/llm_schemas.py` — made multi-clause score nullable and added `reason`.
- `apps/api/src/coherence/llm_integration.py` — single-clause analysis returns `score=None`, `reason="insufficient_clauses"`; repaired malformed f-strings from in-progress edits.
- `apps/api/src/analysis/adapters/graph/nodes_extended.py` — rewired N8 to canonical subgraph while keeping node name/signature stable.
- `apps/api/src/analysis/domain/coherence_derivation.py` — dimension flags now default to `None` when no extraction evidence exists.
- `apps/api/src/coherence/application/use_cases/score_from_extraction.py`, `apps/api/src/coherence/application/services/coherence_calculation_service.py`, `apps/api/src/coherence/domain/rules_engine.py` — added import-time deprecation warnings.
- `apps/api/src/core/observability/monitoring.py` — fixed TASK-BCK-050 duplicate HITL metric definitions blocking imports.
- `apps/api/tests/unit/coherence/test_insufficient_evidence_semantics.py` — RED/GREEN coverage for empty signals, poor quality, and single-clause LLM.
- `apps/api/tests/unit/analysis/domain/test_coherence_derivation_insufficient_evidence.py` — RED/GREEN coverage for unknown dimension defaults.
- `apps/api/tests/unit/analysis/test_coherence_scorer_node_canonical_subgraph.py` — RED/GREEN coverage for N8 canonical delegation contract.
- `apps/api/tests/unit/core/observability/test_monitoring_metric_registration.py` — regression coverage for duplicate metric import.
- `C2PRO_MASTER_BACKLOG.md`, `blackboard.json` — task tracking updates.

## Diff stat
```text
C2PRO_MASTER_BACKLOG.md                            |   7 +-
apps/api/src/analysis/adapters/graph/nodes_extended.py  |  96 +++++--
apps/api/src/analysis/adapters/graph/schema.py     |   4 +-
apps/api/src/analysis/application/persist_analysis_use_case.py | 2 +-
apps/api/src/analysis/domain/coherence_derivation.py | 31 ++-
apps/api/src/analysis/domain/report_assembly.py    |   4 +-
apps/api/src/coherence/application/dtos/coherence_dtos.py | 16 +-
apps/api/src/coherence/application/services/coherence_calculation_service.py | 24 +-
apps/api/src/coherence/application/use_cases/score_from_extraction.py | 10 +-
apps/api/src/coherence/domain/global_score_calculator.py | 8 +-
apps/api/src/coherence/domain/rules_engine.py      |  17 +-
apps/api/src/coherence/graph/graph.py              |  10 +-
apps/api/src/coherence/graph/nodes.py              |  23 +-
apps/api/src/coherence/graph/state.py              |   6 +-
apps/api/src/coherence/llm_integration.py          |  76 +++---
apps/api/src/coherence/llm_schemas.py              |   3 +-
apps/api/src/coherence/scoring.py                  |  85 +++++-
apps/api/src/core/observability/monitoring.py      |  18 --
apps/api/tests/conftest.py                         |  36 ++-
apps/api/tests/unit/coherence/test_llm_schemas.py  |   3 +-
blackboard.json                                    |  78 +++++-
23 files changed, 473 insertions(+), 376 deletions(-)
```

## Test output
```text
$ pytest apps/api/tests/unit/coherence/test_insufficient_evidence_semantics.py apps/api/tests/unit/analysis/domain/test_coherence_derivation_insufficient_evidence.py apps/api/tests/unit/analysis/test_coherence_scorer_node_canonical_subgraph.py apps/api/tests/unit/core/observability/test_monitoring_metric_registration.py -q
...... [100%]

$ python -m compileall -q apps/api/src/coherence apps/api/src/analysis/domain/coherence_derivation.py apps/api/src/analysis/adapters/graph/nodes_extended.py
PASS

$ pytest apps/api/tests/unit/coherence apps/api/tests/integration/coherence apps/api/tests/integration/analysis -xvs
39 passed, then blocked at apps/api/tests/integration/coherence/test_repository.py setup:
PostgreSQL test database unavailable at postgresql://postgres:postgres@postgres-test:5432/c2pro_test

$ rg -n "score=100|coherence_score = 100|return 100" apps/api/src/coherence apps/api/src/analysis/domain/coherence_derivation.py
zero matches

$ mypy src/coherence src/analysis
FAILED: 554 existing/broad type errors remain across src/coherence, src/analysis, and imported core modules; Phase 2-specific syntax/import collection is clean.
```

## Acceptance criteria
- [x] N8 calls canonical 7-node subgraph — verified by `test_coherence_scorer_node_canonical_subgraph.py`.
- [x] Empty signals return `score=None`, `reason="insufficient_evidence"` — verified by `test_insufficient_evidence_semantics.py`.
- [x] `poor_extraction_quality=True` returns insufficient evidence — verified by `test_insufficient_evidence_semantics.py`.
- [x] Single-clause LLM analysis returns `score=None`, `reason="insufficient_clauses"` — verified by `test_insufficient_evidence_semantics.py`.
- [x] `coherence_derivation.py` no-evidence dimension flags default to `None` — verified by `test_coherence_derivation_insufficient_evidence.py`.
- [x] Default-100 grep gate — zero matches in requested source paths.
- [ ] Full requested pytest command — blocked by unavailable local Postgres host `postgres-test`.
- [ ] Manual `/api/v1/analysis/analyze` upload — not run; local API/test DB stack unavailable in this shell.
- [ ] `mypy src/coherence src/analysis` — blocked by existing broad type debt.

## Decisions made
- Kept `ScoringResult` numeric-comparable for compatibility with old score consumers while exposing the new canonical `.score/.reason/.missing_dimensions` contract.
- N8 builds one canonical `Clause` from the analysis graph state and passes extracted data through `Clause.data`; Phase 5 can expand evaluator use of structured extraction data.
- Fixed TASK-BCK-050 in this changeset because it blocked Phase 2 imports and test collection.

## Open issues / followups
- Current workspace branch is not the requested phase branch and includes pre-existing uncommitted Phase 3 files (`coherence/adapters/ai`, `coherence/domain/ports`, `rules_engine/llm_evaluator.py` changes). Orchestrator should separate/merge carefully.
- Local Postgres test service is not reachable as `postgres-test`; integration repository tests cannot run here.
- `mypy src/coherence src/analysis` is not an actionable Phase 2 gate yet; it reports hundreds of existing strictness/type errors outside this phase.

## Handoff to next phase
- Canonical score result fields are `overall_score`, `score_reason`, and `score_missing_dimensions` on `EnrichedCoherenceResult`.
- N8 state now also carries `coherence_reason` and `coherence_missing_dimensions`.
- Deprecated paths remain present and emit `DeprecationWarning`: `ScoreFromExtractionUseCase`, `CoherenceCalculationService`, and `CoherenceRulesEngine`.
