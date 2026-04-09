# Planning Backlog

## 1. Scope

Planner coordination notes and cross-role execution waves derived from the current audited backlog state.

## 0. Status View

**Completed Planning Deliverables**

- 2026-04-08 cross-category execution plan written to this file
- Role-by-role execution waves synchronized into `blackboard.json`

**Pending Planning Follow-On**

- Replan after Wave 1 closes `TASK-LINT-001`, `TASK-LINT-002`, `TASK-ARCH-005`, and `TASK-ARCH-006`
- Normalize a dedicated execution backlog ID for the Alembic hotfix discovered by `TASK-REV-INFRA-001`

## 2. Specifications

### 2026-04-08 Cross-Category Execution Plan

|Wave|Role|Backlog ID|Priority|Depends On|Definition of Done|
|---|---|---|---|---|---|
|Wave 1|reviewer|`TASK-LINT-001`|P0|None|Reconcile the legacy ARG audit entry with the completed 235-hit audit so downstream lint work uses one authoritative classification.|
|Wave 1|backend|`TASK-LINT-002`|P0|`TASK-LINT-001`|Fix the five bucket-A production ARG issues with RED/GREEN tests and reduce ARG002 noise on the touched production files.|
|Wave 1|reviewer|`TASK-ARCH-005`|P1|None|Audit all remaining "aspirational architecture" tenant propagation cases and produce a fix list for execution.|
|Wave 1|backend|`TASK-ARCH-006`|P1|`TASK-ARCH-005`|Propagate or enforce `tenant_id` in the affected use cases and repositories with tests proving no regression.|
|Wave 2|ai|`TASK-BCK-031`|P0|`TASK-BCK-024`|Restore LangGraph checkpoints end-to-end so HITL resume can continue from saved workflow state.|
|Wave 2|ai|`TASK-BCK-027`|P0|`TASK-BCK-031`|Reconcile the active LangGraph pipeline with the reviewed orchestration boundaries by extracting node logic and eliminating remaining framework-coupled orchestration drift.|
|Wave 2|frontend|`TASK-FRT-167`|P2|`TASK-BCK-031`|Ship the HITL resume UI with restore, approve/reject, history, and delivery-status coverage.|
|Wave 2|qa|`TASK-QA-100`|P2|`TASK-BCK-031`, `TASK-FRT-167`|Validate resumed HITL workflow state, approval/rejection behavior, audit trail, and duplicate-notification prevention.|
|Wave 2|qa|`TASK-QA-101`|P2|`TASK-BCK-031`|Cover LangGraph checkpoint save/restore, persistence, and recovery paths to >=80% on adapter modules.|
|Wave 3|backend|`TASK-BCK-028`|P0|`TASK-BCK-026`, `TASK-BCK-027`|Deliver a runnable document-to-alerts E2E suite that exercises the real pipeline instead of contract-only stubs.|
|Wave 3|frontend|`TASK-FRT-166`|P1|`TASK-BCK-028`|Add Playwright coverage for the complete upload → analysis → alert → HITL flow with happy-path and error-path assertions.|
|Wave 3|security|`TASK-FRT-045`|P1|None|Rotate exposed Clerk test credentials, revoke old keys, and confirm sanitized developer onboarding flow.|
|Wave 3|infra|`TASK-INF-049`|P1|None|Complete the documents-module hexagonal migration without breaking current verification suites.|
|Wave 4|devops|`TASK-AI-031`|P1|`TASK-216`|Deploy tracing changes to staging and verify LangSmith traces appear with the expected metadata.|

### Blocker Notes

- `TASK-FRT-167`, `TASK-QA-100`, and `TASK-QA-101` remain blocked until `TASK-BCK-031` is complete.
- `TASK-BCK-027` should start immediately after `TASK-BCK-031`; the AI audit already confirmed the duplicate orchestration root cause is resolved, but node-level logic leakage still needs execution work.
- `TASK-FRT-166` remains blocked until `TASK-BCK-028` delivers a stable end-to-end backend path.
- `TASK-AI-031` is blocked by `TASK-216` and the earlier LangSmith enablement tasks.
- `TASK-BCK-028` should not start before the alert/orchestration work in `TASK-BCK-026` and `TASK-BCK-027` is reconciled.
- `TASK-REV-INFRA-001` produced a concrete Alembic linearization remediation, but the repo does not yet expose a normalized execution backlog ID for that hotfix. Treat it as the first role_infra hotfix before any new migration authoring.
