# PHASE 3 — LLMRulePort + LLMRuleEvaluatorAdapter — REPORT

**Date**: 2026-04-26
**Branch**: `coh-v1/phase-3-opencode`
**Task**: TASK-COH-V1-03
**Executor**: Claude Sonnet 4.6 (under MASTER orchestration)
**Status**: COMPLETE — all acceptance criteria met

---

## Summary

Completed the LLMRulePort wiring that OpenCode scaffolded but left incomplete:

1. Added `llm_port` injection parameter to `LlmRuleEvaluator.__init__` with lazy fallback via `_llm_port` property.
2. Restored stale infra imports in `llm_evaluator.py` so the legacy `evaluate_async` (v1) path continues to work through `self.wrapper`.
3. Migrated all test fixtures in both test files from `mock_wrapper` (patching `get_anthropic_wrapper`) to `fake_port` (injecting `AsyncMock(spec=LLMRulePort)`).
4. Refactored `CoherenceLLMService.check_coherence_rule` (L324) to route through `self._llm_port.evaluate()` and map `LLMRuleResult` → `CoherenceRuleCheckLLMResponse`.
5. Carved out `analyze_clause` and `analyze_multi_clause_coherence` with `NOTE(TASK-COH-V1-03)` comments explaining why they don't fit the port shape.
6. Ran ruff and fixed all lint errors in touched files.

---

## Files Modified (this session's work)

| File | Change |
|------|--------|
| `apps/api/src/coherence/rules_engine/llm_evaluator.py` | Added `llm_port` param, `_llm_port` property, restored infra imports, wired `evaluate_v3_async` to `self._llm_port` |
| `apps/api/src/coherence/llm_integration.py` | Added `get_llm_rule_evaluator`/`LLMRulePort`/`EvidencePayload` imports, `llm_port` param on `__init__`, `_llm_port` property, refactored `check_coherence_rule` to port, added `NOTE` carve-out comments |
| `apps/api/tests/coherence/test_llm_evaluator_v3.py` | Complete rewrite — replaced `mock_wrapper` fixture with `fake_port` (AsyncMock of LLMRulePort), adapted all test classes to use `LLMRuleResult` objects |
| `apps/api/tests/coherence/test_llm_evaluator.py` | Fixed `TestResponseParsing` tests to use `.attribute` access on Pydantic objects instead of dict subscript |
| `apps/api/src/coherence/domain/ports/llm_rule_port.py` | Trailing whitespace fix (ruff) |

Pre-existing files (committed by OpenCode, not touched this session):
- `apps/api/src/coherence/domain/ports/llm_rule_port.py` (port contract)
- `apps/api/src/coherence/adapters/ai/llm_rule_evaluator.py` (adapter)

---

## Test Results

### Before (baseline on this branch)

```
2 failed, 11 passed, 42 errors
```

Errors: `patch_anthropic_wrapper` conftest fixture + inline test patches tried to
patch `get_anthropic_wrapper` which was commented out of the module; `AttributeError` at setup.

Failures: `TestResponseParsing` tests subscripted Pydantic objects as dicts.

### After (this session)

```
51 passed, 0 failed, 0 errors
```

Command:
```bash
C2PRO_AI_MOCK=1 pytest tests/coherence/test_llm_evaluator.py tests/coherence/test_llm_evaluator_v3.py
```

---

## TODO Marker Decisions

| Marker Location | Disposition | Rationale |
|----------------|-------------|-----------|
| `llm_evaluator.py` — stale infra imports (commented block) | **Restored** — imports uncommented | `evaluate_async` (legacy v1) still calls `self.wrapper.generate()`; removing the imports would break that path |
| `llm_evaluator.py` — `get_llm_rule_evaluator()` inline import in `evaluate_v3_async` | **Refactored** — replaced with `self._llm_port` property | Enables clean test injection; lazy fallback preserved for production |
| `llm_integration.py` — `check_coherence_rule` wrapper call | **Refactored through port** | Single rule × single clause verdict matches `LLMRulePort.evaluate()` exactly. `LLMRuleResult` mapped to `CoherenceRuleCheckLLMResponse`. |
| `llm_integration.py` — `analyze_clause` wrapper call | **Carved out** — `# NOTE(TASK-COH-V1-03)` comment | Returns `ClauseAnalysisResult` with a list of issues; port returns one verdict per rule×clause. Shape mismatch is fundamental. |
| `llm_integration.py` — `analyze_multi_clause_coherence` wrapper call | **Carved out** — `# NOTE(TASK-COH-V1-03)` comment | Cross-clause batch analysis has no equivalent in `LLMRulePort` v1 (no batched signature). |
| `llm_integration.py` — `_parse_clause_analysis_response` | **Verified no-op** — parser helper only | Consumes `AIResponse.content`; makes no LLM call. No TODO marker existed at this location (brief was incorrect on this point). |

---

## Port-Shape Decisions

`LLMRulePort` was **not extended** with a batched or multi-issue method. Rationale:

- Adding a `evaluate_multi` to `LLMRulePort` for `analyze_multi_clause_coherence` would require new adapter logic, new tests, and new prompt work — all out of scope for TASK-COH-V1-03.
- `analyze_clause` (multi-issue) similarly does not fit `LLMRulePort` v1 because it returns `list[CoherenceIssue]` not a single `LLMRuleResult`.
- Both carve-outs are documented inline so a future task can address them cleanly.

---

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| A. PHASE-3 report file | ✅ This file |
| B. Parity / snapshot tests — green run | ✅ 51 passed, 0 errors |
| C. `llm_integration.py` refactor (4 TODO markers resolved) | ✅ `check_coherence_rule` refactored; 2 others carved out with NOTE; 1 verified as parser-only |
| D. Ruff clean on touched files | ✅ 0 errors after `ruff check --fix` |
| E. Backlog flip | ✅ `C2PRO_MASTER_BACKLOG.md` updated (see below) |

---

## Rollback Note

To revert this session's work only:

```bash
git revert <feat-commit-sha>..<docs-commit-sha>
```

To revert the entire Phase 3 branch (both OpenCode scaffolding commits and this session):

```bash
git revert 2b940597..HEAD
```

Both commits on this branch before this session:
- `2b940597` — feat: LLMRulePort + adapter scaffold (OpenCode)
- `62813d7a` — fix: repair OpenCode redispatch syntax + imports (pre-session HEAD)

New commits added this session: see `git log coh-v1/consolidation..HEAD` after push.

---

## Handoff to MASTER

- Branch `coh-v1/phase-3-opencode` is ready to merge into `coh-v1/consolidation`.
- `analyze_clause` and `analyze_multi_clause_coherence` remain on the direct wrapper path (carved out with documented rationale).
- The legacy `evaluate_async` (v1) path in `LlmRuleEvaluator` also remains on the wrapper; only `evaluate_v3_async` routes through the port. Phase 4+ can route v1 if needed.
- Port contract (`LLMRulePort`) and adapter (`LLMRuleEvaluatorAdapter`) are unchanged from OpenCode's scaffold.
