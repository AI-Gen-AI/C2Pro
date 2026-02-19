# Fase 1 — Tarea 1.3: Matriz Page <-> Endpoint <-> Fuente de Datos
**Fecha:** 2026-02-19
**Dependencias:** `PHASE1_FRONTEND_PAGE_INVENTORY.md` (1.1) + `PHASE1_BACKEND_ENDPOINT_INVENTORY.md` (1.2)

---

## Resumen Ejecutivo

| Estado del cruce | Pages | Descripcion |
|------------------|-------|-------------|
| Page con mock inline, sin llamada API | 11 | El page **nunca** contacta al backend |
| Page llama API -> backend REAL (DB) | 5 | Flujo correcto end-to-end |
| Page llama API -> backend FAKE (in-memory) | 2 | Llama API pero el backend responde con datos ficticios |
| Page estatica (sin datos) | 14 | Layouts, redirects, placeholders |
| **TOTAL** | **32** | |

### Conclusion

Solo **5 de 32 pages** (16%) tienen un flujo end-to-end real funcional (frontend -> API -> base de datos).

---

## Infraestructura de Conexion Frontend -> Backend

```
Frontend (Next.js)
    │
    ├── apiClient (axios)
    │   baseURL = NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"
    │   interceptor: agrega Authorization: Bearer <token> + X-Tenant-ID
    │
    ├── Generated Client (Orval -> ProjectsService)
    │   usa apiClient internamente
    │   url: "/projects" (relativo a baseURL)
    │
    ├── Custom hooks (useProjectDocuments, useDocumentEntities, etc.)
    │   usan apiClient.get("/projects/{id}/documents")
    │
    └── Direct fetch() (solo observability)
        url: "${API_BASE_URL}/api/v1/observability/status"
```

### MSW (Mock Service Worker)

```
Inicializacion: providers.tsx -> si IS_DEMO=true -> import("@/mocks/browser") -> worker.start()

Handlers registrados (demo-data.ts):
  GET /api/v1/projects
  GET /api/v1/projects/:projectId
  GET /api/v1/projects/:projectId/documents
  GET /api/v1/projects/:projectId/alerts
  GET /api/v1/projects/:projectId/stakeholders
  GET /api/v1/projects/:projectId/wbs
  GET /api/v1/documents/:documentId/clauses

Estado: MSW esta configurado pero NINGUNA page lo usa porque las pages
        con datos mock hardcodean los datos inline en vez de llamar a la API.
```

---

## Matriz Completa

### Leyenda

| Simbolo | Significado |
|---------|-------------|
| **MOCK_INLINE** | Page tiene datos hardcodeados, NO llama a ningun endpoint |
| **API->DB_REAL** | Page llama API, backend consulta PostgreSQL |
| **API->FAKE_MEM** | Page llama API, backend responde desde dict en memoria |
| **STATIC** | Page sin datos dinamicos |
| -- | No aplica |
| (CONFLICTO) | Dos routers definen la misma ruta |

---

### Pages de Dashboard Principal

| # | Page | Endpoint que DEBERIA llamar | Endpoint que REALMENTE llama | Backend | Flujo Real |
|---|------|-----------------------------|-------------------------------|---------|------------|
| 1 | `(app)/page.tsx` | `GET /api/v1/dashboard/summary` | **NINGUNO** — usa `const DATA = { score: 78, project: "Torre Skyline" }` | -- | **MOCK_INLINE** |
| 2 | `(app)/documents/page.tsx` | `GET /api/v1/projects/{id}/documents` | **NINGUNO** — usa `const mockDocuments = [8 docs]` | -- | **MOCK_INLINE** |
| 3 | `(app)/alerts/page.tsx` | `GET /api/v1/projects/{id}/alerts` | **NINGUNO** — usa `const mockAlerts = [7 alertas]` | -- | **MOCK_INLINE** |
| 4 | `(app)/raci/page.tsx` | `GET /api/v1/projects/{id}/raci` | **NINGUNO** — usa `const mockRaciData = [8 actividades]` | -- | **MOCK_INLINE** |
| 5 | `(app)/observability/page.tsx` | `GET /api/v1/observability/status` + `GET /api/v1/observability/analyses` | `fetch("${API_BASE_URL}/api/v1/observability/status")` + `fetch(".../analyses")` | `ObservabilityService` -> SQLAlchemy | **API->DB_REAL** |
| 6 | `(app)/settings/page.tsx` | -- | -- (formulario local) | -- | **STATIC** |
| 7 | `(app)/evidence/page.tsx` | -- | -- (redirect a /projects) | -- | **STATIC** |
| 8 | `(app)/stakeholders/page.tsx` | `GET /api/v1/stakeholders/projects/{id}` | Delega a `<StakeholderMatrix>` componente | -- | **STATIC** (datos en componente) |

---

### Pages de Proyectos

| # | Page | Endpoint que DEBERIA llamar | Endpoint que REALMENTE llama | Backend | Flujo Real |
|---|------|-----------------------------|-------------------------------|---------|------------|
| 9 | `(app)/projects/page.tsx` | `GET /api/v1/projects` | `ProjectsService.getProjects()` -> `GET /api/v1/projects` | `projects/router.py` -> `_fake_projects` dict | **API->FAKE_MEM** |
| 10 | `(app)/projects/new/page.tsx` | -- | -- (placeholder) | -- | **STATIC** |
| 11 | `(app)/projects/[id]/page.tsx` | `GET /api/v1/projects/{id}` | **NINGUNO** — usa `const stats = [...]` hardcodeado | -- | **MOCK_INLINE** |
| 12 | `(app)/projects/[id]/analysis/page.tsx` | `POST /api/v1/analyze` | -- (placeholder) | -- | **STATIC** |
| 13 | `(app)/projects/[id]/coherence/page.tsx` | `GET /api/v1/projects/{id}/coherence` o `GET /api/coherence/dashboard/{id}` | **NINGUNO** — usa `const DATA = { score: 72 }` | -- | **MOCK_INLINE** |
| 14 | `(app)/projects/[id]/documents/page.tsx` | `GET /api/v1/projects/{id}/documents` | `useProjectDocuments()` -> `apiClient.get("/projects/{id}/documents")` | `documents/router.py` -> `ListProjectDocumentsUseCase` -> SQLAlchemy | **API->DB_REAL** |
| 15 | `(app)/projects/[id]/evidence/page.tsx` | Multiples: documents + entities + alerts | `useProjectDocuments()` + `useDocumentEntities()` + `useDocumentAlerts()` | `documents/router.py` -> SQLAlchemy | **API->DB_REAL** |

---

### Pages de Auth

| # | Page | Endpoint que DEBERIA llamar | Endpoint que REALMENTE llama | Backend | Flujo Real |
|---|------|-----------------------------|-------------------------------|---------|------------|
| 16 | `(auth)/login/page.tsx` | `POST /api/v1/auth/login` | Formulario (submit via auth store) | `auth/router.py` -> DB | **STATIC** (form) |
| 17 | `(auth)/register/page.tsx` | `POST /api/v1/auth/register` | Formulario (TODO pendiente) | `auth/router.py` -> DB | **STATIC** (form) |

---

### Pages Duplicadas: `app/dashboard/` (A ELIMINAR)

| # | Page | Duplicado de | Flujo Real | Notas |
|---|------|-------------|------------|-------|
| 18 | `dashboard/page.tsx` | `(app)/page.tsx` | **MOCK_INLINE** | Mismo `const DATA = {...}` |
| 19 | `dashboard/projects/[id]/page.tsx` | `(app)/projects/[id]/page.tsx` | **MOCK_INLINE** | Mismo mock |
| 20 | `dashboard/projects/[id]/alerts/page.tsx` | -- (no tiene equivalente) | **MOCK_INLINE** | `const DEMO_ALERTS = [...]` para test S3-04 |
| 21 | `dashboard/projects/[id]/coherence/page.tsx` | `(app)/projects/[id]/coherence/page.tsx` | **MOCK_INLINE** | Mismo mock |
| 22 | `dashboard/projects/[id]/documents/page.tsx` | `(app)/projects/[id]/documents/page.tsx` | **API->DB_REAL** | Mismo hook |
| 23 | `dashboard/projects/[id]/evidence/page.tsx` | `(app)/projects/[id]/evidence/page.tsx` | **API->DB_REAL** | Mismo hook |
| 24 | `dashboard/projects/[id]/analysis/page.tsx` | `(app)/projects/[id]/analysis/page.tsx` | **STATIC** | Placeholder |

---

### Pages Demo: `app/demo/` (A ELIMINAR)

| # | Page | Flujo Real | Notas |
|---|------|------------|-------|
| 25 | `demo/page.tsx` | **STATIC** | Solo redirect a /demo/projects |
| 26 | `demo/projects/page.tsx` | **API->FAKE_MEM** | Re-exporta `(app)/projects/page` |

---

## Mapa de Cobertura MSW vs Uso Real

| Endpoint MSW Handler | Page que DEBERIA usarlo | Page REALMENTE lo usa? |
|----------------------|--------------------------|------------------------|
| `GET /api/v1/projects` | `(app)/projects/page.tsx` | SI — pero backend responde FAKE_MEM de todos modos |
| `GET /api/v1/projects/:id` | `(app)/projects/[id]/page.tsx` | **NO** — page usa mock inline |
| `GET /api/v1/projects/:id/documents` | `(app)/documents/page.tsx` | **NO** — page usa mock inline |
| `GET /api/v1/projects/:id/documents` | `(app)/projects/[id]/documents/page.tsx` | SI — hook llama API |
| `GET /api/v1/projects/:id/alerts` | `(app)/alerts/page.tsx` | **NO** — page usa mock inline |
| `GET /api/v1/projects/:id/stakeholders` | `(app)/stakeholders/page.tsx` | Parcial — delega a componente |
| `GET /api/v1/projects/:id/wbs` | (ninguna page lo muestra) | NO |
| `GET /api/v1/documents/:id/clauses` | (dentro de evidence page) | Parcial |

**Conclusion MSW:** De 7 endpoints que MSW cubre, solo 2 son realmente llamados por alguna page.

---

## Tabla de Gaps: Que Falta para Eliminar Todos los Mocks

| Page con Mock | Endpoint Backend Necesario | Estado del Endpoint | Accion Necesaria |
|---------------|---------------------------|---------------------|-----------------|
| Dashboard principal | `GET /api/v1/dashboard/summary` | **NO EXISTE** | Crear endpoint nuevo que agregue score + alertas + tendencias |
| Documents list | `GET /api/v1/projects/{id}/documents` | REAL (documents router) | Page debe llamar a API en vez de hardcodear. **Resolver conflicto** con projects router |
| Alerts list | `GET /api/v1/projects/{id}/alerts` | FAKE_IN_MEMORY (alerts router) | Reescribir alerts router con SQLAlchemy |
| RACI matrix | `GET /api/v1/projects/{id}/raci` | REAL pero COMENTADO (raci_router) | Descomentar en main.py |
| Project overview | `GET /api/v1/projects/{id}` | FAKE_IN_MEMORY (projects router) | Reescribir projects router con SQLAlchemy |
| Project coherence | `GET /api/v1/projects/{id}/coherence/score` | FAKE_RETURN (dashboard router, score 78) | Conectar con CoherenceEngine real + DB |
| Project [id] page | `GET /api/v1/projects/{id}` (con stats) | FAKE_IN_MEMORY | Reescribir projects router + agregar stats endpoint |

---

## Diagrama de Flujo: Estado Actual vs Deseado

### Estado Actual (11 pages con mock inline)

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Browser        │     │   Next.js Page    │     │   Backend API    │
│                  │────▶│                   │     │                  │
│  GET /dashboard  │     │  const DATA = {   │     │  (nunca          │
│                  │     │    score: 78,     │     │   contactado)    │
│                  │◀────│    project:       │     │                  │
│  Renderiza mock  │     │    "Torre Skyline"│     │                  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

### Estado Actual (5 pages con API real)

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Browser        │     │   Next.js Page    │     │   Backend API    │
│                  │────▶│                   │────▶│                  │
│  GET /projects/  │     │  useProjectDocs() │     │  documents/      │
│  {id}/documents  │     │  -> apiClient.get │     │  router.py       │
│                  │◀────│  ("/projects/     │◀────│  -> SQLAlchemy   │
│  Renderiza real  │     │    {id}/documents")│    │  -> PostgreSQL   │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

### Estado Deseado (TODAS las pages)

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Browser        │     │   Next.js Page    │     │   Backend API    │
│                  │────▶│                   │────▶│                  │
│  GET /dashboard  │     │  useDashboard()   │     │  dashboard/      │
│                  │     │  -> apiClient.get │     │  router.py       │
│                  │◀────│  ("/dashboard/    │◀────│  -> SQLAlchemy   │
│  Renderiza real  │     │    summary")      │     │  -> PostgreSQL   │
└──────────────────┘     └──────────────────┘     └──────────────────┘

                    (En modo demo, MSW intercepta el fetch y responde
                     con datos seed sin llegar al backend)
```

---

## Resumen de Acciones por Prioridad

### P1 — Bloquean el producto

| Accion | Afecta a | Esfuerzo |
|--------|----------|----------|
| Reescribir `projects/router.py` con SQLAlchemy (reemplazar `_fake_projects`) | 8 endpoints | Alto |
| Reescribir `alerts/router.py` con SQLAlchemy (reemplazar `_fake_alerts`) | 8 endpoints | Alto |
| Crear endpoint `GET /api/v1/dashboard/summary` | 1 page | Medio |
| Conectar coherence dashboard con engine real | 1 endpoint | Medio |

### P2 — Habilitan features

| Accion | Afecta a | Esfuerzo |
|--------|----------|----------|
| Descomentar `stakeholders_router` en main.py | 4 endpoints | Bajo |
| Descomentar `raci_router` en main.py | 2 endpoints | Bajo |
| Descomentar `procurement_router` en main.py | 12 endpoints | Bajo |
| Descomentar `analysis_router` en main.py | 1 endpoint | Bajo |
| Resolver conflicto `POST /projects/{id}/documents` (eliminar del projects router) | 1 conflicto | Bajo |

### P3 — Limpian frontend

| Accion | Afecta a | Esfuerzo |
|--------|----------|----------|
| Reemplazar mock inline en 11 pages por llamadas API | 11 pages | Alto |
| Eliminar `app/dashboard/` completo | 7 pages duplicadas | Bajo |
| Eliminar `app/demo/` completo | 2 pages | Bajo |
| Hacer que MSW sea realmente util (pages llamen API en demo) | Infraestructura | Medio |

---

*Este documento cierra la tarea 1.3 y proporciona la base para 1.4 (contrato demo/prod) y 1.5 (endpoints necesarios).*
