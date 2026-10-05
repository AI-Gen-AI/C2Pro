# B1 Canonical Alert Reconciliation & Coherence Acceptance — Spec v1.2

**Status:** implementation-closure / acceptance boundary  
**Reconciled against:** `main@8b9195e2642293ad75a3703ccb25d634b9ac08a2`  
**Architecture authority:** ADR-009, ADR-019, ADR-020, ADR-026, ADR-027, ADR-028  
**Lifecycle rule:** merged code and green CI prove implementation evidence only. They do not by themselves prove deployment or PROD_VALIDATED product acceptance.

## 1. Purpose

B1 governs the integrity boundary between evidence-backed Coherence findings and the durable Alerts/HITL surface.

Canonical journey:

```text
trusted evidence
  -> typed Coherence findings
  -> canonical Alert reconciliation
  -> durable human disposition bound to the reviewed observation
  -> disposition-aware canonical scoring when allowed
  -> one transaction / commit boundary
  -> fresh-session/API/UI durable truth
```

B1 must not create a second Coherence engine, trust engine, temporal engine, or parallel Alert lifecycle.

## 2. Current implementation truth

The original v1.1 design was written before the final B1 implementation slices landed. Current main now includes the material B1 work that followed the initial #828/#829/#834 foundation.

### 2.1 Landed foundations

- stable canonical Alert reconciliation instead of destructive delete/reinsert;
- tenant + COHERENCE scoping;
- duplicate collapse and deterministic same-project serialization;
- durable review state, reviewer evidence and fresh-session persistence;
- trusted detector provenance separated from reviewer evidence;
- verified evidence deep-links only;
- trusted-current clause/revision boundary from the temporal/trust plane.

### 2.2 Landed B1 closure slices

- **#842** — finding-family identity separated from exact observation identity; review basis can change without family churn;
- **#840** — projected six-dimension subscores with honest-null semantics and score-version guard;
- **#853** — validated false-positive exclusion from the full FindingSignal set before canonical rescoring;
- **#858** — transaction-aware individual Coherence review seam and bulk-review bypass guard;
- **#857** — production wiring for review lock + scoring snapshot/replay + canonical rescore inside the review transaction.

The RED/intermediate PRs #833, #837, #841, #844, #847, #835 and #845 are historical evidence and are intentionally not merge candidates.

## 3. Non-negotiable semantics

- Health, Coherence and Alerts are distinct signals.
- Alert category is one of `SCOPE | BUDGET | TIME | TECHNICAL | LEGAL | QUALITY`.
- Alert trigger/reason is orthogonal to category.
- Unknown or unsupported evidence remains `null/Unknown`, never zero/green.
- Human acknowledgement, accepted variance, explanation or resolution without evidence change must not improve raw documentary Coherence.
- A validated false positive may affect score only by removing the invalid finding from the canonical scorer input and running the same scorer/version.
- Trusted score remains canonical. Projected score is provisional, same-engine/same-version only, and cannot silently replace official/trusted reporting.
- Machine detection state may refresh; human evidence, disposition and history are non-destructive.
- A new authoritative observation is a new review basis by default even when the semantic family remains the same.
- Ambiguous legacy ownership fails closed.
- PROPOSED/REJECTED/stale/superseded evidence cannot mutate canonical Alerts or trusted score.

## 4. Identity and review basis

B1 uses two levels:

1. **finding family** — durable semantic continuity across reevaluation/revisions where strong semantic anchors prove the same real finding;
2. **observation basis** — exact evidence/revision instance that was reviewed.

A basis-sensitive disposition such as `false_positive` is valid only for the exact proven observation basis. If the authoritative basis changes, the durable family/history remains, but the prior basis-sensitive disposition cannot silently govern the new observation.

## 5. Transaction and scoring authority

For a score-affecting human review, the durable order is:

```text
serialize/lock project review boundary
  -> load exact Alert / observation
  -> persist review mutation without early commit
  -> validate false-positive basis
  -> load exact scoring snapshot
  -> remove only the validated false-positive finding
  -> run same canonical ScoringService + score_version
  -> persist Coherence result
  -> commit once
```

Failure to prove snapshot/version/basis is fail-closed. The review path must not commit a score-affecting false-positive disposition while leaving the canonical score stale.

Bulk reject is not an alternate bypass for score-affecting Coherence review.

## 6. Acceptance matrix — implementation state

The statuses below are **repository/CI implementation state**, not production promotion.

| ID | Contract | Current implementation evidence |
|---|---|---|
| B1-01 | Stable semantic family identity across unchanged reevaluation and provable cross-revision continuity | **IMPLEMENTED / CI evidence** — #842 |
| B1-02 | Duplicate/retry/concurrent same-project reconciliation is deterministic | **IMPLEMENTED / regression evidence** — reconciliation foundation |
| B1-03 | Human evidence/history durable; basis-sensitive disposition revalidated on new observation | **IMPLEMENTED / CI evidence** — #842 + durable review foundation |
| B1-04 | Reappearance/supersession semantics preserve durable history | **IMPLEMENTED / regression evidence** |
| B1-05 | Trusted evidence/basis provenance exposed without fabricated deep-links | **IMPLEMENTED / regression evidence** |
| B1-06 | Stale/proposed/rejected authority cannot mutate canonical state | **IMPLEMENTED boundary; broader temporal production qualification remains separate** |
| B1-07 | C3b consumes the shared reconciliation/trust boundary; no second reconciliation authority | **PARTIAL / integration evidence; #831 remains the governing broader temporal journey authority** |
| B1-08 | Unsupported dimensions remain null/Unknown with disclosed coverage | **IMPLEMENTED / CI evidence** — #840 |
| B1-09 | Anti-gaming: acknowledgement/explanation does not improve raw score; validated false-positive uses canonical recalculation | **IMPLEMENTED / CI evidence** — #853 + #857 |
| B1-10 | Semantic Alert category/trigger/evidence contract | **IMPLEMENTED / regression evidence** |
| B1-11 | Durable roundtrip and atomic review→rescore boundary | **IMPLEMENTED / CI evidence** — #858 + #857 |
| B1-12 | Exact-runtime production acceptance of the complete Alerts+Coherence matrix | **PENDING** |
| B1-13 | Trusted/projected score authority and same-engine/same-version projected subscores | **IMPLEMENTED / CI evidence** — #840 + #857 |

## 7. Closure decision

B1 runtime implementation is no longer an open-ended feature-development lane.

### Closed at implementation level

- family vs observation identity;
- durable disposition basis;
- ambiguous legacy fail-closed behavior;
- Alert/Coherence transaction boundary;
- validated false-positive canonical rescore;
- review→rescore atomicity;
- projected subscore authority and honest-null handling.

### Not promoted by this document

- exact-runtime B1 production acceptance (B1-12);
- global Coherence-v2 authoritative cutover;
- C3b full temporal V1→V2 production journey;
- Product Control lifecycle fields;
- broader ADR-019 ActionItem ownership/automation;
- P1 Project Controls production qualification.

## 8. Next execution goals

Short-term:

1. finish current correctness hardening before new product scope;
2. reconcile Product Control and development-control baselines to the exact current main;
3. preserve B1 regressions as mandatory CI contracts;
4. build the bounded Alerts + Coherence production acceptance matrix for B1-12.

Medium-term:

1. execute P0c What Changed production qualification;
2. execute P0d Current State production qualification;
3. enter P1 Project Controls through PC-1/PC-2: one canonical WBS and baseline/change governance;
4. keep Schedule as a linked temporal domain, never a source of canonical WBS identity.

Long-term:

1. complete Project Controls cross-domain backbone;
2. qualify governed Risk Register semantics on that backbone;
3. make Procurement Plan / BoQ / RFQ / award consume canonical WBS packages rather than create parallel hierarchy;
4. qualify the complete Contract → Project Controls → Procurement user journey with exact-runtime evidence.

## 9. Change control

Any future change that weakens sections 3–5 requires explicit architecture review.

Regression tests may become stricter; they must not be weakened simply because a later refactor changes implementation shape.

Production promotion remains evidence-driven and must bind exact deployed backend/frontend/runtime identities.
