# Follow-up Ticket: Remove Dormant ORM Fallback Paths

## Ticket

- **ID**: `FOLLOWUP-AUTH-BOOTSTRAP-FALLBACK-REMOVAL`
- **Status**: Open
- **Priority**: P2
- **Owner**: Team Alpha (Sentinel)

## Goal

Remove ORM fallback branches from auth bootstrap helpers after a stable production observation window confirms SQL bootstrap reliability.

## Preconditions

- Production and staging run with `AUTH_BOOTSTRAP_FALLBACK_MODE=deny` for at least 2 consecutive release cycles.
- No unresolved incidents tied to missing `auth_bootstrap.*` functions or grants.
- Telemetry review shows no emergency override to `always` mode during the window.

## Scope

- Remove fallback branches in `apps/api/src/core/auth/bootstrap_lookup.py`.
- Simplify dependent blocked-fallback error handling where no longer needed.
- Update tests to assert SQL-only behavior in production/staging paths.

## Acceptance Criteria

- [ ] No ORM fallback code path remains in auth bootstrap helpers.
- [ ] All auth bootstrap and tenant isolation tests pass.
- [ ] Runbook `docs/runbooks/AUTH_BOOTSTRAP_FALLBACK_POLICY.md` updated to reflect SQL-only posture.

## Notes

This follow-up should be executed as a dedicated SDD change after `harden-auth-bootstrap-fail-closed` is fully verified and promoted.
