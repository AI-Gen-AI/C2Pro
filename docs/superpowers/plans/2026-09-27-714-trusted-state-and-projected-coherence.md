# #714 P0 Trusted-State Commit and Projected Coherence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make HITL the trust boundary for canonical ProjectGraph/Health/Coherence and expose a clearly provisional Coherence projection for pending reviews. This is P0 for #706 closure because the #706 North Star explicitly includes ProjectGraph/HITL canonical correctness, regardless of whether a tenant flag is currently off.

**Architecture:** Persist pre-review output as a versioned candidate, but gate canonical artifact/ProjectGraph commit behind exact-version approval. Rebuild/promote canonical projections after approval/correction; rejection preserves the prior trusted state. Add a separate derived `projected_score` contract computed by the same canonical scoring engine/version from trusted state plus exact pending candidates.

**Tech Stack:** LangGraph, PostgreSQL/SQLAlchemy, Celery ProjectGraph tasks, ECOA Coherence Score v1/v2 contracts, Next.js/React.

**Spec:** `docs/superpowers/specs/2026-09-27-issue-706-production-journey-remediation-design.md`

## Global Constraints

- Pending/rejected candidates never mutate canonical ProjectGraph, Health, or trusted Coherence.
- Approval binds to the exact reviewed version/hash.
- Corrected review produces a new candidate version.
- Canonical commit is exactly-once/idempotent.
- `projected_score` uses the exact same score engine and `score_version` as trusted score.
- Existing null/insufficient-evidence semantics stay authoritative.
- Official exports use trusted score unless explicitly marked scenario/projection.

## Review Focus

- Approval after a newer candidate appears must reject stale/substituted approval.
- Retry of the same approval must not double-commit ProjectGraph/events/snapshot.
- Reject when no prior trusted state exists must leave canonical score null/pending.
- Mixed pending reviews from different candidate versions must project deterministically.
- ECOA v1/v2 feature-state changes must never mix score versions inside one projection.

---

### Task 1: Candidate/trust domain model

**Files:**
- Modify/create persistence/domain types around `apps/api/src/analysis/application/document_artifact_completion.py` and document artifact repository.
- Add migration only if durable trust/version/hash fields are absent.
- Tests under `apps/api/tests/unit/analysis/`.

**Interfaces:**
- Candidate identity includes stable artifact id/version/hash, document/project/tenant, and trust state `PROPOSED | TRUSTED | REJECTED | SUPERSEDED`.
- Produce `persist_candidate_artifact(final_state) -> CandidateArtifactRef`.
- Produce `commit_trusted_artifact(candidate_ref, approval_binding) -> TrustedCommitResult`.

- [ ] **Step 1: Write RED tests for proposed persistence without canonical enqueue**
- [ ] **Step 2: Add minimal version/hash/trust representation**
- [ ] **Step 3: Persist proposed candidate while preserving audit/recovery**
- [ ] **Step 4: Run tests**
- [ ] **Step 5: Commit**

Commit message: `feat(hitl): persist versioned untrusted analysis candidates`

### Task 2: Stop pre-review canonical ProjectGraph enqueue

**Files:**
- Modify: `apps/api/src/analysis/factories/orchestrator_factory.py`
- Modify: `apps/api/src/analysis/application/document_artifact_completion.py`
- Extend: `apps/api/tests/unit/analysis/graph/test_project_graph_trigger.py`

- [ ] **Step 1: RED invariant: `human_approval_required=True` persists candidate but never calls canonical `enqueue_project_graph`**
- [ ] **Step 2: GREEN invariant: non-HITL final output still commits/enqueues once**
- [ ] **Step 3: Implement minimal branch around the trusted commit boundary**
- [ ] **Step 4: Run graph trigger tests**
- [ ] **Step 5: Commit**

Commit message: `fix(project-graph): gate canonical enqueue behind trust`

### Task 3: Exact approval binding and post-HITL trusted commit

**Files:**
- Modify: `apps/api/src/modules/hitl/application/resume_workflow_use_case.py`
- Modify: `apps/api/src/modules/hitl/adapters/persistence/resume_ownership.py`
- Modify trusted artifact completion service.
- Extend HITL resume/recovery tests.

**Interfaces:**
- Approval binding carries exact candidate id/version/hash plus review/operation identity.
- APPROVE/CORRECT -> exact candidate verification -> trusted commit -> ProjectGraph -> snapshot.
- REJECT -> mark candidate rejected, no canonical mutation.

- [ ] **Step 1: Write stale-substitution, duplicate-approval, reject, and correction tests**
- [ ] **Step 2: Verify RED**
- [ ] **Step 3: Implement binding verification and exactly-once commit**
- [ ] **Step 4: Run HITL + ProjectGraph tests**
- [ ] **Step 5: Commit**

Commit message: `feat(hitl): bind approvals to exact trusted-state commit`

### Task 4: Trusted vs projected Coherence API contract

**Files:**
- Modify backend coherence DTO/model/router surfaces that produce `DashboardSummary`.
- Modify: `apps/web/lib/api/contracts.ts`
- Backend tests in coherence scoring/router suites.

**Interfaces:**
- Additive fields:
  - `trusted_score: number | null`
  - `projected_score: number | null`
  - `projected_delta: number | null`
  - `pending_review_count: int`
  - `projection_score_version: "coherence-v1" | "coherence-v2" | null`
- Existing `coherence_score` remains canonical/trusted during migration.

- [ ] **Step 1: RED test: trusted=80 + pending exact candidates evaluate through canonical engine to projected=60**
- [ ] **Step 2: RED test: reject removes pending candidate and projection returns to trusted**
- [ ] **Step 3: RED tests for projection version isolation**

Assert correction replaces candidate rather than stacking old+new; mixed pending candidate versions are deterministic; a coherence-v1 trusted snapshot cannot be combined with coherence-v2 pending results without recomputing under one canonical score version.
- [ ] **Step 4: Implement a projection service that invokes the existing canonical scorer instead of ad-hoc arithmetic**
- [ ] **Step 5: Run coherence tests including null/active-weight guards**
- [ ] **Step 6: Commit**

Commit message: `feat(coherence): add trusted and pending-review projection contract`

### Task 5: Projected-score UI

**Files:**
- Modify: `apps/web/components/coherence/ScoreCard.tsx`
- Modify: `apps/web/components/coherence/DashboardClient.tsx`
- Modify: `apps/web/lib/api/contracts.ts`
- Extend: `apps/web/components/coherence/DashboardClient.test.tsx`

**Interfaces:**
- Trusted score rendered solid/canonical.
- Projected score rendered translucent/outline and labelled “Projected if all pending proposals are accepted unchanged”.
- Delta and pending count visible; pending count links to review queue.
- First-analysis case: trusted `—/Pending`, projected may be numeric and remains explicitly provisional.

- [ ] **Step 1: Write UI tests for trusted 80/projected 60, reject/no-projection, and trusted-null/projected-present**
- [ ] **Step 2: Verify RED**
- [ ] **Step 3: Implement the minimal accessible visual treatment**
- [ ] **Step 4: Run Vitest/typecheck and null-fallback coherence guard**
- [ ] **Step 5: Commit**

Commit message: `feat(web): show pending-review coherence projection`

### Task 6: Canonical-state invariants

**Tests:**
- Integration tests spanning HITL -> artifact -> ProjectGraph -> snapshot/Health -> coherence.

- [ ] **Step 1: Assert pending never changes canonical graph/Health/score**
- [ ] **Step 2: Assert rejected never changes canonical graph/Health/score**
- [ ] **Step 3: Assert approved/corrected changes canonical state exactly once**
- [ ] **Step 4: Run full HITL/coherence/ProjectGraph suites**
- [ ] **Step 5: Commit**

Commit message: `test(trust): prove hitl canonical-state boundary`
