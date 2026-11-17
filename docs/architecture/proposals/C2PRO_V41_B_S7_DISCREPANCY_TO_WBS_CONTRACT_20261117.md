# S7: contract for EPC discrepancy → canonical WBS (Frente B handoff)

**Status:** technical interface / test contract; **NO approved human link has
been fabricated**. Coordinator: CORE #1049; PR owner #1258. WBS owner:
Backend WBS/ProjectGraph; human review owner: UX/Backend HITL. Frente B can
evaluate/read evidence; it cannot auto-approve or create another WBS engine.

## 1. One read-side relationship with separate kinds of authority

`tenant_id → project_id → original_document_id → current_revision_id
→ blob_sha256 → paragraph/section/row locator → detected_discrepancy_key
→ [candidate WBS baseline/node] → [governed mapping approval event]`

The first six steps identify original evidence; **they never confer WBS
approval**. The discrepancy key groups two **numeric detectors for the same
contract/budget totals** but is not a source-of-truth contract amendment,
approved project impact, financial cost booking or HITL record.

Required response fields (additive, not a new canonical table):
- `tenant_id`, `project_id`: from authenticated scope, never client.
- `source_document_id`, `source_revision_id`, `source_blob_sha256`,
  `source_locator`, `source_family`.
- `alert_id`, `rule_code`, `economic_discrepancy_key` (if paired).
  `severity` and `severity_qualification` are separate.
- `source_binding`: `CURRENT_SOURCE_ROW_RESOLVED_NOT_HITL_APPROVED`
  or `NOT_VERIFIED`. Resolving a hash is **not** proof of review.
- `candidate_baseline_id`/`candidate_node_id` (may be null);
  `approved_wbs_link_event_id` **only** after human event.
- `wbs_link_state`: `UNMAPPED` / `PROPOSED` /
  `CURRENT` / `STALE_SOURCE` / `STALE_WBS` /
  `STALE_BOTH` / `UNVERIFIED`. Only `CURRENT` explicitly governed
  mappings count as approved; merely sharing project UUID is `UNMAPPED`.
- `coherence_trusted_score` versus `projected_score` / `pending`
  remain distinct: link approval alone does not improve Coherence.

## 2. Reuse existing WBS services — no parallel engine

For Budget/Schedule row mapping:
- POST/GET `/api/v1/projects/{project_id}/structured-wbs/canonical-links`
  (see `analysis/adapters/http/structured_wbs_link_router.py`).
- `ApproveStructuredWBSLinkService` rejects non-Clerk user, untrusted
  document revision, wrong hash/locator, foreign tenant/project, inactive or
  non-current WBS baseline, conflict in exact source row, or replay with
  different approval intent. Reads report `CURRENT`, `STALE_SOURCE`,
  `STALE_WBS`, `STALE_BOTH`, `UNVERIFIED`.
- A budget activity is **not** a WBS node and link approval does not
  authorize a budget cost/contract date baseline.

For technical source/section mapping:
- `technical-wbs/reviews` records audit-only human review; a separate
  canonical approval endpoint and `ReadCanonicalTechnicalWBSLinksService`
  attest current approved mapping, without asserting technical compliance.
- A `Section 4.1.2` / `Section 4.2` clause stays unverified until
  explicitly reviewed and approved; the current four-source fixture has
  **zero** such approval events.

For contract clauses:
- Original contract paragraph, clause ID if trusted, revision and hash must
  bind to the governing project before referencing a WBS requirement.
- No existing, independently qualified four-source approval path is proven
  by these tests. Source quote exists ≠ approved review ≠ WBS link.
  **Owner:** Backend WBS + UX/HITL, not Frente B.

## 3. Negative-gate acceptance

| Case | Expected |
|---|---|
| Four original sources share project but WBS legacy/unapproved | WBS link request fails closed; no implied CURRENT mapping |
| Document revision UUID belongs to another tenant | No bytes, hash, row or mapping returned |
| Wrong/orphan source revision or locator | `NOT_VERIFIED`, never fabricate hash or source clause |
| Provided blob hash differs from current original revision | Do not overwrite mismatched expectation silently; `NOT_VERIFIED` |
| Source changes after approval | Read state `STALE_SOURCE`; no automatic migration to new revision |
| WBS baseline/node changes | `STALE_WBS` or `STALE_BOTH`; no silent link reattachment |
| Critical analysis incomplete | `overall_score=null`, alerts persist, no healthy label |
| Two rules on one exact economic discrepancy | Same `economic_discrepancy_key`, one score penalty, two independently reviewable alert codes |
| Acknowledgment/acceptance of risk | No automatic score boost and no PROPOSED→VERIFIED transition |

## 4. Evidence from B and remaining acceptance

**New B PG** `test_s7_triplet_four_family_wbs_evidence_pg.py`
runs the four pinned, original synthetic files, real SQL/worker/evaluator,
reopens a second DB session, proves two economic alerts share one numeric
impact, a 92-day **provisional** alert, stable current SHA/row link, real
unverified technical clauses and `NULL` Coherence. The legacy WBS
link authority refuses approval in the absence of a current governed baseline.
Invalid tenant, revision, row and tampered blob SHA do not acquire source
authority. **No HITL decision is executed by B.**

**NO-GO for functional S7:** Backend WBS + HITL must demonstrate a human-
governed current baseline and valid exact WBS relationships **for the same
four original files**, followed by PostgreSQL readback, tenant separation,
relogin and non-promotion after stale/rejected decisions. The pre-existing
three-family PG tests use separate synthetic files, so they **cannot** be
claimed as end-to-end approval of this four-source fixture.

**NO-GO S8:** no complete real browser Journey proof. A's real SEC contract
and B's synthetic fixture remain completely separate.
