# C2Pro Master Orchestration Backlog (v1.0)

**Date:** 2026-03-19
**Status:** ACTIVE
**Goal:** Transition from "Theoretically Built" to "Verified Production-Ready" by resolving security, data integrity, and architectural gaps.

---

## 🛑 Double-Marking Protocol (STRICT)

To maintain project-wide visibility, every task follows the **Dual Update Rule**:

1. When a task is finished, mark it as `[x]` in this file.
2. Immediately locate the **Source Reference** (e.g., `DB-REC-P3`) in the original file and mark it there as well.
3. If a task status diverges between files, the **Master Backlog (this file)** is the source of truth for scheduling, but the **Original File** is the source of truth for technical context.

---

## 👥 Team Assignments

| Team             | Codename     | Focus Area                                                             |
| :--------------- | :----------- | :--------------------------------------------------------------------- |
| **Team Alpha**   | **Sentinel** | Security (RLS), Infrastructure, DevOps, Database Migrations.           |
| **Team Bravo**   | **Nexus**    | AI Orchestration (LangGraph), Core Backend Logic, Real Data Analytics. |
| **Team Charlie** | **Prism**    | Frontend UI/UX, API Client (Orval), Demo-Mode Isolation, Branding.     |

---

## ⛓️ Top-Level Dependency Map

1. **Nexus** depends on **Sentinel** for the `auth_bootstrap` SQL functions to allow register/login under fail-closed RLS.
2. **Prism** depends on **Nexus** for real API endpoints (removing `_fake_projects`) to ensure the UI renders real production data.
3. **Nexus** depends on **Sentinel** for the LangGraph PostgreSQL checkpointer schema.

---

## 🏁 Production Governance

This file is the engineering execution backlog.

Production certification is tracked separately in:

- `docs/planning/PRODUCTION_READINESS_GATE_2026-03-19.md`
- `docs/planning/EXECUTIVE_STATUS_REPORT_2026-03-19.md` (leadership snapshot)

Rule:

- a task may be `[x]` here and still remain blocked for release until its production gate evidence is complete.

---

## 📋 Master Task List

### 🏗️ Team Alpha: Sentinel (Security & Infra)

_Primary Goal: Harden the environment and finalize the migration authority._

| ID       | Task                                                                                                                         | Priority | Dependency | Source Ref                   | Status |
| :------- | :--------------------------------------------------------------------------------------------------------------------------- | :------- | :--------- | :--------------------------- | :----- |
| **A-1**  | **Audit SQL Migrations 006-015:** Mirror RLS cleanup and index drops from Supabase to Alembic.                               | **P0**   | None       | `DB-REC-P3-01`               | [x]    |
| **A-2**  | **Deploy `auth_bootstrap` functions:** Ensure remote Supabase target has the SD functions.                                   | **P0**   | None       | `DB-REC-P0-06`               | [x]    |
| **A-3**  | **Archive Supabase Runner:** Move SQL migrations to `archive/` once Alembic parity is 100%.                                  | **P2**   | A-1        | `DB-REC-P3-03`               | [x]    |
| **A-4**  | **Celery Worker Health:** Implement `/api/v1/health/worker` to monitor parsing health.                                       | **P1**   | None       | `AUDIT-TASK-3.2`             | [x]    |
| **A-5**  | **Automated Secrets Scan:** Add `gitleaks` to GitHub Actions `tests.yml`.                                                    | **P1**   | None       | `AUDIT-TASK-3.4`             | [x]    |
| **A-6**  | **Deduplicate SQL Initializers:** Resolve collision between `001_init` and `001_initial`.                                    | **P2**   | None       | `DB-REC-P3-02`               | [x]    |
| **A-7**  | **CD Pipeline Automation:** Establish merge-to-main auto-deploy for `apps/web` and `apps/api`.                               | **P1**   | None       | `AUDIT-TASK-3.5`             | [x]    |
| **A-8**  | **PII Filter Hardening:** Make Presidio/spaCy required or add a regex fallback for anonymization.                            | **P1**   | None       | `AUDIT-S1`                   | [x]    |
| **A-9**  | **CORS Audit:** Restrict backend allowed origins per environment and verify non-production safety.                           | **P1**   | None       | `AUDIT-S3`                   | [x]    |
| **A-10** | **API Key Validation:** Replace JWT-only stubs with real API key validation for integrations.                                | **P1**   | None       | `CODE-TODO-SEC-APIKEY`       | [x]    |
| **A-11** | **MCP Rate/Audit Persistence:** Move MCP rate limiting and audit writes from memory/comments to Redis/DB-backed persistence. | **P2**   | None       | `CODE-TODO-MCP-RATE`         | [x]    |
| **A-12** | **Runtime/Test Env Guardrail:** Add `scripts/validate_runtime_env.py` to block manual QA against test DBs.                   | **P1**   | None       | `REM-CHECK-6.15.1`           | [x]    |
| **A-13** | **Seeded Identity Isolation:** Ensure pytest identities cannot bleed into shared runtime tenant/user tables.                 | **P1**   | None       | `REM-CHECK-6.15.2`           | [x]    |
| **A-14** | **Sentry Lifecycle Wiring:** Initialize and flush Sentry during API startup/shutdown.                                        | **P2**   | None       | `CODE-TODO-SENTRY`           | [x]    |
| **A-15** | **Supabase Bootstrap Verification:** Complete the active Supabase bootstrap/security checklist in runbooks.                  | **P2**   | A-3        | `RUNBOOK-SUPABASE-CHECKLIST` | [x]    |

### 🧠 Team Bravo: Nexus (AI & Core Backend)

_Primary Goal: Replace synthetic metrics with real data and verify the AI pipeline._

| ID       | Task                                                                                                                                                       | Priority | Dependency | Source Ref                      | Status |
| :------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------- | :------- | :--------- | :------------------------------ | :----- |
| **B-1**  | **Eliminate `_fake_projects`:** Replace with real DB implementation in Project Router.                                                                     | **P0**   | A-2        | `REM-CHECK-2`                   | [x]    |
| **B-2**  | **Eliminate `_fake_alerts`:** Ensure alert mutations survive process restarts via persistence.                                                             | **P0**   | A-2        | `REM-CHECK-3`                   | [x]    |
| **B-3**  | **LangGraph Checkpointer:** Verify Postgres persistence for analysis state transitions.                                                                    | **P1**   | A-1        | `AUDIT-TASK-3.1`                | [x]    |
| **B-4**  | **Real Coherence Dashboard:** Derive scores from `analyses` and `coherence_results` tables.                                                                | **P1**   | B-1        | `REM-CHECK-4`                   | [x]    |
| **B-5**  | **Golden Dataset Baseline:** Curate high-quality contracts (aiming for >10) for automated accuracy regression tests using real-world Spanish project data. | **P2**   | None       | `AUDIT-TASK-3.3`                | [ ]    |
| **B-6**  | **Real MCP Execution:** Replace synthetic completions in `mcp/router.py` with DB calls.                                                                    | **P1**   | A-2        | `REM-CHECK-5`                   | [x]    |
| **B-7**  | **ORM Relationship Cleanup:** Re-enable deferred FK/model imports across analysis/documents/stakeholders/procurement.                                      | **P1**   | A-1        | `CODE-TODO-DB-MODELS`           | [x]    |
| **B-8**  | **Coherence Alert Deduping:** Group repeated coherence findings into summary alerts where appropriate.                                                     | **P2**   | B-4        | `CODE-TODO-COHERENCE-ALERTS`    | [x]    |
| **B-9**  | **LLM Pricing Source of Truth:** Replace hardcoded cost math in `llm_client.py` with `model_router` pricing.                                               | **P2**   | None       | `CODE-TODO-LLM-PRICING`         | [x]    |
| **B-10** | **Alert Mutation AuthZ:** Add `current_user` wiring and admin enforcement to analysis alert update/delete routes.                                          | **P1**   | A-2        | `CODE-TODO-ALERTS-AUTH`         | [x]    |
| **B-11** | **Swagger Endpoint Verification Sweep:** Execute and complete the active backend endpoint workbook against real APIs.                                      | **P2**   | B-1        | `SWAGGER-WB-01`                 | [x]    |
| **B-12** | **Retire Legacy Document Adapters:** Replace/remove transitional legacy extraction and RAG ingestion adapters.                                             | **P2**   | B-1        | `CODE-TODO-LEGACY-DOC-ADAPTERS` | [x]    |

### 🎨 Team Charlie: Prism (Frontend & API Client)

_Primary Goal: Standardize API communication and isolate the Demo experience._

| ID       | Task                                                                                                                   | Priority | Dependency | Source Ref                                      | Status |
| :------- | :--------------------------------------------------------------------------------------------------------------------- | :------- | :--------- | :---------------------------------------------- | :----- |
| **C-1**  | **Unified API URL:** Finish the proxy-first URL standardization across all frontend clients and dashboard paths.       | **P0**   | None       | `DB-REC-P3-04`, `REM-CHECK-11`, `REM-CHECK-7.1` | [x]    |
| **C-2**  | **Dashboard Auth Fix:** Propagate tenant/auth headers correctly in server-side props.                                  | **P0**   | C-1        | `DB-REC-P3-05`                                  | [x]    |
| **C-3**  | **Replace `openapi.json` stub:** Sync real backend JSON to `apps/web/schema/api.json`.                                 | **P1**   | None       | `REM-CHECK-6.14.1`                              | [x]    |
| **C-4**  | **Demo Mode Banner:** High-contrast visual labeling in `Navbar.tsx` for demo modes.                                    | **P1**   | None       | `REM-CHECK-7.3`                                 | [x]    |
| **C-5**  | **Fail-Closed PDF Viewer:** Remove watermarks and throw real 404s in production mode.                                  | **P1**   | B-1        | `REM-CHECK-7.2`, `REM-CHECK-13`                 | [x]    |
| **C-6**  | **LLM Progress Streaming:** Implement SSE "Node Progress Tracker" for N1-N16 nodes.                                    | **P2**   | B-3        | `AUDIT-TASK-3.6`                                | [x] UI |
| **C-7**  | **Real Evidence Rendering:** Ensure production document/evidence views use real downloads and extracted entities only. | **P1**   | B-1        | `REM-CHECK-10`                                  | [x]    |
| **C-8**  | **Frontend Auth Failure Clarity:** Remove ambiguous 401 redirects/fallback behavior in the web client.                 | **P1**   | C-1        | `REM-CHECK-12`                                  | [x]    |
| **C-9**  | **Orval Mock Isolation:** Generate MSW handlers into explicit mock-only output ignored by production builds.           | **P1**   | C-3        | `REM-CHECK-6.14.2`                              | [x]    |
| **C-10** | **Orval CI Sync:** Automate frontend client regeneration against backend OpenAPI in CI.                                | **P1**   | C-3        | `REM-CHECK-6.14.3`                              | [x]    |
| **C-11** | **Document Highlight Mapping:** Finish alert/entity -> PDF highlight mapping in `apps/web/lib/api/index.ts`.           | **P2**   | C-7        | `CODE-TODO-WEB-HIGHLIGHTS`                      | [x]    |
| **C-12** | **Viewer Backend Integration:** Wire entity validation and alert resolution UI flows to real backend PATCH endpoints.  | **P2**   | B-2        | `WIREFRAME-CE-S2-010`                           | [x]    |
| **C-13** | **Highlight Search Verification:** Complete testing/verification of highlight search and related viewer flows.         | **P2**   | C-11       | `WIREFRAME-HIGHLIGHT-SEARCH`                    | [x]    |

### 🧭 Supplemental Intake (Active Pending Work Discovered)

_These tasks were discovered during repo-wide intake across active docs, code TODOs, and runbooks. They should be triaged into the main team queues until completed or intentionally archived._

| Team        | Task                                                                                                | Priority | Source Ref                    | Status |
| :---------- | :-------------------------------------------------------------------------------------------------- | :------- | :---------------------------- | :----- |
| **Charlie** | Finish remaining real-data remediation acceptance criteria and close the manual-QA validation gaps. | **P1**   | `REM-CHECK-COMPLETION`        | [x]    |
| **Alpha**   | Define release promotion, rollback, and environment signoff workflow for production releases.       | **P1**   | `LEAD-GAP-RELEASE-GOVERNANCE` | [x]    |
| **Alpha**   | Define operational ownership, escalation, and on-call expectations for production operations.       | **P1**   | `LEAD-GAP-OPS-READINESS`      | [x]    |

---

## 🔍 Source File Reference Key

- `DB-REC`: `context/working/DB_MIGRATION_RECONCILIATION_PLAN_2026-03-18.md`
- `REM-CHECK`: `docs/audit/REAL_DATA_REMEDIATION_CHECKLIST_2026-03-18.md`
- `REM-CHECK-COMPLETION`: completion criteria in `docs/audit/REAL_DATA_REMEDIATION_CHECKLIST_2026-03-18.md`
- `AUDIT-TASK`: `docs/audit/C2PRO_TECHNICAL_AUDIT_REPORT.md`
- `AUDIT-S*`: blocker findings in `docs/audit/C2PRO_TECHNICAL_AUDIT_REPORT.md`
- `SWAGGER-WB`: `docs/internal/SWAGGER_ENDPOINT_WORKBOOK.md`
- `RUNBOOK-SUPABASE-CHECKLIST`: active checklists in `docs/runbooks/supabase/*.md`
- `CODE-TODO-*`: actionable TODOs in active source files
- `WIREFRAME-*`: active implementation notes in `docs/wireframes/*.md`
- `LEAD-GAP-RELEASE-GOVERNANCE`: `docs/runbooks/ci-cd-setup.md`
- `LEAD-GAP-OPS-READINESS`: `docs/runbooks/incident-response.md`

---

_Report curated by Senior Staff Architect — Orchestrating Teams Alpha, Bravo, and Charlie._
