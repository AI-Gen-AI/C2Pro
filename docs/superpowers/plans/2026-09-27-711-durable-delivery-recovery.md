# #711 Durable Delivery and Bounded Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guarantee that worker/container loss cannot leave document processing indefinitely stranded and that duplicate delivery cannot duplicate durable effects.

**Architecture:** Apply worker-loss redelivery only after pinning ingestion idempotency. Add a stale-work reconciler that classifies abandoned work and either safely re-enqueues it within a bounded attempt budget or transitions it to an explicit retryable failure. Reuse the normal reprocess route for user recovery.

**Tech Stack:** Celery, Redis, SQLAlchemy/PostgreSQL, pytest.

**Spec:** `docs/superpowers/specs/2026-09-27-issue-706-production-journey-remediation-design.md`

## Global Constraints

- Depends on #710 runtime topology being merged and deployable.
- No infinite `processing` state.
- Recovery is tenant-scoped and idempotent.
- HITL pause is not a processing failure and must never be auto-retried as abandoned analysis.
- No manual SQL repair is part of the product recovery contract.

## Review Focus

- Duplicate Celery delivery after an ACK loss must not duplicate clauses/chunks/analysis/events.
- A real HITL pause must never be swept as stale.
- Misconfiguration must not burn transient retry budget forever.
- Recovery attempt ceiling must transition to a truthful retryable error.
- Reprocess after failure must not resurrect an obsolete document revision.

---

### Task 1: Pin document-processing idempotency

**Files:**
- Modify: `apps/api/src/core/tasks/ingestion_tasks.py`
- Extend tests under: `apps/api/tests/unit/core/tasks/`
- Extend integration tests under: `apps/api/tests/integration/document_flow/`

**Interfaces:**
- `process_document_async(document_id: str, revision_id: str | None) -> dict[str, Any]`
- Existing deterministic analysis thread id `document:{document_id}:analysis`.

- [ ] **Step 1: Add tests that invoke the same document/revision twice and assert no duplicate durable clause/chunk/analysis/event effects**
- [ ] **Step 2: Run the focused tests and capture RED behavior**
- [ ] **Step 3: Add the minimum idempotency guards at each durable seam that currently duplicates**
- [ ] **Step 4: Re-run twice-delivery tests until GREEN**
- [ ] **Step 5: Commit**

Commit message: `fix(ingestion): make document processing redelivery idempotent`

### Task 2: Worker-loss delivery semantics

**Files:**
- Modify: `apps/api/src/core/tasks/ingestion_tasks.py` task decorator/options
- Test: `apps/api/tests/unit/core/tasks/test_ingestion_delivery_contract.py`

**Interfaces:**
- Produces task options equivalent to `acks_late=True` and `reject_on_worker_lost=True` for the ingestion task, or a proven equivalent.

- [ ] **Step 1: Write a test that asserts the ingestion task's worker-loss contract**
- [ ] **Step 2: Verify RED**
- [ ] **Step 3: Enable late acknowledgement/redelivery only for tasks whose idempotency was proven in Task 1**
- [ ] **Step 4: Verify GREEN**
- [ ] **Step 5: Commit**

Commit message: `fix(celery): redeliver ingestion after worker loss`

### Task 3: Stale-work reconciler with bounded attempts

**Files:**
- Create: `apps/api/src/core/tasks/document_recovery.py`
- Modify: `apps/api/src/core/tasks/celery_app.py`
- Modify persistence metadata/state only where required.
- Test: `apps/api/tests/unit/core/tasks/test_document_recovery.py`
- Integration: `apps/api/tests/integration/document_flow/test_worker_loss_recovery.py`

**Interfaces:**
- Produce named task `documents.reconcile_stale_processing`.
- Stale classifier must distinguish active work, HITL pause, retryable abandoned work and exhausted work.

- [ ] **Step 1: Write RED tests for PARSING abandoned, analysis-pending abandoned, HITL-pending excluded, and exhausted-attempt transition**
- [ ] **Step 2: Implement the smallest tenant-safe stale selector and bounded attempt bookkeeping**
- [ ] **Step 3: Add the periodic task to the existing beat schedule**
- [ ] **Step 4: Run unit and integration tests**
- [ ] **Step 5: Commit**

Commit message: `feat(recovery): reconcile abandoned document processing`

### Task 4: Crash simulation acceptance in CI/integration

**Files:**
- Extend: `apps/api/tests/integration/document_flow/test_worker_loss_recovery.py`

- [ ] **Step 1: Add a deterministic fault point after task start but before terminal persistence**
- [ ] **Step 2: Assert redelivery/reconciler leads to one terminal durable result or `FAILED_RETRYABLE`**
- [ ] **Step 3: Assert no duplicate durable effects**
- [ ] **Step 4: Run the full relevant integration suite**
- [ ] **Step 5: Commit**

Commit message: `test(recovery): prove worker-loss recovery contract`
