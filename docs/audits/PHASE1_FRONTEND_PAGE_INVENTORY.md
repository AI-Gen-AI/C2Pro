# Fase 1 — Tarea 1.1: Inventario Completo de Pages del Frontend
**Fecha:** 2026-02-19
**Scope:** Todos los archivos `page.tsx`, `layout.tsx`, `route.ts` en `apps/web/app/`

---

## Resumen Ejecutivo

| Clasificacion | Cantidad | % del Total |
|---------------|----------|-------------|
| MOCK_INLINE   | 11       | 34%         |
| API_REAL      | 7        | 22%         |
| STATIC        | 14       | 44%         |
| HYBRID        | 0        | 0%          |
| API_MSW       | 0        | 0%          |
| **TOTAL**     | **32**   | **100%**    |

### Hallazgo clave

**34% de las pages contienen datos mock hardcodeados.** Cero pages usan MSW como mecanismo de mock. La infraestructura MSW existe pero no se usa porque las pages no llaman a la API.

**Cero pages usan Zustand stores.** El store `app-mode` existe pero no se consulta.

**Cero pages importan de `@/mocks/` o `@/lib/mockData`.** Todos los mocks estan inline.

---

## Inventario Completo

### Leyenda de Clasificacion

| Codigo | Significado |
|--------|-------------|
| `MOCK_INLINE` | Datos hardcodeados dentro del archivo (`const DATA = {...}`, `const mock* = [...]`) |
| `API_REAL` | Llama a API real via hooks, generated client, o `fetch()` |
| `STATIC` | Sin datos dinamicos (layout, redirect, placeholder, formulario) |

---

### Grupo: `app/` (Raiz)

| # | Archivo | Tipo | Clasificacion | Fuente de Datos | Notas |
|---|---------|------|---------------|-----------------|-------|
| 1 | `app/page.tsx` | page | STATIC | Ninguna | Verifica auth y redirige a dashboard o login |
| 2 | `app/layout.tsx` | layout | STATIC | Metadata + fonts | Root layout, wrappea con `<Providers>` |
| 3 | `app/api/[...proxy]/route.ts` | route | API_REAL | `fetch()` a `${API_BASE_URL}/api/v1/...` | Proxy que reenvía GET/POST/PUT/DELETE al backend |

---

### Grupo: `app/(auth)/`

| # | Archivo | Tipo | Clasificacion | Fuente de Datos | Notas |
|---|---------|------|---------------|-----------------|-------|
| 4 | `(auth)/login/page.tsx` | page | STATIC | Formulario local | Sin fetch de datos |
| 5 | `(auth)/register/page.tsx` | page | STATIC | Formulario local | Tiene `// TODO` pendiente |

---

### Grupo: `app/(dashboard)/` — RUTAS PRINCIPALES

| # | Archivo | Tipo | Clasificacion | Fuente de Datos | Notas |
|---|---------|------|---------------|-----------------|-------|
| 6 | `(dashboard)/layout.tsx` | layout | STATIC | Componentes `AppSidebar`, `AppHeader`, `DemoBanner` | Layout principal del dashboard |
| 7 | `(dashboard)/page.tsx` | page | **MOCK_INLINE** | `const DATA = { score: 78, categories: [...], alerts: [...], trends: [...] }` | Dashboard principal. Nombre de proyecto "Torre Skyline" hardcodeado. Zero llamadas API |
| 8 | `(dashboard)/alerts/page.tsx` | page | **MOCK_INLINE** | `const mockAlerts = [...]` (7 alertas ficticias) | Alertas globales. Severities, timestamps, descriptions inventados |
| 9 | `(dashboard)/documents/page.tsx` | page | **MOCK_INLINE** | `const mockDocuments = [...]` (8 documentos ficticios) | Lista de documentos. Nombres como "Contrato Principal", "Presupuesto Detallado" |
| 10 | `(dashboard)/evidence/page.tsx` | page | STATIC | Redirect | Redirige a `/projects` |
| 11 | `(dashboard)/observability/page.tsx` | page | **API_REAL** | `fetch(${API_BASE_URL}/api/v1/observability/status)`, `fetch(.../analyses)` | Llama API real con `fetch()`. Auto-refresh 30s. Manejo de errores |
| 12 | `(dashboard)/raci/page.tsx` | page | **MOCK_INLINE** | `const mockRaciData = [...]` (8 actividades), `const raciTypes = {...}` | Matriz RACI completa con datos ficticios. 5 stakeholders inventados |
| 13 | `(dashboard)/settings/page.tsx` | page | STATIC | Estado local (form inputs) | Formulario de configuracion, sin fetch |
| 14 | `(dashboard)/stakeholders/page.tsx` | page | STATIC | Delega a `<StakeholderMatrix>` | El componente puede tener sus propios datos |

---

### Grupo: `app/(dashboard)/projects/` — RUTAS DE PROYECTOS

| # | Archivo | Tipo | Clasificacion | Fuente de Datos | Notas |
|---|---------|------|---------------|-----------------|-------|
| 15 | `(dashboard)/projects/page.tsx` | page | **API_REAL** | `ProjectsService.getProjects()` de `@/lib/api/generated/services` | Usa cliente API generado (Orval). Patron correcto |
| 16 | `(dashboard)/projects/new/page.tsx` | page | STATIC | Ninguna | Placeholder: "Pendiente de wireframes" |
| 17 | `(dashboard)/projects/[id]/layout.tsx` | layout | STATIC | Componente `ProjectTabs` | Tabs de navegacion del proyecto |
| 18 | `(dashboard)/projects/[id]/page.tsx` | page | **MOCK_INLINE** | `const stats = [...]`, alertas hardcodeadas | Overview de proyecto con metricas ficticias |
| 19 | `(dashboard)/projects/[id]/analysis/page.tsx` | page | STATIC | Ninguna | Placeholder minimal |
| 20 | `(dashboard)/projects/[id]/coherence/page.tsx` | page | **MOCK_INLINE** | `const DATA = { score: 72, categories: [...] }` | Score de coherencia hardcodeado |
| 21 | `(dashboard)/projects/[id]/documents/page.tsx` | page | **API_REAL** | `useProjectDocuments()` hook | Usa hook custom que llama API |
| 22 | `(dashboard)/projects/[id]/evidence/page.tsx` | page | **API_REAL** | `useProjectDocuments()`, `useDocumentEntities()`, `useDocumentAlerts()` | Multiples hooks API. Patron correcto |

---

### Grupo: `app/dashboard/` — DUPLICADO (debe eliminarse)

| # | Archivo | Tipo | Clasificacion | Fuente de Datos | Notas |
|---|---------|------|---------------|-----------------|-------|
| 23 | `dashboard/layout.tsx` | layout | STATIC | `AppSidebar`, `AppHeader`, `DemoBanner` | **Duplicado** de `(dashboard)/layout.tsx` |
| 24 | `dashboard/page.tsx` | page | **MOCK_INLINE** | `const DATA = { score: 78, ... }` | **Duplicado** de `(dashboard)/page.tsx` |
| 25 | `dashboard/projects/[id]/layout.tsx` | layout | STATIC | Tabs hardcodeados inline | **Duplicado** con navegacion inline |
| 26 | `dashboard/projects/[id]/page.tsx` | page | **MOCK_INLINE** | `const stats = [...]` | **Duplicado** de `(dashboard)/projects/[id]/page.tsx` |
| 27 | `dashboard/projects/[id]/alerts/page.tsx` | page | **MOCK_INLINE** | `const DEMO_ALERTS = [...]` | Datos demo de alertas para S3-04 |
| 28 | `dashboard/projects/[id]/analysis/page.tsx` | page | STATIC | Ninguna | Placeholder |
| 29 | `dashboard/projects/[id]/coherence/page.tsx` | page | **MOCK_INLINE** | `const DATA = { score: 72, ... }` | **Duplicado** de `(dashboard)/projects/[id]/coherence/page.tsx` |
| 30 | `dashboard/projects/[id]/documents/page.tsx` | page | **API_REAL** | `useProjectDocuments()` | **Duplicado** de `(dashboard)/projects/[id]/documents/page.tsx` |
| 31 | `dashboard/projects/[id]/evidence/page.tsx` | page | **API_REAL** | `useProjectDocuments()`, `useDocumentEntities()`, `useDocumentAlerts()` | **Duplicado** de `(dashboard)/projects/[id]/evidence/page.tsx` |

---

### Grupo: `app/demo/` — RUTAS DEMO (debe eliminarse)

| # | Archivo | Tipo | Clasificacion | Fuente de Datos | Notas |
|---|---------|------|---------------|-----------------|-------|
| 32 | `demo/layout.tsx` | layout | STATIC | `AppSidebar`, `AppHeader`, `DemoBanner` | Tercer layout duplicado |
| 33 | `demo/page.tsx` | page | STATIC | Redirect a `/demo/projects` | Solo redirige |
| 34 | `demo/projects/page.tsx` | page | **API_REAL** | Re-exporta `(dashboard)/projects/page.tsx` | Re-export, usa `ProjectsService` |

---

## Analisis de Datos Mock Encontrados

### Mock Data: `(dashboard)/page.tsx` — Dashboard Principal

```typescript
const DATA = {
  score: 78,
  project: "Torre Skyline",
  categories: [
    { name: "Alcance", score: 85, weight: 0.25 },
    { name: "Presupuesto", score: 72, weight: 0.20 },
    { name: "Cronograma", score: 68, weight: 0.20 },
    { name: "Tecnico", score: 82, weight: 0.15 },
    { name: "Legal", score: 90, weight: 0.10 },
    { name: "Calidad", score: 75, weight: 0.10 }
  ],
  alerts: [
    { severity: "critical", count: 2 },
    { severity: "high", count: 5 },
    // ...
  ],
  trends: [ /* 7 dias de datos inventados */ ]
}
```

**Problema:** Este es el PRIMER page que ve un usuario al entrar. Muestra "Torre Skyline" con score 78 sin importar si hay datos reales.

---

### Mock Data: `(dashboard)/documents/page.tsx` — Lista de Documentos

```typescript
const mockDocuments = [
  { id: "1", name: "Contrato Principal de Construccion", type: "contract", status: "parsed", clauses: 47, ... },
  { id: "2", name: "Presupuesto Detallado", type: "budget", status: "parsed", clauses: 23, ... },
  { id: "3", name: "Cronograma de Obra", type: "schedule", status: "analyzing", clauses: 15, ... },
  // ... 5 documentos mas
]
```

**Problema:** 8 documentos ficticios. Un usuario real nunca veria SUS documentos aqui.

---

### Mock Data: `(dashboard)/alerts/page.tsx` — Alertas

```typescript
const mockAlerts = [
  { id: "1", severity: "critical", title: "Presupuesto excede el 15%...", category: "Presupuesto", ... },
  { id: "2", severity: "high", title: "Plazo de ejecucion no coincide...", category: "Cronograma", ... },
  // ... 5 alertas mas
]
```

---

### Mock Data: `(dashboard)/raci/page.tsx` — Matriz RACI

```typescript
const mockRaciData = [
  {
    activity: "Revision de Contrato",
    stakeholders: {
      "Juan Perez": "R",
      "Maria Lopez": "A",
      "Carlos Diaz": "C",
      // ...
    }
  },
  // ... 7 actividades mas
]
```

---

### Mock Data: `(dashboard)/projects/[id]/coherence/page.tsx` — Score Coherencia

```typescript
const DATA = {
  score: 72,
  categories: [
    { name: "Alcance", score: 80, alerts: 2, weight: 0.25 },
    { name: "Presupuesto", score: 65, alerts: 3, weight: 0.20 },
    // ...
  ]
}
```

---

## Duplicacion Entre Grupos de Rutas

| Ruta en `(dashboard)/` | Duplicado en `dashboard/` | Identico? |
|-------------------------|---------------------------|-----------|
| `page.tsx` (Dashboard) | `page.tsx` | Si, mismos datos mock |
| `projects/[id]/page.tsx` | `projects/[id]/page.tsx` | Si |
| `projects/[id]/coherence/page.tsx` | `projects/[id]/coherence/page.tsx` | Si |
| `projects/[id]/documents/page.tsx` | `projects/[id]/documents/page.tsx` | Si (API real) |
| `projects/[id]/evidence/page.tsx` | `projects/[id]/evidence/page.tsx` | Si (API real) |
| `projects/[id]/analysis/page.tsx` | `projects/[id]/analysis/page.tsx` | Si (placeholder) |
| `alerts/page.tsx` | `projects/[id]/alerts/page.tsx` | No — diferente scope |
| `layout.tsx` | `layout.tsx` | Si, mismo componente |

**Conclusion:** `app/dashboard/` es un duplicado completo de `app/(dashboard)/` y debe eliminarse.

---

## Infraestructura Demo No Utilizada

### 1. MSW (Mock Service Worker) — Configurado pero inutilizado

```typescript
// apps/web/components/providers/providers.tsx
if (!env.IS_DEMO) return;
const { worker } = await import("@/mocks/browser");
await worker.start({ onUnhandledRequest: "bypass" });
```

MSW se inicializa cuando `IS_DEMO=true`, pero como las pages hardcodean datos en vez de llamar a la API, MSW nunca intercepta nada.

### 2. Zustand `app-mode` Store — Definido pero no consultado

```typescript
// apps/web/stores/app-mode.ts
const defaultMode = process.env.NEXT_PUBLIC_APP_MODE === "demo" ? "demo" : "prod";
export const useAppModeStore = create<AppModeState>()(...)
```

Ningun page ni componente importa `useAppModeStore` para decidir comportamiento.

### 3. `lib/mockData.ts` — Probable fuente adicional de mock data

Archivo existente pero no importado por ninguna page (los mocks estan inline).

---

## Mapa Visual: Estado Actual vs Estado Deseado

### Estado Actual

```
app/
├── (dashboard)/
│   ├── page.tsx ---------> const DATA = {...}        ❌ MOCK
│   ├── documents/page.tsx -> const mockDocuments = [...]  ❌ MOCK
│   ├── alerts/page.tsx ----> const mockAlerts = [...]     ❌ MOCK
│   ├── raci/page.tsx ------> const mockRaciData = [...]   ❌ MOCK
│   ├── observability/page.tsx -> fetch(API_URL)           ✅ API REAL
│   ├── projects/
│   │   ├── page.tsx -------> ProjectsService.getProjects() ✅ API REAL
│   │   └── [id]/
│   │       ├── page.tsx ---> const stats = [...]          ❌ MOCK
│   │       ├── coherence/ -> const DATA = {...}           ❌ MOCK
│   │       ├── documents/ -> useProjectDocuments()        ✅ API REAL
│   │       └── evidence/ --> useProjectDocuments()        ✅ API REAL
│
├── dashboard/ -----> DUPLICADO COMPLETO                   ❌ ELIMINAR
├── demo/ ----------> RUTA SEPARADA                        ❌ ELIMINAR
```

### Estado Deseado (Post-Fase 4)

```
app/
├── (app)/
│   ├── page.tsx ---------> DashboardService.getSummary()   ✅ API
│   ├── documents/page.tsx -> DocumentsService.list()       ✅ API
│   ├── alerts/page.tsx ----> AlertsService.list()          ✅ API
│   ├── raci/page.tsx ------> RaciService.getMatrix(id)     ✅ API
│   ├── observability/ -----> fetch(API_URL)                ✅ API
│   ├── projects/
│   │   ├── page.tsx -------> ProjectsService.getProjects() ✅ API
│   │   └── [id]/
│   │       ├── page.tsx ---> ProjectsService.getById(id)   ✅ API
│   │       ├── coherence/ -> CoherenceService.getScore(id) ✅ API
│   │       ├── documents/ -> useProjectDocuments()         ✅ API
│   │       └── evidence/ --> useProjectDocuments()         ✅ API
│
│   (MSW intercepta TODAS las llamadas en modo demo)
│   (No existen rutas /dashboard/ ni /demo/)
```

---

## Endpoints API Necesarios (Detectados)

Para que TODAS las pages funcionen con API real, se necesitan estos endpoints:

| Page | Endpoint Necesario | ¿Existe en Backend? |
|------|--------------------|---------------------|
| Dashboard | `GET /api/v1/dashboard/summary` | Pendiente verificar |
| Documents list | `GET /api/v1/documents` | Si (`documents/adapters/http/router.py`) |
| Alerts list | `GET /api/v1/alerts` | Pendiente verificar |
| RACI matrix | `GET /api/v1/projects/{id}/raci` | Pendiente verificar |
| Project overview | `GET /api/v1/projects/{id}` | Si (projects router) |
| Project coherence | `GET /api/v1/projects/{id}/coherence` | Si (coherence router) |
| Project documents | `GET /api/v1/projects/{id}/documents` | Si (hook ya funciona) |
| Project evidence | `GET /api/v1/projects/{id}/evidence` | Si (hooks ya funcionan) |
| Observability | `GET /api/v1/observability/status` | Si (ya funciona) |

---

*Este inventario sirve como base para las tareas 1.2 (backend), 1.3 (matriz), y 1.5 (endpoints necesarios).*
