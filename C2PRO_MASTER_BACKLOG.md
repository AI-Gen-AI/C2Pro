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
| Backend | [backlogs/BCK_BACKEND.md](backlogs/BCK_BACKEND.md) | backend | 28 | 7 | 21 |
| DevOps | [backlogs/DEV_DEVOPS.md](backlogs/DEV_DEVOPS.md) | devops | 2 | 0 | 2 |
| Documentation | [backlogs/DOC_DOCUMENTATION.md](backlogs/DOC_DOCUMENTATION.md) | shared | 0 | 0 | 0 |
| Frontend | [backlogs/FRT_FRONTEND.md](backlogs/FRT_FRONTEND.md) | frontend | 163 | 26 | 137 |
| Infrastructure | [backlogs/INF_INFRASTRUCTURE.md](backlogs/INF_INFRASTRUCTURE.md) | infra | 59 | 18 | 41 |
| Planning | [backlogs/PLN_PLANNING.md](backlogs/PLN_PLANNING.md) | planner | 0 | 0 | 0 |
| Quality Assurance | [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md) | qa | 96 | 35 | 61 |
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
| `EPIC-CORE-DECOUPLE` | Decouple AI logic from LangGraph nodes (`TASK-IMPL-010` + 14 subtasks) | Refactor | P0 | — | Execute Phases 1–4: domain services → use cases → node delegations → workflow edge + 80% coverage gate. |

### Tier 1 — Architectural Refactor

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `EPIC-DDD-MIGRATION` | Finish hexagonal refactor (docs/stakeholders/procurement) — `TASK-DDD-004/005/006` | Refactor | P1 | EPIC-CORE-DECOUPLE | Complete router/service migration, delete legacy `schemas.py`, enforce tenant propagation on every port. |

### Tier 2 — Features on Stabilized Base

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `EPIC-LANGSMITH-PHASE-1` | LangSmith Hub foundation (`TASK-AI-003/010/011`) | Feature | P1 | EPIC-CORE-DECOUPLE | Provision org + API keys per env, register prompt metadata/tags, configure A/B experiment scaffolding. |
| `EPIC-LANGSMITH-PHASE-2` | Tracing + `ai_usage_logs` integration (`TASK-AI-013/014/015`, `TASK-AI-044`, `TASK-INF-012`) | Feature | P1 | PHASE-1 | Wire `@traced_llm_call` into `usage_logger.py`, persist `trace_id`/`trace_url`, expose `POST /api/v1/ai/feedback`. |
| `EPIC-LANGSMITH-ANALYTICS` | Analytics APIs + UI (`TASK-AI-016..026`, `TASK-AI-046`, `TASK-INF-014`) | Feature | P1 | PHASE-2 | Implement `/api/v1/ai/analytics/*` with Redis cache; build Dashboard + Version/Cost/Drift components. |
| `EPIC-LANGSMITH-VALIDATION` | Unit + integration + E2E (`TASK-AI-027/028/029`) | Feature | P1 | ANALYTICS | Mock SDK in unit, test DB + mocked LangSmith in integration, Playwright E2E. |
| `EPIC-LANGSMITH-ROLLOUT` | Load, staging, 10→50→100% rollout, monitoring, docs (`TASK-AI-030..034`, `TASK-AI-045`, `TASK-INF-013`) | Feature | P1 | VALIDATION | Load-test 10k/day, verify staging, gradual rollout + trace-failure/latency alerts. |
| `EPIC-LC-WORKFLOWS` | Procurement + RACI + Stakeholder flows with EN/ES prompts (`TASK-AI-040..043`, `TASK-INF-008..011`, `TASK-FRT-124..127`) | Feature | P2 | DDD-MIGRATION + PHASE-2 | Three LangChain flows on hexagonal bounded contexts, EN/ES templates via PromptRegistry, traced end-to-end. |
| `EPIC-HITL-OBSERVABILITY` | Metrics + OpenAPI for HITL resume (`TASK-BCK-032/033`) | Feature | P2 | EPIC-CORE-DECOUPLE | Prometheus/DataDog counters from `ResumeWorkflowUseCase`; publish `/hitl/resume/{id}` contract. |
| `EPIC-DLQ-ADMIN` | DLQ admin endpoints (`TASK-BCK-042`) | Feature | P2 | EPIC-CORE-DECOUPLE | `GET /admin/dlq` + `POST /admin/dlq/{id}/retry` against DLQService, admin scope, contract tests. |
| `TASK-1481` | Supervisor API keys (Claude/Codex/Gemini) | Feature | P1 | — | Provision keys, verify `shlex.split` + models.yaml CLI syntax, prove green auto-mode run. |

### Tier 3 — Stabilization & Debt

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `EPIC-TEST-STABILIZATION` | WBS misplacement + flaky SLA + React `act()` (`TASK-BCK-043/044`, `TASK-QA-077`, `TASK-1480`) | Bug | P2 | DDD-MIGRATION | Relocate WBS integration tests, freeze time on SLA boundary, wrap React updates in `act()` with raised timeouts. |
| `EPIC-QA-CONTRACT-COVERAGE` | Contract tests + wireframe TCs + quality-gate reports (`TASK-QA-028/034/050..064/069/070/084..095`) | Refactor | P2 | DDD-MIGRATION | Re-plan 20+ stubs as one contract-test deliverable (schemathesis/pact), migrate DB bootstrap, publish report pipeline. |
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

### Backend (0 pending)

All backend tasks complete as of 2026-04-21. Future backend work will be tracked in the Manifest v3 epics or added here as it surfaces.

### Frontend (2 pending)

| Priority | Task ID | Depends On | Description |
| -------- | ------- | ---------- | ----------- |
| P1 | `TASK-FRT-045` | Security | Rotate exposed Clerk test credentials — BLOCKED on operator access. |
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

- `TASK-QA-028/034/050..064/069/070/084..095` → EPIC-QA-CONTRACT-COVERAGE (single deliverable; current entries are stubs needing replan).
- `TASK-QA-077` → EPIC-TEST-STABILIZATION.
- Full detail: [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md).

### Cross-Category

| Priority | Task ID | Description |
| -------- | ------- | ----------- |
| P1 | `TASK-DDD-004` | Hexagonal refactor of `documents` — router/service migration pending. → EPIC-DDD-MIGRATION. |
| P1 | `TASK-DDD-005` | Hexagonal refactor of `stakeholders` — `schemas.py` deletion + router migration pending. → EPIC-DDD-MIGRATION. |
| P1 | `TASK-DDD-006` | Hexagonal refactor of `procurement` — analysis + migration pending. → EPIC-DDD-MIGRATION. |
| P2 | `TASK-1480` | UI test stabilization — wrap `act(...)` + raise timeouts in `alerts`/`evidence` page tests. → EPIC-TEST-STABILIZATION. |
| P1 | `TASK-1481` | Supervisor API key configuration (Claude/Codex/Gemini CLIs). |

---

## Change Log

| Date | Milestone |
| ---- | --------- |
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
