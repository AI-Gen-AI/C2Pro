# Backend Tasks & Knowledge Base

**Category**: Backend (BCK)
**Owner Role**: backend
**Last Updated**: 2026-05-17

**Quick Links**:

- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_backend.md)

---

## 0. Status View

**Pending Tasks**: 1

**Completed Tasks**: 51

- IDs: `TASK-BCK-001`–`TASK-BCK-033`, `TASK-BCK-035`–`TASK-BCK-049`, `TASK-BCK-052`–`TASK-BCK-054`

> Active runtime defects are tracked below; completed history remains archived in [COMPLETED.md](./COMPLETED.md).

---

## 1. Active Tasks

| Status | Priority | Task ID | Depends On | Description | Source |
| ------ | -------- | ------- | ---------- | ----------- | ------ |
| [ ] | P0 | `TASK-BCK-051` | None | Investigate live `500` responses on project alerts and project stakeholders by correlating production error reference IDs with backend logs and verifying applied Alembic head/schema parity for tenant-hardened tables. Live drift repaired 2026-05-16 through `20260516_0001`; remaining blocker is unavailable production log access for reference-ID correlation. | Production report 2026-05-15 |
| [x] | P0 | `TASK-BCK-052` | None | Fix `/api/v1/analysis/analyze` LangGraph `InvalidUpdateError` caused by duplicated parallel fan-out/join writes to shared keys such as `project_id` after successful parsing. `[x] Implemented (True Multi-Source Fan-In + Branch State Isolation)` | Swagger verification 2026-05-17 |
| [x] | P1 | `TASK-BCK-053` | None | Stop fresh `/api/v1/analysis/analyze` requests from reusing project-level LangGraph checkpoint threads and replaying prior workflow messages into later analyses. `[x] Implemented (Fresh Analysis Thread Isolation)` | Swagger verification 2026-05-17 |
| [x] | P0 | `TASK-BCK-054` | None | Restore live `/api/v1/coherence/evaluate` by fixing the tracing/state contract mismatch, satisfying the current LangSmith SDK `inputs` contract, and making coherence telemetry fail open instead of blocking scoring. `[x] Implemented (Coherence Tracing Contract + Fail-Open Telemetry)` | Swagger verification 2026-05-17 |
| [x] | P0 | `TASK-BCK-055` | None | Coherence Score™ Structured Extraction Layer — complete. `clause_extractor.py` (combined schema, UUID-safe DB cache, `_load_cache()` validity check requiring at least one `_ALL_REQUIRED_KEYS` field), integrated into `prepare_context` in `nodes.py`. Cache check bug fixed: ingestion metadata `{source, category, affected_categories}` was treated as a cache hit; fixed to require real extracted field. Verified: extraction now fires Haiku LLM calls and enriches `clause.data`. `deterministic_findings_count` rose from 8 → 31. | 2026-05-17 |
| [x] | P1 | `TASK-BCK-056` | None | Fix `AnthropicWrapper` calling `self.anonymizer_service.anonymize_document()` on `AnonymizationService` (wrong API). Swapped to `PiiAnonymizerService` from `core.privacy.anonymizer` which has the correct `anonymize_document()` sync API returning `AnonymizedResult` with `.mapping` and `.anonymized_text`. | 2026-05-17 |
| [x] | P1 | `TASK-BCK-057` | BCK-055 | Category-targeted RAG retrieval: replaced `ORDER BY created_at LIMIT 50` with 6 keyword-filtered SQL queries (10 clauses per category: LEGAL/TIME/BUDGET/TECHNICAL/QUALITY/SCOPE). Penalty, warranty, notice, and deliverable clauses previously invisible now surface. `deterministic_findings_count` 13 → 31. | 2026-05-17 |
| [x] | P1 | `TASK-BCK-058` | BCK-055 | DET-TIM-STATUS false positive guard: rule was firing 7 times on payment/price clauses because ingestion stamped `status: at_risk` on non-TIME clauses. Added `infer_category(clause) not in ("TIME", "SCHEDULE")` guard. Moved `infer_category` + `CATEGORY_KEYWORDS` to `rules_engine/category_utils.py` to break circular import. Schedule category score: 65 → 100. | 2026-05-17 |
| [x] | P1 | `TASK-BCK-059` | BCK-058 | DET-TEC-SPEC / DET-QUA-STANDARD / DET-QUA-INSPECT false positive guards: DET-TEC-SPEC was firing 25 times (preamble, party names, payment terms) because it checked `clause.data.get("category")` ingestion metadata. Replaced with `infer_category(clause) != "TECHNICAL"` guard. DET-QUA-STANDARD and DET-QUA-INSPECT got `infer_category not in ("QUALITY","TECHNICAL")` guards. Test clauses updated to use unambiguous keyword-rich text. | 2026-05-17 |

## 2. Specifications

### TASK-BCK-054 — Coherence tracing/state contract repair

- Live cause: `traced_coherence_node()` dereferences `state.tenant_id`, but `CoherenceGraphState` has no direct `tenant_id` field; tenant identity currently lives in `state.config.tenant_id`.
- Why it matters: every coherence node wrapped by tracing can fail before business logic runs, so `/api/v1/coherence/evaluate` is not operable even when request data is valid.
- Chosen repair: preserve one canonical tenant source on `CoherenceGraphState` by exposing a read-only `tenant_id` accessor that delegates to `config.tenant_id`; this keeps observability code simple while avoiding duplicate mutable tenant state.
- Acceptance:
  1. tracing can read tenant/project metadata from a real `CoherenceGraphState`;
  2. the core coherence endpoint returns `200` in Swagger for the current parsed project;
  3. no tenant-filtering or graph behavior is weakened.
- Follow-on defect found during real verification: after the state accessor fix, live execution advanced to a second `500` because `LangSmithClient.start_span()` no longer satisfied the installed SDK signature (`Client.create_run()` requires `inputs`).
- Final repair shape:
  1. expose read-only `CoherenceGraphState.tenant_id -> config.tenant_id`;
  2. pass `inputs={}` when creating LangSmith spans;
  3. make span start/update/end telemetry fail open so observability cannot take down coherence evaluation.

---

## 2. Completed Task IDs (summary)

| Task ID        | Description                                              | Completed     |
| -------------- | -------------------------------------------------------- | ------------- |
| `TASK-BCK-001` | Dependencies injected via FastAPI / service constructors | 2026-04-04    |
| `TASK-BCK-002` | Retire legacy `app/dashboard/`                           | 2026-02-19    |
| `TASK-BCK-003` | Remove `_Default*Service` dummy implementations          | 2026-02-19    |
| `TASK-BCK-004` | LangGraph nodes wrap existing use cases                  | 2026-02-19    |
| `TASK-BCK-005` | HITL real service implementation                         | 2026-02-19    |
| `TASK-BCK-006` | Verifier produces JSON for dashboarding                  | 2026-04-04    |
| `TASK-BCK-007` | Fix Alembic WBS uniqueness migration                     | 2026-04-04    |
| `TASK-BCK-008` | Repair clause-embeddings Alembic revision chain          | 2026-04-04    |
| `TASK-BCK-009` | Fix Railway LangGraph checkpointer psycopg regression    | 2026-04-04    |
| `TASK-BCK-010` | Remove internal constructor fallback wiring              | 2026-02-19    |
| `TASK-BCK-011` | dashboard→app/(app)/ migration plan                      | 2026-04-01    |
| `TASK-BCK-012` | Canonical route parity under app/(app)/                  | 2026-04-01    |
| `TASK-BCK-013` | Preserve /dashboard compatibility                        | 2026-04-01    |
| `TASK-BCK-014` | Retire app/dashboard/                                    | 2026-04-01    |
| `TASK-BCK-015` | Migrate Playwright tests off /dashboard/ paths           | 2026-04-01    |
| `TASK-BCK-016` | Replace canonical route re-exports                       | 2026-04-01    |
| `TASK-BCK-017` | OpenSpec follow-up change creation support               | 2026-04-04    |
| `TASK-BCK-018` | AUTH_BOOTSTRAP_ALLOW_FALLBACK_EMERGENCY config           | 2026-04-07    |
| `TASK-BCK-019` | Prevent Clerk personal-tenant collisions                 | 2026-04-04    |
| `TASK-BCK-020` | Reconcile document adapter contract quality issues       | 2026-05-08    |
| `TASK-BCK-021` | Supabase RLS, composite indexes, pg_stat_statements      | 2026-04-03    |
| `TASK-BCK-022` | Wire TriggerDocumentAnalysisUseCase to Celery            | 2026-04-05    |
| `TASK-BCK-023` | Document update re-trigger flow                          | 2026-04-06    |
| `TASK-BCK-024` | HITL workflow resume mechanism after approval            | 2026-04-06    |
| `TASK-BCK-025` | Real notification delivery (email/Slack/webhook)         | 2026-04-06    |
| `TASK-BCK-026` | Unify AlertGenerator with pipeline save_to_db_node       | 2026-04-06    |
| `TASK-BCK-027` | Reconcile two orchestration systems (deleted unused)     | 2026-04-06    |
| `TASK-BCK-028` | E2E tests for document→LangChain→alerts flow             | 2026-04-06    |
| `TASK-BCK-029` | WBS API endpoint with nested set model                   | 2026-04-06    |
| `TASK-BCK-030` | Authenticated test fixtures for HITL resume tests        | 2026-04-06    |
| `TASK-BCK-031` | LangGraph checkpoint restoration for HITL resume         | 2026-04-06    |
| `TASK-BCK-032` | Monitoring/metrics for workflow resumption               | 2026-04-21    |
| `TASK-BCK-033` | HITL resume API in OpenAPI spec                          | 2026-04-21    |
| `TASK-BCK-035` | Fix duplicate index in Alert model (DuplicateTableError) | 2026-04-06    |
| `TASK-BCK-036` | Fix syntax error in monitoring.py:175                    | 2026-04-06    |
| `TASK-BCK-037` | Update conftest.py for all security models               | 2026-04-06    |
| `TASK-BCK-038` | Implement AIUsageLogORM with schema parity               | 2026-04-06    |
| `TASK-BCK-039` | Gate 4 traceability: sync AuditLogORM                    | 2026-04-06    |
| `TASK-BCK-040` | Ruff linting debt resolution (257→0 violations)          | 2026-05-08    |
| `TASK-BCK-041` | Ruff ARG audit — tenant_id/user_id review                | 2026-05-08    |
| `TASK-BCK-042` | DLQ admin endpoints (GET+POST /api/v1/admin/dlq)         | 2026-04-27    |
| `TASK-BCK-043` | WBS integration tests relocated to tests/integration/    | 2026-04-21    |
| `TASK-BCK-044` | Flaky SLA calculator test fixed with freezegun           | 2026-04-21    |
| `TASK-BCK-045` | Railway alerts import crash (ModuleNotFoundError)        | 2026-04-10    |
| `TASK-BCK-046` | Project status update contract fix                       | 2026-04-11    |
| `TASK-BCK-047` | Document reprocess and status mapping fix                | 2026-04-11    |
| `TASK-BCK-048` | Production alerts route + upload CORS parity             | 2026-04-11    |
| `TASK-BCK-049` | Direct upload Clerk token + error CORS fix               | 2026-04-11    |
| `TASK-BCK-051` | Production alerts/stakeholders 500 triage              | Pending       |
| `TASK-BCK-052` | Analysis graph parallel state merge fix                | 2026-05-17    |
| `TASK-BCK-053` | Fresh analysis checkpoint isolation                    | 2026-05-17    |
| `TASK-BCK-054` | Coherence tracing contract + fail-open telemetry       | 2026-05-17    |
| `TASK-BCK-055` | Coherence structured extraction layer                  | 2026-05-17    |
| `TASK-BCK-056` | AnthropicWrapper anonymizer API mismatch fix           | 2026-05-17    |
| `TASK-BCK-057` | Category-targeted RAG retrieval (6-category SQL)       | 2026-05-17    |
| `TASK-BCK-058` | DET-TIM-STATUS false positive guard                    | 2026-05-17    |
| `TASK-BCK-059` | DET-TEC-SPEC / DET-QUA-* category guards               | 2026-05-17    |
