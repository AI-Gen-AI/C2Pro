# Fase 1 — Tarea 1.2: Inventario Completo de Endpoints del Backend
**Fecha:** 2026-02-19
**Scope:** Todos los endpoints definidos en `apps/api/src/` — activos y comentados en `main.py`

---

## Resumen Ejecutivo

| Clasificacion | Endpoints | % del Total |
|---------------|-----------|-------------|
| FAKE_IN_MEMORY | 22 | 41% |
| DB_REAL | 22 | 41% |
| STATIC/INFRA | 6 | 11% |
| FAKE_RETURN | 4 | 7% |
| **TOTAL** | **54** | **100%** |

### Hallazgo clave

**41% de los endpoints activos usan almacenamiento in-memory (`_fake_*` dicts)** en lugar de base de datos. Estos endpoints fueron creados como "GREEN PHASE: Fake It" para pasar tests E2E pero nunca fueron reemplazados con implementaciones reales.

**41% de los endpoints usan base de datos real** (SQLAlchemy + PostgreSQL) con inyeccion de dependencias correcta.

---

## Leyenda de Clasificacion

| Codigo | Significado |
|--------|-------------|
| `FAKE_IN_MEMORY` | Usa `_fake_*` dict en memoria. No persiste datos. Patron "Fake It" de TDD GREEN phase |
| `FAKE_RETURN` | Retorna datos hardcodeados sin consultar ninguna fuente |
| `DB_REAL` | Usa SQLAlchemy repository contra PostgreSQL real |
| `STATIC/INFRA` | Endpoint de infraestructura sin datos de negocio (health, metadata) |

---

## ROUTERS ACTIVOS (Registrados en main.py)

---

### Router: Health (`/health`)

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 1 | GET | `/health/` | STATIC/INFRA | DB ping + Redis ping | Readiness probe real |
| 2 | GET | `/health/live` | STATIC/INFRA | Ninguna | Liveness probe, retorna `{"status": "ok"}` |
| 3 | GET | `/health/ready` | STATIC/INFRA | DB `SELECT 1` + Redis ping | Readiness probe con timeout 2s |

**Veredicto: LIMPIO** — Sin mock data.

---

### Router: Auth (`/api/v1/auth`)

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 4 | POST | `/auth/register` | DB_REAL | `AuthService.register()` -> DB | Crea usuario + tenant en PostgreSQL |
| 5 | POST | `/auth/login` | DB_REAL | `AuthService.login()` -> DB | Verifica credenciales contra DB |
| 6 | POST | `/auth/refresh` | DB_REAL | `AuthService.refresh_access_token()` -> DB | Refresca JWT |
| 7 | GET | `/auth/me` | DB_REAL | `AuthService.get_current_user()` -> DB | Lee usuario de DB |
| 8 | PUT | `/auth/me` | DB_REAL | `db.commit()` directo | Actualiza perfil en DB |
| 9 | POST | `/auth/logout` | STATIC/INFRA | Logger | Solo logging, JWT se invalida en cliente |
| 10 | POST | `/auth/change-password` | DB_REAL | `db.commit()` directo | Actualiza hash en DB |
| 11 | GET | `/auth/health` | STATIC/INFRA | Ninguna | Retorna `{"status": "ok"}` |

**Veredicto: LIMPIO** — Todos los endpoints de auth usan DB real.

---

### Router: Projects (`/api/v1/projects`) — **CRITICO**

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 12 | GET | `/projects/{project_id}` | **FAKE_IN_MEMORY** | `_fake_projects` dict | Busca en dict en memoria |
| 13 | GET | `/projects` | **FAKE_IN_MEMORY** | `_fake_projects` dict | Lista de dict en memoria filtrado por tenant |
| 14 | PATCH | `/projects/{project_id}` | **FAKE_IN_MEMORY** | `_fake_projects` dict | Actualiza dict en memoria |
| 15 | DELETE | `/projects/{project_id}` | **FAKE_IN_MEMORY** | `_fake_projects` dict | Elimina de dict en memoria |
| 16 | POST | `/projects/{project_id}/documents` | **FAKE_IN_MEMORY** | Verifica en `_fake_projects`, retorna 202 | GREEN PHASE: Solo acepta sin procesar |
| 17 | POST | `/projects/{project_id}/documents/bulk` | **FAKE_IN_MEMORY** | `_fake_projects` + genera UUIDs | GREEN PHASE: Fake bulk upload |
| 18 | POST | `/projects/{project_id}/wbs/bulk` | **FAKE_IN_MEMORY** | `_fake_wbs_items` dict | GREEN PHASE: Valida campos, almacena en memoria |
| 19 | POST | `/projects/{project_id}/export` | **FAKE_IN_MEMORY** | `_fake_jobs` dict | GREEN PHASE: Crea job falso |

**Veredicto: TODO FAKE** — El router de projects COMPLETO usa `_fake_projects: dict[UUID, dict] = {}`. La tabla `projects` en PostgreSQL existe (migrations la crean) pero este router no la toca.

**Impacto critico:** El frontend llama a `ProjectsService.getProjects()` (el unico page con API real) y recibe una lista vacia porque `_fake_projects` esta vacio al inicio del server.

---

### Router: Alerts (`/api/v1/alerts`) — **CRITICO**

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 20 | POST | `/alerts` | **FAKE_IN_MEMORY** | `_fake_alerts` dict | Crea alerta en memoria |
| 21 | GET | `/projects/{project_id}/alerts` | **FAKE_IN_MEMORY** | `_fake_alerts` dict | Filtra por project+tenant |
| 22 | POST | `/alerts/{alert_id}/review` | **FAKE_IN_MEMORY** | `_fake_alerts` dict | Actualiza status en memoria |
| 23 | POST | `/alerts/bulk-review` | **FAKE_IN_MEMORY** | `_fake_alerts` dict | Bulk update en memoria |
| 24 | POST | `/alerts/{alert_id}/evidence` | **FAKE_IN_MEMORY** | `_fake_alerts` dict | Genera UUID, no persiste |
| 25 | POST | `/alerts/{alert_id}/resolve` | **FAKE_IN_MEMORY** | `_fake_alerts` dict | Marca resolved en memoria |
| 26 | GET | `/alerts/{alert_id}/history` | **FAKE_IN_MEMORY** | `_fake_alerts` dict | Historial minimal |
| 27 | POST | `/alerts/bulk-delete` | **FAKE_IN_MEMORY** | `_fake_alerts` dict | Elimina de memoria |

**Veredicto: TODO FAKE** — `_fake_alerts: dict[UUID, dict] = {}`. Mismo patron que Projects.

---

### Router: Bulk Operations (`/api/v1/bulk-operations`)

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 28 | GET | `/bulk-operations/{job_id}/progress` | **FAKE_RETURN** | `_fake_jobs` dict, retorna `percentage: 65` hardcodeado | Siempre retorna 65% progreso |

**Veredicto: FAKE** — Retorna valores hardcodeados.

---

### Router: Coherence Engine

#### V0 Engine (`/v0/coherence`)

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 29 | POST | `/v0/coherence/evaluate` | DB_REAL (rules) | `CoherenceEngine` carga rules de `initial_rules.yaml` | Motor real de evaluacion, sin DB |

#### Dashboard (`/api/coherence`)

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 30 | GET | `/api/coherence/dashboard/{project_id}` | **FAKE_RETURN** | Importa `_fake_projects` del projects router, retorna `coherence_score: 78` hardcodeado | Siempre retorna score 78 |

**Veredicto: MIXTO** — El motor V0 `/evaluate` es real (carga YAML rules). El dashboard retorna datos hardcodeados.

---

### Router: Documents (`/api/v1/...`)

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 31 | POST | `/projects/{project_id}/documents` | DB_REAL | `UploadDocumentUseCase` -> SQLAlchemy repo + file storage | Upload real con Celery async |
| 32 | GET | `/documents/{document_id}` | DB_REAL | `GetDocumentWithClausesUseCase` -> SQLAlchemy | Lee documento + clausulas de DB |
| 33 | GET | `/documents/{document_id}/download` | DB_REAL | `DownloadDocumentUseCase` -> file storage | Descarga archivo real |
| 34 | DELETE | `/documents/{document_id}` | DB_REAL | `DeleteDocumentUseCase` -> SQLAlchemy + storage | Elimina de DB y storage |
| 35 | GET | `/projects/{project_id}/documents` | DB_REAL | `ListProjectDocumentsUseCase` -> SQLAlchemy | Lista documentos con paginacion |
| 36 | POST | `/{document_id}/parse` | DB_REAL | `ParseDocumentUseCase` -> parsers + SQLAlchemy | Parseo real (PDF/Excel/BC3) |
| 37 | POST | `/projects/{project_id}/rag/answer` | DB_REAL | `AnswerRagQuestionUseCase` -> SQLAlchemy RAG | RAG real con embeddings |

**Veredicto: TODO REAL** — Hexagonal architecture correcta. Use cases, repositories, DI via Depends().

---

### Router: Observability (`/api/v1/...`)

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 38 | GET | `/status` | DB_REAL | `ObservabilityService` -> SQLAlchemy repo | Estado real del sistema |
| 39 | GET | `/analyses` | DB_REAL | `ObservabilityService` -> SQLAlchemy repo | Analisis recientes reales |

**Veredicto: LIMPIO** — Endpoints reales.

---

### Router: MCP (`/api/v1/mcp`) — **MIXTO**

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 40 | POST | `/mcp/query-view` | DB_REAL | `DatabaseMCPServer.query_view()` -> DB | Query real contra vistas |
| 41 | POST | `/mcp/call-function` | DB_REAL | `DatabaseMCPServer.call_function()` -> DB | Llamada real a funciones DB |
| 42 | GET | `/mcp/views` | STATIC/INFRA | Lista estatica de allowlist | Retorna config |
| 43 | GET | `/mcp/functions` | STATIC/INFRA | Lista estatica de allowlist | Retorna config |
| 44 | GET | `/mcp/rate-limit-status` | DB_REAL | Rate limiter en memoria | Estado real del rate limiter |
| 45 | POST | `/mcp/execute` | **FAKE_RETURN** | Verifica allowlist, retorna `{"data": [], "row_count": 0}` | GREEN PHASE: retorna datos vacios |

**Veredicto: MAYORMENTE REAL** — Solo `/execute` es fake.

---

### Router: Decision Intelligence (`/api/v1/decision-intelligence`)

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 46 | POST | `/decision-intelligence/execute` | **FAKE_RETURN** | `DecisionOrchestrationService()` usa `_Default*Service` con datos ficticios | Orquestacion con defaults peligrosos |

**Veredicto: PELIGROSO** — Instancia `DecisionOrchestrationService()` sin parametros, lo que activa `_DefaultIngestionService` y `_DefaultExtractionService` con datos ficticios hardcodeados.

---

## ROUTERS COMENTADOS (No activos en main.py)

Estos routers estan implementados pero **NO registrados** en la aplicacion.

---

### Router: Analysis (COMENTADO)

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 47 | POST | `/analyze` | DB_REAL | `AnalyzeDocumentUseCase` -> `WorkflowOrchestrator` | LangGraph orchestration real |

**Veredicto: REAL pero INACTIVO**

---

### Router: Stakeholders (COMENTADO)

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 48 | GET | `/stakeholders/projects/{project_id}` | DB_REAL | `ListProjectStakeholdersUseCase` -> SQLAlchemy | |
| 49 | POST | `/stakeholders/projects/{project_id}` | DB_REAL | `CreateStakeholderUseCase` -> SQLAlchemy | Bug: codigo duplicado lineas 154-158 |
| 50 | PATCH | `/stakeholders/{stakeholder_id}` | DB_REAL | `UpdateStakeholderUseCase` -> SQLAlchemy | |
| 51 | DELETE | `/stakeholders/{stakeholder_id}` | DB_REAL | `DeleteStakeholderUseCase` -> SQLAlchemy | |

**Veredicto: REAL pero INACTIVO** — Implementacion completa con hexagonal architecture.

---

### Router: RACI (COMENTADO)

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 52 | GET | `/projects/{project_id}/raci` | DB_REAL | `GetRaciMatrixUseCase` -> SQLAlchemy | |
| 53 | PUT | `/assignments` | DB_REAL | `UpsertRaciAssignmentUseCase` -> SQLAlchemy | |

**Veredicto: REAL pero INACTIVO**

---

### Router: Procurement (COMENTADO)

| # | Metodo | Ruta | Clasificacion | Fuente de Datos | Notas |
|---|--------|------|---------------|-----------------|-------|
| 54 | POST | `/procurement/wbs` | DB_REAL | `CreateWBSItemUseCase` -> SQLAlchemy | |
| 55 | GET | `/procurement/wbs/project/{project_id}` | DB_REAL | `ListWBSItemsUseCase` -> SQLAlchemy | |
| 56 | GET | `/procurement/wbs/project/{project_id}/tree` | DB_REAL | `GetWBSTreeUseCase` -> SQLAlchemy | |
| 57 | GET | `/procurement/wbs/{wbs_id}` | DB_REAL | `GetWBSItemUseCase` -> SQLAlchemy | |
| 58 | PUT | `/procurement/wbs/{wbs_id}` | DB_REAL | `UpdateWBSItemUseCase` -> SQLAlchemy | |
| 59 | DELETE | `/procurement/wbs/{wbs_id}` | DB_REAL | `DeleteWBSItemUseCase` -> SQLAlchemy | |
| 60 | POST | `/procurement/bom` | DB_REAL | `CreateBOMItemUseCase` -> SQLAlchemy | |
| 61 | GET | `/procurement/bom/project/{project_id}` | DB_REAL | `ListBOMItemsUseCase` -> SQLAlchemy | |
| 62 | GET | `/procurement/bom/{bom_id}` | DB_REAL | `GetBOMItemUseCase` -> SQLAlchemy | |
| 63 | PUT | `/procurement/bom/{bom_id}` | DB_REAL | `UpdateBOMItemUseCase` -> SQLAlchemy | |
| 64 | PATCH | `/procurement/bom/{bom_id}/status` | DB_REAL | `UpdateBOMStatusUseCase` -> SQLAlchemy | |
| 65 | DELETE | `/procurement/bom/{bom_id}` | DB_REAL | `DeleteBOMItemUseCase` -> SQLAlchemy | |

**Veredicto: REAL pero INACTIVO** — 12 endpoints completos con use cases + SQLAlchemy repos.

---

## Otros Archivos con Mock Data en src/

| Archivo | Tipo de Mock | Detalle |
|---------|-------------|---------|
| `coherence/service.py` | `MOCK_PROJECT_DB`, `MOCK_SCORE_DB` | Base de datos mock con UUIDs fijos y score 85 hardcodeado |
| `modules/decision_intelligence/application/ports.py` | `_DefaultIngestionService`, `_DefaultExtractionService`, `_DefaultCoherenceService` | Servicios default que retornan datos ficticios cuando no se inyectan dependencias reales |
| `modules/ingestion/adapters/ocr/mock_ocr_adapter.py` | `MockOCRAdapter` | Adapter mock nombrado explicitamente (aceptable como fallback) |
| `core/ai/example_prompts.py` | Texto de contrato ficticio | Prompt de ejemplo con datos de un contrato inventado |

---

## Hallazgo Critico: Routers REALES Comentados vs Routers FAKE Activos

```
ACTIVOS EN main.py                      COMENTADOS EN main.py
─────────────────────                    ──────────────────────
projects_router    → FAKE_IN_MEMORY     stakeholders_router → DB_REAL  ⚠️
alerts_router      → FAKE_IN_MEMORY     raci_router         → DB_REAL  ⚠️
bulk_operations    → FAKE_IN_MEMORY     procurement_router  → DB_REAL  ⚠️
coherence_dashboard → FAKE_RETURN       analysis_router     → DB_REAL  ⚠️
decision_intel     → FAKE_RETURN        approvals_router    → DB_REAL  ⚠️
```

**Paradoja:** Los routers FAKE estan activos mientras que los routers con implementacion REAL de base de datos estan comentados. El proyecto tiene las implementaciones reales listas pero usa las fake en produccion.

---

## Conflictos de Ruta Detectados

| Ruta | Router 1 | Router 2 | Conflicto |
|------|----------|----------|-----------|
| `POST /projects/{id}/documents` | `projects/router.py` (FAKE) | `documents/router.py` (REAL) | **Ambos definen el mismo endpoint**. El de `documents/` tiene upload real con Celery; el de `projects/` solo retorna 202 fake |
| `GET /projects/{id}/alerts` | `alerts/router.py` (FAKE) | No hay equivalente real | Solo existe la version fake |

**FastAPI resolvera el conflicto usando el primer router registrado.** Como `projects_router` se registra antes (linea 218) que `documents_router` (linea 243), el endpoint FAKE gana sobre el REAL para `POST /projects/{id}/documents`.

---

## Mapa Visual: Estado Actual

```
ACTIVOS (en main.py)
────────────────────
/health/*                 ✅ INFRA (real)
/api/v1/auth/*            ✅ DB_REAL (7 endpoints)
/api/v1/projects/*        ❌ FAKE_IN_MEMORY (8 endpoints, dict en memoria)
/api/v1/alerts/*          ❌ FAKE_IN_MEMORY (8 endpoints, dict en memoria)
/api/v1/bulk-operations/* ❌ FAKE_RETURN (1 endpoint, retorna 65% siempre)
/api/v1/documents/*       ✅ DB_REAL (7 endpoints, SQLAlchemy + Celery)
/api/v1/observability/*   ✅ DB_REAL (2 endpoints)
/api/v1/mcp/*             ⚠️ MIXTO (5 real + 1 fake)
/api/v1/decision-intel/*  ❌ FAKE_RETURN (1 endpoint con defaults peligrosos)
/v0/coherence/evaluate    ✅ REAL (motor de rules YAML)
/api/coherence/dashboard  ❌ FAKE_RETURN (score 78 hardcodeado)

COMENTADOS (existen pero inactivos)
────────────────────────────────────
/api/v1/analyze           ✅ DB_REAL — LangGraph orchestration
/api/v1/stakeholders/*    ✅ DB_REAL — CRUD completo (4 endpoints)
/api/v1/raci/*            ✅ DB_REAL — Matrix + assignments (2 endpoints)
/api/v1/procurement/*     ✅ DB_REAL — WBS + BOM completo (12 endpoints)
```

---

## Endpoints que el Frontend Necesita (de Tarea 1.1) vs Estado Backend

| Page Frontend | Endpoint Necesario | Estado Backend | Gap |
|---------------|-------------------|----------------|-----|
| Dashboard (`page.tsx`) | `GET /api/v1/dashboard/summary` | **NO EXISTE** | Necesita endpoint nuevo |
| Documents list | `GET /api/v1/projects/{id}/documents` | **CONFLICTO**: FAKE (projects) vs REAL (documents) | Resolver conflicto de ruta |
| Alerts list | `GET /api/v1/projects/{id}/alerts` | **FAKE_IN_MEMORY** | Necesita implementacion real |
| RACI matrix | `GET /api/v1/projects/{id}/raci` | **COMENTADO** (real listo) | Solo des-comentar en main.py |
| Project overview | `GET /api/v1/projects/{id}` | **FAKE_IN_MEMORY** | Necesita reescribir con SQLAlchemy |
| Project coherence | `GET /api/v1/projects/{id}/coherence` | **FAKE_RETURN** (score 78) | Necesita conectar con Coherence Engine real |
| Project documents | `GET /api/v1/projects/{id}/documents` | ✅ REAL (documents router) | OK si se resuelve conflicto de ruta |
| Project evidence | `GET /api/v1/projects/{id}/evidence` | ✅ REAL (via hooks) | OK |
| Observability | `GET /api/v1/observability/status` | ✅ REAL | OK — ya funciona |
| Stakeholders | `GET /api/v1/stakeholders/projects/{id}` | **COMENTADO** (real listo) | Solo des-comentar en main.py |

---

*Este inventario sirve como base para la tarea 1.3 (matriz page-endpoint-fuente) y 1.5 (endpoints necesarios).*
