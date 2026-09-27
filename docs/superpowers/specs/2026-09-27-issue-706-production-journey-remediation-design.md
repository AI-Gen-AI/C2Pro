# Issue #706 — Production End-User Journey Remediation Design

**Status:** Approved design basis; implementation not started  
**Authority:** #706 — GOAL: Production end-user journey fully operational  
**Baseline:** main `fd55c7cb59d42da2113ad5a7d3a2c4f084a1c4fd` (#698 merged)

## 1. Goal

C2Pro is GO only when a real authenticated end user can complete the deployed journey:

AUTH → PROJECT → UPLOAD → DURABLE INGESTION → PARSING/EXTRACTION → ANALYSIS → EVIDENCE → SNAPSHOT/HEALTH → UI → HITL → REFRESH/RELOGIN → SAFE RETRY/RECOVERY

without hidden manual repair and without presenting untrusted or fabricated state as canonical truth.

CI remains necessary but insufficient.

## 2. Product invariants

1. Persisted does not imply trusted.
2. AI output may be stored as PROPOSED/UNTRUSTED for audit, recovery and resume.
3. A policy-gated output becomes canonical only after the exact reviewed version is approved.
4. REJECTED output remains audit evidence but MUST NOT mutate canonical ProjectGraph, canonical Health, or the trusted Coherence Score.
5. CORRECTED output is a new candidate version; approval binds to that corrected version, never the superseded proposal.
6. No user-facing state may claim work is queued/running/completed when the durable state proves otherwise.
7. No evidence locator may be fabricated. Unknown position is represented as unknown/null.
8. Async work may never remain indefinitely in a non-terminal processing state. It must recover automatically or enter an explicit retryable/terminal failure state.

## 3. Runtime topology

Production execution must separate lifecycle ownership for:

- API: uvicorn
- Worker: Celery worker consuming the required queues
- Scheduler: Celery beat or equivalent scheduler
- Redis

The same deployable image may be reused with distinct start commands. An API deployment must not implicitly terminate the worker without recoverable delivery semantics.

Acceptance:
- API and worker lifecycles are independently observable.
- Worker receives graceful shutdown.
- Scheduler emits `hitl_resume.reconcile` and project snapshot backstop tasks.
- Queue routing is proven.
- No scheduled recovery code is dead in production.

## 4. Durable delivery and bounded recovery

Required properties:

- late acknowledgement/reject-on-worker-lost or an equivalent durable-delivery contract;
- ingestion/analysis idempotency under duplicate delivery;
- stale-work detection for PARSING / analysis-pending states;
- bounded attempt count;
- automatic recovery OR explicit `FAILED_RETRYABLE`;
- supported user retry through the normal product route;
- no manual DB repair required.

Deliberately killing a shared production worker is NOT required for #706 acceptance. Worker-loss semantics are proven in integration/CI; production proves exact deployed configuration plus a real supported retry path.

## 5. Truthful document/HITL state machine

Canonical semantic states must distinguish at least:

- UPLOADED
- QUEUED
- PARSING
- ANALYZING
- REVIEW_REQUIRED
- ANALYZED
- REJECTED / NEEDS_CHANGES
- FAILED_RETRYABLE
- FAILED_TERMINAL, only if the domain genuinely needs it

Requirements:
- REVIEW_REQUIRED is not rendered as generic processing.
- UI polling stops or changes behavior appropriately for REVIEW_REQUIRED.
- REVIEW_REQUIRED provides a direct route to the review item.
- REJECT produces a truthful durable state.
- exhausted analysis retries never look indistinguishable from active work.
- retry eligibility is consistent across API and UI.

## 6. Trusted-State Commit for HITL

### Pre-review

ANALYSIS → Candidate Artifact → persist as PROPOSED/UNTRUSTED → HITL gate.

The candidate MAY be stored for audit/recovery. It MUST NOT mutate canonical ProjectGraph/Health when HITL is required.

### Approve

Approval must bind to the exact version reviewed, including stable identifiers/hashes sufficient to prevent substitution.

APPROVE → verify binding → finalize exact approved/corrected artifact → TRUSTED COMMIT → canonical ProjectGraph → snapshot → Health.

### Reject

REJECT → proposal remains immutable audit evidence → no canonical graph/Health mutation → previous trusted state remains authoritative.

If no previous trusted state exists, canonical state remains unavailable/pending; it does not inherit rejected findings.

### Correct

AI proposal Vn → human correction → candidate Vn+1 → approval binds Vn+1 → TRUSTED COMMIT.

Required invariants:
1. PENDING_REVIEW artifact never changes canonical ProjectGraph.
2. REJECTED artifact never changes canonical ProjectGraph.
3. APPROVED artifact changes canonical ProjectGraph exactly once.
4. CORRECTED artifact commits the corrected version, not the original.
5. Snapshot/Health never contains a finding whose governing HITL decision is REJECTED.

## 7. Coherence Score: trusted score + pending projection

The canonical Coherence Score represents trusted evidence only.

When pending HITL proposals exist, the UI may also show a clearly non-canonical projection:

- **Trusted Score** — solid; persisted/canonical; used for official exports and project decisions.
- **Projected Score** — translucent/outline; hypothetical result if all currently pending proposals are accepted unchanged.
- **Delta** — impact versus trusted score.
- **Pending review count** — links to the review queue.

Example:
- Trusted Score: 80
- Projected if all pending proposals are accepted unchanged: 60
- Delta: -20

Rules:
1. Pending evidence never changes `trusted_score`.
2. `projected_score` uses the same canonical scoring engine and `score_version` as `trusted_score`.
3. Projection is computed from trusted state + exact pending artifact versions; not by subtracting ad-hoc penalties.
4. Approval recomputes/promotes trusted state; it does not blindly copy the previous projected number.
5. Reject removes that proposal from the projection.
6. Correction supersedes the previous proposal in the projection.
7. With no trusted score: trusted_score=null; projected_score may exist and is explicitly labeled provisional.
8. Official reports/exports use trusted_score unless a projection is explicitly requested and visibly marked as scenario data.
9. Existing null/insufficient-evidence semantics remain authoritative.

## 8. Evidence truthfulness

Minimum accepted evidence locator:

clause → source document → real page_number → offsets/snippet

A real bbox may be added when available.

If bbox is unknown:
- API returns null/unknown.
- UI shows `Exact highlight unavailable`.
- No fixed/default bbox or page number is fabricated.

## 9. ProjectGraph feature-state rule

Before classifying the pre-review ProjectGraph defect as P1, determine the effective ProjectGraph state for the #706 synthetic tenant without exposing secret values.

If ProjectGraph is enabled for the canonical #706 journey, Trusted-State Commit correctness is P0.

If ProjectGraph is disabled in production and outside the current user journey, the fix remains mandatory before enabling it but does not block earlier runtime remediation.

## 10. Synthetic production acceptance

After remediation, implement a production-safe harness using:

- Playwright for real UI AUTH / PROJECT CREATE / UPLOAD / HITL / refresh / relogin;
- deterministic API polling for observable async state;
- tenant-scoped read-only verification for durable DB state where necessary;
- pre-provisioned synthetic Clerk user + Organization + dedicated synthetic tenant;
- one committed non-confidential fixture with verified SHA-256;
- exact Railway/Vercel deployment identities;
- bounded evidence bundle with no secret values.

The acceptance harness performs controlled writes only inside the synthetic tenant.

## 11. Sequencing

1. Runtime topology + scheduler
2. Durable delivery + bounded recovery
3. Truthful document/HITL state machine
4. Evidence truthfulness
5. Trusted-State Commit + ProjectGraph post-HITL correctness + projected Coherence Score
6. Production acceptance harness
7. CI qualification
8. Exact deployed identity verification
9. Synthetic production journey
10. #706 GO only after evidence review

Independent PRs may run in parallel only when they do not share state contracts or overlapping files. Trusted-state/HITL work must consume the final state-machine contract rather than invent a second one.

## 12. #706 closure criteria

#706 may close only when:
- happy path passes in deployed production;
- UI truth matches durable truth;
- evidence is inspectable and non-fabricated;
- HITL approve/reject/correct is durable and canonical-state safe;
- trusted/projected Coherence semantics are correct;
- refresh/relogin preserves state;
- recovery is proven without hidden manual repair;
- exact deployment identities and correlation evidence are captured;
- no unexplained P0/P1 user-journey blocker remains.
