# HITL authorization by project — evidence (PQ-HITL-04C5 / #980), 2026-11-01

Status: **evidence only**. No permission was widened, no role or policy invented, no behaviour changed.
Scope: #1112 head at the time of writing (`integration/acc01-e2e-20261025`). Owner ratification is required before any
authorization policy is implemented; until then S5 is **not accepted on security**.

## What the product authorizes today

| Action | Route | Gate that exists | Project dimension |
|---|---|---|---|
| Read a pending review | `GET /hitl/queue/{item_id}` | authenticated tenant (RLS) | none |
| Read findings + provisional decisions | `GET /hitl/reviews/{row}/findings` | active **human ADMIN/USER** of the review's tenant (`authorize_finding_reviewer`), RLS tenant | none |
| Record a provisional decision | `POST /hitl/reviews/{row}/findings/decisions` | same as above + exact pins (artifact, hash, revision, generation, fencing token) | none |
| FINAL approve / reject | `POST /hitl/queue/{item_id}/approve\|reject` | authenticated user of the tenant — **no role check** | none |

* No membership, ACL, assignment or grant table exists: of 49 ORM tables only `disclaimer_acceptances` has both a project
  and a user column.
* Every RLS policy on `review_items` and `hitl_finding_decisions` is `app.current_tenant` only.
* "Two users of one tenant with different permissions on two projects" is **not expressible**: there is nothing for the
  routes to consult, so no per-project denial can exist. Alerts, WBS governance and temporal routes follow the same rule
  (`project belongs to the caller's tenant`).

## Reproducible evidence

`apps/api/tests/integration/document_flow/test_s5_project_authorization_evidence_pg.py` (real handlers, real PostgreSQL,
5 tests PASS) — characterization, to be flipped when a policy is ratified:

1. no project-level authorization model in the schema;
2. ledger/review RLS policies are tenant-only;
3. an ADMIN and a USER with no tie to the review's project read the findings and record decisions (attributed to them);
4. VIEWER, API and inactive members are denied on the findings routes (403) — the only role gate that exists;
5. **the final approval route accepts a VIEWER**, and the candidate becomes TRUSTED.

## Classification

* **GAP-1 (HIGH, pre-existing, outside the S5 code):** the final approval/rejection routes have no role check. A read-only
  tenant member can turn a PROPOSED candidate into TRUSTED. The S5 routes are stricter than the act they feed.
* **GAP-2 (MEDIUM, design):** no project-scoped authorization. Any ADMIN/USER of the tenant can read and record on any
  project's review. Consistent with the whole product; not introduced by S5.
* Not a GAP: tenant isolation (cross-tenant read/record answer 404, proven in the S5 suites).

## Design criterion (not implemented)

Fail closed when no authorization can be demonstrated. Any project-scoped rule needs an owner-ratified model (who is a
member, who is assigned, which role may read / record / finally approve) before code. This document does not propose one.
