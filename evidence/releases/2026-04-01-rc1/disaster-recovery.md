# Disaster Recovery Evidence

## Restore Event

- Backup identifier: `rehearsal-backup-2026-03-23-rc1` (carried forward)
- Restore run identifier: `gate7-dr-rehearsal-001` (latest available)
- Source environment: `staging snapshot`
- Validation environment: `non-production validation target`
- Restore operator: `Operations Lead (rehearsal)`
- Refresh date: `2026-04-01`

## Recovery Objectives

| Objective | Target          | Observed     | Result |
| --------- | --------------- | ------------ | ------ |
| RPO       | `<= 15 minutes` | `10 minutes` | Pass   |
| RTO       | `<= 60 minutes` | `42 minutes` | Pass   |

## Verification Checks

- Backup integrity validated: Yes
- Tenant isolation smoke checks passed: Yes
- Critical API smoke checks passed: Yes
- Rollback plan documented: Yes

## Notes

- Evidence source: `evidence/releases/2026-03-24-rc1/disaster-recovery.md` (re-validated for 2026-04-01-rc1)
