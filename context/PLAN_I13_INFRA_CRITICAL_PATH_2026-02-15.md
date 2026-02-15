# Critical Path Plan: I13 Real E2E Infrastructure Stabilization

- **Plan ID:** `CPP-I13-INFRA-001`
- **Priority:** `P0 / Critical Path`
- **Date:** `2026-02-15`
- **Objective:** Enable reliable, repeatable **real** I13 E2E execution (no service mocks) and unblock S6 delivery.

## 1) Problem Statement

Current real I13 E2E is blocked by infrastructure, not business logic:

1. Alembic migration chain fails (`20260124_0001` references missing `stakeholder_wbs_raci`).
2. Test runtime depends on tenant validation + DB readiness; requests fail as `401` before I13 assertions.
3. Redis is unavailable in local test runtime (degraded startup path).
4. Docker control is not consistently available from current terminal session.
5. No deterministic DB seed for auth/tenant context in real E2E flows.

## 2) Target State (Exit Criteria)

1. `alembic upgrade head` succeeds on clean `c2pro_test`.
2. Real I13 E2E test suite runs against live app lifespan and reaches route-level assertions.
3. Auth/tenant checks pass with seeded deterministic test tenant/user.
4. CI has a dedicated I13 real E2E gate with explicit infra preflight.
5. Failures, if any, are functional I13 failures (gating/sign-off/citation), not infra failures.

## 3) Workstreams

### WS-A: Migration Repair and DB Determinism

- **Owner:** `@backend-tdd` + `@devops-agent`
- **Scope:** `apps/api/alembic/versions/*.py`, migration runbook
- **Tasks:**

1. Patch `20260124_0001_add_raci_evidence_text.py` to be idempotent and safe.
2. Validate migration order assumptions across all revisions.
3. Execute clean migration rehearsal on fresh `c2pro_test`.
4. Add migration health verification script.

- **Acceptance:** `alembic upgrade head` passes on clean DB.

### WS-B: Test Infra Bootstrap Standardization

- **Owner:** `@devops-agent`
- **Scope:** Docker/test scripts, env bootstrap docs
- **Tasks:**

1. Create one canonical bootstrap path (DB/Redis up, DB exists, migrations applied).
2. Add preflight checks (ports, DB, alembic head, Redis reachability).
3. Enforce fail policy (DB hard fail, Redis soft fail if non-critical).

- **Acceptance:** One bootstrap command prepares local/CI infra end-to-end.

### WS-C: Auth/Tenant Seed and Real E2E Harness

- **Owner:** `@qa-agent` + `@backend-tdd`
- **Scope:** `apps/api/tests/conftest.py`, `apps/api/tests/e2e/flows/test_i13_decision_intelligence_real_e2e.py`
- **Tasks:**

1. Add deterministic tenant/user seed fixture aligned with JWT claims.
2. Ensure lifespan startup/shutdown is active for real E2E.
3. Remove random tenant JWT IDs that trigger false 401s.
4. Keep tests non-mocked at service layer.

- **Acceptance:** Tests reach endpoint business assertions (200/409 path), not auth bootstrap failures.

### WS-D: I13 Route Availability Contract

- **Owner:** `@backend-tdd`
- **Scope:** router wiring + endpoint contract
- **Tasks:**

1. Confirm and register `POST /api/v1/decision-intelligence/execute`.
2. Add minimal contract behavior if full implementation is pending.
3. Add request/response contract tests.

- **Acceptance:** Deterministic route response in all environments.

### WS-E: CI Gate and Scheduled Reliability

- **Owner:** `@devops-agent`
- **Scope:** `.github/workflows/tests.yml` (+ dedicated workflow if needed)
- **Tasks:**

1. Add blocking `i13-real-e2e` job with infra preflight.
2. Publish junit + infra diagnostics artifacts.
3. Keep S5 gates isolated and make S6 gate blocking for merge.

- **Acceptance:** CI red/green is actionable and layer-specific.

### WS-F: Documentation and Runbook

- **Owner:** `@docs-agent`
- **Scope:** tactical board, backlog, architecture plan, runbook
- **Tasks:**

1. Add I13 real E2E infra runbook.
2. Update tactical checklist with infra prerequisites.
3. Document migration patch rationale and risk notes.

- **Acceptance:** Any engineer can bootstrap/run I13 real E2E from docs only.

## 4) Critical Path Sequence

1. **CP-1:** WS-A migration repair.
2. **CP-2:** WS-B bootstrap + preflight.
3. **CP-3:** WS-C seeded auth/tenant harness.
4. **CP-4:** WS-D route contract validation.
5. **CP-5:** WS-E CI gate activation.
6. **CP-6:** WS-F documentation closure.

## 5) Milestones

1. **M1 (Day 0):** Migration fixed + `alembic upgrade head` green.
2. **M2 (Day 1):** Infra bootstrap command green on clean machine.
3. **M3 (Day 1):** Real I13 E2E reaches functional assertions.
4. **M4 (Day 2):** CI `i13-real-e2e` gate active and blocking.
5. **M5 (Day 2):** Docs/runbook updated and approved.

## 6) Risks and Mitigations

1. **Migration assumptions break legacy DBs:** use idempotent guards + smoke rehearsal.
2. **Docker permissions blocked:** provide fallback path + preflight diagnostics.
3. **Random JWT tenant IDs cause false negatives:** enforce seeded tenant fixtures.
4. **Route missing/renamed:** add CI route contract probe.

## 7) Definition of Done

1. `apps/api/tests/e2e/flows/test_i13_decision_intelligence_real_e2e.py` executes without infra/auth setup failures.
2. Alembic head applies cleanly on `c2pro_test`.
3. I13 real E2E is a CI blocking gate.
4. Tactical board and architecture/backlog docs reflect closure.
5. Remaining failures are only functional I13 logic issues.

## 8) Immediate Execution Order

1. Patch/validate `20260124_0001_add_raci_evidence_text.py`.
2. Add deterministic tenant/user seed fixture for I13 real E2E.
3. Re-run I13 real E2E locally with lifespan and seeded auth.
4. Add CI preflight + I13 real E2E job.
5. Update tactical board checklist and runbook.
