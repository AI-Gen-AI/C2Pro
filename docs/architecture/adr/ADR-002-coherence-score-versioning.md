# ADR-002: Coherence Score Versioning

## Status

Accepted

## Context

Coherence Score v1 changes the scoring semantics from legacy flag-based scoring to the canonical exponential-decay model. Existing `coherence_results` rows may already have been used in customer-facing audit decisions, so historical rows must remain immutable.

The Coherence Score v1 PRD explicitly forbids historical recomputation because it would rewrite the audit trail, introduce legal exposure, and spend API/runtime budget on results that customers may already have cited.

## Decision

Add explicit score-version audit fields to `coherence_results`:

- `score_version`: enum with `v0_flag_based` and `v1_exponential_decay`, defaulting to `v0_flag_based`.
- `score_reason`: nullable machine-readable reason for unavailable or version-specific score handling.
- `score_missing_dimensions`: nullable JSONB list of missing dimensions when evidence is insufficient.

Rows created before the v1 cut-off remain `v0_flag_based`. Rows created after the cut-off can use `v1_exponential_decay` once Phase 9 activates the live date. No historical recomputation or backfill to v1 is allowed.

## Cut-Off

`apps/api/src/coherence/config.py` defines `SCORE_VERSION_V1_CUTOFF = datetime(2026, 5, 1, tzinfo=timezone.utc)` as a placeholder. This is marked TBD-final-date. Phase 9 owns the final activation date after dashboard UX, customer communication, and QA sign-off.

## Consequences

The API can expose score version and reason fields so users can distinguish legacy audit rows from v1 rows. Customer-facing copy, tooltip details, and the final dashboard styling are deferred to Phase 9. Old alerts and old score rows remain immutable; new v1 outputs are appended under the new score-version contract.
