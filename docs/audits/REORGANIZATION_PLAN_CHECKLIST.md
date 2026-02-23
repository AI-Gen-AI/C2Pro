# Plan de Reorganización C2Pro — Checklist de Seguimiento
**Creado:** 2026-02-19
**Basado en:** `STRATEGIC_ARCHITECTURE_AUDIT_2026-02-19.md`

---

## Fase 1 — Separación Conceptual (Semana 1-2)

**Objetivo:** Definir qué es demo y qué es producción sin tocar código.

- [x] **1.1** Inventariar cada page del frontend y clasificarla: ¿usa API real o datos mock?
  - Resultado: `PHASE1_FRONTEND_PAGE_INVENTORY.md`
- [x] **1.2** Inventariar cada endpoint del backend y clasificar: ¿tiene mock data hardcodeada?
  - Resultado: `PHASE1_BACKEND_ENDPOINT_INVENTORY.md`
- [x] **1.3** Documentar la matriz page <-> endpoint <-> fuente de datos
  - Resultado: `PHASE1_PAGE_ENDPOINT_MATRIX.md`
- [x] **1.4** Definir el contrato: "En producción, TODA page llama a API. En demo, MSW intercepta"
  - Resultado: `DEMO_VS_PROD_CONTRACT.md`
- [x] **1.5** Definir qué endpoints backend son necesarios para que las pages funcionen sin mock
  - Resultado: `PHASE1_REQUIRED_ENDPOINTS.md`

**Entregable:** `DEMO_VS_PROD_CONTRACT.md` ✅

---

## Fase 2 — Reorganización Estructural del Frontend (Semana 3-4)

**Objetivo:** Una sola estructura de componentes, una sola estructura de rutas.

- [x] **2.1** Auditar `components/` vs `src/components/features/` componente por componente
  - Resultado: `PHASE2_COMPONENT_AUDIT.md`
- [x] **2.2** Para cada duplicado, elegir la mejor implementación y consolidar
  - Resultado: `PHASE2_DUPLICATE_CONSOLIDATION.md`
- [x] **2.3** Mover todos los componentes de `src/components/features/` a `components/features/`
  - 70 archivos movidos: features/ (11 subdirectorios), layout/ (ProjectTabs, ThemeToggle), providers/ (SentryInit)
  - `src/components/` eliminado completamente
- [x] **2.4** Actualizar todos los imports (`@/src/components` -> `@/components/features`)
  - 53 imports actualizados en 48 archivos
  - Layout/providers aplanados: `@/components/layout/ProjectTabs`, `@/components/layout/ThemeToggle`, `@/components/providers/SentryInit`
  - Verificado: 0 referencias restantes a `@/src/components`
- [x] **2.5** Eliminar `app/dashboard/` (duplicado de `app/(app)/`)
  - Comparados 9 pares: 5 identicos, 4 con diferencias menores (dashboard/ era version demo/prototipo)
  - Movido unico archivo exclusivo: `projects/[id]/alerts/page.tsx` → `(app)/projects/[id]/alerts/`
  - Eliminado `app/dashboard/` completo (10 archivos)
- [x] **2.6** Eliminar `app/demo/` (demo se controla por env variable, no por ruta)
  - Eliminados 3 archivos (layout, redirect page, re-export page) — zero contenido unico
  - Actualizados 2 links en landing-page-content.tsx: `/demo/projects` → `/projects`
  - Actualizado e2e test s1-12-demo-access.spec.ts para rutas sin `/demo/`
- [x] **2.7** Renombrar `app/(dashboard)/` a `app/(app)/` para claridad semántica
  - Renombrado directorio: 18 archivos movidos sin cambio de contenido
  - Zero imports afectados (Next.js route groups son transparentes a @/ aliases)
  - Actualizadas 19 docs con referencia `(dashboard)` → `(app)` (excluido context/Legacy/)
- [x] **2.8** Eliminar `lib/mockData.ts` — mover datos relevantes a `mocks/data/seed.ts`
  - `lib/mockData.ts` tenia zero imports — codigo muerto (303 lineas)
  - Datos migrados a `mocks/data/seed.ts` via @mswjs/data factory: 6 projects, 8 alerts, 7 stakeholders
  - Archivo eliminado
- [x] **2.9** Verificar que MSW handlers cubren todos los endpoints que las pages necesitan
  - Auditoria completa: hooks/pages vs MSW handlers
  - Gaps encontrados y corregidos en `mocks/handlers/custom/demo-data.ts`:
    - GET `/api/v1/alerts?document_id=` — nuevo (useDocumentAlerts)
    - GET `/api/v1/stakeholders?project_id=` — nuevo (useStakeholders)
    - PATCH `/api/v1/stakeholders/:id` — nuevo (useUpdateStakeholder)
    - POST `/api/v1/auth/login` — nuevo
    - POST `/api/v1/auth/register` — nuevo
    - POST `/api/v1/auth/refresh` — nuevo
    - GET `/api/v1/auth/me` — nuevo
    - POST `/api/v1/auth/logout` — nuevo
  - Fix: GET `/projects` ahora retorna `{ items, total, page, ... }` (ProjectListResponse)
  - Nota: `getDocumentEntities` es placeholder (retorna `[]`), no necesita handler
- [x] **2.10** Hacer que `useAppModeStore` realmente controle el banner demo y cualquier UI condicional
  - Store: exporta `selectIsDemoMode` selector para evitar `mode === "demo"` disperso
  - Layout: `DemoBanner` ahora condicional via `useAppModeStore(selectIsDemoMode)` en `(app)/layout.tsx`
  - Providers: MSW init usa store en vez de `env.IS_DEMO` directo
  - DemoBanner: proyecto default actualizado a "Petrochemical Plant EPC" (match seed data)
  - `instrumentation.ts` mantiene `process.env` directo (server-side, pre-React)
  - Test: nuevo caso para `selectIsDemoMode`

**Entregable:** Frontend con estructura única y limpia. Zero datos mock en pages.

---

## Fase 3 — Limpieza de Dominio Backend (Semana 5-6)

**Objetivo:** Eliminar mock data de producción, corregir bounded contexts.

- [x] **3.1** Eliminar `MOCK_PROJECT_DB` y `MOCK_SCORE_DB` de `coherence/service.py`
  - Removidos `MOCK_PROJECT_DB`, `MOCK_SCORE_DB`, la clase `CoherenceScore` mock, y `get_coherence_service()` singleton
  - `CoherenceService` reescrito como facade async sobre repos reales (`SqlAlchemyCoherenceRepository`, `SQLAlchemyProjectRepository`)
  - Test `test_full_scoring_loop.py`: eliminado import roto (`src.modules.coherence`) y 3 inyecciones a dicts mock
- [x] **3.2** Eliminar `_DefaultExtractionService` y `_DefaultIngestionService` de `decision_intelligence/ports.py` — reemplazar con errores explícitos
  - Eliminadas las 5 clases `_Default*` (Ingestion, Extraction, Retrieval, CoherenceScoring, HITL) — mismo anti-patron
  - `DecisionOrchestrationService.__init__`: 5 ports ahora requeridos, `_require()` lanza `TypeError` explicito si falta alguno
  - Router: `get_decision_orchestration_service()` lanza `NotImplementedError` hasta que se conecten ports reales
  - Test `test_i13_i14_security_controls.py`: actualizado con stubs explicitos locales en vez de depender de `_Default*`
- [x] **3.3** Mover `core/ai/example_prompts.py` a tests o docs
  - `git mv apps/api/src/core/ai/example_prompts.py docs/api/example_prompts.py`
  - Actualizadas 2 refs en PROMPT_TEMPLATES_GUIDE.md y CE-S2-008_IMPLEMENTATION_SUMMARY.md
- [x] **3.4** Consolidar entidad `Project` en una sola definición (elegir Pydantic o dataclass)
  - **Eleccion: dataclass** (`src/projects/domain/models.py`) — entidad de dominio canonica con validacion y state machine
  - Eliminado `src/projects/domain/project.py` — duplicado Pydantic (zero imports, codigo muerto)
  - Router HTTP: eliminados `ProjectResponse` y `ProjectListResponse` inline → importa `ProjectDetailResponse` y `ProjectListResponse` de `dtos.py`
  - Helper `_to_response()` mapea `_fake_projects` dict a `ProjectDetailResponse` con defaults sensibles
- [x] **3.5** Eliminar `engine.py` legacy de coherence (mantener solo `engine_v2.py`)
  - Eliminado `engine.py` — todo el tráfico migrado a `CoherenceEngineV2` en `engine_v2.py`
  - Router: `get_coherence_engine()` ahora crea `CoherenceEngineV2` con `enable_llm_rules=False`
  - v2 sync `evaluate()` corregido: retorna `overall_score` + `category_breakdown` (era `score` — bug Pydantic)
  - `test_engine.py`: imports corregidos (`src.coherence.engine_v2`), `result.score` → `result.overall_score`
  - `test_engine_v2.py`: imports corregidos, misma corrección `score` → `overall_score`
  - Alias `CoherenceEngine = CoherenceEngineV2` añadido para backward compatibility
  - README y `__init__.py` actualizados para reflejar solo v2
- [x] **3.6** Crear shared DTOs/events para comunicación entre bounded contexts en vez de importar modelos de dominio
  - Creado `src/shared_kernel/` con `enums.py` y `dtos.py`
  - `enums.py`: `AlertSeverity`, `AlertStatus`, `RACIRole`, `WBSItemType` — definiciones canónicas
  - `dtos.py`: `WBSItemDTO` — DTO cross-context para transferencia WBS
  - Módulos propietarios (`analysis/domain/enums.py`, `stakeholders/domain/models.py`, `procurement/domain/models.py`, `projects/domain/wbs_item_dto.py`) re-exportan para backward compat
  - 4 archivos coherence actualizados: `alert_generator.py`, `services/alerts/generator.py`, `services/scoring/calculator.py`, `services/scoring/weights.py` → `from src.shared_kernel.enums`
  - 2 archivos analysis actualizados: `raci_generator.py` (RACIRole), `nodes.py` (AlertSeverity, WBSItemType) → `from src.shared_kernel.enums`
  - 1 archivo procurement actualizado: `import_wbs_from_projects_use_case.py` → `from src.shared_kernel.dtos`
  - `knowledge_graph.py`: RACIRole migrado a shared_kernel (entity imports quedan para 3.7)
- [x] **3.7** Refactorizar `analysis/adapters/graph/knowledge_graph.py` para no importar de `documents.domain`, `procurement.domain`, `stakeholders.domain`
  - Creado `src/analysis/ports/graph_entities.py` con 4 `Protocol` classes: `ClauseView`, `WBSTaskView`, `StakeholderView`, `RaciAssignmentView`
  - `knowledge_graph.py`: eliminados 3 imports de domain (`documents.domain.models.Clause`, `procurement.domain.models.WBSItem`, `stakeholders.domain.models.{RaciAssignment, Stakeholder}`)
  - Type hints actualizados en `_load_*` methods para usar protocols
  - Cero cambios en repositorios — entidades satisfacen protocols por structural typing
- [x] **3.8** Extraer `AlertSeverity` a un módulo shared kernel si es necesario compartirlo
  - Completado como parte de 3.6 — `AlertSeverity` y `AlertStatus` en `src/shared_kernel/enums.py`

**Entregable:** Backend sin mock data en src/, bounded contexts respetados.

---

## Fase 4 — Refactor Frontend: Pages como orquestadores puros (Semana 7-8)

**Objetivo:** Cada page solo hace fetch + renderiza componentes.

- [x] **4.1** `(app)/page.tsx` -> Server component que llama a `DashboardService.getSummary()`
  - `page.tsx`: eliminado `'use client'` + hardcoded `const DATA` → async server component
  - Flujo: `ProjectsService.getProjects()` → primer proyecto → `DashboardService.getSummary(id)`
  - Error state con mensaje contextual si API no disponible o sin proyectos
  - `DashboardService.ts`: `fetch()` a `GET /api/coherence/dashboard/{id}` con `revalidate: 60`
  - `DashboardClient.tsx`: client component extraido con `useState` (view toggle, category selection)
  - `DashboardSummary` type añadido a `models/index.ts`
  - MSW handler `GET /api/coherence/dashboard/:projectId` añadido a `demo-data.ts`
- [ ] **4.2** `(app)/documents/page.tsx` -> Server component que llama a `DocumentsService.list()`
- [ ] **4.3** `(app)/projects/[id]/coherence/page.tsx` -> llama a `CoherenceService.getScore(id)`
- [ ] **4.4** Asegurar que cada page tiene: loading state, error state, empty state
- [ ] **4.5** Implementar error boundaries a nivel de layout
- [ ] **4.6** Agregar MSW handlers para cada endpoint nuevo que las pages necesiten
- [ ] **4.7** Verificar que `NEXT_PUBLIC_APP_MODE=demo` + MSW produce la misma UX que antes (sin regresión)
- [ ] **4.8** Eliminar cualquier `const DATA = {...}` o `const mock* = [...]` que quede en pages

**Entregable:** Frontend donde toda data viene de API (real o mock via MSW).

---

## Fase 5 — Consolidación y Validación (Semana 9-10)

- [ ] **5.1** Ejecutar todos los tests existentes y verificar que pasan
- [ ] **5.2** Verificar flujo completo en modo demo (MSW)
- [ ] **5.3** Verificar flujo completo en modo producción (API real)
- [ ] **5.4** Documentar la arquitectura final en un ADR
- [ ] **5.5** Actualizar los diagramas de flujo para reflejar la realidad del código
- [ ] **5.6** Integrar los nodos faltantes del LangGraph (N1-N17) como wrapping de use cases existentes
- [ ] **5.7** Implementar HITL service real (no solo ports)
- [ ] **5.8** Verificar que feature flags del backend realmente bloquean endpoints no-ready

---

## Checklist de Auditoría Técnica (Validación Final)

### Frontend

- [ ] Solo existe UN directorio de componentes (`components/`)
- [ ] No existe `src/components/` como directorio paralelo
- [ ] No existe `app/dashboard/` (solo `app/(app)/`)
- [ ] No existe `app/demo/` como directorio de rutas
- [ ] Ninguna page contiene `const mock`, `const DATA`, o datos hardcodeados
- [ ] Todas las pages hacen fetch a la API via el client generado
- [ ] MSW handlers cubren todos los endpoints que las pages necesitan
- [ ] `useAppModeStore` se usa activamente para controlar UI demo vs prod
- [ ] Existe error boundary a nivel de layout
- [ ] Cada page tiene loading, error, y empty state
- [ ] No hay imports cruzados entre `@/src/` y `@/components/`
- [ ] `lib/mockData.ts` no existe (datos mock solo en `mocks/`)
- [ ] No hay mensajes en español en código con UI en inglés (o viceversa, pero consistente)

### Backend

- [ ] No existe `MOCK_*` variables en codigo fuente (fuera de tests)
- [ ] No existen `_Default*Service` que retornen datos ficticios
- [ ] La entidad `Project` tiene una sola definicion canonica
- [ ] Ningun modulo importa `from src.{otro_modulo}.domain.models`
- [ ] Si se comparte un enum (ej: `AlertSeverity`), esta en un shared kernel
- [ ] `coherence/engine.py` legacy esta eliminado (solo `engine_v2.py`)
- [ ] Feature flags se verifican en cada endpoint protegido
- [ ] `example_prompts.py` no esta en `/src/` (movido a tests o docs)
- [ ] Cada bounded context puede testearse en aislamiento

### Orquestacion

- [ ] Los 17 nodos del LangGraph estan implementados como funciones
- [ ] Cada nodo wrappea un use case existente (no duplica logica)
- [ ] El GraphState tiene todos los campos necesarios
- [ ] HITL tiene service implementation (no solo ports)
- [ ] Hay tests de integracion para el flujo completo del grafo

### Separacion Demo/Produccion

- [ ] `NEXT_PUBLIC_APP_MODE` controla el modo (demo/production)
- [ ] En demo: MSW intercepta todas las llamadas HTTP
- [ ] En produccion: MSW no se inicializa
- [ ] No hay rutas exclusivas de demo (demo es un modo, no una ruta)
- [ ] El backend no tiene modo demo (siempre responde con datos reales)
- [ ] Mock data solo existe en: `apps/web/mocks/` y `tests/`
