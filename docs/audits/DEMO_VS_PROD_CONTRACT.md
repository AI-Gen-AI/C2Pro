# Contrato Demo vs Produccion — C2Pro
**Fecha:** 2026-02-19
**Tipo:** Especificacion tecnica vinculante
**Aplica a:** Todo el codebase frontend (`apps/web/`) y backend (`apps/api/`)

---

## 1. Principio Fundamental

> **En produccion, TODA page llama a la API. En demo, MSW intercepta.**
>
> Ningun archivo dentro de `app/` contendra datos hardcodeados.
> La unica diferencia entre demo y produccion es QUIEN responde al `fetch()`:
> en produccion, el backend real; en demo, MSW con datos seed.

---

## 2. Variable de Control

| Variable | Valores | Efecto |
|----------|---------|--------|
| `NEXT_PUBLIC_APP_MODE` | `"production"` (default) | MSW NO se inicializa. Todas las llamadas van al backend real |
| `NEXT_PUBLIC_APP_MODE` | `"demo"` | MSW se inicializa con handlers + seed data. Las llamadas HTTP son interceptadas antes de salir del browser |

### Archivos que implementan esto

| Archivo | Responsabilidad |
|---------|-----------------|
| `config/env.ts` | Expone `env.IS_DEMO` y `env.APP_MODE` |
| `app/providers.tsx` | Si `IS_DEMO`, importa MSW worker y espera a que inicie antes de renderizar |
| `mocks/browser.ts` | Configura MSW worker + ejecuta `seedDemoData()` |
| `mocks/data/seed.ts` | Crea datos de ejemplo en la DB in-memory de MSW |
| `mocks/data/db.ts` | Define el schema de la DB in-memory (`@mswjs/data`) |
| `mocks/handlers/` | Define que endpoints intercepta MSW y como responde |

### Estado actual vs contrato

| Aspecto | Estado Actual | Contrato |
|---------|---------------|----------|
| `NEXT_PUBLIC_APP_MODE` en `.env.example` | **NO existe** | DEBE existir con valor `production` |
| `DemoBanner` | Se renderiza SIEMPRE (no consulta `env.IS_DEMO`) | Se renderiza SOLO cuando `env.IS_DEMO === true` |
| `useAppModeStore` | Definido, nunca importado por ninguna page | `DemoBanner` y cualquier UI condicional lo consultan |
| Pages | 11 pages tienen datos inline | 0 pages tienen datos inline |

---

## 3. Reglas del Contrato

### 3.1 Reglas para Pages (`app/**/*.tsx`)

| # | Regla | Verificable |
|---|-------|-------------|
| R1 | Una page NUNCA contiene `const DATA = {...}`, `const mock* = [...]`, ni ningun array/objeto de datos ficticios | Grep: `const (DATA|mock|MOCK|DEMO_|fake)` en `app/` debe retornar 0 resultados |
| R2 | Una page obtiene datos SOLO via: (a) hook custom (`useX()`), (b) generated client (`XService.method()`), o (c) `fetch()` directo a la API | Code review |
| R3 | Una page tiene 3 estados obligatorios: loading, error, empty | Code review |
| R4 | Una page NO importa de `@/mocks/`, `@/lib/mockData`, ni de ningun archivo con datos ficticios | Grep: `from.*mocks|from.*mockData` en `app/` debe retornar 0 resultados |
| R5 | Una page NO consulta `env.IS_DEMO` para decidir que datos mostrar. Los datos siempre vienen de la misma fuente (API) | Grep: `IS_DEMO` en `app/**/page.tsx` debe retornar 0 resultados |

### 3.2 Reglas para Hooks y API Client (`hooks/`, `lib/api/`)

| # | Regla | Verificable |
|---|-------|-------------|
| R6 | Un hook SIEMPRE llama a un endpoint de la API via `apiClient` o generated client | Code review |
| R7 | Un hook NUNCA retorna datos hardcodeados como fallback | Grep: `return \[.*\]` con datos fijos |
| R8 | El `apiClient` SIEMPRE usa `NEXT_PUBLIC_API_URL` como base URL | Ya implementado en `lib/api/client.ts` |

### 3.3 Reglas para MSW (`mocks/`)

| # | Regla | Verificable |
|---|-------|-------------|
| R9 | MSW SOLO se inicializa cuando `env.IS_DEMO === true` | Ya implementado en `providers.tsx` |
| R10 | Los handlers de MSW cubren TODOS los endpoints que las pages necesitan | Test: ejecutar en modo demo y verificar que no hay unhandled requests |
| R11 | Los datos seed de MSW son coherentes entre si (project tiene documents, documents tienen clauses, etc.) | Verificacion manual de `mocks/data/seed.ts` |
| R12 | Los datos seed de MSW usan el MISMO schema de respuesta que el backend real | Validar que los handlers retornan objetos que matchean los DTOs del backend |
| R13 | MSW es la UNICA ubicacion de datos ficticios en todo el frontend | Grep: mock data solo en `mocks/` |

### 3.4 Reglas para el DemoBanner

| # | Regla | Verificable |
|---|-------|-------------|
| R14 | `DemoBanner` se renderiza SOLO cuando `env.IS_DEMO === true` | Condicion en layout |
| R15 | `DemoBanner` usa `useAppModeStore` o `env.IS_DEMO` para decidir si mostrarse | Code review |
| R16 | En produccion, el banner NO existe en el DOM (no solo oculto, sino no renderizado) | Inspeccion DOM en prod mode |

### 3.5 Reglas para el Backend

| # | Regla | Verificable |
|---|-------|-------------|
| R17 | El backend NO tiene modo demo. Siempre responde con datos reales de PostgreSQL | Grep: `MOCK_|_fake_|mock_|demo` en `apps/api/src/` (excluyendo tests) retorna 0 |
| R18 | Ningun router usa `dict = {}` como almacenamiento. Todos usan SQLAlchemy repositories | Code review de routers |
| R19 | No existen `_Default*Service` que retornen datos ficticios | Grep en `apps/api/src/` |
| R20 | Feature flags controlan que endpoints estan activos, NO que datos retornan | Code review |

### 3.6 Reglas Estructurales

| # | Regla | Verificable |
|---|-------|-------------|
| R21 | Existe UNA sola estructura de rutas: `app/(app)/` (antes `(dashboard)`) | `ls app/` no tiene `dashboard/` ni `demo/` |
| R22 | Existe UN solo directorio de componentes: `components/` | `ls` no tiene `src/components/` |
| R23 | `lib/mockData.ts` no existe | File check |
| R24 | Datos mock solo existen en `apps/web/mocks/` y `apps/web/__tests__/` | Grep exhaustivo |

---

## 4. Diagrama de Flujos

### 4.1 Flujo Produccion

```
[Browser]
    |
    | GET /projects
    v
[Next.js Page]
    |
    | useProjects() -> apiClient.get("/projects")
    v
[HTTP Request]
    |
    | Authorization: Bearer <JWT>
    | X-Tenant-ID: <uuid>
    v
[Backend FastAPI]
    |
    | projects_router -> ListProjectsUseCase -> SQLAlchemy -> PostgreSQL
    v
[HTTP Response]
    |
    | { items: [...], total: 5 }
    v
[Page renderiza datos reales]
```

### 4.2 Flujo Demo

```
[Browser]
    |
    | GET /projects
    v
[Next.js Page]
    |
    | useProjects() -> apiClient.get("/projects")
    v
[MSW Intercepta]  <--- El request NUNCA sale del browser
    |
    | handler: http.get("/api/v1/projects", () => db.project.getAll())
    | db tiene datos de seedDemoData()
    v
[MSW Response]
    |
    | [{ id: "proj_demo_001", name: "Torre Skyline" }, ...]
    v
[Page renderiza datos demo]
    |
    | (DemoBanner visible: "Demo Mode - Sample data")
```

### 4.3 Diferencias Visuales

| Elemento UI | Produccion | Demo |
|-------------|------------|------|
| DemoBanner | No existe en DOM | Visible con texto "Demo Mode" |
| Datos mostrados | Datos reales del usuario | Datos seed de MSW |
| Login | Requerido (JWT) | Bypass o credenciales demo |
| URL | Identica | Identica (demo NO es una ruta diferente) |

---

## 5. Gaps Actuales y Acciones para Cumplir el Contrato

### 5.1 Frontend — Pages que violan el contrato

| Page | Violacion | Accion |
|------|-----------|--------|
| `(dashboard)/page.tsx` | R1: `const DATA = { score: 78 }` | Crear hook `useDashboardSummary()` que llame `GET /api/v1/dashboard/summary` |
| `(dashboard)/documents/page.tsx` | R1: `const mockDocuments = [...]` | Usar `useProjectDocuments(projectId)` existente |
| `(dashboard)/alerts/page.tsx` | R1: `const mockAlerts = [...]` | Crear hook `useAlerts(projectId)` que llame `GET /api/v1/projects/{id}/alerts` |
| `(dashboard)/raci/page.tsx` | R1: `const mockRaciData = [...]` | Crear hook `useRaciMatrix(projectId)` que llame `GET /api/v1/projects/{id}/raci` |
| `(dashboard)/projects/[id]/page.tsx` | R1: `const stats = [...]` | Usar `useProject(id)` existente |
| `(dashboard)/projects/[id]/coherence/page.tsx` | R1: `const DATA = { score: 72 }` | Crear hook `useCoherenceScore(projectId)` que llame `GET /api/v1/projects/{id}/coherence` |

### 5.2 Frontend — Infraestructura que falta

| Item | Estado | Accion |
|------|--------|--------|
| `NEXT_PUBLIC_APP_MODE` en `.env.example` | No existe | Agregar `NEXT_PUBLIC_APP_MODE=production` |
| `DemoBanner` condicional | Siempre visible | Wrappear en `{env.IS_DEMO && <DemoBanner />}` |
| `useAppModeStore` | Nunca usado | Integrar en `DemoBanner` y cualquier UI condicional |
| `lib/mockData.ts` | Existe (265 lineas) | Migrar datos utiles a `mocks/data/seed.ts`, luego eliminar |
| `app/dashboard/` | 7 pages duplicadas | Eliminar completamente |
| `app/demo/` | 2 pages | Eliminar completamente |

### 5.3 MSW — Handlers que faltan

| Endpoint Necesario | Handler MSW Existe? | Accion |
|-------------------|---------------------|--------|
| `GET /api/v1/dashboard/summary` | NO | Crear handler que agregue datos de `db.project`, `db.alert` |
| `GET /api/v1/projects` | SI | OK |
| `GET /api/v1/projects/:id` | SI | OK |
| `GET /api/v1/projects/:id/documents` | SI | OK |
| `GET /api/v1/projects/:id/alerts` | SI | OK |
| `GET /api/v1/projects/:id/stakeholders` | SI | OK |
| `GET /api/v1/projects/:id/raci` | NO | Crear handler |
| `GET /api/v1/projects/:id/coherence` | NO | Crear handler (score + breakdown) |
| `GET /api/v1/observability/status` | NO | Crear handler |
| `GET /api/v1/observability/analyses` | NO | Crear handler |

### 5.4 MSW — Seed data que falta

La seed actual (`mocks/data/seed.ts`) crea:
- 1 tenant, 1 user, 2 projects, 2 documents, 3 clauses, 2 alerts, 2 stakeholders, 2 WBS items

Falta para cubrir todas las pages:
- Coherence scores por proyecto (score, breakdown por categoria, tendencias)
- RACI assignments (stakeholder x actividad x rol RACI)
- Dashboard summary (score agregado, alertas por severidad, tendencias)
- Mas documentos con estados variados (parsed, analyzing, error)
- Mas alertas con categorias variadas (SCOPE, BUDGET, TIME, TECHNICAL, LEGAL, QUALITY)

### 5.5 Backend — Endpoints que violan el contrato

| Router | Violacion | Accion |
|--------|-----------|--------|
| `projects/router.py` | R17-R18: `_fake_projects` dict en memoria | Reescribir con SQLAlchemy repository |
| `alerts/router.py` | R17-R18: `_fake_alerts` dict en memoria | Reescribir con SQLAlchemy repository |
| `bulk_operations/router.py` | R17: `percentage: 65` hardcodeado | Conectar con job tracking real |
| `coherence/router.py` (dashboard) | R17: `coherence_score: 78` hardcodeado | Conectar con CoherenceEngine + DB |
| `coherence/service.py` | R17: `MOCK_PROJECT_DB`, `MOCK_SCORE_DB` | Eliminar, usar repositorio real |
| `decision_intelligence/router.py` | R19: `_Default*Service` con datos ficticios | Inyectar dependencias reales o lanzar error |

---

## 6. Checklist de Validacion del Contrato

Cuando todas las acciones esten completadas, ejecutar estas verificaciones:

```bash
# R1: Ningun dato hardcodeado en pages
grep -rn "const DATA\|const mock\|const MOCK\|const DEMO_\|const fake" apps/web/app/ --include="*.tsx"
# Resultado esperado: 0 matches

# R4: Ningun import de mocks en pages
grep -rn "from.*mocks\|from.*mockData" apps/web/app/ --include="*.tsx"
# Resultado esperado: 0 matches

# R5: Pages no consultan IS_DEMO
grep -rn "IS_DEMO" apps/web/app/**/page.tsx
# Resultado esperado: 0 matches

# R17: Backend sin mock data (excluyendo tests)
grep -rn "MOCK_\|_fake_\|_Default.*Service" apps/api/src/ --include="*.py" | grep -v test | grep -v __pycache__
# Resultado esperado: 0 matches

# R21: No existen rutas duplicadas
ls apps/web/app/dashboard 2>/dev/null && echo "FALLA: app/dashboard/ existe" || echo "OK"
ls apps/web/app/demo 2>/dev/null && echo "FALLA: app/demo/ existe" || echo "OK"

# R22: No existe directorio paralelo de componentes
ls apps/web/src/components 2>/dev/null && echo "FALLA: src/components/ existe" || echo "OK"

# R23: mockData.ts no existe
ls apps/web/lib/mockData.ts 2>/dev/null && echo "FALLA: mockData.ts existe" || echo "OK"

# R24: Mock data solo en mocks/ y tests/
grep -rn "mock\|Mock\|MOCK" apps/web/lib/ apps/web/components/ apps/web/hooks/ --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v ".test." | grep -v "__tests__"
# Resultado esperado: Solo imports de tipos, no datos
```

### Validacion en modo demo

```bash
# Arrancar en modo demo
NEXT_PUBLIC_APP_MODE=demo pnpm --filter web dev

# Verificar:
# 1. DemoBanner aparece
# 2. Navegar a /projects -> muestra "Torre Skyline" y "Atlas Plaza"
# 3. Navegar a /projects/proj_demo_001/documents -> muestra "Contract - Torre Skyline.pdf"
# 4. Navegar a /alerts -> muestra 2 alertas
# 5. Console del browser NO muestra errores de "unhandled request"
```

### Validacion en modo produccion

```bash
# Arrancar en modo produccion (default)
pnpm --filter web dev

# Verificar:
# 1. DemoBanner NO aparece
# 2. Navegar a /projects -> llama a GET /api/v1/projects del backend real
# 3. Si backend no corre: muestra error state (no datos ficticios)
# 4. Si backend corre: muestra datos reales de PostgreSQL
```

---

## 7. Resumen del Contrato en Una Frase

> **Demo es un modo de la aplicacion (`NEXT_PUBLIC_APP_MODE=demo`) que activa MSW para interceptar llamadas HTTP en el browser, NO un conjunto de rutas separadas ni datos hardcodeados en pages.**

---

*Este contrato debe ser referenciado en cada PR que modifique pages, hooks, o routers hasta que todas las violaciones esten resueltas.*
