# Release Signoff

## Release Identity

- Release ID: `2026-03-24-rc1`
- Commit SHA: `4a63abb40d9966557237888670a528ffc85ce80f`
- Promotion window: `Local Gate 7 live-runtime swagger verification`

## Required Approvals

| Area              | Required approver role       | Approved by | Approved at | Decision | Notes                                                                                          |
| ----------------- | ---------------------------- | ----------- | ----------- | -------- | ---------------------------------------------------------------------------------------------- |
| Product           | `Product Owner`             | `pending`   | `pending`   | Pending  | Swagger workbook is complete; awaiting release-time suite evidence and formal approval.        |
| Security          | `Security Lead`             | `pending`   | `pending`   | Pending  | Awaiting required security workflow evidence and formal approval.                              |
| Operations        | `Operations / SRE Lead`     | `pending`   | `pending`   | Pending  | Performance and DR evidence are refreshed; workflow artifacts and ops approval remain pending. |
| Release authority | `Engineering Leadership`    | `pending`   | `pending`   | Pending  | Candidate is not certifiable until the suite matrix and approvals are complete.                |

## Approval Preconditions

All of the following must be true before manual approval can be recorded:

- [ ] `manifest.yaml` required suites are green or formally waived for the release type
- [ ] UAT/manual QA execution is recorded in `docs/UAT_CHECKLIST.md` release evidence
- [ ] Performance evidence is attached and accepted
- [ ] DR evidence is attached and accepted
- [ ] Candidate commit SHA remains frozen

## Supporting References

- Swagger workbook evidence: `docs/internal/SWAGGER_ENDPOINT_WORKBOOK.md`
- Swagger verification report: `evidence/releases/2026-03-24-rc1/swagger-verification.md`
- Required suite matrix: `.github/workflows/tests.yml`, `.github/workflows/frontend-ci.yml`, `.github/workflows/e2e-security-tests.yml`, `.github/workflows/evaluation-regression.yml`, `.github/workflows/i13-real-e2e-scheduled.yml`
- UAT/manual QA evidence: `docs/UAT_CHECKLIST.md` (release-time execution record still pending)
- Performance/capacity evidence: `docs/SLA_TARGETS.md` + `evidence/releases/2026-03-24-rc1/performance.md`

## Performance Signoff Reference

- Gate item: `G7-04`
- Target source: `docs/SLA_TARGETS.md`
- Completed evidence: `evidence/releases/2026-03-24-rc1/performance.md`
- Status: `Referenced in final signoff bundle`

## Blocking Items

- [ ] Required suite artifacts remain pending in `manifest.yaml` for `backend`, `frontend`, and `security`.
- [ ] Manual approvals remain pending for product, security, operations, and release authority.
- [ ] Current `manifest.yaml` still reports failing required suites for `backend`, `frontend`, and `security`, so formal signoff is blocked for this candidate.
