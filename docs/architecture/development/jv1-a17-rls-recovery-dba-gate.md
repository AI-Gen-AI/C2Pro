# JV1/A17 — Recovery discovery under non-owner RLS (DBA/Seguridad approval gate)

**State:** P0 BLOCKED. Design only. **No approved migration, privileged function, new table, policy relaxation, deploy, or merge.**
Base SHA `2bdec6c5d2b5a6d3860c5b764e772d6f7cc4de33`.
Ownership: L5a only; any DDL requires separate L0 authorization following DBA/Seguridad approval.

## Confirmed failure

The approval's own transaction stamps
`review_items.review_metadata.a17_score_obligation = {state:'pending', review_id,...}`
through trigger `tr_a17_stamp_postapproval_obligation`.
The periodic scanner currently requests `SELECT id FROM tenants ORDER BY id`.
A **non-owner** PostgreSQL role without `BYPASSRLS`, lacking
`app.current_tenant`, sees zero tenant rows because the existing `tenants`
RLS policy requires `id = nullif(current_setting('app.current_tenant', true), '')::uuid`.
Therefore `APPROVED/pending` jobs may never be discovered, despite intact
PostgreSQL persistence. This is an **at-least-once liveness failure**, not a
HITL authorization failure.

## Feasibility constraint: why a code-only global recovery fix is impossible

A service allowed to see only one tenant via the existing tenant RLS cannot
derive the **complete** set of tenants whose approvals are pending from
`tenants`, `review_items`, `projects`, or `project_events`.
The existing `system_recovery.document_work_index`,
`system_recovery.trusted_projection_index`, and `resume_operations`
track **different** objects. Their coverage does not guarantee the presence
of an entry for every approval (especially approval with no document
clauses). Reinterpreting their tenant IDs as a complete registry would
produce false success and leave orphaned obligations. The same applies to
static env-var tenant lists, Clerk lookups, and non-durable Celery messages.
None may be silently promoted to an authoritative source.

**Restrictions maintained:** do not grant `BYPASSRLS`; do not use
`row_security=off`, superuser in a worker, permissive tenant policies,
unchecked `SECURITY DEFINER`, or table-owner bypass masquerading as
non-owner validation.

## Safe code-only mitigation permitted now (NOT the global fix)

1. `reconcile_pending_postapproval(tenant_id=<trusted UUID>)` scans
   `review_items` **only** with `get_session_with_tenant(tenant_id)`.
   The supplied UUID must originate from a previously authenticated internal
   tenant-bound operation, **not** from arbitrary user text or Celery ingress.
   It is a single-tenant capability, not a tenant enumeration strategy.
2. The old global scan remains compatible where existing privileges return
   tenant IDs, but **raises `A17_RECOVERY_TENANT_DISCOVERY_UNAVAILABLE`
   instead of claiming a successful empty sweep** when RLS returns none.
   This is observable fail-closed behavior, not autonomous recovery.
3. Existing PostgreSQL approval trigger, six-attempt backoff,
   `pg_advisory_xact_lock`, Score/withheld idempotency, review decisions,
   tenant RLS policies, migration and Celery Beat scheduling are unchanged.

No production GO is implied. An empty genuinely tenant-less database also
raises in global mode; operators must distinguish this from RLS invisibility
through authorized database diagnostics.

## Recommended DBA/Seguridad design (requires SEPARATE L0 authorization)

**Preferred:** minimal PostgreSQL outbox/index specifically for A17 under the
existing `system_recovery` schema, written **in the same transaction** as the
HITL approval and containing only:
`approval_review_id UUID PRIMARY KEY, tenant_id UUID, project_id UUID,
state (pending/done/operator_required), retry_after, attempts,
approved_at, created_at`.
All sensitive evidence/Score remains in existing tenant-bound business tables.

* The authoritative producer is the current `review_items` approval
  transition, including raw SQL HITL resume. A non-approved or rolled-back
  review must leave **no** outbox item; a confirmed approval must leave one.
* Use strict owner/role separation, no `BYPASSRLS` login, and no business-row
  grants to the scheduler. DBA must decide whether a narrowly owned,
  search_path-pinned and audited trigger helper is necessary. **Do not**
  create a `SECURITY DEFINER` helper before separate review.
* The scanner may read **only** the routing index; each returned identifier is
  rechecked with explicit tenant GUC, project/review identity,
  `APPROVED` decision, exact review physical PK and obligation state.
  Scan must be bounded, deterministic, cursor-based/fair under large tenants.
* `done` and Score/withheld outcome must commit atomically; read-model
  projection can lag but cannot contradict the approved row. Survive process,
  broker and Beat restart. Two workers must never persist two outcomes for
  the same approval; retry backoff and operator-required must be observable.
* DB roles: a dedicated non-owner scanner with only the minimal `SELECT`
  privilege on routing index; separately tenant-scoped writer. No arbitrary
  cross-tenant business data, no inherited owner privilege, no public EXECUTE.
* Migration rollback and historical data policy must be explicit; no retroactive
  migration of old approvals without separately approved backfill.

**Acceptance tests after DBA gate:** PostgreSQL 16, full migrated schema,
two tenants with and without documents, a third with no artifacts, RLS roles
without GUC, foreign-tenant SELECT/UPDATE denied, approval rollback, postcommit
kill then new process, two worker races, delayed original callback, corrupt
index row and tenant mismatch, withheld-without-Score, backoff exhaustion,
scheduler general/PROJECTGRAPH_ONLY, CI/CodeCov patch >=80%, Secret Scan,
Drift Guard, Sonar, JUnit and independent exact-SHA LV.

## Decision

**P0 global liveness is NOT GREEN until DBA-approved authoritative discovery
is implemented and the original non-owner PG16 negative becomes PASS**.
The current code-only mitigation improves safety and tenant-scoped recovery;
it does not satisfy the top-level acceptance condition.
`A17_MERGE_HOLD · A18_HOLD · JV1_GLOBAL=NO_GO`.
