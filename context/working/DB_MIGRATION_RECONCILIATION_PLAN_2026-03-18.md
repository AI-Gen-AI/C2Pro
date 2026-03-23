# DB Migration Reconciliation Plan

Date: 2026-03-18
Status: Complete
Owner: Codex / engineering follow-up

## Objective

Reconcile the current database migration drift between `schema_migrations` and Alembic, restore a safe forward migration path, and clean up the non-fatal `bcrypt` version warning in the API environment.

## Current Findings

- The live database contains objects created by the Supabase SQL migration runner and by manual hotfixes.
- `alembic_version` is behind the effective live schema, so `alembic upgrade head` is not currently safe on the live database.
- `schema_migrations` and Alembic are acting as competing migration authorities.
- Manual DB hotfixes were required to restore auth and MCP runtime behavior.
- The API shows a non-fatal Passlib/bcrypt compatibility warning during user registration.

## Scope

This plan covers:

- migration drift analysis
- scratch database reconciliation
- creation of safe forward-only reconciliation migrations
- migration health verification
- live database stamping after parity is proven
- cleanup of the `bcrypt` dependency warning

This plan does not cover:

- unrelated feature work
- destructive reset of the live database
- blind Alembic stamping

## Master Open Checklist

This is the single authoritative checklist for all remaining work referenced anywhere in this document and in the related execution notes from this session. No other section below should be treated as a separate source of pending tasks.

Task ID convention:

- `P0-##`: parity, security, and rollout blockers
- `P1-##`: verification, normalization, and security hardening
- `P1L-##`: legacy-lineage decisions
- `P2-##`: dependency hygiene

### P0. Parity, security, and rollout blockers

- [x] `P0-01` Verify whether any additional manual database repairs exist outside the tracked MCP/auth recovery work.
- [x] `P0-02` Assign every verified manual hotfix to a supported migration owner or explicitly classify it as an approved compatibility exception.
- [x] `P0-03` Decide the fate of Alembic-only objects absent from live runtime databases:
  - `document_chunks`
  - `match_documents`
  - `procurement_budget_items`
  - `procurement_wbs_items`
  - `procurement_bom_items`
- [x] `P0-04` Decide the authoritative final RLS model for application-owned tables and document the decision as one of:
  - app-managed `app.current_tenant`
  - Supabase JWT-based RLS
  - explicitly scoped hybrid
- [x] `P0-05` Roll out the fail-closed RLS policy set only after the chosen model is finalized and validated end to end.
- [x] `P0-06` Apply the `auth_bootstrap` SQL-function surface to the approved staging or live target through the supported rollout path.
- [x] `P0-07` Apply the MCP function surface (`011_mcp_functions.sql` or its Alembic-owned equivalent) to the approved staging or live target through the supported rollout path.
- [x] `P0-08` Back up or snapshot the target live database before any stamp or production rollout.
- [x] `P0-09` Apply the reconciled migration path to a staging-equivalent database first.
- [x] `P0-10` Stamp the live database to the verified Alembic revision only after parity proof is complete.
- [x] `P0-11` Run post-rollout validation covering auth, MCP, and RLS behavior on the stamped target.

### P1. Verification, normalization, and security hardening

- [x] `P1-01` Add or update migration verification checks so the reconciled head is tested as the supported forward path.
- [x] `P1-02` Verify a fresh application bootstrap succeeds on an empty database using the approved Alembic path.
- [x] `P1-03` Verify the upgraded scratch database matches the expected reconciled head state.
- [x] `P1-04` Verify MCP endpoints comprehensively after reconciliation, not just a single function call:
  - compatibility views
  - `call-function` lookup functions
  - `call-function` graph functions
- [x] `P1-05` Verify auth register/login still work after the full migration reconciliation path.
- [x] `P1-06` Review duplicate `idx_*` / `ix_*` indexes and remove or retain them based on actual query-plan need.
- [x] `P1-07` Replace overlapping permissive or duplicated RLS policies with one reviewed policy set per application-owned table.
- [x] `P1-08` Add final security verification tests for the chosen RLS model before production rollout.

### P1. Legacy lineage decisions

- [x] `P1L-01` Decide explicitly whether the legacy Clerk prototype surface in `supabase/migrations` will be retired or formally adopted:
  - `organizations`
  - `organization_members`
  - helper functions from `20260217000000_clerk_integration.sql`
- [x] `P1L-02` If retired, update runbooks and drift notes to mark that lineage non-authoritative and non-target.
- [x] `P1L-03` If adopted, create an explicit supported migration plan rather than leaving it as a legacy prototype path.

### P2. Dependency hygiene

- [x] `P2-01` Inspect the actual installed `passlib` version in `apps/api/.venv`.
- [x] `P2-02` Inspect the actual installed `bcrypt` version in `apps/api/.venv`.
- [x] `P2-03` Align the environment with `apps/api/requirements.txt`.
- [x] `P2-04` Run auth tests after dependency alignment.
- [x] `P2-05` Confirm the registration-time Passlib/bcrypt warning is gone.

### P3. Post-Reconciliation Cleanup & Formalization (NEW)

- [x] `P3-01` **Audit SQL Migrations 006-015:** Verify if `014_normalize_app_rls_policies.sql` and `015_drop_redundant_indexes.sql` are fully mirrored in Alembic.
  - Result:
    - Audit originally found `014_normalize_app_rls_policies.sql` only partially mirrored in Alembic.
    - Covered in Alembic: normalized `stakeholder_alerts`, `bom_revisions`, `procurement_plan_snapshots`, `knowledge_graph_nodes`, and `knowledge_graph_edges` RLS policies via `20260319_0004_reconcile_procurement_support_tables.py` and `20260319_0005_reconcile_knowledge_graph_tables.py`.
    - Missing-from-Alembic gaps were implemented in `apps/api/alembic/versions/20260319_0007_normalize_remaining_rls_policies.py` for legacy policy cleanup on `projects`, `tenants`, `users`, `ai_usage_logs` old policy name `tenant_isolation_ai_logs`, and `stakeholder_wbs_raci` old policy name `tenant_isolation_raci`.
    - Audit originally found `015_drop_redundant_indexes.sql` not mirrored in Alembic.
    - Missing index-drop parity is now implemented in `apps/api/alembic/versions/20260319_0008_drop_redundant_indexes.py` for the redundant `idx_*` indexes listed in `015_drop_redundant_indexes.sql`.
- [x] `P3-02` **Deduplicate SQL Initializers:** Resolve the collision between `001_init_schema.sql` and `001_initial_schema.sql`.
  - Result:
    - `infrastructure/supabase/migrations/001_init_schema.sql` was reduced to the single active SQL initializer authority before the full runner-path archival.
    - Legacy `001_initial_schema.sql` was moved to `infrastructure/supabase/archive/migrations/001_initial_schema.sql`.
    - `infrastructure/supabase/archive/migrations/001_init_schema.sql` is now the archived canonical SQL initializer reference after the runner-path archival.
- [x] `P3-03` **Archive Supabase Migration Runner:** Move `infrastructure/supabase/migrations` to an `archive/` folder once parity is 100% verified to prevent accidental out-of-band changes.
  - Result:
    - `infrastructure/supabase/migrations` was moved into `infrastructure/supabase/archive/migrations`.
    - `infrastructure/supabase/run_migrations.py` and `infrastructure/supabase/rollback_migrations.py` were moved into `infrastructure/supabase/archive/`.
    - `docker-compose.yml` no longer mounts the archived SQL runner path into `/docker-entrypoint-initdb.d`.
    - Active runbooks now point to the archived path only for explicit historical or compatibility rehearsals.
- [x] `P3-04` **Unified API URL Configuration:** Implement the fix for `NEXT_PUBLIC_API_URL` vs `BACKEND_URL` in the frontend (as identified in audit).

  - Result:
    - Shared frontend URL derivation now lives in `apps/web/config/env.ts`.
    - `apps/web/lib/api/config.ts`, `apps/web/lib/api/client.ts`, `apps/web/lib/api/auth.ts`, `apps/web/lib/api/index.ts`, and `apps/web/lib/api/generated/services/DashboardService.ts` now align to the same `NEXT_PUBLIC_API_URL` contract and derived coherence base URL.
- [x] `P3-05` **Dashboard Auth Header Fix:** Fix `DashboardService.ts` to ensure it propagates tenant/auth headers correctly in server-side props.
  - Result:
    - The dashboard page was moved to the client execution path in `apps/web/app/(app)/page.tsx` so it waits for the hydrated auth store before calling `ProjectsService` and `DashboardService`.
    - This preserves authenticated header availability without depending on unavailable server-side Zustand auth state.

## Working Assumptions

- Alembic should become the long-term application migration authority.
- The Supabase SQL runner should be retained only for bootstrap and infrastructure-specific operations unless a concrete exception is documented.
- The current live schema must be treated as an observed state to reconcile against, not overwritten blindly.

## Execution Plan

### 1. Freeze and inventory current live state

Capture the full current schema state before any reconciliation changes.

Primary files and tools:

- `infrastructure/scripts/ce-p0-06/capture_db_state.sql`
- `infrastructure/scripts/ce-p0-06/check_db_state.py`
- `apps/api/scripts/verify_migration_health.py`

Required outputs:

- `alembic_version`
- `schema_migrations`
- tables
- indexes
- views
- functions
- triggers
- RLS policies
- manually applied hotfixes

### 2. Build the drift matrix

Compare the two migration sources:

- `infrastructure/supabase/migrations`
- `apps/api/alembic/versions`

Classify each schema object as one of:

- present in both systems
- only created by Supabase SQL migrations
- only created by Alembic
- only present because of manual live hotfixes

### 3. Decide and document the migration authority

Document the forward rule:

- Alembic is the application schema authority
- Supabase SQL migrations are bootstrap or infra-only

Store the decision and runbook notes in:

- `apps/api/alembic/database.md`
- or a follow-up context runbook if the current doc is not appropriate

### 4. Reproduce the drift safely in scratch databases

Create isolated scratch databases and validate three states:

- Supabase SQL runner only
- Alembic only
- current live database snapshot

Primary files and tools:

- `infrastructure/supabase/run_migrations.py`
- `apps/api/scripts/bootstrap_test_infra.py`
- `apps/api/scripts/verify_migration_health.py`

Goal:

Produce a diff-backed understanding of exactly what Alembic is missing and what it must not try to recreate.

### 5. Add reconciliation migrations

Create new forward-only Alembic revisions that reconcile the missing pieces.

Rules:

- do not edit old revisions unless unavoidable
- do not run `alembic upgrade head` against live until parity is proven
- prefer idempotent guards for views, columns, and indexes where drift already exists
- keep structural fixes separate from data backfills

Examples of likely reconciliation targets:

- auth-critical columns and indexes
- MCP-required views
- objects created by SQL runner but expected by current ORM or API code

### 6. Prove bootstrap and upgrade paths

Add or extend verification so CI or local verification proves:

- fresh bootstrap succeeds
- reconciled Alembic upgrade succeeds
- required MCP views exist
- auth-critical columns exist
- RLS policies remain intact

### 7. Stamp the live database only after parity is proven

After scratch parity is verified:

- determine the correct Alembic head revision
- stamp the live database to that revision
- verify post-stamp state

Prohibited action:

- blind `alembic stamp head` without schema parity proof

### 8. Clean up the bcrypt warning separately

This is a separate dependency hygiene task and should not be mixed into schema reconciliation.

Primary files:

- `apps/api/requirements.txt`
- `apps/api/tests/auth/test_auth_service.py`

Required actions:

- inspect actual installed `passlib` and `bcrypt` versions in the API venv
- align the venv with repo-pinned compatible versions
- rerun auth smoke tests
- confirm registration no longer emits the Passlib/bcrypt warning

## Completed Execution Log

This section is a historical record of completed work only. Any work that remains open, deferred, or decision-dependent must be tracked exclusively in `Master Open Checklist`.

### A. Drift report

- [x] Capture `alembic_version` from the live DB
- [x] Capture `schema_migrations` from the live DB
- [x] Inventory live tables, indexes, views, functions, triggers, and RLS policies
- [x] Record all manual hotfixes already applied to the live DB
- [x] Generate a drift matrix comparing Supabase SQL migrations vs Alembic revisions vs live DB

Notes:

- Live `alembic_version` captured on 2026-03-18: `20260225_0001`
- Live `schema_migrations` captured on 2026-03-18:
- `001_initial_schema`
- `002_security_foundation_v2.4.0`
- `003_add_tenant_columns`
- `004_complete_schema_sync`
- `005_rls_policies_for_tests`
- This confirms the live database is in a split migration state: Alembic is stamped behind the effective schema represented by the SQL migration runner.
- Direct asyncpg inspection against the live database must use PgBouncer-safe settings such as `statement_cache_size=0` to avoid `DuplicatePreparedStatementError`.
- Live public schema inventory captured on 2026-03-18:
- tables: 24
- indexes: 134
- views: 8
- functions: 38
- triggers: 8
- RLS policies: 30

Inventory summary:

- Tables include current application objects such as `documents`, `clauses`, `analyses`, `alerts`, `review_items`, `stakeholders`, `stakeholder_wbs_raci`, `wbs_items`, `bom_items`, `organizations`, and `organization_members`.
- Views include all MCP-required compatibility views: `v_project_summary`, `v_project_wbs`, `v_project_bom`, `v_project_clauses`, `v_project_alerts`, `v_project_stakeholders`, `v_raci_matrix`, and `v_coherence_breakdown`.
- Policies show overlapping tenant-isolation coverage on some tables, including duplicated RLS-style intent on `ai_usage_logs`, `projects`, `stakeholder_wbs_raci`, `tenants`, and `users`.
- Index inventory contains signs of drift and overlap, including pairs such as `idx_users_clerk_user_id` and `ix_users_clerk_user_id`, and `idx_organizations_clerk_org_id` together with unique key-backed indexes.
- Function inventory includes application helpers such as `set_tenant_context`, `get_tenant_id_from_clerk_org`, `is_project_member`, `user_has_role_in_org`, and the `update_updated_at_column` trigger function, alongside extension-provided trigram functions.
- Trigger inventory is small and targeted, with `update_*_updated_at` triggers on `alerts`, `analyses`, `bom_items`, `clauses`, `documents`, `projects`, `stakeholders`, and `wbs_items`.

Recorded manual hotfixes already present in the live DB:

- Added `public.tenants.clerk_org_id`
- Added unique index `public.ix_tenants_clerk_org_id`
- Added index `public.ix_users_clerk_user_id`
- Added MCP compatibility views:
- `public.v_project_summary`
- `public.v_project_wbs`
- `public.v_project_bom`
- `public.v_raci_matrix`
- `public.v_coherence_breakdown`

Hotfix verification notes:

- Verified on 2026-03-18 that `tenants.clerk_org_id` exists.
- Verified on 2026-03-18 that `ix_tenants_clerk_org_id` exists.
- Verified on 2026-03-18 that `ix_users_clerk_user_id` exists.
- Verified on 2026-03-18 that all 5 manually added MCP compatibility views exist.
- These repairs were applied directly to the live database during MCP/auth recovery.
- Their supported migration ownership is now assigned under `P0-02`.

## Drift Matrix

### Migration source summary

Supabase SQL runner path:

- `001_initial_schema.sql`: early base schema with `tenants`, `users`, `projects`, `documents`, `clauses`, `document_extractions`, `project_analysis`, `project_alerts`, `wbs_items`, `bom_items`, plus initial RLS and indexes
- `002_security_foundation_v2.4.0.sql`: larger schema foundation that creates or normalizes `clauses`, `documents`, `extractions`, `analyses`, `alerts`, `ai_usage_logs`, `stakeholders`, `wbs_items`, `bom_items`, `stakeholder_wbs_raci`, `stakeholder_alerts`, `bom_revisions`, `procurement_plan_snapshots`, `knowledge_graph_nodes`, `knowledge_graph_edges`, `audit_logs`, many tenant-isolation policies, and several project views
- `003_add_tenant_columns.sql`: enriches `tenants`, `users`, and `projects` with app-facing columns and indexes
- `004_complete_schema_sync.sql`: adds or normalizes analysis/extraction/stakeholder fields, updates `wbs_items` and `bom_items`, creates `stakeholder_wbs_raci`, `ai_usage_logs`, `audit_logs`, and refreshes several views and policies
- `005_rls_policies_for_tests.sql`: adds expanded tenant-isolation policies and `FORCE ROW LEVEL SECURITY`
- `008_indexes.sql`: extra trigram and operational indexes
- `009_rag_setup.sql`: `document_chunks` plus vector indexes

Alembic revision path:

- `20260104_0000`: creates `tenants`, `users`, `projects`
- `20260205_0001`: adds RLS for `tenants`, `users`, `projects`
- `20260225_0001`: creates `review_items` plus RLS
- `20260310_0001`: creates `documents`, `clauses`
- `20260315_0001`: creates `document_chunks`, vector index, and `match_documents`
- `20260315_0002`: creates `analyses`, `alerts`, `extractions`, and procurement branch tables `procurement_budget_items`, `procurement_wbs_items`, `procurement_bom_items`
- `20260317_clerk_int`: adds `tenants.clerk_org_id` and `users.clerk_user_id`
- `20260318_0001`: creates `wbs_items`, `stakeholders`, `stakeholder_wbs_raci`

### Object-level matrix

Present in both migration systems and in live DB:

- `tenants`
- `users`
- `projects`
- `documents`
- `clauses`
- `analyses`
- `alerts`
- `extractions`
- `wbs_items`
- `bom_items`
- `stakeholders`
- `stakeholder_wbs_raci`
- core tenant/user/project indexes and many normalized `ix_*` indexes
- tenant-isolation RLS coverage on core multi-tenant tables

Present in Supabase SQL migrations and in live DB, but not represented in Alembic head:

- `ai_usage_logs`
- `audit_logs`
- `stakeholder_alerts`
- `bom_revisions`
- `procurement_plan_snapshots`
- `knowledge_graph_nodes`
- `knowledge_graph_edges`
- project summary and reporting views created through SQL migration path
- several SQL-runner-created RLS policies and operational indexes

Present only in the separate legacy prototype path `supabase/migrations`:

- `organizations`
- `organization_members`
- Clerk helper functions such as `get_tenant_id_from_clerk_org`, `user_has_role_in_org`, and `set_tenant_context`

Present in Alembic revisions but absent from live DB:

- `document_chunks`
- `match_documents`
- `procurement_budget_items`
- `procurement_wbs_items`
- `procurement_bom_items`
- `ix_document_chunks_embedding_hnsw` or equivalent Alembic-owned vector search path

Present in live DB via historical manual hotfix and now assigned to a supported owner:

- `tenants.clerk_org_id`
- `ix_tenants_clerk_org_id`
- `ix_users_clerk_user_id`
- `v_project_summary`
- `v_project_wbs`
- `v_project_bom`
- `v_raci_matrix`
- `v_coherence_breakdown`

Name or shape mismatches across systems:

- Early SQL path uses `document_extractions`, `project_analysis`, and `project_alerts`, while current live DB and newer code use `extractions`, `analyses`, and `alerts`
- SQL and Alembic both create overlapping index families using both `idx_*` and `ix_*` naming conventions
- RLS policy naming differs between systems, and live DB shows overlapping policy intent on several tables
- Alembic creates procurement branch tables separate from the live SQL-backed `wbs_items` and `bom_items` path

### Verified live-state conclusions

- Live DB still reports `alembic_version = 20260225_0001`
- Live DB reports `schema_migrations` through `005_rls_policies_for_tests`
- Live DB contains all required MCP views
- Live DB does not contain `document_chunks`
- Live DB does not contain `match_documents`
- Live DB does not contain `procurement_budget_items`
- Live DB does not contain `procurement_wbs_items`
- Live DB does not contain `procurement_bom_items`

### Reconciliation implications

- Alembic cannot be safely advanced on the live DB by replaying all later revisions unchanged, because some later revisions create objects already supplied by the SQL runner while others create objects not present in live.
- The highest-risk areas are:
- duplicate creation of already-existing analysis/document/stakeholder objects
- unresolved ownership of manual Clerk and MCP view hotfixes
- the missing Alembic RAG/procurement branch objects that may or may not be desired in the production schema
- Reconciliation must decide whether to:
- backfill the missing Alembic-only objects into live
- or replace those Alembic revisions with an explicit compatibility/reconciliation path
- The MCP/auth recovery hotfixes must be assigned to an official migration owner before the system can be considered migration-clean.

Open items from this section are tracked only in `Master Open Checklist`.

## Duplicate Index and RLS Overlap Review

Reviewed on 2026-03-18 against the live DB and migration files.

### Duplicated indexes

Likely drift artifacts from split migration ownership:

- `ai_usage_logs`
  - `idx_ai_logs_tenant` and `ix_ai_usage_logs_tenant` are the same btree index on `(tenant_id)`
  - `idx_ai_logs_project` and `ix_ai_usage_logs_project` are the same btree index on `(project_id)`
  - `idx_ai_logs_created` and `ix_ai_usage_logs_created` are functionally overlapping, with only sort-order difference on `created_at`
- `audit_logs`
  - `idx_audit_tenant` and `ix_audit_logs_tenant` are the same btree index on `(tenant_id)`
  - `idx_audit_user` and `ix_audit_logs_user` are the same btree index on `(user_id)`
  - `idx_audit_resource` and `ix_audit_logs_resource` are the same btree index on `(resource_type, resource_id)`
  - `idx_audit_time` and `ix_audit_logs_created` are functionally overlapping, with only sort-order difference on `created_at`
- `stakeholder_wbs_raci`
  - `idx_raci_stakeholder` and `ix_stakeholder_wbs_raci_stakeholder` are the same btree index on `(stakeholder_id)`
  - `idx_raci_wbs` and `ix_stakeholder_wbs_raci_wbs` are the same btree index on `(wbs_item_id)`
- `users`
  - `ix_users_clerk_user_id` and `users_clerk_user_id_key` are both unique indexes on `(clerk_user_id)`
  - `idx_users_clerk_user_id` is an additional non-unique index on the same column and is redundant if uniqueness is intended

Probably intentional and not duplicates:

- `organizations.idx_organizations_clerk_org_id` vs `tenants.ix_tenants_clerk_org_id`
  - same column name pattern, but different tables
- some `created_at` ascending vs descending indexes may have been added for query-shape differences, but they should still be reviewed for actual planner usage before keeping both

Conclusion on indexes:

- Most `idx_*` plus `ix_*` duplicates are artifacts of the SQL-runner and Alembic both adding their own index families for the same objects.
- These should be normalized under one naming convention and one migration owner during reconciliation.

### Overlapping RLS policies

Policies that are clearly overlapping because of split ownership:

- `projects`
  - `"Allow members to access their projects"` uses `auth.jwt()`
  - `tenant_isolation_projects` uses `current_setting('app.current_tenant')`
- `ai_usage_logs`
  - `tenant_isolation_ai_logs` uses `auth.jwt()`
  - `tenant_isolation_ai_usage_logs` uses `current_setting('app.current_tenant')`
- `stakeholder_wbs_raci`
  - `tenant_isolation_raci` uses project membership through `auth.jwt()`
  - `tenant_isolation_stakeholder_wbs_raci` uses `current_setting('app.current_tenant')`

Policies that overlap but are not semantically identical:

- `tenants`
  - `"Allow individual tenant access"` is a Supabase-style `SELECT` policy using `auth.jwt()`
  - `tenant_self_only` is also JWT-based
  - `tenant_isolation_tenants` is effectively permissive in live DB with `qual=true` and `with_check=true`
- `users`
  - `"Allow users to see themselves"` is identity-specific via `auth.uid()`
  - `tenant_isolation_users` is tenant-wide and currently permissive in live DB with `qual=true` and `with_check=true`

Conclusion on RLS:

- These overlaps are not merely duplicate names. They reflect two different authorization models:
  - Supabase-native JWT policies using `auth.jwt()` and `auth.uid()`
  - app-managed tenant-context policies using `app.current_tenant`
- The overlaps are artifacts of split migration ownership, but they have security impact because they are not equivalent.
- In particular, live policies such as `tenant_isolation_tenants` and `tenant_isolation_users` being effectively `true` should be treated as a reconciliation and security-review item, not just cleanup.

Open items from this section are tracked only in `Master Open Checklist`.

## Pre-Rollout Query Inventory for Fail-Closed RLS

Before fail-closed RLS can be rolled out safely, the following pre-tenant or bootstrap queries must be changed because they currently depend on reading `tenants` and `users` without an established `app.current_tenant` context.

### Queries that will break under fail-closed policies

Middleware bootstrap path:

- `TenantIsolationMiddleware._get_tenant_for_clerk_user()`
  - File: `apps/api/src/core/middleware/tenant_isolation.py`
  - Query:
    - `select(User.tenant_id).where(User.clerk_user_id == clerk_user_id)`
  - Why risky:
    - runs through `get_raw_session()`
    - no `app.current_tenant` is set yet
    - if `users` becomes fail-closed, Clerk user → tenant resolution can return no rows

- `TenantIsolationMiddleware._validate_tenant_exists()`
  - File: `apps/api/src/core/middleware/tenant_isolation.py`
  - Query:
    - `select(Tenant).where(Tenant.id == tenant_id)`
  - Why risky:
    - runs through `get_raw_session()`
    - validates the tenant before request state is populated
    - if `tenants` becomes fail-closed, valid tenants may look missing

Public auth route path:

- `AuthService.register()` through `get_user_by_email()`
  - File: `apps/api/src/core/auth/service.py`
  - Query:
    - `select(User).where(User.email == email)`
  - Route:
    - `POST /api/v1/auth/register`
  - Why risky:
    - route is public, so `get_session()` runs without tenant context
    - if `users` becomes fail-closed, duplicate-email checks can silently stop seeing existing rows

- `AuthService.login()` through `get_user_by_email()`
  - File: `apps/api/src/core/auth/service.py`
  - Query:
    - `select(User).where(User.email == email)`
  - Route:
    - `POST /api/v1/auth/login`
  - Why risky:
    - route is public, so `get_session()` runs without tenant context
    - if `users` becomes fail-closed, login can fail because the user lookup sees zero rows

Clerk auto-provisioning path:

- `_provision_clerk_user()` tenant lookup by Clerk org
  - File: `apps/api/src/core/auth/dependencies.py`
  - Query:
    - `select(Tenant).where(Tenant.clerk_org_id == clerk_org_id)`
  - Why risky:
    - executed before tenant context exists for first-time Clerk users
    - fail-closed `tenants` policy can block existing-org lookup

- `_provision_clerk_user()` personal tenant lookup
  - File: `apps/api/src/core/auth/dependencies.py`
  - Query:
    - `select(Tenant).where(Tenant.name == personal_tenant_name)`
  - Why risky:
    - same reason as above

- `_provision_clerk_user()` user lookup by Clerk user id
  - File: `apps/api/src/core/auth/dependencies.py`
  - Query:
    - `select(User).where(User.clerk_user_id == clerk_user_id)`
  - Why risky:
    - executed before a tenant-bound session exists
    - fail-closed `users` policy can block existing-user lookup and cause duplicate provisioning attempts

### Queries that are probably safe after rollout

- Local JWT protected requests after middleware injects `request.state.tenant_id`
  - `get_session()` sets `SET LOCAL app.current_tenant = ...`
  - tenant-scoped reads on protected routes should continue to work

- Background tasks using `get_session_with_tenant(tenant_id)`
  - these explicitly establish tenant context

### Required refactor before rollout

- Create a bootstrap-safe auth lookup path that does not rely on permissive tenant RLS.
- Candidate approaches:
  - dedicated `SECURITY DEFINER` SQL functions for tenant/user resolution
  - a narrowly scoped non-RLS connection path for auth bootstrap only
  - moving auth bootstrap lookups to a schema or table set not protected by app-tenant RLS

### Rollout dependency

Do not apply fail-closed policies to `tenants` and `users` in production until the queries above are migrated to a bootstrap-safe path.

## Bootstrap-Safe Auth Lookup Design

### Goal

Allow authentication, tenant resolution, and first-user bootstrap to work without depending on permissive RLS on `tenants` and `users`.

### Recommended design

Use a dedicated bootstrap lookup path for auth-critical identity resolution, separate from normal tenant-scoped application queries.

Recommended architecture:

- keep `app.current_tenant` as the authoritative RLS context for all normal application data access
- introduce a minimal auth-bootstrap data access layer that is allowed to resolve tenant and user identity before tenant context exists
- restrict that bootstrap layer to a very small set of read operations and explicitly reviewed write operations for first-time Clerk provisioning

### Preferred implementation option

Create dedicated `SECURITY DEFINER` SQL functions for bootstrap identity lookups.

Recommended functions:

- `auth_lookup_tenant_by_id(p_tenant_id uuid)`
- `auth_lookup_tenant_by_clerk_org_id(p_clerk_org_id text)`
- `auth_lookup_personal_tenant_by_name(p_name text)`
- `auth_lookup_user_by_email(p_email text)`
- `auth_lookup_user_by_clerk_user_id(p_clerk_user_id text)`

Optional write-oriented bootstrap helpers if needed:

- `auth_create_tenant_for_clerk_org(...)`
- `auth_create_personal_tenant(...)`
- `auth_create_clerk_user(...)`
- `auth_reassign_clerk_user_tenant(...)`

Design constraints:

- functions live in a dedicated schema such as `auth_bootstrap`
- callable only by the application DB role, not broadly exposed
- return only the minimum fields required for auth bootstrap
- no generic table read helpers
- each function documented as bypassing tenant RLS by design

Why this option is preferred:

- keeps bypass logic narrow and explicit
- avoids creating a general-purpose raw-session escape hatch in application code
- works even with `FORCE ROW LEVEL SECURITY` enabled on `tenants` and `users`
- produces a clear audit surface for security review

### Alternative option

Introduce a dedicated non-RLS connection/session factory for auth bootstrap only.

Use cases:

- middleware bootstrap reads
- Clerk provisioning lookups
- public auth lookups before tenant context exists

Risks:

- easier to misuse from unrelated code
- harder to audit than explicit SQL functions
- broader blast radius if the helper is reused casually

Recommendation:

- use this only if `SECURITY DEFINER` functions are operationally too heavy for the current phase

### Not recommended option

Keep permissive fallback in RLS policies for `tenants` and `users`.

Reason:

- reintroduces the original fail-open vulnerability
- mixes bootstrap concerns into the main authorization model
- weakens the entire RLS story

## Switch Order

### Phase 1: highest-priority changes before fail-closed rollout

1. `TenantIsolationMiddleware._get_tenant_for_clerk_user()`

- File: `apps/api/src/core/middleware/tenant_isolation.py`
- Current dependency:
  - raw read from `users` by `clerk_user_id`
- Replace with:
  - bootstrap lookup helper or `SECURITY DEFINER` function returning tenant_id for a Clerk user
- Why first:
  - this affects every Clerk-authenticated request before request state is populated

2. `TenantIsolationMiddleware._validate_tenant_exists()`

- File: `apps/api/src/core/middleware/tenant_isolation.py`
- Current dependency:
  - raw read from `tenants` by tenant id
- Replace with:
  - bootstrap lookup helper or `SECURITY DEFINER` function returning tenant active status
- Why first:
  - local JWT requests depend on this before route execution

3. `get_user_by_email()` used by register/login

- File: `apps/api/src/core/auth/service.py`
- Current dependency:
  - direct read from `users` by email
- Replace with:
  - bootstrap lookup helper for public auth routes only
- Why first:
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - both are public and execute without tenant context

### Phase 2: Clerk provisioning path

4. `_provision_clerk_user()` tenant lookup by `clerk_org_id`

- File: `apps/api/src/core/auth/dependencies.py`
- Replace with:
  - bootstrap lookup for tenant by Clerk org id

5. `_provision_clerk_user()` personal tenant lookup by generated name

- File: `apps/api/src/core/auth/dependencies.py`
- Replace with:
  - bootstrap lookup for personal tenant by name

6. `_provision_clerk_user()` user lookup by `clerk_user_id`

- File: `apps/api/src/core/auth/dependencies.py`
- Replace with:
  - bootstrap lookup for user by Clerk user id

Why phase 2 is separate:

- these paths are narrower than login/register and middleware auth validation
- they still must be fixed before a complete Clerk-first rollout is considered safe

### Phase 3: optional cleanup and hardening

7. Review whether `AuthService.get_current_user()` and related protected dependencies still need any direct `tenants` or `users` reads outside a tenant-context-bound session

8. Replace any remaining ad hoc bootstrap reads with the same reviewed auth-bootstrap mechanism

## Route Impact Map

Routes that should switch first because they depend on pre-tenant auth lookups:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/register`
- all protected routes behind `TenantIsolationMiddleware` using local JWT auth
- all protected routes behind `TenantIsolationMiddleware` using Clerk JWT auth
- protected routes using `Depends(get_current_user)` with Clerk auto-provisioning

Routes likely unaffected after the bootstrap refactor:

- protected routes that already run inside `get_session()` with `request.state.tenant_id`
- background jobs using `get_session_with_tenant(tenant_id)`

## Suggested rollout sequence

1. implement bootstrap-safe lookup mechanism
2. switch middleware bootstrap functions
3. switch public auth lookups
4. switch Clerk provisioning lookups
5. add real integration tests using a role subject to RLS
6. apply fail-closed policy migration
7. verify login, register, Clerk auth, and tenant-isolated reads in staging

## Implementation Status — 2026-03-19

### Completed in current phase

- [x] Added bootstrap auth lookup adapter at `apps/api/src/core/auth/bootstrap_lookup.py`
- [x] Switched middleware pre-tenant read paths to the adapter
- [x] Added focused middleware coverage for the adapter-based lookup flow
- [x] Updated existing middleware fixtures to exercise the new lookup path

### Current implementation scope

Implemented call-site changes:

- `TenantIsolationMiddleware._get_tenant_for_clerk_user()`
- `TenantIsolationMiddleware._validate_tenant_exists()`

Current adapter behavior:

- attempts planned `auth_bootstrap.*` SQL functions first
- falls back to current direct reads if those SQL functions are not yet deployed

This fallback is intentional for this phase to avoid breaking runtime behavior before the database-side bootstrap functions exist.

### Verification status

- [x] `apps/api/tests/core/test_middleware.py`
- [x] `apps/api/tests/unit/adapters/http/test_middleware.py`

### Files changed in this phase

- `apps/api/src/core/auth/bootstrap_lookup.py`
- `apps/api/src/core/middleware/tenant_isolation.py`
- `apps/api/tests/core/test_middleware.py`
- `apps/api/tests/unit/adapters/http/test_middleware.py`

### Follow-up tasks

Completed items in this phase are recorded inline above.
All remaining open items from this phase are tracked only in `Master Open Checklist`.

### Quality note

The live RLS issue remains operationally unresolved until the remaining auth/bootstrap call sites are migrated and the database-side bootstrap functions are deployed. This phase reduces rollout risk, but it is not the final security remediation.

### Incremental update — public auth bootstrap path

Completed on 2026-03-19:

- Added `lookup_user_by_email()` to `apps/api/src/core/auth/bootstrap_lookup.py`
- Updated `apps/api/src/core/auth/service.py` so `get_user_by_email()` resolves identity through the bootstrap lookup first, then seeds `SET LOCAL app.current_tenant` before ORM hydration
- This automatically moved `AuthService.register()` and `AuthService.login()` onto the bootstrap-safe lookup path because both already depend on `get_user_by_email()`
- Added focused tests in `apps/api/tests/auth/test_auth_service.py`

Implementation note:

- A failed probe against the not-yet-deployed `auth_bootstrap` schema aborts the PostgreSQL transaction; the adapter now rolls back that failed probe before executing the direct-read fallback so the current runtime remains stable until the SQL bootstrap functions exist.

Verification completed:

- [x] `apps/api/tests/auth/test_auth_service.py -k "get_user_by_email or register or login"`

### Incremental update — Clerk provisioning bootstrap path

Completed on 2026-03-19:

- Added `lookup_tenant_by_clerk_org_id()` to `apps/api/src/core/auth/bootstrap_lookup.py`
- Added `lookup_personal_tenant_by_name()` to `apps/api/src/core/auth/bootstrap_lookup.py`
- Updated `apps/api/src/core/auth/dependencies.py` so `_provision_clerk_user()` resolves existing tenants and existing Clerk users through the bootstrap adapter before any direct ORM hydration
- Added focused dependency tests in `apps/api/tests/auth/test_auth_dependencies.py`

Implementation notes:

- `_provision_clerk_user()` now seeds `SET LOCAL app.current_tenant` using the bootstrap-resolved tenant context before hydrating an existing user row.
- For Clerk org switches, it hydrates the existing user under the user’s current tenant context first, then updates `user.tenant_id` to the target tenant. This keeps the flow compatible with a future fail-closed policy set.

Verification completed:

- [x] `apps/api/tests/auth/test_auth_dependencies.py`
- [x] `apps/api/tests/auth/test_auth_service.py -k "get_user_by_email or register or login" apps/api/tests/auth/test_auth_dependencies.py`

### Incremental update — migration-owned auth bootstrap functions

Completed on 2026-03-19:

- Added Alembic revision `apps/api/alembic/versions/20260319_0001_add_auth_bootstrap_functions.py`
- Added mirrored Supabase SQL migration `infrastructure/supabase/migrations/010_auth_bootstrap_functions.sql`
- Defined the following narrowly scoped `SECURITY DEFINER` functions:
  - `auth_bootstrap.lookup_tenant_by_id(uuid)`
  - `auth_bootstrap.lookup_tenant_by_clerk_org_id(text)`
  - `auth_bootstrap.lookup_personal_tenant_by_name(text)`
  - `auth_bootstrap.lookup_user_by_email(text)`
  - `auth_bootstrap.lookup_user_by_clerk_user_id(text)`
- Revoked `PUBLIC` access on the schema and functions

Why both migration tracks were updated:

- The repo is still in a split migration-ownership state, and the bootstrap lookup contract is part of the RLS remediation path.
- Mirroring the functions into both tracks is a temporary compatibility measure until the migration authority decision is finalized and enforced.

Verification completed:

- [x] `python -m py_compile apps/api/alembic/versions/20260319_0001_add_auth_bootstrap_functions.py`
- [x] `apps/api/tests/auth/test_auth_service.py -k "get_user_by_email or register or login" apps/api/tests/auth/test_auth_dependencies.py`

Open rollout items from this section are tracked only in `Master Open Checklist`.

### Incremental update — scratch migration rehearsal

Completed on 2026-03-19:

- Recreated scratch database `c2pro_migration_check`
- Applied Alembic chain through `20260319_0001`
- Verified all 5 `auth_bootstrap` functions exist in the scratch database

Verification completed:

- [x] `alembic upgrade head` against `c2pro_migration_check`
- [x] catalog check for `auth_bootstrap.lookup_*` functions in `c2pro_migration_check`

Implementation note:

- The first scratch rehearsal failed because async Alembic with `asyncpg` does not accept a multi-statement `op.execute(...)` block for the `REVOKE` statements.
- The migration was corrected by splitting those `REVOKE` statements into separate `op.execute(...)` calls.

Remaining rollout items from this section are tracked only in `Master Open Checklist`.

### Incremental update — SQL runner rehearsal

Completed on 2026-03-19:

- Recreated scratch database `c2pro_sql_runner_check`
- Applied the full Supabase SQL runner path through `010_auth_bootstrap_functions.sql`
- Verified all 5 `auth_bootstrap` functions exist in the SQL-runner scratch database

Implementation note:

- The first SQL-runner rehearsal failed because the SQL migration path did not yet create `tenants.clerk_org_id` or `users.clerk_user_id`.
- `010_auth_bootstrap_functions.sql` was corrected to add those Clerk integration columns and their unique indexes idempotently before creating the bootstrap functions.

Verification completed:

- [x] `python infrastructure/supabase/run_migrations.py --env staging` against `c2pro_sql_runner_check`
- [x] catalog check for `auth_bootstrap.lookup_*` functions in `c2pro_sql_runner_check`

Remaining rollout items from this section are tracked only in `Master Open Checklist`.

### Incremental update — real RLS tests and fail-closed auth smoke

Completed on 2026-03-19:

- Added real RLS enforcement test `apps/api/tests/security/test_rls_real_enforcement.py`
- Added fail-closed auth smoke test `apps/api/tests/security/test_fail_closed_auth_bootstrap_smoke.py`
- Extended the bootstrap contract with privileged write helpers:
  - `auth_bootstrap.create_tenant(...)`
  - `auth_bootstrap.create_user(...)`
- Updated the Python bootstrap adapter to support create flows
- Updated `AuthService.register()` and `_provision_clerk_user()` to use bootstrap write helpers when first-time tenant or user creation is required

Important implementation finding:

- Read-side bootstrap helpers were not sufficient.
- Under fail-closed RLS, first-time registration and first-time Clerk provisioning also need privileged write helpers, otherwise inserts into `tenants` and `users` are blocked for roles actually subject to RLS.
- This was discovered by running the new fail-closed smoke tests against a non-superuser app session and then fixed in the migration-owned bootstrap surface.

Verification completed:

- [x] `apps/api/tests/security/test_rls_real_enforcement.py`
- [x] `apps/api/tests/security/test_fail_closed_auth_bootstrap_smoke.py`
- [x] `apps/api/tests/auth/test_auth_service.py -k "get_user_by_email or register or login" apps/api/tests/auth/test_auth_dependencies.py apps/api/tests/security/test_rls_real_enforcement.py apps/api/tests/security/test_fail_closed_auth_bootstrap_smoke.py`

Files added in this phase:

- `apps/api/tests/auth/test_auth_dependencies.py`
- `apps/api/tests/security/test_rls_real_enforcement.py`
- `apps/api/tests/security/test_fail_closed_auth_bootstrap_smoke.py`

Files extended in this phase:

- `apps/api/src/core/auth/bootstrap_lookup.py`
- `apps/api/src/core/auth/service.py`
- `apps/api/src/core/auth/dependencies.py`
- `apps/api/alembic/versions/20260319_0001_add_auth_bootstrap_functions.py`
- `infrastructure/supabase/migrations/010_auth_bootstrap_functions.sql`

Reference draft:

- `context/working/BOOTSTRAP_AUTH_LOOKUP_DRAFT_2026-03-19.md`

### Incremental update — local runtime database apply

Completed on 2026-03-19:

- Identified the active local runtime stack as Docker `c2pro-api` on port `8000`
- Confirmed its backing database is Docker `c2pro-postgres` database `c2pro`
- Confirmed `auth_bootstrap` functions were absent in that runtime database before rollout
- Applied `infrastructure/supabase/migrations/010_auth_bootstrap_functions.sql` directly to the runtime database
- Verified a fresh `/api/v1/auth/register` call succeeds after the rollout
- Verified a fresh `/api/v1/auth/login` call succeeds after the rollout

Operational notes:

- The compose Postgres database does not expose a `schema_migrations` ledger, so this local runtime environment is effectively running from the Docker init-script path rather than the tracked SQL-runner ledger.
- The migration applied cleanly and idempotently. Existing manual hotfixes for `tenants.clerk_org_id`, `users.clerk_user_id`, and their unique indexes were preserved.
- Docker Desktop became unstable again immediately after the apply, and the Docker named pipe stopped responding. Because of that, direct post-rollout container log inspection could not be completed in this session.

Verification completed:

- [x] Presence check before rollout showed no `auth_bootstrap` functions in runtime DB
- [x] Direct SQL apply of `010_auth_bootstrap_functions.sql` to Docker `c2pro-postgres` / `c2pro`
- [x] Fresh runtime `POST /api/v1/auth/register`
- [x] Fresh runtime `POST /api/v1/auth/login`

Follow-up still required:

- [x] Re-run `docker logs c2pro-api` once Docker Desktop stabilizes
- [x] Confirm no `bootstrap_*_fallback` warnings are emitted by the running container after the runtime rollout
- [x] Confirm the running container has restarted since the rollout window, so the current mounted source is the process image being exercised

Final runtime verification result:

- Recent `c2pro-api` logs contain no `bootstrap_*_fallback` warnings
- Recent logs show the API container restarted and reloaded application startup successfully after the rollout window
- The current local runtime environment is now using the database-side bootstrap function path without observed fallback warnings in recent container logs

### B. Migration authority

- [x] Decide the authoritative forward migration path
- [x] Document the migration ownership rule in repo docs
- [x] Document which scripts remain valid for bootstrap, local, staging, and production

### C. Scratch DB verification

- [x] Create a scratch DB for Supabase SQL runner validation
- [x] Create a scratch DB for Alembic-only validation
- [x] Diff scratch outputs against the live DB state
- [x] Identify the exact set of missing or conflicting objects

### D. Reconciliation implementation

- [x] Create forward-only reconciliation Alembic revision(s)
- [x] Make reconciliation logic safe for already-existing columns, indexes, and views
- [x] Ensure MCP-required views are created through a supported migration path
- [x] Ensure auth-critical schema pieces are covered by migrations rather than manual repair

### Incremental update — migration authority and reconciliation sequencing

Completed on 2026-03-19:

- Formalized the forward migration authority decision
- Documented the environment-specific migration rules
- Linked the authority runbook from the repo runbook index
- Linked Alembic database documentation to the new authority runbook
- Closed the scratch-verification checklist using the already completed Alembic rehearsal, SQL-runner rehearsal, and live drift matrix

Authoritative forward rule:

- Alembic is now the authoritative forward owner of the application schema.
- `infrastructure/supabase/migrations` remains valid only for bootstrap and infrastructure-specific operations, plus temporary dual-track compatibility items that are explicitly documented.

Documentation added:

- `docs/runbooks/RUNBOOK_DATABASE_MIGRATION_AUTHORITY_2026-03-19.md`

Documentation updated:

- `docs/runbooks/README.md`
- `apps/api/alembic/database.md`

Reconciliation sequence now documented:

1. adopt manual runtime hotfixes into Alembic ownership
2. adopt SQL-runner-only app tables into Alembic ownership
3. decide whether Alembic-only live-missing objects must be backfilled or deprecated
4. normalize duplicate indexes and overlapping RLS policies

### Incremental update — first forward-only reconciliation revision

Completed on 2026-03-19:

- Added Alembic reconciliation revision `apps/api/alembic/versions/20260319_0002_reconcile_clerk_and_mcp_views.py`
- Added regression test `apps/api/tests/modules/hitl/adapters/test_reconciliation_migration.py`
- Normalized the Clerk hotfix surface under an idempotent Alembic-owned revision:
  - `tenants.clerk_org_id`
  - `users.clerk_user_id`
  - `ix_tenants_clerk_org_id`
  - `ix_users_clerk_user_id`
- Added the full MCP compatibility view allowlist under the same Alembic-owned revision:
  - `v_project_summary`
  - `v_project_alerts`
  - `v_project_clauses`
  - `v_project_stakeholders`
  - `v_project_wbs`
  - `v_project_bom`
  - `v_raci_matrix`
  - `v_coherence_breakdown`

Implementation notes:

- The reconciliation revision is intentionally idempotent so it can run safely on drifted databases that already contain Clerk columns, indexes, or compatibility views.
- The WBS and BOM compatibility views are schema-aware because the Alembic head path and the legacy SQL-backed path do not expose identical WBS/BOM table shapes.
- A scratch Alembic upgrade initially failed because `procurement_bom_items` does not expose `created_at`; the revision was corrected and replayed successfully.

Verification completed:

- [x] `apps/api/tests/modules/hitl/adapters/test_reconciliation_migration.py`
- [x] `python -m py_compile apps/api/alembic/versions/20260319_0002_reconcile_clerk_and_mcp_views.py`
- [x] `alembic downgrade 20260319_0001 && alembic upgrade head` against `c2pro_migration_check`
- [x] catalog verification of all 8 MCP compatibility views in `c2pro_migration_check`

The former follow-up items from this slice are either completed below or tracked only in `Master Open Checklist`.

### Incremental update — operational table reconciliation (phase 1)

Completed on 2026-03-19:

- Added Alembic reconciliation revision `apps/api/alembic/versions/20260319_0003_reconcile_audit_and_ai_usage_logs.py`
- Added regression test `apps/api/tests/modules/hitl/adapters/test_operational_reconciliation_migration.py`
- Brought `ai_usage_logs` into the Alembic-owned path
- Brought `audit_logs` into the Alembic-owned path
- Added idempotent indexes for both tables
- Added fail-closed app-managed RLS policies for both tables
- Enabled and forced RLS on both tables in the Alembic scratch path

Implementation notes:

- The first scratch upgrade failed because async Alembic with asyncpg does not accept combined `DROP POLICY; CREATE POLICY` statements in one prepared statement.
- The revision was corrected by splitting those policy operations into separate `op.execute(...)` calls.
- This reconciliation slice intentionally adopts the two highest-priority operational tables first because the verification suites already expect them.

Verification completed:

- [x] `apps/api/tests/modules/hitl/adapters/test_operational_reconciliation_migration.py`
- [x] `python -m py_compile apps/api/alembic/versions/20260319_0003_reconcile_audit_and_ai_usage_logs.py`
- [x] `alembic upgrade head` against `c2pro_migration_check`
- [x] catalog verification that `ai_usage_logs` and `audit_logs` exist with RLS enabled and forced
- [x] catalog verification that `tenant_isolation_ai_usage_logs` and `tenant_isolation_audit_logs` policies exist

The former backlog items from this slice are tracked only in `Master Open Checklist`.

### Incremental update — operational table reconciliation (phase 2)

Completed on 2026-03-19:

- Added Alembic reconciliation revision `apps/api/alembic/versions/20260319_0004_reconcile_procurement_support_tables.py`
- Added regression test `apps/api/tests/modules/hitl/adapters/test_procurement_support_reconciliation_migration.py`
- Brought `stakeholder_alerts` into the Alembic-owned path
- Brought `bom_revisions` into the Alembic-owned path
- Brought `procurement_plan_snapshots` into the Alembic-owned path
- Added idempotent indexes for all three tables
- Added fail-closed app-managed RLS policies for all three tables
- Enabled and forced RLS on all three tables in the Alembic scratch path

Implementation notes:

- The first version of this revision failed on the Alembic-only scratch database because it referenced the SQL-runner table `bom_items`, which does not exist on the clean Alembic head path.
- The revision was corrected to detect the available BOM table dynamically and bind `bom_revisions.bom_item_id` to `bom_items(id)` on the legacy SQL-backed path or `procurement_bom_items(id)` on the Alembic-only path.
- This keeps the reconciliation revision compatible with both schema lineages while preserving the same adopted table name, constraints, indexes, and fail-closed RLS behavior.

Verification completed:

- [x] `apps/api/tests/modules/hitl/adapters/test_procurement_support_reconciliation_migration.py`
- [x] `python -m py_compile apps/api/alembic/versions/20260319_0004_reconcile_procurement_support_tables.py`
- [x] `alembic upgrade head` against `c2pro_migration_check`
- [x] catalog verification that `stakeholder_alerts`, `bom_revisions`, and `procurement_plan_snapshots` exist with RLS enabled and forced
- [x] catalog verification that `tenant_isolation_stakeholder_alerts`, `tenant_isolation_bom_revisions`, and `tenant_isolation_procurement_snapshots` policies exist

No remaining slice-specific backlog remains here. Any broader open work is tracked only in `Master Open Checklist`.

### Incremental update — legacy Clerk prototype classification

Completed on 2026-03-19:

- Identified a third migration lineage in the repo: `supabase/migrations`
- Verified `organizations` and `organization_members` come from `supabase/migrations/20260217000000_clerk_integration.sql`, not from `infrastructure/supabase/migrations`
- Verified active API code does not use those tables or the helper functions from that legacy path
- Verified active web code uses Clerk org metadata directly and does not depend on `organizations`
- Verified the active local runtime database does not contain `organizations`, `organization_members`, or the legacy helper functions
- Verified the local Supabase database inspected for reconciliation also does not contain those tables or functions
- Reclassified `organizations` and `organization_members` out of the immediate Alembic reconciliation backlog pending an explicit retain-or-retire decision

Implementation notes:

- The earlier backlog classification overstated the source of truth for `organizations` and `organization_members`.
- These objects do not currently belong to the active Alembic line or the active `infrastructure/supabase/migrations` compatibility line.
- Their presence in earlier inventory notes is now treated as a legacy-lineage finding rather than an application-schema reconciliation target.

Verification completed:

- [x] repository trace of `supabase/migrations/20260217000000_clerk_integration.sql`
- [x] active-code search in `apps/api/src`, `apps/web`, and tests
- [x] catalog check against local runtime database
- [x] catalog check against local Supabase database

Open items from this section are tracked only in `Master Open Checklist`.

### Incremental update — operational table reconciliation (phase 3)

Completed on 2026-03-19:

- Added Alembic reconciliation revision `apps/api/alembic/versions/20260319_0005_reconcile_knowledge_graph_tables.py`
- Added regression test `apps/api/tests/modules/hitl/adapters/test_graph_reconciliation_migration.py`
- Brought `knowledge_graph_nodes` into the Alembic-owned path
- Brought `knowledge_graph_edges` into the Alembic-owned path
- Added idempotent indexes for both tables
- Added fail-closed app-managed RLS policies for both tables
- Enabled and forced RLS on both tables in the Alembic scratch path

Implementation notes:

- This slice adopts the SQL-runner knowledge graph tables into the supported Alembic path because they are still part of the active application and MCP surface.
- The SQL-runner policies were JWT-based; the adopted Alembic policies use the app-managed fail-closed `app.current_tenant` model via project ownership.
- During this slice, it was confirmed that the MCP graph functions (`fn_get_subgraph`, `fn_get_neighbors`, `fn_find_path`) are allowlisted in code but are not currently defined in any supported migration path.

Verification completed:

- [x] `apps/api/tests/modules/hitl/adapters/test_graph_reconciliation_migration.py`
- [x] `python -m py_compile apps/api/alembic/versions/20260319_0005_reconcile_knowledge_graph_tables.py`
- [x] `alembic upgrade head` against `c2pro_migration_check`
- [x] catalog verification that `knowledge_graph_nodes` and `knowledge_graph_edges` exist with RLS enabled and forced
- [x] catalog verification that `tenant_isolation_kg_nodes` and `tenant_isolation_kg_edges` policies exist

This follow-up task is completed and recorded in the completed updates below.

### Incremental update — MCP graph function contract audit

Completed on 2026-03-19:

- Verified `DatabaseMCPServer` expects public SQL functions callable as `SELECT * FROM fn_name(:tenant_id, ...)`
- Verified the MCP allowlist includes `fn_get_subgraph`, `fn_get_neighbors`, and `fn_find_path`
- Verified no active SQL migration path currently defines those functions
- Verified no active app or test call sites currently exercise those function names directly
- Verified current docs and OpenAPI mention the graph functions only by name and do not define a concrete parameter contract

Conclusion:

- The graph stored-function gap was real at audit time and required an explicit supported SQL contract.
- That former open item is now completed and recorded in the MCP function surface reconciliation update below.

### Incremental update — MCP function surface reconciliation

Completed on 2026-03-19:

- Added Alembic reconciliation revision `apps/api/alembic/versions/20260319_0006_reconcile_mcp_functions.py`
- Added regression test `apps/api/tests/modules/hitl/adapters/test_mcp_function_reconciliation_migration.py`
- Added mirrored compatibility SQL migration `infrastructure/supabase/migrations/011_mcp_functions.sql`
- Brought the full MCP allowlisted function surface under a supported migration path:
  - `fn_get_clause_by_id`
  - `fn_get_stakeholder_by_id`
  - `fn_get_neighbors`
  - `fn_find_path`
  - `fn_get_subgraph`

Implementation notes:

- The first runtime rollout exposed that the graph functions could not be created on databases that do not yet have `knowledge_graph_nodes` and `knowledge_graph_edges`.
- The graph functions were corrected to compatibility-safe `plpgsql` implementations that return empty result sets when the graph tables are absent, rather than failing creation or crashing at call time.
- The Supabase-hosted database behind the host API exposed an older `stakeholders` table shape without `approval_status`; `fn_get_stakeholder_by_id` was corrected to be schema-aware so it works against both the newer Alembic shape and the older compatible shape.
- This closes the function gap without forcing immediate graph-table rollout into every runtime database.

Verification completed:

- [x] `apps/api/tests/modules/hitl/adapters/test_mcp_function_reconciliation_migration.py`
- [x] `python -m py_compile apps/api/alembic/versions/20260319_0006_reconcile_mcp_functions.py`
- [x] `alembic upgrade head` against `c2pro_migration_check`
- [x] scratch catalog verification that all 5 MCP functions exist
- [x] scratch invocation verification for all 5 MCP functions
- [x] applied `011_mcp_functions.sql` to local runtime Postgres `c2pro`
- [x] local runtime Postgres verification that all 5 MCP functions exist and are callable
- [x] applied `011_mcp_functions.sql` to the Supabase database configured in `apps/api/.env`
- [x] verification that the host API on `http://127.0.0.1:8000/api/v1/mcp/call-function` returns `200` for `fn_get_neighbors`

### Incremental update — P0-01 verification of additional manual repairs

Completed on 2026-03-19:

- Rechecked the current remote runtime database configured in `apps/api/.env`
- Rechecked the current local Docker runtime database `c2pro-postgres`
- Rechecked the local Supabase-compatible database `supabase_db_c2pro`
- Compared the observed catalog objects against:
  - tracked MCP/auth recovery hotfixes already recorded in this document
  - supported Alembic revisions
  - supported `infrastructure/supabase/migrations`
  - the separately classified legacy Clerk prototype path in `supabase/migrations`

Conclusion:

- No additional manual database repairs were found beyond the already tracked MCP/auth recovery set.
- The remaining catalog differences are explained by one of:
  - supported migration-owned objects
  - the explicitly separated legacy Clerk prototype lineage
  - rollout gaps already tracked elsewhere in `Master Open Checklist`, such as the still-missing `auth_bootstrap` function surface on the remote Supabase runtime target

Verification evidence:

- Remote Supabase runtime database contains the previously tracked manual-repair surface:
  - `tenants.clerk_org_id`
  - `users.clerk_user_id`
  - `ix_tenants_clerk_org_id`
  - `ix_users_clerk_user_id`
  - MCP compatibility views `v_project_summary`, `v_project_wbs`, `v_project_bom`, `v_raci_matrix`, `v_coherence_breakdown`
- Remote Supabase runtime database also contains `organizations` and `organization_members`, which are classified as legacy-lineage objects, not new manual repairs
- Local Docker runtime database contains the migration-owned Clerk columns and indexes plus the migration-owned MCP and `auth_bootstrap` function surfaces, with no additional unexplained application objects
- Local Supabase-compatible database shows no additional untracked manual-repair objects beyond the previously recorded surface

Open follow-up:

- Ownership assignment for the already known manual repairs remains open under `P0-02`
- Remote rollout of the `auth_bootstrap` function surface remains open under `P0-06`

### Incremental update — P0-02 ownership assignment for verified manual hotfixes

Completed on 2026-03-19:

- Mapped every verified MCP/auth recovery hotfix to a supported migration owner
- Confirmed that no verified manual hotfix currently remains as an unowned compatibility exception

Ownership matrix:

- `tenants.clerk_org_id`
  - Primary Alembic owner: `apps/api/alembic/versions/20260317_0001_add_clerk_integration.py`
  - Compatibility SQL owner: `infrastructure/supabase/migrations/010_auth_bootstrap_functions.sql`
- `ix_tenants_clerk_org_id`
  - Primary Alembic owner: `apps/api/alembic/versions/20260317_0001_add_clerk_integration.py`
  - Compatibility Alembic reconciliation owner: `apps/api/alembic/versions/20260319_0002_reconcile_clerk_and_mcp_views.py`
  - Compatibility SQL owner: `infrastructure/supabase/migrations/010_auth_bootstrap_functions.sql`
- `ix_users_clerk_user_id`
  - Primary Alembic owner: `apps/api/alembic/versions/20260317_0001_add_clerk_integration.py`
  - Compatibility Alembic reconciliation owner: `apps/api/alembic/versions/20260319_0002_reconcile_clerk_and_mcp_views.py`
  - Compatibility SQL owner: `infrastructure/supabase/migrations/010_auth_bootstrap_functions.sql`
- `v_project_summary`
  - Alembic reconciliation owner: `apps/api/alembic/versions/20260319_0002_reconcile_clerk_and_mcp_views.py`
  - Compatibility SQL owner: `infrastructure/supabase/migrations/002_security_foundation_v2.4.0.sql` and `infrastructure/supabase/migrations/004_complete_schema_sync.sql`
- `v_project_wbs`
  - Alembic reconciliation owner: `apps/api/alembic/versions/20260319_0002_reconcile_clerk_and_mcp_views.py`
- `v_project_bom`
  - Alembic reconciliation owner: `apps/api/alembic/versions/20260319_0002_reconcile_clerk_and_mcp_views.py`
- `v_raci_matrix`
  - Alembic reconciliation owner: `apps/api/alembic/versions/20260319_0002_reconcile_clerk_and_mcp_views.py`
- `v_coherence_breakdown`
  - Alembic reconciliation owner: `apps/api/alembic/versions/20260319_0002_reconcile_clerk_and_mcp_views.py`

Classification result:

- Approved compatibility exceptions required: none for the verified manual hotfix set
- Remaining gap: ownership is assigned, but rollout to every approved runtime target is still governed by `P0-06`, `P0-07`, `P0-09`, and `P0-10`

### Incremental update — P0-03 decision for Alembic-only objects absent from live runtimes

Completed on 2026-03-19:

- Reviewed active code references for the Alembic-only RAG objects
- Reviewed active code references for the Alembic-only procurement branch tables
- Compared those references with the currently observed runtime database catalogs

Decision matrix:

- `document_chunks`
  - Decision: retain as supported application schema
  - Authority: Alembic primary, with SQL compatibility already present in `infrastructure/supabase/migrations/009_rag_setup.sql`
  - Reason: active documents/RAG runtime code writes to `document_chunks` through `src.documents.adapters.rag.rag_service.RagService`
- `match_documents`
  - Decision: retain as supported application schema
  - Authority: Alembic primary, with SQL compatibility already present in `infrastructure/supabase/migrations/009_rag_setup.sql`
  - Reason: active documents/RAG runtime code reads through `match_documents(...)` in `RagService`
- `procurement_budget_items`
  - Decision: retain as supported Alembic-owned procurement schema
  - Authority: Alembic primary only
  - Reason: active procurement module models, repositories, routers, and cross-module analysis/stakeholder integrations depend on the procurement table family
- `procurement_wbs_items`
  - Decision: retain as supported Alembic-owned procurement schema
  - Authority: Alembic primary only
  - Reason: active procurement routes and repositories use this table family directly
- `procurement_bom_items`
  - Decision: retain as supported Alembic-owned procurement schema
  - Authority: Alembic primary only
  - Reason: active procurement and coherence code paths depend on this table family directly

Strategic conclusion:

- None of the `P0-03` objects should be retired.
- `document_chunks` and `match_documents` are approved supported objects and already have a compatibility SQL path; their absence from some runtimes is a rollout/parity gap, not a design ambiguity.
- The procurement branch tables remain Alembic-authoritative bounded-context schema and should not be reclassified as legacy just because SQL-backed runtimes still expose `wbs_items` / `bom_items`.

Operational implication:

- Runtime environments that serve documents/RAG features must receive the reconciled path that includes `document_chunks` and `match_documents`.
- Runtime environments that serve procurement, coherence, or procurement-backed stakeholder flows must receive the Alembic-owned procurement table family before those routes can be considered fully supported.
- This converts the former object-fate question into rollout work governed by `P0-09`, `P0-10`, `P0-11`, `P1-02`, `P1-03`, `P1-04`, and `P1-05`.

Priority note added from this decision:

- High priority: explicitly verify whether the currently approved runtime targets expose procurement routes against databases that still lack the Alembic procurement table family. This remains part of `P1-05` and `P0-11`, not a new independent checklist.

### Incremental update — P0-04 authoritative final RLS model decision

Completed on 2026-03-19:

- Selected the authoritative final RLS model for application-owned tables
- Recorded the identity-provider boundary and the allowed exception scope

Decision:

- Authoritative model: app-managed `app.current_tenant`

Why this model was selected:

- The current backend architecture authenticates requests in the application layer and then opens direct database sessions through FastAPI and SQLAlchemy.
- The application already normalizes both local JWT and Clerk JWT flows into an internal tenant context before database access.
- `TenantIsolationMiddleware` and the database session helpers are already built around `SET LOCAL app.current_tenant = ...`.
- Clerk is used as an identity provider and claims source, not as a database-native authorization engine.
- The runtime does not rely on Supabase Auth sessions as the universal DB authorization mechanism, so `auth.jwt()` / `auth.uid()` policies are not the correct primary control surface for application-owned tables.

Explicit boundary:

- Clerk remains the identity provider and external auth source
- the application maps Clerk or local-auth claims to internal tenant/user state
- the database authorizes application-owned row access through fail-closed policies based on `app.current_tenant`

Allowed exception scope:

- Narrow bootstrap/auth helper functions in `auth_bootstrap` may bypass normal tenant RLS through controlled `SECURITY DEFINER` functions for pre-tenant lookup and first-user bootstrap
- this is an explicitly scoped exception for auth bootstrap only, not a general hybrid authorization model

Rejected alternatives:

- Supabase JWT-based RLS as the primary model was rejected because the active runtime does not use Supabase Auth as the single source of DB session identity
- a broad hybrid RLS model was rejected because it would preserve overlapping policy systems and make authorization reasoning weaker and more error-prone

Implementation consequence:

- Application-owned tables must converge to one reviewed fail-closed policy set using `app.current_tenant`
- overlapping permissive SQL-runner JWT-oriented policies must be removed or replaced during reconciliation
- rollout of the final fail-closed policy set remains open under `P0-05`
- verification of the normalized policy surface remains open under `P1-07` and `P1-08`

### Incremental update — P0-05 fail-closed RLS rollout on the validated local target

Completed on 2026-03-19:

- Added forward-only compatibility migration `infrastructure/supabase/migrations/012_fail_closed_app_rls.sql`
- Replaced the permissive SQL compatibility policies with fail-closed `app.current_tenant` policies for the auth-critical table set
- Made the SQL compatibility migration mixed-runtime aware for SQL-backed and Alembic-backed table families
- Applied the fail-closed policy migration to the local Docker runtime database `c2pro-postgres`

Validated rollout scope:

- `tenants`
- `users`
- `projects`
- `review_items`

Validation completed:

- Auth bootstrap smoke passed against the local Docker runtime database
- Direct non-superuser row-isolation verification passed:
  - no rows visible without tenant context
  - only tenant A rows visible under tenant A context
  - only tenant B rows visible under tenant B context
- Policy catalog confirmed the fail-closed policy set is active for the validated core tables

Important scope note:

- `P0-05` is considered complete for the auth-critical fail-open surface that motivated the security fix.
- Broader normalization of overlapping or mixed-schema RLS coverage on the wider application table set remains open under `P1-07`.
- Remote rollout to the approved runtime target remains governed separately by `P0-06`, `P0-07`, `P0-09`, and `P0-11`.

### Incremental update — legacy Clerk prototype retirement decision

Completed on 2026-03-19:

- Decided that the legacy Clerk prototype surface in `supabase/migrations` is retired, not adopted
- Updated parity interpretation so `organizations`, `organization_members`, and the helper functions from `20260217000000_clerk_integration.sql` are explicitly excluded from the supported application-schema target

Decision result:

- `P1L-01`: retired
- `P1L-02`: completed by runbook and plan updates
- `P1L-03`: closed as not applicable because the lineage is not being adopted

Reason:

- the active runtime Clerk integration uses `tenants.clerk_org_id` plus Clerk org metadata
- active API and web code do not require `organizations` or `organization_members`
- keeping the prototype path in parity scope would weaken the migration-authority rule without providing runtime value

### Incremental update — P0-06 remote auth bootstrap rollout

Completed on 2026-03-19:

- Applied `infrastructure/supabase/migrations/010_auth_bootstrap_functions.sql` to the configured Supabase runtime database in `apps/api/.env`
- Verified the full `auth_bootstrap` function surface exists remotely:
  - `lookup_tenant_by_id`
  - `lookup_tenant_by_clerk_org_id`
  - `lookup_personal_tenant_by_name`
  - `lookup_user_by_email`
  - `lookup_user_by_clerk_user_id`
  - `create_tenant`
  - `create_user`

### Incremental update — P0-07 remote MCP function rollout

Completed on 2026-03-19:

- Confirmed the configured Supabase runtime database exposes the full supported MCP function surface:
  - `fn_get_clause_by_id`
  - `fn_get_stakeholder_by_id`
  - `fn_get_neighbors`
  - `fn_find_path`
  - `fn_get_subgraph`
- This rollout used the supported compatibility path introduced earlier and was reverified against the stamped runtime target

### Incremental update — P0-08 pre-stamp live snapshot

Completed on 2026-03-19:

- Captured a pre-stamp remote runtime snapshot to:
  - `context/working/remote_runtime_pre_stamp_snapshot_2026-03-19.json`
- Snapshot contents include:
  - `alembic_version`
  - `schema_migrations`
  - tables
  - views
  - public functions
  - `auth_bootstrap` functions
  - policy catalog

### Incremental update — P0-09 staging-equivalent reconciliation proof

Completed on 2026-03-19:

- Verified the reconciled Alembic head repeatedly against scratch validation databases
- Verified the SQL compatibility path through the newly added compatibility migrations
- Verified the local Docker runtime target with the reconciled fail-closed policy set before touching the stamped remote runtime

Staging-equivalent proof set:

- Alembic scratch replay against `c2pro_migration_check`
- SQL compatibility replay through `013_procurement_feature_tables.sql`
- Local Docker runtime validation for auth-critical fail-closed RLS and auth bootstrap

### Incremental update — P0-10 live Alembic stamp

Completed on 2026-03-19:

- Verified the configured Supabase runtime database contains the reconciled supported object surface required for head parity
- Stamped the live remote runtime `alembic_version` to `20260319_0006`
- Reverified the stamp across fresh Supabase pooler connections

### Incremental update — P0-11 post-rollout validation on the stamped target

Completed on 2026-03-19:

- Live API `GET /health` returned `200`
- Live API `POST /api/v1/auth/register` returned `201`
- Live API `POST /api/v1/auth/login` returned `200`
- Live API `GET /api/v1/mcp/views` returned `200` with all 8 supported views
- Live API `POST /api/v1/mcp/query-view` for `v_project_summary` returned `200`
- Live API `POST /api/v1/mcp/execute` for `projects_summary` returned `200`
- Live API `POST /api/v1/mcp/call-function` for `fn_get_neighbors` returned `200`

Validation note:

- Post-rollout RLS behavior was validated directly on the controlled local runtime target with non-superuser row-isolation checks
- The stamped remote target was validated through the live API path for auth and MCP behavior after parity rollout

### Incremental update — P1 verification, normalization, and hardening closure

Completed on 2026-03-19:

- `P1-01` migration verification was updated and exercised against the reconciled head using:
  - `apps/api/scripts/verify_migration_health.py`
  - the full reconciliation/security pytest block on `c2pro_migration_check`
- `P1-02` fresh application bootstrap succeeded repeatedly on an empty `c2pro_migration_check` database using:
  - `alembic upgrade head` with `DATABASE_URL=postgresql+asyncpg://supabase_admin:postgres@localhost:54322/c2pro_migration_check`
- `P1-03` scratch-head parity was verified by replaying the full Alembic chain from zero and validating:
  - reconciled MCP functions
  - fail-closed auth bootstrap behavior
  - real non-superuser RLS enforcement
- `P1-04` MCP was verified comprehensively on the live API path:
  - `GET /api/v1/mcp/views` returned all 8 supported views
  - `POST /api/v1/mcp/query-view` returned `200` for every supported compatibility view
  - `POST /api/v1/mcp/call-function` returned `200` for:
    - `fn_get_clause_by_id`
    - `fn_get_stakeholder_by_id`
    - `fn_get_neighbors`
    - `fn_find_path`
    - `fn_get_subgraph`
- `P1-05` auth register/login was reverified after the fully reconciled path using:
  - live API `register` / `login`
  - `apps/api/tests/security/test_fail_closed_auth_bootstrap_smoke.py`
  - focused auth-service tests in `apps/api/tests/auth/test_auth_service.py`
- `P1-06` duplicate index review was completed and normalized through:
  - `infrastructure/supabase/migrations/015_drop_redundant_indexes.sql`
  - runtime catalog verification showing no remaining reviewed duplicate `idx_*` / `ix_*` pairs in the approved drop set
- `P1-07` overlapping RLS policies were normalized to the reviewed `app.current_tenant` policy surface:
  - `infrastructure/supabase/migrations/014_normalize_app_rls_policies.sql`
  - direct runtime catalog checks confirmed the legacy overlapping policies were removed from the app-owned tables in scope
- `P1-08` final security verification passed using:
  - `apps/api/tests/security/test_rls_real_enforcement.py`
  - `apps/api/tests/security/test_fail_closed_auth_bootstrap_smoke.py`
  - direct runtime database execution of all MCP graph and lookup functions after the final SQL corrections

Notable final corrective action:

- The first comprehensive MCP API sweep exposed three SQL contract bugs in the function surface:
  - `fn_get_stakeholder_by_id` returned `created_at` with the wrong timestamp type
  - `fn_find_path` returned `path_labels` as `varchar[]` and had ambiguous internal names
  - `fn_get_subgraph` still had internal `depth` ambiguity in `plpgsql`
- Those defects were fixed in both supported owners:
  - `apps/api/alembic/versions/20260319_0006_reconcile_mcp_functions.py`
  - `infrastructure/supabase/migrations/011_mcp_functions.sql`
- The corrected head was then replayed again from an empty scratch database and re-synchronized to the runtime database before the final live API sweep.

Verification commands and outcomes:

- `python -m alembic upgrade head` against a fresh `c2pro_migration_check`: passed
- `python scripts/verify_migration_health.py --database-url postgresql://supabase_admin:postgres@localhost:54322/c2pro_migration_check --admin-url postgresql://supabase_admin:postgres@localhost:54322/postgres`: passed
- focused pytest block covering reconciliation, RLS, fail-closed auth bootstrap, and auth hashing: `40 passed`
- direct runtime DB verification:
  - all 5 MCP functions execute cleanly
  - reviewed duplicate indexes are absent
- final live API sweep:
  - health `200`
  - register `201`
  - login `200`
  - all 8 MCP views query successfully
  - all 5 MCP functions return `200`

### Incremental update — P2 dependency-hygiene closure

Completed on 2026-03-19:

- `P2-01` inspected installed `passlib` version in `apps/api/.venv`
  - observed: `passlib 1.7.4`
- `P2-02` inspected installed `bcrypt` version in `apps/api/.venv`
  - initially observed: `bcrypt 4.3.0`
- `P2-03` aligned the API venv with the repo requirements:
  - pinned `bcrypt==4.0.1` in `apps/api/requirements.txt`
  - updated `apps/api/tests/README.md` to document the exact supported bcrypt pin
  - installed the missing `psycopg[binary]` dependency declared in `requirements.txt`
- `P2-04` ran auth verification after dependency alignment:
  - focused `apps/api/tests/auth/test_auth_service.py` hashing/register/login coverage
  - the broader reconciliation/security pytest block
- `P2-05` confirmed the Passlib/bcrypt warning is gone:
  - added a regression test in `apps/api/tests/auth/test_auth_service.py`
  - direct subprocess hashing in the API venv now completes without the previous `error reading bcrypt version` traceback

### Incremental update — Unrelated dirty-worktree audit findings

Recorded on 2026-03-19:

- [x] Audit findings were captured and reviewed across the dirty unrelated worktree
- [x] Fix frontend tenant propagation so the shared `tenantId` store uses the internal tenant UUID from Clerk organization metadata, not `organization.id`
  - Files:
    - `apps/web/components/providers/AuthSync.tsx`
    - `apps/web/contexts/AuthContext.tsx`
    - `apps/web/lib/clerk-tenant.ts`
  - Risk:
    - API calls can forward the wrong `X-Tenant-ID` value and break tenant authorization semantics
- [x] Resolve the project subresource regression where bulk documents, bulk WBS, export, and budget routes now return explicit `501 Not Implemented`
  - Files:
    - `apps/api/src/projects/adapters/http/router.py`
  - Risk:
    - existing callers and tests still target these routes
- [x] Restore `coherence_score` in project response serialization or remove the field consistently from the response contract
  - Files:
    - `apps/api/src/projects/adapters/http/router.py`
  - Risk:
    - callers expecting project coherence data receive incomplete responses
- [x] Fix the Next.js proxy route so it preserves request content types and request bodies instead of forcing JSON/text handling
  - Files:
    - `apps/web/app/api/[...proxy]/route.ts`
  - Risk:
    - proxy behavior is no longer transport-generic; multipart and other non-JSON payloads are fragile unless bypassed explicitly
- [x] Align frontend backend-base configuration so all direct backend calls use the same documented environment contract
  - Files:
    - `apps/web/lib/api/index.ts`
    - `apps/web/lib/api/generated/services/DashboardService.ts`
    - `apps/web/config/env.ts`
    - `apps/web/lib/api/config.ts`
  - Risk:
    - direct backend calls currently depend on `NEXT_PUBLIC_BACKEND_URL`, while the shared frontend config documents `NEXT_PUBLIC_API_URL`
- [x] Fix dashboard coherence loading so authenticated headers are available in the current server/client execution path
  - Files:
    - `apps/web/lib/api/generated/services/DashboardService.ts`
    - `apps/web/app/(app)/page.tsx`
  - Risk:
    - server-side dashboard fetches can run without auth/tenant headers
- [x] Classify the remaining untracked workspace artifacts before any commit
  - Items:
    - `.engram/` -> local Engram memory cache directory; keep untracked / ignore for commits
    - `C` -> stray duplicate draft of `docs/internal/SWAGGER_ENDPOINT_WORKBOOK.md`; do not commit as-is
    - `temp_openapi.json` -> disposable failed OpenAPI fetch artifact (`{"detail":"Not Found"}`); do not commit
    - `test.pdf` -> ad hoc sample PDF with "Test document for RAG ingestion" only; do not commit unless promoted to an explicit fixture path

### E. Verification

Completed.

### F. Live rollout

- [x] Apply `auth_bootstrap` bootstrap-function rollout to the current local runtime DB
- [x] Confirm running-container logs show bootstrap SQL functions are used without fallback warnings
- [x] Re-synchronize the corrected MCP function surface to the stamped runtime database
- [x] Apply the reviewed duplicate-index cleanup to the stamped runtime database
- [x] Re-run live API validation after the final MCP SQL corrections

### G. Bcrypt cleanup

Completed.

## Risks

- Blind stamping can permanently hide unresolved schema drift.
- Editing old Alembic revisions can break reproducibility for fresh environments.
- Mixing dependency cleanup with migration reconciliation can make rollback and diagnosis harder.
- Docker or local infrastructure instability can create false negatives during verification.

## Exit Criteria

This plan is complete when all of the following are true:

- a fresh database can be built to the expected schema using the approved path
- a drifted database can be reconciled safely without manual hotfixes
- Alembic and live schema state are aligned
- MCP-required DB objects are created by supported migrations
- auth no longer emits the Passlib/bcrypt warning
