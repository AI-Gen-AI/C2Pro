# Backend Tasks & Knowledge Base

**Category**: Backend (BCK)
**Owner Role**: backend
**Last Updated**: 2026-05-08

**Quick Links**:

- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_backend.md)

---

## 0. Status View

**Pending Tasks**: 5

**Completed Tasks**: 49

- IDs: `TASK-BCK-001`–`TASK-BCK-033`, `TASK-BCK-035`–`TASK-BCK-049`

> Active production follow-ups are tracked below. Detailed completed-task history and specifications remain archived in [COMPLETED.md](./COMPLETED.md).

---

## 1. Active Tasks

| Status | Priority | Task ID | Depends On | Description | Source |
| ------ | -------- | ------- | ---------- | ----------- | ------ |
| [ ] | P0 | `TASK-BCK-051` | None | Investigate live `500` responses on project alerts and project stakeholders by correlating production error reference IDs with backend logs and verifying applied Alembic head/schema parity for tenant-hardened tables. Railway logs at `2026-05-16T18:20:52Z` now confirm project-alert reads fail with `UndefinedColumnError: column alerts.related_clause_ids does not exist`, proving `20260516_0001` did not fully restore live alerts parity. | Production report 2026-05-15 |
| [ ] | P1 | `TASK-BCK-052` | `TASK-BCK-051` | Verify backend production error capture into Sentry after the live-500 incident: prove that an unhandled backend exception reaches the `c2pro` Sentry project with expected environment/release tags, or document and repair the observability gap. | `TASK-BCK-051 live triage 2026-05-16` |
| [ ] | P0 | `TASK-BCK-053` | None | Investigate live `500` on project document upload observed at `2026-05-16T18:06:14Z` with reference ID `ae928e97-224f-4b17-8f2c-f315823281a9`; Railway logs at `2026-05-16T21:35:46Z` now confirm a separate enum drift incident: production `documents.document_type` expects `documenttype` while the ORM binds `document_type`. | `Browser error capture + Railway logs 2026-05-16` |
| [ ] | P0 | `TASK-BCK-054` | `TASK-BCK-051` | Complete the alerts production-drift repair with a new forward revision `20260516_0002` that adds the missing `alerts.related_clause_ids` column, then redeploy/apply the live schema fix before retesting the project alerts route. | `TASK-BCK-051 Railway logs 2026-05-16` |
| [ ] | P0 | `TASK-BCK-055` | `TASK-BCK-053` | Repair document upload enum drift with a forward migration that normalizes live `documents.document_type` from legacy PostgreSQL enum `documenttype` to canonical `document_type`, then redeploy/retest the upload route. | `TASK-BCK-053 Railway logs 2026-05-16` |

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
| `TASK-BCK-052` | Production Sentry backend capture verification         | Pending       |
| `TASK-BCK-053` | Production document upload 500 triage                  | Pending       |
| `TASK-BCK-054` | Complete alerts production drift repair                | Pending       |
| `TASK-BCK-055` | Repair document upload enum drift                     | Pending       |
