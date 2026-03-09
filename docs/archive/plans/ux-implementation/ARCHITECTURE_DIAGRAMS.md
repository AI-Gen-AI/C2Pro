# C2Pro UX Implementation - Architecture Diagrams

## Overview

This document provides visual architecture diagrams for the WBS Management and Procurement Intelligence modules.

---

## 1. System Context

```mermaid
C4Context
    title C2Pro System Context - WBS & Procurement

    Person(finalUser, "Final User", "Project team member viewing project data")
    Person(tenantAdmin, "Tenant Admin", "Manages projects and team")
    Person(c2proAdmin, "C2Pro Admin", "System administrator")

    System_Boundary(c2pro, "C2Pro Platform") {
        System(webApp, "C2Pro Web Application", "Next.js 15 + React 19")
        System(api, "C2Pro API", "FastAPI + Python")
        System(ai, "AI Core", "LangGraph + LLM")
    }

    System_Ext(email, "Email Service", "Notifications")
    System_Ext(storage, "Cloud Storage", "R2 Document Storage")

    Rel(finalUser, webApp, "Views projects, documents, WBS, procurement", "HTTPS")
    Rel(tenantAdmin, webApp, "Manages WBS, procurement, users", "HTTPS")
    Rel(c2proAdmin, webApp, "System configuration, analytics", "HTTPS")

    Rel(webApp, api, "REST API", "JSON/HTTPS")
    Rel(api, ai, "AI orchestration", "gRPC/HTTP")
    Rel(api, email, "Send notifications", "SMTP/API")
    Rel(api, storage, "Store/retrieve documents", "S3 API")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## 2. Container Diagram - WBS Module

```mermaid
C4Container
    title WBS Module - Container Architecture

    Person(user, "User", "Views or manages WBS")

    Container_Boundary(frontend, "Frontend - Next.js App") {
        Container(wbsPage, "WBS Page", "Next.js Server Component", "/projects/[id]/wbs")
        Container(wbsTree, "WBSTree", "React Client Component", "Interactive tree")
        Container(wbsDetail, "WBSItemDetail", "React Client Component", "Item detail panel")
        Container(wbsStore, "WBS Store", "Zustand", "State management")
        Container(orval, "Orval Hooks", "Generated", "API integration")
    }

    Container_Boundary(backend, "Backend - FastAPI") {
        Container(wbsRouter, "WBS Router", "FastAPI Router", "HTTP endpoints")
        Container(wbsUC, "WBS Use Cases", "Python", "Orchestration logic")
        Container(wbsDomain, "WBS Domain", "Python", "Business rules")
        Container(wbsRepo, "WBS Repository", "Python", "Data access")
    }

    ContainerDb(postgres, "PostgreSQL", "PostgreSQL 15+", "WBS items, hierarchy")

    Rel(user, wbsPage, "Navigates to", "Browser")
    Rel(wbsPage, wbsTree, "Renders", "Props")
    Rel(wbsTree, wbsStore, "Reads/Updates", "State")
    Rel(wbsTree, orval, "API calls", "React Query")
    Rel(orval, wbsRouter, "HTTP requests", "REST/JSON")
    Rel(wbsRouter, wbsUC, "Delegates", "Function calls")
    Rel(wbsUC, wbsDomain, "Uses", "Domain methods")
    Rel(wbsDomain, wbsRepo, "Persists", "Port interface")
    Rel(wbsRepo, postgres, "SQL queries", "SQLAlchemy")
```

---

## 3. Container Diagram - Procurement Module

```mermaid
C4Container
    title Procurement Module - Container Architecture

    Person(procurement, "Procurement Lead", "Manages material orders")

    Container_Boundary(frontend, "Frontend - Next.js App") {
        Container(procPage, "Procurement Page", "Next.js", "/projects/[id]/procurement")
        Container(bomTable, "BOMTable", "React", "Bill of materials")
        Container(ltCalc, "LeadTimeCalculator", "React", "Lead time widget")
        Container(procTimeline, "ProcurementTimeline", "React", "Gantt chart")
        Container(procStore, "Procurement Store", "Zustand", "State management")
    }

    Container_Boundary(backend, "Backend - FastAPI") {
        Container(procRouter, "Procurement Router", "FastAPI", "HTTP endpoints")
        Container(bomGen, "BOM Generator", "Python", "Creates BOM from WBS")
        Container(ltService, "Lead Time Service", "Python", "Calculates lead times")
        Container(planGen, "Plan Generator", "Python", "Creates procurement plan")
        Container(procRepo, "Procurement Repository", "Python", "Data access")
    }

    ContainerDb(postgres, "PostgreSQL", "PostgreSQL", "BOM, lead times, plans")

    Rel(procurement, procPage, "Navigates to", "Browser")
    Rel(procPage, bomTable, "Renders", "Props")
    Rel(procPage, ltCalc, "Renders", "Props")
    Rel(procPage, procTimeline, "Renders", "Props")
    Rel(bomTable, procStore, "Reads", "State")
    Rel(ltCalc, procRouter, "API calls", "REST")
    Rel(procRouter, bomGen, "Generates BOM", "Function")
    Rel(procRouter, ltService, "Calculates lead times", "Function")
    Rel(procRouter, planGen, "Generates plan", "Function")
    Rel(bomGen, procRepo, "Stores BOM", "Repository")
    Rel(ltService, procRepo, "Stores calculations", "Repository")
    Rel(planGen, procRepo, "Stores plan", "Repository")
    Rel(procRepo, postgres, "SQL queries", "SQLAlchemy")
```

---

## 4. Component Diagram - WBS Tree

```mermaid
C4Component
    title WBSTree Component - Internal Structure

    Container_Boundary(wbsTree, "WBSTree Component") {
        Component(treeRoot, "TreeRoot", "React", "Root container")
        Component(treeNode, "TreeNode", "React", "Recursive node renderer")
        Component(nodeCard, "WBSItemCard", "React", "Item display card")
        Component(dragDrop, "DragDropProvider", "React DnD", "Drag & drop context")
        Component(expander, "ExpanderButton", "React", "Expand/collapse toggle")
        Component(alertBadge, "AlertBadge", "React", "Coherence alert indicator")
    }

    Container_Boundary(hooks, "Custom Hooks") {
        Component(useWBS, "useWBS", "Hook", "WBS data fetching")
        Component(usePermissions, "useWbsPermissions", "Hook", "Permission checks")
        Component(useDragDrop, "useDragDrop", "Hook", "D&D handlers")
    }

    Container(zustand, "Zustand Store", "State Management", "WBS state")

    Rel(treeRoot, treeNode, "Renders children", "Props")
    Rel(treeNode, treeNode, "Recurses", "Props (children)")
    Rel(treeNode, nodeCard, "Renders", "Props")
    Rel(treeNode, expander, "Renders", "Props")
    Rel(treeNode, alertBadge, "Renders (conditional)", "Props")
    Rel(treeRoot, dragDrop, "Wraps", "Context")
    Rel(treeNode, useWBS, "Uses", "Hook")
    Rel(treeNode, usePermissions, "Uses", "Hook")
    Rel(treeNode, useDragDrop, "Uses", "Hook")
    Rel(useWBS, zustand, "Reads/Writes", "State")
```

---

## 5. Component Diagram - Procurement Dashboard

```mermaid
C4Component
    title Procurement Dashboard - Internal Structure

    Container_Boundary(dashboard, "Procurement Dashboard") {
        Component(tabs, "TabNavigation", "React", "BOM | Lead Times | Plan | Alerts")

        Container_Boundary(bomTab, "BOM Tab") {
            Component(bomTable, "BOMTable", "React", "Sortable table")
            Component(costSummary, "CostSummary", "React", "Total cost display")
            Component(wbsFilter, "WBSFilter", "React", "Filter by WBS item")
        }

        Container_Boundary(ltTab, "Lead Times Tab") {
            Component(ltWidget, "LeadTimeWidget", "React", "Calculator form")
            Component(ltResults, "LeadTimeResults", "React", "Results display")
            Component(incotermSel, "IncotermSelector", "React", "Dropdown")
            Component(riskIndicator, "RiskIndicator", "React", "Risk badges")
        }

        Container_Boundary(planTab, "Plan Tab") {
            Component(gantt, "ProcurementGantt", "React", "Timeline chart")
            Component(criticalPath, "CriticalPathOverlay", "React", "Highlight")
            Component(orderMarkers, "OrderDateMarkers", "React", "Milestones")
        }

        Container_Boundary(alertsTab, "Alerts Tab") {
            Component(alertList, "ProcurementAlertList", "React", "Alert cards")
            Component(alertActions, "AlertActionButtons", "React", "Resolve/Dismiss")
        }
    }

    Rel(tabs, bomTab, "Switches to", "Click")
    Rel(tabs, ltTab, "Switches to", "Click")
    Rel(tabs, planTab, "Switches to", "Click")
    Rel(tabs, alertsTab, "Switches to", "Click")
```

---

## 6. Sequence Diagram - Create WBS Item

```mermaid
sequenceDiagram
    actor User
    participant UI as WBSTree
    participant API as WBS API
    participant UC as CreateWBSItemUC
    participant Dom as WBSDomain
    participant Repo as WBSRepository
    participant DB as PostgreSQL
    participant Event as EventBus

    User->>UI: Click "Add Child"
    UI->>UI: Open WBSItemForm
    User->>UI: Enter name, dates, budget
    User->>UI: Click "Save"

    UI->>API: POST /wbs/items
    Note over UI,API: {name, parentId, dates, budget}

    API->>UC: execute(CreateWBSItemRequest)
    UC->>Dom: validate_parent_exists(parentId)
    Dom-->>UC: true

    UC->>Dom: generate_code(parentId)
    Dom-->>UC: "2.1.3.2" (auto-generated)

    UC->>Dom: validate_code_format(code)
    Dom-->>UC: valid

    UC->>Repo: create(item)
    Repo->>DB: INSERT INTO wbs_items
    DB-->>Repo: success
    Repo-->>UC: item

    UC->>Event: publish(WBSItemCreated)
    UC-->>API: WBSItemDTO
    API-->>UI: 201 Created + item

    UI->>UI: Update tree state
    UI->>User: Show success + new item
```

---

## 7. Sequence Diagram - Generate Procurement Plan

```mermaid
sequenceDiagram
    actor User
    participant UI as ProcurementPage
    participant API as ProcurementAPI
    participant BOM as BOMGenerator
    participant LT as LeadTimeService
    participant Plan as PlanGenerator
    participant Repo as ProcurementRepository
    participant DB as PostgreSQL

    User->>UI: Navigate to Procurement
    UI->>API: GET /procurement/bom
    API->>BOM: generate_from_wbs(projectId)
    BOM->>Repo: get_wbs_items(projectId)
    Repo->>DB: SELECT * FROM wbs_items
    DB-->>Repo: WBS items
    Repo-->>BOM: items
    BOM->>BOM: map_to_bom_items()
    BOM->>Repo: save_bom(items)
    Repo->>DB: INSERT INTO bom_items
    BOM-->>API: BOM items
    API-->>UI: BOM + total cost
    UI->>User: Display BOM table

    User->>UI: Click "Calculate Lead Times"
    UI->>UI: Select project location
    UI->>API: POST /procurement/lead-times
    Note over UI,API: {projectLocation: "Barcelona"}

    API->>LT: calculate_for_bom(bomItems, location)
    loop For each BOM item
        LT->>LT: lookup_production_time(material)
        LT->>LT: lookup_transit_time(supplier, location)
        LT->>LT: lookup_customs_time(origin, destination)
        LT->>LT: apply_incoterm_adjustment(incoterm)
        LT->>LT: add_buffer_days(risk_level)
    end
    LT->>Repo: save_lead_times(results)
    Repo->>DB: INSERT INTO lead_times
    LT-->>API: LeadTimeResult[]
    API-->>UI: Lead time calculations
    UI->>User: Display lead times with risk indicators

    User->>UI: Click "Generate Plan"
    UI->>API: POST /procurement/plan
    API->>Plan: generate_plan(leadTimes, projectDates)
    Plan->>Plan: calculate_order_dates()
    Plan->>Plan: identify_critical_path()
    Plan->>Plan: check_r14_alerts()
    Plan->>Repo: save_plan(planItems)
    Repo->>DB: INSERT INTO procurement_plans
    Plan-->>API: ProcurementPlan
    API-->>UI: Plan + critical path + alerts
    UI->>User: Display Gantt chart with alerts
```

---

## 8. Data Flow - Demo Mode

```mermaid
flowchart TD
    subgraph Frontend["Frontend Application"]
        A[User Action] --> B{Demo Mode?}
        B -->|Yes| C[Demo Data Store]
        B -->|No| D[Orval API Hook]

        C --> E[Mock Data]
        D --> F[Real API]

        E --> G[UI Components]
        F --> G
    end

    subgraph Backend["Backend (Real Mode Only)"]
        F --> H[WBS/Procurement API]
        H --> I[Domain Services]
        I --> J[Repositories]
        J --> K[(PostgreSQL)]
    end

    style C fill:#fff4e1
    style E fill:#fff4e1
    style F fill:#e1f5ff
    style H fill:#e1f5ff
```

---

## 9. Role-Based Access Flow

```mermaid
flowchart TD
    Start([User Request]) --> Auth{Authentication}
    Auth -->|Invalid| Denied[401 Unauthorized]
    Auth -->|Valid| Role{Extract Role}

    Role -->|Final User| FUPerm{Check Permission}
    Role -->|Tenant Admin| TAPerm{Check Permission}
    Role -->|C2Pro Admin| CAPerm[Full Access]

    FUPerm -->|Read Only| FUAllow[Allow View]
    FUPerm -->|Write| FUDeny[403 Forbidden]

    TAPerm -->|Read| TAAllow[Allow View]
    TAPerm -->|Write| TACRUD[Allow CRUD]

    CAPerm --> All[Allow All Operations]

    FUAllow --> Render[Render UI]
    TACRUD --> Render
    All --> Render
    FUDeny --> Error[Show Error]
    Denied --> Error

    style FUAllow fill:#e1f5ff
    style TACRUD fill:#fff4e1
    style All fill:#ffe1e1
```

---

## 10. State Management - WBS Store

```mermaid
stateDiagram-v2
    [*] --> Idle

    Idle --> Loading: fetchWBS(projectId)
    Loading --> Loaded: API Success
    Loading --> Error: API Error

    Loaded --> Editing: selectItem(item)
    Editing --> Saving: saveItem(changes)
    Saving --> Loaded: Save Success
    Saving --> Error: Save Error

    Loaded --> Creating: createItem(parent)
    Creating --> Saving: submitNew(data)

    Loaded --> Dragging: startDrag(item)
    Dragging --> Saving: drop(target)

    Loaded --> Deleting: deleteItem(item)
    Deleting --> Confirming: confirmDelete()
    Confirming --> Loaded: Delete Success
    Confirming --> Error: Delete Error

    Error --> Idle: retry()
    Error --> Loaded: dismiss()

    Loaded --> [*]: unmount()
```

---

## 11. Deployment Architecture

```mermaid
C4Deployment
    title Production Deployment - Kubernetes

    Deployment_Node(cdn, "Cloudflare CDN", "Edge Network") {
        Container(static, "Static Assets", "Next.js Build")
    }

    Deployment_Node(k8s, "Kubernetes Cluster", "AWS EKS / GCP GKE") {
        Deployment_Node(frontend, "Frontend Namespace") {
            Container(nextjs, "Next.js App", "3 replicas", "Port 3000")
        }

        Deployment_Node(backend, "Backend Namespace") {
            Container(api, "FastAPI App", "3 replicas", "Port 8000")
            Container(celery, "Celery Workers", "2 replicas", "Async tasks")
        }

        Deployment_Node(data, "Data Namespace") {
            Container(postgres, "PostgreSQL", "Primary + Replica")
            Container(redis, "Redis", "Cache + Event Bus")
        }
    }

    Deployment_Node(storage, "Object Storage", "Cloudflare R2") {
        Container(docs, "Documents", "PDF, DOCX, XLSX")
    }

    Rel(cdn, nextjs, "Cache miss", "HTTPS")
    Rel(nextjs, api, "API calls", "Internal HTTPS")
    Rel(api, postgres, "SQL", "Port 5432")
    Rel(api, redis, "Cache/Events", "Port 6379")
    Rel(api, storage, "Files", "S3 API")
    Rel(celery, redis, "Queue", "Port 6379")
```

---

## Legend

### C4 Model Notation

- **Person**: End users and roles
- **System**: High-level systems
- **Container**: Applications or data stores within a system
- **Component**: Building blocks within a container
- **Relationship**: Connections between elements

### Color Coding

- 🟦 Blue: Frontend/React components
- 🟩 Green: Backend/Python components
- 🟨 Yellow: Data stores
- 🟥 Red: External systems
- 🟪 Purple: Infrastructure

---

_Diagrams created with Mermaid.js_  
_Part of UX Implementation Master Plan v1.0_
