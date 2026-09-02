# SESSION 2026-09-02 — P0-SEC Supabase Security Audit (PHASE 1, READ-ONLY)

**Project under audit**: `tcxedmnvebazcsaridge`
**Scope**: exposed-schema / RLS / tenant-isolation hardening
**Independent of**: PR #586 (not modified), P0b acceptance PR (not touched)
**Mutation performed**: NONE. No DDL, no GRANT/REVOKE, no migration, no policy change,
no Clerk/Railway/Product-Control/backlog change. All conclusions from `pg_catalog`,
`information_schema`, Supabase Security Advisor, and repository reads.
**Data handling**: metadata, row COUNTS and catalog structure only. No customer
content, clause text, evidence payloads, document bodies, tokens or keys were read.

---

## 1. EXECUTIVE VERDICT

**Overall posture: WEAKER than the Security Advisor indicates.** The advisor's 7
`ERROR` rows are real but are neither the highest-severity nor the complete P0 set.
Two of the three most serious findings produce **no advisor lint at all**, because
they involve tables where RLS *is* enabled — the advisor stops looking there.

**Evidence of current exposure or breach: UNPROVEN (no breach reported).**
No exploitation was attempted and no access logs were examined. What *is*
catalog-proven is that reachable configuration currently permits anonymous access to
live rows (see P0-SEC-11 and P0-SEC-04). Absence of proof of access is not proof of
absence; it is simply outside a read-only audit's reach.

**Immediate risk**, ranked by what is actually reachable today:

1. **1,669 live LangGraph checkpoint rows are anonymously readable** — RLS enabled
   but the policy is `USING (true)`. Not advisor-flagged.
2. **6 tables carry fail-open tenant policies** that collapse to `tenant_id = tenant_id`
   with no tenant context — which is exactly the state of every PostgREST request.
   This is fail-open for **writes as well as reads**. Not advisor-flagged.
3. **The database's default ACLs auto-grant `anon` full DML + TRUNCATE on every new
   table** and EXECUTE on every new function. This is the recurrence engine: fixing
   today's seven tables without this leaves the next table equally exposed.

**The single most important architectural finding**, which reframes all remediation:
the C2Pro frontend does not use the Supabase Data API at all. There is no
`@supabase/supabase-js` dependency, no browser client, no `NEXT_PUBLIC_SUPABASE_*`
usage. The only Supabase REST caller in the entire repository is one server-side
route using the **service_role** key. Therefore essentially the whole `public` schema
is INTERNAL_ONLY, and the correct fix is to **revoke the Data API roles from the
schema** rather than to author RLS policies for ~50 tables. RLS then becomes
defence-in-depth instead of the sole control.

**One thing this codebase got right** and which should not be disturbed: all 8 views
carry `security_invoker=true`, so they correctly inherit base-table RLS. This is a
common Supabase footgun and it is already handled.

---

## 2. P0 FINDINGS

### P0-SEC-11 — LangGraph checkpoint tables anonymously readable (NEW, not advisor-flagged)

| Table | Rows | RLS | Policy |
|---|---|---|---|
| `checkpoints` | 81 | ENABLED | `checkpoints_select` FOR SELECT TO public **USING (true)** |
| `checkpoint_blobs` | 274 | ENABLED | `checkpoint_blobs_select` — **USING (true)** |
| `checkpoint_writes` | 1314 | ENABLED | `checkpoint_writes_select` — **USING (true)** |
| `checkpoint_migrations` | 10 | ENABLED | `checkpoint_migrations_select` — **USING (true)** |

Four catalog-proven facts make this reachable, jointly and without exploitation:
(a) RLS is enabled but the only policy is `USING (true)`; (b) the policy's role is
`public`, which includes `anon`; (c) `anon` holds `SELECT` on all four tables;
(d) the `public` schema is PostgREST-exposed — proven by the advisor's own
`rls_disabled_in_public` lint, which by definition only fires on exposed schemas.

**Severity: P0.** These are the only tables in the audit with a *large* live row count
and *no* tenant scoping whatsoever. These tables hold serialized LangGraph
`ProjectState` for the N1–N17 pipeline. Per `CLAUDE.md` that state carries extracted
contract risks, WBS, stakeholders and clause data, and N2 `pii_anonymizer` runs
*before Claude* — not before checkpointing. **The sensitivity of the payloads is
inferred from pipeline semantics, not read** (reading them was out of scope), so
confirm content sensitivity before final classification. The access-control defect
is confirmed regardless of payload.

Writes are correctly denied: RLS is on and no INSERT/UPDATE/DELETE policy exists.
`FORCE RLS` is off on all four (see P1-SEC-12).

### P0-SEC-04 — Fail-open RLS: `COALESCE(..., tenant_id)` — CONFIRMED

24 policies across 6 tables use:

```sql
tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, tenant_id)
```

With no tenant context the inner expression is `NULL`, `COALESCE` returns `tenant_id`,
and the predicate becomes `tenant_id = tenant_id` → **TRUE for every row**.
PostgREST never sets `app.current_tenant`, so this is the *normal* state for any
anon or authenticated Data API request.

| Table | Policies | Rows | Distinct tenants |
|---|---|---|---|
| `document_revisions` | `docrev_{select,insert,update,delete}` | **8** | **3** |
| `document_artifacts` | `document_artifacts_{select,insert,update,delete}` | 0 | 0 |
| `project_events` | `project_events_{select,insert,update,delete}` | 0 | 0 |
| `project_states` | `project_states_{select,insert,update,delete}` | 0 | 0 |
| `project_state_entities` | `pse_{select,insert,update,delete}` | 0 | 0 |
| `project_snapshots` (parent) | `project_snapshots_{select,insert,update,delete}` | 0 | 0 |

**Current data at risk: 8 `document_revisions` rows spanning 3 tenants** — this is
genuine cross-tenant read exposure, not a hypothetical.

**The write side is worse than the read side and is easy to miss.** The same
fail-open expression is the `WITH CHECK` on INSERT and the `USING` on UPDATE/DELETE.
With no context, `anon` can insert rows bearing *any* `tenant_id`, and can update or
delete every existing row. At 0 rows a table is not "safe" — it is writable.

Fail-mode classification for every policy in this group: **FAIL_OPEN**.

Repository origin is not drift — the pattern is authored in-repo:
`apps/api/alembic/versions/20260614_0003_partition_project_snapshots.py:25`,
`apps/api/src/analysis/adapters/persistence/models.py:606`,
`apps/api/src/temporal/adapters/persistence/models.py:126`.

### P0-SEC-03 — Default privileges auto-expose every future object — CONFIRMED

`pg_default_acl` for owners `postgres` **and** `supabase_admin` in schema `public`:

| Object type | anon | authenticated | service_role |
|---|---|---|---|
| table | `arwdDxtm` | `arwdDxtm` | `arwdDxtm` |
| sequence | `rwU` | `rwU` | `rwU` |
| function | `X` | `X` | `X` |

Answering the audit's questions directly:

- *A developer creates a new table in `public` today* → `anon` automatically receives
  **INSERT, SELECT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER, MAINTAIN**.
  `authenticated` receives the same. `service_role` receives the same.
- *A new function is created* → `anon`, `authenticated`, `service_role` and `PUBLIC`
  all automatically receive **EXECUTE**.

**Classification: `P0-SEC-DEFAULT-ACL` = CONFIRMED.**

This is the systemic root cause and the reason the other findings recur. Every one of
the ~50 tables in `public` currently shows the full `anon/authenticated/service_role`
= ALL grant, with no exceptions — consistent with these defaults having been applied
uniformly and never narrowed. Remediating the seven advisor-flagged tables without
changing these defaults guarantees regression.

### P0-SEC-01 — Exposed tables with RLS disabled — CONFIRMED

| Table | Rows | RLS | Policies | tenant_id | anon grants |
|---|---|---|---|---|---|
| `evidence_claims` | 0 | **OFF** | 0 | yes | ALL |
| `evidence_extraction_events` | 0 | **OFF** | 0 | yes | ALL |
| `category_centroids` | 0 | **OFF** | 0 | no | ALL |

Zero rows means **no current read exposure** — do not report data loss. But the
*write* surface is live today: `anon` holds INSERT, UPDATE, DELETE and **TRUNCATE**.

`category_centroids` deserves separate emphasis. It is global reference data for
coherence scoring (`apps/api/src/coherence/application/services/centroid_builder.py`,
`pgvector_centroid_repository.py`). Anonymous write access to it is an **integrity
attack on Coherence Score™** — poisoned or truncated centroids would silently corrupt
the platform's headline metric. That is a P0 on integrity grounds even at 0 rows, and
it is a stronger argument than the confidentiality framing the advisor implies.

Repository origin confirmed — the source migrations never enable RLS:
`apps/api/alembic/versions/20260529_0001_add_evidence_intelligence_tables.py`,
`apps/api/alembic/versions/20260603_0019_4f92ed11a27b_add_category_centroids.py`.
This is a repo defect, not production drift.

### P0-SEC-02 — Partition RLS not inherited — CONFIRMED

Answering the audit's seven questions:

1. **Does parent RLS protect a leaf?** **No.** Parent policies apply only when the
   query is routed *through* the parent. A query addressing a leaf directly is
   governed solely by that leaf's own RLS, which is disabled.
2. **Can PostgREST address a leaf directly?** **Yes.** Each leaf is an ordinary table
   in the exposed schema with full `anon` grants, e.g.
   `/rest/v1/project_snapshots_2026_08`.
3. **GRANTs on each leaf**: `anon`, `authenticated`, `service_role` = ALL, on all four.
4. **Does a future partition reproduce protection?** **No.** `CREATE TABLE … PARTITION OF`
   does not inherit `relrowsecurity`. Verified: parent `rls_enabled=true`, all four
   leaves `false`.
5. **Is the DEFAULT partition protected?** **No** — `project_snapshots_default` is
   RLS-disabled, and it is where *all* rows outside the three defined months land.
6. **Partition-creation helper/job?** The migration creates `default` plus 3 months
   (`_create_partitions()`). **No `pg_cron` is installed** and no scheduled partition
   job exists. So beyond 2026-08 every snapshot silently falls into the RLS-disabled
   default partition.
7. **Could a new month become exposed silently?** **Yes** — by either path.

`_install_snapshot_policies()` at line 103 enables RLS on the parent only.

**Classification: `P0-SEC-PARTITION-RLS` = CONFIRMED.**

**Sequencing constraint:** enabling RLS on the leaves alone would make them inherit
the parent's *fail-open* policy, achieving nothing. **P0-SEC-02 must not ship ahead of
P0-SEC-04.**

---

## 3. P1 FINDINGS

### P1-SEC-05 — Tenant-context split — CONFIRMED, but **downgraded from P0**

`app.current_tenant_id` appears **zero times** in `apps/api/src`. The application's
sole runtime convention is `app.current_tenant`, set via `SET LOCAL`:
`core/database.py:221,272`, `core/auth/dependencies.py:157`,
`core/auth/service.py:281,357`, plus `SET SESSION app.current_tenant = ''` at
`core/database.py:115` (which is what makes the `NULLIF(...,'')` guard meaningful).

| Object | Policy | Context source | Runtime setter | Match | Fail mode if absent |
|---|---|---|---|---|---|
| `disclaimer_acceptances` | `disclaimer_tenant_isolation_{select,insert}` | `app.current_tenant_id` | none | **MISMATCH** | FAIL_CLOSED |
| `dlq_failed_tasks` | `dlq_tenant_isolation` | `app.current_tenant_id` | none | **MISMATCH** | FAIL_CLOSED |
| `wbs_nodes` | `wbs_nodes_tenant_isolation` | `app.current_tenant_id` | none | **MISMATCH** | FAIL_CLOSED |
| `notification_configs` | `tenant_isolation` | `app.current_tenant_id` (**no `missing_ok`**) | none | **MISMATCH** | **ERROR** (42704) |
| `organizations` | `org_isolation` | `request.jwt.claims->>'tenant_id'` OR `app.current_tenant_id` | none | **MISMATCH** | FAIL_CLOSED |
| `organization_members` | `org_members_isolation` | same | none | **MISMATCH** | FAIL_CLOSED |
| all others (~40) | various | `app.current_tenant` | `SET LOCAL` | MATCH | FAIL_CLOSED |

**This is deliberately not a P0.** Every mismatch fails *closed*, so it creates no
exposure. It is a correctness and availability defect: the backend is likely reading
zero rows from these six tables, and `notification_configs` raises a hard error rather
than returning empty. Severity must reflect architecture, not lint count — inflating
this to P0 would misdirect remediation effort away from P0-SEC-11 and P0-SEC-04.

`set_tenant_context(uuid)` sets `app.current_tenant_id` with `is_local := true`
(transaction-scoped, so no session bleed across the pooler) and **nothing in the
application calls it**. Dead code, inconsistent with the real convention.

Three policies also lack the `NULLIF(…, '')` guard, so an empty-string GUC raises
`invalid input syntax for type uuid` rather than denying cleanly.

### P1-SEC-06 — `is_project_member` SECURITY DEFINER — **downgraded from P0**

```
public.is_project_member(p_project_id uuid)
  SECURITY DEFINER = true | proconfig = NULL | extension-owned = NO
  EXECUTE: PUBLIC, postgres, anon, authenticated, service_role
  body: SELECT 1 FROM projects WHERE id = p_project_id
        AND tenant_id = (auth.jwt() ->> 'tenant_id')::UUID
```

Assessment against the audit's questions:

- **Is direct RPC invocation intended?** No — no caller exists in the repository.
- **Does it require SECURITY DEFINER?** No.
- **Could SECURITY INVOKER work?** Yes; `projects` RLS is fail-closed and correct.
- **Which roles genuinely need EXECUTE?** None.
- **Are referenced objects schema-qualified?** No (`projects`, `auth.jwt()` partially).
- **Does `auth.jwt()` tenant identity match the real model?** **No.** C2Pro authenticates
  with Clerk; the frontend instantiates no Supabase client and no Supabase JWT is ever
  minted for a user. `auth.jwt()` yields no `tenant_id`, the comparison is `= NULL`,
  and the function returns false. It is dead against the actual auth model.

**Why P1 and not P0:** the search_path-hijack vector requires CREATE on a schema
earlier in `search_path` (`"$user", public, extensions`). Catalog evidence:
`public` = `{…,anon=U/…,authenticated=U/…}` — **USAGE only, no CREATE**;
`extensions` = `anon=U` likewise. Neither `anon` nor `authenticated` can create the
shadowing object the attack needs. Preferred remediation is therefore **DROP or REVOKE**,
not merely pinning `search_path`.

**Classification: P1.**

### P1-SEC-08 — Function EXECUTE grants

All 15 application functions grant EXECUTE to `PUBLIC`, `anon`, `authenticated` and
`service_role` — a direct consequence of P0-SEC-03. Fourteen are SECURITY INVOKER, so
RLS still applies and none is independently exploitable. Three sub-groups:

- **Trigger functions exposed as RPC** — `update_updated_at_column`,
  `prevent_project_events_mutation`, `prevent_project_snapshots_update`. Direct RPC
  invocation errors, but they should never have carried a grant.
- **Caller-supplies-tenant functions** — `fn_get_clause_by_id`, `fn_get_neighbors`,
  `fn_find_path`, `fn_get_subgraph`, `fn_get_stakeholder_by_id` accept `p_tenant_id`
  as a parameter. Safe **only** because the underlying tables are fail-closed; the
  design places the entire trust boundary on RLS with no in-function check. Fragile.
- **Lookup/search functions** — `get_tenant_id_from_clerk_org`, `find_similar_clauses`,
  `find_cross_document_pairs`, `match_documents`, `user_has_role_in_org`,
  `set_tenant_context`. Invoker + fail-closed base tables ⇒ deny under `anon`.

### P1-SEC-07 — Mutable `search_path`

All 15 have `proconfig = NULL`; the advisor flags them all. Only `is_project_member`
is SECURITY DEFINER, and it is the only one where a mutable `search_path` is a
privilege-escalation vector at all. For the other 14 (INVOKER) this is hardening, not
a vulnerability. Combined with `anon` lacking CREATE, real exploitability is **low**.
Recommended `search_path` when fixed: `pg_catalog, public` (add `extensions` for the
`vector`-dependent ones: `find_similar_clauses`, `match_documents`,
`find_cross_document_pairs`).

### P1-SEC-12 — `FORCE RLS` absent + table-owner bypass — **UNPROVEN, must verify**

All `public` tables are owned by `postgres`. **A table owner bypasses RLS unless
`FORCE ROW LEVEL SECURITY` is set.** 15 tables lack it: `project_snapshots` (parent),
`alembic_version`, `checkpoint_blobs`, `checkpoint_migrations`, `checkpoint_writes`,
`checkpoints`, `document_artifacts`, `document_revisions`, `dlq_failed_tasks`,
`notification_configs`, `organization_members`, `organizations`, `project_events`,
`project_state_entities`, `project_states`, `schema_migrations`, `waitlist_signups`,
`wbs_nodes`.

If the FastAPI runtime connects as `postgres`, **tenant isolation on those tables is
not enforced at all**, regardless of policy text. `DATABASE_URL` is environment-supplied
and could not be resolved from the repository read-only, so the runtime role is
**UNPROVEN**. This must be verified before any remediation is designed, because it
would change the meaning of every policy above.

---

## 4. P2 / INFORMATIONAL

- **P2-SEC-13 — Migration metadata readable by `anon`.** `alembic_version` (1 row) and
  `schema_migrations` (5 rows) both carry `USING (true)` SELECT policies. Schema-version
  fingerprinting only. Low impact; fix alongside the schema-wide revoke.
- **P1-SEC-09 — Extensions in `public`.** See §10. **Defer.**
- **P1/P2-SEC-10 — Leaked Password Protection.** See §12. **NOT_APPLICABLE.**
- **Views — no finding.** All 8 (`v_coherence_breakdown`, `v_project_alerts`,
  `v_project_bom`, `v_project_clauses`, `v_project_stakeholders`, `v_project_summary`,
  `v_project_wbs`, `v_raci_matrix`) have `security_invoker=true` and correctly inherit
  base-table RLS. Explicitly called out because it is the usual Supabase failure mode
  and this project already handles it. **Do not "fix".**

---

## 5. DATA API SURFACE — what genuinely needs exposure

Repository trace (frontend, backend, generated clients, RPC, anon key):

- **No `@supabase/supabase-js` dependency.** Root `package.json:39` carries
  `"supabase": "^2.109.1"` — that is the **CLI** dev-dependency, not a client library.
- **No browser Supabase client.** Zero hits for `NEXT_PUBLIC_SUPABASE_*`,
  `createBrowserClient`, `createServerClient` across `apps/web`.
- **No backend Supabase REST client.** `apps/api/src/config.py` merely declares the
  settings fields; FastAPI talks to PostgreSQL directly via SQLAlchemy/asyncpg.
- **Exactly one Supabase REST caller in the repository**:
  `apps/web/app/api/waitlist/route.ts` — server-side, `SUPABASE_SERVICE_ROLE_KEY`,
  `POST /rest/v1/waitlist_signups?on_conflict=email`.

**DATA_API_REQUIRED_OBJECTS**

| Object | Operation | Role | Justification |
|---|---|---|---|
| `waitlist_signups` | INSERT (upsert on `email`) | **service_role only** | `apps/web/app/api/waitlist/route.ts` |

**INTERNAL_ONLY_OBJECTS** — *every other table, view, sequence and function in
`public`.* `DIRECT_POSTGREST_REQUIRED = NO` for all of them. Nothing in the repository
requires `anon` or `authenticated` to hold **any** privilege on **any** object.

This is the decisive result. The `anon` and `authenticated` roles are unused by C2Pro;
they exist only because Supabase provisions them and the default ACLs grant them
everything. The canonical remediation is therefore a **schema-wide revoke**, with RLS
retained as defence-in-depth — not fifty new policies.

---

## 6. TENANT ISOLATION

- **Canonical runtime variable: `app.current_tenant`** (`SET LOCAL`, transaction-scoped).
- **Mismatched objects (6)**: `disclaimer_acceptances`, `dlq_failed_tasks`,
  `notification_configs`, `organizations`, `organization_members`, `wbs_nodes` —
  all read `app.current_tenant_id`, which the application never sets. All fail closed;
  `notification_configs` errors. Detail in §3 P1-SEC-05.
- **Fail-open policies (24 across 6 tables)**: detail in §2 P0-SEC-04.
- **`request.jwt.claims` / `auth.jwt()`**: used by `organizations`,
  `organization_members` and `is_project_member`. Vestigial under Clerk — no Supabase
  JWT is ever issued to a C2Pro user.
- **Correctly fail-closed (~40 tables)**: the `NULLIF(current_setting('app.current_tenant',
  true), '')::uuid` form yields `NULL`, so `tenant_id = NULL` → NULL → deny. This is the
  pattern to standardize on. Live data behind it — `documents` (18), `clauses` (209),
  `projects` (20), `tenants` (26), `users` (24) — is **not** exposed to `anon`.

### Tenant isolation test model (designed, NOT executed)

Identities: **NO CONTEXT**, **TENANT A**, **TENANT B**, **SERVICE/BACKEND**.
Applies to: `projects`, `documents`, `clauses`, `document_chunks`, `analyses`,
`project_snapshots` (+ every partition, addressed directly), `evidence_claims`,
`evidence_extraction_events`, `project_events`.

| Identity | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| NO CONTEXT | 0 rows / denied | denied | denied | denied |
| TENANT A | A only, never B | A only | A only | A only |
| TENANT B | B only, never A | B only | B only | B only |
| SERVICE/BACKEND | only the explicitly intended administrative capability | — | — | — |

Cross-tenant INSERT/UPDATE/DELETE must be denied in every case. Partition leaves must
be asserted **by direct address**, not only through the parent — that is precisely the
gap P0-SEC-02 describes. To be run against a dedicated test project, never production.

---

## 7. PARTITIONS

Covered in §2 P0-SEC-02. Summary: parent RLS ENABLED with a *fail-open* policy; all
four leaves RLS DISABLED with full `anon` grants and directly addressable via
PostgREST; no `pg_cron` and no partition-creation job, so every month after 2026-08
lands in the RLS-disabled `project_snapshots_default`. Fixing existing months without
fixing creation, and without first fixing the fail-open policy, achieves nothing.

## 8. FUNCTIONS / RPC

15 application functions (§3 P1-SEC-06/07/08) — 1 SECURITY DEFINER, 14 INVOKER, all
`proconfig = NULL`, all EXECUTE to PUBLIC/anon/authenticated/service_role.

**Extension-owned, handled separately (§14 of the brief):** `pgaudit_ddl_command_end()`
and `pgaudit_sql_drop()` — owner `supabase_admin`, extension-owned by `pgaudit`,
SECURITY DEFINER, `search_path` already explicitly configured. Bodies must not be
altered, the functions must not be dropped, and `pgaudit` must not be moved during
this workstream. Whether `PUBLIC`/`anon` EXECUTE can be revoked without breaking the
extension is **UNPROVEN** and needs isolated testing — these are event-trigger
functions invoked internally by the extension, so a revoke is *likely* safe, but
"likely" is not sufficient for a production change to an audit extension. Defer to
P1-SEC-E.

## 9. DEFAULT PRIVILEGES

Covered in §2 P0-SEC-03. `P0-SEC-DEFAULT-ACL = CONFIRMED` for both `postgres` and
`supabase_admin` owners across tables, sequences and functions in `public`. Note the
same permissive defaults exist for the `storage` schema, which is outside this
workstream's scope but should be registered.

## 10. EXTENSIONS

| Extension | Schema | Version | Dependent objects | Code refs | Migration refs | Safe to move? | Dedicated migration? |
|---|---|---|---|---|---|---|---|
| `vector` | public | 0.8.0 | **237** | pervasive (embeddings, pgvector repos) | many | **NO** | YES |
| `pg_trgm` | public | 1.6 | **47** | search paths | several | NO | YES |
| `pgaudit` | public | 17.1 | 4 | none | none | Maybe | YES |

`vector` at 237 dependent objects touches every embedding column, index, operator and
cast; relocating it risks ORM type resolution, index validity and extension upgrades.
**This is not P0 and should not ride with the RLS work.** Once the schema-wide revoke
lands, the practical risk of these extensions sitting in `public` drops sharply, which
further justifies deferring. Defer to a separate hardening phase.

## 11. MIGRATION DRIFT

| Area | Verdict |
|---|---|
| Evidence tables RLS | **REPO_ONLY defect** — `20260529_0001_…` never enables RLS. Prod matches repo. Not drift. |
| `category_centroids` RLS | **REPO_ONLY defect** — `20260603_0019_…` never enables RLS. Prod matches repo. Not drift. |
| Partition RLS/grants | **REPO_ONLY defect** — `20260614_0003_…:103` enables RLS on parent only; leaves never covered. Prod matches repo. |
| Fail-open COALESCE policies | **MATCH** — authored in-repo (`20260614_0003_…:25`, `analysis/…/models.py:606`, `temporal/…/models.py:126`). Prod matches repo. |
| Default privileges | **PRODUCTION_ONLY** — Supabase platform defaults, **not codified anywhere in the repo**. Highest-value drift finding: nothing in version control describes or constrains them. |
| `app.current_tenant_id` policies | **PRODUCTION_ONLY / stale** — 6 objects reference a GUC with zero occurrences in `apps/api/src`. |
| Dual migration systems | Alembic (authoritative) + `supabase/migrations/**` both present and carrying the same defects. |

**The important conclusion:** with one exception, production is *not* drifting from the
repository — the repository itself encodes the defects. Remediation must therefore land
in migrations, not as console fixes, or it will be re-applied on the next deploy. The
exception (default privileges) is the reverse problem: production state that version
control has never described.

## 12. CURRENT ADVISOR BASELINE

**ERROR (7)** — all `rls_disabled_in_public`

| Object | Disposition |
|---|---|
| `project_snapshots_2026_06` / `_07` / `_08` / `_default` | **FIX** — P0-SEC-02 (after P0-SEC-04) |
| `evidence_claims`, `evidence_extraction_events` | **FIX** — P0-SEC-01 |
| `category_centroids` | **FIX** — P0-SEC-01 (integrity) |

**WARN (22)**

| Group | Disposition |
|---|---|
| `function_search_path_mutable` × 15 | **FIX** (P1-SEC-07) — `is_project_member` first |
| `anon`/`authenticated_security_definer_function_executable` — `is_project_member` | **FIX** (P1-SEC-06) — prefer DROP/REVOKE |
| same — `pgaudit_ddl_command_end`, `pgaudit_sql_drop` (×2 each) | **NEEDS_MORE_EVIDENCE** — extension-owned; revoke safety unproven |
| `extension_in_public` — `vector`, `pg_trgm`, `pgaudit` | **DEFER** (P1-SEC-09) |
| `auth_leaked_password_protection` | **NOT_APPLICABLE** |

**INFO (1)**

| Object | Disposition |
|---|---|
| `waitlist_signups` — RLS enabled, no policy | **INTENTIONAL — `EXPECTED_DENY_ALL`** |

**`waitlist_signups` verdict:** the server route uses the **service_role** key, which
bypasses RLS entirely. RLS-on-with-no-policy is therefore *correct* fail-closed design
for a table that must never be Data-API readable. 2 rows present. **Do not create a
public insert policy.** One residual gap: `anon` still holds SELECT/INSERT *grants*, so
RLS is the only thing preventing anonymous reads of signup PII — the schema-wide revoke
should remove that single point of failure.

**Leaked Password Protection:** `IS SUPABASE AUTH USED FOR HUMAN LOGIN? = **NO**.`
Authentication is Clerk (`core/middleware/clerk_auth.py`); no Supabase client is ever
instantiated; no `auth.users` reference exists in application code. Enabling this would
harden an unused subsystem and clear a cosmetic warning while changing nothing real.
**Classify NOT_APPLICABLE / LOW. Do not enable.**

**Two P0 findings produce no advisor lint at all** (P0-SEC-11, P0-SEC-04) because both
sit on tables where RLS is enabled. The dashboard cannot be the completion criterion.

---

## 13. PROPOSED REMEDIATION PHASES (DESIGN ONLY — nothing authored)

### P0-SEC-A — Immediate exposure containment
- **Option A (minimal):** drop the four `USING (true)` SELECT policies on the
  checkpoint tables; `REVOKE ALL … FROM anon, authenticated` on the checkpoint tables,
  the three RLS-off tables, and the four snapshot partitions.
- **Option B (canonical, recommended):** `REVOKE ALL ON ALL TABLES/SEQUENCES/FUNCTIONS
  IN SCHEMA public FROM anon, authenticated`, then re-grant *only* the §5 required
  object. Justified because §5 proves `anon`/`authenticated` are unused by C2Pro.
- Prereq: **resolve P1-SEC-12** (runtime DB role) first. Rollback: re-GRANT (recorded
  pre-state). Expected advisor impact: `rls_disabled_in_public` persists until RLS is
  enabled — B fixes exposure without silencing the lint, which is the correct outcome.

### P0-SEC-B — Fail-closed tenant policy normalization
- Replace all 24 `COALESCE(…, tenant_id)` policies with the fail-closed
  `NULLIF(current_setting('app.current_tenant', true), '')::uuid` form already used by
  ~40 tables. Standardize the 6 `app.current_tenant_id` objects onto `app.current_tenant`.
  Add the missing `NULLIF` guards. Fix or drop `set_tenant_context`.
- **Breakage risk: HIGH** — any backend path relying on fail-open today will start
  returning zero rows. Must be preceded by an audit of callers to those 6 tables.
- Add `FORCE ROW LEVEL SECURITY` per P1-SEC-12 findings.

### P0-SEC-C — Partition hardening + future-partition guard
- Enable RLS on all four leaves; revoke leaf grants; **and** make partition creation
  reproduce RLS/grants (event trigger, or a helper the migration and any future job
  must call). **Must land after P0-SEC-B**, else leaves inherit a fail-open policy.

### P0-SEC-D — Function/RPC + default privileges
- `ALTER DEFAULT PRIVILEGES … REVOKE` for tables, sequences and functions, for **both**
  `postgres` and `supabase_admin` owners — otherwise A–C regress on the next table.
- DROP or REVOKE `is_project_member`; revoke EXECUTE on trigger functions; pin
  `search_path` on what remains.

### P1-SEC-E — Extensions / pgaudit (separate phase)
- Test `pgaudit` EXECUTE revoke in isolation. Extension relocation only with a
  dedicated migration and a full dependency plan (`vector`: 237 objects).

**Ordering is load-bearing:** A → B → C → D. C before B re-creates the fail-open hole
on the leaves; D before A leaves the recurrence engine running.

## 14. REQUIRED TESTS (specified, not implemented)

**Static detectors (CI gate, `pytest` + catalog queries):** RLS-off in exposed schema;
partition RLS (parent vs. every leaf, incl. default); new-partition-inherits-protection;
default-ACL detector (`pg_default_acl` must grant nothing to anon/authenticated);
PUBLIC/anon/authenticated table-grant detector; SECURITY DEFINER + PUBLIC EXECUTE
detector; mutable `search_path` detector; **fail-open `COALESCE(...)` policy detector**;
**mixed `current_tenant`/`current_tenant_id` detector**; `USING (true)` policy detector
(would have caught P0-SEC-11); `FORCE RLS` detector.

**Tenant E2E (dedicated test project):** the §6 matrix — NO CONTEXT denies; A sees only
A; A cannot see B; B sees only B; cross-tenant INSERT/UPDATE/DELETE denied — asserted
against partition leaves **by direct address** as well as through the parent.

**CI gate proposal:** a `supabase-security-lint` job running the static detectors against
a migrated ephemeral database on every PR touching `apps/api/alembic/**` or
`supabase/migrations/**`, failing on any new violation. The advisor is a dashboard, not
a gate, and it misses two of the three P0s here — the gate must be catalog-driven.

## 15. BREAKAGE / ROLLBACK RISKS

- **Highest:** the §13-A revoke breaks the waitlist if the re-grant is wrong. The route
  uses **service_role**, so revoking `anon`/`authenticated` should not affect it —
  confirm before shipping. Distinguish carefully: FastAPI direct PostgreSQL (A),
  service_role REST (B), authenticated PostgREST (C, unused), anon PostgREST (D, unused),
  Clerk→FastAPI (E). A revoke touching C/D is inert for C2Pro; one touching B breaks
  the waitlist.
- **P1-SEC-12 is a precondition, not a footnote.** If FastAPI connects as `postgres`,
  adding `FORCE RLS` will suddenly start enforcing policies that have never been
  exercised — potentially breaking many backend reads at once.
- P0-SEC-B flips fail-open to fail-closed: any silent dependence on fail-open becomes an
  immediate zero-rows regression.
- `pgaudit` EXECUTE revoke: unproven; could disturb audit logging.
- `vector` relocation: 237 dependent objects — do not attempt in this workstream.
- All changes must ship as Alembic migrations mirrored into `supabase/migrations/**`
  (§11), or the next deploy re-introduces the defects.

## 16. RECOMMENDED NEXT MASTER ACTION

1. **Resolve P1-SEC-12 first** — confirm the runtime `DATABASE_URL` role. It gates the
   meaning of every policy and the safety of `FORCE RLS`.
2. **Confirm checkpoint payload sensitivity** (P0-SEC-11) — one authorized structural
   inspection to fix its final classification.
3. **Authorize P0-SEC-A only**, as a single reversible containment migration.
4. Then authorize B → C → D in order.

## 17. EXACT OBJECTS THAT WOULD CHANGE IN THE FIRST REMEDIATION PR (P0-SEC-A)

**No PR created. No DDL executed. Awaiting MASTER authorization.**

**Policies dropped (4):** `checkpoints_select`, `checkpoint_blobs_select`,
`checkpoint_writes_select`, `checkpoint_migrations_select`.

**Grants revoked from `anon` + `authenticated`** (Option A scope, 11 tables):
`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`,
`evidence_claims`, `evidence_extraction_events`, `category_centroids`,
`project_snapshots_2026_06`, `project_snapshots_2026_07`, `project_snapshots_2026_08`,
`project_snapshots_default`.
*(Option B instead: schema-wide revoke on `public`, re-granting only `waitlist_signups`
INSERT to `service_role`.)*

**RLS enabled (3):** `evidence_claims`, `evidence_extraction_events`, `category_centroids`
— containment only; fail-closed tenant policies for the first two land in P0-SEC-B, and
`category_centroids` needs its model decided (§below) before policies are written.

**Unchanged in this PR:** all fail-open policies (P0-SEC-B), partition RLS (P0-SEC-C),
default privileges and functions (P0-SEC-D), all extensions, `waitlist_signups`,
Supabase Auth settings, PR #586, Product-Control, and the backlog.

**`category_centroids` model — recommendation:** classify **A. INTERNAL_ONLY**. It is
global reference data with no `tenant_id`, written by `centroid_builder.py` and read by
`pgvector_centroid_repository.py`, both server-side. No frontend path exists (§5), so
`PUBLIC_READ_ONLY` and `AUTHENTICATED_READ_ONLY` are unjustified. Public **write**
privileges (INSERT/UPDATE/DELETE/**TRUNCATE**) are categorically inappropriate on
reference data feeding Coherence Score™ — that is the integrity argument in P0-SEC-01.

**`evidence_claims` / `evidence_extraction_events` model — recommendation:**
**INTERNAL_ONLY**, backend-only via `apps/api/src/evidence/`. Producer and consumer are
both server-side; no frontend Data API need exists. They carry `tenant_id`,
`project_id` and `document_id` and are expected to hold extracted evidence payloads —
high future sensitivity even though both are empty today. Prefer denying Data API
access over relying on RLS alone.

---

## AUDIT EXIT CRITERIA — STATUS

A ✅ exposed-object inventory · B ✅ Data API dependency map · C ✅ RLS/policy/grant matrix ·
D ✅ partition assessment · E ✅ tenant-context map · F ✅ fail-open inventory ·
G ✅ function/RPC privilege matrix · H ✅ SECURITY DEFINER assessment ·
I ✅ default privilege assessment · J ✅ extension dependency assessment ·
K ✅ migration drift · L ✅ prioritized findings · M ✅ remediation options ·
N ✅ migration sequencing · O ✅ regression-test plan · P ✅ advisor mapping

**PHASE 1 COMPLETE. No production mutation performed. STOPPED for MASTER
remediation authorization.**

**Carried as UNPROVEN:** runtime `DATABASE_URL` role (P1-SEC-12) · checkpoint payload
sensitivity (P0-SEC-11) · `pgaudit` EXECUTE revoke safety.

---
---

# AMENDMENT — PRE-REMEDIATION GATE (2026-09-02, READ-ONLY)

Phase-1 accepted by MASTER. MASTER independently confirmed anon-visible row counts
(checkpoints 81 / blobs 274 / writes 1314 / migrations 10 / document_revisions 8).
This amendment resolves the two architectural preconditions. **No mutation performed.**

## A — BACKEND / CELERY DATABASE ROLE

### Evidence

`pg_stat_activity` (metadata only, no query text) shows **no FastAPI or Celery
connection present**. Only three client backends exist:

| role | application_name | client class | conns |
|---|---|---|---|
| `authenticator` | `postgrest` | external | 1 |
| `postgres` | `mgmt-api` | external | 1 |
| `supabase_admin` | `postgres_exporter` | external | 1 |

Live correlation is therefore **not available** — the runtime is not currently
connected. The role is established instead from configuration (evidence class *c*):

- `.env.example:29` — `postgresql://postgres.<project-ref>:***@aws-1-<region>.pooler.supabase.com:6543/postgres`
  (Supavisor **transaction-mode** pooler; the pooler username `postgres.<ref>` maps to role **`postgres`**)
- `.env.example:34` — direct connection variant, same `postgres.<project-ref>` principal
- `docker-compose.yml:135` (api) and `:185` (celery-worker) — **identical `DATABASE_URL`**

No credential, password or full URL is reproduced here.

### Role attributes (`pg_roles`)

| role | superuser | **BYPASSRLS** | can login |
|---|---|---|---|
| `supabase_admin` | **yes** | **yes** | yes |
| **`postgres`** | no | **YES** | yes |
| `service_role` | no | **yes** | no (via authenticator) |
| `authenticator` | no | no | yes |
| `anon` / `authenticated` | no | no | no |

### Verdict

```
BACKEND_DB_ROLE     = postgres        (via Supavisor pooler principal postgres.<project-ref>)
CELERY_DB_ROLE      = postgres        (same DATABASE_URL; only Redis differs)
SUPERUSER?          = NO              (rolsuper = false)
BYPASSRLS?          = YES             (rolbypassrls = true)
TABLE_OWNER?        = YES             (all public tables owned by postgres)
CURRENT_RLS_EFFECT  = BYPASSED
```

Confidence: **CONFIRMED by configuration**, not by live correlation. Residual
caveat: production Railway env vars were not readable, so a non-documented role
cannot be excluded with certainty. Both documented forms resolve to `postgres`.

### CONSEQUENCE — this corrects the Phase-1 P1-SEC-12 framing

`FORCE ROW LEVEL SECURITY` removes only the **table-owner** exemption. It does
**not** override the **BYPASSRLS role attribute**. `postgres` holds BYPASSRLS, so:

> **Would enabling FORCE RLS on tenant tables break FastAPI/Celery? → NO.**
> It would be a **no-op** for this connection model.

Phase-1 listed FORCE RLS as a high-risk change that might break backend reads. That
was wrong in this specific direction and is corrected here: it is neither risky nor
useful under the current role. It cannot restore tenant enforcement either.

**Three consequences that reshape remediation:**

1. **Every RLS policy in this database is currently decorative for the backend.**
   Production tenant isolation rests entirely on application-level `WHERE tenant_id`
   filtering, not on RLS. The `SET LOCAL app.current_tenant` calls are set but never
   evaluated on the backend path.
2. **RLS today protects exactly one surface: the external PostgREST surface**
   (`anon` / `authenticated`) — precisely the surface P0-SEC-A closes.
3. **P0-SEC-A is therefore near-zero product-breakage risk.** Revoking `anon` and
   `authenticated` cannot affect FastAPI, Celery or LangGraph, because none of them
   use those roles. This is a much stronger safety argument than Phase-1 could make.

Restoring real backend-side RLS would require changing the connection role to a
non-BYPASSRLS principal — a substantial change, correctly out of scope here.

**Side note (not a P0-SEC finding):** port 6543 is transaction-mode pooling, where
`SET SESSION app.current_tenant = ''` (`core/database.py:115`) is not reliably
scoped to subsequent statements. `SET LOCAL` usage is correct and unaffected.

## B — LANGGRAPH CHECKPOINT ARCHITECTURE

### Schema (standard `langgraph-checkpoint-postgres`)

| table | columns | PK |
|---|---|---|
| `checkpoints` | `thread_id`, `checkpoint_ns`, `checkpoint_id`, `parent_checkpoint_id`, `type`, `checkpoint` jsonb, `metadata` jsonb | (`thread_id`,`checkpoint_ns`,`checkpoint_id`) |
| `checkpoint_blobs` | `thread_id`, `checkpoint_ns`, `channel`, `version`, `type`, `blob` bytea | (`thread_id`,`checkpoint_ns`,`channel`,`version`) |
| `checkpoint_writes` | `thread_id`, `checkpoint_ns`, `checkpoint_id`, `task_id`, `idx`, `channel`, `type`, `blob` bytea, `task_path` | (`thread_id`,`checkpoint_ns`,`checkpoint_id`,`task_id`,`idx`) |
| `checkpoint_migrations` | `v` | (`v`) |

Secondary indexes: `*_thread_id_idx` on the three data tables. **Foreign keys: none.**

### Tenant correlation — the decisive result

- **No `tenant_id` column. No `project_id` column.** On any of the four.
- `thread_id` is generated as **`str(uuid4())`** — `apps/api/src/analysis/application/analyze_document_use_case.py:23`.
  It is a **random UUID with no tenant or project derivation**.
- `checkpoint_ns` is LangGraph-internal subgraph namespacing, not a tenant boundary.

**Therefore tenant RLS is not naturally expressible on these tables.** Any tenant
policy would require adding columns — which MASTER prohibited, and rightly so.
This proves (rather than assumes) that **access removal is the correct control**.

Note the asymmetry that makes this urgent: the **keys** carry no tenant identity, but
the **payloads** do — `checkpoint`/`metadata` jsonb and `blob` bytea hold serialized
`ProjectState`, and `nodes.py:500-515` writes `thread_id` and project context into
checkpoint metadata. Tenant-bearing data under non-tenant-derivable keys is the
worst combination for RLS and the best case for revoking access. *(Payloads were
not read.)*

### Access path

- **Writer/reader:** `AsyncPostgresSaver` over a psycopg `AsyncConnectionPool` built
  from `settings.database_url_async` — `analysis/adapters/graph/workflow.py:325-393`
  (`conn_string` at :362 strips `+asyncpg`). Lifecycle via
  `ensure_checkpointer_ready()` / `close_checkpointer_resources()` in `main.py:109,174`.
- **Consumers:** `modules/hitl/adapters/checkpoint_service.py` (`aget_tuple`) and
  `modules/hitl/application/resume_workflow_use_case.py` (HITL resume).
- **Access class: DIRECT PostgreSQL as `postgres`.** Not PostgREST. Not service_role.

### Origin of the `USING (true)` policies — a lint workaround, not a requirement

`apps/api/alembic/versions/20260403_0003_fix_security_definer_views_rls_infra.py`
— docstring line 10: *"6 infrastructure tables missing RLS (alembic_version, checkpoint_*)"*;
lines 35-53 loop over the four tables emitting:

```
DROP POLICY IF EXISTS "{table}_select" ON {table};
CREATE POLICY "{table}_select" ON {table} FOR SELECT USING (true);
```

**These policies are C2Pro-authored to clear the `rls_disabled_in_public` advisor
ERROR. LangGraph does not require them.** Enabling RLS satisfied the linter; the
permissive policy re-opened the data to `anon`. This is the concrete case for the
Phase-1 position that a green dashboard is not the objective — chasing the lint
*created* the most exposed surface in the database.

### Verdicts

```
CHECKPOINT_DATA_API_REQUIREMENT = NOT_REQUIRED
CAN WE REVOKE anon/authenticated/PUBLIC FROM CHECKPOINTS? = YES
```

Proof: no browser Supabase client exists (Phase-1 §5); the only REST caller is the
waitlist route on **service_role**; the checkpointer uses direct PostgreSQL as
`postgres`, which is both owner and BYPASSRLS. Removing `anon`/`authenticated`/`PUBLIC`
privileges cannot affect any code path in the repository.

## C — SUPERSEDED PHASE-1 SEQUENCING CONSTRAINT

Phase-1 stated P0-SEC-C (partition RLS) must not ship before P0-SEC-B (fail-open
policies), because leaves would inherit a fail-open parent policy. **That constraint
assumed the `anon` grants remained in place.** Once PR-A revokes those grants, the
external path is closed regardless of policy text, and the ordering constraint
dissolves — leaf RLS can safely ship in PR-A. P0-SEC-B remains required, but as
defence-in-depth and correctness work, not as a prerequisite for partition hardening.

## D — VERIFIED NON-RISKS FOR PR-A

- **Realtime:** `supabase_realtime` publication contains **no `public` tables** →
  no subscription breakage.
- **Waitlist:** uses `service_role`, which retains its grants and holds BYPASSRLS →
  unaffected.
- **Studio / mgmt-api:** connects as `postgres` → unaffected.
- **PostgREST `authenticator`:** retains role-switching to `service_role` → unaffected.

## E — CARRIED FORWARD AS UNPROVEN

- Production Railway env vars not readable → backend role is config-confirmed, not
  live-confirmed.
- Checkpoint payload contents not read (out of scope, by instruction).
- `pgaudit` EXECUTE revoke safety (deferred to P1-SEC-E).

**Gate status: BOTH PRECONDITIONS RESOLVED. No mutation performed.
STOPPED for MASTER authorization of P0-SEC-A.**

---
---

# AMENDMENT 2 — P0-SEC-A IMPLEMENTED AS CODE (2026-09-02)

**Status: MIGRATION AUTHORED AND VALIDATED. NOT APPLIED TO PRODUCTION.**
Validation ran exclusively against a disposable local PostgreSQL 16.13 instance.

## Accepted architecture truth

`postgres` (BYPASSRLS, owner, not superuser) is the FastAPI/Celery role;
`service_role` also holds BYPASSRLS; FORCE RLS cannot override BYPASSRLS;
LangGraph checkpoints use direct PostgreSQL via `AsyncPostgresSaver`; the
checkpoint `USING (true)` policies were a C2Pro lint workaround; no `public`
table is in the Realtime publication; the frontend has no Data API dependency;
the waitlist uses server-side `service_role`.

## Scope delivered

1. Revoke ALL on ALL TABLES + SEQUENCES in `public` from `anon`, `authenticated`,
   `PUBLIC`. `service_role` untouched.
2. Drop the 4 permissive checkpoint `SELECT ... USING (true)` policies.
3. Enable RLS on `evidence_claims`, `evidence_extraction_events`,
   `category_centroids` (no policies authored — `category_centroids` is global
   reference data and must not be given manufactured tenant semantics).
4. Enable RLS on the 4 snapshot leaf/default partitions (no policies — copying
   the parent's fail-open policy down would reproduce the defect).
5. Close default privileges for TABLES + SEQUENCES. FUNCTIONS untouched (P0-SEC-D).

## Two defects caught during implementation

**(a) `%` placeholder collision.** The first draft used `format('%I', ...)` and
`RAISE NOTICE '%'`. A literal `%` in migration SQL is consumed by psycopg2's
parameter interpolation under `op.execute()`, so the statements would have
behaved differently under Alembic than under a raw `psql` test — passing local
validation and failing at deploy. Rewritten using `quote_ident()` and
concatenation; a regression test asserts the emitted SQL contains no `%`. The
same bug was then found and fixed in the lint script's `LIKE` patterns.

**(b) Hard-coded default-ACL owner list was incomplete.** The first draft
iterated `ARRAY['postgres','supabase_admin',current_user]`. The self-verifying
gate failed at the "after upgrade" phase with 4 blocking violations, because the
fixture's owner (`c2pro_owner`) was not in that list and its default ACL kept
granting to `anon`. Rewritten to drive from `pg_default_acl`, selecting only
entries that actually grant to an external role — the minimal delta, and
complete for any owner. This is exactly the "do not assume owner/global syntax"
trap; a fixed list silently leaves the recurrence engine running.

Related and unchanged: `postgres` is NOT a member of `supabase_admin`, so an
unguarded `ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin` fails at deploy.
Each target is attempted only when `pg_has_role(current_user, rec.owner, 'USAGE')`
holds, and skipped with a NOTICE otherwise. In production, running as `postgres`,
the `postgres` entry closes and `supabase_admin` is reported as requiring
platform-level action.

## Evidence

**RED (pre-state, disposable DB):** `anon` read checkpoints 1 / blobs 1 / writes 1
/ migrations 1, `document_revisions` 2 rows across 2 tenants (fail-open),
evidence 1, centroids 1, snapshot leaf 1. `anon` INSERT succeeded on
`category_centroids`, `evidence_claims`, and cross-tenant `document_revisions`.
A newly created table auto-granted `DELETE,INSERT,REFERENCES,SELECT,TRIGGER,TRUNCATE,UPDATE`
to `anon`. Security lint: **45 blocking violations**.

**GREEN (post-migration):** 38/38 external denial assertions DENIED for both
`anon` and `authenticated`. Backend non-regression PASS: checkpoint put/get round
trip, checkpoint resume read, evidence writer, centroid read, snapshot
writer/read with leaf routing, tenant-scoped read, waitlist INSERT+SELECT as
`service_role`. New table/sequence inherit no external grants; `service_role`
default grants persist. Security lint: **PASSED (0 blocking, 6 informational)**.

**Scope invariants held:** 6 fail-open COALESCE policies still present; snapshot
leaves carry 0 policies; function default EXECUTE UNCHANGED; `waitlist_signups`
still 0 policies (EXPECTED_DENY_ALL); FORCE RLS count still 0; `service_role`
retains grants on all 15 tables; `anon`/`authenticated` grants = 0.

**Cycle:** `p0_sec_a_gate.py` asserts RED → GREEN → RED → GREEN and passes.
Downgrade restores exactly the 45 pre-state violations, proving deterministic
symmetry. Re-apply is idempotent.

**Pytest:** 59 passed against the migrated DB; 37 failed / 22 passed against the
un-migrated DB (RED-first confirmed).

## Gaps — NOT run, and why

The repository's own Python suite could not be executed here: `apps/api` runtime
dependencies are not installed and the package index repeatedly timed out in
this sandbox. Therefore **the P0b canonical Acceptance Journey, the document
analysis pipeline tests, and the Celery task-path tests were NOT run.** Their
DB-level equivalents were exercised directly against the disposable database
(items 1, 2, 5, 6, 7, 9, 10 of the required matrix), but that is not a substitute.
These must go green in CI before production authorization.

No Supabase development branch was created (that needs separate cost
authorization), so no non-production Security Advisor result exists yet.

## Residual findings after P0-SEC-A

P0-SEC-B (24 fail-open policies; `app.current_tenant_id` split on 6 objects),
P0-SEC-D (function EXECUTE grants, SECURITY DEFINER `is_project_member`, mutable
search_path on 15 functions, FUNCTION default ACL), P1-SEC-E (extensions in
`public`; `vector` has 237 dependents), and the unproven production
`DATABASE_URL` role.

**NOT APPLIED TO PRODUCTION. Awaiting MASTER production-remediation authorization.**
