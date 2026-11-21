# B4 — Source-only provisional comparison (20 November 2026)

**Status:** PASS_LIMITED / isolated harness only. No UAT deployment, merge, model calls, database writes, acceptance or score.

## Why B4 exists

B3/PR #1281 proves immutable revision inventory can reach the actual ProjectGraph source-loading/identity nodes. The runtime still does **not** supply source rows or contract quotes to the comparison node, and N4→N12 has not been validated.

B4 avoids a second comparison engine: `preview_b4_provisional_comparison()` reuses the **existing** `compare_original_source_rows()` and its `schedule_overruns_deadline()` and `budget_exceeds_contract()` comparators. It is an explicit read-only preview, not part of the production workflow.

## What was demonstrated

Synthetic fixtures from one tenant/project and three revision-pinned source references:
- Contract: an in-memory `DocumentArtifact` test stand-in for a repository-loaded trusted contract; two test N2 chunk quotes with self-consistent SHA-256 and locators.
- Schedule: one synthetic normalized source activity; date-only completion 2027-08-12 against contractual 2027-05-12.
- Budget: one synthetic explicit declared total USD 1,300,000 against contract price USD 1,000,000.

Expected outputs:
- `DET-CRS-SCHDEAD`: +92 calendar days, **PROVISIONAL**.
- `DET-CRS-NEGMARGIN`: +USD 300,000, **PROVISIONAL**.
- Each output includes a contract quote pointer and structured-source revision/locator pointer, review required, `scored=False`.
- `coherence_score=None`, N12 not run, no trusted promotions, snapshots, alerts or approval writes.

Negative checks: absence of trusted artifact yields NOT_ASSESSED; mismatched tenant/project/revision/blob, invalid unit/quote checksums, wrong artifact revision, duplicate locators, and unlabeled budget totals are rejected. No comparable quotes yields NOT_ASSESSED, not a green pass.

## Critical non-claims

- The schedule normalization in this test is synthetic; the native MPXJ parser does **not** establish timezone/calendar semantics or an approved completion milestone. An automatically selected maximum task finish is NOT an approved project finish.
- The fixture's `DocumentArtifact` is mock data, **not** proof that N4, N12 or HITL produced/approved anything. Likewise an N2 quote hash is self-consistency, **not** physical PDF page attestation.
- An `unit_sha256` confirms that a proposed JSON payload is internally intact, **not** that a real XLSX/XER/MPP byte stream or a declared BOQ total was independently parsed. Only the existing revision-scoped reader may certify original file origin.
- Budget margin/tax/scope must be comparable; a sum of individual BOQ lines must not silently become a declared total.
- `preview_b4_provisional_comparison` is not an endpoint; it must never be exposed with arbitrary client-supplied artifacts/units/quotes or called as a trust/score authority. It expects inputs from existing tenant-scoped trusted-artifact and original-revision resolvers.

## Next functional gate, not another synthetic benchmark

Use one **real, consented, same-project** contract PDF and its relevant annexes + schedule and budget revisions:
1. Resolve and verify original immutable bytes and document versions through existing use cases.
2. Supply N2 literal text/physical source references (N4/N12 quality separately checked) and original XLSX schedule/budget units; do not fabricate "TRUSTED" artifacts for source-only candidates.
3. Verify field-level normalization: date calendar, selected completion milestone, currency, taxes, total semantics, source coverage and the exact source locator.
4. Execute one read-only ProjectGraph comparison and show provisional evidence to a reviewer; allow NOT_ASSESSED whenever evidence or comparability fails.
5. Only after that verify N4→N12→HITL and then consider score/alerts under their original authority gates.

**Recommendation:** Keep B4 as a DRAFT experimental stack on B3, without modifying #1276, main, Railway or Vercel.
