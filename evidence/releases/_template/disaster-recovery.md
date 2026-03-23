# Disaster Recovery Evidence Template

## Restore Event

- Backup identifier: `<backup-id>`
- Restore run identifier: `<restore-run-id>`
- Source environment: `<source>`
- Validation environment: `<target>`
- Restore operator: `<name>`

## Recovery Objectives

| Objective | Target     | Observed     | Result      |
| --------- | ---------- | ------------ | ----------- |
| RPO       | `<target>` | `<observed>` | Pass / Fail |
| RTO       | `<target>` | `<observed>` | Pass / Fail |

## Verification Checks

- Backup integrity validated: Yes / No
- Tenant isolation smoke checks passed: Yes / No
- Critical API smoke checks passed: Yes / No
- Rollback plan documented: Yes / No

## Notes

- Exceptions or follow-up actions: `<notes>`
