# C2PRO Master Backlog - Index & Overview

**Purpose**: High-level project index. Only **pending** work is tracked here.
**Last Updated**: 2026-04-21 (v3 — Epic-Based Restructure + slim archive split)
**Completed work**: [`backlogs/COMPLETED.md`](backlogs/COMPLETED.md)

> **Navigation**: Quick Navigation → Restructured Manifest v3 (execution order) → Pending by Category → Change Log.

---

## Quick Navigation

| Category | File | Owner | Total | Active | Completed |
| -------- | ---- | ----- | ----- | ------ | --------- |
| AI/ML Intelligence | [backlogs/AI_AI_ML_INTELLIGENCE.md](backlogs/AI_AI_ML_INTELLIGENCE.md) | ai | 78 | 46 | 32 |
| Backend | [backlogs/BCK_BACKEND.md](backlogs/BCK_BACKEND.md) | backend | 28 | 6 | 22 |
| DevOps | [backlogs/DEV_DEVOPS.md](backlogs/DEV_DEVOPS.md) | devops | 2 | 0 | 2 |
| Documentation | [backlogs/DOC_DOCUMENTATION.md](backlogs/DOC_DOCUMENTATION.md) | shared | 0 | 0 | 0 |
| Frontend | [backlogs/FRT_FRONTEND.md](backlogs/FRT_FRONTEND.md) | frontend | 163 | 26 | 137 |
| Infrastructure | [backlogs/INF_INFRASTRUCTURE.md](backlogs/INF_INFRASTRUCTURE.md) | infra | 59 | 18 | 41 |
| Planning | [backlogs/PLN_PLANNING.md](backlogs/PLN_PLANNING.md) | planner | 0 | 0 | 0 |
| Quality Assurance | [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md) | qa | 96 | 34 | 62 |
| Code Review | [backlogs/REV_CODE_REVIEW.md](backlogs/REV_CODE_REVIEW.md) | reviewer | 25 | 0 | 25 |
| Security | [backlogs/SEC_SECURITY.md](backlogs/SEC_SECURITY.md) | security | 0 | 0 | 0 |

---

## Restructured Manifest v3 (Epic-Based, 2026-04-21)

> Authoritative execution order. Sorted by **architectural dependency** first, **business value** second.
> Session record: `blackboard/SESSION_2026-04-21_backlog_audit.md`.

### Tier 0 — Foundation (blocks all downstream feature work)

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `EPIC-TENANT-RLS-HARDENING` | Multi-tenant RLS + credential hygiene | Architecture | P0 | — | Ship Alembic RLS policy on `clause_embeddings`, close SEC-009..011 gaps, and unblock `TASK-FRT-045` via approved secret channel. |
| `EPIC-CORE-DECOUPLE` ✅ | Decouple AI logic from LangGraph nodes (`TASK-IMPL-010` + 14 subtasks) | Refactor | P0 | — | Phases 1–4 completed 2026-04-21; 92% coverage on refactored modules (domain/use-case 100%, nodes 85–87%). Unblocks DDD-MIGRATION, LANGSMITH-PHASE-1, HITL-OBSERVABILITY, DLQ-ADMIN. |

### Tier 1 — Architectural Refactor

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `EPIC-DDD-MIGRATION` | Finish hexagonal refactor (docs/stakeholders/procurement) — `TASK-DDD-004/005/006` | Refactor | P1 | EPIC-CORE-DECOUPLE | Complete router/service migration, delete legacy `schemas.py`, enforce tenant propagation on every port. |

### Tier 2 — Features on Stabilized Base

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `EPIC-LANGSMITH-PHASE-1` | LangSmith Hub foundation (`TASK-AI-003/010/011`) | Feature | P1 | EPIC-CORE-DECOUPLE | Provision org + API keys per env, register prompt metadata/tags, configure A/B experiment scaffolding. |
| `EPIC-LANGSMITH-PHASE-2` ✅ | Tracing + `ai_usage_logs` integration (`TASK-AI-013/014/015`, `TASK-AI-044`, `TASK-INF-012`) | Feature | P1 | PHASE-1 | Wire `@traced_llm_call` into `usage_logger.py`, persist `trace_id`/`trace_url`, expose `POST /api/v1/ai/feedback`. Completed 2026-05-01 via PR #94. |
| `EPIC-LANGSMITH-ANALYTICS` | Analytics APIs + UI (`TASK-AI-016..026`, `TASK-AI-046`, `TASK-INF-014`) | Feature | P1 | PHASE-2 | Implement `/api/v1/ai/analytics/*` with Redis cache; build Dashboard + Version/Cost/Drift components. |
| `EPIC-LANGSMITH-VALIDATION` | Unit + integration + E2E (`TASK-AI-027/028/029`) | Feature | P1 | ANALYTICS | Mock SDK in unit, test DB + mocked LangSmith in integration, Playwright E2E. |
| `EPIC-LANGSMITH-ROLLOUT` | Load, staging, 10→50→100% rollout, monitoring, docs (`TASK-AI-030..034`, `TASK-AI-045`, `TASK-INF-013`) | Feature | P1 | VALIDATION | Load-test 10k/day, verify staging, gradual rollout + trace-failure/latency alerts. |
| `EPIC-LC-WORKFLOWS` | Procurement + RACI + Stakeholder flows with EN/ES prompts (`TASK-AI-040..043`, `TASK-INF-008..011`, `TASK-FRT-124..127`) | Feature | P2 | DDD-MIGRATION + PHASE-2 | Three LangChain flows on hexagonal bounded contexts, EN/ES templates via PromptRegistry, traced end-to-end. |
| `EPIC-HITL-OBSERVABILITY` | Metrics + OpenAPI for HITL resume (`TASK-BCK-032/033`) | Feature | P2 | EPIC-CORE-DECOUPLE | Prometheus/DataDog counters from `ResumeWorkflowUseCase`; publish `/hitl/resume/{id}` contract. |
| `EPIC-DLQ-ADMIN` ✅ | DLQ admin endpoints (`TASK-BCK-042`) | Feature | P2 | EPIC-CORE-DECOUPLE | `GET /admin/dlq` + `POST /admin/dlq/{id}/retry` against DLQService, admin scope, contract tests. Completed 2026-04-27. |
| `TASK-1481` | Supervisor API keys (Claude/Codex/Gemini) | Feature | P1 | — | Provision keys, verify `shlex.split` + models.yaml CLI syntax, prove green auto-mode run. |
| `EPIC-COH-V1-CONSOLIDATION` | Coherence Score v1 — pipeline consolidation + InsufficientEvidence + alerts (pre-signature audit only) | Feature | P0 | EPIC-CORE-DECOUPLE | 9-phase orchestration (Codex/Gemini/OpenCode) merging into `coh-v1/consolidation`. Fixes the `score=100` bug, consolidates two parallel pipelines, builds 18 evaluators behind `LLMRulePort`, persists `score_version` with hard cut-off, wires `AlertGeneratorService` + `meta_alert` AUDIT_INCOMPLETE. PRD: `.claude/PRPs/prds/coherence-score-v1-consolidation.prd.md`. Briefs: `blackboard/SESSION_2026-04-25_coherence-v1-orchestration.md`. |

### Tier 3 — Stabilization & Debt

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `EPIC-TEST-STABILIZATION` ✅ | WBS misplacement + flaky SLA + React `act()` (`TASK-BCK-043/044`, `TASK-QA-077`, `TASK-1480`) | Bug | P2 | DDD-MIGRATION | Completed 2026-04-30; WBS relocation + initial SLA freeze shipped 2026-04-21, remaining SLA boundary cases frozen and alert React tests wrapped in `act()` with raised Vitest timeouts (PR #93). |
| `EPIC-QA-CONTRACT-COVERAGE` | Contract tests + wireframe TCs + quality-gate reports — replanned 2026-05-03 (W7); 31 stubs collapsed into `TASK-QA-200..213` across 3 tracks; spec in [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md#epic-qa-contract-coverage--plan) | Refactor | P2 | DDD-MIGRATION | 3 tracks: Schemathesis (Track A, Sonnet, ~31h), wireframe TCs (Track B, OpenCode, ~22h), quality-gate report pipeline (Track C, Codex, ~7h). DB bootstrap migration folded into Track A. Pact-style contracts WONT-DO (single-consumer monorepo). |
| `EPIC-COVERAGE-GATES` | 70% module coverage + regression proof (merged `AI-048..051`, `INF-016..019`, `FRT-132..135`) | Feature | P3 | QA-CONTRACT-COVERAGE | Target 70% on listed modules, ship coverage-plan tests, prove zero regression. |
| `EPIC-SENTRY-PERF` | Sentry auth alerts + perf benchmarks (`TASK-INF-055/056`) | Feature | P3 | TENANT-RLS-HARDENING | Sentry alerts for auth-failure patterns; codify benchmark harness + baselines. |
| `EPIC-AI-CACHE` | Flash/cache layer (`TASK-AI-047`, `TASK-INF-015`) | Feature | P3 | LANGSMITH-ROLLOUT | README_FLASH cache on Claude wrapper, hit-rate metrics into LangSmith A/B attribution. |
| `TASK-FRT-041` | Clerk production email templates | Feature | P3 | TENANT-RLS-HARDENING | BLOCKED on operator access; close via `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md`. |

### Pruned — `[STATUS: WONT DO]`

| Task ID | Justification |
| ------- | ------------- |
| `TASK-AI-038` | Duplicate of completed `TASK-INF-006`. |
| `TASK-BCK-040` | Superseded by `TASK-QA-072` Phase 1 (2692→82); no new scope. |
| `TASK-BCK-041` | Superseded by completed `TASK-ARCH-002`/`TASK-LINT-002` — 0 security bugs. |
| `TASK-QA-100` / `TASK-QA-101` | Orphan IDs — no specification in source backlog. |
| `TASK-INF-049` / `050` / `051` | Duplicate execution lanes of completed `TASK-DDD-004/005/006`. |
| `TASK-AI-039` / `TASK-INF-007` | Validator already shipped @2026-04-09 via `TASK-FRT-123`. |
| `TASK-FRT-091` | Already marked `[x]` @2026-04-06 in master; detail drift only. |

---

## Pending Tasks by Category

> Only `[ ]` items are listed here. For completed task history, see [`backlogs/COMPLETED.md`](backlogs/COMPLETED.md) or the category backlog files.

### Backend (1 pending)

| Priority | Task ID | Depends On | Description |
| -------- | ------- | ---------- | ----------- |

### Frontend (2 pending)

| Priority | Task ID | Depends On | Description |
| -------- | ------- | ---------- | ----------- |
| P1 | `TASK-FRT-045` | Security | Rotate exposed Clerk test credentials — UNBLOCKED: backend secret channel endpoint + sanitized env templates shipped @2026-04-21. |
| P3 | `TASK-FRT-041` | None | Production email templates and sender verified in Clerk — BLOCKED on operator access. |

### AI / ML Intelligence

Grouped under LangSmith epics (see Manifest v3 §Tier 2):
- `TASK-AI-002`, `TASK-AI-003`, `TASK-AI-010..034`, `TASK-AI-040..047` — split across EPIC-LANGSMITH-PHASE-1/2/ANALYTICS/VALIDATION/ROLLOUT + EPIC-LC-WORKFLOWS + EPIC-AI-CACHE.
- `TASK-IMPL-010` plus 14 subtasks (`.3`..`.16`) → EPIC-CORE-DECOUPLE.
- Full detail: [backlogs/AI_AI_ML_INTELLIGENCE.md](backlogs/AI_AI_ML_INTELLIGENCE.md).

### Infrastructure

- `TASK-INF-008..015` — merged into EPIC-LC-WORKFLOWS / LANGSMITH-PHASE-2 / AI-CACHE.
- `TASK-INF-016..019` — merged into EPIC-COVERAGE-GATES.
- `TASK-INF-055` (Sentry auth monitoring) + `TASK-INF-056` (perf benchmarks) → EPIC-SENTRY-PERF.
- Full detail: [backlogs/INF_INFRASTRUCTURE.md](backlogs/INF_INFRASTRUCTURE.md).

### Quality Assurance

- `EPIC-QA-CONTRACT-COVERAGE` — replanned 2026-05-03 (W7); 31 stubs (`TASK-QA-028/034/050..064/069/070/084..095`) collapsed into 13 planned subtasks (`TASK-QA-200..213`) across 3 tracks. Full spec: [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md#epic-qa-contract-coverage--plan).
- Full detail: [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md).

### Cross-Category

| Priority | Task ID | Description |
| -------- | ------- | ----------- |
| P1 | `TASK-DDD-004` | Hexagonal refactor of `documents` — router/service migration pending. → EPIC-DDD-MIGRATION. |
| P1 | `TASK-DDD-005` | Hexagonal refactor of `stakeholders` — `schemas.py` deletion + router migration pending. → EPIC-DDD-MIGRATION. |
| P1 | `TASK-DDD-006` | Hexagonal refactor of `procurement` — analysis + migration pending. → EPIC-DDD-MIGRATION. |
| P1 | `TASK-1481` | Supervisor API key configuration (Claude/Codex/Gemini CLIs). |

### Coherence v1 (EPIC-COH-V1-CONSOLIDATION)

> Briefs: `blackboard/SESSION_2026-04-25_coherence-v1-orchestration.md` · PRD: `.claude/PRPs/prds/coherence-score-v1-consolidation.prd.md`

| Priority | Task ID | Agent | Depends On | Description |
| -------- | ------- | ----- | ---------- | ----------- |
| P0 | `[x] TASK-COH-V1-01` | Codex | — | Delete `engine_v2.py`, `rules.py`, `service.py`, `services/scoring/calculator.py`. ADR-001. `[x] Implemented (Dead-Code Deletion + ADR)` |
| P0 | `[x] TASK-COH-V1-02` | Gemini 3 Pro | 01 | Rewire N8 → 7-node subgraph. Replace default-100 with `InsufficientEvidence` in `scoring.py:144`, `llm_integration.py:409-414`, `coherence_derivation.py:112-123`. `[x] Implemented (Pipeline Consolidation + InsufficientEvidence)` |
| P0 | `[x] TASK-COH-V1-03` | OpenCode (scaffold) → MASTER (recovery) → Sonnet (completion) | 01 | Define `LLMRulePort` in domain. Move `AnthropicWrapper` callers to `coherence/adapters/ai/`. Snapshot tests. `[x] Implemented (LLMRulePort + LLMRuleEvaluatorAdapter wired through LlmRuleEvaluator and CoherenceLLMService.check_coherence_rule; analyze_clause and analyze_multi_clause_coherence carved out; tests migrated to port injection; 51 passed, 0 errors. Branch: coh-v1/phase-3-opencode → consolidation. See blackboard/coh-v1/PHASE-3-opencode-REPORT.md and PHASE-3-opencode-REDISPATCH.md)` |
| P0 | `[x] TASK-COH-V1-04` | Codex | 01 | Alembic: `score_version` enum + `score_reason` + `score_missing_dimensions`. Repository writes. UI badge stub. ADR-002. `[x] Implemented (Migration + Persistence + UI Stub)` |
| P0 | `[x] TASK-COH-V1-05` | OpenCode | 02, 03, 04 | Build 12 deterministic + 6 LLM evaluators (3+1 × 6 categories). Wire into registry. Orphan `rule_id` startup check. `[x] Implemented (18-Entry Evaluator Registry + Orphan Rule Check)` |
| P0 | `[x] TASK-COH-V1-06` | OpenCode (delivery) → MASTER (recovery) | 02, 05 | `format_output` calls `AlertGeneratorService.process_violations`. Add `AlertType.AUDIT_INCOMPLETE`. ADR-003 ledger transition. `[x] Implemented (AUDIT_INCOMPLETE meta-alert + bilingual templates + ADR-003)` |
| P0 | `[x] TASK-COH-V1-07` | Codex | 02, 04, 05 | Golden-corpus schema: `expected_score_range` + `expected_alerts`. Annotate 15 bundles. CI assertion. `[x] Implemented (Golden Corpus Expectations + CI Assertions)` |
| P0 | `[x] TASK-COH-V1-08` | Gemini 3 Pro (delivery) → MASTER (recovery) | 02 | LangSmith spans on 6 of 7 nodes (skip LLM until rollout=100%). EU-residency attribute allowlist + contract test. Runbook. `[x] Implemented (@traced_coherence_node decorator + allowlist schema + 5/5 contract tests + runbook)` |
| P0 | `[x] TASK-COH-V1-09` | OpenCode (delivery) → MASTER (recovery) | 04, 06, 07 | Dashboard badge + tooltip, alert UX (sort, filter, copy-to-clipboard, AUDIT_INCOMPLETE banner), customer email + FAQ + activated cut-off date. E2E. `[x] Implemented (v1 Dashboard UX + Alert Copy + Customer Comms)` |

---

## Change Log

| Date | Milestone |
| ---- | --------- |
| 2026-05-03 | **EPIC-QA-CONTRACT-COVERAGE replanned (W7 MASTER deliverable)** — 31 legacy QA stubs (`TASK-QA-028/034/050..064/069/070/084..095`) had no specs anywhere; collapsed into 13 planned subtasks (`TASK-QA-200..213`) across 3 tracks: (A) Schemathesis-driven API contract coverage from `docs/api/openapi.yaml` (42 paths / 56 operations across 19 routers), (B) wireframe-traceability TCs for the 6 wireframes in `docs/wireframes/0*.md` plus CE-S2-010 evidence-viewer dossier, (C) quality-gate report pipeline (composite GH Action + PR-comment + CI gate). DB bootstrap migration (refactor `tests/conftest.py` from 1279 LOC) folded into Track A. Pact-style consumer-driven contracts marked WONT-DO (single-consumer monorepo). Dispatch slate: Track A → Sonnet (~31h), Track B → OpenCode (~22h), Track C → Codex (~7h). Full spec inline in `backlogs/QA_QUALITY_ASSURANCE.md`. |
| 2026-05-02 | **B1 + B2 + B3 wave landed** — three parallel-agent PRs merged into main: PR #92 `feat(admin): TASK-BCK-042 — DLQ admin endpoints + BCK-050 metric dedup` (Codex), PR #93 `fix(tests): TASK-QA-077 + TASK-1480 — flake stabilization` (OpenCode), PR #94 `feat(ai): EPIC-LANGSMITH-PHASE-2 — @traced_llm_call decorator + AI feedback endpoint` (Gemini 3 Pro). MASTER (Opus 4.7) reviewed inline due to org Sonnet quota; B3 unblocked by wiring the existing `mock_lookup_tenant_by_id` fixture in `tests/conftest.py`. Reports: `blackboard/dlq-admin/CODEX-REPORT.md`, `blackboard/test-stab/OPENCODE-REPORT.md`, `blackboard/langsmith-phase2/GEMINI-REPORT.md`. |
| 2026-04-27 | **TASK-BCK-042 complete** — Added the `src.admin` bounded context for DLQ administration with Pydantic v2 DTOs, Protocol-backed list/retry use cases, admin HTTP router mounted at `/api/v1/admin/dlq`, and non-admin 403 coverage for both endpoints. The list endpoint is intentionally cross-tenant for admin review; retry delegates to existing `DLQService.increment_retry`. Acceptance: admin unit/integration suite 7/7 passed; OpenAPI snapshot includes `/api/v1/admin/dlq` and `/api/v1/admin/dlq/{dlq_id}/retry`. Bundled BCK-050 fix collapses duplicate Prometheus registration of `c2pro_hitl_checkpoint_load_errors_total` via dual-label compat wrapper. See `blackboard/dlq-admin/CODEX-REPORT.md`. |
| 2026-04-27 | **TASK-COH-V1-09 merged to consolidation** (OpenCode/Sonnet 4.6 delivery + MASTER recovery) — `coh-v1/phase-9-opencode` (commit `1caa8a13`) merged with `--no-ff` (merge `1b771354`). Final state: completed `ScoreVersionBadge` pill + tooltip + customer FAQ link; `CoherenceClient` v1 announcement banner, nullable-score "Score withheld" state, AUDIT_INCOMPLETE CTA; `AlertReviewCenter` severity sort + status filter + copy-to-clipboard with synchronous toast; nullable `score_version` / `score_reason` / `score_missing_dimensions` in dashboard contracts; `/demo/coherence-v1` QA route; customer FAQ at `docs/customer/COHERENCE_V1_FAQ.md`; HTML+TXT announcement templates at `apps/api/src/notifications/templates/`; activated cut-off confirmed at `2026-05-01T00:00:00Z`. **MASTER recovery:** OpenCode reported Playwright e2e/coherence-v1 as 1 passed, but a fresh run failed at line 28 of the spec — the copy-to-clipboard handler awaited `navigator.clipboard.writeText` before calling `setCopiedAlertId`, and in headless chromium without granted clipboard-write permission `writeText` hangs indefinitely (neither resolves nor rejects), so the "Copied" toast never rendered. Repaired in `AlertReviewCenter.tsx` by inverting the order — set state synchronously, then fire-and-forget the clipboard write with attached `.catch()` — so UI feedback always shows regardless of clipboard outcome. Re-verified: 19/19 targeted Vitest pass, `pnpm tsc --noEmit` clean, Playwright 1/1 pass (7.3s). Repository-wide `pnpm vitest run` remains red on 10 pre-existing unrelated frontend suites (21 failing tests, none touching Phase 9 surface). Originally delivered off-pattern on consolidation working tree → wave-branch reconstructed. See `blackboard/coh-v1/PHASE-9-opencode-REPORT.md`. EPIC-COH-V1-CONSOLIDATION fully complete. |
| 2026-04-26 | **TASK-COH-V1-07 complete** — Extended golden-corpus bundle schema with `expected_score_range`, `expected_alerts`, and `score_check`; annotated all 15 existing bundles; added CI assertions for score ranges and expected alert recall; added `apps/api` compatibility entrypoint for `python -m evals.run_evals`; documented bundle-authoring rules in `evals/README.md`. Verification: 15/15 bundles passed, 30/30 expected alerts matched, aggregate alert recall 100%; `tests/evals/test_golden_corpus.py` passed 13/13 including scratch impossible-range failure proof. See `blackboard/coh-v1/PHASE-7-codex-REPORT.md`. |
| 2026-04-26 | **TASK-COH-V1-08 merged to consolidation** (Gemini 3 Pro delivery + MASTER recovery) — `coh-v1/phase-8-gemini` (commit `1dcad3a4`) merged with `--no-ff` (merge `3abd71fe`). Final state: `@traced_coherence_node` decorator (`apps/api/src/core/observability/coherence_tracing.py`) wraps 6 of 7 subgraph nodes (prepare_context, deterministic_evaluate, rag_similarity_check, cross_clause_eval, scoring_arbiter, format_output; `llm_semantic_evaluate` skipped per spec). EU-residency-safe attribute allowlist (`COHERENCE_SPAN_ATTRIBUTE_ALLOWLIST` + Pydantic models) in `coherence_span_schema.py`. `LangSmithClient` extended with `start_span` / `end_span` / `update_span_metadata` / `create_event` and cached `get_client()` singleton. **MASTER recovery:** preserved `enabled` property as backwards-compat alias for the renamed `is_enabled` (caller `prompt_registry.py:89` would have broken otherwise). Discrete alert events emitted from `format_output` on high/critical-severity findings. Contract tests 5/5 pass; 33/33 combined Phase 5+6+8 tests green. Originally delivered off-pattern on consolidation working tree → wave-branch reconstructed. Runbook at `docs/runbooks/COHERENCE_TELEMETRY.md`. See `blackboard/coh-v1/PHASE-8-gemini-REPORT.md`. |
| 2026-04-26 | **TASK-COH-V1-06 merged to consolidation** (OpenCode/Sonnet 4.6 delivery + MASTER recovery) — `coh-v1/phase-6-opencode` (commit `c9aee300`) merged with `--no-ff` (merge `776f379c`). Final state: `AlertType.AUDIT_INCOMPLETE` in `shared_kernel/enums.py`; `format_output` emits an AUDIT_INCOMPLETE meta-alert when `score is None` and `missing_dimensions` is non-empty (helper `_create_audit_incomplete_alert` builds the Alert with synthetic `Evidence`); `alert_generator.py` extended with AUDIT_INCOMPLETE template (es) + `TEMPLATES_EN` skeleton + `get_template(rule_id, locale)` + `template_locale_default="es"`; ADR-003 documents the v0 → v1 ledger cut-off strategy. **MASTER recovery:** OpenCode shipped a green report but its 6-case integration suite was 2/6 failing — `Alert` model requires `evidence: Evidence` and the helper omitted it. Repaired by adding synthetic Evidence (sentinel `source_clause_id="__AUDIT_INCOMPLETE__"`). Final 6/6 pass; 22/22 registry tests still green (no Phase 5 regression). Originally delivered off-pattern on consolidation working tree → wave-branch reconstructed. See `blackboard/coh-v1/PHASE-6-opencode-REPORT.md`. |
| 2026-04-26 | **TASK-COH-V1-05 complete** — Expanded the Coherence Score v1 evaluator registry to 18 entries (12 deterministic + 6 LLM-backed), wired graph deterministic/LLM nodes through the fixed registry, added `LLMRulePort`-backed YAML evaluator coverage including a new technical rule, added alert-template metadata for every v1 `rule_id`, and enforced orphan `rule_id` validation at registry startup. `tests/unit/coherence/rules_engine/` passes 22/22; integration remains blocked by unavailable `postgres-test`; mypy still reports broad existing type debt. |
| 2026-04-26 | **TASK-COH-V1-03 merged to consolidation** (Sonnet executor under MASTER orchestration) — `coh-v1/phase-3-opencode` merged with `--no-ff` after acceptance. Final state: `LLMRulePort` Protocol + `LLMRuleResult` dataclass in `coherence/domain/ports/`; `LLMRuleEvaluatorAdapter` + `get_llm_rule_evaluator()` factory in `coherence/adapters/ai/`; `LlmRuleEvaluator.evaluate_v3_async` + `CoherenceLLMService.check_coherence_rule` route through the port via lazy injection; `analyze_clause` and `analyze_multi_clause_coherence` carved out with `NOTE(TASK-COH-V1-03)` (multi-issue and batch shapes do not fit port v1); test fixtures migrated from `patch("get_anthropic_wrapper")` to `AsyncMock(spec=LLMRulePort)`; 51 passed / 0 failed / 0 errors (was 2 / 11 / 42). See `blackboard/coh-v1/PHASE-3-opencode-REPORT.md`. |
| 2026-04-25 | **TASK-COH-V1-03 redispatched to OpenCode** — Original Phase 3 work delivered the `LLMRulePort` Protocol + `LLMRuleResult` dataclass + `LLMRuleEvaluatorAdapter` + `get_llm_rule_evaluator()` factory + port injection in `LlmRuleEvaluator`, but stopped short of: (a) finishing the `CoherenceLLMService` refactor (4 sites still called `get_anthropic_wrapper()` directly despite docstring claiming port delegation — flagged with inline `TODO(TASK-COH-V1-03 OpenCode redispatch)` markers in `llm_integration.py`), (b) writing the PHASE-3 report file, (c) running snapshot/parity tests, (d) clearing LSP errors. Branch `coh-v1/phase-3-opencode` (commit `2b940597`) carried the WIP + redispatch brief at `blackboard/coh-v1/PHASE-3-opencode-REDISPATCH.md`. Resolved by Sonnet on 2026-04-26 (entry above). |
| 2026-04-25 | **TASK-COH-V1-02 complete** — N8 now delegates to the canonical 7-node coherence subgraph, `ScoringService` returns nullable `ScoringResult` with `insufficient_evidence` semantics, single-clause LLM analysis returns `insufficient_clauses`, extraction-derived unknown dimensions default to `None`, and deprecated flag-based entry points now warn on import. Targeted unit/compile/grep verification passed; broader integration verification is blocked by unavailable local Postgres (`postgres-test`). |
| 2026-04-25 | **TASK-BCK-050 complete** — Removed duplicate HITL Prometheus metric definitions for checkpoint load errors and approval rate, kept the TASK-BCK-032 label contracts, and added an import regression test for `monitoring.py`. |
| 2026-04-25 | **TASK-COH-V1-04 complete (rehook)** — Added `coherence_score_version` enum migration and `coherence_results` audit fields (`score_version`, `score_reason`, `score_missing_dimensions`), extended repository/DTO/domain result surfaces, added the TBD v1 cut-off constant, shipped `ScoreVersionBadge` smoke coverage, and documented no-recompute cut-off rationale in ADR-002. Cherry-picked through pre-commit hooks on `coh-v1/phase-4-codex-rehook`; original commit `d6374ed4` had used `--no-verify` and was redone for hook compliance. |
| 2026-04-25 | **TASK-BCK-050 filed (P1, Backend)** — Duplicate Prometheus metric registration: `HITL_CHECKPOINT_LOAD_ERRORS` defined twice in `apps/api/src/core/observability/monitoring.py` (lines 335 `["error_type"]` + 361 `["reason"]`, same metric name `c2pro_hitl_checkpoint_load_errors_total`). Blocks `pytest -x` collection at module import. Surfaced during TASK-COH-V1-01 review; pre-existing on `main`. Pending count: 0 → 1. |
| 2026-04-25 | **TASK-COH-V1-01 complete** — Deleted dead Coherence v0 files (`engine_v2.py`, `rules.py`, `service.py`, `services/scoring/calculator.py`), removed orphan package/test import surfaces, and added `docs/architecture/adr/ADR-001-coherence-deadcode-deletion.md`. Full `apps/api` pytest remains blocked by pre-existing collection issues (`golden.evaluators` path shadowing; HITL Prometheus duplicate metric registration when bypassed). |
| 2026-04-25 | **EPIC-COH-V1-CONSOLIDATION created (orchestration plan)** — Coherence Score v1 consolidation epic registered in Tier 2 with 9 sub-tasks (`TASK-COH-V1-01..09`) assigned across Codex / Gemini 3 Pro / OpenCode (Sonnet 4.6). Orchestrator (Claude Opus 4.7) reviews and merges per phase into `coh-v1/consolidation`. PRD: `.claude/PRPs/prds/coherence-score-v1-consolidation.prd.md`. Briefs (self-contained dispatch packs + per-phase report paths + acceptance commands): `blackboard/SESSION_2026-04-25_coherence-v1-orchestration.md`. Reports land in `blackboard/coh-v1/PHASE-N-<agent>-REPORT.md`. Wave plan: A=[1] · B=[2,3,4] · C=[5] · D=[6,7,8] · E=[9]. |
| 2026-04-21 | **EPIC-LANGSMITH-ROLLOUT complete** — Delivered deterministic canary routing (`src/core/ai/rollout_router.py`) with fail-open fallback for traced-call outages, k6 synthetic load profile (`apps/api/tests/load/langsmith_rollout_load_test.js`) for 10k/day-equivalent staging validation, critical rollout alert rules (`ops/alerts/langsmith_rollout_alerts.yml`) for trace failure and p99 latency regression thresholds, and emergency rollback/operator runbook (`docs/runbooks/LANGSMITH_ROLLOUT_EMERGENCY.md`). Backlog mutation payload: `[STATUS: DONE - EPIC-LANGSMITH-ROLLOUT] [ACTION: LANGSMITH IN PRODUCTION - ROLLOUT AT 10% - MONITORING ACTIVE]`. |
| 2026-04-21 | **EPIC-LANGSMITH-VALIDATION complete** — Delivered testing pyramid for LangSmith observability: global SDK isolation fixture (`langsmith.Client` + `langchain.hub`), unit tests for traced decorator/feedback/analytics aggregation, integration tests proving `ai_usage_logs` persistence + analytics/feedback API behavior against test DB with mocked external AI layer, and Playwright E2E dashboard validation with deterministic `/api/v1/ai/analytics/*` route interception. Backlog mutation payload: `[STATUS: DONE - EPIC-LANGSMITH-VALIDATION] [ACTION: TEST PYRAMID GREEN - PIPELINE UNBLOCKED]`. |
| 2026-04-21 | **EPIC-DDD-MIGRATION complete** — Enforced tenant-first port signatures across documents/stakeholders/procurement bounded-context repositories, added tenant boundary type guard (`src/core/tenants/types.py`), and propagated tenant-aware adapter/use-case wiring in stakeholder and procurement flows. Backlog mutation payload: `[STATUS: DONE - EPIC-DDD-MIGRATION] [ACTION: LEGACY SCHEMAS.PY DESTROYED]`. |
| 2026-04-21 | **EPIC-TENANT-RLS-HARDENING complete** — Added Alembic migration `20260421_0001_harden_clause_embeddings_rls.py` to enforce fail-closed RLS on `clause_embeddings` via `projects.tenant_id` + `app.current_tenant`; delivered approved secret channel endpoint `GET /api/v1/security/secret-channel/clerk` with token-gated access and backend provider abstraction (`env_json`/AWS Secrets Manager/Vault); sanitized frontend/backend env templates to remove shared secret-bearing workflow. `TASK-FRT-045` moved to unblocked execution state. |
| 2026-04-21 | **TASK-BCK-032 complete** — HITL resume monitoring: added `c2pro_hitl_checkpoint_load_errors_total`, `c2pro_hitl_workflow_resume_errors_total`, `c2pro_hitl_decision_total`, and `c2pro_hitl_approval_rate` Prometheus metrics; feature-detected DataDog StatsD adapter (`c2pro.hitl.*`); tenant-scoped audit log event `hitl_decision_recorded`; runbook `docs/runbooks/HITL_RESUME_MONITORING.md` with PromQL dashboards + alert rules; 20 new unit tests in `apps/api/tests/unit/core/observability/test_hitl_metrics.py` and `apps/api/tests/unit/modules/hitl/test_resume_workflow_metrics.py`. Backend pending count: 1 → 0. |
| 2026-04-21 | **TASK-BCK-033 complete** — OpenAPI contract for `POST /api/v1/hitl/resume/{review_id}` now includes explicit operationId, request/response examples, and enum-constrained decision schema (`approve`/`reject`), with coverage in `apps/api/tests/core/test_hitl_resume_openapi.py`. Backend pending count: 2 → 1. |
| 2026-04-21 | **EPIC-TEST-STABILIZATION partial close** — TASK-BCK-043 (relocated `test_wbs_node_repository.py` from `tests/unit/wbs/` to `tests/integration/wbs/`) and TASK-BCK-044 (added `freezegun==1.5.1`; froze time on `test_calculate_at_exact_due_time` boundary case) shipped on `claude/execute-backlog-task-kBOJ3`. Backend pending count: 4 → 2. |
| 2026-04-21 | **Slim-master restructure** — Moved 132 completed rows and verbose history to `backlogs/COMPLETED.md`; fixed Quick Navigation table spacing; master now tracks pending-only + Restructured Manifest v3. |
| 2026-04-21 | **Restructured Manifest v3 (Epic-Based)** — 130+ pending tasks consolidated into 15 dependency-ordered epics across 4 tiers; 3 foundational epics injected; 11 duplicate/orphan tasks pruned as WONT DO. See `blackboard/SESSION_2026-04-21_backlog_audit.md`. |
| 2026-04-20 | **Backlog-drift reconciliation pass** — TASK-BCK-020/028/030, TASK-AI-007, TASK-1474/1479, TASK-EVAL-015 flipped to `[x]` with verification pointers. |
| 2026-04-11 | **Production bug fixes** — TASK-BCK-046 (project status select + `expected_version`) and TASK-BCK-047 (document reprocess endpoint + retry button) shipped. |
| 2026-04-09 | **TASK-IMPL-010 complete** — Decouple AI logic from LangGraph nodes; 222/222 tests GREEN; `nodes.py` -24%, `nodes_extended.py` -23%. |
| 2026-04-04 | **Agent orchestration unification complete** — All 16 UNIFY tasks shipped; mandatory `backlog_id`, 4-layer defense-in-depth validation, 9-role schemas, Agent Orchestration Guide. |

Older entries archived in [`backlogs/COMPLETED.md`](backlogs/COMPLETED.md).
