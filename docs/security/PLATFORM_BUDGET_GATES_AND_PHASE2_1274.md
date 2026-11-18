# AI-01 #1274 — Security, 1270 integration and phase 2 (18 Nov 2026)

## Status

Existing PR #1275 is DRAFT/HOLD, owner-only. No deployment, merge,
persistent credentials, UAT/production budget modification or billed AI calls.
Tenant global cap USD 5 is unchanged.

## Routes

- GET /api/v1/platform/budgets: Clerk verified platform org, exactly one
  server-side owner allowlist ID. Reader DSN must be independently authorised.
  Without restricted capability: 503 fail-closed. Others: 403.
- PATCH /api/v1/platform/budgets/limit: explicit C2.6 platform registry
  identity, same owner gate. **HARD OFF: unconditional 503**, regardless
  of any runtime config. No DB connection, and no call to write service.
- Client UI: single table, search/pagination, Edit button and minimal modal.
  Edit form includes tenant, cap/committed, new cap, reason. Save disabled;
  no browser PATCH is sent.

## Capability matrix

| Principal | Tenants | TENANT budget buckets | Documents/private data | Mutation |
|---|---|---|---|---|
| Dedicated reader login | SELECT on 8 necessary columns | SELECT on 7 necessary columns, TENANT rows only | DENY | DENY including column-level UPDATE |
| Customer tenant login | Own row, under tenant RLS | Own rows, under tenant RLS | No platform grant | DENY |
| Future writer login (NOT CREATED) | SELECT + UPDATE(ai_budget_monthly) only | SELECT + UPDATE(cap_usd) only | DENY | Append-only audit INSERT only |
| Runtime ordinary / DLQ admin creds | Never fallback | Never fallback | No new grant | No grant |

Capabilities require non-owner/no superuser/no BYPASSRLS/no CREATE and no
unexpected membership, table or column privilege. No persistent credential
or PostgreSQL role is provisioned by this PR.

## Disposable PostgreSQL 16 evidence

Run only within the authorised scratch workspace (not UAT/prod):

    BUDGET_QA_PYTHON=/isolated/python pg_virtualenv -v 16 bash apps/api/tests/security/fixtures/run_platform_budget_scratch.sh

The automatically destroyed cluster includes only TWO synthetic tenants.
PASS: budget reader sees both permitted financial summaries; private columns,
documents, UPDATE and CREATE denied; synthetic customer sees own tenant only.
An injected column-only UPDATE grant was detected and revoked before normal
reader tests.

The isolated UNMOUNTED transaction function was exercised with real
SQLAlchemy/PostgreSQL: two caps updated atomically, idempotent audit receipt,
stale CAS denied, cap below committed amount denied, audit INSERT failure
rolled back both caps, and tenant-first lock serialised a concurrent reservation.

Important: Synthetic PostgreSQL/RLS is NOT the real Alembic schema, and the
transaction exercise used local disposable database owner credentials.
Future restricted writer rights, Clerk integration and UAT policies are NOT
certified.

## #1270 dependency: BLOCKED_1270_SCHEMA

PR #1275 base main SHA 299aaf19 does NOT include n4_budget_buckets or the N4
incremental store source. PR #1270 is OPEN DRAFT; its Railway pilot deployment
is NOT a merge into main.

Before runtime read enablement: independently approve/integrate #1270, rebase
#1275 against the approved SHA (or CORE-authorised explicit integration branch),
inspect the declared diff, rerun schema/RLS tests on actual Alembic migrations
and confirm period/key uniqueness, missing buckets, UNKNOWN reservations,
tenant-vs-child cap restrictions, reconciliation and monthly reset semantics.
No hidden cherry-pick or assumption of database equivalence.

## Phase 2 implementation prepared; security still HOLD

Prepared edit DTO: UUID tenant, UTC period, expected cap (CAS), positive
six-decimal new cap, meaningful reason, unique request UUID and explicit
confirmation. Offline-only write usecase locks tenant row then matching TENANT
bucket, validates both reconciled counters, policy max and spent+reserved
including UNKNOWN as held liability; updates only two cap fields and creates
append-only audit row in same transaction. It is NOT wired to runtime PATCH.

Remaining gates:
1. Separate restricted writer LOGIN and effective grants/RLS; durable audit
   migration with immutable actor ID/tenant/before/after/reason/period/time.
2. Re-test with exact Alembic schema, actual reserve_call race, duplicate
   idempotency collisions -> HTTP 409, month rollover, deny other tenant,
   CSRF/CORS, revocation, policy maximum, UNKNOWN and ledger divergence.
3. Independent QA SECURITY PASS and explicit CORE activation approval.

## E2E exact diagnosis

Completed GitHub Actions #44403949586, job 135154385419. Coherence-v1
passed 3/3; in journey-3-wedge.spec.ts:285 Clerk testing sign-in failed:
"Password is incorrect". The failure occurred at the authentication helper
before any access to /platform/budgets. Fixture/password mismatch is observed,
not its upstream cause. Do not read or rotate real Clerk secrets without
separate authorised identity remediation; rerun only the focal E2E fixture.

**Verdict:** synthetic read capability PASS_LIMITED; real read
BLOCKED_SECURITY_ENABLEMENT and BLOCKED_1270_SCHEMA; write HARD_OFF.
