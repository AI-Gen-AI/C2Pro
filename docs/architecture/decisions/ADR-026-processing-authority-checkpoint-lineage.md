# ADR-026 — Processing Authority, Checkpoint Lineage and HITL Resume Fencing

**Status:** Accepted  
**Date:** 2026-10-01  
**Decision owners:** #711, #758  
**Implementation evidence:** PR #759 merged to `main` at `be0c7c7eac087ea95698362ed7a9a163618f9e9a`  
**Related:** ADR-020; #714 (in-flight Trusted-State Commit)

## Context

#711 introduced durable document-processing ownership with attempts, PostgreSQL-clock leases and fencing tokens. That protected application durable writes, but LangGraph checkpoint writes are persisted independently by `AsyncPostgresSaver`.

Pre-#758, all attempts shared:

`document:{document_id}:analysis`

A stale worker could append after takeover and a current worker could then select that stale checkpoint as "latest". The metadata write could be correctly fenced while the checkpoint value being attached belonged to a stale authority.

## Decision

### 1. Durable processing authority
`document_processing_operations` owns the current document-processing authority.

The grant includes `tenant_id`, `document_id`, `revision_id`, `generation`, stage, `attempt_id`, `owner_token` and monotonic `fencing_token`, governed by a PostgreSQL-clock lease.

### 2. In-transaction canonical write fencing
Canonical durable mutations re-check the exact grant under row lock **inside the transaction performing the business mutation**. Stale/expired/superseded grants fail closed.

### 3. Generation boundary
`begin_generation` advances generation and fence atomically with a reprocess/new-revision reset. Prior workers/review lineages become non-current at that boundary.

### 4. Authority-scoped LangGraph lineage
Normal owned analysis uses:

`document:{document_id}:g{generation}:f{fencing_token}:analysis`

A stale attempt may still append to its old thread, but that lineage is unreachable from the current authority.

### 5. Exact HITL checkpoint tuple
Review/resume binds exact persisted:
- `thread_id`;
- `checkpoint_ns`;
- `checkpoint_id`;

plus processing-lineage generation/fencing metadata where applicable.

### 6. Resume/recovery lineage comparison
HITL acquisition/recovery compares durable operation lineage with current review lineage under lock. A superseded lineage becomes deterministic non-actionable history (for example `LINEAGE_SUPERSEDED`), not a silently rebound current operation.

### 7. Legacy compatibility
`document:{document_id}:analysis` remains compatibility-only for no-authority/legacy paths. Owned production analysis must not create normal work on the shared lineage.

## Invariants

1. A stale processing attempt cannot become the current review's checkpoint lineage.
2. "Latest checkpoint" is safe only inside an authority-pure thread.
3. Reprocess/new revision invalidates prior processing/review lineage at generation transition.
4. HITL replays the checkpoint the human decision was authorized against.
5. Recovery cannot revive a superseded lineage because its durable row still exists.
6. Stale checkpoint evidence may remain append-only/auditable but non-canonical and non-actionable.
7. Application-write fencing and graph-lineage fencing are complementary.

## Consequences

**Benefits:** deterministic takeover, exact provenance, resilient HITL retry/recovery, preserved audit history.

**Costs:** more checkpoint threads, more lineage identity in review/resume records, explicit legacy compatibility handling, operator tooling must understand generation/fence.

## Alternatives rejected

- shared document thread + latest checkpoint;
- fencing only the metadata write;
- deleting stale checkpoints;
- application wall-clock ownership;
- folding #714 trusted-state semantics into #758.

#758 is a lower-level execution-lineage authority. #714 owns a separate canonical/trusted-state decision.

## Evidence

- #711 — durable Celery delivery and bounded recovery.
- #758 — stale-checkpoint race/invariant.
- PR #759 — implementation.
- `test_758_checkpoint_lineage_authority_fence.py`
- `test_758_stale_resume_operation_lineage.py`
- checkpoint-lineage unit tests.
- HITL V3 fencing/endpoint integration tests.
