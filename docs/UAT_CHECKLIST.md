# C2Pro UAT / Manual QA Signoff Checklist - G7-03

> **Document ID**: G7-03  
> **Status**: ACTIVE  
> **Last Updated**: 2026-03-27  
> **Owner**: Product / Security / Operations

---

## 1. Goal

Define the minimum manual validation and signoff record required before a C2Pro release candidate can be approved for promotion.

This checklist exists to prove three things:

1. Product workflows are usable with real persisted data.
2. Security controls still hold under manual authenticated use.
3. Operations can deploy, observe, and recover the candidate safely.

---

## 2. Execution Plan

Use this checklist in the following order for each release candidate:

1. Confirm release identity and environment safety.
2. Execute product UAT flows on the intended runtime.
3. Execute security-focused manual QA.
4. Execute operations and release-readiness checks.
5. Record defects, risk acceptances, and final decisions in the release bundle signoff.

---

## 3. Preconditions

All items below must be true before manual signoff starts:

- Candidate commit SHA is frozen and recorded in `evidence/releases/<release-id>/signoff.md`.
- Required automated suites from `docs/RELEASE_CRITERIA.md` are green or explicitly risk-accepted.
- Runtime environment has passed `scripts/validate_runtime_env.py` or equivalent runtime-vs-test guard.
- Test users, tenant, and sample documents are known and approved for the run.
- Release owner has defined rollback contact and promotion window.

If any precondition is false, manual signoff is blocked.

---

## 4. Product UAT

Record `Pass`, `Fail`, or `N/A` for each item.

| ID | Area | Manual Verification | Result | Notes |
| -- | ---- | ------------------- | ------ | ----- |
| `P-01` | Auth | Login succeeds for a valid tenant user and protected routes load without mock/demo fallbacks. | `___` | |
| `P-02` | Auth | Logout and token expiry handling return the user to an explicit auth state without ambiguous redirects. | `___` | |
| `P-03` | Dashboard | Dashboard shows persisted project, alert, and coherence data after refresh. | `___` | |
| `P-04` | Projects | Project list, project detail, and filters return tenant-scoped real data only. | `___` | |
| `P-05` | Documents | Document viewer loads real files, not placeholders, and fails closed for missing or unauthorized files. | `___` | |
| `P-06` | Highlights | Document/entity highlights map to real extracted data and remain stable after reload. | `___` | |
| `P-07` | Alerts | Alert list, alert detail, and alert status changes persist correctly after page reload. | `___` | |
| `P-08` | MCP-backed flows | User-facing flows depending on MCP or analysis execution return real responses and no synthetic completions. | `___` | |
| `P-09` | AI orchestration | Long-running analysis shows progress/state transitions and completes with persisted output. | `___` | |
| `P-10` | Error handling | Invalid or unavailable resources show explicit error states rather than silent fallbacks. | `___` | |

Product signoff rule:

- No `Fail` items in `P-01` through `P-10`.

---

## 5. Security Manual QA

| ID | Area | Manual Verification | Result | Notes |
| -- | ---- | ------------------- | ------ | ----- |
| `S-01` | Tenant isolation | User from tenant A cannot access tenant B resources by URL, ID tampering, or stale navigation. | `___` | |
| `S-02` | Authorization | Non-admin or lower-privilege users cannot perform admin-only mutations. | `___` | |
| `S-03` | Document access | Unauthorized document fetches fail closed and do not leak metadata or file contents. | `___` | |
| `S-04` | API auth | Protected API endpoints reject missing, expired, or malformed bearer tokens with explicit auth errors. | `___` | |
| `S-05` | MCP safety | MCP endpoints reject unauthorized access and destructive operations remain blocked. | `___` | |
| `S-06` | Sensitive data | Logs, responses, and UI states do not expose secrets, raw credentials, or avoidable PII. | `___` | |
| `S-07` | CORS/browser behavior | Browser-origin requests follow the intended environment CORS policy without open wildcard behavior. | `___` | |
| `S-08` | Auditability | Security-relevant mutations and MCP operations create audit evidence in runtime storage. | `___` | |

Security signoff rule:

- No `Fail` items in `S-01` through `S-08`.

---

## 6. Operations Manual QA

| ID | Area | Manual Verification | Result | Notes |
| -- | ---- | ------------------- | ------ | ----- |
| `O-01` | Release identity | Release ID, candidate SHA, and target environment match the release bundle. | `___` | |
| `O-02` | Deployment | API and frontend candidate are reachable after deploy/restart with expected environment configuration. | `___` | |
| `O-03` | Health | `/health`, worker health checks, and core dependencies report healthy state. | `___` | |
| `O-04` | Observability | Logs, traces, and error reporting appear in the expected observability tools for the candidate. | `___` | |
| `O-05` | Queue/worker | Background jobs can be submitted and completed without stuck queue or silent worker failure. | `___` | |
| `O-06` | Rate limiting / guardrails | Runtime guardrails such as budget, rate limit, and fail-closed controls behave as expected. | `___` | |
| `O-07` | Rollback readiness | Rollback owner, rollback steps, and rollback artifact references are present and current. | `___` | |
| `O-08` | Data safety | Backup/restore and DR evidence referenced in the release bundle matches the candidate window. | `___` | |

Operations signoff rule:

- No `Fail` items in `O-01` through `O-08`.

---

## 7. Defect and Risk Recording

Any failed or waived item must be recorded in `evidence/releases/<release-id>/signoff.md` with:

- item ID
- defect or risk summary
- owner
- mitigation
- disposition: `fix before release` or `risk accepted`
- expiration date for any temporary acceptance

Open `P0` or unresolved tenant/security failures block release automatically.

---

## 8. Final Signoff Record

Copy this section into the release bundle and complete it at release time.

| Signoff Area | Owner | Decision | Evidence Reference | Notes |
| ------------ | ----- | -------- | ------------------ | ----- |
| Product | `_____` | `Approve / Reject` | `docs/UAT_CHECKLIST.md` + release notes | |
| Security | `_____` | `Approve / Reject` | security workflow + manual QA notes | |
| Operations | `_____` | `Approve / Reject` | deploy/health/rollback evidence | |
| Release authority | `_____` | `Approve / Reject` | complete Gate 7 bundle | |

---

## 9. Exit Criteria

`G7-03` is considered complete for a release candidate only when:

- this checklist is fully executed
- all required rows have a recorded result
- no blocking failures remain open
- signoff decisions are attached to `evidence/releases/<release-id>/signoff.md`

Without that evidence, Gate 7 remains incomplete even if automated tests are green.
