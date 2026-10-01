# LangGraph PostgreSQL Checkpointing and Lineage

**Status:** Current supporting architecture  
**Updated:** 2026-10-01  
**Canonical decision:** ADR-026  
**Package contract:** `langgraph-checkpoint-postgres==3.1.2`

## Purpose

C2Pro persists LangGraph workflow state in PostgreSQL so analysis can survive process restarts, HITL interruptions and bounded recovery.

Checkpoint storage is **not** the authority for which worker may publish canonical application state. Processing authority and checkpoint lineage are separate but coordinated boundaries.

## Schema ownership

The checkpoint schema is package-managed by `AsyncPostgresSaver.setup()`, including `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` and migration metadata. Do not maintain a parallel `ai_checkpoints` schema.

`apps/api/scripts/checkpoint_bootstrap.py` is the only application path allowed to run `setup()`; it requires owner/bootstrap authority.

Runtime:
- uses restricted checkpoint access;
- performs no checkpoint DDL;
- verifies the exact supported package version;
- performs read-only schema readiness;
- fails closed when a configured PostgreSQL backend is unreachable/outdated.

## Processing authority vs checkpoint storage

`document_processing_operations` owns canonical processing authority. Checkpoint writes happen through LangGraph outside that business transaction, so checkpoint **selection** is fenced by lineage identity.

## Authority-scoped analysis threads

Normal owned analysis uses:

`document:{document_id}:g{generation}:f{fencing_token}:analysis`

A stale worker can append only to its old lineage. Current work never asks for "latest checkpoint across all attempts for this document".

Historical `document:{document_id}:analysis` is compatibility-only for execution without bound processing authority.

## HITL checkpoint identity

A pending review records the graph lineage and interrupt checkpoint. Resume uses exact persisted:
- `thread_id`;
- `checkpoint_ns`;
- `checkpoint_id`.

Review persistence also carries processing-lineage generation/fencing metadata.

A new generation/reprocess invalidates the prior review lineage at the generation boundary. Resume/recovery rejects superseded lineage rather than selecting another attempt's newer checkpoint.

## Runtime readiness

At startup:
1. verify package version;
2. open checkpoint pool;
3. verify schema floor marker;
4. refuse startup for unavailable/outdated configured PostgreSQL checkpoint backend.

SQLite/test-only execution may explicitly use in-memory checkpointing where allowed. PostgreSQL production-like execution must not silently downgrade because infrastructure failed.

## Operational bootstrap

Run:
`python apps/api/scripts/checkpoint_bootstrap.py`

Any checkpoint-package upgrade requires a deliberate pin change, owner bootstrap migration, readiness/security tests and checkpoint/HITL regression proof.

## Failure/recovery semantics

- takeover creates a newer fence and different graph thread;
- stale checkpoints remain historical evidence;
- HITL recovery compares durable operation lineage to current review lineage;
- superseded lineage is non-actionable, not silently rebound;
- missing immutable checkpoint identity fails closed/escalates according to the HITL recovery contract.

## Verification surfaces

Representative tests:
- `apps/api/tests/security/test_c2_checkpoint_boundary.py`;
- `apps/api/tests/unit/core/ai/test_langgraph_checkpointer.py`;
- `apps/api/tests/integration/document_flow/test_758_checkpoint_lineage_authority_fence.py`;
- `apps/api/tests/modules/integration/test_758_stale_resume_operation_lineage.py`;
- `apps/api/tests/modules/integration/test_p0b_checkpoint_tuple_restore_hotfix.py`;
- HITL V3 fencing tests.

## Non-goal

This guide does not promote #714 Trusted-State Commit to accepted/landed behavior.
