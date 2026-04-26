# PHASE-3 — OpenCode Redispatch Brief

**Task:** TASK-COH-V1-03 — LLMRulePort + LLMRuleEvaluatorAdapter
**Branch:** `coh-v1/phase-3-opencode` (cut from `coh-v1/consolidation`)
**Status:** WIP — scaffolding committed, refactor incomplete
**Audited by:** MASTER (Claude Opus 4.7) on 2026-04-25

---

## TL;DR

OpenCode delivered the **port + adapter scaffolding** but stopped short of:
1. Writing the PHASE-3 report file
2. Running snapshot/parity tests
3. Finishing the `CoherenceLLMService` refactor (4 stale `get_anthropic_wrapper()` calls remain)
4. Clearing the LSP errors flagged in the test suite

This branch contains the partial work plus inline `TODO(TASK-COH-V1-03 ...)` markers
calling out exactly where the refactor was abandoned. **Acceptance criteria below.**

---

## What Already Exists On This Branch

### 1. Domain port (NEW — looks correct)

`apps/api/src/coherence/domain/ports/llm_rule_port.py`
- `LLMRulePort` `@runtime_checkable` `Protocol`
- `LLMRuleResult` frozen `@dataclass`
- Async `evaluate()` signature with `rule_id`, `rule_name`, `rule_description`,
  `detection_logic`, `category`, `clause_id`, `clause_text`, `clause_data`, `tenant_id`

### 2. Concrete adapter (NEW — looks correct)

`apps/api/src/coherence/adapters/ai/llm_rule_evaluator.py`
- `LLMRuleEvaluatorAdapter` wraps `AnthropicWrapper` (lazy singleton via property)
- Implements `LLMRulePort.evaluate()`
- Maps legacy category strings to canonical `CoherenceCategory`
- Parses `LlmEvaluationV3Response` via `parse_llm_json`
- Translates impact_score → severity via `impact_to_severity`
- `get_llm_rule_evaluator()` factory at line 201

### 3. Port wiring in `LlmRuleEvaluator` (PARTIAL)

`apps/api/src/coherence/rules_engine/llm_evaluator.py`
- `__init__` accepts `llm_port: LLMRulePort | None = None`
- Lazy resolution property at lines 237-244 calling `get_llm_rule_evaluator()`
- ⚠️ **Need to verify**: do all evaluator code paths actually go through the port now,
  or are there still bypasses?

### 4. Module docstring updated in `llm_integration.py` (LIES)

The module header (lines 1-8) reads:
```
Integration layer that delegates to LLMRulePort for domain purity.
Now receives LLMRulePort via injection.
```
…but the body still imports and calls `get_anthropic_wrapper()` directly at:
- L283 — single-clause rule eval
- L362 — full coherence rule check
- L443 — multi-clause cross analysis
- L685 — `get_statistics()` reaching into wrapper internals

Each site is now flagged with a `TODO(TASK-COH-V1-03 OpenCode redispatch)` comment
explaining what the right shape should be. **Pick those up and finish the work.**

---

## What Is MISSING (Acceptance Criteria for Re-merge)

### A. PHASE-3 report file (BLOCKER)

Create `blackboard/coh-v1/PHASE-3-opencode-REPORT.md` matching the format of
`PHASE-1-codex-REPORT.md` and `PHASE-2-gemini-REPORT.md`. Must include:

- Files added / modified with line counts
- Snapshot/parity test results (counts: passed/failed/errored)
- Decisions made on the 4 TODO markers (each one: kept-as-is, refactored, or carved out)
- Any port-shape changes (e.g. did multi-clause force you to add a batched method?)
- Rollback note (revert SHA range)

### B. Snapshot / parity tests (BLOCKER)

Existing `apps/api/tests/coherence/test_llm_evaluator.py` and
`tests/coherence/test_llm_evaluator_v3.py` currently fail with
`2 failed, 11 passed, 42 errors` on this branch. Either:

1. Add a parity test proving `LlmRuleEvaluator` (port-injected) yields identical
   `LLMRuleResult` for fixed inputs vs. the pre-refactor wrapper-direct call, **or**
2. Snapshot-test the `LLMRuleEvaluatorAdapter.evaluate()` output against frozen
   `LlmEvaluationV3Response` fixtures.

Target: green test run for the coherence test directory before merge.

### C. Finish `llm_integration.py` refactor (BLOCKER)

Resolve every `TODO(TASK-COH-V1-03 ...)` marker. Three paths each:
- Route through `self._llm_port.evaluate(...)` and delete the wrapper import, OR
- Document the carve-out in PHASE-3 report with rationale (e.g. multi-clause needs
  a different port method), OR
- Extend `LLMRulePort` with a new method (and update the adapter + tests).

The fourth marker (`get_statistics`) should likely move stats accumulation onto
the port itself or be made adapter-agnostic.

### D. LSP / type-check pass (BLOCKER)

Run from `apps/api`:
```bash
pyright src/coherence/  # or mypy if configured
ruff check src/coherence/ tests/coherence/
```
Should be **clean** for files in `src/coherence/domain/ports/`,
`src/coherence/adapters/ai/`, `src/coherence/rules_engine/`,
`src/coherence/llm_integration.py`.

### E. Backlog flip (REQUIRED by `.claude/rules/CRITICAL_BACKLOG_REQUIREMENT.md`)

Update `C2PRO_MASTER_BACKLOG.md`:
- Flip TASK-COH-V1-03 from `[ ]` to `[x]` once A–D are green
- Append Change Log entry with date, branch, and commit SHA
- Note any spawned follow-up tasks

---

## Test Commands (run from `apps/api/`)

```bash
# Full coherence test set
C2PRO_AI_MOCK=1 pytest tests/coherence/ -xvs

# Just the LLM evaluator surface
C2PRO_AI_MOCK=1 pytest tests/coherence/test_llm_evaluator.py tests/coherence/test_llm_evaluator_v3.py -xvs

# Quick smoke that imports compile
python -c "from src.coherence.llm_integration import CoherenceLLMService; from src.coherence.rules_engine.llm_evaluator import LlmRuleEvaluator; from src.coherence.adapters.ai.llm_rule_evaluator import LLMRuleEvaluatorAdapter; print('IMPORTS OK')"
```

---

## Don'ts (Project Rules)

- ❌ **No `--no-verify`** on commits — the `block-no-verify@1.1.2` hook will reject it.
- ❌ **No `Co-Authored-By:` trailers** — globally disabled.
- ❌ **No new task-specific markdown files** outside `backlogs/` or `blackboard/`
  (per `.claude/rules/DOCUMENTATION_STRUCTURE.md`).
- ❌ **Do not push to `main`** — this branch merges into `coh-v1/consolidation`, not main.
- ❌ **Do not bypass `LLMRulePort`** for new code paths in `coherence/`. The whole
  point of TASK-COH-V1-03 is to make the port the *only* seam.

## Do's

- ✅ Cite test SHAs and file:line in PHASE-3 report
- ✅ If you change `LLMRulePort` shape, also update `LLMRuleEvaluatorAdapter`
- ✅ Use `C2PRO_AI_MOCK=1` for tests so we don't burn ANTHROPIC_API_KEY budget
- ✅ Keep diffs surgical — no drive-by refactors of unrelated coherence code

---

## Why This Branch Was Cut

MASTER staged Phase 2 (`InsufficientEvidence` semantics) into `coh-v1/consolidation`
cleanly, but Phase 3 work was tangled with stale wrapper calls and an incomplete
refactor. Cutting `coh-v1/phase-3-opencode` from consolidation isolates the WIP so
OpenCode can finish without polluting the integration branch.

When A–E are green, merge `coh-v1/phase-3-opencode` → `coh-v1/consolidation` (no FF,
preserve the redispatch history).

---

*Generated by MASTER (Claude Opus 4.7) on 2026-04-25*
*Source of truth for this redispatch — do not duplicate to other files*
