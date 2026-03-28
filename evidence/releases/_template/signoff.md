# Release Signoff Template

## Release Identity

- Release ID: `YYYY-MM-DD-rcN`
- Commit SHA: `<git-sha>`
- Promotion window: `<window>`

## Required Approvals

| Area              | Required approver role    | Approved by | Approved at | Decision         | Notes     |
| ----------------- | ------------------------- | ----------- | ----------- | ---------------- | --------- |
| Product           | `<role>`                  | `<name>`    | `<datetime>`| Approve / Reject | `<notes>` |
| Security          | `<role>`                  | `<name>`    | `<datetime>`| Approve / Reject | `<notes>` |
| Operations        | `<role>`                  | `<name>`    | `<datetime>`| Approve / Reject | `<notes>` |
| Release authority | `<role>`                  | `<name>`    | `<datetime>`| Approve / Reject | `<notes>` |

## Approval Preconditions

- [ ] `manifest.yaml` required suites are green or formally waived
- [ ] UAT/manual QA execution record is attached
- [ ] Performance evidence is attached
- [ ] DR evidence is attached
- [ ] Candidate commit SHA is frozen

## Supporting References

- Required suite matrix: `<workflow runs or artifacts>`
- Swagger workbook evidence: `<links or notes>`
- UAT/manual QA evidence: `docs/UAT_CHECKLIST.md` + release-time completed checklist notes
- Performance/capacity evidence: `docs/SLA_TARGETS.md` + `evidence/releases/<release-id>/performance.md`
- Rollback owner: `<name>`
- Incident reference, if any: `<id or none>`
