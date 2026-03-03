# ADR-006: Post-Reorganization Architecture (Phases 1–5)

**Date:** 2026-02-24
**Status:** Accepted
**Scope:** C2Pro Monorepo (`apps/web`, `apps/api`)
**Reference:** `STRATEGIC_ARCHITECTURE_AUDIT_2026-02-19.md`, `DEMO_VS_PROD_CONTRACT.md`

## Context

The strategic architecture audit of 2026-02-19 identified critical structural problems:

- **P1 — Demo/Prod contamination:** Mock data (`MOCK_PROJECT_DB`, `const mockAlerts`, `lib/mockData.ts`) was embedded in production source code. There was no reliable way to distinguish demo UI from production UI.
- **P2 — Duplicated frontend structures:** Three competing route trees (`app/dashboard/`, `app/demo/`, `app/(dashboard)/`), two parallel component directories (`components/` vs `src/components/features/`), and inconsistent import paths.
- **P3 — Violated bounded contexts:** Backend modules imported directly from each other's domain layers (`from src.documents.domain.models import Clause` inside analysis module). Shared enums were copy-pasted across modules.
- **P4 — Legacy engine coexistence:** `coherence/engine.py` (v1) and `coherence/engine_v2.py` existed side by side with unclear ownership.
- **P5 — Incomplete hexagonal wiring:** `_DefaultExtractionService` and similar stubs returned fictitious data silently, masking missing integrations.

A 5-phase reorganization was executed (Phases 1–5, tracked in `REORGANIZATION_PLAN_CHECKLIST.md`).

## Decision

We adopt the architecture described below as the canonical state of the codebase after reorganization. All future work must conform to these structures.

---

### 1. Demo/Production Separation

**Principle:** Demo is a _mode_, not a route. A single environment variable controls everything.

```
NEXT_PUBLIC_APP_MODE=demo   → MSW intercepts all HTTP calls
NEXT_PUBLIC_APP_MODE=<else> → Requests reach real backend API
```

**Enforcement points (4 gates):**

| Gate | File | Mechanism |
|------|------|-----------|
| Server-side MSW | `instrumentation.ts` | Early return if not demo; dynamic `Function("path", "return import(path)")` import |
| Client-side MSW | `app/providers.tsx` | `useAppModeStore(selectIsDemoMode)` → lazy `await import("@/mocks/browser")` → `worker.start()` |
| UI banner | `components/layout/DemoBanner.tsx` | Conditionally rendered via `selectIsDemoMode` |
| Centralized flag | `config/env.ts` | `IS_DEMO: process.env.NEXT_PUBLIC_APP_MODE === "demo"` |

**Mock data location:** `apps/web/mocks/` only. Zero mock data in `lib/`, `components/`, or page files.

**Tree-shaking:** All MSW imports are dynamic. No static `import ... from "msw"` exists outside `mocks/`. Production bundles exclude MSW entirely.

---

### 2. Frontend Architecture

#### 2.1 Route Structure

```
app/
├── (auth)/login, register       # Public auth routes
├── (app)/                       # Protected routes (layout: sidebar + header)
│   ├── page.tsx                 # Dashboard (server component)
│   ├── projects/                # Project CRUD + sub-pages
│   │   └── [id]/(alerts, coherence, documents, evidence, analysis)
│   ├── alerts/                  # Global alert view
│   ├── documents/               # Global document library
│   ├── evidence/                # Evidence review entry
│   ├── stakeholders/            # Stakeholder matrix
│   ├── raci/                    # RACI matrix
│   ├── observability/           # System health
│   ├── settings/                # User preferences
│   ├── loading.tsx              # Shared skeleton
│   └── error.tsx                # Shared error boundary
├── global-error.tsx             # Root error boundary
└── providers.tsx                # Provider tree + MSW gate
```

No `app/dashboard/`, no `app/demo/`. Eliminated in Phase 2.

#### 2.2 Data Flow

Every page follows one of two patterns:

| Pattern | When | Example |
|---------|------|---------|
| **Server Component → Service** | Initial loads, list pages | `ProjectsService.getProjects()` in async `page.tsx` |
| **Client Component → Hook → apiClient** | Interactive pages | `useProjectAlerts(id)` → `apiClient.get(...)` |

The same `apiClient` (Axios) and services are used in both demo and production. In demo mode, MSW intercepts at the network level; no code path differs.

#### 2.3 Component Organization

```
components/
├── ui/            # Radix UI primitives (button, card, dialog, etc.)
├── features/      # Domain components (alerts/, coherence/, documents/, evidence/, etc.)
├── layout/        # AppSidebar, AppHeader, DemoBanner
└── providers/     # AuthSync, SentryInit
```

No `src/components/`. Eliminated in Phase 2; 70 files consolidated, 53 imports updated.

#### 2.4 State Management

| Layer | Tool | Examples |
|-------|------|---------|
| Server state | React Query (`@tanstack/react-query`) | Caching, refetch, background sync |
| Client state | Zustand | `useAuthStore`, `useAppModeStore`, `useFilterStore`, `useSidebarStore` |
| Auth context | React Context + Clerk | `AuthProvider` wraps Clerk → exposes `useAuth()` |

#### 2.5 Provider Hierarchy

```
<Providers>                          ← MSW gate (blocks render until ready in demo)
  <ClerkProvider>                    ← Authentication
    <SentryInit />                   ← Error tracking
    <QueryClientProvider>            ← React Query cache
      <AuthSync>                     ← Clerk token → Zustand sync (50s interval)
        <ThemeProvider>              ← Dark/light mode
          <AuthProvider>             ← Combined auth context
            {children}
```

#### 2.6 MSW Handler Coverage

12 handler files, ~50 endpoints. Coverage verified page-by-page (Task 5.2):

| Handler file | Endpoints | Domain |
|-------------|-----------|--------|
| `demo-data.ts` | 16 | Projects, documents, alerts, stakeholders, WBS, coherence, auth |
| `alert-review.ts` | 9 | Alert approve/reject/sync/undo, coherence-sync |
| `uploads.ts` | 3 | Chunked upload pipeline |
| `processing-stream.ts` | 1 | SSE processing stages |
| `cookie-consent.ts` | 3 | GDPR consent |
| `legal-disclaimer.ts` | 2 | Gate-8 legal |
| `onboarding-sample-project.ts` | 4 | Onboarding flow |
| `document-viewer.ts` | 2 | PDF download, entity extraction |
| `observability.ts` | 2 | System status, analyses |
| `raci.ts` | 2 | RACI matrix |
| `s3-12-a11y-responsive.ts` | 5 | Accessibility testing |
| `health.ts` | 1 | Health check |

Seed data: 1 tenant, 1 user, 6 projects, 8 documents, 3 clauses, 8 alerts, 7 stakeholders, 2 WBS items.

---

### 3. Backend Architecture

#### 3.1 Module Layout (Hexagonal)

Each bounded context follows Ports & Adapters:

```
module/
├── domain/          # Pure business logic — no framework imports
│   ├── models.py    # @dataclass entities
│   └── exceptions.py
├── ports/           # Abstract interfaces (ABC or Protocol)
│   └── *_repository.py
├── application/     # Use cases + orchestration
│   ├── use_cases/
│   ├── dtos.py
│   └── dependencies.py  # FastAPI Depends() factories
└── adapters/        # Implementations
    ├── http/router.py          # FastAPI APIRouter
    └── persistence/*_repository.py  # SQLAlchemy
```

#### 3.2 Bounded Contexts

| Context | Module Path | Router Status | Key Entities |
|---------|-------------|---------------|--------------|
| **Projects** | `src/projects/` | Active | Project (dataclass, canonical) |
| **Documents** | `src/documents/` | Active | Document, Clause |
| **Alerts** | `src/alerts/` | Active | Alert (in-memory, GREEN phase) |
| **Coherence** | `src/coherence/` | Active | CoherenceResult, CoherenceRule |
| **Analysis** | `src/analysis/` | Router commented out | GraphNode, AnalysisRecord |
| **Stakeholders** | `src/stakeholders/` | Router commented out | Stakeholder, RaciAssignment |
| **Procurement** | `src/procurement/` | Router commented out | WBSItem, BOM |
| **Decision Intelligence** | `src/modules/decision_intelligence/` | Active | DecisionOrchestrationService |
| **Bulk Operations** | `src/bulk_operations/` | Active | Bulk review/delete |

#### 3.3 Shared Kernel

Located at `src/shared_kernel/`:

- **`enums.py`**: `AlertSeverity`, `AlertStatus`, `RACIRole`, `WBSItemType` — canonical definitions re-exported by owning modules for backward compatibility.
- **`dtos.py`**: `WBSItemDTO` (frozen dataclass) — cross-context transfer object with validation.

**Rule:** Modules import shared types from `shared_kernel`, never from another module's `domain/`.

#### 3.4 Cross-Boundary Communication

| Mechanism | Used For |
|-----------|----------|
| Shared kernel enums/DTOs | Type alignment across modules |
| Protocol-based ports | `analysis/ports/graph_entities.py` defines `ClauseView`, `WBSTaskView`, `StakeholderView` as Protocols — satisfied by structural typing, no domain imports |
| Event bus (in-memory) | `core/events/event_bus.py` — async pub/sub with deep-copy isolation |

#### 3.5 Core Infrastructure

| Component | Location | Purpose |
|-----------|----------|---------|
| Database | `core/database.py` | SQLAlchemy async + PostgreSQL RLS (`app.current_tenant` GUC) |
| Auth | `core/auth/` | JWT (access + refresh), User/Tenant models, `get_current_user` dependency |
| Middleware | `core/middleware/` | `TenantIsolationMiddleware` (JWT → tenant context), `RateLimitMiddleware`, `RequestLoggingMiddleware` |
| Cache | `core/cache.py` | `TenantScopedCache` — keys prefixed with tenant_id to prevent cross-tenant leakage |
| Observability | `core/observability/` | `structlog`, Prometheus metrics, Sentry |
| MCP | `core/mcp/` | Model Context Protocol server for schema discovery |

#### 3.6 Multi-Tenancy (5 layers)

1. **Database:** PostgreSQL RLS policies filter by `tenant_id`; `SET LOCAL app.current_tenant` in every session
2. **Middleware:** `TenantIsolationMiddleware` extracts tenant from JWT, validates existence, sets `request.state.tenant_id`
3. **Session:** `get_session(request)` auto-sets GUC from request state
4. **Cache:** `TenantScopedCache._scoped_key(tenant_id, key)` prevents cross-tenant reads
5. **Background tasks:** `TenantContext` (ContextVar) + `get_session_with_tenant(tenant_id)` for async-safe isolation

#### 3.7 Coherence Engine

Only `engine_v2.py` exists. `engine.py` (legacy v1) eliminated in Phase 3. `CoherenceEngine` is an alias for `CoherenceEngineV2`.

Features: deterministic rule evaluation, category-specific rules (budget, legal, scope, technical, time), anti-gaming detection, optional LLM rule enhancement.

#### 3.8 LangGraph Integration

**Workflow** (`analysis/adapters/graph/workflow.py`):
```
router_node → risk/wbs/budget extractors → critique_node → [save | human_interrupt] → END
```

**State:** `ProjectState` with document text, extracted risks/WBS, confidence score, human approval flag.

**Checkpointing:** PostgreSQL via `AsyncPostgresSaver` for resumable flows.

---

### 4. API Contract (Frontend ↔ Backend)

**Frontend base URL:** `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api/v1`)

**Backend prefix:** `settings.api_v1_prefix = "/api/v1"` (all routers registered with this prefix)

**Endpoint parity (verified Task 5.3):**

| Status | Count | Examples |
|--------|-------|---------|
| **Implemented** | 16 | auth (5), projects (2), documents (3), alerts (1), coherence dashboard (1), observability (2), stakeholders/project (1), WBS (1) |
| **Router exists, not wired** | 4 | Stakeholders flat query, RACI global, procurement — commented out in `main.py` |
| **MSW-only (no backend)** | 4 | `/documents/:id/clauses`, `/documents/:id/entities`, `/alerts?document_id=`, alert PATCH/DELETE |

**Coherence dashboard** is registered at `/api/coherence/dashboard/:projectId` (outside `/api/v1` prefix — direct mount for E2E test compatibility).

---

### 5. Testing Architecture

| Layer | Tool | Count | Scope |
|-------|------|-------|-------|
| Unit + Component | Vitest + RTL | 132 files | Isolated components, hooks, stores |
| Integration | Vitest + MSW | 48 files | Hook→API flow, data transformations |
| E2E | Playwright | 18 specs | Full page flows, SSR, accessibility |

**Result after reorganization:** 162/162 files pass, 295/295 tests pass.

---

### 6. Eliminated Artifacts

| Artifact | Phase | Reason |
|----------|-------|--------|
| `app/dashboard/` | 2.5 | Duplicate of `app/(app)/` |
| `app/demo/` | 2.6 | Demo is a mode, not a route |
| `src/components/` | 2.3 | Consolidated into `components/` |
| `lib/mockData.ts` | 2.8 | Dead code (303 lines, zero imports) |
| `coherence/engine.py` | 3.5 | Superseded by `engine_v2.py` |
| `_Default*Service` stubs | 3.2 | Silent failures masked missing integrations |
| `MOCK_PROJECT_DB`, `MOCK_SCORE_DB` | 3.1 | Production code contained test data |
| `projects/domain/project.py` | 3.4 | Duplicate Pydantic model (canonical is dataclass) |
| Hardcoded `const mock*` in pages | 4.8 | Replaced by hooks calling API (MSW intercepts in demo) |

---

## Consequences

### Positive

- **Single source of truth:** One route tree, one component directory, one entity definition per domain concept.
- **Clean demo/prod boundary:** Environment variable controls mode; MSW intercepts transparently. No code path diverges between modes.
- **Testable modules:** Hexagonal architecture + Protocol-based ports enable isolated testing. Each bounded context can be tested without starting the full app.
- **Safe multi-tenancy:** 5-layer enforcement (DB RLS, middleware, session, cache, context var) prevents cross-tenant data leakage.
- **No silent failures:** `_Default*` stubs replaced by explicit `TypeError`/`NotImplementedError`. Missing integrations surface immediately.

### Negative / Trade-offs

- **8 backend endpoints still missing:** Frontend calls endpoints that only MSW handles. Production mode will show errors for evidence viewer, document clauses, and alert-by-document features until backend catches up.
- **3 routers commented out:** Stakeholders, RACI, and procurement routers exist but are not wired in `main.py`. Enabling them requires completing their GREEN phase implementations.
- **Boilerplate overhead:** Hexagonal architecture requires `ports/`, `adapters/`, `application/`, `domain/` directories per module — more files for the same feature.
- **Dual import patterns:** Some hooks use React Query (`useProjects`), others use raw `useState` + `apiClient` (`useAlerts`). Inconsistency should be normalized over time.

### Mitigations

- Backend gaps are tracked in `REORGANIZATION_PLAN_CHECKLIST.md` (Tasks 5.6–5.8).
- The observability router prefix mismatch was fixed during this audit (Task 5.3).
- `DEMO_VS_PROD_CONTRACT.md` enforces the 24 rules (R1–R24) for any future feature work.

---

## Alternatives Considered

1. **Keep separate demo route tree (`/demo/`):** Rejected — led to duplicate pages and divergent UX.
2. **Inline mock data with feature flags:** Rejected — mixes concerns, pollutes production bundle.
3. **Microservices instead of modular monolith:** Rejected — operational overhead not justified at current scale.
4. **Single shared `types/` directory for backend:** Rejected — violates bounded context isolation. Shared kernel is intentionally minimal.

---

Last Updated: 2026-02-24

Changelog:
- 2026-02-24: Initial ADR documenting post-reorganization architecture after Phases 1–5.
