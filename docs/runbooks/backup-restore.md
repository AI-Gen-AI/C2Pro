# Backup and Restore Runbook

## Purpose

Define the minimum repeatable procedure to back up and restore C2Pro data safely.

## Scope

- PostgreSQL backup and restore workflow.
- Verification checkpoints before and after restore.
- Escalation path for restore incidents.

## Procedure Overview

1. Confirm target environment and maintenance window.
2. Create timestamped backup artifact.
3. Validate backup integrity.
4. Restore into a non-production validation target first.
5. Run smoke checks and data integrity checks.
6. Promote restore to target environment only after validation sign-off.

## Notes

- Never run restore directly in production without an approved rollback plan.
- Keep tenant isolation validation in the post-restore checks.

## Gate 7 Evidence Record

Every certification bundle under `evidence/releases/<release-id>/` MUST capture:

- backup identifier
- restore run identifier
- source and validation environments
- restore operator and approver
- observed RPO and RTO
- backup integrity result
- tenant isolation verification result
- critical API smoke check result
- exceptions, follow-up actions, or waivers

Recommended artifact: `evidence/releases/<release-id>/disaster-recovery.md`.

---

Last Updated: 2026-02-13

Changelog:

- 2026-02-13: Added initial runbook scaffold for backup and restore operations.
