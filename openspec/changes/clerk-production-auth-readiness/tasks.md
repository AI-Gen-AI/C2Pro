# Tasks: Clerk Production Authentication Readiness

## Phase 1: Foundation / Contracts

- [x] 1.1 Review `TASK-1174` through `TASK-1179` in `C2PRO_MASTER_BACKLOG.md` and extract the closure requirements into one ordered workflow.
- [x] 1.2 Review the current `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` and identify gaps between explanatory guidance and executable runbook behavior.
- [x] 1.3 Create OpenSpec artifacts for production Clerk authentication readiness under `openspec/changes/clerk-production-auth-readiness/`.

## Phase 2: Specification / Design

- [x] 2.1 Define requirements in `specs/auth-production/spec.md` for live keys, production URLs, production sender, deployment wiring, and closure evidence.
- [x] 2.2 Document architecture decisions, operator flow, environment contract, and evidence contract in `design.md`.
- [x] 2.3 Ensure all scenarios use explicit GIVEN/WHEN/THEN wording and all requirements use RFC 2119 terms.

## Phase 3: Runbook Rewrite

- [x] 3.1 Rewrite `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` into an executable runbook with preflight, ordered steps, smoke tests, and rollback.
- [x] 3.2 Add a task matrix mapping `TASK-1174` through `TASK-1179` to explicit execution steps and evidence.
- [x] 3.3 Add secret-handling guardrails and clarify that repository wiring is not the same as production completion.

## Phase 4: Verification / Handoff

- [x] 4.1 Run `npm run verify:openspec -- --change clerk-production-auth-readiness` and capture the result.
- [x] 4.2 Manually review the rewritten runbook against the new spec and confirm each scenario has a corresponding validation step.
- [x] 4.3 Hand off the runbook as the canonical execution document for future closure of `TASK-1174` through `TASK-1179`.

## Completion Notes

- OpenSpec artifacts for production Clerk auth readiness are present and aligned to the current backlog tasks.
- The runbook rewrite converts the prior explanatory guide into an operator procedure with closure evidence.
- Verification command evidence: `python scripts/verify_openspec_change.py --change clerk-production-auth-readiness` completed with exit code `0` and generated `openspec/changes/clerk-production-auth-readiness/verify-report.md`.
