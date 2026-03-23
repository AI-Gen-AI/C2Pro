# Release Signoff

## Release Identity

- Release ID: `2026-03-23-rc1`
- Commit SHA: `c1b0c73dfb07ea1904bdbc51d2917cc69b6e7d51`
- Promotion window: `Rehearsal validation window for Gate 7 flow`

## Required Approvals

| Area              | Owner                         | Decision | Notes                                                                           |
| ----------------- | ----------------------------- | -------- | ------------------------------------------------------------------------------- |
| Product           | `Product Owner (rehearsal)`   | Approve  | Rehearsal bundle validates repo-backed signoff shape only.                      |
| Security          | `Security Lead (rehearsal)`   | Approve  | Security evidence references the required workflow summary artifact.            |
| Operations        | `Operations Lead (rehearsal)` | Approve  | DR and rollback sections present for release-flow rehearsal.                    |
| Release authority | `Release Manager (rehearsal)` | Approve  | Approval is limited to Gate 7 promotion-flow rehearsal, not production release. |

## Supporting References

- Required suite matrix: `.github/workflows/tests.yml`, `.github/workflows/frontend-ci.yml`, `.github/workflows/e2e-security-tests.yml`, `.github/workflows/evaluation-regression.yml`, `.github/workflows/i13-real-e2e-scheduled.yml`
- Swagger workbook evidence: `docs/internal/SWAGGER_ENDPOINT_WORKBOOK.md`
- Rollback owner: `Operations Lead (rehearsal)`
- Incident reference, if any: `none`
