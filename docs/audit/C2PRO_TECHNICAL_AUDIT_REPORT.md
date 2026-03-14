# C2Pro Technical Audit Report

**Date:** 2026-03-14
**Role:** Lead Engineering & Product Orchestrator (Lead Architect & Scrum Master)
**Methodology:** Tree of Thoughts + Multiple Perspectives
**Scope:** Full-stack audit of c2pro multi-agent LLM application

---

## Phase 1: Expert Agents Report

---

### Agent 1 — Frontend (UI/UX)

**Stack:** Next.js (App Router), TypeScript strict mode, Zustand, TanStack React Query, Tailwind CSS, Clerk Auth, Sentry.

**Current State:**

- **Routing & Pages:** Full route structure exists under `apps/web/app/` covering auth (`sign-in`, `register`), protected app shell (`dashboard`, `projects/[id]`, `projects/[id]/coherence`, `projects/[id]/wbs`, `projects/[id]/risks`, `raci`, `documents`, `admin`).
- **State Management:** Zustand stores for `app-mode`, `auth`, `filters`, `processing`. Provider stack is correctly layered: `Clerk > Sentry > ReactQuery > AuthSync > Theme > Auth > DemoMode`.
- **Custom Hooks:** Data-fetching hooks (`useProject`, `useProjectOverview`, `useRaci`, `useDocumentAlerts`, `useWbsFilter`) and UI hooks (`useHighlightSearch`, `useCountUp`, `use-toast`).
- **API Client:** OpenAPI code-gen via `orval` for type-safe backend communication.
- **Demo Mode:** `isDemoMode` flag exists, enabling UI testing without a live backend — this is a key asset for unblocking frontend QA.

**Blockers:**

| # | Blocker | Impact |
|---|---------|--------|
| F1 | No confirmed E2E test suite running against the real backend | Cannot validate user flows beyond mocked data |
| F2 | MSW mocks may drift from actual API contracts | False-positive test results |
| F3 | Streaming/real-time feedback for long-running LLM operations not yet implemented | UX gap during 10-60s orchestration runs |

**Next Steps:**

1. Run Playwright E2E suite against a local `docker-compose` stack (backend + DB + Redis) to validate real flows.
2. Add a visual loading/progress state for the LangGraph orchestration pipeline (N1-N16 node progress).
3. Automate OpenAPI spec sync (`orval`) in CI to prevent mock drift.

---

### Agent 2 — Backend (Core & API)

**Stack:** FastAPI (100% async), SQLAlchemy (AsyncSession), PostgreSQL (Supabase), Alembic migrations, Redis (Upstash), Pydantic v2, Hexagonal Architecture (Ports & Adapters).

**Current State:**

- **Architecture:** Clean hexagonal design with bounded contexts: Projects, Documents, Coherence, Stakeholders, Procurement, HITL, Observability. Each context has domain entities, application services, ports (interfaces), and adapters (implementations).
- **Database:** 9+ Alembic migrations (`000` through `009`), including RLS policies, tenant columns, indexes, and RAG setup. Multi-tenant isolation via PostgreSQL RLS with `app.current_tenant` GUC variable.
- **API Surface:** RESTful routes under `/api/v1/` for projects, documents, coherence, RACI, HITL reviews, procurement.
- **Document Pipeline:** `CompositeFileParser` supporting PDF (PyMuPDF), Excel (openpyxl), Word (python-docx), BC3/FIEBDC. Upload flow: `POST /documents/upload` → storage → async parsing → orchestration trigger.
- **Event-Driven:** Redis Pub/Sub event bus with subscribers for notifications, analytics, and dead letter queue.

**Blockers:**

| # | Blocker | Impact |
|---|---------|--------|
| B1 | No evidence of a working `docker-compose up` that boots all services end-to-end | Developers cannot spin up the full stack locally |
| B2 | Database migration state unknown (have migrations run successfully against a real DB?) | Schema may be out of sync |
| B3 | Celery/background task runner for document processing not confirmed operational | Upload → parse → orchestrate pipeline may hang |

**Next Steps:**

1. Validate `docker-compose.yml` boots: PostgreSQL, Redis, MinIO, FastAPI, and runs migrations automatically.
2. Confirm the document upload → parse → LangGraph trigger pipeline works with a real PDF.
3. Add a `/health` endpoint that validates DB connectivity, Redis connectivity, and Anthropic API key presence.

---

### Agent 3 — CI/CD (Infrastructure & DevOps)

**Stack:** GitHub Actions, Docker multi-stage builds, Vercel (frontend), Railway (backend), Supabase Cloud (DB), Cloudflare R2 (storage), Upstash (Redis).

**Current State:**

- **CI Workflows (6 found):**

| Workflow | Trigger | Purpose | Status |
|----------|---------|---------|--------|
| `tests.yml` | push/PR | Unit (70% threshold), integration, S5 AI gates | **In Progress** |
| `e2e-security-tests.yml` | push/PR | RLS multi-tenant isolation (11 scenarios) | **In Progress** |
| `frontend-ci.yml` | push/PR | Next.js build, lint | **In Progress** |
| `frontend-e2e.yml` | push/PR | Playwright E2E | **Unknown** |
| `evaluation-regression.yml` | scheduled | LLM accuracy drift detection | **Unknown** |
| `scheduled-drift-checks.yml` | nightly | Cost & performance monitoring | **Unknown** |

- **Docker:** Multi-stage Dockerfile for backend (3.11-slim builder → runtime). Non-root user, health checks, metadata labels.
- **Local Dev:** `docker-compose.yml` exists with PostgreSQL, Redis, MinIO services. Bootstrap script at `infrastructure/scripts/bootstrap_test_infra.py`.

**Blockers:**

| # | Blocker | Impact |
|---|---------|--------|
| C1 | No evidence of a working Staging environment | Cannot test deployments before production |
| C2 | CI pipeline status unknown — are all 6 workflows green? | May be accumulating broken builds |
| C3 | No deployment automation to Railway/Vercel confirmed | Manual deploys are error-prone and slow |

**Next Steps:**

1. Run all 6 CI workflows and document pass/fail status.
2. Set up a Staging environment (Railway preview + Supabase branch DB).
3. Add deployment automation: merge to `main` → auto-deploy to Staging; manual promote to Production.

---

### Agent 4 — Security (SecOps)

**Stack:** Clerk (AuthN), PostgreSQL RLS (AuthZ), Presidio PII anonymization, Supabase JWT, audit trail.

**Current State:**

- **Authentication:** Dual provider (Clerk primary, Supabase fallback). JWT → extract `sub` (user_id) + `org_id` (tenant_id) → set PostgreSQL GUC → RLS enforcement.
- **Multi-Tenant Isolation:** RLS policies on every table. 11 E2E security test scenarios covering cross-tenant read/write/delete, concurrent isolation, inactive tenant denial.
- **PII Anonymization (GATE 8):** Presidio integration anonymizes prompts before sending to Claude. De-anonymization on response. Mapping stored for re-identification.
- **API Key Management:** `ANTHROPIC_API_KEY` via environment variables. `.env.example` template exists. `.gitignore` correctly excludes `.env` files.
- **Audit Trail:** `audit_trail.py` + persistence adapter tracking user actions, data access, timestamps.
- **Rate Limiting:** Middleware exists for request throttling.

**Blockers:**

| # | Blocker | Impact |
|---|---------|--------|
| S1 | PII anonymization depends on optional `spacy` — may not be installed in all environments | PII could leak to Claude in dev/test |
| S2 | No confirmed secrets scanning in CI (e.g., `gitleaks`, `trufflehog`) | API keys could be committed accidentally |
| S3 | CORS configuration not audited — may be overly permissive in dev | XSS vector in non-production |

**Next Steps:**

1. Make `spacy` + Presidio a required dependency (not optional) or add a fallback regex-based PII filter.
2. Add `gitleaks` to CI as a pre-commit hook and GitHub Action.
3. Audit CORS settings: restrict origins to known frontend domains per environment.

---

### Agent 5 — QA & Usability (Testing) **[CRITICAL BLOCKER]**

**Stack:** pytest (backend), Vitest + MSW (frontend unit/integration), Playwright (frontend E2E), Locust (performance).

**Current State:**

- **Test Files Found:**

| Category | Location | Count | Status |
|----------|----------|-------|--------|
| Unit | `tests/unit/` | Multiple | **Exist, status unknown** |
| Integration | `tests/integration/`, `tests/test_i*.py` | 8+ suites (I3, I5, I6, I10-I14) | **Exist, status unknown** |
| E2E Security | `tests/e2e/security/` | 11 scenarios | **Exist, status unknown** |
| E2E Workflow | `tests/e2e/workflows/` | Document upload flow | **Exist, status unknown** |
| Performance | `tests/performance/` | Stress test + Locust | **Exist, status unknown** |
| Accuracy | `tests/accuracy/` | LLM regression | **Exist, status unknown** |
| Frontend Unit | `apps/web/**/*.test.*` | Unknown count | **Exist, status unknown** |
| Frontend E2E | Playwright config | Unknown | **Exist, status unknown** |

- **Mock Mode:** `C2PRO_AI_MOCK=1` enables mock LLM responses — **critical for deterministic testing**.
- **Test Light Mode:** `C2PRO_TEST_LIGHT=1` disables cost controller — **enables CI without budget checks**.
- **Fixtures:** Async DB fixtures with RLS isolation, authenticated HTTP client, pre-created test projects.

**THE CORE PROBLEM:** Tests exist in significant volume, but there is **no evidence they have been executed successfully**. The project has invested heavily in writing test code but has not confirmed:
1. All tests pass.
2. The test infrastructure (DB, Redis, mock LLM) boots correctly.
3. The E2E flow (upload document → parse → orchestrate → view results) completes.

**Blockers:**

| # | Blocker | Severity | Impact |
|---|---------|----------|--------|
| Q1 | No confirmed green test run for any test suite | **CRITICAL** | Cannot validate any functionality |
| Q2 | Test infrastructure bootstrap not verified | **HIGH** | Tests may fail on setup, not on logic |
| Q3 | No E2E test covering the full LLM pipeline with mock mode | **HIGH** | Core value proposition untested |
| Q4 | LLM accuracy regression tests never confirmed to run | **MEDIUM** | Model drift undetectable |

**Proposed E2E Testing Strategy for LLM Workflows:**

```
┌─────────────────────────────────────────────────────────┐
│              E2E TEST PYRAMID FOR LLM APPS              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Level 4: Production Monitoring (LangSmith evals)       │
│    - Accuracy drift detection (scheduled)               │
│    - Cost anomaly alerts                                │
│    - Latency P95 tracking                               │
│                                                         │
│  Level 3: Integration with Real LLM (gated, expensive)  │
│    - Golden dataset: 10 contracts → known outputs       │
│    - Run weekly or on-demand                            │
│    - Assert: risk count ±20%, category accuracy ≥80%    │
│                                                         │
│  Level 2: Integration with Mock LLM (CI, fast)          │
│    - C2PRO_AI_MOCK=1                                    │
│    - Full pipeline: upload → parse → orchestrate → DB   │
│    - Assert: data flows correctly, no exceptions        │
│    - Assert: RLS isolation maintained                   │
│                                                         │
│  Level 1: Unit Tests (fast, deterministic)              │
│    - JSON parsing, token counting, cost calculation     │
│    - Prompt template rendering                          │
│    - Graph routing logic (no LLM calls)                 │
│    - Pydantic model validation                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Immediate Action Plan:**

1. **Day 1:** Run `pytest tests/unit/ -v` with `C2PRO_AI_MOCK=1` and document results.
2. **Day 1:** Boot `docker-compose up -d` and run `alembic upgrade head` to validate DB.
3. **Day 2:** Run `pytest tests/integration/ -v` against the Docker stack.
4. **Day 3:** Execute the E2E document upload flow test against mock LLM.
5. **Day 5:** Create a "golden test" with a real contract PDF and validate the full N1-N16 pipeline.

---

### Agent 6 — AI Integration / LLMOps

**Stack:** Anthropic Claude (Haiku/Sonnet/Opus), LangGraph (17-node orchestration), LangSmith (tracing), tiktoken (token counting), tenacity (retry), circuit breaker pattern.

**Current State:**

- **Agent Architecture (actual, not "writer"/"reviewer"):**

| Agent | File | Role |
|-------|------|------|
| `BaseAgent` | `base_agent.py` | Abstract base with retry + JSON hardening |
| `RiskExtractionAgent` | `risk_agent.py` | Extract risks from contracts (6 categories) |
| `WBSExtractionAgent` | `wbs_agent.py` | Extract WBS items (deliverables, work packages, activities) |
| LLM Coherence Evaluator | `llm_evaluator.py` | Detect contradictions, ambiguities, vague terms |
| Citation Validator | Node N15 | Verify claims against source documents |

- **Orchestration:** LangGraph 17-node graph (`workflow.py`):

```
N1(ingest) → N2(anonymize) → N3(route) → [N4|N5|N9](extract) → N12(critique)
  → [retry|HITL|continue] → N6(stakeholders) → N7(RACI) → N8(coherence)
  → N15(citations) → N10(knowledge graph) → N17(save) → N11(decisions)
  → N16(assemble) → END
```

- **Model Routing:** `AITaskType` enum routes 20+ task types to appropriate Claude tier:
  - **Haiku (flash):** Classification, simple extraction — $0.25/$1.25 per 1M tokens
  - **Sonnet (standard):** Complex extraction, coherence — $3.00/$15.00 per 1M tokens
  - **Opus (powerful):** Deep reasoning (Phase 2+) — $15.00/$75.00 per 1M tokens

- **Resilience:**
  - Retry with exponential backoff (tenacity: 3 attempts, 4-10s wait)
  - Circuit breaker (5 failures → open, 60s recovery)
  - Fallback client (primary → secondary LLM)
  - Timeout handler (30s default, returns `{"status": "fallback_retry"}`)

- **Cost Control:**
  - Pre-execution budget validation per tenant
  - Monthly budget with daily tracking
  - Alerts at 50%, 75%, 90%, 100% thresholds
  - `BudgetExceededException` blocks calls at 100%

- **Hallucination Mitigation (4 layers):**
  1. Citation Validator (N15): claims vs. source document
  2. Coherence Rules Engine: internal contradiction detection
  3. Confidence scoring: extraction confidence (0-1)
  4. Human-in-the-Loop (N13/N14): gate for low-confidence results

- **Observability:** `UsageAnalyticsService` tracking tokens, cost, latency per call. LangSmith integration for traces. Sentry for errors.

**Blockers:**

| # | Blocker | Impact |
|---|---------|--------|
| A1 | LangGraph workflow never confirmed to run end-to-end | 17-node pipeline may have broken edges or state issues |
| A2 | No golden dataset for accuracy benchmarking | Cannot measure extraction quality or detect drift |
| A3 | "Writer" and "reviewer" roles mentioned in project description don't map to actual agents | Terminology mismatch — actual agents are `RiskExtraction`, `WBS`, `Coherence`, `Citation` |
| A4 | PostgreSQL checkpointer for LangGraph state not confirmed operational | Graph may lose state on failure |

**Next Steps:**

1. Run the LangGraph workflow with `C2PRO_AI_MOCK=1` to validate graph topology and state transitions.
2. Create a golden dataset: 5 contracts with manually annotated risks, WBS, stakeholders, and coherence scores.
3. Clarify terminology: document the actual agent roles vs. the "writer"/"reviewer" abstraction.
4. Test the HITL checkpoint (N13/N14): simulate low-confidence extraction and verify human review queue.

---

## Phase 2: Orchestrator Synthesis

---

### Development Status Report (Executive Summary)

**Paragraph 1 — Architecture & Code Quality:**
C2Pro demonstrates a mature, well-architected codebase following hexagonal architecture, domain-driven design, and event-driven patterns. The backend (FastAPI + SQLAlchemy + PostgreSQL) implements proper multi-tenant isolation via RLS, comprehensive PII anonymization, and a sophisticated 17-node LangGraph orchestration pipeline. The frontend (Next.js + TypeScript + Zustand) has a complete page structure, type-safe API client, and provider stack. The AI layer integrates Anthropic Claude with intelligent model routing (Haiku/Sonnet/Opus), circuit breakers, retry logic, budget enforcement, and 4-layer hallucination mitigation. From a code structure standpoint, this project is significantly more advanced than a typical early-stage application.

**Paragraph 2 — The Critical Gap (Testability):**
Despite the substantial investment in architecture and code, the project suffers from a single overarching blocker: **no confirmed execution of the system end-to-end**. Test files exist across all layers (unit, integration, E2E, security, performance, accuracy), but there is no evidence any suite has been run successfully. The infrastructure bootstrap (`docker-compose`, migrations, Redis, MinIO) has not been validated as a working stack. The LangGraph 17-node pipeline has not been confirmed to execute from N1 (document ingestion) through N16 (final assembly). This means the core value proposition — uploading a contract and receiving risk analysis, WBS, RACI matrix, and coherence scoring — remains **theoretically implemented but practically unverified**.

**Paragraph 3 — Path Forward:**
The immediate priority is to make the system **testable and executable**. This does not require new feature development — the code exists. It requires operational validation: booting the infrastructure, running migrations, executing the test suites, and confirming the LLM pipeline works with mock mode (`C2PRO_AI_MOCK=1`). Once a single E2E flow succeeds (upload PDF → extract risks → generate RACI → score coherence → view in UI), the project transitions from "built" to "working." From there, the focus shifts to creating golden datasets for accuracy benchmarking, setting up Staging environments, and hardening the CI pipeline.

---

### Audit Checklist

| # | Area | Item | Status | Notes |
|---|------|------|--------|-------|
| 1 | **Backend** | FastAPI app structure & routing | **In Progress** | Routes exist, not confirmed running |
| 2 | **Backend** | PostgreSQL schema & migrations | **In Progress** | 9 migrations written, execution unverified |
| 3 | **Backend** | Multi-tenant RLS isolation | **In Progress** | Policies + 11 test scenarios written |
| 4 | **Backend** | Document upload & parsing pipeline | **In Progress** | PDF/Excel/Word/BC3 parsers written |
| 5 | **Backend** | Redis event bus & caching | **In Progress** | Code exists, operational status unknown |
| 6 | **AI/LLM** | LangGraph 17-node orchestration | **In Progress** | Full graph defined, never executed E2E |
| 7 | **AI/LLM** | Model routing (Haiku/Sonnet/Opus) | **In Progress** | YAML config + fallback, untested at runtime |
| 8 | **AI/LLM** | Cost controller & budget enforcement | **In Progress** | Code complete, no real usage data |
| 9 | **AI/LLM** | PII anonymization (Presidio) | **In Progress** | Optional dependency — may not be installed |
| 10 | **AI/LLM** | Hallucination mitigation (4 layers) | **In Progress** | Citation validator, coherence, confidence, HITL written |
| 11 | **AI/LLM** | Mock LLM mode (`C2PRO_AI_MOCK=1`) | **In Progress** | Exists, not confirmed functional |
| 12 | **Frontend** | Page structure & routing | **In Progress** | All pages scaffolded |
| 13 | **Frontend** | State management (Zustand) | **In Progress** | 4 stores implemented |
| 14 | **Frontend** | Demo mode for offline testing | **In Progress** | Flag exists, UX coverage unclear |
| 15 | **Frontend** | API client (orval OpenAPI codegen) | **In Progress** | Generated, sync with backend unverified |
| 16 | **CI/CD** | GitHub Actions workflows (6) | **In Progress** | Files exist, pass/fail status unknown |
| 17 | **CI/CD** | Docker multi-stage build | **In Progress** | Dockerfile written, build not confirmed |
| 18 | **CI/CD** | Staging environment | **Pending** | No Staging env exists |
| 19 | **CI/CD** | Production deployment automation | **Pending** | Target infra identified (Vercel/Railway), no automation |
| 20 | **Security** | Clerk authentication | **In Progress** | Integrated, flow not tested E2E |
| 21 | **Security** | Secrets scanning in CI | **Pending** | No `gitleaks` or equivalent |
| 22 | **Security** | CORS audit | **Pending** | Configuration not reviewed |
| 23 | **QA** | Unit test suite execution | **Blocked** | Tests written, never confirmed green |
| 24 | **QA** | Integration test suite execution | **Blocked** | Requires working Docker stack |
| 25 | **QA** | E2E test (full pipeline) | **Blocked** | Requires all services + mock LLM |
| 26 | **QA** | Golden dataset for accuracy | **Pending** | No benchmark contracts exist |
| 27 | **QA** | Performance/load testing | **Pending** | Locust file exists, never run |
| 28 | **QA** | Frontend E2E (Playwright) | **Blocked** | Requires running backend |

---

### Action Plan (Backlog) — Prioritized

**Priority 0 — Unblock Testability (Days 1-3)**

| # | Task | Owner (Agent) | Depends On | Deliverable |
|---|------|---------------|------------|-------------|
| 1 | **Boot local infrastructure:** Run `docker-compose up -d` (PostgreSQL, Redis, MinIO). Fix any issues. | Backend + CI/CD | None | All services healthy |
| 2 | **Run database migrations:** Execute `alembic upgrade head` against local PostgreSQL. Fix schema errors. | Backend | Task 1 |  `alembic current` shows latest revision |
| 3 | **Run unit tests:** `C2PRO_AI_MOCK=1 pytest tests/unit/ -v`. Fix failures. | QA | None | Green unit test suite with pass count |
| 4 | **Start FastAPI server:** `uvicorn src.main:app` against Docker services. Verify `/health` and `/docs`. | Backend | Tasks 1, 2 | Swagger UI accessible |
| 5 | **Run integration tests:** `C2PRO_AI_MOCK=1 pytest tests/integration/ -v`. Fix failures. | QA | Tasks 1, 2 | Green integration suite |

**Priority 1 — First E2E Flow (Days 3-5)**

| # | Task | Owner (Agent) | Depends On | Deliverable |
|---|------|---------------|------------|-------------|
| 6 | **Test document upload:** `POST /documents/upload` with a real PDF. Verify storage + parsing. | Backend + QA | Task 4 | Document parsed, clauses extracted |
| 7 | **Test LangGraph pipeline:** Trigger orchestration with `C2PRO_AI_MOCK=1`. Verify N1→N16 executes. | AI/LLMOps | Tasks 4, 6 | Graph completes, results in DB |
| 8 | **Test frontend connection:** Start Next.js dev server, authenticate via Clerk, navigate to project. | Frontend | Task 4 | Dashboard renders with real data |
| 9 | **Run E2E security tests:** `pytest tests/e2e/security/ -v`. Verify all 11 tenant isolation scenarios. | Security + QA | Tasks 1, 2 | 11/11 scenarios pass |
| 10 | **Validate HITL flow:** Simulate low-confidence extraction, verify review item appears in queue. | AI/LLMOps + QA | Task 7 | Review item created, UI shows it |

**Priority 2 — Stabilize & Harden (Days 5-10)**

| # | Task | Owner (Agent) | Depends On | Deliverable |
|---|------|---------------|------------|-------------|
| 11 | **Create golden dataset:** 5 contracts with manually annotated risks, WBS, stakeholders, coherence. | AI/LLMOps | Task 7 | Dataset + expected output JSON |
| 12 | **Run accuracy regression:** Test golden dataset with real Claude API. Measure precision/recall. | AI/LLMOps | Task 11 | Accuracy baseline documented |
| 13 | **Confirm all CI workflows green:** Push to a PR branch, verify all 6 GitHub Actions pass. | CI/CD | Tasks 3, 5 | All workflows green on PR |
| 14 | **Make Presidio/spacy required:** Add to `requirements.txt` or implement regex fallback. | Security | None | PII anonymization guaranteed |
| 15 | **Add secrets scanning:** Add `gitleaks` to CI pipeline and pre-commit hooks. | Security + CI/CD | None | Secrets scan passing in CI |
| 16 | **Audit CORS configuration:** Review and restrict per environment. | Security | Task 4 | CORS policy documented |
| 17 | **Add streaming progress UI:** Show LangGraph node progress (N1-N16) in frontend during analysis. | Frontend | Task 7 | Users see pipeline progress |

**Priority 3 — Production Readiness (Days 10-20)**

| # | Task | Owner (Agent) | Depends On | Deliverable |
|---|------|---------------|------------|-------------|
| 18 | **Set up Staging environment:** Railway preview + Supabase branch DB + Vercel preview. | CI/CD | Task 13 | Staging URL accessible |
| 19 | **Automate deployments:** Merge to `main` → auto-deploy to Staging. Manual promote to Prod. | CI/CD | Task 18 | CI/CD pipeline green with auto-deploy |
| 20 | **Run performance tests:** Execute Locust load test against Staging. Identify bottlenecks. | QA | Task 18 | P95 latency and throughput baseline |
| 21 | **Document agent terminology:** Clarify "writer"/"reviewer" vs actual agents (Risk, WBS, Coherence, Citation). | AI/LLMOps | None | Updated architecture docs |
| 22 | **Set up LangSmith production tracing:** Configure production project, dashboards, alerts. | AI/LLMOps | Task 19 | LangSmith dashboard live |
| 23 | **Implement scheduled drift checks:** Enable `evaluation-regression.yml` and `scheduled-drift-checks.yml`. | AI/LLMOps + CI/CD | Tasks 11, 19 | Nightly checks running |

---

### Terminology Clarification

The project description references **"writer"** and **"reviewer"** agent roles. Based on codebase analysis, the actual agent architecture is:

| Described Role | Actual Implementation | Function |
|---|---|---|
| "Writer" (inference) | `RiskExtractionAgent`, `WBSExtractionAgent`, Coherence Evaluator | Agents that **generate** structured output from documents |
| "Reviewer" (quality) | `CritiqueNode` (N12), `CitationValidator` (N15), HITL (N13/N14) | Agents/nodes that **validate and critique** generated output |

The "writer"/"reviewer" pattern is correctly implemented as a **generator-critic loop** within the LangGraph pipeline, where extraction nodes produce output and the critique node evaluates quality, triggering retries or human review when confidence is low.

---

### Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Infrastructure never boots correctly | Medium | **Critical** | Priority 0, Task 1 — fix immediately |
| Tests pass with mocks but fail with real LLM | High | High | Golden dataset (Task 11) + weekly real-LLM runs |
| PII leaks to Claude in environments without Presidio | Medium | **Critical** | Task 14 — make Presidio required |
| Cost overrun from unmonitored LLM usage | Low | High | Budget controller exists, needs real-world validation |
| LangGraph state corruption on failure | Medium | High | Test checkpointer (Task 7), add recovery logic |
| Frontend-backend API contract drift | Medium | Medium | Automate orval sync in CI (Task 13) |

---

*Report generated by Lead Engineering & Product Orchestrator — C2Pro Technical Audit Session*
