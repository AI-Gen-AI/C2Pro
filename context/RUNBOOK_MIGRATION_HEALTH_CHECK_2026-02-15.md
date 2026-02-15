# Migration Health Runbook

Date: `2026-02-15`  
Scope: `WS-A Migration Repair and DB Determinism`

## Objective
Guarantee that Alembic migrations can be applied from a clean database state to head revision deterministically.

## Files
- `apps/api/alembic/versions/20260124_0001_add_raci_evidence_text.py`
- `apps/api/alembic/versions/20260124_0002_add_approval_status.py`
- `apps/api/scripts/verify_migration_health.py`

## Prerequisites
1. PostgreSQL reachable on `localhost:5433`.
2. Admin credentials available for database creation:
   - `postgresql://postgres:postgres@localhost:5433/postgres`
3. Python environment with:
   - `psycopg`
   - `alembic`

## Standard Verification Command
```powershell
python apps/api/scripts/verify_migration_health.py --recreate-db
```

## What the Verifier Checks
1. Parses Alembic revisions and validates a linear chain:
   - exactly one root
   - exactly one head
   - no cycles
   - no disconnected revisions
2. Recreates `c2pro_test` from scratch.
3. Runs `alembic upgrade head`.
4. Verifies `alembic_version.version_num` equals expected head revision.

## Expected Success Output
```text
OK migration graph: <N> files, head=<REVISION>
OK recreated database: c2pro_test
OK alembic upgrade head
OK alembic_version matches expected head
```

## Notes on Safety Patches
Migrations `20260124_0001` and `20260124_0002` were hardened to avoid failing when legacy tables are absent:
- table existence checks
- column existence checks
- index existence checks
- downgrade guarded similarly

This preserves forward progress for environments where those tables are introduced later or managed by separate modules.
