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
| Backend | [backlogs/BCK_BACKEND.md](backlogs/BCK_BACKEND.md) | backend | 53 | 6 | 47 |
| DevOps | [backlogs/DEV_DEVOPS.md](backlogs/DEV_DEVOPS.md) | devops | 2 | 0 | 2 |
| Documentation | [backlogs/DOC_DOCUMENTATION.md](backlogs/DOC_DOCUMENTATION.md) | shared | 0 | 0 | 0 |
| Frontend | [backlogs/FRT_FRONTEND.md](backlogs/FRT_FRONTEND.md) | frontend | 170 | 16 | 154 |
| Infrastructure | [backlogs/INF_INFRASTRUCTURE.md](backlogs/INF_INFRASTRUCTURE.md) | infra | 59 | 17 | 42 |
| Planning | [backlogs/PLN_PLANNING.md](backlogs/PLN_PLANNING.md) | planner | 0 | 0 | 0 |
| Quality Assurance | [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md) | qa | 120 | 108 | 12 |
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
| `EPIC-LC-WORKFLOWS` | [PHASE 2 DEFERRED] Procurement + RACI + Stakeholder + intelligent WBS flows with EN/ES prompts (`TASK-AI-040..043`, `TASK-AI-049`, `TASK-INF-008..011`, `TASK-FRT-124..127`) | Feature | P2 | DDD-MIGRATION + PHASE-2 | LangChain flows on hexagonal bounded contexts, EN/ES templates via PromptRegistry, traced end-to-end. Deferred to Phase 2 — not on critical path to launch. Re-evaluate after current Coherence Score / alerts / HITL features prove stable in production and after the Swagger flow audit is complete. |
| `✅ EPIC-HITL-OBSERVABILITY` | Metrics + OpenAPI for HITL resume (`TASK-BCK-032/033`) | Feature | P2 | EPIC-CORE-DECOUPLE | Prometheus/DataDog counters from `ResumeWorkflowUseCase`; publish `/hitl/resume/{id}` contract. Completed 2026-04-21 via TASK-BCK-032 + TASK-BCK-033 Change Log entries. |
| `EPIC-DLQ-ADMIN` ✅ | DLQ admin endpoints (`TASK-BCK-042`) | Feature | P2 | EPIC-CORE-DECOUPLE | `GET /admin/dlq` + `POST /admin/dlq/{id}/retry` against DLQService, admin scope, contract tests. Completed 2026-04-27. |
| `✅ EPIC-COH-V1-CONSOLIDATION` | Coherence Score v1 — pipeline consolidation + InsufficientEvidence + alerts (pre-signature audit only) | Feature | P0 | EPIC-CORE-DECOUPLE | 9-phase orchestration (Codex/Gemini/OpenCode) merging into `coh-v1/consolidation`. Fixes the `score=100` bug, consolidates two parallel pipelines, builds 18 evaluators behind `LLMRulePort`, persists `score_version` with hard cut-off, wires `AlertGeneratorService` + `meta_alert` AUDIT_INCOMPLETE. PRD: `.claude/PRPs/prds/coherence-score-v1-consolidation.prd.md`. Briefs: `blackboard/SESSION_2026-04-25_coherence-v1-orchestration.md`. Completed 2026-04-27 via all 9 V1-01..09 tasks marked [x] and Change Log EPIC-COH-V1-CONSOLIDATION complete evidence. |

### Tier 3 — Stabilization & Debt

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `EPIC-TEST-STABILIZATION` ✅ | WBS misplacement + flaky SLA + React `act()` (`TASK-BCK-043/044`, `TASK-QA-077`, `TASK-1480`) | Bug | P2 | DDD-MIGRATION | Completed 2026-04-30; WBS relocation + initial SLA freeze shipped 2026-04-21, remaining SLA boundary cases frozen and alert React tests wrapped in `act()` with raised Vitest timeouts (PR #93). |
| `EPIC-QA-CONTRACT-COVERAGE` ✅ | Contract tests + wireframe TCs + quality-gate reports — replanned 2026-05-03 (W7); 31 stubs collapsed into `TASK-QA-200..213` across 3 tracks; spec in [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md#epic-qa-contract-coverage--plan) | Refactor | P2 | DDD-MIGRATION | All 3 tracks complete. Track A PR #106 (Schemathesis + OpenAPI drift CI). Track B PR #107 (wireframe coverage tracker + 6 wireframe TCs). Track C PR #108 (quality-report composite action + `scripts/quality_report.py` + workflow wiring + PR sticky comments). |
| `EPIC-COVERAGE-GATES` ✅ | 70% module coverage + regression proof (merged `AI-048..051`, `INF-016..019`, `FRT-132..135`) | Feature | P3 | QA-CONTRACT-COVERAGE | Completed @2026-04-09: 73 coverage-improvement tests added; 70%+ achieved; zero regressions (409 unit tests passing). Frontend recovery refreshed @2026-05-07 on current `origin/main` with targeted route/API coverage for `TASK-FRT-132..135` and no package/lock/config churn from stale OpenCode worktree. |
| `EPIC-OPS-DOCFLOW` | Real document operability gate (`TASK-OPS-DOCFLOW-003..012`) | Quality | P0 | EPIC-COVERAGE-GATES | Move confidence from scoped coverage to the real C2Pro core flow: sanitized real construction documents upload, parse, anonymize, extract, score, alert, and render through tenant-safe API/UI. Source plan: `blackboard/coverage-gates/REAL-DOCUMENT-OPERABILITY-SPEC-PLAN.md`. |
| `EPIC-SENTRY-PERF` | Sentry auth alerts + perf benchmarks (`TASK-INF-055/056`) | Feature | P3 | TENANT-RLS-HARDENING | Sentry alerts for auth-failure patterns; codify benchmark harness + baselines. TASK-INF-056 W5b pytest-benchmark harness completed 2026-05-03 with baseline saved; TASK-INF-055 remains blocked on Sentry/operator prerequisites. |
| `EPIC-AI-CACHE` ✅ | Flash/cache layer (`TASK-AI-047`, `TASK-INF-015`) | Feature | P3 | LANGSMITH-ROLLOUT | Completed @2026-04-09: FlashCacheService + PromptCacheService in prompt_cache.py; SHA-256 content-hash keys, 1h Redis TTL. Tests in test_coverage_gates_ai_coverage.py. |
| `TASK-FRT-041` | Clerk production email templates | Feature | P3 | TENANT-RLS-HARDENING | BLOCKED on operator access; close via `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md`. |

### Tier 4 — Coherence Score™ v2 Hotfix & Cutover (2026-05-26)

> **Trademark-critical.** Coherence Score™ is a registered C2Pro differentiator. Bug repro: `POST /api/v1/coherence/evaluate/diagnostics` on SCOPE-only project returns `overall_score=15` — must return `null` + `score_reason="insufficient_active_weight"` per ADR-009 §1 P1 + §14. Spec: `docs/superpowers/specs/2026-05-25-ecoa-v2-hotfix-and-cutover-design.md`. Plan: `docs/superpowers/plans/2026-05-25-ecoa-v2-hotfix-and-cutover.md`.

| Task ID | Title | Type | Priority | Blocking Deps | Technical Strategy |
| ------- | ----- | ---- | -------- | ------------- | ------------------ |
| `EPIC-ECOA-V2-HOTFIX-AND-CUTOVER` | ECOA v2 §14 active-weight guard + adapter fix + frontend null-safe + `score_version` canonical + cache namespacing + per-tenant v2 cutover | Bug+Feature | P0 | EPIC-COH-V1-CONSOLIDATION | 7-task epic (`TASK-COH-V2-HOTFIX-001` through `-CUTOVER-004`). Phase A+B: v1 hotfix + adapter (one PR). C: frontend null-safe (one PR). F: `score_version` canonical 2-value enum + Alembic backfill. G: cache namespace versioning + flag-flip invalidation. D: v2 authoritative behind per-tenant flag — extend existing `Tenant.settings: JSONB` (alerts pattern, no new tables); canary 10→50→100 with shadow-MAE ≤ 15 auto-block. E: ADR-009 status flip + OpenAPI regen + codemap. Branch policy: **no pushes to `main`** for any task. |

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
| P0 | `TASK-BCK-051` | None | Investigate live `500` responses on project alerts and project stakeholders by correlating production error references with backend logs and verifying applied Alembic head/schema parity for tenant-hardened tables. Live schema drift was repaired on 2026-05-16 via `20260516_0001`; 2026-05-25 local parity check repaired stale stakeholder contract fixture drift and verified Alembic single head `20260524_0001`; log correlation remains blocked on unavailable production log access. |
| ~~P0~~ | ~~`TASK-BCK-052`~~ | None | ~~Fix `/api/v1/analysis/analyze` runtime failure where LangGraph parallel fan-out/join wiring duplicated downstream state writes such as `project_id`, causing `InvalidUpdateError` after successful document parsing.~~ `[x] Implemented (True Multi-Source Fan-In + Branch State Isolation)` |
| ~~P1~~ | ~~`TASK-BCK-053`~~ | None | ~~Stop fresh `/api/v1/analysis/analyze` requests from reusing project-level LangGraph checkpoint threads, which replays prior workflow messages into new analyses for the same project.~~ `[x] Implemented (Fresh Analysis Thread Isolation)` |
| ~~P0~~ | ~~`TASK-BCK-054`~~ | None | ~~Restore live `/api/v1/coherence/evaluate` by reconciling the tracing wrapper with the actual `CoherenceGraphState` tenant contract; current Swagger call fails with `AttributeError: 'CoherenceGraphState' object has no attribute 'tenant_id'`.~~ `[x] Implemented (Coherence Tracing Contract + Fail-Open Telemetry)` |
| ~~P0~~ | ~~`TASK-BCK-055`~~ | None | ~~Replace fake project-level bulk WBS creation with real persistence or align retrieval contract; current Swagger flow returns `201 created_count=4` from `/api/v1/projects/{project_id}/wbs/bulk` but `/api/v1/projects/{project_id}/wbs` immediately returns `items=[]`, `total_items=0`.~~ `[x] Implemented (Persisted bulk WBS writes + hierarchy preservation)` |
| ~~P0~~ | ~~`TASK-BCK-060`~~ | `TASK-BCK-055` | ~~Reconcile `/api/v1/projects/{project_id}/wbs` with its published contract: live route currently returns a flat list plus `total_items`, while Swagger promises hierarchy + coverage and the router even computes a tree then discards it.~~ `[x] Implemented (Project WBS hierarchy + coverage response)` |
| P1 | `TASK-BCK-063` | None | Persist `parsed_at` when document parsing succeeds: live `GET /api/v1/documents/{document_id}` returns `upload_status="parsed"` with `parsed_at=null`, and the parse use case still contains a placeholder comment instead of a real timestamp update. |
| P0 | `TASK-BCK-064` | `TASK-BCK-062` | Reconcile schedule ingestion with coherence scoring: after a live schedule upload parses successfully and creates WBS items, `/api/v1/coherence/evaluate/diagnostics` still reports `score_missing_dimensions=["schedule"]`, so schedule evidence is not yet contributing to the coherence model. |
| ~~P1~~ | ~~`TASK-BCK-065`~~ | None | ~~Harden RAG answer failure handling: live `POST /api/v1/projects/{project_id}/rag/answer` leaks upstream OpenAI embeddings `429 Too Many Requests` as HTTP `500` with traceback instead of a controlled retryable API response.~~ `[x] Implemented (provider 429 maps to clean retryable 503 JSON; document_id used as project_id returns tenant-scoped 404 before embeddings)` |
| ~~P1~~ | ~~`TASK-BCK-066`~~ | None | ~~Reconcile `/api/v1/observability/status` auth/OpenAPI contract: the route has no auth dependency so Swagger omits `Authorization`, but global middleware still requires authentication, causing live Swagger calls to return `401` even with a valid authorized session.~~ `[x] Implemented (private observability routes now expose bearer auth in OpenAPI; live `/status` and `/analyses` both return 200 with authenticated requests)` |
| ~~P0~~ | ~~`TASK-BCK-067`~~ | `TASK-BCK-062` | ~~Make schedule document parsing idempotent for schedule-derived activity projections: re-parsing the same Excel schedule tried to insert duplicate generated activity code `1.0` into `procurement_wbs_items`, violating `uq_procurement_wbs_project_code` and surfacing as HTTP `500`.~~ `[x] Implemented (same-source schedule-derived activities update instead of duplicate; live reparse returned 202)` |
| ~~P1~~ | ~~`TASK-BCK-068`~~ | `TASK-BCK-065` | ~~Restore RAG answer completion after provider credit by removing stale `match_documents` dependency, ingesting parsed Excel schedule rows into `document_chunks`, making LangSmith tracing fail open, and returning an extractive schedule end-date answer when the configured Anthropic model is unavailable.~~ `[x] Implemented (tenant-scoped direct RAG retrieval + schedule chunk ingestion + extractive schedule fallback; live 200 returned 2015-01-02)` |
| ~~P1~~ | ~~`TASK-BCK-069`~~ | `TASK-BCK-068` | ~~Extend RAG answer resilience for non-date schedule questions: live equipment-purchase question still leaked Anthropic model `404` as HTTP `500` because only schedule end-date fallback was deterministic.~~ `[x] Implemented (equipment extractive fallback + LLM generation failure maps to retryable 503 when no deterministic answer exists; live 200 returned two transformer items)` |
| ~~P1~~ | ~~`TASK-BCK-070`~~ | `TASK-BCK-068` | ~~Ingest parsed contract clause payloads into project RAG chunks: live Swagger penalty question returned 200 but only schedule sources because contract `f6543818-b7a6-4357-8f48-43238a4f8a65` had 210 clauses and zero `document_chunks`.~~ `[x] Implemented (contract clause payloads, generic text payloads, and existing text_blocks now normalize to RAG text; unit proof TS-UD-RAG-ERR-002 green)` |
| ~~P1~~ | ~~`TASK-BCK-071`~~ | `TASK-BCK-070` | ~~Improve RAG penalty answer fallback: live Swagger retrieved contract sources for liquidated damages but answered `No lo encuentro en el documento` despite evidence for `recover damages` and `decrease in the Contract Price`.~~ `[x] Implemented (if the LLM abstains, deterministic damages fallback summarizes retrieved contract damages evidence; unit proof TS-UD-RAG-ERR-003 green)` |
| ~~P1~~ | ~~`TASK-BCK-072`~~ | None | ~~Expose bearer auth in OpenAPI for protected alerts routes: live Swagger `GET /api/v1/alerts/projects/{project_id}` generated curl without `Authorization` and returned `401 missing_or_invalid_token`.~~ `[x] Implemented (alerts routers advertise HTTPBearer so Swagger sends bearer tokens; TS-I12-ALERTS-HTTP-001 green)` |
| ~~P0~~ | ~~`TASK-BCK-073`~~ | None | ~~Fix `/api/v1/analysis/analyze` functional failure where `risk_extraction` and `wbs_extraction` tools returned failed results because `BaseTool` called `_execute_impl(..., tenant_id=...)` but tool implementations named the parameter `_tenant_id`.~~ `[x] Implemented (AI tool execution contract restored; TS-QA-SWAGGER-ANALYSIS-001 green)` |
| ~~P0~~ | ~~`TASK-BCK-074`~~ | `TASK-BCK-073` | ~~Repair the Analysis ⇄ HITL seam after Swagger showed extracted risks but `analysis_id=null`, `Automatic critique inconclusive`, and auto-approved HITL rows that still interrupted before persistence.~~ `[x] Implemented (critique cost-controller tenant-session path + HITL auto-approved continuation + resume invokes LangGraph; TS-QA-SWAGGER-ANALYSIS-002 green)` |
| ~~P0~~ | ~~`TASK-BCK-075`~~ | None | ~~Repair API startup failure from split Alembic heads after main sync; Docker startup failed with `Multiple head revisions are present for given argument 'head'`.~~ `[x] Implemented (Alembic merge revision 20260524_0001; TS-QA-SWAGGER-MIGRATION-001 green)` |
| ~~P0~~ | ~~`TASK-BCK-076`~~ | `TASK-BCK-074` | ~~Repair API startup failure from LangGraph reserved channel `checkpoint_id` after HITL seam fix.~~ `[x] Implemented (removed reserved checkpoint_id from ProjectState; compile regression green)` |
| ~~P0~~ | ~~`TASK-BCK-061`~~ | None | ~~Restore local document uploads by reconciling database migration state with the tenant-hardened document repository; live Swagger `POST /api/v1/projects/{project_id}/documents` failed with `UndefinedColumnError: column documents.tenant_id does not exist` while code expected direct `tenant_id` and migration `20260517_0002` existed but the running DB remained at `20260510_0001`.~~ `[x] Implemented (Applied pending migrations; live schedule upload restored)` |
| ~~P0~~ | ~~`TASK-BCK-062`~~ | None | ~~Make Excel schedule parsing production-credible~~ `[x] Implemented` — live real schedule upload now parses from a title sheet with the actual header on row 10 and Spanish columns (`Actividad`, `Inicio`, `Fin`); malformed sheet shape is handled without HTTP `500`, parsed WBS codes are preserved, and WBS level is inferred before persistence. Verified live on 2026-05-17 via `POST /api/v1/documents/f04d4f22-684f-4874-b93b-dc5436ef720b/parse -> 202 parsed`. |
| ~~P0~~ | ~~`TASK-BCK-055`~~ | None | ~~Coherence Score™ Structured Extraction Layer~~ `[x] Implemented` — extraction layer runs on every evaluation, populates `clause.data` from clause text via Claude Haiku, caches in `clauses.extracted_entities`. Verified: TECHNICAL score 100→71.5, deterministic findings 8→13, new rules `DET-TEC-BOMBUDGET` + `DET-TEC-SPEC` firing. Second-call latency near-zero (DB cache hits). LEGAL/SCOPE still 100 due to RAG retrieval coverage (not an extraction bug). |
| ~~P1~~ | ~~`TASK-BCK-056`~~ | None | ~~Fix `AnthropicWrapper` calling `anonymize_document()` on wrong service class~~ `[x] Implemented` — swapped to `PiiAnonymizerService` from `core.privacy.anonymizer` which has the correct sync API. |

### Frontend (2 pending)

| Priority | Task ID | Depends On | Description |
| -------- | ------- | ---------- | ----------- |
| ~~P1~~ | ~~`TASK-FRT-045`~~ | Security | ~~Rotate exposed Clerk test credentials~~ `[x] @2026-05-08 — Operator completed.` |
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
- `EPIC-QA-SWAGGER-MANUAL-VERIFICATION` — active 2026-05-17 real Swagger audit across `TASK-QA-214..321`; each task is one unique method + path operation, marked only after a live Swagger execution with outcome notes. Full board: [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md#epic-qa-swagger-manual-verification--real-swagger-endpoint-audit).
- Full detail: [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md).

### Cross-Category

|Status|Priority|ID|Dependency|Task|Source|
|---|---|---|---|---|---|
|[x]|P0|`TASK-OPS-DOCFLOW-003`|`TASK-OPS-DOCFLOW-002`|Restore root lint execution in the worktree; `pnpm lint` starts ESLint and passes on current main/worktree. `[x] Implemented (Tooling Bootstrap Verification)`|`blackboard/coverage-gates/REAL-DOCUMENT-OPERABILITY-SPEC-PLAN.md`|
|[x]|P0|`TASK-OPS-DOCFLOW-004`|`TASK-OPS-DOCFLOW-003`|Define the sanitized real document corpus manifest and first inventory of real PDF/DOCX/TXT fixtures. `[x] Implemented (Manifest + Real Fixture Inventory)`|`blackboard/coverage-gates/REAL-DOCUMENT-OPERABILITY-SPEC-PLAN.md`|
|[x]|P0|`TASK-OPS-DOCFLOW-005`|`TASK-OPS-DOCFLOW-004`|Add backend integration spec for real document upload and tenant-safe persistence/storage metadata. `[x] Implemented (Real Upload + Persistence Contract)`|`blackboard/coverage-gates/REAL-DOCUMENT-OPERABILITY-SPEC-PLAN.md`|
|[x]|P0|`TASK-OPS-DOCFLOW-006`|`TASK-OPS-DOCFLOW-005`|Add backend integration spec for real parsing and anonymization before AI analysis. `[x] Implemented (Real Parsing + Anonymization Contract)`|`blackboard/coverage-gates/REAL-DOCUMENT-OPERABILITY-SPEC-PLAN.md`|
|[x]|P0|`TASK-OPS-DOCFLOW-007`|`TASK-OPS-DOCFLOW-006`|Add backend integration spec for real extraction outputs: clauses, risks, and expected categories. `[x] Implemented (Real Clause/Risk/WBS Extraction Contract)`|`blackboard/coverage-gates/REAL-DOCUMENT-OPERABILITY-SPEC-PLAN.md`|
|[x]|P0|`TASK-OPS-DOCFLOW-008`|`TASK-OPS-DOCFLOW-007`|Add backend integration spec for real coherence score, score reason/version, missing-dimension semantics, and alerts. `[x] Implemented (Real Coherence Score + Alerts Contract)`|`blackboard/coverage-gates/REAL-DOCUMENT-OPERABILITY-SPEC-PLAN.md`|
|[x]|P1|`TASK-OPS-DOCFLOW-009`|`TASK-OPS-DOCFLOW-008`|Add authenticated API retrieval contract for processed document, coherence result, and project alerts with tenant isolation. `[x] Implemented (Tenant-Scoped API Retrieval Contract)`|`blackboard/coverage-gates/REAL-DOCUMENT-OPERABILITY-SPEC-PLAN.md`|
|[x]|P1|`TASK-OPS-DOCFLOW-010`|`TASK-OPS-DOCFLOW-009`|Add frontend display spec for real backend-shaped coherence and alerts payloads. `[x] Implemented (Frontend Real Output Display Contract)`|`blackboard/coverage-gates/REAL-DOCUMENT-OPERABILITY-SPEC-PLAN.md`|
|[x]|P1|`TASK-OPS-DOCFLOW-011`|`TASK-OPS-DOCFLOW-008`|Add golden regression spec for structured real-document outputs using score ranges and alert category/severity assertions. `[x] Implemented (Real-Document Golden Regression Contract)`|`blackboard/coverage-gates/REAL-DOCUMENT-OPERABILITY-SPEC-PLAN.md`|
|[x]|P1|`TASK-OPS-DOCFLOW-012`|`TASK-OPS-DOCFLOW-009,TASK-OPS-DOCFLOW-010,TASK-OPS-DOCFLOW-011`|Add CI quality gate for real document flow plus coverage, lint, and full backend-suite evidence or approved blocker tracking. `[x] Implemented (CI Gate + Blocker Tracking)`|`blackboard/coverage-gates/REAL-DOCUMENT-OPERABILITY-SPEC-PLAN.md`|
|[x]|P1|`TASK-OPS-DOCFLOW-013`|`TASK-OPS-DOCFLOW-012`|Fix INF coverage blocker: align HITL checkpoint metric label contract and raise scoped observability/resilience/security coverage gate to `>=70%`. `[x] Implemented (INF Coverage Gate Restored)`|`TASK-OPS-DOCFLOW-012 local verification`|
|[x]|P1|`TASK-OPS-DOCFLOW-014`|`TASK-OPS-DOCFLOW-012`|Fix full backend suite collection blocker: restore `golden.evaluators` imports or migrate `tests/golden` fixtures to the current golden corpus package. `[x] Implemented (Golden Package Collection Restored)`|`TASK-OPS-DOCFLOW-012 local verification`|
|[x]|P1|`TASK-OPS-DOCFLOW-015`|`TASK-OPS-DOCFLOW-014`|Fix full backend suite dependency blocker: install or gate the Schemathesis contract suite dependency so `tests/contract/schemathesis/*` can collect in local and CI environments. `[x] Implemented (Schemathesis Dependency Restored)`|`TASK-OPS-DOCFLOW-014 local verification`|
|[x]|P1|`TASK-OPS-DOCFLOW-016`|`TASK-OPS-DOCFLOW-014`|Fix stale full-suite legacy contract imports for relocated alert and procurement router APIs, including `src.alerts.router` and `get_bom_repository` import paths. `[x] Implemented (Legacy Contract Imports Migrated)`|`TASK-OPS-DOCFLOW-014 local verification`|
|[x]|P1|`TASK-OPS-DOCFLOW-017`|`TASK-OPS-DOCFLOW-016`|Fix full-suite Schemathesis no-match contract: update `tests/contract/schemathesis/test_observability_admin_router.py` frontend-support selection so every parametrized contract maps to current OpenAPI operations. `[x] Implemented (Frontend-support tag selector)`|`TASK-OPS-DOCFLOW-016 local verification`|
|[x]|P1|`TASK-OPS-DOCFLOW-018`|`TASK-OPS-DOCFLOW-017`|Fix DB-backed alert API contract execution drift: align `tests/core/test_alerts_router_contract.py` fixtures/routes with current active alerts router and required `alerts.tenant_id` persistence contract. `[x] Implemented (Tenant-hardened alert contract fixtures)`|`TASK-OPS-DOCFLOW-016 local verification`|
|[x]|P1|`TASK-FRT-171`|None|Keep project overview usable when the alerts subrequest fails after production schema drift. `[x] Implemented (Partial Failure Resilience)`|Production report 2026-05-15|

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

### Coherence v2 (EPIC-ECOA-V2-HOTFIX-AND-CUTOVER, 2026-05-26)

> Spec: `docs/superpowers/specs/2026-05-25-ecoa-v2-hotfix-and-cutover-design.md` · Plan: `docs/superpowers/plans/2026-05-25-ecoa-v2-hotfix-and-cutover.md`. Inline detail: `backlogs/BCK_BACKEND.md` §2 (TASK-COH-V2-*).

| Priority | Task ID | Depends On | Description |
| -------- | ------- | ---------- | ----------- |
| P0 | `[ ] TASK-COH-V2-HOTFIX-001` | None | v1 scoring §14 active-weight guard + drop `mean × coverage_ratio` collapse in `apps/api/src/coherence/scoring.py:397-400` + propagate `score_reason` end-to-end through router and DTOs. Widen `DashboardSummary.global_score`/`coherence_score` to `float \| None`. Branch `fix/coherence-v1-active-weight-guard`. |
| P0 | `[ ] TASK-COH-V2-ADAPTER-002` | `TASK-COH-V2-HOTFIX-001` | Fix `apps/api/src/coherence/adapters/v1_to_v2.py:65-96` partial-coverage branch: classify null `sub_scores` as `CategoryStatus.INSUFFICIENT_EVIDENCE`, compute real `active_weight` from `DEFAULT_CATEGORY_WEIGHTS`, apply §14 guard. Ships in HOTFIX-001 PR. |
| P0 | `[ ] TASK-COH-V2-FRONTEND-003` | `TASK-COH-V2-HOTFIX-001` | Frontend null-safe rendering of Coherence Score per ADR-009 §18: remove `?? 0` / `\|\| 0` on all score paths; null → "Pending evidence" neutral state. Vitest + Playwright E2E. Branch `feat/coherence-frontend-null-safe`. No UI flag. |
| P0 | `[ ] TASK-COH-V2-VERSIONING-006` | `TASK-COH-V2-HOTFIX-001` | Mandatory `score_version` on every surface (DB, DTO, telemetry, shadow logs, exports, cache keys, analytics) — canonical 2-value enum `"coherence-v1"`/`"coherence-v2"`. Alembic backfill of NULL + `"v0_flag_based"` + `"v1_exponential_decay"` → `"coherence-v1"`. CI contract test. Branch `feat/coherence-score-version-canonical`. |
| P0 | `[ ] TASK-COH-V2-CACHING-007` | `TASK-COH-V2-VERSIONING-006` | New `apps/api/src/coherence/cache_keys.py` single source of truth; namespaces `coherence:v1:*` / `coherence:v2:*`; lint ban on ad-hoc `f"coherence:..."` literals; one-shot purge script `apps/api/scripts/invalidate_coherence_cache.py` at Phase A deploy; flag-flip invalidation handler. Branch `feat/coherence-cache-namespacing`. |
| P1 | `[ ] TASK-COH-V2-DOCS-005` | `TASK-COH-V2-HOTFIX-001` | Rename malformed `worktrees/sentry-perf/w5b-benchmarks/docs/architecture/adr/ADR-009-` → `ADR-009-evidence-oriented-coherence-orchestration.md`; status `Proposed` → `Accepted` with date; regenerate `docs/api/openapi.yaml` via `make openapi`; update codemap. Branch `docs/coherence-adr-009-accepted`. |
| P1 | `[ ] TASK-COH-V2-CUTOVER-004` | `-001 -003 -006 -007` | Make ECOA v2 authoritative behind per-tenant flag. D.0 audit verdict: **EXISTS_PARTIAL** — extend `Tenant.settings: JSONB` at `apps/api/src/core/auth/models.py:100` (alerts pattern at `apps/api/src/alerts/adapters/persistence/tenant_repository.py`); extract shared `apps/api/src/core/feature_flags/tenant_flags_service.py`; remove `apps/api/src/config.py:319` "Per-tenant override is deferred" comment. Canary 10→50→100% over 3 days with shadow-MAE ≤ 15 auto-block. Branches `feat/coherence-v2-authoritative-canary` (D.0) then `feat/coherence-v2-authoritative` (D.1+). |

- 2026-05-17 — Added TASK-BCK-060 (Honest Coherence Scoring): ApplicabilityState + coverage_map + HeuristicBaselineProvider + coverage-penalized scoring + three-state CategoryBreakdown. Removes fabricated 100/0 subcategory scores. Implemented on branch feat/honest-coherence-scoring, 104 coherence tests green.

- 2026-05-24 — **EPIC-ECOA-V2 (ADR-009 Phase 1 + Phase 2) — implemented on branch `claude/ecoa-v2-phase1-phase2-BHSq5`.** Locked the ADR-009 v2 contract with TRI terminology (`technical_reliability_index`, `evidence_coverage`, `evidence_freshness`, `score_explanation`, `active_weight`). Added 11 new backend modules: `coherence_v2_dtos.py` (nullable Pydantic v2 contract with model_validator forbidding `coherence_score` on no-evidence states), `v2_constants.py` (six-category thresholds, severity multipliers, `MIN_ACTIVE_WEIGHT = 0.35`, equal weights), `category_state_machine.py` (deterministic 6-state machine), `services/v2/{evidence_service, conflict_service, category_aggregator, aggregator_v2, orchestrator, shadow_runner}.py`, `adapters/v1_to_v2.py`, `calculate_v2_from_signals` in `scoring.py` (additive — v0.3 path untouched), `RuleExecutionTrace` + `coherence.rule_default_100_used` warning telemetry on the deprecated v0 engine. Wired the additive `categories_v2` field on `DashboardSummary`; v1 byte-equivalent when `coherence_v2_enabled=False`. Shadow Mode emits `coherence.shadow.delta` structlog events (no DB table — deferred to Phase 3). Frontend: `lib/api/contracts.ts` now exports `CategoryStatus`, `CategoryV2`, `GlobalV2`, `CoherenceV2Payload`; `DashboardClient.tsx:129` `?? 0` replaced by `<CoherenceEmptyState>` empty-state render; new `CategoryStatusBadge.tsx` honors the ADR color contract (red reserved for `conflicting_evidence` only); MSW handler accepts `?cohV2Scenario=excellent|insufficient|conflict`; `ScoreVersionBadge` learns `v2_evidence_aware`. Tests: 68 new backend tests (`tests/coherence/test_{v2_dtos,v2_constants,category_state_machine,category_aggregator,aggregator_v2,scoring_v2,rules_engine_trace,v1_to_v2_adapter,v2_feature_flag,shadow_runner,shadow_mae_guardrail,orchestrator_v2,router_v2_field}.py`) all pass with `pytest --noconftest`; 3 new frontend test files + 2 extended (`DashboardClient.test.tsx`, `CategoryStatusBadge.test.tsx`, `CoherenceEmptyState.test.tsx`) — 24 web coherence tests pass; full TS typecheck zero errors. Settings: `coherence_v2_enabled: bool = False`, `coherence_v2_shadow_mode: bool = True` (env aliases `COHERENCE_V2_ENABLED` / `COHERENCE_V2_SHADOW_MODE`). MAE guardrail asserts `mae ≤ 15` against `tests/coherence/calibration_dataset/project_excellent.json`. **Phase 3 (rollout) is deferred per ADR-009 §7.2 — gated on Shadow Mode telemetry.**

**2026-05-07**: TASK-AI-038 verified complete (python_mcp_server.md already correct). TASK-AI-039 implemented as validate_prompt_templates.py CLI (commit 71f717c8). AI backlog: 89 completed / 9 active.

**2026-05-08**: TASK-BCK-041 complete — ruff ARG/SIM noqa pass; src/ 0 violations (commit dab24151). 29 ARG + 7 SIM/F violations suppressed with # noqa across 22 files in apps/api/src/. TASK-BCK-020 closed (all 6 doc adapter issues resolved 2026-03-28 per docs/TEST_COVERAGE_ISSUES_REPORT.md). TASK-BCK-040 closed (ruff 257→0 violations, target <50 exceeded). TASK-AI-003 closed — operator created LangSmith org + API keys, .env updated. TASK-FRT-045 closed — operator rotated Clerk test credentials. TASK-INF-015 closed — FlashCacheService already fully implemented in prompt_cache.py. TASK-INF-014 deferred [~] — requires LangSmith production data (4-6 weeks).

**2026-05-26**: Added **EPIC-ECOA-V2-HOTFIX-AND-CUTOVER** — 7 tasks (`TASK-COH-V2-HOTFIX-001` through `-CUTOVER-004`) covering trademark-critical Coherence Score™ fix and v1→v2 cutover. Bug repro: SCOPE-only project returns `overall_score=15` instead of `null` per ADR-009 §14. Phase D.0 audit complete: reuse `Tenant.settings: JSONB` (alerts pattern), do not build new infra. Decisions locked: widen score fields to `float \| None`, blind backfill legacy `score_version` → `"coherence-v1"`, OpenAPI minor bump, MCP grep clean (zero consumers). Spec + plan at `docs/superpowers/{specs,plans}/2026-05-25-ecoa-v2-hotfix-and-cutover*.md`. **No pushes to `main`** for any task in this epic.

---

