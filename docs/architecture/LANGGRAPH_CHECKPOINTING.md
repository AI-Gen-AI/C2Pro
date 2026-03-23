# LangGraph PostgreSQL Checkpointing

**Task:** B-3 (AUDIT-TASK-3.1)
**Status:** ✅ Implemented
**Date:** 2026-03-20

---

## Overview

This document describes the LangGraph PostgreSQL checkpointing implementation for C2Pro's AI orchestration workflows. Checkpointing enables persistent state management, allowing workflows to be resumed after interruptions, restarts, or failures.

## Purpose

The checkpointing system provides:

1. **Workflow Resumption**: Resume interrupted analysis workflows after process restarts
2. **Manual Recovery**: Manually recover and inspect stalled analysis runs
3. **State Inspection**: Debug workflow execution by examining checkpoint state
4. **Audit Trail**: Track workflow execution progress through state transitions
5. **Reliability**: Ensure no analysis work is lost due to system failures

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                 LangGraph Workflow                      │
│  (N1 → N2 → ... → N16 orchestration nodes)             │
└──────────────────┬──────────────────────────────────────┘
                   │ Automatic checkpointing
                   ▼
┌─────────────────────────────────────────────────────────┐
│            AsyncPostgresSaver                            │
│  (langgraph-checkpoint-postgres)                        │
└──────────────────┬──────────────────────────────────────┘
                   │ Persist state
                   ▼
┌─────────────────────────────────────────────────────────┐
│           PostgreSQL Tables                             │
│  - ai_checkpoints: Main checkpoint storage              │
│  - checkpoint_writes: Write tracking                    │
└─────────────────────────────────────────────────────────┘
```

### Database Schema

#### `ai_checkpoints` Table

Stores workflow checkpoint state:

```sql
CREATE TABLE ai_checkpoints (
    thread_id TEXT NOT NULL,              -- Workflow execution identifier
    checkpoint_ns TEXT NOT NULL DEFAULT '',-- Namespace for checkpoint grouping
    checkpoint_id TEXT NOT NULL,          -- Unique checkpoint ID (UUID)
    parent_checkpoint_id TEXT,            -- Previous checkpoint reference
    type TEXT,                            -- Checkpoint type
    checkpoint JSONB NOT NULL,            -- Serialized workflow state
    metadata JSONB NOT NULL DEFAULT '{}', -- Additional metadata
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
```

**Indexes:**
- `idx_ai_checkpoints_thread_id` - Fast lookups by thread
- `idx_ai_checkpoints_parent` - Checkpoint chain traversal

#### `checkpoint_writes` Table

Tracks individual writes within checkpoints:

```sql
CREATE TABLE checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,              -- Task that performed the write
    idx INTEGER NOT NULL,               -- Write sequence number
    channel TEXT NOT NULL,              -- Channel name
    type TEXT,                           -- Write type
    value JSONB,                         -- Written value
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
```

**Indexes:**
- `idx_checkpoint_writes_lookup` - Fast lookup by thread/checkpoint

### Security

Both tables have Row Level Security (RLS) enabled with service-level full access policies, as checkpointing is a system-level concern managed by the orchestration layer.

## Implementation

### Configuration

The checkpointer is initialized in `src/analysis/adapters/graph/workflow.py`:

```python
def _build_checkpointer():
    """Build PostgreSQL checkpointer or fallback to memory."""
    from src.config import settings

    # SQLite is not supported for checkpointing
    if settings.database_url_async.startswith("sqlite"):
        logger.warning("checkpointer_fallback",
                      reason="SQLite not supported")
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        return AsyncPostgresSaver.from_conn_string(
            settings.database_url_async,
            table_name="ai_checkpoints",
        )
    except ImportError:
        logger.warning("checkpointer_fallback",
                      reason="langgraph-checkpoint-postgres not installed")
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
```

### Workflow Execution

Workflows use checkpointing via thread configuration:

```python
async def run_orchestration(initial_state: dict, thread_id: str) -> dict:
    """Run LangGraph workflow with checkpointing."""
    app = get_graph_app()  # Includes PostgreSQL checkpointer

    config = {
        "configurable": {
            "thread_id": thread_id  # Enables checkpoint persistence
        },
        "run_name": f"C2Pro_Orchestration_{doc_type}_{project_id}",
        "tags": ["c2pro", "orchestration", doc_type],
    }

    # Workflow automatically saves checkpoints at each node transition
    result = await app.ainvoke(initial_state, config)

    return result
```

## Usage

### Running a Workflow

```python
from src.analysis.adapters.graph.workflow import run_orchestration
from uuid import uuid4

# Create initial state
initial_state = {
    "project_id": str(project_id),
    "tenant_id": str(tenant_id),
    "doc_type": "contract",
    "document_bytes": pdf_bytes,
}

# Generate unique thread ID for this analysis
thread_id = f"analysis_{project_id}_{uuid4()}"

# Run workflow - checkpoints automatically saved
result = await run_orchestration(initial_state, thread_id)
```

### Resuming After Interruption

```python
# To resume a workflow, use the SAME thread_id
# The checkpointer will automatically load the latest checkpoint
thread_id = "analysis_123e4567-e89b-12d3-a456-426614174000_abc123"

# Resume from last checkpoint
result = await run_orchestration(initial_state, thread_id)
```

### Manual Checkpoint Inspection

```python
from src.analysis.adapters.graph.workflow import _build_checkpointer

checkpointer = _build_checkpointer()

# Get latest checkpoint for a thread
config = {"configurable": {"thread_id": thread_id}}
checkpoint = await checkpointer.aget(config)

if checkpoint:
    print(f"Checkpoint ID: {checkpoint.id}")
    print(f"State: {checkpoint}")
```

### Querying Checkpoints

```sql
-- Find all checkpoints for a specific thread
SELECT checkpoint_id, type, metadata
FROM ai_checkpoints
WHERE thread_id = 'analysis_123e4567_...'
ORDER BY checkpoint_id DESC;

-- Count checkpoints per thread
SELECT thread_id, COUNT(*) as checkpoint_count
FROM ai_checkpoints
GROUP BY thread_id
ORDER BY checkpoint_count DESC
LIMIT 10;

-- Find stalled workflows (no recent checkpoints)
SELECT DISTINCT thread_id,
       MAX(metadata->>'step') as last_step,
       COUNT(*) as total_checkpoints
FROM ai_checkpoints
GROUP BY thread_id
HAVING COUNT(*) > 0 AND COUNT(*) < 17  -- Expected 17 nodes (N1-N16 + final)
ORDER BY total_checkpoints ASC;
```

## Verification

### Installation

1. **Install Package:**
   ```bash
   pip install langgraph-checkpoint-postgres>=2.0.0
   ```

2. **Run Migration:**
   ```bash
   # Alembic (preferred)
   cd apps/api
   alembic upgrade head

   # OR direct SQL
   psql $DATABASE_URL < infrastructure/supabase/migrations/016_langgraph_checkpoints.sql
   ```

3. **Verify Installation:**
   ```bash
   python apps/api/scripts/verify_langgraph_checkpointer.py
   ```

### Testing

Run the verification test suite:

```bash
pytest apps/api/tests/unit/core/ai/test_langgraph_checkpointer.py -v
```

The test suite verifies:
- ✅ Checkpointer initializes with PostgreSQL (not MemorySaver)
- ✅ Database tables exist with correct schema
- ✅ Indexes are created for performance
- ✅ RLS policies are enabled
- ✅ Workflow compiles with checkpointer attached

## Monitoring

### Key Metrics

Monitor checkpoint system health:

```sql
-- Checkpoint creation rate (per hour)
SELECT
    DATE_TRUNC('hour', (metadata->>'timestamp')::timestamp) as hour,
    COUNT(*) as checkpoints_created
FROM ai_checkpoints
WHERE (metadata->>'timestamp')::timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;

-- Average checkpoints per workflow
SELECT AVG(checkpoint_count) as avg_checkpoints_per_workflow
FROM (
    SELECT thread_id, COUNT(*) as checkpoint_count
    FROM ai_checkpoints
    GROUP BY thread_id
) subquery;

-- Storage usage
SELECT
    pg_size_pretty(pg_total_relation_size('ai_checkpoints')) as checkpoints_size,
    pg_size_pretty(pg_total_relation_size('checkpoint_writes')) as writes_size;
```

### Alerts

Set up monitoring for:
- Checkpoint table growth rate (alert if > 10GB/day)
- Failed checkpoint writes (alert on ImportError in logs)
- Workflows with incomplete checkpoints (< 17 nodes)

## Troubleshooting

### Fallback to MemorySaver

If you see warnings about MemorySaver fallback:

```
checkpointer_fallback: langgraph-checkpoint-postgres not installed, using MemorySaver
```

**Solutions:**
1. Install the package: `pip install langgraph-checkpoint-postgres>=2.0.0`
2. Verify installation: `python -c "from langgraph.checkpoint.postgres import AsyncPostgresSaver"`
3. Restart the application

### Database Connection Errors

If checkpointer fails to connect:

1. Verify DATABASE_URL_ASYNC is set correctly
2. Check PostgreSQL is running and accessible
3. Verify migrations have been applied
4. Check firewall/network connectivity

### Checkpoint Not Found

If resuming fails to find checkpoint:

1. Verify thread_id is exactly the same (case-sensitive)
2. Check checkpoint exists: `SELECT * FROM ai_checkpoints WHERE thread_id = '...'`
3. Verify checkpoint_ns matches (default is empty string '')

## Performance Considerations

### Checkpoint Size

Each checkpoint stores the complete workflow state. For large documents:
- Average checkpoint size: 50-500 KB
- Typical workflow: 17 checkpoints (N1-N16)
- Total storage per analysis: ~1-8 MB

### Optimization Tips

1. **Pruning Old Checkpoints:**
   ```sql
   -- Delete checkpoints older than 30 days
   DELETE FROM ai_checkpoints
   WHERE (metadata->>'timestamp')::timestamp < NOW() - INTERVAL '30 days';
   ```

2. **Archiving Completed Workflows:**
   ```sql
   -- Move completed workflow checkpoints to archive table
   CREATE TABLE ai_checkpoints_archive AS
   SELECT * FROM ai_checkpoints WHERE thread_id IN (
       SELECT thread_id FROM ai_checkpoints
       GROUP BY thread_id
       HAVING COUNT(*) >= 17  -- Complete workflow
   );
   ```

3. **Index Maintenance:**
   ```sql
   -- Periodically reindex for performance
   REINDEX TABLE ai_checkpoints;
   REINDEX TABLE checkpoint_writes;
   ```

## Migration History

| Version | Date | Description |
|---------|------|-------------|
| 20260320_0001 | 2026-03-20 | Initial checkpointer implementation (Alembic) |
| 016 | 2026-03-20 | Checkpointer tables (Supabase migration) |

## References

- **LangGraph Checkpointing Docs**: https://langchain-ai.github.io/langgraph/concepts/persistence/
- **AsyncPostgresSaver API**: https://langchain-ai.github.io/langgraph/reference/checkpoints/#postgreschecksaver
- **Task B-3**: `docs/planning/MASTER_ORCHESTRATION_BACKLOG_2026-03-19.md`
- **Audit Task 3.1**: `docs/audit/C2PRO_TECHNICAL_AUDIT_REPORT.md`

---

**Last Updated:** 2026-03-20
**Status:** ✅ Production Ready
**Owner:** Team Bravo (Nexus)
