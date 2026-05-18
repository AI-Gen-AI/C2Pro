# Frontend Tasks & Knowledge Base

**Category**: Frontend (FRT)
**Owner Role**: frontend
**Last Updated**: 2026-05-16

**Quick Links**:

- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_frontend.md)

---

## 0. Status View

**Pending Tasks**: 1

- IDs: `TASK-FRT-041` (blocked — requires Clerk dashboard operator access)

**Completed Tasks**: 173

- IDs: `TASK-FRT-001`-`TASK-FRT-040`, `TASK-FRT-042`-`TASK-FRT-174`

**Usage Note**:

- Use this section to see what still needs execution without scanning the full table.
- The detailed register below remains the authoritative task history.

## 1. Active Tasks

| Status | Priority | Task ID        | Depends On | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Source                                              |
| ------ | -------- | -------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| [ ]    | P3       | `TASK-FRT-041` | None       | Production email templates and sender verified in Clerk `[-] Blocked: Requires operator Clerk dashboard access. Verification checklist in docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md (TASK-1177). Steps: (1) Verify sender email is noreply@c2pro.app with verified domain, (2) Customize sign-in/sign-up/reset templates with C2Pro branding, (3) Test email delivery from production instance.` | `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md`        |
| [x]    | P1       | `TASK-FRT-172` | None       | Add an explicit return path from the dashboard portfolio overview to the Projects list so users are not stranded after entering Dashboard. `[x] Implemented (Dashboard Navigation Recovery)` | `User report 2026-05-16` |
| [x]    | P1       | `TASK-FRT-173` | `TASK-BCK-053` | Replace raw document-upload failure copy with a plain-language state that tells the user the file was not queued and what to do next. `[x] Implemented (Upload Failure Clarity)` | `User report 2026-05-16` |
| [x]    | P1       | `TASK-FRT-174` | None       | Standardize dialogs, alert dialogs, and sheets on one high-contrast elevated surface so sub-windows remain readable and visually consistent across the app. `[x] Implemented (Shared Sub-Window Surface System)` | `User report 2026-05-16` |

**Statistics**:

- Total: 174 tasks
- Active: 1 (0.6%)
- Completed: 173 (99.4%)
- Blocked: 1 (0.6%)

---

## 2. Specifications

### TASK-FRT-171 - Production partial failure resilience

- Keep the project overview route renderable when the alerts subrequest fails but the coherence dashboard payload succeeds; use the dashboard alert count as a fallback and show a local panel warning instead of replacing the whole page with an error.

### TASK-FRT-172 - Dashboard return path

- Keep the dashboard overview reversible: the top-level portfolio screen must expose a visible link back to `/projects` before any project drill-down begins.

### TASK-FRT-173 - Upload failure clarity

- If an upload request fails before the file is queued, the UI must say that plainly, distinguish it from a successful queue handoff, and give the user a next step instead of surfacing a raw transport message.

### TASK-FRT-174 - Shared sub-window surface system

- Dialogs, alert dialogs, and sheets should use the same solid elevated surface, foreground color, border treatment, and shadow so secondary windows feel like one system and preserve contrast in both themes.

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

- **Total Tasks**: 174
- **Completed**: 173 (99.4%)
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
