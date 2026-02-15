# Critical Path Plan: I13 Real E2E Infrastructure Stabilization

- **Plan ID:** `CPP-I13-INFRA-001`
- **Priority:** `P0 / Critical Path`
- **Date:** `2026-02-15`
- **Objective:** Enable reliable, repeatable **real** I13 E2E execution (no service mocks) and unblock S6 delivery.

## 1) Problem Statement

Current real I13 E2E is blocked by infrastructure, not business logic:

1. Alembic migration chain fails (`20260124_0001` references missing `stakeholder_wbs_raci`).
2. Test runtime previously failed on tenant validation (`401`) before I13 assertions.
3. Redis is unavailable in local test runtime (degraded startup path).
4. Docker control is not consistently available from current terminal session.
5. Deterministic DB seed for auth/tenant context was missing in real E2E flows.
6. Current active blocker: `POST /api/v1/decision-intelligence/execute` returns `404` (route contract not wired/available).

## 1.1) Current Verified Status (2026-02-15)

- `WS-C` auth/bootstrap stabilization is now in place:
  - deterministic seeded tenant/user fixture aligned with JWT claims.
  - random JWT tenant IDs removed from I13 real E2E harness.
  - lifespan startup/shutdown remains active in real E2E (`LifespanManager`).
- Real I13 E2E requests now pass authentication and reach app routing.
- Active failure class moved from `401` to `404` across all 5 tests:
  - `pytest apps/api/tests/e2e/flows/test_i13_decision_intelligence_real_e2e.py -q`
  - Result: `5 failed`, all `404 Not Found`.

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

1. Locate or create I13 HTTP router module under hexagonal adapter boundary:
   - expected route: `POST /api/v1/decision-intelligence/execute`
   - keep router thin and use use-case orchestration only.
2. Register router in `create_application()` with `api_v1_prefix`.
3. Define/lock request-response contract for real E2E path:
   - success path (`200`) includes coherence/evidence/citations fields.
   - gated paths (`409`) include explicit blocking reasons.
4. Add route contract tests to detect missing wiring regressions:
   - one smoke test ensuring endpoint exists (not `404`) under valid auth.
   - one contract test per main branch (`200`, `409` low confidence, `409` missing citations, `409` mandatory sign-off).
5. Keep service layer non-mocked for real E2E; only infra prerequisites are seeded.

- **Acceptance:** Deterministic route response in all environments.

### WS-D.1: Immediate 404 Remediation Plan (New)

- **Trigger:** All I13 real E2E scenarios now fail with `404`, not `401`.
- **Execution Steps:**

1. `RED`:
   - Add a focused test: authenticated call to `/api/v1/decision-intelligence/execute` must be `!= 404`.
   - Verify failure reproduces current blocker.
2. `GREEN`:
   - Wire route in app router registration.
   - Implement minimal contract adapter/use-case path to return controlled `200/409` responses per existing I13 assertions.
3. `REFACTOR`:
   - align DTO naming, error mapping, and route docs with architecture plan.
   - keep tenant validation and auth dependency unchanged.
4. Verify:
   - re-run `apps/api/tests/e2e/flows/test_i13_decision_intelligence_real_e2e.py`.
   - confirm failures, if any, are functional assertions (not missing route).

- **Acceptance:** I13 suite reaches business assertions (`200/409`) and no test fails by `404`.

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

### WS-G: RLS GUC Contract Hardening (New)

- **Owner:** `@qa-agent` + `@backend-tdd` + `@security-agent`
- **Scope:** `apps/api/tests/e2e/security/test_multi_tenant_isolation.py`, tenant context runtime wiring
- **Tasks:**

1. `RED` (`@qa-agent`):
   - Add failing security tests for PostgreSQL tenant GUC contract (`app.current_tenant`) without skip fallback.
   - Ensure missing GUC configuration fails explicitly instead of being masked.
2. `GREEN` (`@backend-tdd`):
   - Implement request-lifecycle tenant context set/reset in infra layer using PostgreSQL session config.
   - Keep auth and tenant validation behavior unchanged.
3. `REFACTOR` (`@backend-tdd` + `@security-agent`):
   - Consolidate context handling in one infra utility.
   - Verify safe telemetry/logging (no sensitive leakage) and deterministic behavior in local/CI.

- **Acceptance:** No skip for GUC contract tests; failures are hard and actionable when GUC contract regresses.

## 4) Critical Path Sequence

1. **CP-1:** WS-A migration repair.
2. **CP-2:** WS-B bootstrap + preflight.
3. **CP-3:** WS-C seeded auth/tenant harness.
4. **CP-4:** WS-D route contract validation (404 remediation first).
5. **CP-5:** WS-E CI gate activation.
6. **CP-6:** WS-F documentation closure.
7. **CP-7:** WS-G RLS GUC contract hardening.

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
3. Re-run I13 real E2E locally with lifespan and seeded auth (expect no `401`).
4. Execute WS-D.1 to remove `404` blocker on `/api/v1/decision-intelligence/execute`.
5. Add CI preflight + I13 real E2E job.
6. Update tactical board checklist and runbook.
7. Execute WS-G RED for `app.current_tenant` contract and unblock GREEN implementation.

---

Last Updated: 2026-02-15

Changelog:
- 2026-02-15: Added current-state checkpoint (401 resolved, 404 active blocker) and detailed WS-D.1 remediation plan for missing I13 route contract.
- 2026-02-15: Added WS-G for PostgreSQL `app.current_tenant` GUC contract hardening (RED/GREEN/REFACTOR ownership and acceptance).
