# ADR-026: HITL-Gated Trusted-State Commit Boundary and Exact Review Binding

**Status:** Accepted / implemented on `main`  
**Date:** 2026-10-01  
**Decision class:** Trust, HITL and canonical-state architecture  
**Implementation lineage:** #714 / PR #726  
**Basis:** Retrospective codification of the accepted issue/PR contracts and merged implementation evidence; this ADR creates no new runtime authority.
**Related:** ADR-013, ADR-014, ADR-017, ADR-018, ADR-020, ADR-027

## Context

C2Pro uses AI-assisted extraction and ProjectGraph analysis. When routing requires human review, that review must be a real trust boundary. A gated workflow is unsafe if a pending or rejected candidate can alter canonical project state, or if an approval can be replayed against a different candidate/checkpoint than the one the reviewer saw.

This is not merely a UI-state problem. It is a canonical-state integrity problem.

## Decision

For **HITL-gated analyses**, C2Pro separates **proposal state** from **trusted canonical state**.

This ADR does **not** require every analysis to enter HITL. The current policy router may explicitly produce a non-gated completion (`human_approval_required=False`); that path can persist `TRUSTED` state and enqueue ProjectGraph without a human action. Whether the router's automation policy is sufficiently narrow for each business decision class remains governed by ADR-020 and is tracked separately from the exact-binding invariant defined here.

1. Analysis produces a candidate in `PROPOSED/UNTRUSTED` state.
2. A pending or rejected candidate cannot mutate canonical ProjectGraph, Health or Coherence.
3. Human approval is bound to the exact candidate/version/hash and its exact processing/checkpoint lineage.
4. Approval commits the trusted candidate exactly once.
5. A correction creates/supersedes candidate state before commit; the superseded proposal can never be committed.
6. Canonical exports use trusted state by default.
7. Scenario/projected outputs must be explicitly labelled provisional and never overwrite the trusted value.

## Projected Coherence

A projected Coherence value may be calculated from:

`trusted state + exact pending proposals`

but it remains hypothetical. It must:

- use the same canonical scoring semantics/version;
- expose its pending-proposal count and delta;
- be distinguishable from the trusted score in UI and exports;
- never become the trusted score solely because it was computed.

## Invariants

The following invariants apply whenever a candidate is routed through HITL:

- **TS-1:** `PENDING_REVIEW` never changes trusted ProjectGraph state.
- **TS-2:** `REJECTED` never changes trusted ProjectGraph state.
- **TS-3:** `APPROVED` commits the exact reviewed candidate exactly once.
- **TS-4:** `CORRECTED` commits only the corrected/superseding candidate.
- **TS-5:** trusted Health/Coherence excludes rejected findings.
- **TS-6:** approval cannot be rebound to another candidate, version, checkpoint or processing generation.
- **TS-7:** projected/scenario state is never silently exported as canonical state.

## Scope boundary

**In scope:** analyses for which review is required; proposal/trust state, exact candidate/review/checkpoint binding, correction/rejection semantics and projected-vs-trusted separation.

**Out of scope:** the business policy that decides which analyses may bypass HITL. ADR-020 defines the intended automation boundary; current confidence/impact routing is only a partial realization of that richer policy.

## Consequences

**Positive**

- human review becomes an actual authorization boundary;
- stale/replayed approvals cannot legitimize different state;
- canonical state remains explainable and audit-grade;
- scenario/projection UX can exist without weakening trust semantics.

**Constraints**

- review/candidate/checkpoint identity must be persisted durably;
- processing lineage must itself be trustworthy (ADR-027);
- migrations and projections must preserve the distinction between proposed and trusted state.

## Alternatives rejected

- **Review as a UI flag only:** rejected because canonical writes could precede human approval.
- **Approve “latest candidate”:** rejected because concurrent/reprocess activity can change what “latest” means.
- **Overwrite trusted score with a projection:** rejected because hypothetical and authoritative state become indistinguishable.

## Validation status

Implementation is merged on `main`, but this ADR does not claim the complete production journey is PROD_VALIDATED. Production acceptance remains governed by ADR-028 / #715.
