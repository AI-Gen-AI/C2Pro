# Database Migration Authority Runbook

Date: `2026-03-19`  
Scope: `DB migration authority, environment usage rules, and reconciliation sequencing`

## Objective

Establish one forward migration authority for the application schema, define which migration tools remain valid in each environment, and document the reconciliation order for the current split-state database estate.

## Decision

Effective immediately:

- `apps/api/alembic/versions` is the authoritative forward migration path for the application schema.
- `infrastructure/supabase/archive/migrations` is an archived reference-only SQL runner path.
- `supabase/migrations` is a legacy prototype migration path and must not be used as an active schema authority.

This means:

- new application tables, columns, indexes, views, and RLS changes must be owned by Alembic
- staging and production schema evolution must not depend on `schema_migrations`
- staging and production schema evolution must not depend on `supabase/migrations`
- Supabase SQL files remain valid only where Alembic cannot be the owning mechanism

## Why This Decision Was Made

Observed state on `2026-03-18` and `2026-03-19`:

- the live drifted database reports `alembic_version = 20260225_0001`
- the same database reports `schema_migrations` through `005_rls_policies_for_tests`
- the live schema contains SQL-runner-owned objects, Alembic-owned objects, and manual hotfixes
- the repo also contains a separate legacy prototype path under `supabase/migrations`, including `20260217000000_clerk_integration.sql`
- `alembic upgrade head` is not safe on the drifted live database without reconciliation
- the bootstrap-auth remediation had to be mirrored into both tracks temporarily to keep the runtime stable while ownership is being normalized

Alembic is the better forward owner because it is already wired into the API repo, test infrastructure, and deterministic head checks.

## Environment Rules

### 1. Fresh application schema in CI or scratch databases

Use:

- `alembic upgrade head`

Do not use:

- `infrastructure/supabase/archive/run_migrations.py`

Reason:

- CI and scratch environments must prove deterministic application-schema bootstrapping from the Alembic graph.

### 2. Existing local compose runtime database

Use:

- targeted SQL apply only for temporary compatibility or bootstrap recovery when the existing Docker volume has already bypassed normal initialization
- Alembic for future reconciled app-schema changes once parity is proven

Do not assume:

- mounting archived SQL bootstrap scripts into `/docker-entrypoint-initdb.d` is no longer part of the supported local runtime path

Reason:

- the compose Postgres volume is persistent and does not replay init scripts after first initialization.

### 3. Local Supabase stack

Use:

- archived SQL runner files under `infrastructure/supabase/archive/` only for historical reference or explicitly isolated compatibility rehearsals
- Alembic for application-schema determinism checks
- never `supabase/migrations` as an active migration source

Reason:

- the Supabase stack is still part of the compatibility surface, but it is not the forward application-schema authority.

### 3a. Legacy prototype Supabase path

Path:

- `supabase/migrations`

Status:

- legacy prototype / reference-only

Do not use for:

- local runtime rollout
- staging rollout
- production rollout
- schema drift reconciliation

Current finding:

- `supabase/migrations/20260217000000_clerk_integration.sql` introduces `organizations`, `organization_members`, and Clerk helper functions that are not present in the active Alembic path, are not present in the active local databases, and are not used by the current runtime Clerk integration, which now relies on `tenants.clerk_org_id` plus Clerk org metadata.
- Retirement decision (2026-03-19): this legacy Clerk prototype surface is explicitly retired and is not part of the supported parity target for staging or production schema management.

### 4. Staging and production application schema changes

Use:

- Alembic only

Do not use:

- `run_migrations.py` as the primary schema owner for app changes
- direct SQL hotfixes unless part of an approved incident procedure and later reconciled into Alembic

Reason:

- the drift problem exists precisely because both systems were allowed to act as schema owners.

### 5. Supabase-only infrastructure bootstrap

Use:

- `infrastructure/supabase/archive/migrations`

Examples:

- extension/bootstrap prerequisites
- Supabase platform-specific setup
- temporary compatibility SQL that must exist before the Alembic-owned runtime can take over

Condition:

- every such exception must be documented and, where relevant to the app schema, mirrored or superseded by Alembic.

## Approved Tooling by Task

| Task                                                 | Approved path                                                                               |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| App schema from clean DB                             | `alembic upgrade head`                                                                      |
| Alembic graph / head validation                      | `apps/api/scripts/verify_migration_health.py`                                               |
| Archived SQL-runner compatibility rehearsal          | `python infrastructure/supabase/archive/run_migrations.py --env staging` against scratch DB |
| Existing compose DB hotfix or bootstrap-compat apply | targeted `psql` or one-off SQL apply, then reconcile into Alembic                           |
| Staging / production app rollout                     | Alembic revision(s) only                                                                    |
| Supabase platform bootstrap                          | SQL runner / SQL editor path                                                                |

## Temporary Exceptions Still Allowed

These are compatibility exceptions while reconciliation is in progress:

- `infrastructure/supabase/archive/migrations/010_auth_bootstrap_functions.sql`
- `apps/api/alembic/versions/20260319_0001_add_auth_bootstrap_functions.py`

Why this exception exists:

- the runtime RLS remediation required the same bootstrap contract in both tracks before migration ownership could be normalized safely.

Exit condition:

- once the reconciled Alembic path fully owns the required schema surface and the legacy SQL-runner path is demoted to infra/bootstrap-only, dual-track ownership must stop.

## Reconciliation Revision Set

The next forward-only Alembic work should be split into bounded revision groups.

### Revision group 1: adopt manual runtime hotfixes

Goal:

- make all currently required Clerk and MCP compatibility objects Alembic-owned

Target objects:

- `tenants.clerk_org_id`
- `ix_tenants_clerk_org_id`
- `users.clerk_user_id` / `ix_users_clerk_user_id` normalization if needed
- `v_project_summary`
- `v_project_wbs`
- `v_project_bom`
- `v_raci_matrix`
- `v_coherence_breakdown`

Notes:

- these must be idempotent because the drifted runtime databases already contain them

### Revision group 2: adopt SQL-runner-only operational tables required by the live app estate

Goal:

- remove app-schema dependence on legacy SQL-runner ownership

Priority objects:

- `ai_usage_logs`
- `audit_logs`
- `stakeholder_alerts`
- `bom_revisions`
- `procurement_plan_snapshots`

Notes:

- this group must include index and RLS normalization where those tables are application-owned

Out-of-scope pending classification:

- `organizations`
- `organization_members`

Reason:

- these objects currently trace back to the legacy `supabase/migrations` Clerk prototype path rather than the active Alembic path or the archived `infrastructure/supabase/archive/migrations` compatibility reference path
- they are absent from the active local runtime database and the local Supabase database inspected during reconciliation
- active API and web code paths do not depend on them

### Revision group 3: decide the fate of Alembic-only objects absent from live

Decision needed per object:

- required and must be backfilled into live
- deprecated or superseded and should not be introduced into the reconciled schema

Current decision set pending:

- `document_chunks`
- `match_documents`
- `procurement_budget_items`
- `procurement_wbs_items`
- `procurement_bom_items`

### Revision group 4: normalize duplicate indexes and overlapping RLS policies

Goal:

- eliminate split-ownership artifacts without changing intended access behavior

Priority:

- duplicate `idx_*` / `ix_*` families
- overlapping tenant-isolation policies
- final fail-closed RLS rollout after bootstrap-safe auth path is proven

## Required Safety Rules

- never run `alembic upgrade head` against a drifted live DB without parity proof
- never use `alembic stamp head` as a substitute for reconciliation
- never leave a manual DB hotfix undocumented
- every emergency SQL repair must be assigned to an Alembic owner or explicitly classified as infra-only

## Current Status

Completed:

- drift matrix
- scratch Alembic rehearsal
- scratch SQL-runner rehearsal
- runtime bootstrap-function rollout
- runtime verification that bootstrap fallback warnings are absent in recent container logs

Still open:

- first Alembic reconciliation revision group
- migration verification updates for reconciled head
- staging-equivalent rollout
- final live stamp after parity proof
