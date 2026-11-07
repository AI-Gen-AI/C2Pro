# P0-E Read-only database bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the existing P0-E planner input from authenticated, tenant-scoped PostgreSQL state without writing anything.

**Architecture:** A SELECT-only SQLAlchemy repository validates authoritative project/artifact/review evidence and maps scoped historical RISK alerts to planner snapshots. A small service invokes the existing planner without changing its matching or fail-closed logic.

**Tech Stack:** Python 3.11, SQLAlchemy async, PostgreSQL, pytest.

**Spec:** `docs/superpowers/specs/2026-11-07-p0e-read-only-db-bridge-design.md`

## Global Constraints

- No writes, migrations, endpoints, LLM calls, or HITL actions.
- Tenant/project/document/revision/artifact scope is revalidated from persisted rows.
- Artifact payload is serialized and digested exactly as `SqlAlchemyDocumentArtifactRepository._insert` does.
- Authority requires active/trusted artifact state and a matching APPROVED review binding.
- Historical alert relevance comes from persisted alert document references, not only `source_artifact_id`.
- Existing planner remains the source of advisory results and `PLAN_BLOCKED` behavior.

## Review Focus

- Cross-tenant selector: project lookup must reject it before artifact disclosure.
- Superseded/proposed artifact: the planner must receive no fabricated trusted authority.
- Missing or mismatched approved review binding: authority must be unavailable.
- Three persisted alerts mapped to two ordered V2 risks: only the exact two can be retained.
- Missing/invalid evidence and dismissed/rejected statuses: require review or preserve the human disposition without mutation.

---

### Task 1: Read boundary and planner service

**Files:**
- Create: `apps/api/src/analysis/application/historical_risk_alert_reconciliation_reader.py`
- Create: `apps/api/src/analysis/adapters/persistence/historical_risk_alert_reconciliation_reader.py`
- Test: `apps/api/tests/unit/analysis/test_historical_risk_alert_reconciliation_reader.py`

**Interfaces:**
- Produces: `HistoricalRiskAlertReconciliationService.plan(scope)` returning the existing `ReconciliationPlan`.
- Consumes: a repository that returns an exact `ReconciliationInput` from persisted scope.

- [ ] Write unit tests for exact advisory delegation, cross-tenant refusal, stale authority block, duplicate risk ambiguity, invalid quote review, and preserved human dispositions.
- [ ] Run unit tests to verify the missing reader service fails.
- [ ] Implement the typed read boundary, SELECT-only mapper, and service delegation.
- [ ] Run unit tests to verify they pass.

### Task 2: PostgreSQL integration coverage

**Files:**
- Test: `apps/api/tests/modules/integration/test_p0e_read_only_db_bridge.py`

**Interfaces:**
- Consumes: the Task 1 service with the real SQLAlchemy repository and existing PG `db` fixture.

- [ ] Write real PostgreSQL data tests for the complete two-of-three advisory report, cross-tenant/stale authority, missing review evidence, duplicate n:1, quote validation, preserved final dispositions, and unchanged rows.
- [ ] Run the integration test to verify it fails before its implementation is complete.
- [ ] Complete only the smallest read mapping required by the failing integration tests.
- [ ] Run focused tests, Ruff, compile, and the relevant project suite.
