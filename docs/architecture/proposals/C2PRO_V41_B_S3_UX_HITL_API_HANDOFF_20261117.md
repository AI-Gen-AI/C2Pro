# C2Pro V4.1 — S3 API/UI contract handoff to UX and Backend HITL

**Owner of this contract:** Frente B (read-only response semantics).
**Owners of implementation:** UX (presentation), Backend HITL (decisions,
authorization and audit), Ops (identity/deploy), QA (independent acceptance).
**Canonical coordinator:** GitHub #1049. No new screen or HITL action is
implemented in this PR. This is a grounded existing-API handoff.

## 1. Existing routes and payload contracts

| Surface | Existing endpoint | Fields to respect |
|---|---|---|
| Health | `GET /api/v1/projects/{project_id}/health` | `HealthVector.composite_score: number|null`; `composite_band`, `composite_trend`, `dimensions[].{dimension,score,band,confidence,evidence,missing_data,null_reason}` |
| Coherence | `GET /api/v1/coherence/dashboard/{project_id}` | `coherence_score`, `trusted_score`, `score_version`, `score_reason`, `score_missing_dimensions`, `projected_score`, `projection_baseline_score`, `projected_delta`, `pending_review_count`, `projection_status`, `projection_reason` |
| Persistent alerts | `GET /api/v1/alerts/projects/{project_id}` | `AlertListResponse.items[]`: `id`, `category`, `rule_code`, `severity`, `status`, `evidence_status`, `source_clause_id`, `detection_evidence`, `reviewed_by`, `reviewed_at`, `affected_entities` |
| Alert evidence | Same `AlertResponse` object | `detection_evidence.source_{document_id,revision_id,locator,clause_id}`, `claim`, `quote`; `structured_sources[]`: `family`, `document_id`, `revision_id`, `source_locator`, `blob_sha256` |

*URL sources:* `apps/api/src/health/adapters/http/router.py`,
`apps/api/src/coherence/router.py`,
`apps/api/src/alerts/adapters/http/router.py`,
`apps/api/src/alerts/application/dtos.py`,
`apps/web/lib/api/contracts.ts`. These are exact schema shapes currently
present in repo, not additional new API commitments.

IMPORTANT: Health currently uses domain dimensions CONTRACT, RISK,
DOCUMENTATION, GOVERNANCE, SCHEDULE, COST, DELIVERABLES; Coherence uses
SCOPE, BUDGET, TIME, TECHNICAL, LEGAL, QUALITY. **Do not relabel one
taxonomy as the other** without an explicit versioned mapping. The
single-document coverage has six categories; this is not automatically
six complete project Health dimensions.

## 2. Required UI decisions / fail-honest semantics

1. **Unknown is not healthy:** a null score is displayed as unknown/not assessed
   ("—"), never "0", "100" or "sin riesgo". Surface `null_reason`,
   `missing_data` and coverage alongside any numeric subtotal.
2. **N4/N12 incomplete:** no "clean assessment" proof when no risk was found
   but N12 critique is `UNASSESSED`. Fixed in B `risk_scorer.py`.
   Existing source-verified risk score may remain unchanged with explicit
   missing-critical-coverage warning and reduced confidence.
3. **Trusted/provisional split:** `trusted_score` or canonical
   `coherence_score` is the validated current score. `projected_score`
   is **only** a what-if scenario if all actionable proposals were
   approved unchanged. Display separately with "provisional", never
   copy it to canonical state, never add `projected_delta` to trusted score.
   No pending candidates: no projected panel; unavailable projection:
   show reason without hiding the validated baseline.
4. **Per-risk item:** show severity, title, category, state (PROPOSED /
   source VERIFIED / NOT_VERIFIED / trusted review state), short rationale
   and expandable exact source/revision/locator/quote. A source-verified
   quote alone does not mean a human approved the risk.
5. **Alerts are distinct:** an alert may be open with score null. A
   scoreless re-evaluation must not create duplicates, erase a human
   review or auto-resolve a prior alert on missing evidence.
6. **Human decisions:** review/approve/reject/correct must use the
   existing exact-candidate, ACL/SoD, revision-and-version-bound HITL
   service. A "mark risk as accepted" / alert acknowledgement is **not**
   evidence that project coherence improved or PROPOSED was trusted.
   No new decision mutation is authorized to Frente B.
7. **Tenant boundary:** unknown project and foreign tenant project both
   receive 404 for Health and alert project reads; no filename,
   locator or alert is disclosed across tenants. A 404 is not a blank
   valid project (200 with UNKNOWN).
8. **S7 source provenance:** a spreadsheet `source_locator` is an
   observed row, not an approved WBS node. Link to original bytes only
   if document/revision/hash/locator belongs to tenant and original.

## 3. Acceptance matrix UX / Backend / QA

| Input | Expected UI+API | QA owner |
|---|---|---|
| No Health snapshot | `null`, `UNKNOWN`, "no health snapshot available" | UX+QA |
| N4 zero verified risks, N12 unassessed | risk `null/UNKNOWN`, no clean evidence, no green badge | QA |
| Verified risk + N12 unassessed | keep supported subtotal; add critique gap, cap confidence | QA |
| One PROPOSED with no citation | risk not VERIFIED/trusted; source link disabled; no Score boost | UX+HITL |
| Trust 72, projected 88, 2 pending | display 72 current and 88 provisional separately; no canonical mutation | UX+QA |
| Score unassessed, alerts persisted | `null` score with still-visible alert count and severity | UX+QA |
| Re-evaluate same scoreless alert twice | one persistent alert, no auto-resolution or duplicate | Backend+QA |
| Review acknowledgement of risk | decision recorded; no automatic numeric change unless independent canonical recalculation with evidence | HITL+QA |
| Source revision stale/foreign | no source render, no cross-tenant disclosure | Backend+Ops |
| Accept actual candidate once / retry | exactly-once durable human decision, item audit, no hidden approve-all | HITL+QA |

## 4. Current verification vs remaining ownership

- B exact-SHA focused S3 unit suite: 172/172 PASS; 6/6 real-PG
  scoreless-alert persistence tests PASS. Both are **not** browser UAT.
- UX component `ProjectedCoherencePanel.tsx` already distinguishes
  trusted/provisional; QA must verify the user-facing route after
  runtime deployment on exact composite SHA.
- No evidence that every per-risk UI action, HITL finalization,
  source locator and cross-document WBS link is visible and correct in
  an authenticated real-browser session.
- **GO technical conditioned; NO-GO for final S3 UX acceptance.**
