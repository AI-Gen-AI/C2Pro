# ADR-032: Explicit Human Trust Approval of Structured Sources (Budget and Schedule)

**Status:** Accepted with conditions (owner, 2026-11-01). Implementation bounded to #1112 by the single writer; no integral UAT and no paid AI until the focused S7 increment is evidenced.
**Date:** 2026-11-01 (amended 2026-11-01 with the owner's decisions Q1–Q4 and conditions C1–C5)
**Decision class:** Trust / HITL / canonical-source architecture
**Conforms to:** ADR-026 (trusted-state commit boundary, #714), ADR-027 (processing authority), ADR-025 / ADR-029 (canonical WBS; `SCHEDULE ACTIVITY != WBS NODE`), ADR-031 (a schedule *baseline* approval is a different fact), ADR-020 (HITL)
**Amends:** nothing. It adds a second *entry point* to the existing trust authority; it creates no second authority.
**Evidence:** integral S1–S8 deterministic rehearsal `41243943437` on `964c08f23` (#1112), independent PostgreSQL read.

## Owner decisions and conditions (binding, 2026-11-01)

- **Q1 — separation of duties ON by default.** A requester cannot approve their own candidate. The only exception is an explicit, audited, per-tenant setting (never implicit): `trust_governance.structured_source_self_approval = {enabled, reason, granted_by, granted_at}`. Every decision that uses it records `self_approved = true`, `self_approval_exception = true` and the reason in the audit event; it is reported as *not an independent approval*.
- **Q2 — no automatic candidates at ingestion** in this increment.
- **Q3 — API and UI.** The request and the human decision ship with an interface (Documents row action and review-card decision); S7 is not complete without them.
- **Q4 — legacy route.** `/hitl/queue/{id}/approve|reject` refuses every review that carries a `candidate_binding` and has no graph `thread_id`; legacy reviews without a binding behave as before.
- **C1 — visibility.** Structured artifacts are outside ProjectGraph input, the projected-Coherence input and analytic materialization, but remain visible to the revision authority (resolver, Current State, What Changed) and to the WBS link services.
- **C2 — typed commit.** No free-form flag on `commit_candidate`. A separate, typed and validated operation commits structured candidates; the graph operation refuses structured artifacts and the structured operation refuses everything else.
- **C3 — distinct states.** *Unevaluated source*, *absence of amounts*, *rejected source* and *resolved alert* stay distinct; their observable effects are documented (table below) and asserted by tests.
- **C4 — no APPROVED-while-PROPOSED.** A bound, thread-less review cannot end APPROVED while its artifact is PROPOSED, and legitimate recovery is never silently blocked (the refusal names the correct endpoint, is logged, and the decision endpoint is the recovery path).
- **C5 — the 409s stay.** Stale versions, hashes or authorities keep answering 409 in the trust endpoints and in the unchanged link services.

## Context

The S7 canonical-link services (`ApproveStructuredWBSLinkService`, `approve_canonical_technical_wbs_link`) are correct and must not be weakened: a link may rest only on a source revision that is **TRUSTED and current**, re-verified against the stored bytes, the row locator, the WBS baseline and the node.

The integral run shows that a Budget or Schedule workbook uploaded through the UI can **never** satisfy that precondition:

| Observation | Evidence |
|---|---|
| `POST structured-wbs/canonical-links` for Budget and Schedule answers **409** "Canonical source or WBS authority changed"; the technical link (a contract-family source) answers 201 | run `41243943437`, S7 |
| PostgreSQL holds **0** `document_artifacts` rows for the Budget and Schedule documents; the resolver status is `single_revision`, never `trusted` | verifier checks `S7: budget/schedule … trusted artifact`, and a local probe against PostgreSQL |
| The only writer of a TRUSTED artifact is graph completion (N17) or the HITL **graph resume** finalization; `commit_candidate` has exactly **one** caller (`resume_ownership.commit_trust_in_transaction`) | code |
| A review row without a graph `thread_id` is decided by `service.approve_item`, which **only flips the row status**: it never calls `commit_candidate` | `hitl/adapters/http/router.py`, non-graph branch |

Structured sources are completed by structured parsing and "legitimately never need the text graph" (`ingestion_tasks.TEXT_ANALYSIS_DOCUMENT_TYPES`). They therefore have no candidate to approve and no human act that could make them trusted. The consequence is a product gap, not a test defect: S7 cannot pass for Budget and Schedule, and today's `single_revision` fallback treats an unreviewed upload as the current source.

## Decision

Reuse the #714 trust authority (`PROPOSED → TRUSTED` by exact binding, compare-and-set under a row lock, immutable audit) through a **new, explicit, human-driven entry point for structured sources**. Nothing is trusted by import, by parsing, by the existence of a WBS or by linking.

### D1 — A structured candidate is a `DocumentArtifact` with no AI content

A candidate is a persisted `DocumentArtifact` (`document_artifacts` row, `trust_state = proposed`) with `doc_type ∈ {budget, schedule}` and `document_revision_id` set. It carries **no** `extracted_risks`, `extracted_wbs`, `bom_items`, `coherence_findings` or confidence: those fields stay empty, so nothing the structured file contains is re-presented as an analysis result.

Identity of the structured content is carried by one additive, optional, frozen field of the contract:

```
structured_source: { family: "budget"|"schedule",
                     blob_sha256,            # == document_revisions.blob_hash, re-verified from the stored bytes
                     parser_id, parser_version,
                     row_count,
                     content_digest }        # SHA-256 of the canonical JSON of the parser-observed rows incl. source_locator
```

`artifact_hash` (already `sha256(canonical payload)`) therefore binds document, revision, bytes and parsed content. The change is additive and optional (absent ⇒ `None`), so `PAYLOAD_CONTRACT_VERSION` stays `v1` and every persisted payload still validates; the cost is that code older than this change cannot read a payload carrying the field (`extra="forbid"`), which matters only for a rollback after a candidate was requested. Tenant and project are the artifact row's own scoped columns (RLS), as for every artifact. The rows themselves are **not** copied into the payload: the bytes are immutable, the parse is deterministic, and the link services already re-parse the verified bytes by locator.

### D2 — Upload creates an untrusted source; a candidate exists only on explicit request

Upload and ingestion are unchanged: the revision stays untrusted (`single_revision`), nothing is proposed, nothing is reviewed. A human **requests** a trust candidate for a specific revision:

`POST /api/v1/documents/{document_id}/revisions/{revision_id}/trust-candidate`
body `{ idempotency_key }` → `201 { artifact_id, artifact_version, artifact_hash, review_item_id, review_row_id }`

The service (one tenant-scoped transaction): authenticates a human user (same predicate as the link services: active, role admin/user, bound `clerk_user_id`); locks DOCUMENT → PROJECT; re-reads the stored bytes and **re-verifies `blob_hash`** (`read_verified_revision_file`); parses with the existing `ExcelFileParser`; builds the candidate; calls the existing `repository.save(artifact, trust_state=PROPOSED)` (which supersedes older proposals, closes their reviews, and opens a review **bound to exactly this artifact id/version/hash**). Replays with the same `(revision, content_digest, idempotency_key)` return the same candidate; a different key for an identical pending candidate is also a replay (never a second candidate). Non-XLSX, unparsable, or empty sources are refused (422) before anything is written.

*Owner decision Q2: no automatic creation in this increment. Why on request and not at ingestion:* proposing at ingestion changes the evaluation semantics of every existing budget upload (see E5) and every existing journey. It is the natural end state, but it is a separate, later amendment; this increment must not move any score or alert that is not explicitly under review.

### D3 — The decision is a dedicated command that commits in the same transaction

`POST /api/v1/documents/{document_id}/revisions/{revision_id}/trust-decision`
body `{ artifact_id, artifact_version, artifact_hash, decision: "APPROVE"|"REJECT", reason, idempotency_key }`.

One transaction, canonical lock order **DOCUMENT → PROJECT → ARTIFACT** (as `materialize_in_transaction`): verify the review row bound to exactly this binding is pending and `decision_ready`; verify the artifact is still the current PROPOSED version with that digest; re-verify the revision bytes; record the review decision (`approved_by`, `approved_at`, rejection reason); then the **typed** structured operations `commit_structured_candidate` (APPROVE) or `reject_candidate` (REJECT); append the audit event (D6). `commit_structured_candidate` accepts only an artifact whose payload carries a valid `structured_source` (family budget/schedule) and performs the same compare-and-set as `commit_candidate` with its own, fixed effect set (no projection obligation, `materialization = not_required`); `commit_candidate` in turn refuses a structured artifact. There is no parameter that selects effects. APPROVE and the commit cannot be separated: there is no state "approved but not trusted".

Replays return the stored decision; a changed replay (other decision, reason or binding) is refused; a binding that no longer matches the current PROPOSED version (superseded by a newer request, rejected, already trusted with other content) fails closed with **409** (`StaleCandidateError`), exactly as in #714.

The refusal is enforced **in the service layer** (`HumanInTheLoopService.approve_item` and the route's thread-less reject branch), not only in HTTP, so no caller can reach it: a review that carries a `candidate_binding` and no graph `thread_id` is refused with a typed `BoundReviewRequiresTrustDecision` (HTTP 409, logged, message naming the trust-decision endpoint). Reviews without a binding (legacy) and graph reviews with a thread are unaffected. The trust-decision endpoint records its own decision through the review repository inside its own transaction; it is the legitimate recovery path for a bound thread-less review. This closes a latent hole: today a bound, thread-less review (e.g. the minimal review opened when HITL routing degrades) can be flipped to APPROVED while its artifact stays PROPOSED.

### D4 — Materialization effects, resolved one by one (E1–E9)

| # | Effect of `commit_candidate` today (graph artifact) | Effect for a structured candidate | Resolution |
|---|---|---|---|
| E1 | Records a ProjectGraph projection obligation (`trusted_projection_index.projection_state = pending`) and the Celery enqueue follows | A graph run on trusted artifacts would load the structured one | **No obligation, no enqueue.** The structured commit uses a repository variant that skips `_record_projection_obligation` and `enqueue_project_graph` |
| E2 | `list_trusted_for_project` is the **ProjectGraph input** (coherence, impact, Health snapshot) | A budget/schedule artifact with empty lists could be read as "budget present, total 0" | `list_trusted_for_project`, `list_active_for_project` and `list_pending_candidates` **exclude** artifacts whose payload has `structured_source`. They are authority records, not analysis output |
| E3 | `materialize_in_transaction` writes an `analyses` row (type `SCHEDULE`/`RISK`), alerts from risks, a `materialization.completed` event | Would create an analysis row with a null score and a mislabelled type | **`materialization_state = not_required`** for structured candidates; the materializer is never invoked. No `analyses`, no alerts, no completion event |
| E4 | Canonical WBS / BOM / RACI | Schedule activities are never canonical WBS (#852); budget lines never canonical BOM (#860) | Unchanged and explicit: nothing is written. WBS stays governed by ADR-029 |
| E5 | Resolver `canonical` (budget declaration, mirror guard) is `trusted OR (single AND (any_trusted OR NOT any_proposed))` | While a candidate is PENDING the budget is **not canonical** (a PROPOSED artifact never moves canonical alerts: ADR-026) | **Accepted and stated:** requesting a candidate suspends the budget's canonical findings until the decision; the evaluation reports the budget as *not evaluated*, never as resolved (existing mirror guard). After APPROVE the revision is `trusted` and `canonical` again with identical content |
| E6 | Reupload of a document with a trusted artifact | A later revision stays pending until its own candidate is approved (existing rule `trusted_bound = 1 ⇒ current = trusted revision`) | Unchanged; it is the revision-authority rule, now applicable to Budget/Schedule |
| E7 | ADR-031: `BASIS_APPROVED_BASELINE` means a human approved this schedule revision as the temporal baseline | Trust of a schedule *source* is not a baseline approval | **No interaction.** A trusted schedule source does not alter planned-finish basis, TIME, or Score |
| E8 | Document lifecycle (`analyzed`), RAG chunks, clauses | Unaffected | Unchanged |
| E9 | Pending projected Coherence (trusted + pending candidates) | A structured candidate would be projected | Excluded by E2: no projected value changes |

Net effect of an approved structured trust: one `document_artifacts` row `trusted/active`, the previous trusted one `superseded`, one review decision, one audit event. No Health, Coherence, ProjectGraph, Alert, WBS or Score row changes.


### D4b — Observable distinctions (C3), asserted by tests

| State | How it arises | Evaluation / alerts / score (observable) |
|---|---|---|
| **Unevaluated source** | A budget with a pending candidate (not `canonical`), or an unresolved document | The evaluation reports the document as not evaluated (`evaluation_complete = false`); the alert mirror never auto-resolves anything on its account; the dimension is *missing*, never zero |
| **Absence of amounts** | A trusted or single budget whose workbook declares no stated total | No budget declaration (`stated_total` absent) → the BUDGET dimension is not assessed; **not** a total of 0 and **not** a rejection |
| **Rejected source** | A candidate that a human rejected (`rejected_only`, single revision) | The revision stays unresolved/untrusted; nothing trusted; alerts preserved; it is never read as current |
| **Resolved alert** | An evaluated finding no longer holds on evaluated evidence | The only state that may resolve an alert; requires the sources to have been evaluated |

### D5 — Linking stays a separate, stricter act (unchanged services)

A TRUSTED, current source only **enables requesting** a link. The link approval remains the existing explicit human act with full revalidation of baseline, node, revision, blob hash and locator, and keeps its **409** for stale sources or authorities. No check of `ApproveStructuredWBSLinkService` or the technical equivalent is relaxed or bypassed. Trust approval never creates, implies or pre-approves a link, and a link approval never trusts a source.

### D6 — Audit and self-approval

Two new `ProjectEvent` types (registry `KNOWN_EVENT_TYPES`): `structured_source.trust_requested` and `structured_source.trust_decided`. Payload: family, document, revision, artifact id/version/hash, `blob_sha256`, `content_digest`, row count, actor (`user:<id>`), decision, reason, idempotency key, and for the decision `requested_by`, `decided_by`, **`self_approved`** (`requested_by == decided_by`). Separation of duties is **enforced by default** (Q1): `decided_by == requested_by` is refused (HTTP 403 `SEPARATION_OF_DUTIES_REQUIRED`) unless the tenant carries the explicit exception setting above. A decision under the exception is recorded with `self_approval_exception = true` and the reason, and the verifier and the manifest report it as *not an independent approval*.

### D7 — Persistence

No new table and no new RLS surface: candidates are `document_artifacts` rows, reviews are `review_items` rows, audit is `project_events`. `trusted_projection_index` is not touched for structured sources (E1/E3). The one DB-visible change is verified to be only code-level (event types are validated in the domain registry); if a database CHECK on `event_type` exists it gets one Alembic migration plus the Supabase CLI sync (the two migration systems must stay aligned).

## Pre-implementation verification gates (results recorded 2026-11-01)

- **G1.** `list_pending_candidates` and `project_pending_coherence` tolerate an artifact filtered out by `structured_source` (E2/E9). **Result: PASS (code read).** `list_pending_candidates` builds its result from `_ACTIONABLE_PENDING_SQL` rows and a second `select`; filtering the built list cannot break the projection, which treats an empty list as "no pending". The dashboard's `pending_review_count` is derived from that same pending-candidate list, so it too excludes structured candidates (it counts analysis proposals feeding the projection); a pending structured candidate is visible as a review item in the Review queue and as a state of its Documents row, not in the Coherence pending count. Asserted by test 10.
- **G2.** The resolver keeps `trusted` for the revision of a structured artifact without a graph run ever loading it. **Result: PASS (code read).** `current_revision_lateral` reads `document_artifacts` only (`trust_state='trusted' AND lifecycle_status='active' AND document_revision_id IS NOT NULL`); it never consults `trusted_projection_index` or a graph run. Asserted by test 4.
- **G3.** The legacy-approve guard breaks no existing journey. **Result: see the delivery report** (the PJ-01 / triplet / S5 / S7 suites are run against PostgreSQL after the guard lands; a graph review always carries a `thread_id`, so the guard cannot reach it).
- **G4.** `PAYLOAD_CONTRACT_VERSION` / the `DocumentArtifact` schema are not part of the generated OpenAPI. **Result: PASS.** Neither `docs/api/openapi.yaml` nor `apps/web/schema/api.json` mentions `DocumentArtifact` or `x-contract-version`. The new endpoints and the additive review-response field are, so OpenAPI and the web client are regenerated.

## PostgreSQL test plan (REAL database, real repositories, no mocks of the trust authority)

1. A candidate request on a Budget (then a Schedule) revision creates exactly one `PROPOSED` artifact with `structured_source` (bytes hash, parser version, row count, content digest) and one pending review bound to it; **no** `analyses`, alert, graph event or `trusted_projection_index` row.
2. Idempotent request: same key and same key-less replay return the same candidate; a second key on an identical pending candidate returns it; a changed revision creates a new candidate and supersedes the older one and closes its review.
3. Tampered stored bytes (hash mismatch) → refused before any write (422).
4. APPROVE: artifact `trusted/active`, previous trusted `superseded`, review `APPROVED` with actor and time, event `trust_decided` with `self_approved` computed; resolver status `trusted` for exactly that revision; a replay returns the stored decision; **no** analysis/alert/projection obligation/graph enqueue.
5. REJECT with reason: artifact `rejected`, review `REJECTED` with the reason (SHA-256 compared), nothing trusted, resolver unchanged (`single_revision`).
6. Stale binding (artifact superseded by a newer request, wrong version, wrong hash, already rejected) → 409, zero writes.
7. Concurrency: two simultaneous APPROVE calls commit once (the second is `already_trusted`/replay); an APPROVE racing a newer request fails closed.
8. Tenant isolation: another tenant can neither request nor decide (404/403) and sees neither candidate nor review.
9. Legacy `/hitl/queue/{id}/approve` on a bound, thread-less review → 400 and the review stays pending; on an unbound legacy review → unchanged behaviour.
10. Effects E1–E9 as assertions: ProjectGraph input unchanged; `list_pending_candidates` empty for structured; dashboard/Health/Score byte-identical before and after APPROVE; Coherence evaluation identical before the request and after the approval (and *not evaluated* for the budget while pending, alerts preserved, never resolved).
11. Budget reupload after trust: the new revision stays pending and current stays the trusted one (E6).
12. **Link integration (the S7 cases):** after APPROVE, the structured link request for the exact row succeeds (201) and is `CURRENT`; before APPROVE it answers 409; after a reupload (new revision) the existing link turns `STALE_SOURCE` and a new link request on the stale source answers 409. The three link services are exercised unmodified.
13. Independence: request, decision and link by distinct humans record `self_approved = false`; the same human records `true`; the verifier reports both.

## Acceptance criteria

- **A1** Budget and Schedule revisions uploaded through the UI can be trusted only through D2+D3, with a persistent, exact-binding audit trail.
- **A2** No scoring, Health, ProjectGraph, Alert, WBS, BOM or analysis side effect is produced by a structured trust decision (test 4, 10).
- **A3** All thirteen tests above pass on PostgreSQL; the existing PJ-01, triplet, S5 and S7 suites are unchanged and green.
- **A4** S7 `PASS` in the integral run requires: Budget and Schedule candidates requested and approved by the signed-in human through the application; three `CURRENT` human-approved links; independent PostgreSQL verification of each artifact, review decision, event and link; self-approval reported as such. The runner never writes an artifact, review or event itself.
- **A5** S4 (alert → Budget/Schedule row link), S5 (granular finding decisions) and S3 (reason of an insufficient evaluation) remain `PARTIAL` until their own corrections ship; this ADR does not claim them.
- **A6** Status words follow Product Control vocabulary: merge/CI ≠ `PROD_VALIDATED`.

## Alternatives rejected

- **Trust at ingestion (automatic proposal).** Correct as an end state but moves every existing budget evaluation (E5) at once; deferred to a later amendment (Q2).
- **Let the link approval imply trust.** Collapses two human acts and lets a link create authority.
- **Run N17 / the graph on structured sources.** Fabricates analysis output (a score, an `analyses` row) for data that was never analysed.
- **Populate `bom_items` / `extracted_wbs` from the workbook.** Feeds ProjectGraph, Health and Coherence with data nobody reviewed as analysis, and contradicts #852 / #860.
- **Reuse the legacy approve route.** It flips status without committing; it would create "approved but not trusted".
- **Relax the link checks.** Forbidden (condition 7).

## Consequences

**Positive.** S7 becomes provable on real uploads with an exact, auditable chain (bytes → candidate → human decision → trusted revision → human link); the latent approved-but-uncommitted hole is closed; the trust authority remains single.

**Costs / constraints.** One additive contract field with a version bump; two endpoints, one use case, one repository variant, two event types; a documented evaluation pause for a budget while its candidate is pending; a UI entry ("request trust approval" on the Budget/Schedule row, and the decision on the review card) that the first increment may deliver as API-only if the owner prefers.

## Open questions

None open: Q1–Q4 were decided by the owner (see *Owner decisions and conditions*).

## Validation status

Accepted with conditions; implementation in progress on #1112 (see the delivery report for evidence). Evidence cited above is from the integral deterministic rehearsal (AI mocked), which is not UAT and not production evidence.
