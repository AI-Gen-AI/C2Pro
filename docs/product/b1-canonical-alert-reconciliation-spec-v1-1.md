# B1 Canonical Alert Reconciliation & Coherence Product Acceptance — Spec v1.1

**Status:** Canonical focused specification for Line B implementation and acceptance
**Decision owner:** Product / architecture approval in the 2026-10-04 B1 review
**Baseline:** `origin/main@4e3928b3f91ded93163b617214ddde48149b2039` (PR #828 + #829 + #834 merged on top of C3a)
**Architecture authority:** ADR-009, ADR-019, ADR-020, ADR-026, ADR-027, ADR-028
**Parallel work/dependencies:** #831 (Lane C / C3b, open)
**Lifecycle note:** This specification does not promote realization, deployment, or PROD_VALIDATED state.

## 1. Purpose

B1 closes the remaining product-integrity gap between evidence-backed Coherence findings and the durable Alerts/HITL surface.

Required journey:

```text
trusted evidence
  -> typed Coherence findings
  -> canonical Alert reconciliation
  -> durable human disposition
  -> disposition-aware canonical scoring where ADR-009 allows it
  -> one durable write boundary
  -> fresh-session/API/UI reload truth
```

The objective is not merely to persist Alert mutations. It is to establish one canonical lifecycle for a finding across reevaluation, retries, trusted document revisions, human review, temporal materialization and production acceptance without creating a second Coherence engine, trust engine or temporal engine.

## 2. Current baseline truth

The baseline now consumes Line-B PRs #828, #829 and #834 as current truth.

### 2.1 Already merged by #828, #829 and #834

At `a0512c5f...`, the live Coherence alert path now:

- routes findings through `AlertGeneratorService` instead of destructive `DELETE + INSERT`;
- scopes reconciliation by tenant and `AlertType.COHERENCE`;
- collapses duplicate detector emissions inside one evaluation;
- preserves ACKNOWLEDGED and DISMISSED human state across unchanged reevaluation;
- reopens RESOLVED findings when they genuinely recur;
- auto-resolves only current OPEN findings that disappear;
- serializes same-project reevaluations with a transaction advisory lock;
- keeps the caller-owned transaction with `commit=False`;
- verifies persisted clause provenance against C3a trusted-current truth;
- uses versioned fingerprint recomputation (`fingerprint_version=3`) for legacy compatibility;
- separates detector evidence from reviewer-attached evidence.

PR #829 additionally exposes detector provenance through the canonical Alerts response and real Review Center, preserves the detector/reviewer evidence split, and deep-links only database-verified clause/document evidence.

PR #834 additionally closes the previously demonstrated HITL persistence gap: approval status, reviewer/timestamp/comment, resolution state/notes and reviewer-attached evidence are durable across a fresh session. It also makes bulk review fail closed through bounded batch size, mandatory individual review for HIGH/CRITICAL approval, and mandatory rationale for bulk rejection.

These are implementation advances, not automatic B1 product acceptance.

### 2.2 Residual gaps on current main

B1.1 must target only gaps that still exist after #828/#829/#834:

1. **Score/Alert atomicity remains broken.** `/coherence/evaluate` still commits `CoherenceResultORM` before Alert reconciliation and then treats mirror failure as best-effort. A durable score can therefore exist without its canonical Alert surface.
2. **ADR-009 disposition-to-score integration remains unwired.** A validated `false_positive` still lacks the governed path that removes the invalid finding before the canonical score is finalized, while acknowledged/accepted/explained discrepancies must preserve their score impact.
3. **Cross-revision identity semantics remain partial.** #828 gives stable current-path identity and safe handling for revision-unstable synthetic locators, but persisted clause UUIDs are revision-bound. There is not yet an explicit family-vs-observation contract with evidence-basis-bound human disposition.
4. **Legacy identity conflict handling is not explicit.** #828 can recompute versioned legacy fingerprints, but B1 still requires a fail-closed policy when more than one historical row could claim the same semantic family.
5. **C3b materialization remains open.** #831 must consume the shared Alert reconciliation contract and may not create parallel identity/trust semantics.

The full HITL persistence defect demonstrated by the original B1 RED is now closed by #834 and becomes a mandatory regression contract rather than residual RED justification.

Tests whose only purpose is to re-prove a seam already closed by #828/#829/#834 are regression tests, not new RED justification.

## 3. Non-negotiable product semantics

- Health, Coherence and Alerts remain separate signals.
- Alert category is one of `SCOPE | BUDGET | TIME | TECHNICAL | LEGAL | QUALITY`.
- Alert trigger is orthogonal to category.
- Unknown or unsupported Coherence is `null/Unknown`, never zero or green.
- Human acceptance does not rewrite documentary inconsistency.
- `accepted_variance` / `explained_conflict` preserve raw Coherence impact.
- Only `false_positive`, corrected extraction/data, changed trusted evidence, or supersession may remove/replace a finding and drive recalculation under ADR-009.
- pending, rejected, stale or superseded candidate state cannot mutate canonical Alerts or trusted Coherence.
- canonical reads/writes fail closed on tenant/project/revision authority mismatch.

## 4. Ownership and authority

### 4.1 Coherence owns detection and scoring

The Coherence engine owns typed finding detection and canonical scoring. It does not own durable human lifecycle.

### 4.2 Alerts owns durable lifecycle

The Alerts bounded context owns:

- canonical finding identity;
- durable Alert row lifecycle;
- human disposition and reviewer evidence;
- reconciliation of current findings against prior durable Alerts.

### 4.3 One canonical reconciliation boundary

There is exactly one canonical Alert reconciliation boundary.

It MUST NOT:

- compute a Coherence score;
- grant or mutate trust;
- commit its own SQL transaction;
- create a second temporal engine;
- silently repair production truth during acceptance.

The caller owns commit/rollback and supplies trusted authority.

## 5. Two-level identity model

One identifier is insufficient because human continuity and exact evidence provenance are different concerns.

### 5.1 Finding family identity

`finding_key` identifies the durable semantic issue family.

Canonical inputs:

```text
identity_schema_version
producer / alert_type
rule_code
rule_identity_version
canonical category
trigger
stable semantic anchors
```

Database scope is `tenant_id + project_id + alert_type + finding_key`.

A trusted revision UUID is not automatically part of family identity.

Never use as family identity:

- title;
- message;
- rendered quote;
- severity label;
- UI wording.

Preferred stable anchors:

1. canonical WBS/entity identifiers that survive revision;
2. document identity + stable clause/business key;
3. normalized compared-object references;
4. explicitly marked weak fallback identity.

Weak identity MUST be labelled `identity_quality=weak` and MUST NOT carry a human disposition automatically across a new authoritative basis.

### 5.2 Observation identity

`observation_key` identifies the exact current evidence basis for a finding family.

It includes:

- exact trusted artifact/revision authority;
- current source clause/entity identifiers;
- normalized expected/observed or comparison payload;
- canonical rule identity version.

It excludes non-semantic rendering changes.

A new trusted revision is a new review basis by default because the reviewer saw a different authoritative artifact. B1 does not invent a cross-revision equivalence shortcut.

A future certified equivalence rule may preserve review basis only if it proves the compared evidence is semantically unchanged.

### 5.3 Versioning

Keep distinct:

- `identity_schema_version`: fingerprint algorithm/shape;
- `rule_identity_version`: semantic identity contract for a rule;
- `detector_version`: implementation provenance only.

A detector bugfix does not automatically create a new family.

An intentionally incompatible rule identity or unsafe anchor change creates explicit successor/supersession lineage.

## 6. Detection evidence vs human evidence

### 6.1 Machine-owned refreshable state

Examples:

- severity;
- category;
- trigger;
- expected / observed;
- current source locator;
- current source clause/entity;
- current trusted revision/artifact basis;
- current observation key;
- detector provenance;
- machine-generated title/message/recommendation.

These may refresh in place for the same family.

### 6.2 Human-owned non-destructive state

Examples:

- approval/disposition;
- reviewer identity and timestamp;
- review rationale/comment;
- resolution notes and root cause;
- manually attached evidence;
- lifecycle/history;
- observation basis reviewed by the human.

Reevaluation MUST NOT silently erase these fields.

Canonical metadata split:

```text
alert_metadata.detection_evidence
alert_metadata.human_evidence[]
alert_metadata.history[]
alert_metadata.disposition
```

Legacy dict-shaped detector payloads must be normalized without corrupting reviewer evidence lists.

## 7. Human disposition basis and lifecycle

Every human decision stores `disposition_basis_key = observation_key`.

Current persisted status values may remain `OPEN | ACKNOWLEDGED | DISMISSED | RESOLVED`. B1 does not require a new REOPENED enum; reopening is a history event back to OPEN.

### 7.1 Same family, same observation

- OPEN remains OPEN;
- ACKNOWLEDGED remains ACKNOWLEDGED;
- DISMISSED/false-positive remains DISMISSED;
- detection fields may refresh;
- no duplicate review/history event is fabricated.

### 7.2 Same family, new authoritative observation

A changed authoritative basis makes the prior basis-sensitive disposition stale.

- prior review/history remains immutable;
- ACKNOWLEDGED or DISMISSED returns to OPEN/PENDING review;
- append one basis-change reopen history event;
- prior disposition remains inspectable.

This prevents a V1 false-positive decision from suppressing a materially different V2 observation.

### 7.3 RESOLVED finding reappears

If family continuity is provable:

- reuse the same durable Alert row/id;
- set status to OPEN;
- retain full history;
- append one reopen event.

If continuity is not provable, use successor/supersession semantics instead.

### 7.4 Finding disappears

A previously active finding may auto-resolve only when it is absent from a complete canonical reconciliation set.

Incomplete/unsupported evaluation MUST NOT auto-resolve prior findings.

### 7.5 Identity changes

If semantic family identity changes because of incompatible `rule_identity_version` or unsafe anchor continuity:

- create a successor family;
- close the prior active family as superseded where justified;
- preserve predecessor/successor lineage;
- never copy prior human disposition silently.

## 8. Persistence contract

The semantic contract is mandatory; physical schema changes are evidence-driven.

Current #828 persists `fingerprint` + `fingerprint_version=3` in Alert metadata and serializes the canonical reevaluation path. B1 MUST preserve compatibility with that state.

Target semantic fields:

```text
finding_key
identity_schema_version
rule_identity_version
current_observation_key
disposition_basis_key
```

B1.1 must first prove whether metadata-backed identity plus the canonical lock boundary is insufficient for the required invariants.

A schema migration MUST NOT be added merely because dedicated columns look cleaner.

If DB-level uniqueness/queryability is required to close a demonstrated gap, the minimum promoted fields are:

```text
finding_key                 nullable string during migration
identity_schema_version     nullable integer during migration
rule_identity_version       nullable string during migration
current_observation_key     nullable string
disposition_basis_key       nullable string
```

with a partial uniqueness constraint/index for:

```text
(tenant_id, project_id, alert_type, finding_key)
WHERE finding_key IS NOT NULL
```

Any migration must preserve #828 fingerprints/history and satisfy Alembic/Supabase parity.

## 9. Legacy identity policy

B1 MUST NOT reset historical dispositions because legacy rows lack the new family model.

Policy:

1. classify legacy Coherence Alerts before canonical cutover;
2. adopt a row only when a strong family identity maps one-to-one;
3. preserve existing row ID and all human state;
4. never silently choose the newest/first row among ambiguous candidates;
5. never silently merge reviewer histories;
6. classify ambiguity as `LEGACY_IDENTITY_CONFLICT`;
7. destructive reconciliation for that family fails closed until explicit remediation;
8. rollout requires zero unresolved legacy identity conflicts in the affected acceptance scope.

#828 versioned fingerprint recomputation is compatibility input to this policy, not a substitute for ambiguity handling.

## 10. Transaction and scoring-order contract

The current two-commit best-effort sequence is forbidden for canonical B1 writes.

Correct logical order:

```text
prepare typed detector findings against one trusted authority snapshot
BEGIN
  validate trusted/current authority
  acquire reconciliation serialization
  reconcile finding families + load durable dispositions
  derive scoring-eligible findings under ADR-009
  compute/finalize canonical score with the canonical scorer
  persist Alerts and Coherence result / owning canonical projection
COMMIT ONCE
```

The reconciler does not calculate the score.

It returns the disposition effect needed by the caller:

- acknowledged / accepted / explained findings remain scoring-eligible;
- a validated false-positive may be excluded before canonical score finalization;
- resolve without changed trusted evidence does not remove documentary score impact.

If reconciliation or final persistence fails, neither the new Alert reconciliation nor the new Coherence result becomes durable.

No `partial_projection` state or outbox/eventual-consistency architecture is introduced in B1 without evidence that it is needed.

## 11. Concurrency and idempotency

Canonical reconciliation is serialized by transaction-scoped lock for `(tenant_id, project_id)`.

Requirements:

- bounded lock timeout under service/database policy;
- timeout is retriable and fail-closed;
- no partial business state after timeout/failure;
- repeated identical evaluation is semantically idempotent;
- duplicate findings in one run collapse before persistence;
- concurrent same-project evaluations cannot create two canonical family rows;
- retries do not duplicate lifecycle history.

Lock order for governed materialization:

```text
authority/operation row if applicable
  -> tenant/project reconciliation lock
  -> Alert rows
```

Inverse order is forbidden.

## 12. Reconciler boundary contract

Conceptual application contract:

```python
reconcile(
    scope: AlertScope,
    findings: list[CanonicalFinding],
    authority: TrustedEvidenceBasis,
    operation_key: str,
) -> ReconcileReport
```

The reconciler rejects:

- PROPOSED authority;
- REJECTED authority;
- stale/superseded authority;
- tenant/project mismatch;
- ambiguous legacy identity where destructive reconciliation would be required.

`ReconcileReport` includes at least:

- created;
- updated;
- preserved;
- reopened;
- resolved;
- superseded;
- duplicate_findings_collapsed;
- legacy_rows_adopted;
- scoring_eligible_finding_keys;
- scoring_excluded_false_positive_keys;
- basis_key / operation_key.

Canonical failure outcomes:

- `UNTRUSTED_EVIDENCE_BASIS`;
- `SCOPE_AUTHORITY_MISMATCH`;
- `RECONCILIATION_LOCK_TIMEOUT`;
- `LEGACY_IDENTITY_CONFLICT`.

B1 introduces no new event bus/outbox event as a source of truth.

A report never self-promotes lifecycle state.

## 13. C3b / #831 integration contract

B owns Alert reconciliation semantics.

C3b owns when an exact trusted temporal candidate may materialize.

C3b MUST:

- reuse canonical trusted-state authority;
- call the B reconciler inside governed materialization;
- pass the exact approved candidate/revision/artifact basis and operation identity;
- never implement a second Alert reconciler;
- never mutate B identity/disposition semantics locally.

B1-07 validates this boundary. Full post-approval temporal materialization remains #831 scope.

If #831 lands while B remains open, rebase onto current main and rerun affected B1 contracts.

## 14. Coherence / HITL anti-gaming

Per governing ADR-009:

- genuine inconsistency acknowledged: raw score unchanged;
- accepted variance: raw score unchanged;
- explained conflict: raw score unchanged;
- resolve action without changed evidence: raw score unchanged;
- false positive: invalid finding may be removed and canonical score recalculated;
- corrected extraction/data: recalculate;
- changed trusted evidence: recalculate;
- supersession by newer authority: recalculate.

For current API semantics:

- `approve` means genuine/acknowledged and does not remove score impact;
- `reject` is explicit false-positive disposition and may remove the invalid finding through canonical recalculation;
- `resolve` is lifecycle/action state only until trusted evidence changes.

### 14.1 Trusted score vs projected/provisional score

B1 reuses the already-shipped #714 trusted/projected Coherence contract. It MUST NOT invent a second score-authority model.

- **trusted_score** is the solid canonical project score from the currently trusted/approved evidence state and validated score-affecting dispositions only.
- **projected_score** is a non-canonical scenario, rendered visually provisional/translucent, answering what the same canonical engine/version would produce if the exact pending score-affecting candidates were accepted.
- `projected_score` NEVER replaces `trusted_score`, NEVER becomes the official export/report score, and is NEVER copied into canonical state on approval; approval triggers recomputation from the newly trusted state.
- pending candidate evidence, a pending correction, or a pending score-affecting disposition cannot mutate `trusted_score`.
- a detected finding on already trusted evidence **does affect the documentary trusted/raw score immediately**; merely leaving an Alert unreviewed MUST NOT hide an evidence-backed discrepancy.
- reviewing a genuine discrepancy as acknowledged / accepted variance / explained conflict does not create a better projected score because ADR-009 says its documentary impact is unchanged.
- only a pending action that is permitted to change the scoring set under ADR-009 — validated false-positive, corrected data/extraction, changed trusted evidence, or supersession — may yield a different provisional score.
- when both trusted and projected exist, both MUST use the same canonical scorer and identical `score_version`. Version mismatch => projection unavailable, never arithmetic conversion.
- when no trusted score exists yet, `trusted_score=null`; a projected score may exist but remains explicitly provisional.
- the UI MUST label projected score as non-approved and show the pending-review cause/count sufficient to explain why it is provisional.
- the six canonical subscores remain first-class: `sub_scores` are the trusted category scores; a projection MUST additionally expose `projection_baseline_sub_scores` and `projected_sub_scores` for the same six dimensions.
- projected subscores follow exactly the same engine/version and honest-null rules as the projected global score; a missing/unsupported dimension remains `null`, never 0.
- approval NEVER copies a projected subscore into trusted state; the newly trusted artifact set is recomputed and its category scores become the new trusted `sub_scores`.

This preserves the existing #714 product semantics while extending B1 lifecycle decisions into the same authority model.

## 15. Honest-null propagation

B1 preserves ADR-009:

- unsupported dimension remains `null`;
- null is never coerced to 0 or 100;
- coverage/applicability remains disclosed;
- partial supported-subset score is allowed only under existing ADR-009 active-weight/status rules;
- UI must show partial/insufficient-evidence status honestly.

### 15.1 Numeric score guardrails — 0/100

B1 does not recalibrate score bands, but acceptance MUST preserve these invariants across every score version it surfaces:

1. lack of evidence, insufficient active weight, processing error, pending documents, or unavailable projection can NEVER fabricate `0`;
2. a critical finding can NEVER mechanically force category or global score to `0`;
3. `100` can NEVER be a fallback for missing/unassessed evidence;
4. a score of `100` is only admissible when the active scoring version genuinely computes a fully assessed clean state with no score-impacting finding; it is not a default;
5. a projected score MUST be recomputed by the same scoring engine/version as its trusted baseline, not by adding/subtracting alert penalties;
6. score history records score value, score version, authority state (trusted vs projected), and the evidence/disposition basis that caused a legitimate change.

Current numeric truth is deliberately not hidden:

- the canonical per-category scorer currently uses interim severity bands: **LOW 80–95**, **MEDIUM 65–80**, **HIGH 45–65**, **CRITICAL 25–45**;
- the canonical global envelope currently caps an open worst finding at **LOW 100 / MEDIUM 95 / HIGH 90 / CRITICAL 85**;
- these are interim calibrated guardrails, not immutable business thresholds;
- the legacy/live v1 path still contains older global caps and a separate scoring curve. B1 MUST NOT mix those values with a projection from another `score_version`; ADR-009 §F owns scorer convergence/cutover.

B1 does not redefine or recalibrate the canonical scorer.

## 16. Review UX contract

PR #829 is merged and provides detector-evidence addressability plus verified Evidence Viewer deep-links. B1 consumes that implementation as baseline evidence.

The actual review journey must make inspectable, where available:

- canonical category;
- trigger/rule;
- severity;
- expected vs observed;
- source/evidence locator;
- current evidence/revision basis;
- current status/disposition;
- prior disposition/history after reopen.

A product acceptance cannot pass if the data exists only in backend metadata.

Unverified/textual locators may be visible but MUST NOT fabricate a source deep-link.

## 17. B1 acceptance matrix

Merged #828 is implementation evidence toward B1-01/B1-02/B1-03/B1-05. Merged #829 is evidence toward B1-05/B1-10/B1-11. Merged #834 is evidence toward B1-03/B1-11 and review-integrity behavior. None is automatic PASS for full B1 acceptance.

| ID | Mandatory PASS |
|---|---|
| **B1-01-STABLE-IDENTITY** | Same semantic finding across unchanged reevaluation keeps one durable family/id; a revision change alone does not force a new family when strong semantic anchors prove continuity. |
| **B1-02-IDEMPOTENCY-CONCURRENCY** | Duplicate emissions collapse; retry is history-idempotent; concurrent same-project evaluations produce one deterministic family state. |
| **B1-03-HUMAN-STATE** | Reevaluation cannot erase human evidence/history; same basis preserves disposition; new authoritative basis revalidates basis-sensitive disposition while preserving history. |
| **B1-04-REAPPEAR-SUPERSEDE** | Resolved family reappears on same id where continuity is provable; incompatible identity creates linked successor semantics. |
| **B1-05-PROVENANCE** | Material Alerts expose reproducible trusted evidence/basis, locator, rule/trigger and expected/observed where applicable. |
| **B1-06-TRUST-BOUNDARY** | PROPOSED/REJECTED/stale/superseded basis cannot mutate canonical Alerts or trusted Coherence; isolation fails closed. |
| **B1-07-C3B-CONTRACT** | Exact approved C3b candidate can call shared reconciler once; no second trust/materialization/reconciliation engine exists. |
| **B1-08-HONEST-COHERENCE** | Unsupported remains null/Unknown with disclosed coverage/status; no 0/green coercion. |
| **B1-09-ANTI-GAMING** | Acknowledge/accepted/explained/resolve-without-evidence-change does not improve raw Coherence; validated false-positive/data correction/changed evidence/supersession uses canonical recalculation. |
| **B1-10-SEMANTIC-ALERT** | Category is canonical dimension; trigger orthogonal; detection fields may refresh without identity churn; presentation text is not identity. |
| **B1-11-DURABLE-ROUNDTRIP** | POST mutation -> commit -> new DB session/transaction -> API GET -> browser refresh/relogin all agree; no identity-map/React-memory false PASS. |
| **B1-12-PROD-ACCEPTANCE** | Exact composite runtime/SHA, synthetic project, UI evidence, durable verifier, reevaluation/retry/concurrency proof and independent evidence validator all PASS before lifecycle promotion. |
| **B1-13-SCORE-AUTHORITY** | Trusted score remains canonical/solid; projected score is visibly provisional, same-engine/same-version only, cannot mutate official reports, pending non-score-changing Alert review does not fabricate a different score, and null/unknown never becomes 0 or default 100. |

Every applicable test asserts tenant/project/revision isolation.

## 18. B1.1 RED contract set after #828

The first new RED package must demonstrate residual defects, not already-fixed history.

At minimum:

1. force Alert reconciliation failure after the current first Coherence commit and prove the result can remain durable today;
2. keep #834 fresh-session review persistence, reviewer-evidence, and bulk-review-integrity contracts GREEN;
3. prove a validated false-positive has no governed canonical recalculation path yet, while acknowledgement must not change raw score;
4. construct a cross-revision case with provable semantic continuity and show the current fingerprint model lacks explicit family/observation/disposition-basis semantics;
5. construct an ambiguous legacy-fingerprint case and prove current reconciliation has no explicit fail-closed ownership classification;
6. keep #829 detector-provenance and verified-deep-link regressions GREEN while later B1 slices change lifecycle/scoring internals;
7. pin #831 so C3b cannot introduce a second reconciler or canonical writes from untrusted/stale authority.

#828/#829/#834 regression tests remain GREEN throughout later B1 work.

## 19. Baseline and rebase policy

- B1.0 baseline is `4e3928b3f91ded93163b617214ddde48149b2039` and already includes #828, #829 and #834.
- No `b1-baseline` tag is required; exact SHA is the immutable authority.
- B1 work uses a clean worktree.
- The unrelated untracked `apps/storage/` in another checkout is not deleted without ownership evidence; isolation is sufficient.
- If `origin/main` advances, including #831 or another overlapping B/C change, rebase and rerun affected RED/GREEN/acceptance.
- production qualification binds exact deployed backend/frontend identities under ADR-028, not merely the B1.0 source baseline.

## 20. Non-goals

B1 does not:

- make global Coherence v2 authoritative;
- implement Tier-2/agentic Coherence cutover;
- create a new scorer;
- create a second temporal engine;
- complete C3b itself;
- build the full ADR-019 ActionItem correlation/ownership product;
- introduce event/outbox architecture without evidence;
- create a C2Pro-specific Skill, MCP server or new agent role;
- promote Product Control from docs/tests alone.

## 21. Change control

This spec governs cross-module ownership, persistent identity, concurrency and trust-adjacent semantics.

Implementation that intentionally deviates from sections 4–15 requires explicit amendment to this spec and, where applicable, the owning ADR.

Acceptance may become stricter; it may not be weakened merely to make code pass.

## 22. Approved implementation sequence

```text
B1.0  Freeze current main 4e3928b3... and consume #828 + #829 + #834 as merged truth
B1.1  RED only for residual post-#828 false-PASS modes
B1.2  Complete durable Alert lifecycle: basis semantics + legacy ambiguity; preserve #834 HITL durability
B1.3  Atomic Coherence <-> Alert persistence + governed disposition-to-score eligibility
B1.4  Preserve #829 provenance/deep-link + #834 reviewer-evidence integrity and complete category/trigger/expected-observed UX
B1.5  C3b/#831 shared-reconciler boundary
B1.6  Exact-head independent/adversarial review + required CI
B1.7  Production qualification against B1-01 through B1-13
```

Implementation follows RED -> GREEN -> REFACTOR for each bounded slice.

A locally green suite or merged PR does not imply production acceptance.

[executed on device: vmi3226522 (f25c3740-ed77-4837-8d92-d0f9660f9596)]

[executed on device: vmi3226522 (f25c3740-ed77-4837-8d92-d0f9660f9596)]