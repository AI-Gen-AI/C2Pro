# #715 Production Synthetic Acceptance Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the real deployed #706 end-user journey in a dedicated synthetic production tenant, with exact deployment and persistence evidence and no hidden manual repair.

**Architecture:** Reuse the P0b Playwright journey, Clerk auth helpers, and DB verifier, but replace local/mock assumptions with production preflight guards, real UI actions, deterministic polling and least-privilege read-only post-run verification. Controlled writes are allowed only inside a positively identified synthetic tenant.

**Tech Stack:** Playwright, Clerk, FastAPI API polling, PostgreSQL read-only verifier, Railway, Vercel, qualification evidence schema.

**Spec:** `docs/superpowers/specs/2026-09-27-issue-706-production-journey-remediation-design.md`

## Global Constraints

- Implement only after #710–#714 required blockers are merged/deployed.
- No `@clerk/testing` testing-token shortcut against production.
- No customer tenant access.
- No admin repair operations or SQL writes.
- No secrets in Playwright reports, screenshots, HAR, logs, GitHub comments, or evidence.
- Production worker crash injection is not required; worker-loss is proven in integration, while production proves supported retry/recovery and exact deployed configuration.

## Review Focus

- Wrong tenant identity must abort before the first mutation.
- Deployment skew outside the allowed contract must abort.
- Fixture hash mismatch must abort.
- Browser close/relogin must not change durable project state.
- A failed run must leave enough bounded evidence to diagnose without exposing secrets.

---

### Task 0: Synthetic production identity prerequisite

**Surfaces:** Clerk production identity/Organization and C2Pro tenant mapping.

**Interfaces:**
- Pre-provisioned identity is dedicated to #706 acceptance and has no customer-tenant access.
- Required secret names are limited to synthetic login credentials/ids plus production URLs and the dedicated read-only verifier connection.

- [ ] **Step 1: Provision or verify the dedicated synthetic user + Organization through the supported operator path**
- [ ] **Step 2: Verify the mapped C2Pro tenant is explicitly synthetic before storing credentials for the harness**
- [ ] **Step 3: Record identifiers only in protected configuration; never commit credential values**

### Task 1: Production preflight

**Files:**
- Create: `apps/web/src/tests/e2e/prod-acceptance/support/prod-preflight.ts`
- Create: `apps/api/scripts/verify_prod_synthetic_journey.py`
- Tests for fail-closed guard helpers.

**Interfaces:**
- Inputs are secret NAMES/env only; never log values.
- Preflight verifies production URLs/identity, exact expected backend/frontend commits/deployments, health, synthetic tenant identity, fixture hash and required credentials.

- [ ] **Step 1: RED tests for wrong tenant, wrong environment, wrong fixture hash and deployment mismatch**
- [ ] **Step 2: Implement fail-closed preflight**
- [ ] **Step 3: Run tests**
- [ ] **Step 4: Commit**

Commit message: `test(prod): add fail-closed synthetic acceptance preflight`

### Task 2: Real production auth/session helper

**Files:**
- Create: `apps/web/src/tests/e2e/prod-acceptance/support/prod-auth.synthetic.ts`
- Reuse patterns from `apps/web/src/tests/e2e/support/p0b-auth.ts`.

**Interfaces:**
- Real Playwright login with pre-provisioned synthetic Clerk user/org.
- Positively asserts active organization and expected C2Pro tenant before mutation.

- [ ] **Step 1: Add tests/helper assertions without credential output**
- [ ] **Step 2: Implement real login/session invariant**
- [ ] **Step 3: Commit**

Commit message: `test(prod): add isolated synthetic clerk auth`

### Task 3: Canonical UI journey

**Files:**
- Create: `apps/web/src/tests/e2e/prod-acceptance/706-production-synthetic.spec.ts`
- Reuse: `apps/web/src/tests/e2e/p0b-single-document-health.spec.ts`
- Fixture: `apps/web/src/tests/e2e/test-data/sample-contract.pdf` or the verified replacement from #713.

**Interfaces:**
- AUTH -> project create -> upload -> deterministic status polling -> Health/evidence -> HITL when present -> hard reload -> logout/login -> supported retry where safely triggerable.

- [ ] **Step 1: Implement project name `ACCEPT-706-<run_id>` and record project/document ids**
- [ ] **Step 2: Upload only the committed fixture after hash verification**
- [ ] **Step 3: Poll observable API state with terminal success/failure and explicit timeout; no arbitrary sleeps**
- [ ] **Step 4: Assert six Health categories and trusted/projected semantics**
- [ ] **Step 5: Assert evidence known-page behavior**
- [ ] **Step 6: Exercise one HITL action when fixture/policy produces one; otherwise use a dedicated safe fixture/condition rather than pretending coverage**
- [ ] **Step 7: Hard refresh, logout/login, assert durable equality**
- [ ] **Step 8: Exercise supported user retry without crashing shared production infrastructure**
- [ ] **Step 9: Commit**

Commit message: `test(prod): implement issue 706 synthetic user journey`

### Task 4: Tenant-scoped durable verifier

**Files:**
- Extend: `apps/api/scripts/verify_prod_synthetic_journey.py`
- Reuse assertions from: `apps/api/scripts/verify_p0b_journey.py`

**Interfaces:**
- Read-only connection only.
- Verifies document, clauses/chunks, analysis/artifact, graph/event, snapshot/Health and HITL correction when exercised.
- Every query includes synthetic tenant/project scope.

- [ ] **Step 1: Write verifier tests with synthetic IDs and cross-tenant rejection**
- [ ] **Step 2: Implement bounded read-only assertions**
- [ ] **Step 3: Verify no row contents/secrets are emitted unnecessarily**
- [ ] **Step 4: Commit**

Commit message: `test(prod): verify synthetic journey durable state`

### Task 5: Qualification evidence bundle and manual workflow

**Files:**
- Create: `.github/workflows/prod-synthetic-acceptance.yml`
- Emit evidence conforming to `validation/product/qualification-evidence.schema.yaml`.
- Documentation: concise operator runbook under `docs/product/`.

**Interfaces:**
- Workflow is manual-only until the first successful controlled production run.
- Evidence binds exact Railway/Vercel identities plus persisted synthetic entity IDs/correlation IDs.

- [ ] **Step 1: Add workflow/security tests preventing scheduled execution and secret artifact leakage**
- [ ] **Step 2: Implement manual dispatch**
- [ ] **Step 3: Validate evidence with `validation/product/validate_qualification_evidence.py`**
- [ ] **Step 4: Commit**

Commit message: `ci(prod): add manual synthetic acceptance workflow`

### Task 6: First #706 production qualification

**Surfaces:** Railway, Vercel, Clerk synthetic identity, production DB read-only verifier.

- [ ] **Step 1: Verify exact deployed identities after all remediation merges**
- [ ] **Step 2: Execute preflight; abort on any mismatch**
- [ ] **Step 3: Execute one clean synthetic run**
- [ ] **Step 4: Run durable verifier**
- [ ] **Step 5: Review service logs for unexplained P0/P1 errors**
- [ ] **Step 6: Validate evidence bundle**
- [ ] **Step 7: Decide #706 GO/NO-GO strictly from captured evidence**
