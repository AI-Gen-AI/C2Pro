# HITL authorization by project — technical proposal for S5-01 / S5-02, 2026-11-01

Status: **S5-01 / S5-02 IMPLEMENTED (owner decision D-1…D-7 of 2026-11-01); see "Implementation status" at the end.**
The text below is the original proposal, kept for rationale. Where it differs from what was built, the implementation
status section wins (notably: the FK to `users` is on `users(id)` alone, the tenant is proved at check time). Role gate on the final decision (GAP-1) is already fixed and is
a prerequisite, not part of this proposal. The ratified D1–D8 text was not supplied to the implementer: the mapping
below follows the requirements stated in the commission and must be checked against it.

## 1. Inventory of the authorities that exist today

| Authority | What it knows | Project dimension | Reusable for project permissions? |
|---|---|---|---|
| Clerk JWT (`clerk_auth.py`) | user id, organization id, `org_role` (`admin`/`member`) | none | identity only |
| `users.role` (`UserRole`: ADMIN, USER, VIEWER, API) + `is_active`, `tenant_id` | one role per user, tenant-wide | none | yes: the *human gate* (done). Not a permission source |
| `tenants.settings` (JSONB) | tenant flags (e.g. `trust_governance`, `wbs_governance`) | none | yes: carries a rollout mode |
| `organization_members` | role per org member | none; **exists only in the Supabase CLI migrations, not in Alembic/ORM, and the API never reads it** | no |
| `projects` | tenant, no owner/creator column; `uq_projects_tenant_id (tenant_id, id)` | is the project | provides the FK target |
| `review_items` | `project_id`, `document_id`, status, lineage | yes (the review's project) | provides the resource to authorize |
| RLS | policies on `review_items`/`hitl_finding_decisions` read only `app.current_tenant` | none | tenant isolation only |
| `authorize_finding_reviewer` / `authorize_final_decider` | active human ADMIN/USER of the tenant | none | the identity layer both routes share |

Conclusion: **no reusable source of per-project permission exists** (the only table with both a user and a project
column is `disclaimer_acceptances`). A new source is required; reusing `users.role` or `organization_members` would
either over-grant tenant-wide or depend on a table the API does not own.

## 2. Permissions to support

| Permission | Guards | Today |
|---|---|---|
| `READ_REVIEW` | `GET /hitl/reviews/{row}/findings` (and the review card payload for that row) | tenant ADMIN/USER |
| `REVIEW_FINDING` | `POST /hitl/reviews/{row}/findings/decisions` | tenant ADMIN/USER |
| `APPROVE_CANDIDATE` | `POST /hitl/queue/{id}/approve\|reject`, `POST /hitl/resume/{id}` | tenant ADMIN/USER |

Rules requested: explicit grant and explicit revocation; **ADMIN has no implicit global approval** (an ADMIN holds
`APPROVE_CANDIDATE` only where it was granted); a USER granted on project P1 and not on P2 is allowed on P1 and denied
on P2; REVIEWER (`REVIEW_FINDING`) and APPROVER (`APPROVE_CANDIDATE`) are distinct permissions. Permissions do not
imply each other (a grant bundle is a procedure, not a hierarchy). Reads outside S5 (documents, alerts, WBS, Health) are
**not** touched.

## 3. Exact DDL proposed (Alembic revision + Supabase mirror, both, because the repo has two migration systems)

```sql
-- additive key so a grant can bind the user AND the tenant (same pattern as uq_projects_tenant_id)
ALTER TABLE public.users ADD CONSTRAINT uq_users_tenant_id UNIQUE (tenant_id, id);

CREATE TABLE public.project_review_grants (
  grant_id      uuid PRIMARY KEY,
  tenant_id     uuid NOT NULL,
  project_id    uuid NOT NULL,
  user_id       uuid NOT NULL,
  permission    varchar(20) NOT NULL,
  granted_by    uuid NOT NULL,
  granted_at    timestamptz NOT NULL DEFAULT clock_timestamp(),
  grant_reason  text NOT NULL,
  revoked_by    uuid,
  revoked_at    timestamptz,
  revoke_reason text,
  CONSTRAINT fk_prg_project FOREIGN KEY (tenant_id, project_id) REFERENCES public.projects (tenant_id, id) ON DELETE RESTRICT,
  CONSTRAINT fk_prg_user    FOREIGN KEY (tenant_id, user_id)    REFERENCES public.users (tenant_id, id)    ON DELETE RESTRICT,
  CONSTRAINT fk_prg_granter FOREIGN KEY (tenant_id, granted_by) REFERENCES public.users (tenant_id, id)    ON DELETE RESTRICT,
  CONSTRAINT ck_prg_permission CHECK (permission IN ('READ_REVIEW','REVIEW_FINDING','APPROVE_CANDIDATE')),
  CONSTRAINT ck_prg_reason     CHECK (length(btrim(grant_reason)) > 0),
  CONSTRAINT ck_prg_revocation CHECK (
    (revoked_at IS NULL AND revoked_by IS NULL AND revoke_reason IS NULL)
    OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND length(btrim(coalesce(revoke_reason,''))) > 0
        AND revoked_at >= granted_at))
);
-- at most one ACTIVE grant per (project, user, permission); history is kept
CREATE UNIQUE INDEX uq_prg_active ON public.project_review_grants (tenant_id, project_id, user_id, permission) WHERE revoked_at IS NULL;
CREATE INDEX ix_prg_lookup ON public.project_review_grants (tenant_id, user_id, project_id) WHERE revoked_at IS NULL;

-- immutability: DELETE is refused; UPDATE may only set the three revocation columns, once
CREATE FUNCTION public.project_review_grants_guard() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path = public, pg_temp AS $fn$
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION USING ERRCODE='restrict_violation', MESSAGE='project review grants are append-only'; END IF;
  IF OLD.revoked_at IS NOT NULL OR (NEW.grant_id, NEW.tenant_id, NEW.project_id, NEW.user_id, NEW.permission,
       NEW.granted_by, NEW.granted_at, NEW.grant_reason)
     IS DISTINCT FROM (OLD.grant_id, OLD.tenant_id, OLD.project_id, OLD.user_id, OLD.permission,
       OLD.granted_by, OLD.granted_at, OLD.grant_reason) THEN
    RAISE EXCEPTION USING ERRCODE='restrict_violation', MESSAGE='a grant can only be revoked, once';
  END IF;
  RETURN NEW;
END $fn$;
CREATE TRIGGER trg_prg_guard BEFORE UPDATE OR DELETE ON public.project_review_grants
  FOR EACH ROW EXECUTE FUNCTION public.project_review_grants_guard();

ALTER TABLE public.project_review_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_review_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY prg_tenant ON public.project_review_grants
  USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
```

Event types to register (append-only `project_events`, same transaction as the grant): `hitl.project_grant_created`,
`hitl.project_grant_revoked` (and, for rollout, `hitl.project_authorization_would_deny`).

## 4. Enforcement (S5-02) — one authorizer, three guarded areas

`ProjectReviewAuthorizer.require(session, tenant_id, user_id, project_id, permission)` reads the **active** grant
(`revoked_at IS NULL`) and raises when none exists (fail closed). `project_id` always comes from the review row
(`review_items.project_id`), never from the request. Order in each route: human gate (exists) → load the review in the
caller's tenant → project permission → proceed. `READ_REVIEW` denial answers **404** (no existence leak); the two write
permissions answer **403** with a stable code. The use-case boundary keeps its own check: `AuthorizedFinalDecider` is
extended with the proven project permission so `execute` refuses a decider that was authorized for another project.

Granting/revoking: a service callable by an active tenant ADMIN only, writing the grant and its event atomically. The
grantor must not equal the grantee for `APPROVE_CANDIDATE` (see decision D-3).

## 5. Rollout without locking anyone out

`tenants.settings.hitl_project_authorization.mode` ∈ `off` | `audit` | `enforce`.
* `off` (default for every existing tenant): behaviour exactly as today (role gate only).
* `audit`: the authorizer evaluates and records `would_deny` (log + event) but allows.
* `enforce`: denies. Enabled per tenant, after the tenant's grants exist and `audit` showed zero unexpected denials.

Initial grants are **never created by the migration or by a bootstrap**. An operator-run script
(`scripts/grant_project_review_permissions.py`, dry-run by default, requires `--reason` and the grantor id) creates
explicit grants from a list the owner approves; it can print, as *evidence only*, which users decided reviews before
(from `hitl.correction` events) to help the owner decide.

Integral runner: the isolated tenant A needs its single human granted the three permissions on its project by the
seed; the self-approval remains labelled `SELF_APPROVED_NOT_INDEPENDENT`.

## 6. Tests the implementation must ship

Same USER granted on P1 / denied on P2 across read, review and approve; ADMIN without `APPROVE_CANDIDATE` denied;
REVIEW_FINDING does not allow approving; revocation effective on the next request and recorded; a grant cannot cross
tenants (FK) nor be edited or deleted (trigger); RLS isolation; `audit` mode records and allows, `enforce` denies; the
existing P0b / trusted-state suites unchanged (decider carries the project permission); runner seeding.

## 7. Decisions the owner must take

* **D-1** Confirm the three permissions and the no-implication rule against the ratified D1–D8 text.
* **D-2** Who may grant: tenant ADMIN only? May an ADMIN grant themselves `READ_REVIEW`/`REVIEW_FINDING`?
* **D-3** May a user hold `APPROVE_CANDIDATE` for a candidate whose findings they reviewed, and may a grantor grant it to
  themselves? Forbidding it conflicts with single-human tenants (the isolated tenant A, S7 independence); the ADR-032
  audited-exception pattern would be needed.
* **D-4** Read denial: 404 (proposed) or 403.
* **D-5** Default mode for **new** tenants (`enforce` proposed) and the date after which `off` stops being allowed.
* **D-6** Whether the lookup of a project's grants is also exposed to the UI (to hide Approve) — read-only, proposed.
* **D-7** Authorization to add the Alembic revision and the Supabase mirror, and to run the one-off grant script per tenant.

## 8. Not covered here (observed, out of scope)

`POST /hitl/queue/{id}/release` (closes an already-approved item; no trust change) and `POST /hitl/escalate` (SLA sweep)
authenticate but do not require the human gate; they move no candidate to TRUSTED and are left unchanged. The legacy
`approve_item`/`reject_item` service path for non-graph reviews is reached only through the guarded routes and is refused
for any review bound to a candidate (`BoundReviewRequiresTrustDecision`).

## Implementation status (S5-01 + S5-02, bounded) — added 2026-11-01

**Built:** Alembic `20261101_0001` + Supabase mirror `20261101000100_s5_project_review_grants.sql` (additive; downgrade
provided); `project_review_grants` (append-only, single revocation, guard trigger, SECURITY DEFINER writers that write
the grant and its audit event in one transaction, forced RLS, REVOKE from PUBLIC/anon/authenticated); one
`ProjectReviewAuthorizer` applied to findings read (READ_REVIEW), granular decisions (REVIEW_FINDING) and
approve / reject / resume (APPROVE_CANDIDATE) at the application boundary (`ResumeWorkflowUseCase.execute`, the findings
services) plus the non-graph decision path; 403 when the actor has other grants on the project, 404 when it has none;
read-only `GET /hitl/reviews/{row}/capabilities` plus the same capabilities on the findings read, and advisory UI hiding that costs no extra request (the product's per-user rate limit is 60 requests/minute and the E2E smoke suite sits at its edge: a dedicated per-card call tipped it over, proven by a 429 in the E2E backend log); `scripts/grant_project_review_permissions.py`
(dry-run by default; `--apply` only on a loopback test database with `ENVIRONMENT=test`).

**Identity (precondition P1):** the principal is `(tenant_id, users.id)`. `get_current_user` reassigns the SAME
`users` row to the new tenant on a Clerk organization switch, so a composite FK `(tenant_id, user_id) → users(tenant_id,id)`
would break sign-in (proven by `test_s5_org_switch_principal_pg.py`). The FK is therefore on `users(id)` and the tenant
is proved at check time (`users.tenant_id = grants.tenant_id AND is_active`): a grant of A is dormant while the user is in
B and applies again in A. No auth refactor was needed.

**Modes and the retirement gate for permissive modes.** `off` and `audit` are TRANSITIONAL, not secure. The migration marks
every pre-existing tenant `off` (transitional) so nobody is locked out and nobody self-grants; a tenant WITHOUT the marker
(every new tenant) is `enforce`, as is an unknown value. **No date is invented.** A tenant leaves `off` only when: (1) its
real grants exist and were reviewed by its owner, (2) a period in `audit` shows no unexpected
`hitl_project_authorization_would_deny`, (3) the negatives (no-grant, partial-capability, other-project) pass for it.
S5 is NOT declared secure while any operative tenant sits in `off`/`audit`. Synthetic nonproduction tenants (E2E and the
integral UAT seeds) carry an explicit transitional `off` marker with its reason, because their project is created by the
journey after the seed.

**Not done / residual:** real grants on real tenants and `enforce` in Production (need separate per-environment approval);
concurrent revocation is *prepared* (`revalidate()` locks the grant `FOR SHARE`, proven by a PostgreSQL concurrency test)
but is not wired into the first-TRUSTED transaction — that is S5-05; queue list/get are not project-filtered; `release` /
`escalate` lack the human gate; grants are dormant, not auto-revoked, when a user leaves a tenant; the legacy characterization
tests in `test_s5_project_authorization_evidence_pg.py` describe the transitional `off` behaviour, not the secure one.

## D1 and S5-03 — implementation status (owner decision of 2026-11-01, second increment)

**D1 — explicit grants after the project exists (nonproduction, isolated database only).** `scripts/grant_integral_uat_project.py`
runs once the journey's project (and the Clerk Development identities A/B, which it never creates) exist: it refuses outside
`ENVIRONMENT=test` on a loopback database; grants READ_REVIEW / REVIEW_FINDING / APPROVE_CANDIDATE through the governed SQL
function (actor, reason, audit event); and switches tenant A and tenant B to `enforce` before any HITL operation. The single
human of tenant A cannot be granted by anyone else, so the step uses the documented, limited, audited single-person exception
(tenant A only; every grant labelled `SELF_GRANTED_NOT_INDEPENDENT`); an independent ADMIN (`--grantor`) needs no exception. The
integral spec calls it right after "project A created" (milestone `project-a-grants-enforce`) and the independent verifier
now holds the run to: both tenants in `enforce`, exactly the three active grants of the authenticated user of tenant A, an actor
and reason on each, the exception complete when a self-grant exists, no exception/grant for tenant B, one audit event per grant.
The earlier rehearsal under `off` keeps its historical value; it does not prove security under `enforce`. **No integral run was
executed for this increment.** PostgreSQL tests (`test_s5_integral_grants_step_pg.py`) demonstrate enforce before/after, denial
between two projects of the same tenant, revocation, A/B isolation and fail-closed behaviour.

**S5-03 — deterministic reconciliation (C+B).** `domain/finding_reconciliation.py` (pure) and
`application/finding_reconciliation_service.py` (loads the exact candidate and the COMPLETE ledger under the caller's project
authority). It is NOT a signature and NOT a promotion: it neither approves, rejects, trusts nor writes anything.

Meaning of each decision (latest decision on a finding wins; the ledger is append-only):

| Ledger state of a finding | Resolution | Effect |
|---|---|---|
| CONFIRMED | RETAINED | valid decision, kept with its evidence (event, reviewer, reason) |
| DISMISSED | EXCLUDED | out of the effective content, history kept; announces DISMISSED_EXCLUSION (a derived Vn+1 is required) |
| NEEDS_INFO | BLOCKED_NEEDS_INFO | blocks the signature until a LATER decision supersedes it |
| CORRECTION_PROPOSED | CORRECTION_PENDING | announces CORRECTION_PROPOSED (a NEW candidate and its own signature); never applied |
| none | UNDECIDED | blocks (fail closed) |
| critique | — | blocks only if MATERIAL, evidence VERIFIED and OPEN; otherwise advisory |

`signable_as_is` is true only when nothing blocks and no derived candidate is required. A ledger that is not contiguous from
revision 1, whose CAS chain is broken, that holds an event of another tenant/review, a duplicate event, or a decision on a
finding outside the candidate is INCONSISTENT and concludes nothing. Decisions recorded against another artifact hash,
document revision, generation or fence are STALE: ignored, reported, never applied.

**Contract for S5-04 (signature).** Call `reconcile(tenant_id, user, review_row_id, capability=APPROVE_CANDIDATE)`; sign only
if `result.signable_as_is` (else produce the derived candidate and reconcile that one); bind the act to `result.receipt()`
(`digest`, review/project/artifact id-version-hash, generation, fencing token, ledger revision, effective-content digest,
policy version `s5-03/v1`).

**Contract for S5-05 (first TRUSTED).** Inside the transaction that commits TRUSTED call
`verify_current(receipt, ..., lock=True)` (FOR SHARE on the review row; the ledger writer's FOR UPDATE then waits) together with
`ProjectReviewAuthorizer.revalidate`. A digest difference is `ReconciliationStale`; a revoked grant is a denial, not "stale".
**This atomicity is S5-05's and is NOT claimed solved by S5-03.**

**Pinned gap (closed by S5-04, see below).** `test_GAP_…` pinned that with a NEEDS_INFO on the ledger the final approval still
committed; it is now `test_the_gap_s503_pinned_is_closed_…` and asserts the refusal.

**Critique coverage (honest limit).** Critique has no typed persisted envelope (`finding_decision_writer` refuses CRITIQUE
decisions). The service therefore reports `critique_coverage`: `NONE_PRESENT`, or `UNSTRUCTURED_NOT_EVALUATED` when
`critique_notes` prose exists (an advisory). The material+verified+open rule is implemented and tested on typed input, but no
production producer exists until a typed critique envelope does.

**Residual risks / conditions for S5 acceptance.** S5-04 (signature bound to the receipt) and S5-05 (transactional revalidation of
grant + digest at the first TRUSTED) are not implemented; the derived-candidate (Vn+1) producer for DISMISSED/CORRECTION does not
exist; critique has no typed source; real grants on real tenants and `enforce` in Production need separate approval; an integral
run under `enforce` with independent real-AI UAT has not been executed; `off`/`audit` tenants remain non-secure.


## S5-04 and S5-05 — implementation status (third increment)

**S5-04 — the final approval is bound to a CURRENT reconciliation.** `application/approval_authority.py`,
called from `ResumeWorkflowUseCase.execute` right after the #714 pre-flight and BEFORE any resume operation exists: under
`enforce`, an approval of a candidate-bound analysis review needs `signable_as_is` (consistent ledger, no NEEDS_INFO, no
undecided finding, no material verified open critique, no derived candidate required). Otherwise
`ReconciliationBlocksApproval` -> HTTP 409 `reconciliation_blocks_approval` (with blocker / derivation codes); nothing is
created, nothing is recorded. Consequence to state plainly: under `enforce`, a reviewer who DISMISSES or proposes a
CORRECTION for a finding cannot approve the current candidate, because the derived candidate (Vn+1) that would carry that
content does not exist (NOT_IMPLEMENTED); they can reject, or decide the findings differently. Provisional decisions, the
approval and the TRUSTED promotion remain three acts; rejection never needs the reconciliation. `off` keeps the legacy rule;
`audit` logs `hitl_reconciliation_would_block_approval` and allows (both transitional, NOT secure).

**S5-05 — revalidation inside the first-TRUSTED transaction.** The approver, grant and receipt digest are stored on the
claimed operation (`resume_operations.operation_metadata.authority`; an explicit JSON null for any decision taken under the
legacy rule, so an earlier attempt's authority is never inherited). `revalidate_at_promotion` runs from
`_apply_trust_decision` immediately before `commit_candidate` -- the single place both N17 and finalization promote from, and
therefore also the reconciler's recovery path -- and only when the candidate is still PROPOSED (a first promotion).
It re-reads the approver as an active human member, takes the APPROVE_CANDIDATE grant `FOR SHARE` (a revocation waits for the
transaction or is seen), re-reconciles with the review row `FOR SHARE` (the ledger writer's `FOR UPDATE` conflicts) and requires
the approved digest. Failure raises `PromotionNotAuthorized` and rolls the transaction back: no TRUSTED state, no analysis, the
review stays pending and retryable. Under `enforce` a promotion with NO recorded authority fails closed. Because N17 runs inside
the graph's save node, the HTTP surface of a promotion-time refusal is the generic 502 "workflow failed; review unchanged"; the
safety property is the state and is asserted (and the refusal is attributed to S5-05 by a spy on the revalidation).
No SQL privilege was widened and no migration was added.

**Not resolved by S5-04 / S5-05 (independent gaps, kept open):** P1 SQL administrative authority = NOT_VERIFIED (a grant's
existence is not proof that an authenticated human administrator issued it); critique without a typed source = UNEVALUATED;
derived-candidate (Vn+1) producer = NOT_IMPLEMENTED; S5 as a whole = PARTIAL / NOT_ACCEPTED; no integral run under `enforce`
with the real browser has been executed.


## Milestone — deterministic rehearsal complete, with limitations (2026-11-02)

`DETERMINISTIC_REHEARSAL_COMPLETE_WITH_LIMITATIONS`. Integral run 41418544161 (HEAD `36cba4dc0667d9dd6fb5b45907f1d8f152e5fd9c`,
`deterministic-rehearsal`, tenants A/B in `enforce`, Clerk Development, mock AI, zero paid calls): browser S1, S2, S3, S4, S6 and
S8 PASS; S5 and S7 PARTIAL as declared; independent PostgreSQL verification 140/140; no first failure. The positive S5 route
(five CONFIRMED -> UI approval -> one resume operation with authority, an active APPROVE_CANDIDATE grant and the digest -> TRUSTED)
and the negative route (four decisions persisted, `409 reconciliation_blocks_approval`, rejection with no approve operation and
nothing promoted) were both exercised. The earlier failure (run 41404854469, zero decisions on the draft) was a runner read race
(stale React Query cache read at first paint), closed in the runner only. **This is not a UAT**: the findings are authored
(`DETERMINISTIC_CONTROLLED_CANDIDATE`), not extracted by a provider, and S7 relies on a single human. No claim of acceptance is made.


## S5 Vn+1 — the derived-candidate producer (fourth increment)

**Contract reused, not redesigned.** S5-03 already says what each decision means: DISMISSED -> EXCLUDED ("a derived candidate is
required"); CORRECTION_PROPOSED -> "a NEW candidate and its own signature, never applied"; S5-04 refuses to sign a candidate that
needs one. Nothing could produce it. The ratified D1-D8 text was never supplied to the implementer, so this increment is bounded to
those statements and to the product's own governed operation `propose_correction` (Vn SUPERSEDED, Vn+1 inserted PROPOSED with the
next version, the review rebinds compare-and-set from the exact candidate it replaces).

**What was built** (`domain/derived_candidate.py` pure; `application/derived_candidate_service.py`; route
`POST /hitl/reviews/{review_row_id}/derived-candidate` with `{source_artifact_hash, expected_ledger_revision}`):

1. Authorize the human (`REVIEW_FINDING` on the review's own project) and lock the review row `FOR UPDATE` (the ledger writer's lock).
2. Reconcile the CURRENT candidate. Refuse (409, nothing written) when the candidate in the request is not the review's, when the
   ledger head differs from `expected_ledger_revision`, when the ledger is INCONSISTENT, when anything blocks (NEEDS_INFO, an
   undecided finding, a material verified open critique), or when no derivation is needed (`no_derivation_required`).
3. Materialize: CONFIRMED findings are carried byte-for-byte; DISMISSED ones are left out; a correction replaces ONE field with the
   reviewer's own text (see A2). The source payload is never mutated; no text is generated.
4. Create Vn+1 through `propose_correction` and append the provenance to `review_items.review_metadata.candidate_derivations`
   (policy `s5-derive/v1`; source candidate id/version/SHA-256 and document revision; ledger head; reconciliation digest; every
   excluded/corrected finding with its decision event id and digests; the deriving human). One transaction: any failure rolls
   back the new candidate, the rebinding and the provenance together.
5. Idempotent: the same `(source_artifact_hash, expected_ledger_revision)` replays the recorded result (`replayed: true`) even after
   Vn+1 has received decisions; two concurrent requests produce one candidate.

**What deriving does NOT do.** It approves, rejects and trusts nothing; it creates no resume operation, event or analysis; it does
not touch a TRUSTED artifact; it carries no decision over - every finding of Vn+1 is undecided, so a human must decide them again
and approve explicitly, and S5-04 (a CURRENT reconciliation of Vn+1) and S5-05 (grant + digest inside the first-TRUSTED
transaction) apply to Vn+1 unchanged. A decision still aimed at the superseded Vn is refused by the existing pin check.

**Open points (documented, not decided here).**
* **A1 - authority.** `REVIEW_FINDING` was used because it is the capability that takes the decisions this materializes and the act only
  PROPOSES. If the owner prefers `APPROVE_CANDIDATE`, it is a one-constant change in the service and its tests.
* **A2 - which field a correction replaces.** The contract does not name it. `description` (the only free-text body of a risk, and
  what the screen's "Proposed replacement text" is shown against) is the implemented interpretation, but it is **gated**:
  `CORRECTIONS_RATIFIED = False` makes the service answer `409 correction_semantics_not_ratified`. Exclusions are unambiguous and not gated.
* **A3 - provenance store.** (superseded by "A1-A4 closure" below) the first increment kept the provenance only in the mutable
  `review_metadata`; it now lives in an append-only `hitl.candidate_derived` project event written with the candidate.
* **A4 - scoring.** (superseded by "A1-A4 closure" below) the first increment inherited the source's N8 scoring; Vn+1 now carries
  none and the source's is kept as history.
* **No screen yet.** The route and the generated client exist; the review card has no "Derive candidate" action.

**Tests.** `tests/unit/modules/hitl/test_derived_candidate.py` (pure) and `tests/integration/document_flow/test_s5_derived_candidate_pg.py`
(PostgreSQL, 19 tests): original candidate unchanged; exclusion and (ratified) correction applied only as specified; NEEDS_INFO and
incomplete decisions blocked; no promotion without a valid human approval; capability required / revoked grant; another tenant;
stale ledger/candidate; idempotent retry; concurrent requests; rollback and recovery; a pre-existing TRUSTED artifact untouched.
Seven deliberate mutations of the implementation each turned a test RED.

**Status (first increment).** Derived-candidate (Vn+1) producer: IMPLEMENTED for exclusions, GATED for corrections (A2), without UI. S5 as a whole remains
PARTIAL / NOT_ACCEPTED; P1 SQL administrative authority NOT_VERIFIED; typed critique UNEVALUATED; independent security review PENDING;
S7 independent approval absent.


## A1-A4 closure and the Vn+1 user flow (second increment, 2026-11-02)

**About "the ratified D1-D8".** The text ratified on 2026-11-01 is not in the repository: the code and tests only *refer* to it
("the ratified D1-D8 model (S5-01/S5-02)" in `final_decision_authorization.py`; "owner design D1-D8, C+B" in
`finding_reconciliation.py`), and the proposal above says it "was not supplied to the implementer". What is contrasted below is
therefore what IS recoverable and binding in the repo: the S5-01/S5-02 permission model (explicit grants, no implication between
READ_REVIEW / REVIEW_FINDING / APPROVE_CANDIDATE, ADMIN without implicit approval) and the S5-03 table (DISMISSED -> EXCLUDED,
CORRECTION_PROPOSED -> "a NEW candidate and its own signature, never applied"). No new interpretation replaces them; wherever the
ratified text could say more, the point stays an owner decision.

### Differential matrix

| | Prior contract (in the repo) | Implementation before this increment | Minimal change | Acceptance test | Residual risk |
|---|---|---|---|---|---|
| **A1 Authority** | S5-01/02: three permissions that do not imply each other; approval and the first TRUSTED need an active `APPROVE_CANDIDATE` (S5-04/05) | Deriving needs `REVIEW_FINDING`; approving needs `APPROVE_CANDIDATE`; both already enforced | None in behaviour. Decision recorded: `REVIEW_FINDING` PROPOSES a derivation, `APPROVE_CANDIDATE` approves and promotes | `test_approving_alone_does_not_allow_deriving_and_deriving_alone_does_not_allow_approving` (APPROVE-only cannot derive; REVIEW_FINDING-only cannot approve/promote; holding both is still two explicit acts) | A single human holding both (tenant A) can propose and approve: the same declared single-person limit as S7 (`SELF_GRANTED_NOT_INDEPENDENT`); separation of duties for human-corrected content is an owner decision (O-3) |
| **A2 Corrections** | S5-03: a correction "needs a NEW candidate and its own exact signature; it was NOT applied" | Gate shut: `CORRECTIONS_RATIFIED = False` -> `409 correction_semantics_not_ratified`; materializer replaces `description` behind the gate | None to the gate (stays shut). The semantics are specified below so the owner can ratify or amend them; exclusions stay operational | `test_a_correction_is_refused_until_the_owner_ratifies_which_field_it_replaces`; `test_the_correction_gate_is_shut_by_default` (a CI pin: flipping the constant fails the build until the tests are updated deliberately) | The specification below is a proposal, not ratified text; the Vn+1 payload cannot mark a risk as human-corrected without a contract change (O-1) |
| **A3 Provenance** | Nothing yet (the first increment invented a mirror in `review_metadata`) | Provenance in mutable JSON only | Reuse the canonical event ledger: one append-only `hitl.candidate_derived` `project_events` row, written in the SAME session/transaction as the new candidate and the rebinding; replay is read from the event, the review metadata is only a mirror (`event_id` inside). No table, no migration | `test_the_derivation_is_recorded_as_an_append_only_project_event_in_the_same_transaction` (payload, actor, source revision, trigger refuses UPDATE/DELETE); `test_a_failure_after_the_candidate_but_before_the_event_leaves_neither`; `test_the_replay_comes_from_the_event_ledger_not_from_the_mutable_review_metadata`; `test_a_refused_derivation_writes_no_event` | The event is evidence, not a signature: it does not prove an authenticated human ADMIN issued the grants (P1 SQL administrative authority stays NOT_VERIFIED); `project_events` is tenant-RLS and append-only by trigger, not by a separate write-once role; the event carries digests, not the full diff (the diff is reconstructible from Vn, Vn+1 and the ledger) |
| **A4 Scoring** | N8 output is stored on the artifact and is what the TRUSTED materializer writes as the analysis score (`MaterializationContent.from_artifact`) | Vn+1 inherited Vn's score: a stale Score would have been materialized as the evaluation of different content | Vn+1 is created with `CandidateScoring(None, None, evaluation=PENDING_REEVALUATION, derived_from_artifact_id=Vn)`; Vn's row is untouched (history) and the event records `source_scoring` / `derived_scoring`. Additive keys: legacy envelopes serialize exactly as before | `test_the_derived_candidate_carries_no_score_and_the_original_score_stays_as_history` (Vn 82 kept; Vn+1 null + PENDING; materializer yields no score; event holds both) | N8 cannot be re-run on Vn+1 today (below): until it can, a derived candidate approved and trusted yields NO coherence score for that analysis, honestly null; the S3 "null Score states its reason" path must be confirmed to render this reason (O-4) |

### A2 - what CORRECTION_PROPOSED means (specification for ratification; nothing here activates the gate)

1. **It is a statement about the analysis output, never an edit of the document.** The reviewer says "the extracted finding reads
   wrongly; it should read X". The contractual document, its revision, blob SHA-256 and clauses are not touched, and replacing a
   risk's narrative does not make the contract say anything else. If the reviewer believes the DOCUMENT is wrong, that is a new
   document revision (the revision flow), not a correction.
2. **What may be substituted:** only the narrative `description` of the risk (the system's wording of the finding). Nothing else.
3. **What must stay intact:** `title`, `category`, `severity`, `likelihood`, `clause_ref` and `source` (classification and
   evidence pointers belong to the extraction; a wrong classification or a wrong citation needs its own decision type, not a
   rewording). The original wording is never lost: it stays in Vn (superseded, immutable payload and hash), its SHA-256 is in the
   provenance, and the reviewer's reason and text stay in the ledger.
4. **Confidence.** `confidence` is the model's self-assessment of the ORIGINAL wording; it does not describe human text. The proposed
   rule is to clear it (`null`) on a corrected finding rather than leave a model confidence on human-written text (owner decision O-2).
5. **Traceability of the human origin.** `RiskItem` is `extra="forbid"`: a `human_corrected` marker in the payload is a contract
   change (new `x-contract-version`, ADR amendment) and is NOT introduced (O-1). Until then the human origin is carried by the
   `hitl.candidate_derived` event (ordinal, decision event id, original and proposed digests) and by the compare view.
6. **How the user sees it.** Per corrected finding, side by side: original wording | proposed wording (word-level difference), the
   reviewer's reason and name, and the ORIGINAL clause evidence (the `clause_ref` / source link still points at the unmodified
   document text) so a faithful correction can be judged against what the document actually says. A badge reads "Corrected by
   {name} - not extracted by the model".
7. **What validation Vn+1 requires.** Vn+1 starts undecided; each corrected finding must be explicitly CONFIRMED on its corrected
   wording after the difference was shown, by a human with `REVIEW_FINDING`; the candidate is then approved by a human with an
   active `APPROVE_CANDIDATE`, under S5-04 (a CURRENT reconciliation of Vn+1) and S5-05 (grant + digest inside the first-TRUSTED
   transaction). Proposed hardening (NOT implemented, part of the ratification): a correction identical to the original, empty, or longer than the field's limit is refused at derivation.
8. **Open owner decisions for ratification:** O-1 payload marker (contract change), O-2 clear `confidence`, O-3 separation of duties
   (should the approver of human-corrected content be someone other than its author, with the tenant exception for single-human
   tenants), O-5 whether the corrected text is subject to the PII anonymizer before it can reach any later model call.

### A4 - when the score can be recomputed (condition, not implemented)

N8 (`coherence_scorer`) runs inside the analysis graph over the graph state of that run. The artifact keeps the resulting
`coherence_score` and `score_version`, not the state, so Vn+1 cannot be re-scored from what is persisted. A score for a derived
candidate may be produced ONLY when all hold: (a) an N8 evaluation is run on the effective content of Vn+1 (not on Vn); (b) with
the same `score_version` as the engine now in force (otherwise it is a new version, shown as such); (c) from inputs reconstructible
from persisted data (the artifact payload and trusted project state), or from a graph state persisted for that purpose; (d) the
result is recorded as a NEW evaluation bound to Vn+1's artifact id and hash. Until then the state is `PENDING_REEVALUATION`; no
fallback to Vn's number, no estimate, no zero. **O-4 (owner/QA):** confirm that the Health/Score surfaces show an honest
"not evaluated" reason for an analysis trusted from a derived candidate (the materializer writes a null score; the rendering was
not exercised in this increment).

### Vn+1 user flow (minimal; design only - no screen was changed)

1. **Review the findings and the decisions** (existing findings panel): a summary strip counts confirmed / dismissed / correction /
   needs-info / undecided from the findings read the screen already has.
2. **See what will be excluded or corrected** ("Effect of your decisions", a read-only preview shown once no finding is undecided
   and none is NEEDS_INFO): excluded findings struck through with the reviewer's reason; corrected findings as original -> proposed
   with the clause evidence link; blockers listed by name when present. The preview should be a server answer (the reconciliation),
   not a second client implementation: a read-only `GET .../derived-candidate/preview` is the proposed addition.
3. **Request the derivation** ("Create revised candidate"): enabled only when the reconciliation has derivations and no blockers and
   the caller holds `REVIEW_FINDING`; confirmation text: "This creates a new PROPOSED version. Nothing is approved. Your decisions on
   V{n} do not carry over: you will review V{n+1} again. Its score is not evaluated yet." The call carries the candidate SHA-256 and
   the ledger head the screen holds; `409` codes map to plain messages (`derivation_blocked`, `no_derivation_required`,
   `stale_ledger_revision`, `stale_or_unbound_candidate`, `correction_semantics_not_ratified`, `derivation_not_possible`).
4. **Compare V{n} and V{n+1}** (after `201`, and any time from the card): counts retained / excluded / corrected, each excluded and
   corrected finding with its decision and author, both artifact hashes, the source revision, the derivation event id, and the score
   line "Not evaluated yet - previous score {82} kept as history". A read-only `GET .../derivations` (from the events) feeds it.
5. **Review and approve V{n+1} explicitly:** the same findings panel re-binds to V{n+1} (new pins), every finding undecided,
   corrected ones badged; Approve stays a separate act, disabled with the reason when the caller lacks `APPROVE_CANDIDATE`
   (the capabilities already ride on the findings read).

API additions this flow needs (not built here): the preview and the derivations read. UI files to touch when it is built:
`components/features/review/ReviewFindingsPanel.tsx` plus two small components (effect preview, compare dialog) and
`app/(app)/projects/[id]/review/page.tsx` only if the card layout must change; confirm none is currently assigned to Codex first.

**Status (second increment).** Derived-candidate producer: exclusions OPERATIONAL, corrections GATED (specification above awaiting
ratification), provenance APPEND-ONLY EVENT, scoring PENDING-REEVALUATION, UX specified but not built. Still open: P1 SQL
administrative authority NOT_VERIFIED; typed critique UNEVALUATED; independent security review PENDING; S7 independent approval;
S5 PARTIAL / NOT_ACCEPTED.

