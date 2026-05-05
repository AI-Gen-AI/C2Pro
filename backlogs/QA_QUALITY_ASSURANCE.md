# Quality Assurance Backlog: Ruff Linting Debt Classification (TASK-REV-QUALITY-001)

## Executive Summary

**Status**: ✅ OK (Debt Classified)
**Date**: 2026-04-07
**Auditor**: Role_reviewer (Gemini CLI)

The audit of 82 remaining Ruff errors has been completed. The errors have been classified into 4 tiers to guide remediation efforts. Most errors are either obligatory `# noqa` for framework callbacks or unused arguments in newly refactored code that require cleanup.

## Status View

**Completed QA / Audit Tasks**

- `TASK-REV-QUALITY-001`
- `TASK-REV-QUALITY-002`
- `TASK-QA-080`
- `TASK-QA-082`
- `TASK-QA-098`
- `TASK-QA-099`
- `TASK-QA-102`
- `TASK-QA-103`
- `TASK-QA-077`
- `TASK-1480`

**Pending QA Tasks**

- `TASK-QA-100`
- `TASK-QA-101`

## TASK-QA-077 + TASK-1480: Test Stabilization Leftovers

**Status**: ✅ COMPLETE
**Date**: 2026-04-30 (PR #93)
**Executor**: OpenCode (Sonnet 4.6); MASTER-reviewed inline (Opus 4.7)

### Scope

- `TASK-QA-077`: stabilize remaining SLA boundary/relative-time tests after `TASK-BCK-044`
- `TASK-1480`: stabilize alert React tests by wrapping state-changing interactions in `act()` and adding targeted timeout headroom

### Changes

1. SLA flake prevention
   - Added `freezegun.freeze_time` to the remaining `SLACalculator.calculate()` tests that derived `created_at` from live `datetime.now(UTC)`
   - Kept the fix in `apps/api/tests/unit/alerts/domain/test_sla_calculator.py`; no production SLA code changed
2. Alert UI test stabilization
   - Wrapped state-changing `fireEvent` calls in React `act()` in `AlertReviewCenter.test.tsx` (including two new test cases added by PR #91 for status-filter and copy-to-clipboard, wrapped during MASTER's rebase conflict resolution)
   - Wrapped the keyboard undo interaction in `AlertUndoToast.test.tsx`
   - Raised targeted Vitest timeout/hook timeout to `10_000ms` for the alert test files

### Verification

- `python -m pytest tests/unit/alerts/domain/test_sla_calculator.py tests/unit/alerts/domain/test_sla_serialization.py --count=5`: `365 passed`
- `pnpm vitest run components/features/alerts/AlertReviewCenter.test.tsx components/features/alerts/AlertUndoToast.test.tsx components/features/alerts/alert-undo.test.ts`: `5` consecutive runs green, `0` React `act()` warnings
- `pnpm tsc --noEmit`: passed
- Lint clean post-merge

### Notes

- `pytest-repeat` was used only for local acceptance verification (5x repeat). It is not a CI dependency.
- `freezegun` was already in `apps/api/requirements.txt` since `TASK-BCK-044`.
- Pre-existing out-of-scope blockers documented for separate tickets: (a) `tests/golden/__init__.py` shadowing `src/golden` blocks broad `pytest -k`; (b) `axios@1.15.0` lockfile resolution prevents `pnpm install --offline`.

**Pending Cross-Role Remediation Inputs**

- `TASK-LINT-002`
- `TASK-LINT-003`

**Usage Note**

- Use this block to distinguish completed audit/verification work from open validation tasks.
- The detailed classification and ORM audit sections below remain the full QA evidence base.

## Error Classification Summary

| Tier | Category | Count (Approx) | Action |
| :--- | :--- | :---: | :--- |
| **TIER 1** | Obligatory `# noqa` | 15 | Add `# noqa` with specific codes. |
| **TIER 2** | Real Bugs / Unused Logic | 12 | Fix unused logic (mostly `tenant_id` omissions). |
| **TIER 3** | False Positives | 5 | Ignore or slightly refactor to clarify for linter. |
| **TIER 4** | Code Smells / Debt | 50+ | Incremental cleanup; mostly imports and formatting. |

## Tier 1 - Obligatory `# noqa` (Framework Callbacks)

These errors are caused by required method signatures from SQLAlchemy or FastAPI that don't use all arguments.

- **SQLAlchemy Events**:
    - `core/auth/models.py`: `generate_tenant_slug(mapper, ...)` - `mapper` is unused but required by signature.
    - `core/database.py`: `_receive_before_cursor_execute` and `_receive_after_cursor_execute` - `cursor`, `statement`, `parameters`, `context`, `executemany` are mostly unused but required.
    - `core/database.py`: `_initialize_tenant_guc` - `connection_record` is unused.

## Tier 2 - Real Bugs / Unused Logic (Action Required)

These are cases where arguments SHOULD be used or where logic is incomplete.

- **Tenant Isolation Omissions**:
    - `alerts/application/use_cases/create_alert_use_case.py`: `tenant_id` is passed but NOT used in the `Alert` domain entity or repository call. **CRITICAL: This is a potential tenant isolation bypass if the repository expects it.**
    - `analysis/adapters/ai/tools/risk_extraction_tool.py`: `tenant_id` unused.
    - `analysis/adapters/ai/tools/wbs_extraction_tool.py`: `tenant_id` unused.
    - `documents/application/list_project_documents_use_case.py`: `tenant_id` unused.
- **Logic Bugs**:
    - `alerts/application/use_cases/list_alerts_use_case.py`: `status_enum = AlertStatus(severity)` -> **BUG**: Uses `severity` variable to initialize `AlertStatus`. Should use `status`.
    - `alerts/application/ports/project_repository.py`: Undefined name `Project`. Missing import.

## Tier 3 - False Positives

- `analysis/domain/coherence_derivation.py`: `UP038` - Ruff suggests `int | float` for `isinstance`, but this is unsafe in some Python versions or complex contexts.
- `coherence/graph/nodes.py`: `F401` - Reports `PgvectorEmbeddingRepository` as unused, but it's likely used in a type hint or dynamic dispatch that Ruff is missing.

## Tier 4 - Code Smells (Design Debt)

- **Import Debt**: Massively unsorted imports in `alerts` and `core` modules (`I001`).
- **Unused Imports**: `F401` errors in multiple routers (`alerts/router.py`, `coherence/graph/nodes.py`).
- **Whitespace**: `W293` (blank line contains whitespace) in `core/auth/token_revocation.py` and `core/database.py`.
- **Simplification**: `SIM108` (Use ternary operator) in `core/database.py`.

## Remediation Plan

1. **Sprint 2 (Immediate)**: Fix Tier 2 bugs.
   - Correct `list_alerts_use_case.py` status/severity bug.
   - Add missing `Project` import.
   - Investigate why `tenant_id` is ignored in `CreateAlertUseCase`.
2. **Sprint 2 (Routine)**: Apply Tier 1 `# noqa`.
   - Add `# noqa: ARG001` to SQLAlchemy event listeners.
3. **Sprint 3**: Bulk fix Tier 4.
   - Run `ruff check --fix` for safe errors (imports, whitespace, ternary).

## Quality Assurance Backlog: ORM Models Audit (TASK-REV-QUALITY-002)

## Executive Summary

**Status**: ❌ FAIL (Gate 4 Traceability)
**Date**: 2026-04-07
**Auditor**: Role_reviewer (Gemini CLI)

The audit reveals significant gaps in Gate 4 traceability (1:1 mapping between migrations and ORM models). Multiple tables exist in the database (via migrations) that have no corresponding SQLAlchemy models, and critical models (AuditLog) are completely out of sync with their repositories and underlying schema.

## 1. Migration vs. ORM Inventory

| Table Name | Migration File | ORM Model Found? | File Path | Status |
| :--- | :--- | :---: | :--- | :---: |
| `clause_embeddings` | `20260401_0001` | ❌ No | - | **CRITICAL** |
| `document_chunks` | `20260315_0001` | ❌ No | - | **CRITICAL** |
| `stakeholder_alerts`| `20260319_0004` | ❌ No | - | **HIGH** |
| `bom_revisions` | `20260319_0004` | ❌ No | - | **HIGH** |
| `procurement_plan_snapshots` | `20260319_0004` | ❌ No | - | **HIGH** |
| `knowledge_graph_nodes` | `20260319_0005` | ❌ No | - | **MEDIUM** |
| `knowledge_graph_edges` | `20260319_0005` | ❌ No | - | **MEDIUM** |
| `checkpoints` | `20260320_0001` | ❌ No | - | **LOW** (LangGraph) |
| `audit_logs` | `20260319_0003` | ✅ Yes | `core/security/.../models.py` | **MISMATCH** |
| `ai_usage_logs` | `20260319_0003` | ✅ Yes | `core/ai/models.py` | **DRIFT** |

## 2. Detailed Findings

### ORM-M01: Audit Traceability Failure (CRITICAL)
- **Issue**: `SQLAlchemyAuditRepository` is hard-coded to expect fields (`actor_id`, `timestamp`, `event_hash`, `previous_hash`) that DO NOT EXIST in the `audit_logs` table (Migration `20260319_0003`) or the `AuditLogORM` model.
- **Impact**: The entire audit trail persistence is currently BROKEN and will fail with `AttributeError` or `ProgrammingError` on execution.
- **Remediation**: Re-sync the domain `AuditEvent`, the ORM model, and the database schema. Add hashing columns to the migration.

### ORM-M02: RAW SQL Dependency (HIGH)
- **Issue**: `PgvectorEmbeddingRepository` and `RagService` interact with `clause_embeddings` and `document_chunks` using string-templated raw SQL instead of SQLAlchemy models.
- **Impact**: Bypasses SQLAlchemy's type safety, unit-of-work, and makes migrations/refactoring harder. Gate 4 traceability is impossible without models.
- **Remediation**: Create `ClauseEmbeddingORM` and `DocumentChunkORM`. Refactor repositories to use these models.

### ORM-M03: Schema Drift in AI Usage (MEDIUM)
- **Issue**: `AIUsageLogORM` includes `trace_id` and `trace_url` columns which are NOT present in the database schema (Migration `20260319_0003`).
- **Impact**: `AIUsageLog` creation will fail if these fields are populated.
- **Remediation**: Add an Alembic migration to add these columns to `ai_usage_logs`.

## 3. Remediation Plan

1. **Sprint 1 (Immediate)**: Fix `AuditLog` mismatch. This is a core security requirement.
2. **Sprint 1 (Immediate)**: Add `trace_id` columns to `ai_usage_logs` to stop schema drift.
3. **Sprint 2**: Create missing ORM models for RAG (`document_chunks`) and Coherence (`clause_embeddings`).
4. **Sprint 3**: Consolidate remaining support tables (Knowledge Graph, Procurement Snapshots) into ORM models.

## Success Criteria Verification
- [ ] 100% 1:1 mapping between `op.create_table` and SQLAlchemy classes.
- [ ] `SQLAlchemyAuditRepository` passes integration tests with real DB schema.
- [ ] No raw SQL `INSERT`/`SELECT` in repositories where ORM models could be used.

## TASK-QA-102: Pgvector Test Bootstrap Prerequisite

**Status**: ✅ COMPLETE
**Date**: 2026-04-08
**Discovered During**: Retry verification of `apps/api/tests/verification/test_gate2_identity.py`

### Failure Signature

- `sqlalchemy.exc.ProgrammingError: ... type "vector" does not exist`
- Raised during `Base.metadata.create_all()` while creating `clause_embeddings`
- First visible in Gate 2 identity verification, but this affects any DB-backed suite that initializes metadata against PostgreSQL without the pgvector extension

### Impact

- Blocks `apps/api/tests/verification/test_gate2_identity.py` before request-level auth assertions run
- Masks actual Gate 2 auth results behind infrastructure/bootstrap failure
- Risks similar failures in coherence, retrieval, and RAG-backed verification suites

### Required Fix

1. Ensure the PostgreSQL test bootstrap enables pgvector before `Base.metadata.create_all()`
2. Verify the Docker test database/image exposes the `vector` extension
3. Add a narrow executable verification test that fails fast when pgvector is unavailable

### Evidence

- Retry on 2026-04-08:
  - `apps/api/tests/auth/test_token_revocation.py`: `7 passed`
  - Initial `apps/api/tests/verification/test_gate2_identity.py`: `1 passed, 10 errors`
  - Final `apps/api/tests/verification/test_gate2_identity.py`: `11 passed`
  - Shared bootstrap follow-up fixes completed in the same change set:
    - centralized `CREATE EXTENSION IF NOT EXISTS vector`
    - removed duplicate `DocumentChunkORM` index declarations
    - imported `DLQFailedTask` for mapper registration with `DocumentORM`

## TASK-QA-098: E2E Complete User Journey Validation

**Status**: ✅ VALIDATION COMPLETE / ❌ ACCEPTANCE FAILED
**Date**: 2026-04-08
**Executor**: QA Lead (Codex CLI)
**Suite**: `TS-E2E-FLW-JRN-001`

### Scope

- Validate `apps/api/tests/e2e/flows/test_complete_user_journey_e2e.py`
- Acceptance targets from backlog:
  - coverage `>=85%` across `auth`, `documents`, `analysis`, `coherence`, `alerts`
  - runtime `<5min`
  - no flaky behavior across `3` runs

### Validation Results

- Coverage measurement run:
  - Command targeted `src.core.auth`, `src.documents`, `src.analysis`, `src.coherence`, `src.alerts`
  - Result: approximately `35%` total coverage
  - Runtime: `252.2s`
  - Acceptance status: **FAIL**
- Repeatability runs:
  - Run 1: `3 passed, 2 skipped` in `137.8s`
  - Run 2: `3 passed, 2 skipped` in `139.6s`
  - Run 3: `3 passed, 2 skipped` in `137.0s`
  - Acceptance status: runtime **PASS**, flake check **PASS**

### Environment Blockers Observed

- Document upload scenario is skipped locally because the upload storage path is not writable
- Decision Intelligence execution scenario is skipped locally because real runtime ports are not wired

### Defects Found And Fixed During Validation

1. Document persistence timestamp mismatch
   - `SqlAlchemyDocumentRepository` wrote aware UTC datetimes to naive PostgreSQL `TIMESTAMP` columns
   - Added regression in `apps/api/tests/unit/adapters/documents/test_document_repository.py`
   - Fixed normalization in `apps/api/src/documents/adapters/persistence/sqlalchemy_document_repository.py`
2. Alerts review persistence timestamp mismatch
   - `SqlAlchemyAlertRepository.save()` wrote aware UTC datetimes to naive PostgreSQL `TIMESTAMP` columns
   - Added regression in `apps/api/tests/unit/alerts/test_alert_repository.py`
   - Fixed normalization in `apps/api/src/alerts/adapters/persistence/alert_repository.py`
3. Missing alert lifecycle history on create
   - Alert create flow did not record the initial `created` history entry expected by the E2E traceability contract
   - Added regression in `apps/api/tests/unit/alerts/application/test_create_alert_use_case.py`
   - Updated `CreateAlertUseCase` and alerts router to propagate `user_id` and append the `created` event
4. Stale alert list contract in E2E suite
   - Updated `apps/api/tests/e2e/flows/test_complete_user_journey_e2e.py` to use `/api/v1/alerts/projects/{project_id}?status_filter=open`

### Conclusion

- `TASK-QA-098` is complete as a validation/reporting task
- The validated suite is now deterministic in the current local runtime
- Acceptance criteria are still **not met** because:
  - measured coverage is far below the required `>=85%`
  - `2/5` journey checks remain environment-skipped rather than executable

## TASK-QA-099: E2E Complete User Journey Code Review

## TASK-QA-103: Modules Suite Stabilization

**Status**: ✅ COMPLETE
**Date**: 2026-04-09
**Executor**: QA Lead (Codex CLI)

### Scope

- Restore `apps/api/tests/modules` to green in the local GitHub-like runtime
- Fix real runtime regressions uncovered during the sweep
- Reconcile stale contract tests that no longer matched the live application surface

### Key Runtime Fixes

1. HITL resume workflow stabilization
   - Replaced real LangGraph checkpoint/runtime dependencies in `test_hitl_resume_endpoint.py` with deterministic dependency overrides while preserving the real route and repository path
   - Fixed `ResumeWorkflowUseCase` review metadata handling (`checkpoint_id`, `thread_id`, `review_decision`)
   - Normalized naive UTC persistence in `modules/hitl/adapters/persistence/repository.py`
2. Procurement and project budget correctness
   - Fixed WBS tree root filtering in `procurement/adapters/persistence/wbs_repository.py` by using `IS NULL` instead of Python `is None`
   - Fixed Decimal arithmetic in `projects/adapters/http/router.py` budget alias
3. Test asset and contract reconciliation
   - Updated stale ingestion, reupload, fallback, budget, WBS, and stakeholder contract tests to the current codebase layout and route behavior
   - Corrected legacy path assumptions (`src/modules/...`) and auth setup drift in isolated contract-test apps

### Verification

- Targeted reruns completed during stabilization for:
  - HITL resume integration
  - LLM fallback integration
  - WBS repository integration
  - budget API contract coverage
  - stakeholders ports contract coverage
  - WBS API contract coverage
- Final suite result:
  - `python -m pytest apps/api/tests/modules --maxfail=1 --tb=short`
  - `1450 passed, 2 skipped`

### Remaining Non-Blocking Notes

- The two skipped DLQ module tests are still explicit legacy placeholders for admin endpoints not implemented in-app
- JWT tests emit `InsecureKeyLengthWarning` in test fixtures only; this did not block the suite

**Status**: ✅ REVIEW COMPLETE
**Date**: 2026-04-08
**Reviewer**: QA Lead (Codex CLI)
**Target**: `apps/api/tests/e2e/flows/test_complete_user_journey_e2e.py`
**Suite**: `TS-E2E-FLW-JRN-001`

### Findings

1. **HIGH**: The coherence evaluation assertion does not prove the six-category contract the test claims to validate.
   - Location: `apps/api/tests/e2e/flows/test_complete_user_journey_e2e.py:222`
   - The test docstring says it validates "coherence v2 output with category breakdown" across six categories, but the actual assertion only requires `len(categories) >= 1` and that categories are a subset of a broad allowlist.
   - This means the test still passes if `/api/v1/coherence/evaluate` regresses to returning only a single category, which would violate the suite contract while remaining green.
   - Required fix: assert the expected normalized six-category set for the evaluated payload, or explicitly split the endpoint contract if dashboard-only coverage is intended.

2. **HIGH**: The Decision Intelligence test is not part of the end-to-end journey it claims to cover.
   - Location: `apps/api/tests/e2e/flows/test_complete_user_journey_e2e.py:137`
   - `test_002_complete_journey_langgraph_decision_execution_contract` sends a random `project_id` (`uuid4()`) and synthetic base64 bytes without creating a project, uploading a document, or linking execution to prior journey state.
   - As written, it only checks a standalone HTTP contract and cannot catch regressions in project scoping, tenant propagation, or upload-to-analysis integration.
   - Required fix: create a real project and use artifacts from the upload/bootstrap flow, or rename/scope the test as a contract-only check and move true E2E coverage into a runtime-backed scenario.

3. **MEDIUM**: Critical-path tests are normalized to `skip`, which makes the suite look healthy while key journey slices are never executable in the default runtime.
   - Location: `apps/api/tests/e2e/flows/test_complete_user_journey_e2e.py:19`
   - Location: `apps/api/tests/e2e/flows/test_complete_user_journey_e2e.py:44`
   - The helpers convert infrastructure/runtime failures into skips for both Decision Intelligence execution and document upload.
   - This is pragmatic for local development, but for a suite named "complete user journey" it weakens signal: the suite can report green with `3 passed, 2 skipped` while the upload and analysis stages never run.
   - Required fix: gate these tests behind an explicit runtime marker or environment flag and treat missing prerequisites as a failed CI contract for the environments that are supposed to provide them.

### Residual Risk

- The suite is now deterministic in the current local runtime, but it still overstates functional coverage.
- `TASK-QA-098` already proved acceptance failure on measured coverage (`~35%`) and environment skips; this review explains why the code structure allows that gap to persist.

---

## EPIC-QA-CONTRACT-COVERAGE — Plan

**Status**: 📋 Planned
**Date**: 2026-05-03
**Planner**: MASTER (Opus 4.7) — W7 inline planning deliverable
**Replaces (31 stubs, no specs)**: TASK-QA-028, TASK-QA-034, TASK-QA-050..064, TASK-QA-069, TASK-QA-070, TASK-QA-084..095
**Blocks**: EPIC-COVERAGE-GATES
**Blocked by**: EPIC-DDD-MIGRATION
**Critical-path-to-launch?**: No (Tier 3 quality debt)

### Problem Statement

The legacy 31 QA stub IDs have no specs anywhere — they appear only in the master backlog and the 2026-04-21 audit session, never in any backlog or planning file. Today's contract coverage is fragmented: 1 global suite (`tests/contract/test_api_contracts.py`, 454 LOC) plus ~15 ad-hoc per-module `*_contract.py` files with mixed conventions (port contracts, router-dependency contracts, route-shape contracts, all sharing a filename suffix). No schema-driven contract tool is installed (no `schemathesis`, no `pact-python`). OpenAPI is generated by `apps/api/scripts/generate_openapi.py` (42 paths / 56 operations) but no CI job validates the live app against it. `apps/web/openapi.json` is a stub. There is no aggregated quality-gate report. `tests/conftest.py` is 1279 LOC.

### Scope: Three Tracks, One Epic

**Track A — API contract coverage via Schemathesis** (replaces all "API contract test stub" QA tasks).

- Tooling: `schemathesis` (Hypothesis-based, OpenAPI-driven request fuzzing).
- Targets: 42 paths / 56 operations across 19 routers. Verifies status codes match `responses:`, body shapes match `components/schemas`, error envelope is uniform (already enforced by `APIContractMiddleware`).
- Auth: Schemathesis hooks mint JWTs via existing `tests/conftest.py` helpers; route-level auth stays real.
- Multi-tenant: hook injects `X-Tenant-ID` header from a test-tenant fixture.
- Mocked boundaries: Claude (`C2PRO_AI_MOCK=1`), Clerk JWKS (cached fixture), R2 (LocalStack-style), Redis (real local).
- Stateful tests: opt-in for routers with non-trivial state (alerts, hitl, projects, documents).
- Output: per-router JUnit XML + aggregated `contract-coverage.json`.

**Track B — Wireframe-traceability TCs**.

- Targets: 6 wireframes in `docs/wireframes/0*.md` (dashboard, projects, evidence-viewer, alerts, stakeholders, RACI) + CE-S2-010 evidence-viewer dossier.
- Tooling: existing Vitest + RTL + MSW.
- Convention: each test file declares `WIREFRAME_REF = "docs/wireframes/04-alerts.md#section"`; tracker script `scripts/wireframe_coverage.ts` walks tests and emits `wireframe-coverage.json`.
- CI fails if any wireframe in `docs/wireframes/0*.md` has zero covering test.

**Track C — Quality-gate report pipeline**.

- Composite GH Action `.github/actions/quality-report/action.yml` + `scripts/quality_report.py` (jinja2 markdown render).
- Inputs: `contract-coverage.json`, `wireframe-coverage.json`, existing `coverage.xml`, existing per-gate JUnit XMLs.
- Outputs: PR-comment table (delta vs base), `quality-report.md` artefact (90-day retention), CI gate (contract-coverage drop > 2% on `main` PR fails build).

### Cross-Cutting: DB Bootstrap Migration (folded into Track A)

Move `apps/api/scripts/bootstrap_test_infra.py` invocation into a `tests/_bootstrap.py` auto-imported by `conftest.py`. Extract the 5 autouse SDK-isolator fixtures into `tests/fixtures/sdk_isolators.py`. Target: `conftest.py` ≤ 700 LOC.

### Subtask Decomposition (13 subtasks, ~60h)

**Track A — Schemathesis (Backend)**

- [x] `TASK-QA-200` — Add `schemathesis` to `requirements-sprint1.txt`; create `tests/contract/schemathesis/conftest.py` with auth/tenant hooks; smoke-test `/health/live`. Replaces QA-028, QA-050. Est 3h. Owner: Sonnet. @2026-05-04 branch `qa-coverage/track-a-schemathesis`.
- [x] `TASK-QA-201` — Schemathesis suite for `auth`, `projects`, `documents` routers + JUnit + coverage JSON. Replaces QA-051..053. Est 5h. Owner: Sonnet. @2026-05-04 same branch.
- [x] `TASK-QA-202` — Schemathesis suite for `analysis`, `coherence`, `alerts`, `hitl` routers (stateful where applicable). Replaces QA-054..057. Est 6h. Owner: Sonnet. @2026-05-04 same branch.
- [ ] `TASK-QA-203` — Schemathesis suite for `wbs`, `procurement`, `stakeholders`, `decision_intelligence`, `bulk_operations` routers. Replaces QA-058..062. Est 6h. Owner: Codex.
- [ ] `TASK-QA-204` — Schemathesis suite for `mcp`, `ai_feedback`, `dlq`, `frontend_support`, `observability`, `tenants`, `admin` routers. Replaces QA-063..064, QA-069..070. Est 5h. Owner: Codex.
- [x] `TASK-QA-205` — OpenAPI drift gate: regenerate YAML in CI, fail PR if `git diff` non-empty unless commit message contains `[openapi]`. Replaces QA-034. Est 2h. Owner: Sonnet. @2026-05-04 `.github/workflows/openapi-drift.yml`.
- [x] `TASK-QA-206` — DB bootstrap migration: refactor `conftest.py` (463 LOC ≤700), extract fixtures to `tests/fixtures/sdk_isolators.py`, `tests/_bootstrap.py`, `tests/fixtures/auth.py`; documented in `tests/README.md`. Cross-cutting. Est 4h. Owner: Sonnet. @2026-05-04 same branch.

**Track B — Wireframe TCs (Frontend)**

- [x] `TASK-QA-207` — Wireframe TC convention + `scripts/wireframe_coverage.ts` tracker + CI hook. Replaces QA-084. Est 3h. Owner: Sonnet (MASTER). @2026-05-05 branch `qa-coverage/track-b-wireframes`: `apps/web/scripts/wireframe_coverage.ts` + `.github/workflows/wireframe-coverage.yml`.
- [x] `TASK-QA-208` — Wireframe TCs for `01-dashboard.md` + `02-projects.md`. Replaces QA-085, QA-086. Est 4h. Owner: Sonnet (MASTER). @2026-05-05 `src/tests/wireframes/WF-01-dashboard.wireframe.test.tsx` + `WF-02-projects.wireframe.test.tsx`.
- [x] `TASK-QA-209` — Wireframe TCs for `03-evidence-viewer.md` + CE-S2-010 dossier (PDF viewer, highlights, keyboard nav). Replaces QA-087, QA-088. Est 6h. Owner: Sonnet (MASTER). @2026-05-05 `src/tests/wireframes/WF-03-evidence-viewer.wireframe.test.tsx`.
- [x] `TASK-QA-210` — Wireframe TCs for `04-alerts.md`. Replaces QA-089, QA-090. Est 4h. Owner: Sonnet (MASTER). @2026-05-05 `src/tests/wireframes/WF-04-alerts.wireframe.test.tsx`.
- [x] `TASK-QA-211` — Wireframe TCs for `05-stakeholders.md` + `06-raci-matrix.md`. Replaces QA-091..093. Est 5h. Owner: Sonnet (MASTER). @2026-05-05 `src/tests/wireframes/WF-05-stakeholders.wireframe.test.tsx` + `WF-06-raci-matrix.wireframe.test.tsx`.

**Track C — Report Pipeline (Infra)**

- [ ] `TASK-QA-212` — `.github/actions/quality-report/action.yml` + `scripts/quality_report.py` markdown render. Replaces QA-094. Est 4h. Owner: Codex.
- [ ] `TASK-QA-213` — Wire report into `tests.yml`, `frontend-ci.yml`, `qa-swarm.yml`; PR comment via `marocchino/sticky-pull-request-comment`. Replaces QA-095. Est 3h. Owner: Codex.

### Dispatch Slate (suggested)

| Branch | Tracks | Agent | Tasks | ETA |
|---|---|---|---|---|
| `qa-coverage/track-a-schemathesis` | A | Sonnet 4.6 | QA-200..206 | ~31h |
| `qa-coverage/track-b-wireframes` | B | OpenCode (Sonnet 4.6) | QA-207..211 | ~22h |
| `qa-coverage/track-c-report` | C | Codex | QA-212..213 | ~7h |

QA-200 is the unblocker. B/C start in parallel; C's acceptance test runs only after A ships its first router suite.

### Acceptance Criteria (Epic-level)

1. `schemathesis run docs/api/openapi.yaml --base-url=http://localhost:8000` exits 0 against a freshly bootstrapped local API.
2. `contract-coverage.json` reports ≥ 95% of OpenAPI paths covered.
3. `wireframe-coverage.json` reports 100% of `docs/wireframes/0*.md` files have at least one covering test.
4. PR-comment quality report appears on a fresh PR.
5. `make test-api` runtime increase ≤ 90 s vs baseline.
6. `tests/conftest.py` ≤ 700 LOC; SDK isolators live in `tests/fixtures/sdk_isolators.py`.
7. CI gate fails on (a) OpenAPI drift, (b) wireframe-coverage drop, (c) contract-coverage drop > 2%.

### Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Schemathesis fuzz finds genuine bugs in 19 routers — scope creep | Triage rule: contract violation = Track-A fix; real bug = new BCK-* ticket. |
| `tests/conftest.py` refactor breaks suites | TASK-QA-206 lands last in Track A behind a green Schemathesis suite; single-revert rollback. |
| Wireframe docs ahead/behind product | Tracker reports both directions; stale wireframes get `WONT-COVER`, not a test. |
| `schemathesis` regresses `pip install` time | Pin version; documented. |
| OpenAPI drift gate too strict | Escape hatch: commit message containing `[openapi]` skips. |

### Out-of-Scope (WONT-DO)

- Pact-style consumer-driven contracts (single consumer + provider in same monorepo; Schemathesis covers provider, MSW covers consumer).
- Visual-regression for wireframes (separate Percy/Chromatic epic).
- E2E Playwright wireframe tests (Track B is component-level only).
- Coverage % per module ≥ 70% (that's EPIC-COVERAGE-GATES, downstream).
