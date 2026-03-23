# Task B-3 Hard Proof Report

Task: `B-3` (`AUDIT-TASK-3.1`)
Date: 2026-03-21
Owner: Team Bravo - Nexus (AI & Core Backend)
Status: `COMPLETE` (checkpoint persistence proven and full analysis flow restored)

Status update (2026-03-22): Verification was re-run in the current local stack. `python -m pytest tests/unit/core/ai/test_langgraph_checkpointer.py` passed (`9 passed`), and `DATABASE_URL_ASYNC=postgresql+asyncpg://postgres:postgres@localhost:5432/c2pro python apps/api/scripts/verify_langgraph_checkpointer.py` reported `[SUCCESS] ALL CHECKS PASSED!` with existing checkpoint rows present in PostgreSQL.

## What Was Fixed

1. Aligned LangGraph checkpointer schema to package expectations (v3-compatible):
   - `checkpoints`
   - `checkpoint_writes` (`blob BYTEA`, `task_path TEXT`)
   - `checkpoint_blobs`
   - `checkpoint_migrations`
2. Removed schema drift source (`ai_checkpoints`/`value JSONB` mismatch) from active migration path.
3. Added deterministic startup initialization:
   - `ensure_checkpointer_ready()` now runs during FastAPI lifespan startup.
   - `AsyncPostgresSaver.setup()` is executed once before traffic.
4. Added shutdown cleanup for checkpointer pool resources.

## Files Changed

- `apps/api/src/analysis/adapters/graph/workflow.py`
- `apps/api/src/main.py`
- `apps/api/alembic/versions/20260320_0001_add_langgraph_checkpointer.py`
- `infrastructure/supabase/migrations/016_langgraph_checkpoints.sql`
- `apps/api/tests/unit/core/ai/test_langgraph_checkpointer.py`
- `apps/api/scripts/verify_langgraph_checkpointer.py`

## SQL Snapshot Proof

### checkpoint_writes column contract

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name='checkpoint_writes'
ORDER BY ordinal_position;
```

Observed:

```text
thread_id text NOT NULL
checkpoint_ns text NOT NULL
checkpoint_id text NOT NULL
task_id text NOT NULL
idx integer NOT NULL
channel text NOT NULL
type text NULL
blob bytea NOT NULL
task_path text NOT NULL
```

### checkpoint index snapshot

```sql
SELECT tablename, indexname
FROM pg_indexes
WHERE tablename IN ('checkpoints','checkpoint_writes','checkpoint_blobs')
ORDER BY tablename, indexname;
```

Observed:

```text
checkpoint_blobs_pkey
checkpoint_blobs_thread_id_idx
checkpoint_writes_pkey
checkpoint_writes_thread_id_idx
idx_checkpoint_writes_lookup
checkpoints_pkey
checkpoints_thread_id_idx
idx_checkpoints_parent
idx_checkpoints_thread_id
```

### checkpoint row counts after E2E run

```sql
SELECT
  (SELECT COUNT(*) FROM checkpoints) AS checkpoints,
  (SELECT COUNT(*) FROM checkpoint_writes) AS checkpoint_writes,
  (SELECT COUNT(*) FROM checkpoint_blobs) AS checkpoint_blobs,
  (SELECT COUNT(*) FROM checkpoint_migrations) AS checkpoint_migrations;
```

Observed (final run):

```text
checkpoints: 35
checkpoint_writes: 684
checkpoint_blobs: 183
checkpoint_migrations: 9
```

### recent persisted checkpoints

```sql
SELECT thread_id, checkpoint_id, (metadata->>'step') AS step, metadata->>'source' AS source
FROM checkpoints
ORDER BY checkpoint_id DESC
LIMIT 5;
```

Observed: same `thread_id` with sequential `step` values (`10..14`), source `loop`.

## Test Output Proof

### E2E execution

Command:

```bash
python scripts/test_checkpointer_e2e.py
```

Key output (verbatim highlights, final run):

```text
[Step 1] checkpoints - EXISTS (16 rows)
[Step 5] Analysis completed
Status: 200
WBS items: 13
[Step 7] Final Database State:
  checkpoints       - [OK] EXISTS with 35 rows
  checkpoint_writes - [OK] EXISTS with 684 rows
  checkpoint_blobs  - [OK] EXISTS with 183 rows

[SUCCESS] SUCCESS - Checkpointer is working!
The LangGraph PostgreSQL checkpointer is functioning correctly.
Workflow state will persist across process restarts.
```

### WBS uniqueness bug closure

Root cause fixed: global uniqueness on `procurement_wbs_items.code` caused false cross-project collisions in `save_to_db`.

Applied DB and model changes:

- Unique constraint moved to project scope: `UNIQUE (project_id, code)`
- Parent relation scoped by project: `FOREIGN KEY (project_id, parent_code) REFERENCES procurement_wbs_items(project_id, code)`

Constraint snapshot:

```sql
SELECT conname, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'procurement_wbs_items'::regclass
  AND contype IN ('u','f')
ORDER BY conname;
```

Observed:

```text
fk_wbs_parent_per_project       FOREIGN KEY (project_id, parent_code) REFERENCES procurement_wbs_items(project_id, code) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED
uq_procurement_wbs_project_code UNIQUE (project_id, code)
```

### Verification script

Command:

```bash
DATABASE_URL_ASYNC=postgresql+asyncpg://postgres:postgres@localhost:5432/c2pro \
python apps/api/scripts/verify_langgraph_checkpointer.py
```

Key output:

```text
[OK] PASS - Package
[OK] PASS - Database
[OK] PASS - Initialization
[OK] PASS - Write Read
[OK] PASS - Compilation
[OK] PASS - Existing

[SUCCESS] ALL CHECKS PASSED!
Task B-3 (AUDIT-TASK-3.1) verification: [OK] COMPLETE
```

## Conclusion

B-3 is complete with hard proof.

- Schema compatibility issue is fixed.
- Startup now guarantees checkpointer migrations/setup run before serving requests.
- End-to-end execution writes checkpoint state transitions to PostgreSQL and can be inspected directly in SQL.
- Analysis endpoint now completes with HTTP `200` in the same E2E run where checkpoints are persisted.
