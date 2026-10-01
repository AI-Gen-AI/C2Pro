# ADR-026: Trusted-State Commit Boundary and Exact Approval Binding

**Status:** Accepted architecture · implementation landed for #714; broader production qualification remains separate  
**Date:** 2026-10-01  
**Related:** ADR-014, ADR-017, ADR-018, ADR-020, #706, #714, #715

## Context

C2Pro persists AI-derived analysis for durability, audit and recovery. Persistence alone cannot confer business trust.

Before #714, a HITL-gated artifact could be durable while the architectural distinction between a persisted proposal and canonical trusted project state was insufficiently explicit. That creates a substitution risk: ProjectGraph, Health or Coherence could consume output that a human had not approved, or an approval could be applied to a newer/different candidate than the one reviewed.

## Decision

C2Pro adopts a first-class **Trusted-State Commit boundary**.

The canonical flow is:

`UNTRUSTED INPUT → proposal/candidate → persisted evidence → independent/human verification → exact approval binding → TRUSTED COMMIT → canonical projections`

### 1. Persisted is not trusted

A candidate may be durably persisted for audit/recovery while remaining non-canonical.

Trust states are semantically distinct (for example proposed/trusted/rejected/superseded). Canonical readers and canonical ProjectGraph/Health/Coherence processing must consume only trusted state.

### 2. Approval binds the exact reviewed object

A consequential approval/correction must bind, at minimum, the exact candidate identity/version and integrity digest/hash required by the implementation contract.

An approval cannot be treated as generic permission to promote “whatever is latest”.

### 3. Stale/substituted approval fails closed

If the reviewed candidate has been replaced, superseded or does not match the approval binding, promotion is rejected.

### 4. Trusted commit is idempotent

Retrying the same valid approval must not duplicate canonical effects.

Exactly-once is a semantic property at the trust boundary even when underlying infrastructure uses at-least-once delivery/retry.

### 5. Reject does not mutate canonical state

Rejecting a candidate preserves the prior trusted state. If no prior trusted state exists, canonical state remains absent/pending rather than fabricating a value.

### 6. Correction is a new candidate/version

A correction supersedes the reviewed proposal. It is not an in-place mutation that destroys provenance.

### 7. Canonical projections follow trusted commit

ProjectGraph, Health, Coherence, snapshots and other trusted projections are triggered/recomputed from trusted evidence after promotion.

Pending/rejected proposals may feed explicitly labelled hypothetical projections but not canonical state.

### 8. Trusted and projected Coherence are separate

- `trusted_score`: canonical.
- `projected_score`: hypothetical result under an explicitly defined pending-candidate scenario.
- projection uses the same canonical scorer/version.
- official exports and decisions use trusted state unless projection is explicitly requested and visibly marked.

## Security rationale

This boundary prevents:

- approval substitution / loopjacking;
- stale approval applied to a new candidate;
- persistence being mistaken for trust;
- pending AI output contaminating official project state;
- retries duplicating canonical side effects;
- audit history being overwritten by correction.

## Consequences

### Positive

- clear business trust boundary;
- stronger auditability and non-repudiation;
- safe retry/recovery semantics;
- clean separation between advisory AI output and official project state;
- ProjectGraph/Health/Coherence can reason over explicitly trusted inputs.

### Negative

- more lifecycle state and version/hash bookkeeping;
- approval flows must carry binding metadata;
- recovery/fencing correctness becomes part of acceptance;
- projections require version-consistent recomputation.

## Relationship to ADR-017 and ADR-020

ADR-017 defines asynchronous ProjectGraph orchestration. ADR-020 defines HITL workflow semantics.

ADR-026 refines both: **HITL-gated output must cross the trust boundary before canonical ProjectGraph/Health/Coherence mutation**.

## Implementation / lifecycle note

#714 is closed and PR #726 is merged as of the audit baseline. This ADR records the architectural rule, not a claim that the entire #706 production journey is validated.

Production proof remains governed by #715 and the production qualification contract.

## Rejected alternatives

1. **Persist = trusted** — rejected; conflates durability with authority.
2. **Approve latest candidate** — rejected; vulnerable to substitution/race.
3. **In-place correction** — rejected; destroys provenance.
4. **Pending candidate mutates canonical score then rolls back on reject** — rejected; official state becomes temporarily untrustworthy.
5. **Ad-hoc projected penalty arithmetic** — rejected; projection must use canonical scorer/version.

## Verification expectations

Tests must cover at least:

- pending never changes canonical state;
- reject never changes canonical state;
- exact approval changes canonical state once;
- duplicate approval is idempotent;
- stale/substituted approval is rejected;
- correction supersedes rather than stacks stale candidate state;
- projection and trusted score never mix incompatible score versions.
