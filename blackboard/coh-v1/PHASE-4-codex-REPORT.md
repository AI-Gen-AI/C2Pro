# TASK-COH-V1-04 Phase 4 Report

## Summary

Added Coherence Score v1 audit-trail fields to persistence, exposed them through repository/domain DTOs, added a placeholder v1 cut-off constant, shipped a UI badge stub, and documented the no-recompute policy in ADR-002.

## Changed

- Added Alembic migration `apps/api/alembic/versions/20260425_0001_coherence_score_versioning.py`.
- Added `score_version`, `score_reason`, and `score_missing_dimensions` to `CoherenceResultORM`.
- Extended `CoherenceCalculationResult`, `CoherenceResult`, and `EnrichedCoherenceResult`.
- Updated `SqlAlchemyCoherenceRepository.save()` and read mappings.
- Added `SCORE_VERSION_V1_CUTOFF` placeholder in `apps/api/src/coherence/config.py`.
- Added `apps/web/src/components/coherence/ScoreVersionBadge.tsx` and smoke test.
- Added `docs/architecture/adr/ADR-002-coherence-score-versioning.md`.

## Migration SQL

```sql
SET LOCAL lock_timeout = '5s';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'coherence_score_version') THEN
        CREATE TYPE coherence_score_version AS ENUM ('v0_flag_based', 'v1_exponential_decay');
    END IF;
END
$$;

ALTER TABLE coherence_results
ADD COLUMN IF NOT EXISTS score_version coherence_score_version
    NOT NULL DEFAULT 'v0_flag_based';

ALTER TABLE coherence_results
ADD COLUMN IF NOT EXISTS score_reason TEXT;

ALTER TABLE coherence_results
ADD COLUMN IF NOT EXISTS score_missing_dimensions JSONB;
```

Downgrade drops the three columns and then `DROP TYPE IF EXISTS coherence_score_version`.

## RLS Review

Existing `coherence_results` RLS policy filters through `projects.tenant_id` and does not reference score columns. No policy update is required.

## Verification

- `pnpm vitest run src/components/coherence/ScoreVersionBadge.test.tsx`: PASS.
- `pnpm tsc --noEmit`: PASS.
- `python -m compileall` for touched backend modules/migration: PASS.
- `python -m alembic heads`: PASS, single head `20260425_0001`.
- `pytest tests/integration/coherence/test_repository.py -xvs`: BLOCKED, no reachable local test Postgres (`postgres-test` DNS failure).
- `alembic upgrade head --sql`: BLOCKED before this migration by older offline-incompatible migrations using live inspection/connection methods against Alembic `MockConnection`.
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`: BLOCKED, Docker daemon is not running and local Supabase Postgres on `localhost:54322` refused connection.

## PR

Title: `feat(coherence): score_version migration + ADR-002`
