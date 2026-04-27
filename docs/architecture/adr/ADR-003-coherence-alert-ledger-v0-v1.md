# ADR-003: Coherence Alert Ledger Migration v0 → v1

## Status

Accepted

## Context

Coherence v1 introduces:

1. New `AUDIT_INCOMPLETE` meta-alert type for insufficient evidence
2. Fingerprint-based deduplication for alerts
3. Auto-resolution when violations are no longer detected
4. Bilingual templates (Spanish default, English optional)

Existing alerts created under v0 must remain immutable for audit trail integrity.

## Decision

**Cut-off migration strategy:**

1. **Immutable Legacy**: All alerts created before v1 cut-off remain in the legacy ledger. They are:
   - Marked with a migration flag in `alert_metadata`
   - NOT backfilled or recomputed
   - Read-only in queries

2. **New v1 Ledger**: Alerts created after v1 activation use:
   - Fingerprint deduplication
   - Auto-resolution via `AlertGeneratorService.process_violations()`
   - `AUDIT_INCOMPLETE` type for missing dimensions

3. **Cut-Off Date**: Defined in `apps/api/src/coherence/config.py` as `ALERT_V1_CUTOFF`. Default: `datetime(2026, 5, 1, tzinfo=timezone.utc)`.

4. **Data Archival**: Old alerts are archived but queryable:
   - Query parameter `include_archived=true` returns legacy alerts
   - API filter `alert_version: "v0"|"v1"|"all"` for distinction
   - Dashboard shows version badge on each alert

## Migration Path

```
Before v1:
  - Alerts table: legacy rows only
  - No fingerprint dedup
  - No auto-resolution
  - No AUDIT_INCOMPLETE type

After v1 activation:
  - New rows: fingerprint dedup + auto-resolution + AUDIT_INCOMPLETE
  - Old rows: marked archived but immutable
  - Combined query returns all by default
```

## Consequences

1. **Database**: New `alert_metadata` JSONB column stores `fingerprint`, `version: "v1"`.
2. **API**: New `alert_type` includes `AUDIT_INCOMPLETE`.
3. **Dashboard**: Version badges on alerts, filter by version.
4. **Backwards Compatibility**: Existing `AlertGenerator` continues to work for v0 paths.

## Cut-Off Owner

Phase 9 owns the final activation date after UX review, customer communication, and QA sign-off.

## References

- TASK-COH-V1-06: Alert generation wiring + meta_alert
- ADR-002: Coherence Score Versioning ( precedent for immutable historical rows )
