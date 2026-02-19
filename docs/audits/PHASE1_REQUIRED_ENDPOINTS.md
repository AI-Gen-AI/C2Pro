# Fase 1 — Tarea 1.5: Endpoints Backend Necesarios para Eliminar Mocks
**Fecha:** 2026-02-19
**Dependencias:** Tareas 1.1, 1.2, 1.3, 1.4

---

## Resumen Ejecutivo

| Categoria | Endpoints | Esfuerzo |
|-----------|-----------|----------|
| Ya existen con DB real y estan ACTIVOS | 5 | 0 — ya funcionan |
| Ya existen con DB real pero estan COMENTADOS | 19 | Bajo — descomentar + validar |
| Existen pero son FAKE (reescribir) | 17 | Alto — reemplazar con SQLAlchemy |
| NO existen (crear desde cero) | 3 | Medio — nuevo codigo |
| **TOTAL necesarios** | **44** | |

### Conclusion

**19 endpoints reales ya estan escritos** y solo necesitan ser descomentados en `main.py`. El esfuerzo principal esta en reescribir los 17 endpoints fake de `projects/router.py` y `alerts/router.py`.

---

## Endpoint Map por Page del Frontend

### Page: Dashboard Principal (`(app)/page.tsx`)

**Datos que necesita:** Score global de coherencia, alertas por severidad, tendencias, nombre del proyecto.

| Endpoint | Metodo | Ruta completa | Existe? | Estado | Accion |
|----------|--------|---------------|---------|--------|--------|
| Dashboard Summary | GET | `/api/v1/dashboard/summary` | **NO** | -- | **CREAR** |

**Especificacion del endpoint nuevo:**

```
GET /api/v1/dashboard/summary

Response 200:
{
  "projects": [
    {
      "id": "uuid",
      "name": "string",
      "coherence_score": 78,
      "alert_counts": {
        "critical": 2,
        "high": 5,
        "medium": 8,
        "low": 3
      },
      "document_count": 12,
      "last_analysis_at": "2026-02-19T..."
    }
  ],
  "global_stats": {
    "total_projects": 5,
    "avg_coherence_score": 72,
    "total_alerts": 18,
    "critical_alerts": 2
  }
}

Implementacion:
- Crear DashboardRouter en apps/api/src/dashboard/router.py
- Use case: GetDashboardSummaryUseCase
- Agrega datos de projects + coherence + alerts desde DB
- Requiere: projects table, coherence_scores table, alerts table
```

---

### Page: Lista de Documentos (`(app)/documents/page.tsx`)

**Datos que necesita:** Lista de documentos del proyecto con nombre, tipo, estado, clausulas.

| Endpoint | Metodo | Ruta completa | Existe? | Estado | Accion |
|----------|--------|---------------|---------|--------|--------|
| List project documents | GET | `/api/v1/projects/{id}/documents` | **SI** | DB_REAL (documents router) | **RESOLVER CONFLICTO** |

**Conflicto actual:** Dos routers definen `POST /projects/{id}/documents`:
- `projects/router.py` linea 155 — FAKE (solo retorna 202)
- `documents/router.py` linea 185 — REAL (upload + Celery)

**Accion:** Eliminar el endpoint duplicado de `projects/router.py`. El de `documents/router.py` es el correcto.

**Page action:** Reemplazar `const mockDocuments = [...]` por `useProjectDocuments(projectId)` (hook ya existe y funciona).

---

### Page: Lista de Alertas (`(app)/alerts/page.tsx`)

**Datos que necesita:** Alertas filtradas por severidad, categoria, estado.

| Endpoint | Metodo | Ruta completa | Existe? | Estado | Accion |
|----------|--------|---------------|---------|--------|--------|
| List project alerts | GET | `/api/v1/alerts/projects/{project_id}` | **SI** | DB_REAL pero **COMENTADO** | **DESCOMENTAR** `alerts_router` de `analysis/adapters/http/` |
| Alert stats | GET | `/api/v1/alerts/projects/{project_id}/stats` | **SI** | DB_REAL pero **COMENTADO** | Incluido en el mismo router |

**Router real:** `analysis/adapters/http/alerts_router.py`
- Usa `SqlAlchemyAlertRepository` + use cases (`ListAlertsUseCase`, `GetAlertsStatsUseCase`)
- Soporta filtros: severities, statuses, category, paginacion con cursor
- **Completamente funcional** — solo falta registrarlo en `main.py`

**Accion:**
1. Registrar `alerts_router` de `analysis/adapters/http/alerts_router.py` en `main.py`
2. Desregistrar el `alerts_router` FAKE de `alerts/router.py`
3. Crear hook `useProjectAlerts(projectId)` en el frontend

---

### Page: Matriz RACI (`(app)/raci/page.tsx`)

**Datos que necesita:** Actividades x stakeholders x roles RACI.

| Endpoint | Metodo | Ruta completa | Existe? | Estado | Accion |
|----------|--------|---------------|---------|--------|--------|
| Get RACI matrix | GET | `/api/v1/projects/{project_id}/raci` | **SI** | DB_REAL pero **COMENTADO** | **DESCOMENTAR** |
| Upsert RACI assignment | PUT | `/api/v1/assignments` | **SI** | DB_REAL pero **COMENTADO** | Incluido en el mismo router |

**Router real:** `stakeholders/adapters/http/raci_router.py`
- Usa `GetRaciMatrixUseCase` + `UpsertRaciAssignmentUseCase` -> SQLAlchemy
- **Completamente funcional**

**Accion:**
1. Descomentar `raci_router` en `main.py` (linea 40 + lineas 272-275)
2. Crear hook `useRaciMatrix(projectId)` en el frontend

---

### Page: Project Overview (`(app)/projects/[id]/page.tsx`)

**Datos que necesita:** Detalles del proyecto + metricas (documents, alerts, score).

| Endpoint | Metodo | Ruta completa | Existe? | Estado | Accion |
|----------|--------|---------------|---------|--------|--------|
| Get project by ID | GET | `/api/v1/projects/{project_id}` | SI pero **FAKE_IN_MEMORY** | `_fake_projects` dict | **REESCRIBIR** |

**Accion:** Reescribir `projects/router.py` para que `GET /projects/{id}` consulte PostgreSQL en vez de un dict en memoria.

**Alternativa rapida:** Crear un **nuevo** `projects/adapters/http/real_router.py` que use SQLAlchemy y reemplazar el import en `main.py`. Esto evita romper tests E2E existentes que dependen del fake.

---

### Page: Project Coherence (`(app)/projects/[id]/coherence/page.tsx`)

**Datos que necesita:** Score de coherencia, breakdown por categoria, pesos, alertas.

| Endpoint | Metodo | Ruta completa | Existe? | Estado | Accion |
|----------|--------|---------------|---------|--------|--------|
| Coherence dashboard | GET | `/api/coherence/dashboard/{project_id}` | SI pero **FAKE_RETURN** | Retorna `coherence_score: 78` hardcodeado | **REESCRIBIR** |

**Accion:** Reescribir `get_coherence_dashboard()` en `coherence/router.py` para:
1. Consultar la tabla `coherence_scores` en PostgreSQL
2. Si no hay score calculado, retornar `null` (no 78)
3. Usar `CalculateCoherenceUseCase` que **ya existe** y es funcional

---

### Page: Project Documents (`(app)/projects/[id]/documents/page.tsx`)

| Endpoint | Metodo | Ruta completa | Existe? | Estado | Accion |
|----------|--------|---------------|---------|--------|--------|
| List project documents | GET | `/api/v1/projects/{id}/documents` | **SI** | DB_REAL | **NINGUNA** — ya funciona |

**Estado: OK** — `useProjectDocuments()` -> `apiClient.get("/projects/{id}/documents")` -> `documents/router.py` -> SQLAlchemy.

---

### Page: Project Evidence (`(app)/projects/[id]/evidence/page.tsx`)

| Endpoint | Metodo | Ruta completa | Existe? | Estado | Accion |
|----------|--------|---------------|---------|--------|--------|
| List project documents | GET | `/api/v1/projects/{id}/documents` | **SI** | DB_REAL | **NINGUNA** |
| Get document entities | GET | `/api/v1/documents/{id}/entities` | **SI** | DB_REAL | **NINGUNA** |
| Get document alerts | GET | `/api/v1/alerts?document_id={id}` | Parcial | -- | Verificar |

**Estado: MAYORMENTE OK** — Los hooks `useProjectDocuments`, `useDocumentEntities`, `useDocumentAlerts` ya funcionan.

---

### Page: Lista de Proyectos (`(app)/projects/page.tsx`)

| Endpoint | Metodo | Ruta completa | Existe? | Estado | Accion |
|----------|--------|---------------|---------|--------|--------|
| List projects | GET | `/api/v1/projects` | SI pero **FAKE_IN_MEMORY** | `_fake_projects` dict | **REESCRIBIR** |

**Accion:** Reescribir `list_projects()` en `projects/router.py` para consultar PostgreSQL.

---

### Page: Observability (`(app)/observability/page.tsx`)

| Endpoint | Metodo | Ruta completa | Existe? | Estado | Accion |
|----------|--------|---------------|---------|--------|--------|
| System status | GET | `/api/v1/observability/status` | **SI** | DB_REAL | **NINGUNA** |
| Recent analyses | GET | `/api/v1/observability/analyses` | **SI** | DB_REAL | **NINGUNA** |

**Estado: OK** — Ya funciona end-to-end con `fetch()` directo.

---

### Page: Stakeholders (`(app)/stakeholders/page.tsx`)

| Endpoint | Metodo | Ruta completa | Existe? | Estado | Accion |
|----------|--------|---------------|---------|--------|--------|
| List stakeholders | GET | `/api/v1/stakeholders/projects/{project_id}` | **SI** | DB_REAL pero **COMENTADO** | **DESCOMENTAR** |
| Create stakeholder | POST | `/api/v1/stakeholders/projects/{project_id}` | **SI** | DB_REAL pero **COMENTADO** | Incluido |
| Update stakeholder | PATCH | `/api/v1/stakeholders/{id}` | **SI** | DB_REAL pero **COMENTADO** | Incluido |
| Delete stakeholder | DELETE | `/api/v1/stakeholders/{id}` | **SI** | DB_REAL pero **COMENTADO** | Incluido |

**Router real:** `stakeholders/adapters/http/router.py` — CRUD completo con SQLAlchemy. **Bug detectado:** lineas 154-158 tienen codigo duplicado con raises inalcanzables.

**Accion:**
1. Descomentar `stakeholders_router` en `main.py` (linea 41 + lineas 267-270)
2. Fix bug de lineas duplicadas en `update_stakeholder()`

---

## Inventario Completo: Todos los Endpoints Necesarios

### Categoria A: Ya funcionan (0 esfuerzo)

| # | Endpoint | Router | Page que lo usa |
|---|----------|--------|-----------------|
| A1 | `GET /api/v1/projects/{id}/documents` | documents/router.py | projects/[id]/documents, evidence |
| A2 | `GET /api/v1/documents/{id}` | documents/router.py | evidence (detalle) |
| A3 | `DELETE /api/v1/documents/{id}` | documents/router.py | documents (borrar) |
| A4 | `GET /api/v1/observability/status` | observability/router.py | observability |
| A5 | `GET /api/v1/observability/analyses` | observability/router.py | observability |

---

### Categoria B: Descomentar en main.py (esfuerzo bajo)

| # | Endpoint | Router real (comentado) | Page que lo necesita |
|---|----------|------------------------|---------------------|
| B1 | `GET /alerts/projects/{id}` | analysis/adapters/http/alerts_router.py | alerts |
| B2 | `GET /alerts/projects/{id}/stats` | analysis/adapters/http/alerts_router.py | alerts, dashboard |
| B3 | `GET /alerts/{id}` | analysis/adapters/http/alerts_router.py | alert detail |
| B4 | `PATCH /alerts/{id}` | analysis/adapters/http/alerts_router.py | alert review |
| B5 | `DELETE /alerts/{id}` | analysis/adapters/http/alerts_router.py | alert delete |
| B6 | `GET /stakeholders/projects/{id}` | stakeholders/router.py | stakeholders |
| B7 | `POST /stakeholders/projects/{id}` | stakeholders/router.py | stakeholders (crear) |
| B8 | `PATCH /stakeholders/{id}` | stakeholders/router.py | stakeholders (editar) |
| B9 | `DELETE /stakeholders/{id}` | stakeholders/router.py | stakeholders (eliminar) |
| B10 | `GET /projects/{id}/raci` | stakeholders/raci_router.py | raci |
| B11 | `PUT /assignments` | stakeholders/raci_router.py | raci (editar) |
| B12 | `POST /procurement/wbs` | procurement/router.py | (futuro) |
| B13 | `GET /procurement/wbs/project/{id}` | procurement/router.py | (futuro) |
| B14 | `GET /procurement/wbs/project/{id}/tree` | procurement/router.py | (futuro) |
| B15 | `GET/PUT/DELETE /procurement/wbs/{id}` | procurement/router.py | (futuro) |
| B16 | `POST /procurement/bom` | procurement/router.py | (futuro) |
| B17 | `GET /procurement/bom/project/{id}` | procurement/router.py | (futuro) |
| B18 | `GET/PUT/DELETE /procurement/bom/{id}` | procurement/router.py | (futuro) |
| B19 | `POST /analyze` | analysis/router.py | analysis |

**Pasos concretos en main.py:**

```python
# DESCOMENTAR estas lineas en main.py:

from src.analysis.adapters.http.alerts_router import router as real_alerts_router  # NUEVO
from src.analysis.adapters.http.router import router as analysis_router
from src.stakeholders.adapters.http.router import router as stakeholders_router
from src.stakeholders.adapters.http.raci_router import router as raci_router
from src.procurement.adapters.http.router import router as procurement_router

# REGISTRAR:
app.include_router(real_alerts_router, prefix=api_v1_prefix)
app.include_router(analysis_router, prefix=api_v1_prefix)
app.include_router(stakeholders_router, prefix=api_v1_prefix)
app.include_router(raci_router, prefix=api_v1_prefix)
app.include_router(procurement_router, prefix=api_v1_prefix)

# DESREGISTRAR el alerts_router FAKE:
# ELIMINAR: from src.alerts.router import router as alerts_router
```

---

### Categoria C: Reescribir (reemplazar fake con SQLAlchemy)

| # | Endpoint actual (FAKE) | Router fake | Accion |
|---|------------------------|-------------|--------|
| C1 | `GET /projects` | projects/router.py | Reescribir con `ListProjectsUseCase` -> SQLAlchemy |
| C2 | `GET /projects/{id}` | projects/router.py | Reescribir con `GetProjectUseCase` -> SQLAlchemy |
| C3 | `PATCH /projects/{id}` | projects/router.py | Reescribir con `UpdateProjectUseCase` -> SQLAlchemy |
| C4 | `DELETE /projects/{id}` | projects/router.py | Reescribir con `DeleteProjectUseCase` -> SQLAlchemy |
| C5 | `POST /projects/{id}/documents` | projects/router.py | **ELIMINAR** (duplicado del de documents/router.py) |
| C6 | `POST /projects/{id}/documents/bulk` | projects/router.py | Reescribir o mover a bulk_operations |
| C7 | `POST /projects/{id}/wbs/bulk` | projects/router.py | Reescribir o mover a procurement |
| C8 | `POST /projects/{id}/export` | projects/router.py | Reescribir con job queue real |
| C9 | `GET /bulk-operations/{id}/progress` | bulk_operations/router.py | Conectar con Celery task tracking |
| C10 | `GET /api/coherence/dashboard/{id}` | coherence/router.py | Reescribir con `CalculateCoherenceUseCase` + DB |

**Estrategia recomendada:** Crear `projects/adapters/http/sqlalchemy_router.py` nuevo, migrar los endpoints uno por uno, y cambiar el import en `main.py` cuando esten listos. Esto evita romper tests E2E existentes.

---

### Categoria D: Crear desde cero

| # | Endpoint | Justificacion | Complejidad |
|---|----------|---------------|-------------|
| D1 | `GET /api/v1/dashboard/summary` | No existe. El dashboard principal lo necesita para mostrar vista agregada | Media — agrega datos de 3 tablas |
| D2 | `GET /api/v1/projects/{id}/coherence` | No existe como endpoint de lectura. Solo hay POST `/v0/coherence/evaluate` y GET fake `/api/coherence/dashboard/{id}` | Media — wrapper sobre `CalculateCoherenceUseCase` |
| D3 | `POST /api/v1/projects` | No existe. El frontend tiene `projects/new/page.tsx` pendiente | Baja — CRUD basico |

---

## Orden de Ejecucion Recomendado

### Sprint 1: Quick wins (descomentar)

```
1. Descomentar stakeholders_router   → habilita page stakeholders
2. Descomentar raci_router           → habilita page RACI
3. Registrar alerts_router REAL      → habilita page alerts
   + desregistrar alerts_router FAKE
4. Descomentar procurement_router    → habilita futuras pages
5. Descomentar analysis_router       → habilita page analysis
```

**Resultado:** 19 endpoints reales activados sin escribir codigo nuevo.

### Sprint 2: Reescribir projects router

```
6. Crear projects SQLAlchemy repository (si no existe)
7. Crear use cases: List, Get, Update, Delete
8. Reescribir projects/router.py con SQLAlchemy
9. Eliminar endpoint POST /projects/{id}/documents del projects router
10. Verificar que frontend projects/page.tsx sigue funcionando
```

**Resultado:** 8 endpoints fake reemplazados.

### Sprint 3: Crear endpoints nuevos

```
11. Crear GET /api/v1/dashboard/summary
12. Crear GET /api/v1/projects/{id}/coherence (wrapper de CalculateCoherenceUseCase)
13. Crear POST /api/v1/projects (crear proyecto)
14. Reescribir coherence dashboard endpoint con DB real
```

**Resultado:** Todas las pages tienen endpoint backend real.

### Sprint 4: Frontend migration

```
15. Reemplazar mock inline en 11 pages por hooks + API calls
16. Crear hooks faltantes: useDashboardSummary, useProjectAlerts, useRaciMatrix, useCoherenceScore
17. Crear MSW handlers faltantes
18. Enriquecer seed data de MSW
19. Eliminar app/dashboard/, app/demo/, lib/mockData.ts
```

**Resultado:** Contrato cumplido al 100%.

---

*Este documento cierra la Fase 1 de separacion conceptual. Todas las tareas 1.1-1.5 estan completadas.*
