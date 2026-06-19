# ADR-015: Temporal Intelligence Layer

**Status:** Accepted — P0 (Foundation) · C2Pro v3.0 canon
**Date:** 2026-06-07
**Deciders:** Jesús Camacho (VP Engineering)
**Basis:** Multi-model arbitration — DeepSeek / Codex / Claude / Gemini v3.0 ADR blueprints + Architecture Challenger verdict.
**Related:** ADR-014 (aggregate); ADR-016 (consumes revisions/deltas); ADR-018 (consumes snapshots for trends).

## Context

"Version" is currently an integer counter: `ReuploadDocumentUseCase` does a SHA-256 compare, increments `version`, resets status, and re-processes — there is **no revision lineage, no event store, and no snapshot timeline**. The platform is amnesiac: each analysis is a point in time disconnected from the last. This blocks trends, early warning, change-impact, and "what changed since last week" — i.e., most of the v3.0 vision.

## Decision

**Hybrid temporal model: an append-only domain event log (source of truth for *change*) + materialized append-only snapshots (authoritative reads) + content-addressed revision lineage.** Full event sourcing is explicitly **not** adopted.

1. **Immutable `DocumentRevision` lineage** — `rev_no`, `parent_revision_id`, `blob_hash`, `valid_from/valid_to`, content-addressed blob in R2. Promote the existing reupload hash to a durable revision row, fixing the "amnesiac reset."
2. **Append-only `ProjectEvent` log** — `event_type` (extensible registry, incl. the reserved `procurement.*` / `stakeholder.*` namespaces from ADR-014), `payload` jsonb, `actor`, `confidence`, `evidence_refs`. Tenant-scoped (RLS, fail-closed).
3. **Append-only materialized `ProjectSnapshot`** — health vector + coherence subscore + counts + totals at time *t*. Makes trend/delta queries O(1) without replaying events. **Never UPDATE — only INSERT.**

### Snapshot strategy
Write a snapshot on: (1) a document revision ingested; (2) a ProjectGraph run completes; (3) a material HITL correction; (4) a daily scheduled Celery job; (5) a schedule/budget baseline change.

### Lineage
All derived intelligence traces back: `ProjectSnapshot → ProjectEvent → DocumentRevision → EvidenceRef (page/span/hash/confidence)` per INV-1.

### Sequencing (Challenger-informed)
Ship **`DocumentRevision` first** (it alone unblocks the Change-Impact wedge in ADR-016), then the event log + snapshot scheduler. Do not block the wedge on the full triad.

## Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| **Hybrid event-log + materialized snapshots** | **Chosen** | Change gets event provenance; answers (health/trends) are cheap materialized reads. "Invariant by formula, adaptive by profile" applied to time. |
| Full event sourcing (rebuild state by replay) | **Rejected** | High complexity the consensus warns against; replay is needed only for audit, not the hot read path (DeepSeek leaned here; overruled). |
| Revisions + ChangeSet only, snapshots indefinitely deferred | **Rejected as end-state, adopted as sequence** | Snapshots are required for Health trends; but the Challenger is right they ship *second*, not first. |

## Consequences

**Positive:** unlocks "what changed?", audit trails, early warning, health trends, and later forecasting.
**Negative:** storage growth → **retention/partitioning policy is mandatory from day one** (e.g., daily snapshots for 90d, weekly thereafter; partition by month). Careful tenant isolation + indexing required.

## Scope
`DocumentRevision` lineage (content-addressed); `ProjectEvent` append-only log + extensible type registry; `ProjectSnapshot` materialized read model; snapshot triggers; retention/partitioning policy.

## Out of scope
Full event sourcing / state-replay as a read path; semantic interpretation of changes (ADR-016); predictive forecasting (Month 12).

## Dependencies
ADR-014.

## Success criteria
- Every upload produces a durable, retrievable, comparable revision.
- "What changed between revision N and N+1 / since last week" is answerable from stored data.
- Every analysis is tied to a reproducible `ProjectSnapshot`.
- Snapshot/event storage growth is bounded by an enforced retention policy.

## Implementation note
Thin-Spine, **Month 2** (revisions in Weeks 3–4; event log + snapshots + retention in Month 2). Append-only design makes the whole layer safe-to-disable: if unread, it is harmless.
