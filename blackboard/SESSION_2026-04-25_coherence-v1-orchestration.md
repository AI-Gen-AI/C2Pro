# SESSION 2026-04-25 — Coherence Score v1 Orchestration

**PRD**: `.claude/PRPs/prds/coherence-score-v1-consolidation.prd.md`
**Epic**: `EPIC-COH-V1-CONSOLIDATION` (added to `C2PRO_MASTER_BACKLOG.md` Tier 2)
**Orchestrator**: Claude Opus 4.7 (this session)
**Worker agents**: Codex, Gemini 3 Pro, OpenCode (Sonnet 4.6)
**Integration branch**: `coh-v1/consolidation` (created after Phase 1 lands; agent branches merge into it; final squash-merge into `main`)

---

## 0. Standard Rules — Every Agent Must Obey

These apply to all 9 phases. Do not repeat in individual briefs.

1. **Read CLAUDE.md and `.claude/rules/` before starting.** Project rules override defaults.
2. **No new task-specific markdown files** (`DOCUMENTATION_STRUCTURE.md`). Inline notes go in your phase report only.
3. **Backlog update**: when your phase is complete, flip the row in `C2PRO_MASTER_BACKLOG.md` from `[ ]` to `[x]` and append a Change Log entry dated `2026-04-25` (or the actual completion date) with verification details (`CRITICAL_BACKLOG_REQUIREMENT.md`).
4. **No commit attribution** (no `Co-Authored-By` trailers — disabled globally).
5. **No `--no-verify`** on commits. If a hook fails, fix the root cause.
6. **No push to `main`.** Push to your phase branch (`coh-v1/phase-N-<agent>`). The orchestrator merges into `coh-v1/consolidation`.
7. **PII before Claude**: any new code path that calls Claude must run through the existing `PIIAnonymizerNode` (N2) or `AnthropicWrapper` (which already anonymizes). Never bypass.
8. **Tenant isolation**: any new repository method must accept `tenant_id` and join through the tenant boundary. Reference: `apps/api/src/core/tenants/types.py`.
9. **Hexagonal purity**: domain layer (`*/domain/`) must not import from `core/ai/`, `core/database`, or any infrastructure module. Use Protocols and inject at composition root.
10. **Tests first** for any new evaluator or behavior change. Coverage gate: 80% on touched modules.
11. **Run before reporting**:
    - `cd apps/api && ruff check src/ tests/`
    - `cd apps/api && mypy src/`
    - `cd apps/api && pytest -xvs <touched-test-paths>`
    - `cd apps/web && pnpm tsc --noEmit` (only if frontend touched)
12. **Report file**: write to the exact path in your brief. The orchestrator reads it as your handoff.

### Report Format (every phase)

```markdown
# PHASE N — <title> — REPORT

**Agent**: <name>
**Branch**: coh-v1/phase-N-<agent>
**Status**: complete | blocked | needs-review
**Date**: YYYY-MM-DD

## Summary
<2–3 lines: what shipped>

## Files changed
- path/to/file.py (+X / -Y) — <one-line reason>

## Diff stat
<paste of `git diff --stat coh-v1/consolidation..HEAD`>

## Test output
<paste of pytest, ruff, mypy summary lines — full output if anything red>

## Acceptance criteria
- [x] criterion 1 — verified by <command>
- [x] criterion 2 — verified by <command>

## Decisions made
- <any non-trivial choice and why>

## Open issues / followups
- <anything the orchestrator or next phase needs to know>

## Handoff to next phase
- <what downstream phases must know about this output: API shapes, file locations, schema changes>
```

---

## 1. Wave Plan

```
Wave A:  [1] Codex                                              ← solo, blocks all
Wave B:  [2] Gemini  ║  [3] Gemini  ║  [4] Codex                ← parallel after 1
Wave C:  [5] OpenCode                                           ← solo, after 3
Wave D:  [6] OpenCode  ║  [7] Codex  ║  [8] Gemini              ← parallel after 5 + deps
Wave E:  [9] OpenCode                                           ← closing gate
```

**Current status (2026-04-26)**:

| Phase | Task | Status | Report |
| ----- | ---- | ------ | ------ |
| 9 | `TASK-COH-V1-09` | needs-review | `blackboard/coh-v1/PHASE-9-opencode-REPORT.md` |

After Phase 1 lands and is reviewed, the orchestrator creates `coh-v1/consolidation` from `main` and all subsequent phase branches merge into it via PR. Final squash-merge of `coh-v1/consolidation` into `main` happens after Phase 9 + corpus-CI green.

---

## 2. Brief — TASK-COH-V1-01 — Dead-code deletion + ADR

- **Agent**: Codex
- **Branch**: `coh-v1/phase-1-codex` (from `main`)
- **Depends on**: —
- **Wave**: A
- **Report**: `blackboard/coh-v1/PHASE-1-codex-REPORT.md`

### Goal
Delete four unimported, dead coherence files and document the reasoning in one short ADR. Clears ground for Phase 2 consolidation.

### Read first
- PRD §Phase 1, §Decisions Log row "Dead-code timing", §Research Summary "Dead code present".
- `apps/api/src/coherence/engine_v2.py`
- `apps/api/src/coherence/rules.py`
- `apps/api/src/coherence/service.py`
- `apps/api/src/coherence/services/scoring/calculator.py`

### In scope
1. Delete the four files above.
2. Run `grep -rn "from coherence.engine_v2\|from coherence.rules\|from coherence.service\b\|from coherence.services.scoring.calculator" apps/ tests/` and remove any orphan imports (there should be none).
3. Create `docs/architecture/adr/ADR-001-coherence-deadcode-deletion.md` explaining:
   - What each deleted file was.
   - Why it is dead (no production import path).
   - Where the canonical equivalent lives (`coherence/scoring.py::ScoringService`, `coherence/graph/graph.py` 7-node subgraph, `coherence/rules_engine/registry.py`).
   - Forward-pointer to PRD `coherence-score-v1-consolidation`.

### Out of scope
- Do NOT touch `coherence/scoring.py`, `coherence/graph/`, `coherence/rules_engine/`, `coherence/llm_integration.py`, `coherence/domain/`. Those are Phase 2/3/5 territory.
- Do NOT modify `services/alerts/generator.py` or `alert_generator.py` — Phase 6.

### Acceptance
- [ ] `git ls-files apps/api/src/coherence/engine_v2.py apps/api/src/coherence/rules.py apps/api/src/coherence/service.py apps/api/src/coherence/services/scoring/calculator.py` returns empty.
- [ ] `grep -rn "engine_v2\|coherence\.rules\b\|coherence\.service\b\|services\.scoring\.calculator" apps/ tests/` returns zero hits in import statements.
- [ ] `cd apps/api && pytest -x` exits green.
- [ ] `docs/architecture/adr/ADR-001-coherence-deadcode-deletion.md` exists and is referenced in PR description.

### Deliverables
- 4 files deleted, ADR added, branch pushed.
- Report at `blackboard/coh-v1/PHASE-1-codex-REPORT.md`.
- PR title: `chore(coherence): delete v0 dead-code (engine_v2, rules, service, scoring/calculator)`.

---

## 3. Brief — TASK-COH-V1-02 — Pipeline consolidation + InsufficientEvidence

- **Agent**: Gemini 3 Pro
- **Branch**: `coh-v1/phase-2-gemini` (from `coh-v1/consolidation`)
- **Depends on**: Phase 1
- **Wave**: B (parallel with 3, 4)
- **Report**: `blackboard/coh-v1/PHASE-2-gemini-REPORT.md`

### Goal
Make the canonical `/coherence/evaluate` 7-node subgraph the single scoring path. Replace every default-to-100 with `InsufficientEvidence` semantics: `score=null` + `reason` + `missing_dimensions`.

### Read first
- PRD §Problem Statement, §Evidence (lines 22–28), §Phase 2, §Technical Approach "Canonical pipeline" + "InsufficientEvidence semantics".
- `apps/api/src/coherence/scoring.py` (focus line 144 `calculate_from_signals`).
- `apps/api/src/coherence/llm_integration.py` (focus lines 409–414 hardcoded 100; lines 32–39 import boundary — note for Phase 3, do not fix here).
- `apps/api/src/analysis/domain/coherence_derivation.py` (focus lines 112–123 flag defaults).
- `apps/api/src/coherence/graph/graph.py` (the 7-node subgraph — `prepare_context` → `deterministic_evaluate` → `llm_semantic_evaluate` → `rag_similarity_check` → `cross_clause_eval` → `scoring_arbiter` → `format_output`).
- `apps/api/src/analysis/adapters/graph/` — find the N8 `coherence_scorer` node and trace what it currently calls.
- `apps/api/src/coherence/application/use_cases/score_from_extraction.py` (deprecation candidate).

### In scope
1. **Rewire N8** (`coherence_scorer` node) to invoke the `/coherence/evaluate` 7-node subgraph internally instead of the flag-based path. Keep the node name/signature stable for graph compatibility.
2. **Modify `ScoringService.calculate_from_signals`** to return:
   ```python
   ScoringResult(score=None, reason="insufficient_evidence", missing_dimensions=[...])
   ```
   when `signals` is empty OR `poor_extraction_quality` flag is set. Define `ScoringResult` if it does not already carry these fields (extend dataclass; do not break existing consumers — `score` becomes `Optional[float]`).
3. **Modify `coherence_derivation.py:112-123`** flag defaults: instead of `not has_high_risk_in_categories(...)` defaulting to `True`, default to `None` when no extractions exist for that dimension; only set `True`/`False` when there is positive evidence. Adjust downstream consumers.
4. **Modify `llm_integration.py:409-414`**: when `len(clauses) < 2`, return `score=None` + `reason="insufficient_clauses"` instead of hardcoded `100`.
5. **Mark deprecated**: add `warnings.warn(DeprecationWarning, ...)` on import of `ScoreFromExtractionUseCase`, `CoherenceCalculationService`, and the flag-based `CoherenceRulesEngine`. Removal scheduled next sprint — do not delete in this PR.
6. **Tests**: 4 unit tests for insufficient-evidence cases:
   - empty signals
   - `poor_extraction_quality=True`
   - single-clause LLM analysis
   - contract-only upload (integration test against full N1–N17)

### Out of scope
- Phase 3 work: `LLMRulePort` definition, moving `AnthropicWrapper` imports. Leave `llm_integration.py:32-39` alone.
- Phase 4 work: `score_version` column. Use whatever column shape exists; Phase 4 adds the new fields.
- Phase 5 work: new evaluators. Use the current 3 deterministic evaluators only.
- Phase 6 work: alert generation wiring.

### Acceptance
- [ ] Manual test: upload a single-contract PDF via `/api/v1/analysis/analyze` returns `coherence_score: null` + `reason: "insufficient_evidence"` + `missing_dimensions: ["schedule", "budget"]`. Use `C2PRO_AI_MOCK=1`.
- [ ] `cd apps/api && pytest tests/unit/coherence/ tests/integration/coherence/ tests/integration/analysis/ -xvs` green.
- [ ] `grep -n "score=100\|coherence_score = 100\|return 100" apps/api/src/coherence/ apps/api/src/analysis/domain/coherence_derivation.py` returns zero matches in non-test code paths (test fixtures with hardcoded 100 are fine).
- [ ] `cd apps/api && mypy src/coherence src/analysis` green.
- [ ] No new infrastructure imports in `coherence/domain/`.

### Deliverables
- Code changes on branch.
- Report with full pytest summary + manual upload result + `git diff --stat`.
- PR title: `feat(coherence): consolidate to 7-node subgraph + InsufficientEvidence semantics`.

---

## 4. Brief — TASK-COH-V1-03 — Domain boundary fix (LLMRulePort)

- **Agent**: Gemini 3 Pro
- **Branch**: `coh-v1/phase-3-gemini` (from `coh-v1/consolidation`)
- **Depends on**: Phase 1
- **Wave**: B (parallel with 2, 4)
- **Report**: `blackboard/coh-v1/PHASE-3-gemini-REPORT.md`

### Goal
Eliminate the hexagonal-purity violation: `coherence/rules_engine/llm_evaluator.py` and `coherence/llm_integration.py` import `AnthropicWrapper` directly from infrastructure. Define `LLMRulePort` Protocol in domain, move concrete implementations to `coherence/adapters/ai/`, inject at composition root.

### Read first
- PRD §Phase 3, §Technical Approach "Domain port", §Decisions Log "Domain boundary".
- `apps/api/src/coherence/rules_engine/llm_evaluator.py` (focus lines 41–43, infra import).
- `apps/api/src/coherence/llm_integration.py` (focus lines 32–39, infra import).
- `apps/api/src/coherence/domain/` — current shape of the domain layer.
- `apps/api/src/coherence/rules_engine/registry.py` — composition site.
- `apps/api/src/core/ai/llm_client.py` and `apps/api/src/core/ai/service.py` — `AnthropicWrapper` definition.

### In scope
1. **Define port**: `apps/api/src/coherence/domain/ports/llm_rule_port.py`
   ```python
   from typing import Protocol
   class LLMRulePort(Protocol):
       async def evaluate(self, *, rule_id: str, prompt: str, context: dict) -> LLMRuleResult: ...
   ```
   Define `LLMRuleResult` (frozen dataclass) in the same domain module.
2. **Adapter**: `apps/api/src/coherence/adapters/ai/llm_rule_evaluator.py` — concrete implementation that wraps `AnthropicWrapper` and satisfies `LLMRulePort`.
3. **Refactor**: `coherence/rules_engine/llm_evaluator.py` constructor takes `LLMRulePort` (not `AnthropicWrapper`). Remove infra imports from this file.
4. **Refactor**: `coherence/llm_integration.py` either becomes a thin facade over `LLMRulePort` OR moves wholesale into `coherence/adapters/ai/`. Pick whichever is cleaner — document the choice in your report.
5. **Composition root**: `coherence/rules_engine/registry.py` (or wherever the registry is built) injects the concrete adapter. Do this at the FastAPI app startup, not at import time.
6. **Snapshot tests** (must run before refactor and pass after):
   - Choose 5 representative rule outputs from current `qualitative_rules.yaml` runs.
   - Capture output JSON to `apps/api/tests/snapshots/llm_rule_evaluator/`.
   - Re-run after refactor; outputs must match.

### Out of scope
- Phase 5: building new evaluators against the port. Just make the existing 3 deterministic + current LLM path work through the port.
- Phase 2: scoring contract.
- Renaming or restructuring `core/ai/` itself.

### Acceptance
- [ ] `grep -rn "from core\.ai\|from src\.core\.ai\|import core\.ai" apps/api/src/coherence/domain apps/api/src/coherence/rules_engine` returns zero hits.
- [ ] `grep -rn "AnthropicWrapper" apps/api/src/coherence/domain apps/api/src/coherence/rules_engine` returns zero hits.
- [ ] Snapshot tests green: outputs match pre-refactor baseline.
- [ ] `cd apps/api && pytest tests/unit/coherence/ -xvs` green.
- [ ] `cd apps/api && mypy src/coherence` green.
- [ ] `cd apps/api && pytest tests/integration/coherence/ -xvs` green (real injection path works).

### Deliverables
- New port + adapter, refactored callers, snapshot tests committed.
- Report with snapshot diff (must be empty), import-violation grep output (zero), composition-root wiring snippet.
- PR title: `refactor(coherence): introduce LLMRulePort + restore domain purity`.

---

## 5. Brief — TASK-COH-V1-04 — `score_version` migration + ADR

- **Agent**: Codex
- **Branch**: `coh-v1/phase-4-codex` (from `coh-v1/consolidation`)
- **Depends on**: Phase 1
- **Wave**: B (parallel with 2, 3)
- **Report**: `blackboard/coh-v1/PHASE-4-codex-REPORT.md`

### Goal
Add audit-trail fields to `coherence_results` and persist them via the repository. No historical recomputation. Hard cut-off documented in ADR.

### Read first
- PRD §Phase 4, §Technical Approach "Persistence", §Decisions Log "Backfill strategy".
- `apps/api/src/coherence/adapters/db/sqlalchemy_repository.py` (or whichever file holds `SqlAlchemyCoherenceRepository`).
- `apps/api/alembic/versions/` — observe naming convention of recent migrations.
- `apps/api/src/coherence/domain/` — find the `CoherenceResult` / `ScoringResult` domain object.

### In scope
1. **Alembic migration** `apps/api/alembic/versions/20260425_xxxx_coherence_score_versioning.py`:
   - Add `score_version: ENUM('v0_flag_based', 'v1_exponential_decay')` NOT NULL DEFAULT `'v0_flag_based'` to `coherence_results`.
   - Add `score_reason: TEXT NULL` to `coherence_results`.
   - Add `score_missing_dimensions: JSONB NULL` to `coherence_results`.
   - Forward + reverse migration both clean.
   - Update RLS policies if any reference these columns (likely no change needed; verify).
2. **Domain model**: extend `CoherenceResult` (or equivalent) with the three new fields. Keep `score: Optional[float]` (Phase 2 may have already done this — confirm).
3. **Repository**: `SqlAlchemyCoherenceRepository.save()` writes the new fields. Reads return them.
4. **Cut-off constant**: `apps/api/src/coherence/config.py` (create if absent):
   ```python
   SCORE_VERSION_V1_CUTOFF = datetime(2026, 5, 1, tzinfo=timezone.utc)  # placeholder; orchestrator confirms
   ```
   Mark as TBD-final-date; the live cut-off is set in Phase 9.
5. **UI badge stub**: a placeholder React component `apps/web/src/components/coherence/ScoreVersionBadge.tsx` that renders `(v0)` or `(v1)` based on the API field. Real styling/tooltip lands in Phase 9.
6. **ADR**: `docs/architecture/adr/ADR-002-coherence-score-versioning.md` — explains immutability of pre-cut-off rows, why no recomputation, how customer comms will land in Phase 9.

### Out of scope
- Setting the live cut-off date — Phase 9.
- Tooltip copy + final dashboard styling — Phase 9.
- Backfilling old rows with `v1` — explicitly forbidden.

### Acceptance
- [ ] `cd apps/api && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` succeeds without errors.
- [ ] `cd apps/api && pytest tests/integration/coherence/test_repository.py -xvs` green (write + read round-trip preserves the three fields).
- [ ] `cd apps/web && pnpm tsc --noEmit` green.
- [ ] `cd apps/web && pnpm vitest run src/components/coherence/ScoreVersionBadge.test.tsx` green (write a smoke test).
- [ ] ADR-002 exists with cut-off rationale.

### Deliverables
- Migration + repo + domain extension + UI stub + ADR.
- Report with `alembic upgrade --sql` output (the SQL the migration would emit) and roundtrip-test result.
- PR title: `feat(coherence): score_version migration + ADR-002`.

---

## 6. Brief — TASK-COH-V1-05 — Evaluator registry expansion to 18

- **Agent**: OpenCode (Sonnet 4.6)
- **Branch**: `coh-v1/phase-5-opencode` (from `coh-v1/consolidation` after Phases 2+3+4 are merged in)
- **Depends on**: Phase 3 (LLMRulePort), Phase 2 (scoring contract), Phase 4 (score_version)
- **Wave**: C
- **Report**: `blackboard/coh-v1/PHASE-5-opencode-REPORT.md`

### Goal
Build out the evaluator registry to v1 target: 12 deterministic + 6 LLM-backed evaluators, distributed 3 deterministic + 1 LLM across each of the 6 C2Pro categories. Wire all 18 into `scoring_arbiter`.

### Read first
- PRD §Phase 5, §Technical Approach "Evaluator registry", §Decisions Log "Evaluator count v1".
- `apps/api/src/coherence/rules_engine/registry.py` (current 3 entries — line 32–36).
- `apps/api/src/coherence/rules_engine/qualitative_rules.yaml` (15–20 LLM rule definitions, currently unwired).
- `apps/api/src/coherence/domain/categories.py` (or equivalent — the 6 categories enum).
- `apps/api/src/coherence/alert_generator.py` (lines 14–55) — `RULE_TITLES`, `RULE_SEVERITIES`, `TEMPLATES` keys. **Every new evaluator's `rule_id` must already have an entry in these dicts, OR you must add the entry in this PR.** Build-time check rejects orphan `rule_id`s — add this check.

### In scope
1. Identify the 6 categories. For each:
   - Implement 3 deterministic evaluators against the existing `RuleEvaluator` ABC (or its successor — confirm with Phase 2's output).
   - Wrap 1 YAML rule from `qualitative_rules.yaml` as a typed `LLMRuleEvaluator` instance using the `LLMRulePort` from Phase 3.
2. Each evaluator declares `rule_id`. Add a startup-time check: every `rule_id` must exist in `RULE_TITLES`, `RULE_SEVERITIES`, and `TEMPLATES`. Fail fast at app init.
3. Wire all 18 into `coherence/rules_engine/registry.py`.
4. `scoring_arbiter` consumes their `FindingSignal` outputs (no change needed if Phase 2 left this stable — confirm).
5. Unit tests: 1 per evaluator (18 tests minimum). Each test feeds a known input and asserts the `FindingSignal` shape + severity + `rule_id`.
6. **Per-category coverage table** in your report — categories × {deterministic count, LLM count, FP rate on golden corpus, FN rate on golden corpus}. FP/FN values may be `TBD` if Phase 7 corpus extension hasn't landed; mark explicitly.

### Out of scope
- Phase 6 alert wiring — you only ensure `rule_id` keys exist in template tables; do not modify `format_output` node.
- Phase 7 golden corpus extension.
- Adding more than 18 evaluators ("scaling post-validation" — out of v1 scope).

### Acceptance
- [ ] `len(registry.list_evaluators()) == 18` (assert in a unit test).
- [ ] App startup succeeds; orphan-rule_id check passes.
- [ ] `cd apps/api && pytest tests/unit/coherence/rules_engine/ -xvs` — all 18 evaluator tests green.
- [ ] `cd apps/api && pytest tests/integration/coherence/ -xvs` green (full subgraph runs with 18 evaluators).
- [ ] `cd apps/api && mypy src/coherence` green.
- [ ] No `from core.ai` imports in `coherence/rules_engine/`.

### Deliverables
- 18-entry registry + per-evaluator tests + per-category coverage table + orphan-rule_id startup check.
- Report with the coverage table + sample `FindingSignal` for each category.
- PR title: `feat(coherence): expand evaluator registry to 18 (12 det + 6 LLM)`.

---

## 7. Brief — TASK-COH-V1-06 — Alert generation wiring + `meta_alert`

- **Agent**: OpenCode (Sonnet 4.6)
- **Branch**: `coh-v1/phase-6-opencode` (from `coh-v1/consolidation` after Phase 5)
- **Depends on**: Phase 2 (scoring contract), Phase 5 (rule_ids)
- **Wave**: D (parallel with 7, 8)
- **Report**: `blackboard/coh-v1/PHASE-6-opencode-REPORT.md`

### Goal
Wire the existing `AlertGeneratorService` into the canonical `format_output` node. Every finding becomes a persisted, fingerprint-deduplicated, auto-resolving alert. Insufficient evidence emits a `meta_alert` of type `AUDIT_INCOMPLETE` through the same service.

### Read first
- PRD §Phase 6, §Technical Approach "Alert generation wiring", §User Flow steps 4–5.
- `apps/api/src/coherence/alert_generator.py` (`AlertGenerator` class, `TEMPLATES`/`RULE_TITLES`/`RULE_SEVERITIES`).
- `apps/api/src/coherence/services/alerts/generator.py` (`AlertGeneratorService.process_violations`, fingerprint dedup, auto-resolve).
- `apps/api/src/coherence/graph/graph.py` (`format_output` node — current shape).
- `apps/api/src/alerts/` — `Alert` ORM, `AlertType` enum, `AlertCreate` schema.

### In scope
1. **`format_output` node**: after scoring, build `AlertCreate` list for each finding via the existing template machinery and call `AlertGeneratorService.process_violations(project_id, alerts, tenant_id)`.
2. **`AlertType.AUDIT_INCOMPLETE`**: add to the enum. Add template:
   - Title: `"Audit incomplete — full triplet not provided"`
   - Body: `"Coherence Score withheld: missing dimensions {missing_dimensions}. Supply schedule and/or budget to obtain a defensible score."`
   - Severity: `MEDIUM`
3. **Meta-alert path**: when scoring returns `score=None + reason="insufficient_evidence"`, emit ONE `AUDIT_INCOMPLETE` alert per `(project_id, missing_dimensions)` tuple. Fingerprint must include `missing_dimensions` so changing the missing set creates a new alert.
4. **Auto-resolve**: when subsequent re-analysis returns a non-null score, the prior `AUDIT_INCOMPLETE` alert auto-resolves via the existing service.
5. **Bilingualization** (Should-have, not Must): add `template_locale: Literal["es", "en"]` to template lookups; default to `"es"` for backward compat. English templates: skeleton entries marked `# TBD-EN`. Full bilingualization can land in a follow-up — do not block on translations.
6. **ADR-003**: `docs/architecture/adr/ADR-003-coherence-alert-ledger-v0-v1.md` — document the v0→v1 alert-ledger transition (recommend: cut-off resets ledger; old alerts archived but immutable).
7. **Tests**:
   - Re-running same audit twice → zero new alerts (fingerprint dedup).
   - Re-running after vendor revision (finding gone) → prior alert auto-resolves.
   - Contract-only upload → exactly 1 `AUDIT_INCOMPLETE` alert.
   - Supplying schedule + budget after `AUDIT_INCOMPLETE` → that alert auto-resolves.

### Out of scope
- Phase 9 alert UX (severity sort, copy-to-clipboard, in-app banner).
- Translating Spanish templates to English content (skeletons only).
- New alert types beyond `AUDIT_INCOMPLETE`.

### Acceptance
- [ ] `cd apps/api && pytest tests/integration/coherence/test_alert_wiring.py -xvs` green (4 scenarios above).
- [ ] `grep -n "AUDIT_INCOMPLETE" apps/api/src/alerts/` returns enum + template entries.
- [ ] Manual: contract-only upload via `/api/v1/analysis/analyze` produces exactly 1 alert in DB with `type='AUDIT_INCOMPLETE'`.
- [ ] Manual: re-uploading same contract produces 0 new alerts.
- [ ] ADR-003 exists.

### Deliverables
- Wired `format_output`, new alert type + templates, ADR-003, integration tests.
- Report with the 4 test scenarios' pytest output + manual upload alert-table dump.
- PR title: `feat(coherence): wire AlertGeneratorService + AUDIT_INCOMPLETE meta_alert`.

---

## 8. Brief — TASK-COH-V1-07 — Golden corpus extension

- **Agent**: Codex
- **Branch**: `coh-v1/phase-7-codex` (from `coh-v1/consolidation` after Phase 5)
- **Depends on**: Phase 2 (scoring contract), Phase 4 (score_version), Phase 5 (rule_ids stabilized)
- **Wave**: D (parallel with 6, 8)
- **Report**: `blackboard/coh-v1/PHASE-7-codex-REPORT.md`

### Goal
Extend the golden-corpus bundle schema to assert `expected_score_range` and `expected_alerts`. Author expectations for the 15 existing bundles. Wire CI assertions.

### Read first
- PRD §Phase 7, §Success Metrics rows on score=100 + recall + alert fingerprint.
- `evals/` directory — find `run_evals.py`, the bundle schema, and the existing 15 bundles.
- `.github/workflows/` — find the CI workflow that runs the corpus.

### In scope
1. **Schema extension** (existing bundle JSON/YAML schema):
   ```yaml
   expected_score_range:
     min: float | null  # null means "score must be null"
     max: float | null  # null means "score must be null"
     reasoning: string  # human comment
   expected_alerts:
     - rule_id: string
       min_count: int
       severity: low | medium | high | critical
   score_check: required | skip  # skip allowed only with reasoning
   ```
2. **Annotate 15 bundles**: open each existing bundle, infer realistic ranges from the bundle's content, add `expected_score_range` + `expected_alerts`. For contract-only bundles, both `min` and `max` must be `null` and `expected_alerts` must include `{rule_id: "AUDIT_INCOMPLETE", min_count: 1, severity: "medium"}`.
3. **`evals/run_evals.py`**: extend assertions:
   - For each bundle, compute score, compare against range.
   - For each bundle, fetch generated alerts (via the same `AlertGeneratorService` path), compare counts/severities against `expected_alerts`.
   - Report per-bundle pass/fail + aggregate recall metric.
4. **CI**: existing workflow runs `run_evals.py`; ensure it fails the build on any bundle deviation.
5. **Docs**: short note in `evals/README.md` on how to author expectations for new bundles.

### Out of scope
- Adding new bundles (use the existing 15).
- Tuning evaluator thresholds to make the corpus pass — report failures, do not "fix" via threshold drift.

### Acceptance
- [ ] All 15 bundles have `expected_score_range` and `expected_alerts` populated, OR `score_check: skip` with a reason.
- [ ] `cd apps/api && python -m evals.run_evals` exits 0 (or reports legitimate failures the orchestrator triages).
- [ ] CI workflow fails when a bundle's score is outside its range (verify by intentionally setting an impossible range in a scratch branch).
- [ ] `evals/README.md` updated with authoring instructions.

### Deliverables
- Schema + 15 annotated bundles + evals runner + CI assert + README note.
- Report with the per-bundle pass/fail table + aggregate recall %.
- PR title: `test(coherence): golden-corpus expected_score_range + expected_alerts`.

---

## 9. Brief — TASK-COH-V1-08 — Telemetry on deterministic nodes

- **Agent**: Gemini 3 Pro
- **Branch**: `coh-v1/phase-8-gemini` (from `coh-v1/consolidation` after Phase 5)
- **Depends on**: Phase 2 (consolidated nodes)
- **Wave**: D (parallel with 6, 7)
- **Report**: `blackboard/coh-v1/PHASE-8-gemini-REPORT.md`

### Goal
Structured LangSmith spans on 6 of the 7 subgraph nodes (skip `llm_semantic_evaluate` until canary rollout = 100%). Allowlist of span attributes audited for EU residency. `score_version` tag on every span.

### Read first
- PRD §Phase 8, §Technical Approach "Telemetry", §Technical Risks row "LangSmith span attributes leak contract content".
- `apps/api/src/core/observability/` — current LangSmith integration, `@traced_llm_call` decorator, span helpers.
- `apps/api/src/core/ai/rollout_router.py` — canary cohort logic.
- `apps/api/src/coherence/graph/graph.py` — 7 nodes.

### In scope
1. **Span instrumentation** on these 6 nodes: `prepare_context`, `deterministic_evaluate`, `rag_similarity_check`, `cross_clause_eval`, `scoring_arbiter`, `format_output`. Skip `llm_semantic_evaluate`.
2. **Span attributes** (allowlist — define schema in `apps/api/src/core/observability/coherence_span_schema.py`):
   - `coherence.node_name: str`
   - `coherence.score_version: 'v0' | 'v1'`
   - `coherence.findings_count: int`
   - `coherence.rule_ids: list[str]` (IDs only, no content)
   - `coherence.tenant_id: str`
   - `coherence.project_id: str`
   - **NO** clause text, document content, or PII fields.
3. **CI gate**: `apps/api/tests/contract/test_coherence_span_schema.py` rejects PRs that add attribute keys outside the allowlist.
4. **Alert-creation events**: when an alert is created in `format_output`, emit a span tagged with `rule_id` + `severity` (no body text).
5. **Runbook**: `docs/runbooks/COHERENCE_TELEMETRY.md` — how to read the spans, what alerts they should drive.

### Out of scope
- Spans on `llm_semantic_evaluate` (defer to post-rollout).
- Dashboard wiring in LangSmith UI (operational, not code).
- Replacing the existing `@traced_llm_call` decorator.

### Acceptance
- [ ] Run a staged audit; LangSmith UI shows spans for the 6 nodes with the allowlisted attributes only.
- [ ] `cd apps/api && pytest tests/contract/test_coherence_span_schema.py -xvs` green.
- [ ] Adding a new attribute outside the allowlist fails the contract test (verify in a scratch commit and revert).
- [ ] Runbook exists and is referenced from PR description.

### Deliverables
- Span instrumentation + schema + contract test + runbook.
- Report with screenshot or text-export of the span tree from a staged audit + the allowlist.
- PR title: `feat(observability): coherence span instrumentation + EU-residency allowlist`.

---

## 10. Brief — TASK-COH-V1-09 — UX + customer comms for `score_version` and alerts

- **Agent**: OpenCode (Sonnet 4.6)
- **Branch**: `coh-v1/phase-9-opencode` (from `coh-v1/consolidation` after Phases 4, 6, 7)
- **Depends on**: Phase 4 (migration + badge stub), Phase 6 (alerts wired), Phase 7 (corpus green)
- **Wave**: E (closing gate)
- **Report**: `blackboard/coh-v1/PHASE-9-opencode-REPORT.md`

### Goal
Customer-facing dashboard + alert surface + comms ready to flip the cut-off date.

### Read first
- PRD §Phase 9.
- `apps/web/src/app/(app)/projects/[projectId]/coherence/` (or wherever the score view lives).
- `apps/web/src/components/coherence/ScoreVersionBadge.tsx` (Phase 4 stub).
- `apps/web/src/components/alerts/` — existing alert list components.
- `apps/api/src/coherence/config.py::SCORE_VERSION_V1_CUTOFF` (from Phase 4).

### In scope
1. **Score badge**: complete the `ScoreVersionBadge` component — pill + tooltip explaining `v0` vs `v1`, link to ADR-002 in customer-friendly language.
2. **Alert list view**: severity sort, status filter, copy-to-clipboard for templated message (so the procurement director can paste into a vendor email).
3. **AUDIT_INCOMPLETE banner**: when `score=null` is rendered, show a prominent "Supply missing dimensions to unlock full Coherence Score" CTA tied to the `meta_alert`.
4. **Customer comms**:
   - In-app banner template (announcing v1 score availability + what changes).
   - Email template under `apps/api/src/notifications/templates/coherence_v1_announcement.{html,txt}`.
   - One-page customer FAQ at `docs/customer/COHERENCE_V1_FAQ.md` (this IS allowed — it's customer-facing, not task-specific).
5. **Cut-off activation**: confirm the live date with orchestrator; commit the final value to `SCORE_VERSION_V1_CUTOFF`.
6. **Internal QA checklist**: in your report, list 5 manual scenarios you walked through with screenshots.

### Out of scope
- Production rollout coordination (orchestrator's job).
- A/B testing the dashboard layout — single design in this PR.
- Bilingualizing the comms beyond what Phase 6 produced (Spanish primary, English skeletons).

### Acceptance
- [ ] `cd apps/web && pnpm tsc --noEmit && pnpm vitest run` green.
- [ ] `cd apps/web && pnpm playwright test e2e/coherence-v1.spec.ts` green (write 1 E2E covering: contract-only upload → AUDIT_INCOMPLETE banner visible → supply schedule+budget → banner gone, score visible, badge = v1).
- [ ] Manual QA screenshots in report for 5 scenarios: (1) v0 historical row, (2) v1 fresh row, (3) AUDIT_INCOMPLETE state, (4) alert with copy-to-clipboard, (5) email template render.
- [ ] FAQ + email template + in-app banner committed.

### Deliverables
- Dashboard polish + alert UX + comms artifacts + activated cut-off.
- Report with screenshots, E2E pytest output, and the activated cut-off value.
- PR title: `feat(coherence): v1 dashboard, alert UX, customer comms`.

---

## 11. Orchestrator Review Gates

For every returned report, the orchestrator (this Claude Opus 4.7 session) runs:

1. **Read**: `blackboard/coh-v1/PHASE-N-<agent>-REPORT.md`.
2. **Diff scope check**: `git diff --stat coh-v1/consolidation..coh-v1/phase-N-<agent>` — only files in SCOPE touched.
3. **Re-run acceptance commands** locally — every `[x]` must be reproducible.
4. **Cross-phase consistency**:
   - Phase 5 `rule_id`s = Phase 6 template keys = Phase 7 `expected_alerts.rule_id`s.
   - Phase 2 `ScoringResult` shape = Phase 4 column types = Phase 9 frontend types.
   - Phase 3 `LLMRulePort` signature = Phase 5 evaluator constructor.
5. **Project-rule compliance**: backlog row flipped, Change Log updated, no new TASK_*.md files, no Co-Authored-By trailers.
6. **`code-reviewer` agent**: invoked on each PR for CRITICAL/HIGH gate.
7. **Merge** into `coh-v1/consolidation` via squash. Final consolidation merges into `main` after Phase 9 + corpus-CI green.

Block conditions (orchestrator does not merge):
- Any acceptance command red.
- Diff includes files outside SCOPE without explicit `Decisions made` justification.
- Cross-phase contract drift (e.g., Phase 5 added `rule_id` not in Phase 6 templates).

---

## 12. Status Tracker (orchestrator updates as phases land)

| # | Phase | Agent | Branch | Status | PR | Report |
|---|-------|-------|--------|--------|-----|--------|
| 1 | Dead-code deletion | Codex | `coh-v1/phase-1-codex` | ✅ merged into `coh-v1/consolidation` @ `ce28d54b` (2026-04-25) | local | `blackboard/coh-v1/PHASE-1-codex-REPORT.md` |
| 2 | Pipeline consolidation | Gemini | `coh-v1/phase-2-gemini` | needs-review (implemented locally by Codex @ 2026-04-25; tests partly blocked by local Postgres/mypy debt) | local | `blackboard/coh-v1/PHASE-2-gemini-REPORT.md` |
| 3 | LLMRulePort | Gemini | `coh-v1/phase-3-gemini` | ✅ merged into `coh-v1/consolidation` (2026-04-26) | local | `blackboard/coh-v1/PHASE-3-opencode-REPORT.md` |
| 4 | score_version migration | Codex | `coh-v1/phase-4-codex` | ✅ implemented locally (2026-04-25; DB verification blocked by local Postgres) | local | `blackboard/coh-v1/PHASE-4-codex-REPORT.md` |
| 5 | Registry → 18 | OpenCode | `coh-v1/phase-5-opencode` | needs-review (implemented locally by Codex @ 2026-04-26; integration blocked by local Postgres/mypy debt) | local | `blackboard/coh-v1/PHASE-5-opencode-REPORT.md` |
| 6 | Alert wiring + meta_alert | OpenCode | `coh-v1/phase-6-opencode` | blocked on 2,5 | — | — |
| 7 | Golden corpus | Codex | `coh-v1/phase-7-codex` | needs-review (implemented locally @ 2026-04-26; 15/15 corpus bundles green, 100% alert recall) | local | `blackboard/coh-v1/PHASE-7-codex-REPORT.md` |
| 8 | Telemetry | Gemini | `coh-v1/phase-8-gemini` | blocked on 2 | — | — |
| 9 | UX + comms | OpenCode | `coh-v1/phase-9-opencode` | blocked on 4,6,7 | — | — |
