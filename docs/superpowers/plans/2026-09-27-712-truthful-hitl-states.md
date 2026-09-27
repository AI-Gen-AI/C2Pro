# #712 Truthful Document and HITL State Machine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Represent review-required, rejected/needs-changes, retryable failure and active analysis as distinct durable/user-visible states.

**Architecture:** Extend the document lifecycle projection rather than overloading the legacy polling status. Preserve backward compatibility where possible, but make `lifecycle_status` and `status_detail` authoritative for user meaning. Update HITL finalization and the Documents UI to consume those semantics.

**Tech Stack:** FastAPI/Pydantic, SQLAlchemy, Next.js/React Query, Vitest/Playwright.

**Spec:** `docs/superpowers/specs/2026-09-27-issue-706-production-journey-remediation-design.md`

## Global Constraints

- REVIEW_REQUIRED is not `processing`.
- REJECT/NEEDS_CHANGES is durable and cannot poll forever.
- Exhausted retries are not indistinguishable from active work.
- UI retry eligibility must match backend reprocess eligibility.
- Existing API consumers must receive an additive/migratable contract, not silent semantic breakage.

## Review Focus

- Refresh/relogin while review is pending must render the same state.
- Approve and reject must both terminate the pending-review UI state.
- Retryable error must not be shown as final success.
- Legacy `status` compatibility must not overwrite truthful `lifecycle_status`.
- Multiple pending review items for one document must not generate an ambiguous CTA.

---

### Task 1: Domain lifecycle contract

**Files:**
- Modify: `apps/api/src/documents/application/dtos.py`
- Modify: document domain enum/model only if persistence requires a new stored status.
- Extend: `apps/api/tests/unit/adapters/documents/test_document_list_lifecycle_status.py`

**Interfaces:**
- `document_lifecycle_status(status, ...review/failure context...) -> DocumentLifecycleStatus`
- Lifecycle values include `review_required`, `rejected`/needs-changes, and `failed_retryable` as needed.

- [ ] **Step 1: Write RED mapping tests for analysis active vs review required vs rejected vs exhausted retry**
- [ ] **Step 2: Implement the minimal durable/context mapping**
- [ ] **Step 3: Run mapping tests**
- [ ] **Step 4: Commit**

Commit message: `feat(documents): model truthful review and failure states`

### Task 2: API projection and retry contract

**Files:**
- Modify: `apps/api/src/documents/adapters/http/router.py::_document_status_detail_for_polling`
- Modify: document list response construction
- Verify/modify: `POST /projects/{id}/documents/{docId}/reprocess`
- Tests: `apps/api/tests/unit/adapters/documents/test_document_router.py`

- [ ] **Step 1: Write RED tests asserting truthful details and retry eligibility**
- [ ] **Step 2: Implement additive fields such as actionable review reference/retryability when needed**
- [ ] **Step 3: Verify review-required never emits “analysis has not started”**
- [ ] **Step 4: Run router tests**
- [ ] **Step 5: Commit**

Commit message: `fix(documents): expose truthful lifecycle and recovery actions`

### Task 3: HITL reject/approve document finalization

**Files:**
- Modify: `apps/api/src/modules/hitl/adapters/persistence/resume_ownership.py::finalize_v3`
- Modify: `apps/api/src/modules/hitl/application/resume_workflow_use_case.py`
- Extend HITL persistence/resume tests.

**Interfaces:**
- APPROVE -> document becomes analyzed only after downstream persistence succeeds.
- REJECT -> document becomes durable rejected/needs-changes, not `PARSED_PENDING_ANALYSIS`.

- [ ] **Step 1: Add failing approve/reject finalization tests**
- [ ] **Step 2: Implement symmetrical durable finalization semantics**
- [ ] **Step 3: Preserve existing idempotent/fenced resume guarantees**
- [ ] **Step 4: Run HITL resume/recovery suites**
- [ ] **Step 5: Commit**

Commit message: `fix(hitl): finalize reject into truthful document state`

### Task 4: Documents UI behavior

**Files:**
- Modify: `apps/web/hooks/useProjectDocuments.ts`
- Modify: `apps/web/app/(app)/projects/[id]/documents/page.tsx`
- Extend co-located tests.

**Interfaces:**
- In-flight polling predicate excludes terminal attention states.
- REVIEW_REQUIRED shows CTA to `/projects/{id}/review`.
- FAILED_RETRYABLE shows Retry.

- [ ] **Step 1: Write Vitest tests for rendered state/CTA/polling**

Cover: one pending review links directly when a stable item id is exposed; multiple pending reviews route to the project review queue without guessing an item; terminal attention states stop the 5 s in-flight polling loop.
- [ ] **Step 2: Verify RED**
- [ ] **Step 3: Implement minimal UI mapping and CTA**
- [ ] **Step 4: Run frontend unit/typecheck**
- [ ] **Step 5: Commit**

Commit message: `fix(web): render truthful document review states`

### Task 5: E2E HITL state transition

**Files:**
- Extend/create Playwright spec under `apps/web/src/tests/e2e/`.

- [ ] **Step 1: Test pending review -> review page -> approve/reject -> document state -> hard reload**
- [ ] **Step 2: Run E2E against the controlled CI fixture**
- [ ] **Step 3: Commit**

Commit message: `test(hitl): cover truthful review lifecycle end to end`
