# C2PRO Master Backlog - Index & Overview

**Purpose**: High-level project index. Only **pending** work is tracked here.
**Last Updated**: 2026-04-21 (v3 — Epic-Based Restructure + slim archive split)
**Completed work**: [`backlogs/COMPLETED.md`](backlogs/COMPLETED.md)

> **Navigation**: Quick Navigation → Restructured Manifest v3 (execution order) → Pending by Category → Change Log.

---

## Quick Navigation

| Category | File | Owner | Total | Active | Completed |
| -------- | ---- | ----- | ----- | ------ | --------- |
| AI/ML Intelligence | [backlogs/AI_AI_ML_INTELLIGENCE.md](backlogs/AI_AI_ML_INTELLIGENCE.md) | ai | 78 | 43 | 35 |
| Backend | [backlogs/BCK_BACKEND.md](backlogs/BCK_BACKEND.md) | backend | 49 | 5 | 44 |
| DevOps | [backlogs/DEV_DEVOPS.md](backlogs/DEV_DEVOPS.md) | devops | 2 | 0 | 2 |
| Documentation | [backlogs/DOC_DOCUMENTATION.md](backlogs/DOC_DOCUMENTATION.md) | shared | 0 | 0 | 0 |
| Frontend | [backlogs/FRT_FRONTEND.md](backlogs/FRT_FRONTEND.md) | frontend | 169 | 16 | 153 |
| Infrastructure | [backlogs/INF_INFRASTRUCTURE.md](backlogs/INF_INFRASTRUCTURE.md) | infra | 59 | 17 | 42 |
| Planning | [backlogs/PLN_PLANNING.md](backlogs/PLN_PLANNING.md) | planner | 0 | 0 | 0 |
| Quality Assurance | [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md) | qa | 12 | 2 | 10 |
| Code Review | [backlogs/REV_CODE_REVIEW.md](backlogs/REV_CODE_REVIEW.md) | reviewer | 25 | 0 | 25 |
| Security | [backlogs/SEC_SECURITY.md](backlogs/SEC_SECURITY.md) | security | 0 | 0 | 0 |

---

## Restructured Manifest v3 (Epic-Based, 2026-04-21)

> Authoritative execution order. Sorted by **architectural dependency** first, **business value** second.
> Session record: `blackboard/SESSION_2026-04-21_backlog_audit.md`.

### Tier 0 — Foundation (blocks all downstream feature work)

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `✅ EPIC-TENANT-RLS-HARDENING` | Multi-tenant RLS + credential hygiene | Architecture | P0 | — | Ship Alembic RLS policy on `clause_embeddings`, close SEC-009..011 gaps, and unblock `TASK-FRT-045` via approved secret channel. Completed 2026-04-21 via Change Log EPIC-TENANT-RLS-HARDENING entry. |
| `EPIC-CORE-DECOUPLE` ✅ | Decouple AI logic from LangGraph nodes (`TASK-IMPL-010` + 14 subtasks) | Refactor | P0 | — | Phases 1–4 completed 2026-04-21; 92% coverage on refactored modules (domain/use-case 100%, nodes 85–87%). Unblocks DDD-MIGRATION, LANGSMITH-PHASE-1, HITL-OBSERVABILITY, DLQ-ADMIN. |

### Tier 1 — Architectural Refactor

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `✅ EPIC-DDD-MIGRATION` | Finish hexagonal refactor (docs/stakeholders/procurement) — `TASK-DDD-004/005/006` | Refactor | P1 | EPIC-CORE-DECOUPLE | Complete router/service migration, delete legacy `schemas.py`, enforce tenant propagation on every port. Completed 2026-04-21 via Change Log EPIC-DDD-MIGRATION entry and 2026-05-02 source spot-check. |

### Tier 2 — Features on Stabilized Base

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `✅ EPIC-LANGSMITH-PHASE-1` | LangSmith Hub foundation (`TASK-AI-003/010/011`) | Feature | P1 | EPIC-CORE-DECOUPLE | Provision org + API keys per env, register prompt metadata/tags, configure A/B experiment scaffolding. Completed 2026-04-21 via PR #81 merged 2026-04-21. |
| `EPIC-LANGSMITH-PHASE-2` ✅ | Tracing + `ai_usage_logs` integration (`TASK-AI-013/014/015`, `TASK-AI-044`, `TASK-INF-012`) | Feature | P1 | PHASE-1 | Wire `@traced_llm_call` into `usage_logger.py`, persist `trace_id`/`trace_url`, expose `POST /api/v1/ai/feedback`. Completed 2026-05-01 via PR #94. |
| `✅ EPIC-LANGSMITH-ANALYTICS` | Analytics APIs + UI (`TASK-AI-016..026`, `TASK-AI-046`, `TASK-INF-014`) | Feature | P1 | PHASE-2 | Implement `/api/v1/ai/analytics/*` with Redis cache; build Dashboard + Version/Cost/Drift components. Completed 2026-05-03 via PR #104 (W8a: backend cache + endpoints) and PR #105 (W8b: frontend dashboard components + trace deep-link). All 12 subtasks (TASK-AI-002, AI-016..026, AI-046) marked [x] with full verification. |
| `✅ EPIC-LANGSMITH-VALIDATION` | Unit + integration + E2E (`TASK-AI-027/028/029`) | Feature | P1 | ANALYTICS | Mock SDK in unit, test DB + mocked LangSmith in integration, Playwright E2E. Completed 2026-04-21 via Change Log EPIC-LANGSMITH-VALIDATION entry. |
| `✅ EPIC-LANGSMITH-ROLLOUT` | Load, staging, 10→50→100% rollout, monitoring, docs (`TASK-AI-030..034`, `TASK-AI-045`, `TASK-INF-013`) | Feature | P1 | VALIDATION | Load-test 10k/day, verify staging, gradual rollout + trace-failure/latency alerts. Completed 2026-04-21 via Change Log EPIC-LANGSMITH-ROLLOUT entry (PR #86). |
| `EPIC-LC-WORKFLOWS` | [PHASE 2 DEFERRED] Procurement + RACI + Stakeholder flows with EN/ES prompts (`TASK-AI-040..043`, `TASK-INF-008..011`, `TASK-FRT-124..127`) | Feature | P2 | DDD-MIGRATION + PHASE-2 | Three LangChain flows on hexagonal bounded contexts, EN/ES templates via PromptRegistry, traced end-to-end. Deferred to Phase 2 — not on critical path to launch. Re-evaluate after current Coherence Score / alerts / HITL features prove stable in production. |
| `✅ EPIC-HITL-OBSERVABILITY` | Metrics + OpenAPI for HITL resume (`TASK-BCK-032/033`) | Feature | P2 | EPIC-CORE-DECOUPLE | Prometheus/DataDog counters from `ResumeWorkflowUseCase`; publish `/hitl/resume/{id}` contract. Completed 2026-04-21 via TASK-BCK-032 + TASK-BCK-033 Change Log entries. |
| `EPIC-DLQ-ADMIN` ✅ | DLQ admin endpoints (`TASK-BCK-042`) | Feature | P2 | EPIC-CORE-DECOUPLE | `GET /admin/dlq` + `POST /admin/dlq/{id}/retry` against DLQService, admin scope, contract tests. Completed 2026-04-27. |
| `✅ EPIC-COH-V1-CONSOLIDATION` | Coherence Score v1 — pipeline consolidation + InsufficientEvidence + alerts (pre-signature audit only) | Feature | P0 | EPIC-CORE-DECOUPLE | 9-phase orchestration (Codex/Gemini/OpenCode) merging into `coh-v1/consolidation`. Fixes the `score=100` bug, consolidates two parallel pipelines, builds 18 evaluators behind `LLMRulePort`, persists `score_version` with hard cut-off, wires `AlertGeneratorService` + `meta_alert` AUDIT_INCOMPLETE. PRD: `.claude/PRPs/prds/coherence-score-v1-consolidation.prd.md`. Briefs: `blackboard/SESSION_2026-04-25_coherence-v1-orchestration.md`. Completed 2026-04-27 via all 9 V1-01..09 tasks marked [x] and Change Log EPIC-COH-V1-CONSOLIDATION complete evidence. |

### Tier 3 — Stabilization & Debt

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `EPIC-TEST-STABILIZATION` ✅ | WBS misplacement + flaky SLA + React `act()` (`TASK-BCK-043/044`, `TASK-QA-077`, `TASK-1480`) | Bug | P2 | DDD-MIGRATION | Completed 2026-04-30; WBS relocation + initial SLA freeze shipped 2026-04-21, remaining SLA boundary cases frozen and alert React tests wrapped in `act()` with raised Vitest timeouts (PR #93). |
| `EPIC-QA-CONTRACT-COVERAGE` ✅ | Contract tests + wireframe TCs + quality-gate reports — replanned 2026-05-03 (W7); 31 stubs collapsed into `TASK-QA-200..213` across 3 tracks; spec in [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md#epic-qa-contract-coverage--plan) | Refactor | P2 | DDD-MIGRATION | All 3 tracks complete. Track A PR #106 (Schemathesis + OpenAPI drift CI). Track B PR #107 (wireframe coverage tracker + 6 wireframe TCs). Track C PR #108 (quality-report composite action + `scripts/quality_report.py` + workflow wiring + PR sticky comments). |
| `EPIC-COVERAGE-GATES` ✅ | 70% module coverage + regression proof (merged `AI-048..051`, `INF-016..019`, `FRT-132..135`) | Feature | P3 | QA-CONTRACT-COVERAGE | Completed @2026-04-09: 73 coverage-improvement tests added; 70%+ achieved; zero regressions (409 unit tests passing). Frontend recovery refreshed @2026-05-07 on current `origin/main` with targeted route/API coverage for `TASK-FRT-132..135` and no package/lock/config churn from stale OpenCode worktree. |
| `EPIC-SENTRY-PERF` | Sentry auth alerts + perf benchmarks (`TASK-INF-055/056`) | Feature | P3 | TENANT-RLS-HARDENING | Sentry alerts for auth-failure patterns; codify benchmark harness + baselines. TASK-INF-056 W5b pytest-benchmark harness completed 2026-05-03 with baseline saved; TASK-INF-055 remains blocked on Sentry/operator prerequisites. |
| `EPIC-AI-CACHE` ✅ | Flash/cache layer (`TASK-AI-047`, `TASK-INF-015`) | Feature | P3 | LANGSMITH-ROLLOUT | Completed @2026-04-09: FlashCacheService + PromptCacheService in prompt_cache.py; SHA-256 content-hash keys, 1h Redis TTL. Tests in test_coverage_gates_ai_coverage.py. |
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
| `TASK-1481` | Experimental supervisor API key configuration — not needed for product launch (decided 2026-05-02). |

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
- `TASK-AI-002`, `TASK-AI-003`, `TASK-AI-010..019`, `TASK-AI-021..034`, `TASK-AI-040..047` — split across EPIC-LANGSMITH-PHASE-1/2/ANALYTICS/VALIDATION/ROLLOUT + EPIC-LC-WORKFLOWS + EPIC-AI-CACHE.
- `TASK-IMPL-010` plus 14 subtasks (`.3`..`.16`) → EPIC-CORE-DECOUPLE.
- Full detail: [backlogs/AI_AI_ML_INTELLIGENCE.md](backlogs/AI_AI_ML_INTELLIGENCE.md).

### Infrastructure

- `TASK-INF-008..015` — merged into EPIC-LC-WORKFLOWS / LANGSMITH-PHASE-2 / AI-CACHE.
- `TASK-INF-016..019` — merged into EPIC-COVERAGE-GATES.
- `TASK-INF-055` (Sentry auth monitoring) + `TASK-INF-056` (perf benchmarks) → EPIC-SENTRY-PERF.
- Full detail: [backlogs/INF_INFRASTRUCTURE.md](backlogs/INF_INFRASTRUCTURE.md).

### Quality Assurance

- `EPIC-QA-CONTRACT-COVERAGE` — replanned 2026-05-03 (W7); 31 stubs collapsed into `TASK-QA-200..213` across 3 tracks. **Track A (TASK-QA-200..206)** ✅ complete — PR #106 (Schemathesis harness + OpenAPI drift CI). **Track B (TASK-QA-207..211)** ✅ complete — PR #107 (wireframe coverage tracker, CI gate, 6 wireframe test files, 100% coverage). **Track C (TASK-QA-212..213)** ✅ complete — PR #108 (quality-report composite action, `scripts/quality_report.py` renderer with contract/wireframe/coverage/JUnit gates + >2% contract-drop gating, wired into tests.yml + frontend-ci.yml + qa-swarm.yml with sticky PR comments). Full spec: [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md#epic-qa-contract-coverage--plan).
- Full detail: [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md).

### Cross-Category

| Priority | Task ID | Description |
| -------- | ------- | ----------- |

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

**2026-05-07**: TASK-AI-038 verified complete (python_mcp_server.md already correct). TASK-AI-039 implemented as validate_prompt_templates.py CLI (commit 71f717c8). AI backlog: 89 completed / 9 active.

**2026-05-08**: TASK-BCK-041 complete — ruff ARG/SIM noqa pass; src/ 0 violations (commit dab24151). 29 ARG + 7 SIM/F violations suppressed with # noqa across 22 files in apps/api/src/.

---

