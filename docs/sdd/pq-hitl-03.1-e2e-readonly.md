# SDD PQ-HITL-03.1 — E2E read-only revision evidence

**Scope:** Task PQ-HITL-03.1 / Issue #939 / MASTER #936
**Branch:** feat/pq-hitl-03.1-e2e-readonly
**Goal:** Demonstrate real end-to-end functioning of C2Pro with auth, backend PostgreSQL, UI. Read-only evidence navigation, no mutations.

## Context
- Existing E2E harness: `apps/web/playwright.config.ts`, `src/tests/e2e/global.setup.ts`, `auth.setup.ts`, `support/p0b-auth.ts`.
- Seed base: `apps/api/tests/e2e_seed/seed_wedge.py` provides deterministic tenant/user/project/document.
- Revision visibility fixture in unit tests expects:
  - Revision A: synthetic persisted clauses 9
  - Revision B: synthetic persisted clauses 7, status PROPOSED_PENDING_REVIEW
  - Current trusted visible clauses 0, reason CURRENT_TRUST_UNRESOLVED_NOT_ZERO_EXTRACTED
  - Do not promote proposed.

## Requirements
1. Authenticate with Clerk synthetic identity, verify organization and tenant.
2. Navigate to `/projects/{projectId}/evidence?documentId={documentId}`.
3. Revision selector shows two revisions.
4. Selecting Revision A shows `9 stored clauses in this selected revision` and no promotion to trusted.
5. Selecting Revision B shows `7 stored clauses in this selected revision` and status `Proposed — not trusted`.
6. UI shows `No trusted-current revision is available`.
7. Evidence panel `revision-specific-preview` loads revision-bound clause text. SOURCE_NAVIGATION_NOT_PROVEN: clause rows are plain text; no real PDF/blob navigation is asserted until authentic source routing exists.
8. Re-login stability: sign out/in via UI flow, re-assert same states.
9. Negative access: unknown project / wrong tenant project returns 403/404, no data leakage.

## Non-requirements
- No HITL approval, no write operations, no mutation of trust state.
- No production data modifications.
- No `clearCookies()` shortcuts; use real sign-out flow.

## Data model consistency
- Authority for trust is `DocumentArtifactORM` with `trust_state` and `lifecycle_status`; trust resolution performed by `current_revision_sql` resolver, not by columns on `DocumentRevisionORM`.
- `DocumentRevisionORM` holds revision metadata only; no `trust_state`/`current_basis` columns.
- `ClauseORM` is bound to `revision_id`, `tenant_id`, `project_id`, `document_id`; no `document_artifact_id` foreign key.
- `DocumentArtifactORM` ties to `document_revision_id`; artifact version is unique per document via UNIQUE(`document_id`,`artifact_version`).
- Tenant scoping enforced by RLS.

## Seed extension
Separate idempotent fixture `apps/api/tests/e2e_seed/seed_pq_hitl_03_1.py`:
- Reuse existing tenant `00000000-0000-0000-0000-00000000a113`, project `00000000-0000-0000-0000-00000000c303`, document `00000000-0000-0000-0000-00000000d401` from `seed_wedge`.
- No new project creation.
- Create two revisions for the document:
  - REV_A_ID: 9 clauses, artifact `trust_state=trusted`, `lifecycle_status=superseded`, `artifact_version=1`.
  - REV_B_ID: 7 clauses, artifact `trust_state=proposed`, `lifecycle_status=active`, `artifact_version=2`.
- `ClauseORM` linked to `revision_id` only.
- Trust resolution via artifact resolver yields UNRESOLVED, so `No trusted-current revision is available`.

## Test design
Playwright spec `apps/web/src/tests/e2e/pq-hitl-03.1-revision-readonly.spec.ts`:
- Uses `establishAuthenticatedSession` and `openProjects`.
- Assertions on `revision-history-readonly` and `revision-specific-preview`.
- Verifies texts:
  - `9 stored clauses in this selected revision`
  - `7 stored clauses in this selected revision`
  - `No trusted-current revision is available`
  - `Proposed — not trusted`

## CI reuse
- Workflow `.github/workflows/ci.yml` with `RUN_FULL_E2E` can execute Playwright against seeded DB.
- Secrets provided by GitHub; no local credential exposure.

## Risks
- Missing seed data leads to empty revision list.
- UI text changes break selectors; use data-testid.
