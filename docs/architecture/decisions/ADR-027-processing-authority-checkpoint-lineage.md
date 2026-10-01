# ADR-027: Processing Authority and Checkpoint-Lineage Fencing

**Status:** Accepted / implemented on `main`  
**Date:** 2026-10-01  
**Decision class:** Concurrency, recovery and workflow-state integrity  
**Implementation lineage:** #711 and #758 / PR #759  
**Basis:** Retrospective codification of the accepted issue/PR contracts and merged implementation evidence; this ADR creates no new runtime authority.
**Related:** ADR-015, ADR-017, ADR-020, ADR-026

## Context

Late acknowledgement and worker-loss recovery make document processing durable, but redelivery introduces concurrency. Application writes were already protected by processing authority/fencing, while LangGraph checkpoints could still be appended under a shared document thread.

That created a split-brain risk: after worker B takes ownership, stale worker A could append a later checkpoint, and a thread-only “latest checkpoint” lookup could bind B's current review to A's stale execution.

## Decision

Processing authority applies to **both application durable state and selectable workflow checkpoint lineage**.

Each processing generation/attempt is bound to a deterministic authority identity. After takeover, reprocess or revision supersession:

- a stale attempt cannot perform canonical durable mutation;
- its checkpoint evidence may remain append-only, but cannot become selectable as the current lineage;
- current review metadata binds the authority-scoped processing thread and, when capture succeeds, the exact checkpoint tuple;
- HITL resume uses the exact persisted checkpoint identity when present; if no checkpoint ID was captured, thread-only recovery may resolve the latest checkpoint only inside that same authority-scoped attempt lineage;
- absence of an exact checkpoint identity can never fall back across an authority boundary.

## Locking / ordering rule

Finalization and generation transitions must acquire authority in a deterministic order that prevents a stale finalizer from committing after a newer generation becomes authoritative.

The document/generation authority boundary is therefore part of workflow correctness, not a best-effort optimization.

## Invariants

- **PA-1:** after fence `N+1` is acquired, fence `N` cannot make later canonical durable writes.
- **PA-2:** stale checkpoint lineage cannot be selected as current after takeover.
- **PA-3:** current review/checkpoint binding belongs to the current authority generation.
- **PA-4:** HITL resumes the exact persisted checkpoint tuple when available; otherwise thread-only fallback is confined to the same authority-scoped attempt lineage.
- **PA-5:** retry/redelivery remains idempotent and does not duplicate review/trusted effects.
- **PA-6:** reprocess/new revision creates a new generation boundary.
- **PA-7:** “latest checkpoint by document thread” is insufficient across ownership changes.

## Consequences

**Positive**

- recovery no longer trades availability for state corruption;
- LangGraph state and application state share one authority model;
- exact HITL review binding in ADR-026 becomes meaningful.

**Constraints**

- checkpoint namespace/thread identity must encode or bind processing lineage;
- tests must include real concurrent/stale-writer races, not only sequential mocks;
- maintenance code must preserve lock/fence ordering.

## Alternatives rejected

- **Shared thread + latest checkpoint lookup:** rejected because stale writers can win by timestamp/order.
- **Fence only application tables:** rejected because workflow checkpoint selection can still corrupt the canonical continuation.
- **Delete stale checkpoints:** not required; stale evidence may remain if it is deterministically non-selectable.

## Validation status

The fencing implementation and race tests are merged on `main`. Full production end-user qualification remains separate and is not implied by this ADR.
