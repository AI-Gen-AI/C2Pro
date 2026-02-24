# C2Pro — Flow Diagrams (Post-Reorganization)

**Date:** 2026-02-24
**Status:** Current (reflects code after Phases 1–5)
**Reference:** ADR-006, `DEMO_VS_PROD_CONTRACT.md`

> These diagrams supersede all pre-reorganization diagrams found in
> `docs/audits/STRATEGIC_ARCHITECTURE_AUDIT_2026-02-19.md` and
> `docs/audits/PHASE1_*.md`. Those files remain as historical records.

---

## 1. Application Initialization

### 1.1 Provider Tree & MSW Gate

```mermaid
flowchart TD
    A["Next.js renders RootLayout"] --> B["&lt;Providers&gt;"]
    B --> C{"useAppModeStore<br/>selectIsDemoMode"}
    C -- "demo" --> D["mswReady = false<br/>Show: 'Initializing demo...'"]
    D --> E["await import('@/mocks/browser')"]
    E --> F["seedDemoData() — idempotent"]
    F --> G["worker.start({<br/>onUnhandledRequest: 'bypass',<br/>quiet: true})"]
    G --> H["setMswReady(true)"]
    C -- "prod" --> I["mswReady = true<br/>Skip MSW entirely"]
    H --> J["Render provider tree"]
    I --> J
    J --> K["ClerkProvider"]
    K --> L["SentryInit"]
    L --> M["QueryClientProvider"]
    M --> N["AuthSync — Clerk token → Zustand (50s)"]
    N --> O["ThemeProvider"]
    O --> P["AuthProvider"]
    P --> Q["{children}"]
```

### 1.2 Server-Side MSW (instrumentation.ts)

```mermaid
flowchart LR
    A["Next.js startup<br/>instrumentation.ts register()"] --> B{"NEXT_PUBLIC_APP_MODE<br/>=== 'demo'?"}
    B -- No --> C["return — no MSW"]
    B -- Yes --> D["dynamic import('./mocks/node')"]
    D --> E["server.listen({<br/>onUnhandledRequest: 'bypass'})"]
    E --> F["SSR requests intercepted by MSW"]
```

---

## 2. Authentication Flow

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant Clerk
    participant AuthSync
    participant Zustand as useAuthStore
    participant apiClient as Axios apiClient
    participant Backend as FastAPI Backend

    User->>Browser: Visit /login
    Browser->>Clerk: Clerk login UI
    Clerk-->>Browser: JWT access token

    Note over AuthSync: Runs on mount + every 50s
    AuthSync->>Clerk: getToken()
    Clerk-->>AuthSync: token
    AuthSync->>Zustand: setAuth({ token, tenantId })

    User->>Browser: Navigate to /projects
    Browser->>apiClient: GET /api/v1/projects
    Note over apiClient: Request interceptor
    apiClient->>Zustand: getState().token, .tenantId
    Zustand-->>apiClient: token, tenantId
    apiClient->>Backend: GET /api/v1/projects<br/>Authorization: Bearer {token}<br/>X-Tenant-ID: {tenantId}

    Note over Backend: TenantIsolationMiddleware
    Backend->>Backend: Validate JWT → extract tenant_id
    Backend->>Backend: Validate tenant exists in DB
    Backend->>Backend: SET LOCAL app.current_tenant = '{tenant_id}'
    Backend-->>apiClient: 200 { items: [...] }
    apiClient-->>Browser: Project list

    Note over apiClient: Response interceptor (error path)
    Backend-->>apiClient: 401 Unauthorized
    apiClient->>Zustand: clear()
    apiClient->>Browser: redirect → /login
```

---

## 3. Data Flow — Page Patterns

### 3.1 Server Component Pattern (e.g., Dashboard, Documents, Coherence)

```mermaid
flowchart TD
    A["Browser requests /(app)/"] --> B["Next.js Server"]
    B --> C["page.tsx — async server component"]
    C --> D["ProjectsService.getProjects()"]
    D --> E["fetch() with revalidate: 60"]
    E --> F{"NEXT_PUBLIC_APP_MODE?"}
    F -- demo --> G["MSW server intercepts<br/>(instrumentation.ts)"]
    G --> H["Return seed data from @mswjs/data"]
    F -- prod --> I["FastAPI /api/v1/projects"]
    I --> J["PostgreSQL + RLS"]
    J --> I
    I --> K["200 JSON response"]
    H --> L["Server renders HTML"]
    K --> L
    L --> M["Stream HTML to browser<br/>Zero client JS for data fetch"]
```

### 3.2 Client Component Pattern (e.g., Alerts, Stakeholders, RACI)

```mermaid
flowchart TD
    A["Browser mounts Client Component"] --> B["useAlerts() / useRaci() / etc."]
    B --> C["useState + useEffect"]
    C --> D["apiClient.get('/api/v1/alerts')"]
    D --> E["Axios request interceptor<br/>attaches Bearer + X-Tenant-ID"]
    E --> F{"NEXT_PUBLIC_APP_MODE?"}
    F -- demo --> G["MSW Service Worker intercepts"]
    G --> H["Handler reads @mswjs/data<br/>Returns JSON"]
    F -- prod --> I["Real HTTP to backend"]
    I --> J["FastAPI router → use case → DB"]
    J --> I
    H --> K["Component setState(data)"]
    I --> K
    K --> L["React re-renders with data"]
```

### 3.3 React Query Pattern (e.g., Projects list with caching)

```mermaid
flowchart TD
    A["Component mounts"] --> B["useProjects()"]
    B --> C["useQuery({ queryKey: ['projects'],<br/>queryFn: ProjectsService.getProjects })"]
    C --> D{"Cache fresh?<br/>(staleTime: 5min)"}
    D -- Yes --> E["Return cached data<br/>No network request"]
    D -- No --> F["ProjectsService.getProjects()"]
    F --> G["apiClient.get('/projects')"]
    G --> H["Network → MSW or Backend"]
    H --> I["Update cache + return data"]
    I --> J["Component renders"]
    E --> J

    Note over C: Background refetch<br/>on window focus
```

---

## 4. Demo vs Production Mode

```mermaid
flowchart TD
    subgraph env["Environment Configuration"]
        A["NEXT_PUBLIC_APP_MODE"]
    end

    A -- "'demo'" --> B["Demo Mode"]
    A -- "unset / other" --> C["Production Mode"]

    subgraph B["Demo Mode"]
        D["providers.tsx: lazy import mocks/browser"]
        D --> E["seedDemoData() → @mswjs/data factory<br/>1 tenant, 1 user, 6 projects, 8 docs,<br/>3 clauses, 8 alerts, 7 stakeholders"]
        E --> F["worker.start() registers Service Worker"]
        F --> G["All fetch() intercepted by MSW"]
        G --> H["12 handler files, ~50 endpoints"]
        H --> I["DemoBanner visible"]
    end

    subgraph C["Production Mode"]
        J["providers.tsx: skip MSW init"]
        J --> K["mswReady = true immediately"]
        K --> L["All fetch() go to NEXT_PUBLIC_API_URL"]
        L --> M["FastAPI backend → PostgreSQL"]
        M --> N["DemoBanner hidden"]
    end

    style B fill:#fef3c7,stroke:#f59e0b
    style C fill:#d1fae5,stroke:#10b981
```

---

## 5. Backend Request Pipeline

```mermaid
flowchart TD
    A["HTTP Request"] --> B["CORSMiddleware"]
    B --> C["TenantIsolationMiddleware"]
    C --> D{"Path in PUBLIC_PATHS?<br/>/health, /docs, /auth/*"}
    D -- Yes --> E["Skip auth — pass through"]
    D -- No --> F["Extract JWT from Authorization header"]
    F --> G{"Valid JWT?"}
    G -- No --> H["401 Unauthorized"]
    G -- Yes --> I["Extract tenant_id from claims"]
    I --> J["Validate tenant exists in DB<br/>(raw session, no RLS)"]
    J --> K{"Tenant exists?"}
    K -- No --> L["403 Forbidden"]
    K -- Yes --> M["request.state.tenant_id = tenant_id"]
    M --> N["RateLimitMiddleware"]
    N --> O["RequestLoggingMiddleware"]
    O --> P["FastAPI Router"]
    P --> Q["Depends(get_session)"]
    Q --> R["SET LOCAL app.current_tenant = '{tenant_id}'"]
    R --> S["Use Case executes"]
    S --> T["Repository queries<br/>(RLS filters by tenant_id)"]
    T --> U["200 JSON Response"]

    E --> P
```

---

## 6. Multi-Tenancy (5 Layers)

```mermaid
flowchart TD
    subgraph L1["Layer 1 — Middleware"]
        A["TenantIsolationMiddleware<br/>JWT → tenant_id extraction + validation"]
    end

    subgraph L2["Layer 2 — Request State"]
        B["request.state.tenant_id<br/>Available to all route handlers"]
    end

    subgraph L3["Layer 3 — Database Session"]
        C["get_session(request)<br/>SET LOCAL app.current_tenant = tenant_id"]
    end

    subgraph L4["Layer 4 — PostgreSQL RLS"]
        D["Row-Level Security policies<br/>WHERE tenant_id = current_setting('app.current_tenant')"]
    end

    subgraph L5["Layer 5 — Cache"]
        E["TenantScopedCache<br/>key = '{tenant_id}:{cache_key}'"]
    end

    A --> B --> C --> D
    B --> E

    style L1 fill:#fee2e2,stroke:#ef4444
    style L4 fill:#fee2e2,stroke:#ef4444
```

---

## 7. Module Architecture (Hexagonal Pattern)

```mermaid
flowchart LR
    subgraph Inbound["Inbound Adapters"]
        A["FastAPI Router<br/>(HTTP)"]
    end

    subgraph App["Application Layer"]
        B["Use Case"]
        C["DTOs / Schemas"]
    end

    subgraph Domain["Domain Layer"]
        D["Entities<br/>(@dataclass)"]
        E["Domain Services"]
    end

    subgraph Ports["Ports (Interfaces)"]
        F["IRepository<br/>(ABC / Protocol)"]
    end

    subgraph Outbound["Outbound Adapters"]
        G["SQLAlchemy<br/>Repository"]
        H["AI Client<br/>(Anthropic)"]
        I["Event Bus"]
    end

    A -- "Depends()" --> B
    B --> D
    B --> E
    B --> F
    F -.-> G
    F -.-> H
    F -.-> I

    style Domain fill:#ede9fe,stroke:#7c3aed
    style Ports fill:#fef3c7,stroke:#f59e0b
```

---

## 8. Bounded Context Map

```mermaid
flowchart TD
    subgraph SK["Shared Kernel"]
        SK1["enums.py<br/>AlertSeverity, AlertStatus,<br/>RACIRole, WBSItemType"]
        SK2["dtos.py<br/>WBSItemDTO"]
    end

    subgraph PROJ["Projects"]
        P1["Project entity<br/>(dataclass — canonical)"]
    end

    subgraph DOC["Documents"]
        D1["Document, Clause"]
    end

    subgraph ALR["Alerts"]
        A1["Alert routing<br/>(GREEN phase)"]
    end

    subgraph COH["Coherence"]
        C1["CoherenceEngineV2<br/>Rules + Scoring"]
    end

    subgraph ANA["Analysis"]
        AN1["LangGraph Workflow<br/>AI Agents"]
    end

    subgraph STK["Stakeholders"]
        S1["Stakeholder, RACI"]
    end

    subgraph PROC["Procurement"]
        PR1["WBS, BOM"]
    end

    subgraph DI["Decision Intelligence"]
        DI1["Orchestration<br/>5 Protocol ports"]
    end

    SK1 -.-> COH
    SK1 -.-> ANA
    SK1 -.-> STK
    SK2 -.-> PROC

    PROJ --> DOC
    DOC --> COH
    COH --> ALR
    ANA --> COH
    DI1 --> DOC
    DI1 --> COH
    DI1 --> ANA

    style SK fill:#fef9c3,stroke:#ca8a04
    style PROJ fill:#d1fae5,stroke:#10b981
    style DOC fill:#d1fae5,stroke:#10b981
    style ALR fill:#d1fae5,stroke:#10b981
    style COH fill:#d1fae5,stroke:#10b981
    style ANA fill:#fef3c7,stroke:#f59e0b
    style STK fill:#fef3c7,stroke:#f59e0b
    style PROC fill:#fef3c7,stroke:#f59e0b
    style DI fill:#fef3c7,stroke:#f59e0b
```

**Legend:** Green = router active in `main.py` | Yellow = router exists but commented out

---

## 9. LangGraph Workflow (Analysis)

```mermaid
flowchart TD
    A["Entry: router_node"] --> B{"doc_type?"}
    B -- contract --> C["risk_extractor_node<br/>(Claude agent)"]
    B -- technical_spec --> D["wbs_extractor_node<br/>(Claude agent)"]
    B -- budget --> E["budget_parser_node<br/>(Claude agent)"]
    C --> F["critique_node"]
    D --> F
    E --> F
    F --> G{"confidence_score > threshold?"}
    G -- High --> H["save_to_db_node"]
    G -- Low --> I["human_interrupt_node<br/>(HITL)"]
    I --> J["Human reviews + approves"]
    J --> H
    H --> K["END"]

    subgraph State["ProjectState"]
        S1["document_text, doc_type"]
        S2["extracted_risks, extracted_wbs"]
        S3["confidence_score"]
        S4["human_approval_required"]
    end

    style State fill:#f0f9ff,stroke:#3b82f6
```

**Checkpointing:** PostgreSQL via `AsyncPostgresSaver` — flows are resumable across requests.

---

## 10. Frontend Component Tree (App Layout)

```mermaid
flowchart TD
    A["RootLayout — app/layout.tsx"] --> B["Providers — app/providers.tsx"]
    B --> C["(app)/layout.tsx"]

    C --> D{"isDemoMode?"}
    D -- Yes --> E["DemoBanner"]
    D -- No --> F[" "]

    C --> G["AppSidebar"]
    C --> H["AppHeader"]
    C --> I["main"]
    I --> J["loading.tsx — Skeleton"]
    I --> K["error.tsx — Error Boundary"]
    I --> L["Page content"]

    subgraph Pages["Page Routes"]
        L --> M["/(app)/ — Dashboard"]
        L --> N["/projects — List"]
        L --> O["/projects/[id] — Overview"]
        L --> P["/projects/[id]/alerts"]
        L --> Q["/projects/[id]/coherence"]
        L --> R["/projects/[id]/documents"]
        L --> S["/projects/[id]/evidence"]
        L --> T["/alerts — Global"]
        L --> U["/documents — Global"]
        L --> V["/stakeholders"]
        L --> W["/raci"]
        L --> X["/observability"]
    end

    style Pages fill:#f0f9ff,stroke:#3b82f6
```

---

## 11. MSW Handler Registration

```mermaid
flowchart LR
    subgraph handlers["mocks/handlers/index.ts"]
        H1["healthHandler (1)"]
        H2["demoDataHandlers (16)"]
        H3["alertReviewHandlers (9)"]
        H4["uploadHandlers (3)"]
        H5["processingStreamHandler (1)"]
        H6["cookieConsentHandlers (3)"]
        H7["legalDisclaimerHandlers (2)"]
        H8["onboardingSampleProjectHandlers (4)"]
        H9["s312A11yResponsiveHandlers (5)"]
        H10["documentViewerHandlers (2)"]
        H11["observabilityHandlers (2)"]
        H12["raciHandlers (2)"]
    end

    subgraph browser["mocks/browser.ts"]
        B1["seedDemoData()"]
        B2["setupWorker(...handlers)"]
    end

    subgraph data["mocks/data/"]
        D1["db.ts — @mswjs/data factory"]
        D2["seed.ts — seedDemoData()"]
    end

    D2 --> D1
    B1 --> D2
    handlers --> B2

    style handlers fill:#fef9c3,stroke:#ca8a04
    style data fill:#ede9fe,stroke:#7c3aed
```

---

## 12. Endpoint Parity (Frontend ↔ Backend)

```mermaid
flowchart LR
    subgraph FE["Frontend Hooks/Services"]
        F1["useProjects"]
        F2["useProjectDocuments"]
        F3["useProjectAlerts"]
        F4["useAlerts"]
        F5["useStakeholders"]
        F6["useRaci"]
        F7["useProjectOverview"]
        F8["useDocumentEntities"]
        F9["Observability page"]
    end

    subgraph MSW["MSW Handlers<br/>(demo mode)"]
        M1["GET /projects ✓"]
        M2["GET /projects/:id/documents ✓"]
        M3["GET /projects/:id/alerts ✓"]
        M4["GET /alerts ✓"]
        M5["GET /stakeholders ✓"]
        M6["GET /raci ✓"]
        M7["GET /coherence/dashboard/:id ✓"]
        M8["GET /documents/:id/entities ✓"]
        M9["GET /observability/status ✓"]
    end

    subgraph BE["Backend Routers<br/>(prod mode)"]
        B1["projects_router ✓"]
        B2["documents_router ✓"]
        B3["alerts_router ✓"]
        B4["alerts_router ✓"]
        B5["stakeholders_router ⚠ commented out"]
        B6["raci_router ⚠ commented out"]
        B7["coherence_dashboard_router ✓"]
        B8["— ✗ not implemented"]
        B9["observability_router ✓"]
    end

    F1 --> M1 --> B1
    F2 --> M2 --> B2
    F3 --> M3 --> B3
    F4 --> M4 --> B4
    F5 --> M5 --> B5
    F6 --> M6 --> B6
    F7 --> M7 --> B7
    F8 --> M8 --> B8
    F9 --> M9 --> B9

    style B5 fill:#fef3c7,stroke:#f59e0b
    style B6 fill:#fef3c7,stroke:#f59e0b
    style B8 fill:#fee2e2,stroke:#ef4444
```

**Legend:** Green = fully implemented | Yellow = router exists, not wired | Red = MSW-only
