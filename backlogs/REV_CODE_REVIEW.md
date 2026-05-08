# C2Pro Code Review Backlog

**Purpose**: Track code review findings, architectural violations, and quality issues discovered during audits
**Last Updated**: 2026-05-08
**Owner**: reviewer

---

## Status View

**Pending Tasks**: 0

**Completed Tasks**: 25+

- `TASK-REV-SECURITY-001` — Tenant isolation comprehensive audit
- `TASK-REV-BACKEND-001` — Hexagonal architecture compliance audit
- `TASK-REV-QUALITY-001` — Ruff linting debt classification
- `TASK-REV-QUALITY-002` — Missing ORM models audit
- `TASK-REV-FRONTEND-001` — Integration test failures audit
- `TASK-REV-INFRA-001` — Alembic migration chain audit
- `TASK-REV-AI-001` — LangGraph orchestration audit
- `TASK-LINT-001` — ARG002 legacy scope reconciled
- `TASK-LINT-002` — Bucket-A real bug fixes
- `TASK-LINT-003` — Bucket-C interface-contract `# noqa` / underscore cleanup
- `TASK-LINT-004` — ARG001 FastAPI router/dependency cleanup
- `TASK-LINT-005` — UP007 union syntax backlog drift resolved
- `TASK-LINT-006` — BOM + WBS repository write-path tenant enforcement
- `TASK-ARCH-002` — ARG002 audit across codebase (34 production hits classified)
- `TASK-ARCH-003` — Coherence scoring extraction follow-up
- `TASK-ARCH-005` — Use-case tenant propagation audit
- `TASK-ARCH-006` — Stakeholders + procurement tenant propagation fixes
- `TASK-REV-011`–`TASK-REV-020` — Infrastructure/security audit remediation tasks
- `TASK-IMPL-001`–`TASK-IMPL-023` — Full remediation plan (P0–P3)

> All code review tasks are complete. Detailed audit findings and implementation notes have been archived.
> See [COMPLETED.md](./COMPLETED.md) for the completion record.

---

## 1. Active Tasks

_No pending tasks. All REV tasks completed as of 2026-05-08._

---

## 2. Audit Scorecard (final state)

| Category                   | Final Status |
| -------------------------- | ------------ |
| Tenant Isolation           | ✅ PASS (90%+) |
| Hexagonal Architecture     | ✅ 5/6 modules compliant |
| Ruff Linting (src/)        | ✅ 0 errors |
| Gate 4 Traceability (ORM)  | ✅ PASS |
| Security (auth/bypass)     | ✅ PASS |
| Test Coverage              | ✅ 80%+ |

---

## 3. Key Completed Work (summary)

| Task                  | Outcome                                                                 |
| --------------------- | ----------------------------------------------------------------------- |
| TASK-REV-SECURITY-001 | Tenant isolation audit complete; SEC-001–SEC-008 fixed; BYP-001 fixed  |
| TASK-REV-BACKEND-001  | Hexagonal compliance audit; alerts module fully refactored              |
| TASK-REV-QUALITY-001  | 82 Ruff errors classified into 4 tiers                                  |
| TASK-REV-QUALITY-002  | AIUsageLogORM, ClauseEmbeddingORM, DocumentChunkORM created             |
| TASK-REV-FRONTEND-001 | ERR_INVALID_URL root cause identified; fix proposed                     |
| TASK-REV-INFRA-001    | Alembic chain mapped; RLS gaps documented; orchestration duplication resolved |
| TASK-REV-AI-001       | All 17 LangGraph nodes audited; domain services extracted               |
| TASK-LINT-003         | Bucket-C interface contracts annotated with targeted `# noqa: ARG002`  |
| TASK-ARCH-006         | Stakeholder + RACI + BOM use cases now propagate tenant_id explicitly   |
| TASK-IMPL-001–023     | All P0/P1/P2/P3 remediation tasks executed and verified                 |
