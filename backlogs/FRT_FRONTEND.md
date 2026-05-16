# Frontend Tasks & Knowledge Base

**Category**: Frontend (FRT)
**Owner Role**: frontend
**Last Updated**: 2026-05-08

**Quick Links**:

- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_frontend.md)

---

## 0. Status View

**Pending Tasks**: 1

- IDs: `TASK-FRT-041` (blocked — requires Clerk dashboard operator access)

**Completed Tasks**: 170

- IDs: `TASK-FRT-001`-`TASK-FRT-040`, `TASK-FRT-042`-`TASK-FRT-171`

**Usage Note**:

- Use this section to see what still needs execution without scanning the full table.
- The detailed register below remains the authoritative task history.

## 1. Active Tasks

| Status | Priority | Task ID        | Depends On | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Source                                              |
| ------ | -------- | -------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| [ ]    | P3       | `TASK-FRT-041` | None       | Production email templates and sender verified in Clerk `[-] Blocked: Requires operator Clerk dashboard access. Verification checklist in docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md (TASK-1177). Steps: (1) Verify sender email is noreply@c2pro.app with verified domain, (2) Customize sign-in/sign-up/reset templates with C2Pro branding, (3) Test email delivery from production instance.` | `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md`        |

**Statistics**:

- Total: 171 tasks
- Active: 1 (0.6%)
- Completed: 170 (99.4%)
- Blocked: 1 (0.6%)

---

## 2. Specifications

### TASK-FRT-171 - Production partial failure resilience

- Keep the project overview route renderable when the alerts subrequest fails but the coherence dashboard payload succeeds; use the dashboard alert count as a fallback and show a local panel warning instead of replacing the whole page with an error.

---

## 3. Lessons Learned

_Lessons learned will be documented here_

---

## 4. Architectural Decisions

_ADRs for this category will be documented here_

---

## 5. Technical Debt

| Debt ID | Description | Impact | Effort | Created |
| ------- | ----------- | ------ | ------ | ------- |

---

## 6. Metrics

- **Total Tasks**: 170
- **Completed**: 169 (99.4%)
- **Average Completion Time**: TBD
- **Test Coverage**: TBD

---

## 7. Audit Reports

### Frontend Integration Test Audit (TASK-REV-FRONTEND-001)

**Date**: 2026-04-07
**Status**: ✅ Stabilized (48/48 Files Passing)

#### Findings:

1. **Root Cause of ERR_INVALID_URL**: Node.js `fetch` implementation in Vitest/JSDOM does not support relative URLs. Any call to `fetch('/api/...')` throws `ERR_INVALID_URL` because it lacks an origin.
2. **Current Fix**: The project implemented a custom MSW shim in `apps/web/src/tests/shims/msw-node.ts` that overrides `global.fetch` and automatically prepends `http://localhost` to relative paths.
3. **act() Warnings**: Many integration tests (Shortcuts, Mobile Evidence) still emit React `act(...)` warnings. These occur when state updates (e.g., from `fireEvent.keyDown` on `window`) are not correctly wrapped or awaited.
4. **Axios Inconsistency**: `vitest.setup.ts` sets `axios.defaults.baseURL = "/api"`. This is relative and will FAIL in Node for any non-mocked request. It currently works only because integration tests predominantly use `fetch`.

#### Recommendations:

- **Stabilization**: Sprint 2 task should be created to wrap failing state updates in `act()` to eliminate console noise and potential race conditions.
- **Consistency**: Update `axios.defaults.baseURL` to `http://localhost/api` in `vitest.setup.ts` to provide a consistent origin for all HTTP clients in the test environment.
- **Maintenance**: Retain the `msw-node.ts` shim until a full migration to a real `msw/node` setup is feasible (currently blocked by ESM/CJS issues).
