# I10 Stakeholder Resolution + RACI Inference Hardening Implementation Plan

## 1. Architectural Alignment

Feature scope: **I10 Stakeholder Resolution + RACI Inference hardening**.  
Target: move from test-green status to **runtime-integrated, deterministic, hexagonal-compliant implementation** in the active stakeholders flow.

## 2. Implementation Plan (TDD-First)

### Step 1: Baseline and Scope Lock (`@planner-agent`)

- Define and lock canonical module path for Stakeholders runtime.
- Define deprecation strategy for non-canonical runtime path.
- Freeze acceptance criteria for I10.1, I10.2, I10.4, and I10.6.

Canonical runtime path decision:

- Canonical path: `apps/api/src/stakeholders/*`.
- Rationale: This path is currently wired to active adapters/use cases and persistence flow, while `apps/api/src/modules/stakeholders/*` is isolated to I10-focused tests.

Deprecation strategy (`apps/api/src/modules/stakeholders/*`):

1. Phase A (immediate): mark as deprecated and stop adding new logic.
2. Phase B (migration): port required I10 domain/application behavior into `apps/api/src/stakeholders/*`.
3. Phase C (compatibility): keep thin compatibility shims only if required for transitional imports.
4. Phase D (cleanup): remove shims and delete deprecated tree after tests/imports are fully switched.

Frozen acceptance criteria:

- I10.1 Canonical Resolution:
- Alias or exact-name match resolves to an existing canonical stakeholder identity in tenant scope.
- No duplicate stakeholder is created when canonical match exists.
- I10.2 RACI Constraint Enforcement:
- Each activity must have exactly one `Accountable`.
- Invalid matrices fail before persistence or response.
- I10.4 Determinism:
- Same normalized inputs (clauses, tenant, project, stakeholder set) produce stable output structure and stable unresolved references.
- Determinism must be validated with real resolver behavior (no resolver mocking).
- I10.6 Ambiguity Escalation:
- Ambiguous mappings are flagged for PMO/legal/HITL review.
- Ambiguous mappings are not silently merged or auto-persisted as resolved identities.

Definition of Done:

- One runtime path only: `apps/api/src/stakeholders/*`.
- No synthetic stakeholder IDs in ambiguous mappings.
- Determinism proven with non-mocked resolver tests.

### Step 2: RED Tests for Runtime Wiring (`@qa-agent`)

- Add failing integration tests proving I10 behavior is reachable via active use case/router path.
- Add failing test: ambiguous mapping does **not** create/persist unresolved stakeholder IDs.
- Add failing determinism test using real `StakeholderResolver`.

Definition of Done:

- Tests fail for assertion reasons (not import errors).

### Step 3: RED Tests for Hexagonal Contracts (`@qa-agent`)

- Add failing contract tests for ports as `Protocol` (no concrete app logic in ports file).
- Add failing test for tenant isolation in all repository reads/writes in I10 flow.

Definition of Done:

- Contract violations are explicit and reproducible.

### Step 4: GREEN Runtime Unification (`@backend-tdd`)

- Consolidate I10 implementation into the chosen active module path.
- Wire routers/use cases/services to this single implementation.
- Keep legacy path as compatibility shim only if required (short-lived).

Definition of Done:

- I10 behavior is invoked through active HTTP/application path.

### Step 5: GREEN Domain/Application Fixes (`@backend-tdd`)

- Update ambiguity policy: ambiguous entity escalates only (no auto-assigned canonical/stakeholder persistence).
- Enforce single-accountable validation before persistence/output release.
- Ensure deterministic keying for same inputs (stable IDs or stable unresolved-reference policy).

Definition of Done:

- All new RED tests pass.
- Existing I10/S5 tests remain green.

### Step 6: Security and Reliability Hardening (`@security-agent`)

- Add or verify test coverage for no HITL bypass on ambiguity.
- Add or verify test coverage for no cross-tenant leakage.
- Add or verify test coverage for sanitized errors and trace payloads.

Definition of Done:

- Security suite green, with no regression in `TS-SEC-S5-001` behaviors.

### Step 7: Refactor and Cleanup (`@backend-tdd`)

- Split `ports` into pure interfaces (`Protocol`) and separate service implementation module.
- Remove dead/duplicate code paths and update imports.

Definition of Done:

- Static architecture checks pass.
- No duplicated I10 logic remains.

### Step 8: Documentation and Tracking (`@docs-agent`)

- Update `context/C2PRO_TDD_BACKLOG_v1.0.md`.
- Update `context/PLAN_ARQUITECTURA_v2.1.md`.
- Record completion with: `[x] Implemented (Unit Tests & Domain Logic)` plus runtime integration note.

Definition of Done:

- Suite IDs normalized (`STK` vs `STKH`) and traceability consistent.

## 3. Execution Order

1. `@qa-agent` (RED runtime + contract tests)
2. `@backend-tdd` (GREEN unification + policy fixes)
3. `@security-agent` (security assertions)
4. `@backend-tdd` (REFACTOR cleanup)
5. `@docs-agent` (status synchronization)

## 4. Global Definition of Done

- I10 tests pass at unit, integration, and security layers.
- Active router/use case path exercises I10 logic directly.
- Ambiguous mappings always require review and never create synthetic persisted stakeholder identity.
- Determinism for same inputs verified with real resolver path.
- Architecture docs and backlog status are fully synchronized.

## 5. TDD Test Plan (Mandatory RED -> GREEN -> REFACTOR)

### 5.1 Scope and Test Artifacts

- Canonical test target path: `apps/api/src/stakeholders/*`.
- Legacy path under deprecation: `apps/api/src/modules/stakeholders/*` (no new test additions except migration-guard checks).
- Existing reference suites to keep green:
- `apps/api/tests/modules/stakeholders/domain/test_i10_stakeholder_resolution.py`
- `apps/api/tests/modules/stakeholders/application/test_i10_raci_inference_service.py`
- `apps/api/tests/security/test_s5_stakeholders_hitl_observability_security.py`

### 5.2 Planned Test Suites for I10 Hardening

- `TS-I10-STK-INT-001` Runtime wiring integration:
- Verifies active router/use-case path invokes I10 resolution and RACI inference in canonical module.
- Verifies deprecated path is not used by runtime wiring.

- `TS-I10-STK-DOM-002` Ambiguity escalation contract:
- Verifies ambiguous mappings are flagged and never become synthetic persisted stakeholder IDs.
- Verifies no silent auto-merge on ambiguous matches.

- `refa Determinism contract (real resolver):
- Verifies same normalized inputs produce stable output and stable unresolved references.
- Prohibits mocked resolver in determinism test cases.

- `TS-I10-STK-PORT-001` Hexagonal ports contract:
- Verifies application ports are `Protocol` interfaces only.
- Verifies concrete service logic is outside ports module.

- `TS-I10-STK-SEC-001` Security hardening extension:
- Verifies no HITL bypass for ambiguity-driven decisions.
- Verifies tenant isolation and sanitized error payloads in ambiguous and invalid RACI flows.

### 5.3 RED Phase Execution Order

1. RED-1: Add failing runtime wiring tests (`TS-I10-STK-INT-001`).
2. RED-2: Add failing ambiguity persistence tests (`TS-I10-STK-DOM-002`).
3. RED-3: Add failing determinism tests with real resolver (`TS-I10-STK-APP-002`).
4. RED-4: Add failing ports architecture tests (`TS-I10-STK-PORT-001`).
5. RED-5: Add failing security extension tests (`TS-I10-STK-SEC-001`).

RED phase pass criteria:

- Every new test fails for expected assertion/behavioral reasons.
- No implementation edits before all RED tests are committed and reproducible.

### 5.4 GREEN Phase Execution Order

1. GREEN-1: Unify runtime wiring to canonical module path.
2. GREEN-2: Implement ambiguity escalation-only policy and block synthetic identity persistence.
3. GREEN-3: Implement deterministic unresolved-reference strategy.
4. GREEN-4: Refactor ports into `Protocol` interfaces and move concrete services to implementation modules.
5. GREEN-5: Apply security hardening until all new and baseline suites are green.

GREEN phase pass criteria:

- All `TS-I10-STK-*` hardening suites pass.
- Existing I10 and S5 suites remain green with no skipped tests.

### 5.5 REFACTOR Phase Rules

- Refactor only after full GREEN.
- Preserve behavior with no test expectation relaxation.
- Remove duplicate logic from deprecated path after compatibility window closes.
- Keep tenant-scoped query behavior explicit in repositories.

REFACTOR pass criteria:

- No regression in unit, integration, and security suites.
- Imports and module boundaries comply with hexagonal rules.

### 5.6 Test Commands and Gates

- Focused I10 regression run:
- `$env:PYTHONPATH='apps/api'; pytest apps/api/tests/modules/stakeholders/domain/test_i10_stakeholder_resolution.py apps/api/tests/modules/stakeholders/application/test_i10_raci_inference_service.py -q`

- Security regression run:
- `$env:PYTHONPATH='apps/api'; pytest apps/api/tests/security/test_s5_stakeholders_hitl_observability_security.py -q`

- Hardening suite run (when added):
- `$env:PYTHONPATH='apps/api'; pytest apps/api/tests/modules/stakeholders -q`

Gate policy:

- No merge if any I10 hardening suite fails.
- No merge if determinism test uses mocked resolver.
- No merge if tenant isolation assertions fail.

---

Last Updated: 2026-02-17

Changelog:

- 2026-02-17: Created implementation plan from `@planner-agent` audit outcome for I10 Stakeholder Resolution + RACI Inference hardening.
- 2026-02-17: Updated Step 1 with canonical runtime path decision, phased deprecation strategy, and frozen acceptance criteria for I10.1/I10.2/I10.4/I10.6.
- 2026-02-17: Added detailed TDD test plan section with hardening suites, RED/GREEN/REFACTOR sequencing, commands, and merge gates.
