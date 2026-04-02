# C2Pro Master Backlog

> **Canonical Project Task Register**
> **Version:** 2.0.0
> **Last Updated:** 2026-03-29
> **Owner:** CIO / Engineering
> **Authority:** This is the single source of truth for all open work, release blockers, and follow-up tasks across C2Pro.

---

## Operating Rule

- Every active execution task must exist in this file with a stable ID and checkbox state.
- If an agent finds work that is missing here, the agent must add it before or together with the implementation.
- When a task is completed, the agent must mark it complete here in the same change set whenever feasible.
- Supporting documents may contain detail, evidence, implementation notes, or checklists, but they do not own execution status.
- If another document conflicts with this backlog on open or closed work, this backlog wins.

## Recovery Note

- This version restores the missing task inventory that existed in the 2026-03-28 unified roadmap.
- The backlog now keeps planner-grade execution items and source traceability.
- Non-actionable registry noise was intentionally not restored:
  vendored licenses, virtualenv package READMEs, cache metadata, and purely historical archive rows.
- Procedural one-off prompts such as "create branch", "push remote", or "ask the user what feature" were also excluded unless they represent real delivery gates.

## Current Platform Baseline

- Monorepo surfaces: `apps/api` and `apps/web`
- Delivery posture: API-first multi-tenant SaaS platform
- Architecture baseline: modular monolith with hexagonal boundaries
- Security baseline: `tenant_id` filtering mandatory, `clauses` is source of truth
- Current release posture: pending final production gates, release evidence, and remaining hardening work

Primary architecture and delivery references:

- `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_1.md`
- `docs/architecture/decisions/006-post-reorganization-architecture.md`
- `docs/testing/PHASE4_TDD_IMPLEMENTATION_ROADMAP.md`
- `docs/testing/C2PRO_TEST_SUITES_INDEX_v1.1.md`

## Task Lifecycle

| State | Meaning |
|-------|---------|
| `[ ]` | Open and not yet completed |
| `[-]` | In progress or partially complete |
| `[x]` | Completed and verified or formally closed |

Priority levels:

- `P0`: Release-blocking or security-critical
- `P1`: Short-term delivery priority
- `P2`: Important but not release-blocking
- `P3`: Deferred, exploratory, or strategic follow-up

Normalization rules:

- When the same work appears in `MASTER_AUDIT_PLAN.md` and a more specific delivery source, the specific delivery source owns execution and the audit plan is treated as a reference.
- When a source contains summary quality gates and another source contains the granular executable checks, the granular tasks own execution.
- Release snapshot sections reference blocker IDs but do not create second ownership records.

---

## 1. Documentation Task Sources

This section replaces the oversized document registry with the current sources that still generate active work.

| Source File | Area | Status | Active Task Signal |
|-------------|------|--------|--------------------|
| `MASTER_AUDIT_PLAN.md` | Cross-cutting | Active | Remaining audit, security, and testing actions |
| `FRONTEND_TESTING_PLAN.md` | Frontend / QA | Active | Frontend coverage and production test suite work |
| `README.md` | Governance / Security | Active | Release/security gates still referenced |
| `SECURITY_REMEDIATION_CHECKLIST.md` | Security | Active | Hardening and audit follow-up |
| `docs/CASE_CREATION_GUIDELINES.md` | AI / Data Quality | Active | Validation checklist converted into tracked tasks |
| `docs/COVERAGE_IMPROVEMENT_PLAN.md` | Testing | Active | Coverage and regression checks |
| `docs/RELEASE_CRITERIA.md` | Release | Active | Final candidate signoff work |
| `docs/audits/STRATEGIC_ARCHITECTURE_AUDIT_2026-02-19.md` | Backend / Frontend | Active | Architecture remediation items |
| `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` | AI / Coherence | Active | Scoring and orchestration delivery items |
| `docs/internal/RELEASE_SIGNOFF_POLICY.md` | Security / Release | Active | Release certification evidence |
| `docs/planning/FOLLOWUP_AUTH_BOOTSTRAP_FALLBACK_REMOVAL.md` | Security / Auth | Active | Auth fallback removal and verification |
| `docs/planning/PRODUCTION_READINESS_GATE_2026-03-19.md` | Release | Active | Production gate still open |
| `docs/planning/ROADMAP_v2.4.0.md` | Security / Release | Active | Vulnerability and readiness work |
| `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` | Frontend / Security | Active | Production Clerk rollout tasks |
| `docs/runbooks/INSTRUCCIONES_TESTS.md` | Testing | Active | Infra and execution prerequisites |
| `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` | Testing | Active | Test execution and quality gates |
| `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` | Testing | Active | Contract and integration suites |
| `docs/testing/TEST_INVENTORY_2026-03-02.md` | Testing | Active | Inventory close-out evidence |
| `docs/wireframes/01-dashboard.md` | Frontend | Active | Dashboard enhancements |
| `docs/wireframes/02-projects.md` | Frontend | Active | Projects view enhancements |
| `docs/wireframes/03-evidence-viewer.md` | Frontend | Active | Evidence viewer enhancements |
| `docs/wireframes/04-alerts.md` | Frontend | Active | Alert center enhancements |
| `docs/wireframes/06-raci-matrix.md` | Frontend | Active | RACI matrix enhancements |
| `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` | Frontend | Active | UX remediation backlog |
| `evidence/releases/2026-03-24-rc1/signoff.md` | Release / Security | Active | Release artifact completion |

---

## 2. Active Development Backlog

### 2.1 Backend

| Status | Priority | ID | Dependency | Task | Source |
|--------|----------|----|------------|------|--------|
| [x] | P1 | `TASK-120` | Backend | Dependencies injected via FastAPI or service constructors `[x] Implemented (Unit Tests & Domain Logic)` | `.claude/skills/c2pro-doc-analyzer/SKILL.md` |
| [x] | P1 | `TASK-1057` | `TASK-1422` | Retire legacy `app/dashboard/` only after `app/(app)/` reaches parity and live `/dashboard` dependencies plus active local edits are safely migrated `[x] Implemented (Legacy Tree Retired)` | `docs/audits/STRATEGIC_ARCHITECTURE_AUDIT_2026-02-19.md` |
| [x] | P1 | `TASK-1069` | Backend | Remove `_Default*Service` implementations that return dummy data `[x] Implemented (Unit Tests & Domain Logic)` | `docs/audits/STRATEGIC_ARCHITECTURE_AUDIT_2026-02-19.md` |
| [x] | P1 | `TASK-1078` | Backend | LangGraph nodes must wrap existing use cases without logic duplication `[x] Implemented (Unit Tests & Domain Logic)` | `docs/audits/STRATEGIC_ARCHITECTURE_AUDIT_2026-02-19.md` |
| [x] | P1 | `TASK-1080` | Backend | HITL must have a real service implementation `[x] Implemented (Unit Tests & Domain Logic)` | `docs/audits/STRATEGIC_ARCHITECTURE_AUDIT_2026-02-19.md` |
| [x] | P1 | `TASK-1361` | Backend | Verifier must produce JSON suitable for dashboarding `[x] Implemented (Unit Tests & Domain Logic)` | `openspec/changes/openspec-bootstrap-v2/design.md` |
| [x] | P1 | `TASK-1415` | Backend | Fix Alembic WBS uniqueness migration so `upgrade head` drops legacy self-referencing FK dependencies before removing `procurement_wbs_items_code_key` `[x] Implemented (Unit Tests & Domain Logic)` | `apps/api/alembic/versions/20260321_0001_fix_wbs_code_uniqueness_scope.py` |
| [x] | P1 | `TASK-1458` | Backend | Repair the clause-embeddings Alembic revision chain so `alembic upgrade head` resolves to a single linear head again after the 2026-04-01 migration landed on the wrong ancestor `[x] Implemented (Regression Test + Revision Chain Fix)` | `apps/api/alembic/versions/20260401_0001_add_clause_embeddings.py`; `apps/api/tests/modules/hitl/adapters/test_clause_embeddings_migration.py` |
| [x] | P2 | `TASK-1421` | Backend | Remove remaining internal constructor fallback wiring in coherence and graph execution paths after HTTP DI cleanup `[x] Implemented (Explicit Builders + Graph Providers)` | `docs/audits/STRATEGIC_ARCHITECTURE_AUDIT_2026-02-19.md` |
| [x] | P1 | `TASK-1422` | Backend | Build a controlled `app/dashboard/` to `app/(app)/` migration plan that preserves current `/dashboard` behavior and carries forward active local dashboard edits before any deletion `[x] Implemented (Migration Plan)` | `TASK-1057` repo-state verification 2026-04-01 |
| [x] | P1 | `TASK-1423` | `TASK-1422` | Implement canonical route parity under `app/(app)/` for dashboard landing, project budget, and project WBS before touching legacy `app/dashboard/` `[x] Implemented (Route Parity)` | `docs/planning/DASHBOARD_ROUTE_MIGRATION_PLAN_2026-04-01.md` |
| [x] | P1 | `TASK-1424` | `TASK-1423` | Preserve `/dashboard` compatibility and migrate navigation plus route-dependent tests incrementally until legacy route consumers are covered `[x] Implemented (Navigation Compatibility Slice)` | `docs/planning/DASHBOARD_ROUTE_MIGRATION_PLAN_2026-04-01.md` |
| [x] | P1 | `TASK-1425` | `TASK-1426`, `TASK-1427` | Retire `app/dashboard/` only after parity, compatibility coverage, and active local dashboard edits are safely carried forward `[x] Implemented (Redirects + Tree Removal)` | `docs/planning/DASHBOARD_ROUTE_MIGRATION_PLAN_2026-04-01.md` |
| [x] | P1 | `TASK-1426` | `TASK-1424` | Migrate remaining Playwright and integration deep-link specs off hardcoded `/dashboard/...` paths while preserving explicit legacy compatibility assertions during the transition `[x] Implemented (Test Migration)` | `docs/planning/DASHBOARD_ROUTE_MIGRATION_PLAN_2026-04-01.md` |
| [x] | P1 | `TASK-1427` | `TASK-1423` | Replace temporary canonical `app/(app)` route re-exports with standalone implementations so deleting `app/dashboard/` cannot break canonical dashboard, budget, or WBS pages `[x] Implemented (Standalone Canonical Routes)` | `docs/planning/DASHBOARD_ROUTE_MIGRATION_PLAN_2026-04-01.md` |
| [x] | P2 | `TASK-1358` | Backend | Support follow-up change creation without path ambiguity `[x] Implemented (OpenSpec Scaffold CLI)` | `openspec/changes/openspec-bootstrap/proposal.md` |
| [ ] | P1 | `AUTH-FOLLOWUP-01` | Security | Remove dormant ORM fallback paths from auth bootstrap helpers after observation window | `docs/planning/FOLLOWUP_AUTH_BOOTSTRAP_FALLBACK_REMOVAL.md` |
| [x] | P1 | `AUTH-FOLLOWUP-02` | Security | Prevent Clerk personal-tenant fallback collisions and auto-select single-org sessions so org-scoped auth bootstrap works without manual tenant edits `[x] Implemented (Unit Tests & Domain Logic)` | `docs/planning/FOLLOWUP_AUTH_BOOTSTRAP_FALLBACK_REMOVAL.md` |
| [ ] | P1 | `DOC-ADAPTER-QUAL-01` | Testing | Reconcile remaining document adapter contract quality issues | `docs/TEST_COVERAGE_ISSUES_REPORT.md` |

### 2.2 Frontend

| Status | Priority | ID | Dependency | Task | Source |
|--------|----------|----|------------|------|--------|
| [x] | P0 | `TASK-008` | Env Setup | Setup frontend test infrastructure with Vitest, Playwright, and MSW | `FRONTEND_TESTING_PLAN.md` |
| [x] | P3 | `TASK-009` | Env Setup | Create test utilities and helpers | `FRONTEND_TESTING_PLAN.md` |
| [x] | P0 | `TASK-011` | Env Setup | Write authentication tests | `FRONTEND_TESTING_PLAN.md` |
| [x] | P0 | `TASK-012` | Env Setup | Deliver auth flow fully tested | `FRONTEND_TESTING_PLAN.md` |
| [ ] | P0 | `TASK-1174` | Security Sign-off | Clerk project configured in production environment | `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` |
| [x] | P0 | `TASK-1337` | None | Alerts Center: add Root Cause field for Critical and High severity | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` |
| [x] | P1 | `TASK-013` | Env Setup | Projects CRUD tests | `FRONTEND_TESTING_PLAN.md` |
| [x] | P1 | `TASK-014` | Backend API | Dashboard tests | `FRONTEND_TESTING_PLAN.md` |
| [x] | P1 | `TASK-051` | None | Implement remaining frontend-facing API endpoints `[x] Implemented (Unit Tests & Domain Logic)` | `QUICK_SESSION_SUMMARY.md` |
| [x] | P1 | `TASK-1227` | Backend API | Custom dashboard layouts | `docs/wireframes/01-dashboard.md` |
| [x] | P1 | `TASK-1230` | Backend API | Dashboard templates | `docs/wireframes/01-dashboard.md` |
| [x] | P1 | `TASK-1238` | None | Batch upload and import projects | `docs/wireframes/02-projects.md` |
| [x] | P1 | `TASK-1258` | Backend API | Alert analytics dashboard | `docs/wireframes/04-alerts.md` |
| [x] | P1 | `TASK-1339` | Backend API | Dashboard: add drill-down sheet for Coherence Score | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` |
| [x] | P1 | `TASK-1347` | None | Connect all views to real backend API | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md`; normalized owner for prior `TASK-037` |
| [x] | P2 | `TASK-017` | Backend API | UI component library tests `[x] Implemented (Unit Tests & Domain Logic)` | `FRONTEND_TESTING_PLAN.md` |
| [x] | P2 | `TASK-1229` | None | Export dashboard to PDF and Excel | `docs/wireframes/01-dashboard.md` |
| [x] | P2 | `TASK-1237` | None | Export projects to PDF, Excel, and JSON | `docs/wireframes/02-projects.md` |
| [x] | P2 | `TASK-1239` | None | Project templates | `docs/wireframes/02-projects.md` |
| [x] | P2 | `TASK-1242` | None | Interactive graph visualization with D3.js | `docs/wireframes/03-evidence-viewer.md` |
| [x] | P2 | `TASK-1247` | None | Export evidence view to multiple formats | `docs/wireframes/03-evidence-viewer.md` |
| [x] | P2 | `TASK-1249` | None | Evidence templates | `docs/wireframes/03-evidence-viewer.md` |
| [x] | P2 | `TASK-1254` | None | Alert templates | `docs/wireframes/04-alerts.md` |
| [x] | P2 | `TASK-1272` | None | RACI templates by project type | `docs/wireframes/06-raci-matrix.md` |
| [x] | P2 | `TASK-1344` | None | Stakeholder Map: implement drag and drop with `@dnd-kit` | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md`; normalized owner for prior `TASK-036` |
| [x] | P3 | `TASK-015` | Env Setup | Navigation tests | `FRONTEND_TESTING_PLAN.md` |
| [x] | P3 | `TASK-016` | Env Setup | Deliver core app functionality tested | `FRONTEND_TESTING_PLAN.md` |
| [x] | P3 | `TASK-018` | Env Setup | Form validation tests | `FRONTEND_TESTING_PLAN.md` |
| [x] | P3 | `TASK-019` | Env Setup | Document management tests | `FRONTEND_TESTING_PLAN.md` |
| [x] | P3 | `TASK-020` | None | Reach 80 percent frontend coverage | `FRONTEND_TESTING_PLAN.md` |
| [x] | P3 | `TASK-021` | Backend API | Visual regression tests across core pages | [x] Implemented (dedicated Playwright `visual-regression` project, `core-pages.visual.spec.ts`, and five checked-in desktop baselines for demo documents/alerts/stakeholders/raci/evidence; verified on 2026-04-02 via `pnpm exec playwright test --project=visual-regression src/tests/e2e/core-pages.visual.spec.ts --update-snapshots`) |
| [x] | P3 | `TASK-022` | None | Accessibility audit and fixes `[x] Implemented (App Shell Accessibility)` | `FRONTEND_TESTING_PLAN.md` |
| [x] | P3 | `TASK-023` | None | Frontend performance optimization pass `[x] Implemented (Evidence Viewer + Projects Dialog Code Splitting)` | `FRONTEND_TESTING_PLAN.md` |
| [x] | P3 | `TASK-024` | Env Setup, `TASK-1429` | Cross-browser testing `[x] Implemented (Chromium + Firefox + WebKit Smoke Lane)` | `FRONTEND_TESTING_PLAN.md` |
| [x] | P2 | `TASK-1428` | `TASK-024` | Fix Playwright-managed Next dev server bootstrap for cross-browser smoke runs by stabilizing workspace-root/runtime resolution and eliminating the missing `@swc/helpers.../_interop_require_default` failure seen on `npm run test:e2e -- src/tests/e2e/cross-browser-smoke.spec.ts --project cross-browser-chromium --project cross-browser-firefox --project cross-browser-webkit` `[x] Implemented (Managed Server Config Hardening)` | `TASK-024` verification run 2026-04-01 |
| [x] | P2 | `TASK-1429` | `TASK-024`, `TASK-1428` | Resolve the remaining local Next dev runtime hang where `next dev --hostname 127.0.0.1 --port 3100 --webpack` reports ready but HTTP requests to `/`, `/demo`, `/demo/documents`, `/demo/evidence`, and `/projects` time out, preventing the Playwright cross-browser smoke lane from reaching a healthy app response `[x] Implemented (Localhost Runtime + Public Demo Route Stability; proxy matcher now excludes root, demo, auth aliases, and Clerk webhooks at matcher level, re-verified 2026-04-02)` | `TASK-024` route probe 2026-04-01; `TASK-1429` integration re-verification 2026-04-02 |
| [-] | P3 | `TASK-025` | Backend API | Deliver production-ready frontend test suite `[-] In Progress (typecheck, visual-regression, lint bootstrap recovery, WBS filter hook verification, alerts-page verification, projects-page verification, demo-page hydration stabilization, and lint debt remediation pass on 2026-04-02; remaining consolidated blockers are now outside the lint gate)` | `FRONTEND_TESTING_PLAN.md`; `TASK-025` verification run 2026-04-02 |
| [-] | P3 | `TASK-417` | Frontend, `TASK-1175` | Zero auth-related console errors verified at runtime `[-] In Progress (Unauthenticated Clerk warnings removed; remaining runtime warning is development-key usage)` | `docs/archive/plans/Clerk/CLERK_IMPLEMENTATION_CHECKLIST_2026-02-17.md` |
| [-] | P3 | `TASK-1175` | Env Setup, `TASK-1430` | Production Clerk keys use `pk_live_...` and `sk_live_...` `[-] Blocked (Repo state still uses test keys; live-key provisioning requires operator access to production secret stores)` | `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` |
| [ ] | P3 | `TASK-1176` | None | Production domain and sign-in/sign-up URLs configured in Clerk | `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` |
| [ ] | P3 | `TASK-1177` | None | Production email templates and sender verified in Clerk | `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` |
| [ ] | P3 | `TASK-1178` | Backend API | Frontend deployed with production variables | `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` |
| [ ] | P3 | `TASK-1179` | Backend API | Backend deployed and reachable from frontend | `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` |
| [x] | P1 | `TASK-1430` | Security | Treat tracked Clerk secret material in `apps/web/.env.local` as a secret-management incident: remove from tracked env, rotate exposed test credentials, and replace with safe local placeholders or ignored developer-only values per runbook guardrails `[x] Implemented (Tracked-File Assumption Closed; Sanitized Web Env Template Added)` | `TASK-1175` verification 2026-04-01 |
| [-] | P1 | `TASK-1431` | Security | Rotate the already-exposed local Clerk test credentials and redistribute fresh developer-only test keys through an approved secret channel; update local workstations from sanitized templates instead of shared secret-bearing env files `[-] Blocked (Operator access to Clerk test instance and secret channel required; executable runbook added)` | `TASK-1430` follow-up 2026-04-01 |
| [x] | P3 | `TASK-1232` | None | Projects: column customization | `docs/wireframes/02-projects.md` |
| [x] | P3 | `TASK-1233` | None | Projects: save custom filter presets | `docs/wireframes/02-projects.md` |
| [x] | P3 | `TASK-1234` | Backend API | Projects: inline editing | `docs/wireframes/02-projects.md` |
| [x] | P3 | `TASK-1235` | Backend API | Projects: Kanban view toggle | `docs/wireframes/02-projects.md` |
| [x] | P3 | `TASK-1236` | Backend API | Projects: advanced search query builder | `docs/wireframes/02-projects.md` |
| [x] | P2 | `TASK-1432` | Backend API | Projects list API parity for advanced query builder: add server-side `project_type` and date-range filters to `GET /api/v1/projects` so the frontend builder can stop relying on local-only filtering for those dimensions `[x] Implemented (Projects List API Filter Parity)` | `TASK-1236` follow-up 2026-04-01 |
| [x] | P3 | `TASK-1243` | Backend API | Evidence viewer: 3D relationship viewer | `docs/wireframes/03-evidence-viewer.md` |
| [x] | P3 | `TASK-1244` | Backend API | Evidence viewer: timeline of evidence evolution | `docs/wireframes/03-evidence-viewer.md` |
| [x] | P2 | `TASK-1433` | Backend API | Evidence viewer API parity for evolution timeline: expose true evidence history/version events so the frontend can stop deriving the timeline from document and alert timestamps only `[x] Implemented (Document History API + Evidence Timeline Hook)` | `TASK-1244` follow-up 2026-04-01 |
| [x] | P3 | `TASK-1246` | None | Evidence viewer: AI explanation of relationships | `docs/wireframes/03-evidence-viewer.md` |
| [x] | P2 | `TASK-1434` | AI & Backend API | Evidence viewer AI explanation parity: replace the current derived relationship narrative with a true model-backed explanation service grounded in evidence graph data and citations `[x] Implemented (Grounded Relationship Explanation Service + Endpoint + Hook)` | `TASK-1246` follow-up 2026-04-01 |
| [x] | P3 | `TASK-1252` | None | Alerts: alert rules customization | `docs/wireframes/04-alerts.md` |
| [x] | P2 | `TASK-1435` | Backend API | Alerts rule customization persistence: add API-backed save/load for workspace alert-rule configuration so `TASK-1252` stops relying on local-only browser storage | [x] Implemented (API-backed tenant workspace settings, alerts route contract, frontend integration) 2026-04-01 |
| [x] | P3 | `TASK-1256` | None | Alerts: subscriptions for email and Slack | `docs/wireframes/04-alerts.md` |
| [x] | P2 | `TASK-1436` | Backend API | Alerts subscriptions persistence: add API-backed save/load and delivery-target validation for email and Slack subscriptions so `TASK-1256` stops relying on local-only browser storage | [x] Implemented (tenant-scoped API persistence plus backend email/Slack target validation) 2026-04-01 |
| [x] | P3 | `TASK-1257` | None | Alerts: SLA tracking and violations | `docs/wireframes/04-alerts.md` |
| [x] | P2 | `TASK-1437` | Backend API | Alerts SLA policy parity: expose alert SLA policy and due-date fields from the API so `TASK-1257` stops deriving deadlines only from severity and local timestamp rules | [x] Implemented (API now returns SLA policy and due date; frontend consumes API-backed SLA fields) 2026-04-01 |
| [x] | P3 | `TASK-1274` | None | RACI: workload analysis | `docs/wireframes/06-raci-matrix.md` |
| [x] | P3 | `TASK-1275` | None | RACI: conflict detection for overloaded stakeholders | `docs/wireframes/06-raci-matrix.md` |
| [x] | P3 | `TASK-1278` | Backend API | RACI: mobile-optimized list view | `docs/wireframes/06-raci-matrix.md` |
| [x] | P3 | `TASK-1283` | Backend API | RACI: Gantt-style timeline view | `docs/wireframes/06-raci-matrix.md` |
| [x] | P2 | `TASK-1438` | Backend API | RACI timeline parity: expose real activity sequencing and schedule dates from the API so `TASK-1283` stops deriving Gantt phases locally from row order | [x] Implemented (RACI API now returns sequence/task code/planned dates; frontend timeline consumes API-backed scheduling) 2026-04-02 |
| [x] | P3 | `TASK-1334` | Backend API | Evidence Viewer: confirmation dialog for approve/reject | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` |
| [x] | P3 | `TASK-1335` | Backend API | Evidence Viewer: mandatory validation for confidence below 90 percent | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` |
| [x] | P2 | `TASK-1440` | Backend API | Evidence Viewer validation parity: persist mandatory low-confidence approval notes to backend approval audit trail so `TASK-1335` stops enforcing reviewer notes only in the frontend | [x] Implemented (evidence approve flow now sends validation note; approvals audit records approved feedback comments) 2026-04-02 |
| [x] | P3 | `TASK-1336` | None | Alerts Center: dynamic validation by severity | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` |
| [x] | P3 | `TASK-1338` | Backend API | Evidence Viewer: integrate `react-pdf` for real viewer | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` |
| [x] | P3 | `TASK-1340` | None | Alerts Center: lateral detail sheet | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` |
| [x] | P3 | `TASK-1341` | None | Alerts Center: bulk actions with validation | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` |
| [x] | P2 | `TASK-1441` | Backend API | Alerts bulk-action parity: persist validated bulk resolve actions through backend batch endpoints so `TASK-1341` stops resolving multi-select status changes only in frontend state | [x] Implemented (bulk resolve batch endpoint, backend validation, frontend API-backed bulk resolve flow) 2026-04-02 |
| [ ] | P3 | `TASK-1342` | Backend API | Project List: quick view sheet | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` |
| [ ] | P3 | `TASK-1343` | Backend API | Evidence Viewer: highlight sync PDF to data panel | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` |
| [ ] | P3 | `TASK-1345` | Backend API | RACI Matrix: auto-assign AI dialog | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` |
| [ ] | P3 | `TASK-1346` | None | Project List: project creation dialog wizard | `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` |
| [x] | P2 | `TASK-1443` | Frontend | Regenerate or clean stale Next type artifacts under `apps/web/.next/types` so frontend typecheck stops referencing removed `app/dashboard/...` routes after the dashboard-tree migration | [x] Implemented (stale `.next/types` dashboard artifacts removed; `pnpm exec tsc -p apps/web/tsconfig.json --noEmit --pretty false` now advances only to `TASK-1444` baseline errors on 2026-04-02) |
| [x] | P2 | `TASK-1444` | Frontend | Clear remaining frontend TypeScript baseline blockers outside stale `.next` artifacts: missing `JSX` namespace in lazy-dialog/pdf tests, `LazyProjectDialogs` prop mismatch, implicit-`any` hooks, axios browser declaration typing, and `lib/api/services/documents.ts` return-shape mismatch | [x] Implemented (frontend `tsc` passes after lazy-test typing fixes, dialog prop alignment, hook typing cleanup, axios import normalization, and documents contract narrowing on 2026-04-02) |
| [x] | P2 | `TASK-1445` | Frontend, `TASK-1446` | Stabilize local Vitest execution on Windows where worker startup fails with `spawn EPERM`, preventing targeted frontend verification even when the TypeScript baseline is clean | [x] Implemented (Vitest config is ESM-safe, app-rooted, `vmThreads`-backed, and the wrapper defaults to `--configLoader native`; elevated runs now execute ordinary test files and surface real test assertions instead of failing at worker/config startup on 2026-04-02) |
| [x] | P2 | `TASK-1446` | Frontend | Resolve app-local Vitest/MSW bootstrap compatibility after `TASK-1445`: `@/src/tests/setup` imports `msw/node`, which currently fails under elevated Vitest runs with `until-async` ESM/CJS parsing errors before tests execute; either isolate MSW to the integration lane or patch the Vitest dependency pipeline so the global setup can load cleanly | [x] Implemented (Vitest aliases now redirect app-local MSW wrappers to test shims, mock data no longer depends on `@mswjs/data`, and `pnpm vitest run src/tests/integration --config vitest.integration.config.ts --configLoader native` now boots the full integration lane from `apps/web` and reaches real suite assertions instead of failing on the `until-async` MSW bootstrap chain on 2026-04-02) |
| [x] | P2 | `TASK-1447` | Frontend | Fix real frontend auth-client tests surfaced by `TASK-1445`: `apps/web/lib/api/client.test.ts` now executes under Vitest but fails because jsdom no longer allows redefining `window.location`; update the tests or redirect abstraction to use a stable location-mocking strategy | [x] Implemented (auth client now uses a test-overridable browser-location adapter, and `pnpm vitest run lib/api/client.test.ts --config vitest.config.ts --configLoader native` passes on 2026-04-02) |
| [x] | P2 | `TASK-1452` | Frontend | Restore the frontend lint gate for `TASK-025`: `pnpm lint` currently crashes inside the ESLint/AJV stack (`Cannot set properties of undefined (setting 'defaultMeta')`) before app rules run | [x] Implemented (added app-local flat ESLint config, restored compatible `ajv@6` resolution for `eslint` and `@eslint/eslintrc` via workspace overrides, added direct `typescript-eslint` dependency for the web app, and confirmed `pnpm lint` now evaluates project files and reports real rule violations instead of crashing on 2026-04-02) |
| [x] | P2 | `TASK-1453` | Frontend | Repair jsdom-stable WBS filter tests for `TASK-025`: `apps/web/hooks/__tests__/useWbsFilter.test.ts` still redefines `window.location`, breaking 11 tests under the consolidated Vitest lane | [x] Implemented (replaced `window.location` redefinition with same-origin `history.replaceState()` URL setup/reset in the hook tests; `pnpm vitest run hooks/__tests__/useWbsFilter.test.ts --config vitest.config.ts --configLoader native` passes with 11/11 tests on 2026-04-02) |
| [x] | P2 | `TASK-1454` | Frontend | Reconcile alerts-page test contracts for `TASK-025`: `apps/web/app/(app)/alerts/page.test.tsx` currently fails SLA expectations and times out in the API-backed rules/subscriptions/bulk-resolve scenarios | [x] Implemented (updated the SLA test to use API-backed `sla_due_at` data, replaced fake timers with a fixed `Date.now()` stub, added unconditional timer cleanup, and re-verified `app/(app)/alerts/page.test.tsx` with 8/8 tests passing on 2026-04-02) |
| [x] | P2 | `TASK-1455` | Frontend | Reconcile project-page test contracts for `TASK-025`: `LazyProjectDialogs.test.tsx` still detects inline dialog content in `app/(app)/projects/page.tsx`, and `page.test.tsx` quick-view assertions drift on status casing/content | [x] Implemented (updated the lazy-dialog source guard to distinguish direct batch/template imports from the legitimate inline quick-view dialog, aligned quick-view assertions with actual rendered text content, and re-verified `components/features/projects/LazyProjectDialogs.test.tsx` plus `app/(app)/projects/page.test.tsx` with 16/16 tests passing on 2026-04-02) |
| [x] | P2 | `TASK-1456` | Frontend | Eliminate locale-sensitive hydration mismatches in demo pages exposed by the visual-regression lane: `app/demo/documents/page.tsx` and `app/demo/alerts/page.tsx` render `toLocaleDateString()` differently between server and client | [x] Implemented (replaced locale-sensitive demo date rendering with deterministic UTC `YYYY-MM-DD` formatting in the demo alerts/documents pages, added explicit demo-date assertions, and re-verified `app/demo/demo-pages-labeling.test.tsx` with 2/2 tests passing on 2026-04-02) |
| [x] | P2 | `TASK-1457` | `TASK-1452` | Resolve the real frontend lint violations now exposed by the restored lint gate for `TASK-025`: `pnpm lint` no longer crashes, but currently reports app/test/config findings across unused symbols, `any` usage, `@ts-ignore`, `require()` imports, regex escapes, and custom `preserve-caught-error` cases | [x] Implemented (removed dead imports/symbols across demo and app routes, tightened shared API/type definitions from `any` to `unknown`, preserved caught-error causes in auth API helpers, normalized filename sanitizers, converted empty interfaces to type aliases, modernized config imports, and re-verified `pnpm lint` passing cleanly on 2026-04-02) |
| [x] | P3 | `TASK-1460` | Frontend | Remove the deprecated and unused `@mswjs/data` dev dependency from the web workspace so package installation stops surfacing an avoidable unsupported-package warning `[x] Implemented (Manifest Cleanup)` | `apps/web/package.json`; repo install warning triage 2026-04-02 |
| [x] | P2 | `TASK-1461` | Frontend | Restore `next dev` startup after npm lockfile refresh removed an undeclared standalone `webpack` package that `apps/web/next.config.js` imported directly; switch the config to Next's bundled webpack runtime so local dev no longer fails with `ERR_MODULE_NOT_FOUND` `[x] Implemented (Config Import Fix)` | `apps/web/next.config.js`; local dev startup failure 2026-04-02 |
| [x] | P2 | `TASK-1462` | Frontend | Finish the ESM-safe `next.config.js` cleanup so `next dev` no longer crashes on `ReferenceError: __dirname is not defined in ES module scope` after the config started loading as an ES module `[x] Implemented (import.meta.url Directory Resolution)` | `apps/web/next.config.js`; local dev startup failure 2026-04-02 |
| [x] | P3 | `TASK-1463` | Frontend | Remove the remaining Node `MODULE_TYPELESS_PACKAGE_JSON` warning during `next dev` by migrating the web Next config from `next.config.js` to the native ESM filename `next.config.mjs` instead of relying on implicit reparsing `[x] Implemented (Native ESM Config Filename)` | `apps/web/next.config.mjs`; local dev warning cleanup 2026-04-02 |

### 2.3 AI & Intelligence

| Status | Priority | ID | Dependency | Task | Source |
|--------|----------|----|------------|------|--------|
| [ ] | P0 | `TASK-504` | AI & Intelligence | Enforce strict severity taxonomy in scoring: Critical, High, Medium, Low, Info | `docs/archive/plans/tdd-testing/I7_RISK_SCORING_IMPLEMENTATION_CHECKLIST_2026-02-16.md` |
| [ ] | P1 | `TASK-216` | Backend API | Prompt Analytics Dashboard: metrics by prompt version | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md` |
| [ ] | P1 | `TASK-1365` | None | MCP tools must enable complete workflows, not just endpoint wrappers | `Skills/.agents/skills/mcp-builder/reference/node_mcp_server.md` |
| [ ] | P1 | `TASK-1391` | None | Node MCP server naming follows `{service}-mcp-server` | `Skills/.agents/skills/mcp-builder/reference/node_mcp_server.md` |
| [ ] | P1 | `TASK-1404` | None | Python MCP tools must enable complete workflows, not just endpoint wrappers | `Skills/.agents/skills/mcp-builder/reference/python_mcp_server.md` |
| [ ] | P1 | `TASK-1413` | None | Python MCP server naming follows `{service}_mcp` | `Skills/.agents/skills/mcp-builder/reference/python_mcp_server.md` |
| [ ] | P2 | `TASK-218` | None | Template validator and linter for prompt templates | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md` |
| [ ] | P2 | `TASK-220` | None | Multi-language prompt templates in English and Spanish | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md` |
| [ ] | P2 | `LC-01` | Planned | Implement Procurement Plan flow with LangChain | Planning |
| [ ] | P2 | `LC-02` | Planned | Implement RACI flow with LangChain | Planning |
| [ ] | P2 | `LC-03` | Planned | Implement Stakeholder Resolution flow with LangChain | Planning |
| [ ] | P3 | `TASK-215` | None | Persist AI usage into `ai_usage_logs` | `apps/api/src/core/ai/CE-S2-008_IMPLEMENTATION_SUMMARY.md` |
| [ ] | P3 | `TASK-217` | Env Setup | A/B testing framework for prompt versions | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md` |
| [ ] | P3 | `TASK-219` | None | Prompt optimization suggestions from usage metrics | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md` |
| [ ] | P3 | `TASK-222` | None | Implement Flash/cache layer described in AI README | `apps/api/src/core/ai/README_FLASH.md` |
| [ ] | P3 | `TASK-272` | Env Setup | Add all new coverage-improvement tests | `docs/COVERAGE_IMPROVEMENT_PLAN.md` |
| [ ] | P3 | `TASK-273` | Env Setup | Ensure all coverage-improvement tests pass | `docs/COVERAGE_IMPROVEMENT_PLAN.md` |
| [ ] | P3 | `TASK-274` | None | Reach at least 70 percent coverage on targeted area | `docs/COVERAGE_IMPROVEMENT_PLAN.md` |
| [ ] | P3 | `TASK-275` | Env Setup | Prove no regression in existing tests | `docs/COVERAGE_IMPROVEMENT_PLAN.md` |
| [ ] | P3 | `TASK-1088` | None | Score formula uses exponential penalty density model | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1089` | None | Score floor remains 5.0, never reaches 0 | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1090` | None | Score ceiling remains 97.0 when findings exist | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1091` | None | Larger scope absorbs findings better | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1092` | None | Low-confidence findings have reduced impact | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1093` | None | Deterministic signals weighted above LLM output | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1094` | None | Diagnostics include penalty density, scope factor, severity distribution | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1095` | None | LLM returns `impact_score` and `confidence` floats | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1096` | None | Responses validated and clamped to `[0.0, 1.0]` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1097` | None | Batch prompt reduces token usage | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1098` | None | Cost tracking per evaluation | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1099` | None | Graceful fallback on parse errors | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1100` | None | Implement target graph topology for coherence subgraph | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1103` | None | Coherence subgraph compiles without errors | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1104` | None | Coherence subgraph callable standalone and from main pipeline | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1106` | None | pgvector cosine similarity query implemented | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1107` | None | Similarity threshold configurable with default `0.85` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1109` | None | Cross-document pairs fed into cross-clause evaluation | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1110` | None | `/v0/coherence/evaluate` preserves output contract | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1111` | None | Coherence score is granular float, not binary 0/100 | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1112` | None | `low_budget_mode` defaults to true | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1113` | None | Diagnostics exposed via query param or secondary endpoint | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1114` | Env Setup | Golden tests for 0, moderate, and severe findings | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1115` | None | Edge cases: empty clauses, missing data, malformed dates | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1116` | None | Low budget mode cost under $0.01 per project | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |
| [ ] | P3 | `TASK-1117` | Env Setup | All existing tests still pass after coherence changes | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` |

### 2.4 DevOps & Infrastructure

| Status | Priority | ID | Dependency | Task | Source |
|--------|----------|----|------------|------|--------|
| [x] | P3 | `TASK-195` | Env Setup | Integration tests CI job passing | `.github/CICD_SETUP.md` |
| [ ] | P3 | `TASK-197` | None | Coverage gates defined as `>=60%` orange and `>=80%` green | `.github/CICD_SETUP.md` |
| [x] | P1 | `TASK-1459` | DevOps | Keep local API startup and `docker compose up` healthchecks from failing on placeholder Sentry values by skipping invalid DSNs instead of crashing the FastAPI lifespan `[x] Implemented (Startup Regression Test + Invalid DSN Guard)` | `apps/api/src/main.py`; `apps/api/tests/core/test_mcp_startup.py`; local compose failure analysis 2026-04-02 |
| [ ] | P3 | `TASK-456` | DevOps | Monitor auth failures in Sentry | `docs/archive/plans/Clerk/IMPLEMENTATION_GUIDE.md` |
| [ ] | P3 | `TASK-515` | DevOps | Define and run performance benchmarks | `docs/archive/plans/tdd-testing/TDD_QUICK_REFERENCE.md` |

### 2.5 Security

| Status | Priority | ID | Dependency | Task | Source |
|--------|----------|----|------------|------|--------|
| [x] | P0 | TASK-041 | Security | Prepare signoff artifact and approvals package | MASTER_AUDIT_PLAN.md | [x] Prepared release artifact at `evidence/releases/2026-04-01-rc1/` with verified security and performance evidence. |

| [x] | P0 | `TASK-055` | Security | Close Gate 8: document security | `README.md` | [x] Formally documented Gate 8 security in `docs/architecture/GATE_8_SECURITY_SPECIFICATION.md` and updated project status. |
 | [x] | P0 | `TASK-088` | Security | Run golden security tests | `SECURITY_REMEDIATION_CHECKLIST.md` | [x] Verified path traversal, file size limits, and metadata depth validation through automated and manual security tests. |

| [x] | P0 | `TASK-094` | Security | Perform code review with explicit security focus | `SECURITY_REMEDIATION_CHECKLIST.md` | [x] Completed security code review confirming path traversal protection, resource limits, and model immutability. |
 | [x] | P0 | `TASK-095` | Security | Update security audit documentation with fixes | `SECURITY_REMEDIATION_CHECKLIST.md` | [x] Updated `SECURITY_AUDIT_GOLDEN_DATASET.md` and `SECURITY_REMEDIATION_CHECKLIST.md` to reflect all resolved security items. |

| [x] | P0 | `TASK-112` | Security | Authentication required or explicitly marked public on every endpoint | `.claude/skills/api-design/SKILL.md` | [x] Enforced authentication on frontend support and analysis endpoints; explicitly tagged public endpoints in OpenAPI. |
 | [x] | P0 | `TASK-113` | Security | Authorization ensures users access only their own resources | `.claude/skills/api-design/SKILL.md` | [x] Verified dual-layer isolation: PostgreSQL RLS policies and application-level tenant filtering. |

| [ ] | P0 | `TASK-149` | Security | Authorization checks before sensitive operations | `.claude/skills/security-review/SKILL.md` |
| [ ] | P0 | `TASK-150` | Security | Row Level Security enabled in Supabase | `.claude/skills/security-review/SKILL.md` |
| [ ] | P0 | `TASK-163` | Security | User-based authenticated rate limiting | `.claude/skills/security-review/SKILL.md` |
| [ ] | P0 | `TASK-176` | Security | Regular security updates program in place | `.claude/skills/security-review/SKILL.md` |
| [ ] | P0 | `TASK-182` | Security | Proper token handling in authentication flows | `.claude/skills/security-review/SKILL.md` |
| [ ] | P0 | `TASK-183` | Security | Role checks enforced in authorization layer | `.claude/skills/security-review/SKILL.md` |
| [ ] | P0 | `TASK-186` | Security | Security headers such as CSP and X-Frame-Options configured | `.claude/skills/security-review/SKILL.md` |
| [ ] | P0 | `TASK-190` | Security | Verify RLS is enabled in Supabase | `.claude/skills/security-review/SKILL.md` |
| [ ] | P0 | `TASK-558` | Security | Security audit passes with no exposed data | `docs/archive/plans/ux-implementation/MASTER_PLAN_v1.0.md` |
| [ ] | P0 | `TASK-1052` | Security | Build minimum critical-path E2E suite | `docs/audits/PRODUCTION_READINESS_AUDIT_2026-02-14.md` |
| [ ] | P0 | `TASK-1125` | Security | Security E2E pass with release threshold coverage | `docs/internal/RELEASE_SIGNOFF_POLICY.md` |
| [ ] | P0 | `TASK-1140` | Security | No ORM fallback path remains in auth bootstrap helpers | `docs/planning/FOLLOWUP_AUTH_BOOTSTRAP_FALLBACK_REMOVAL.md` |
| [ ] | P0 | `TASK-1141` | Security | Auth bootstrap and tenant isolation tests all pass | `docs/planning/FOLLOWUP_AUTH_BOOTSTRAP_FALLBACK_REMOVAL.md` |
| [ ] | P0 | `TASK-1142` | Security | Update `AUTH_BOOTSTRAP_FALLBACK_POLICY` runbook | `docs/planning/FOLLOWUP_AUTH_BOOTSTRAP_FALLBACK_REMOVAL.md` |
| [ ] | P0 | `TASK-1150` | Security | No high or critical vulnerabilities in Snyk | `docs/planning/ROADMAP_v2.4.0.md` |
| [ ] | P0 | `TASK-1350` | Security | Required suite artifacts included in `manifest.yaml` | `evidence/releases/2026-03-24-rc1/signoff.md` |
| [ ] | P0 | `TASK-1351` | Security | Manual approvals captured from product, security, and operations | `evidence/releases/2026-03-24-rc1/signoff.md` |
| [ ] | P1 | `TASK-160` | Security | Rate limiting enforced on all API endpoints | `.claude/skills/security-review/SKILL.md` |
| [ ] | P0 | `SEC-GOLD-01` | API / Security | Add rate limiting to the golden regression runner CLI | `SECURITY_AUDIT_GOLDEN_DATASET.md` |

### 2.6 Testing & Quality

Normalization for this section:

- `Prerequisite` means environment or fixture setup needed before meaningful test execution.
- `Executable Verification` means runnable suites, assertions, or contract checks that produce delivery evidence.
- `Quality Gate` means cross-suite outcome thresholds such as coverage, lint, typing, and flaky-test control.
- Documentation/reporting tasks stay separate from execution tasks.

#### 2.6.1 Prerequisites

| Status | Priority | ID | Dependency | Task | Source |
|--------|----------|----|------------|------|--------|
| [x] | P0 | `TASK-044` | None | Python 3.11+ installed | `NEXT_STEPS_TO_RUN_TESTS.md` |
| [x] | P0 | `TASK-047` | Prerequisite | PostgreSQL running or fallback available | `NEXT_STEPS_TO_RUN_TESTS.md` |
| [x] | P0 | `TASK-244` | Prerequisite | Configure PostgreSQL test database | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [x] | P0 | `TASK-1183` | Prerequisite | PostgreSQL started with Docker | `docs/runbooks/INSTRUCCIONES_TESTS.md` |
| [ ] | P1 | `TASK-1416` | Prerequisite | Activate backend virtual environment at `apps/.venv` before running `TS-E2E-SEC-TNT-001` | `NEXT_STEPS_TO_RUN_TESTS.md` |
| [ ] | P1 | `TASK-1417` | Prerequisite | Install backend dependencies required by `TS-E2E-SEC-TNT-001` from `apps/api/requirements.txt` | `NEXT_STEPS_TO_RUN_TESTS.md` |
| [ ] | P1 | `TASK-1442` | Prerequisite | Stabilize shared API pytest DB bootstrap in `apps/api/tests/conftest.py`: fix the PostgreSQL enum-reset transaction abort during `test_engine` setup so router and integration suites can execute again | `TASK-1432` verification attempt 2026-04-01 |
| [x] | P3 | `TASK-048` | Prerequisite | Remove or comment `pyfiebdc` from requirements as test blocker | `NEXT_STEPS_TO_RUN_TESTS.md` |
| [x] | P3 | `TASK-049` | Prerequisite | Normalize working directory instructions to `apps/api` | `NEXT_STEPS_TO_RUN_TESTS.md` |
| [x] | P3 | `TASK-1180` | Prerequisite | Docker Desktop installed | `docs/runbooks/INSTRUCCIONES_TESTS.md` |
| [x] | P3 | `TASK-1181` | Prerequisite | Docker Desktop running | `docs/runbooks/INSTRUCCIONES_TESTS.md` |
| [x] | P3 | `TASK-1182` | Prerequisite | `docker ps` works without error | `docs/runbooks/INSTRUCCIONES_TESTS.md` |
| [x] | P3 | `TASK-1184` | Prerequisite | Wait period in infra bootstrap runbook confirmed | `docs/runbooks/INSTRUCCIONES_TESTS.md` |
| [x] | P3 | `TASK-1185` | Prerequisite | Test migrations applied successfully | `docs/runbooks/INSTRUCCIONES_TESTS.md` |

#### 2.6.2 Test Asset Preparation

| Status | Priority | ID | Dependency | Task | Source |
|--------|----------|----|------------|------|--------|
| [x] | P0 | `TASK-227` | Test Assets | `get_auth_headers()` returns valid JWT headers | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-223` | Test Assets | Provide `AsyncClient` test client fixture | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-224` | Test Assets | Provide test database session fixture | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-225` | Test Assets | Provide FastAPI test app fixture | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-226` | Test Assets | Implement `create_test_token()` helper | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-228` | Test Assets | Implement expired token helper | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-229` | Test Assets | Implement invalid-signature token helper | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-230` | Test Assets | Implement tenant factory for tests | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-231` | Test Assets | Implement user factory for tests | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-232` | Test Assets | Implement project factory for tests | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-233` | Test Assets | Implement document factory for tests | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-245` | Test Assets | Implement base fixtures for client and db session | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-246` | Test Assets | Implement authentication helpers | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-247` | Test Assets | Run migrations in test database | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-248` | Test Assets | Implement test data factories | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |

#### 2.6.3 Executable Verification

| Status | Priority | ID | Dependency | Task | Source |
|--------|----------|----|------------|------|--------|
| [x] | P0 | `TASK-1186` | Executable Verification | Security tests executed successfully | `docs/runbooks/INSTRUCCIONES_TESTS.md` |
| [x] | P0 | `TASK-1197` | Executable Verification | Critical E2E tests pass | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` |
| [ ] | P1 | `TASK-1418` | Executable Verification | Execute `TS-E2E-SEC-TNT-001` and confirm `11/11` passes with PostgreSQL or documented `10/11` SQLite fallback | `NEXT_STEPS_TO_RUN_TESTS.md` |
| [x] | P1 | `TASK-239` | Executable Verification | Cross-tenant project isolation covered by test suite | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P2 | `TASK-039` | Executable Verification | Execute wireframe spec test cases TC-001 to TC-010 | `MASTER_AUDIT_PLAN.md` |
| [ ] | P3 | `TASK-042` | Executable Verification | Implement remaining P3 unit tests | `MASTER_AUDIT_PLAN.md` |
| [ ] | P3 | `TASK-249` | Executable Verification | Complete five JWT tests | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-250` | Executable Verification | Validate all JWT tests pass | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-251` | Executable Verification | Implement cross-tenant tests | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-252` | Executable Verification | Validate RLS policies through tests | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-254` | Executable Verification | Implement malicious payload tests | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-234` | Executable Verification | Test protected endpoint with valid JWT | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-235` | Executable Verification | Test protected endpoint with invalid-signature JWT | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-236` | Executable Verification | Test protected endpoint with expired JWT | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-237` | Executable Verification | Test protected endpoint with missing JWT | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-238` | Executable Verification | Test protected endpoint with JWT for non-existent tenant | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-240` | Executable Verification | Test cross-tenant document upload denial | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-241` | Executable Verification | Test cross-tenant clause access denial | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-242` | Executable Verification | Test SQL injection in project search | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-243` | Executable Verification | Test SQL injection in path parameter handling | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-1199` | Executable Verification | `TS-I13-EDGE-001` conditional-edge suite completed | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` |
| [ ] | P3 | `TASK-1200` | Executable Verification | WBS API schema validation tests | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P3 | `TASK-1201` | Executable Verification | Error response contracts | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P1 | `TASK-1203` | Executable Verification | Use case input and output contracts | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P3 | `TASK-1202` | Executable Verification | Domain entity contracts | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P3 | `TASK-1204` | Executable Verification | `WBSTree` prop interface tests | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P3 | `TASK-1205` | Executable Verification | `WBSItemCard` rendering contract | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P3 | `TASK-1206` | Executable Verification | Event handler contracts | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P3 | `TASK-1207` | Executable Verification | State management contracts | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P3 | `TASK-1208` | Executable Verification | Cross-module navigation tests | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P3 | `TASK-1209` | Executable Verification | API-to-frontend data flow contracts | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P3 | `TASK-1210` | Executable Verification | State synchronization contracts | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P3 | `TASK-1221` | Executable Verification | Keyboard navigation contract | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P3 | `TASK-1224` | Executable Verification | ARIA tree structure contract | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [ ] | P3 | `TASK-1225` | Executable Verification | No accessibility violations | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md` |
| [x] | P2 | `TASK-1448` | Frontend | Reconcile frontend CI workflow assertions enforced by suite `S1-13`: ensure `.github/workflows/frontend-ci.yml` contains the required named quality gates and remains reachable from the app-local integration lane | [x] Verified (the app-local integration assertion passes against `.github/workflows/frontend-ci.yml` on 2026-04-02 via `pnpm vitest run src/tests/integration/ci/S1-13-frontend-ci.integration.test.ts --config vitest.integration.config.ts --configLoader native` from `apps/web`) |
| [x] | P2 | `TASK-1449` | Frontend | Reconcile frontend layer-rules ADR assertions enforced by suite `S1-15`: ensure `docs/architecture/decisions/004-frontend-layer-rules.md` stays present and aligned with the current server-vs-client data access contract | [x] Verified (the app-local integration assertion passes against `docs/architecture/decisions/004-frontend-layer-rules.md` on 2026-04-02 via `pnpm vitest run src/tests/integration/ci/S1-15-frontend-adr.integration.test.ts --config vitest.integration.config.ts --configLoader native` from `apps/web`) |
| [x] | P2 | `TASK-1450` | Frontend, Docs | Reconcile three-layer server-component strategy assertions enforced by suite `S2-11`: align technical design, ADR `005-three-layer-sc-test-strategy.md`, TDD backlog, frontend CI workflow, and dedicated frontend E2E workflow with the guardrails expected by the integration suite | [x] Verified (the app-local integration assertion passes against the current technical design/ADR/backlog/workflow set on 2026-04-02 via `pnpm vitest run src/tests/integration/ci/S2-11-sc-test-strategy.integration.test.ts --config vitest.integration.config.ts --configLoader native` from `apps/web`) |
| [x] | P2 | `TASK-1451` | Frontend, QA | Reconcile Sprint 2 test inventory and security-quality gate assertions enforced by suites `S2-12` and `S2-12-SEC`: restore the expected unit/integration/E2E inventory, acceptance-flow evidence, and no-skip/no-placeholder security guardrails under the app-local test layout | [x] Verified (both app-local integration assertions pass on 2026-04-02 via `pnpm vitest run src/tests/integration/ci/S2-12-sprint2-test-gate.integration.test.ts --config vitest.integration.config.ts --configLoader native` and `pnpm vitest run src/tests/integration/ci/S2-12-security-focus.integration.test.ts --config vitest.integration.config.ts --configLoader native` from `apps/web`) |

#### 2.6.4 Quality Gates And Reporting

| Status | Priority | ID | Dependency | Task | Source |
|--------|----------|----|------------|------|--------|
| [x] | P1 | `TASK-517` | Quality Gate | All P0 tests passing at recorded checkpoint | `docs/archive/plans/tdd-testing/TDD_QUICK_REFERENCE.md` |
| [ ] | P3 | `TASK-043` | Quality Gate | Sync TDD backlog counts with exhaustive suite index | `MASTER_AUDIT_PLAN.md` |
| [ ] | P1 | `TASK-1419` | Quality Gate | Prove `TS-E2E-SEC-TNT-001` reaches `>=90%` coverage on tenant isolation modules | `NEXT_STEPS_TO_RUN_TESTS.md` |
| [ ] | P2 | `TASK-1420` | Quality Gate | Prove `TS-E2E-SEC-TNT-001` executes in under `100ms` per test | `NEXT_STEPS_TO_RUN_TESTS.md` |
| [ ] | P3 | `TASK-1188` | Quality Gate | All unit tests pass | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` |
| [ ] | P3 | `TASK-1189` | Quality Gate | New code coverage above 80 percent | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` |
| [ ] | P3 | `TASK-1190` | Quality Gate | No unjustified skipped tests | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` |
| [ ] | P3 | `TASK-1191` | Quality Gate | No `pytest.fail(\"TODO\")` left in completed work | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` |
| [ ] | P3 | `TASK-1192` | Quality Gate | Ruff linting passes | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` |
| [ ] | P3 | `TASK-1193` | Quality Gate | Mypy type checking passes | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` |
| [ ] | P3 | `TASK-1194` | Quality Gate | Integration tests pass | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` |
| [ ] | P3 | `TASK-1195` | Quality Gate | No flaky tests remain | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` |
| [ ] | P3 | `TASK-1196` | Quality Gate | Total coverage above 85 percent | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` |
| [ ] | P3 | `TASK-1198` | Reporting | Test documentation updated | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` |
| [ ] | P3 | `TASK-1226` | Reporting | Full clean execution summary for every runnable test in session | `docs/testing/TEST_INVENTORY_2026-03-02.md` |
| [ ] | P3 | `TASK-253` | Reporting | Document edge cases | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-255` | Reporting | Validate ORM protection paths | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |
| [ ] | P3 | `TASK-256` | Reporting | Document attack surface | `apps/api/tests/security/SECURITY_TESTS_STATUS.md` |

---

## 3. Release Snapshot

### P0 Release Blockers

Reference only. Execution ownership remains in Section 2 under the listed backlog IDs.

| Backlog ID | Task | Source |
|------------|------|--------|
| `REL-RC1-01` | Execute release-candidate UAT and manual QA checklist and record results in the release bundle | `docs/UAT_CHECKLIST.md` |
| `REL-RC1-02` | Attach final Gate 7 signoff decision and evidence to the candidate release bundle | `docs/RELEASE_CRITERIA.md` |
| `TASK-1125` | Security E2E pass with release threshold coverage | `docs/internal/RELEASE_SIGNOFF_POLICY.md` |
| `TASK-1350` | Required suite artifacts included in `manifest.yaml` | `evidence/releases/2026-03-24-rc1/signoff.md` |
| `TASK-1351` | Manual approvals captured from product, security, and operations | `evidence/releases/2026-03-24-rc1/signoff.md` |

### Gate 6 and Gate 7 Traceability

| Gate | Status | Notes |
|------|--------|-------|
| `G6-01` | [x] | LangGraph checkpointer persistence verified |
| `G6-02` | [x] | Golden baseline established |
| `G6-03` | [x] | Node-level execution progress streaming implemented |
| `G6-04` | [x] | Pricing source-of-truth centralized |
| `G6-05` | [x] | Coherence alert grouping improved |
| `G6-06` | [x] | Legacy-adapter retirement assumption closed as not applicable |
| `G7-01` | [x] | Swagger/API contract workbook executed |
| `G7-02` | [x] | Automated release thresholds defined |
| `G7-03` | [x] | UAT and manual QA signoff checklist defined |
| `G7-04` | [x] | Performance and capacity targets defined |
| `G7-05` | [x] | Backup, restore, and DR evidence recorded |

---

## 4. Completed Governance Items

| Status | ID | Task | Notes |
|--------|----|------|-------|
| [x] | `DOC-GOV-01` | Consolidate project governance around one canonical backlog | Completed 2026-03-29 |
| [x] | `DOC-ARCH-01` | Promote technical design into platform-wide v4.1 document | Completed 2026-03-29 |
| [x] | `G6-02-EX-01` | Expand to Core-100 dataset for nightly runs | Completed 2026-03-28 |
| [x] | `G6-06` | Review document adapter retirement assumption and close as not applicable | Closed after validation |
| [x] | `MOD-CLEANUP-01` | Remove deprecated module paths | Completed 2026-03-26 |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-29 | Normalized duplicate ownership: `TASK-036` into `TASK-1344`, `TASK-037` into `TASK-1347`, and removed summary testing duplicates in favor of granular test-execution tasks. |
| 2026-03-29 | Restored the missing categorized task inventory from the 2026-03-28 unified roadmap and kept this file as the only execution authority. |
| 2026-03-29 | Replaced the oversized raw documentation registry with a planner-triaged source table focused on docs that still generate live work. |
| 2026-03-29 | Preserved previously completed governance and gate traceability items. |
