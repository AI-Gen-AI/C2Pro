# Gate 7 Release Evidence Bundles

Gate 7 release certification is tracked in `evidence/releases/<release-id>/`.

Each release bundle MUST contain:

- `manifest.yaml` - canonical status for required suites, signoff, performance, and DR evidence
- `signoff.md` - explicit product, security, operations, and release authority approvals
- `performance.md` - acceptance targets, measured results, and variance notes
- `disaster-recovery.md` - backup, restore, and post-restore verification evidence

Recommended release id format:

- `YYYY-MM-DD-rcN` for release candidates
- `YYYY-MM-DD-hotfixN` for hotfix releases

Bundle rules:

- The bundle MUST reference the exact commit SHA being promoted.
- The bundle MUST point to the workflow runs or artifacts used for the required suite matrix.
- Waivers MUST be recorded in `manifest.yaml` with owner, risk, mitigation, and expiration date.
- Gate 7 is incomplete until all required files are present and approvals are explicit.

Template files live in `evidence/releases/_template/`.
