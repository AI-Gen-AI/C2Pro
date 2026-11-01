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
read-only `GET /hitl/reviews/{row}/capabilities` and advisory UI hiding; `scripts/grant_project_review_permissions.py`
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
