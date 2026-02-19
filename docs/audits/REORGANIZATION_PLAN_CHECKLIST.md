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
- [x] **2.5** Eliminar `app/dashboard/` (duplicado de `app/(dashboard)/`)
  - Comparados 9 pares: 5 identicos, 4 con diferencias menores (dashboard/ era version demo/prototipo)
  - Movido unico archivo exclusivo: `projects/[id]/alerts/page.tsx` → `(dashboard)/projects/[id]/alerts/`
  - Eliminado `app/dashboard/` completo (10 archivos)
- [ ] **2.6** Eliminar `app/demo/` (demo se controla por env variable, no por ruta)
- [ ] **2.7** Renombrar `app/(dashboard)/` a `app/(app)/` para claridad semántica
- [ ] **2.8** Eliminar `lib/mockData.ts` — mover datos relevantes a `mocks/data/seed.ts`
- [ ] **2.9** Verificar que MSW handlers cubren todos los endpoints que las pages necesitan
- [ ] **2.10** Hacer que `useAppModeStore` realmente controle el banner demo y cualquier UI condicional

**Entregable:** Frontend con estructura única y limpia. Zero datos mock en pages.

---

## Fase 3 — Limpieza de Dominio Backend (Semana 5-6)

**Objetivo:** Eliminar mock data de producción, corregir bounded contexts.

- [ ] **3.1** Eliminar `MOCK_PROJECT_DB` y `MOCK_SCORE_DB` de `coherence/service.py`
- [ ] **3.2** Eliminar `_DefaultExtractionService` y `_DefaultIngestionService` de `decision_intelligence/ports.py` — reemplazar con errores explícitos
- [ ] **3.3** Mover `core/ai/example_prompts.py` a tests o docs
- [ ] **3.4** Consolidar entidad `Project` en una sola definición (elegir Pydantic o dataclass)
- [ ] **3.5** Eliminar `engine.py` legacy de coherence (mantener solo `engine_v2.py`)
- [ ] **3.6** Crear shared DTOs/events para comunicación entre bounded contexts en vez de importar modelos de dominio
- [ ] **3.7** Refactorizar `analysis/adapters/graph/knowledge_graph.py` para no importar de `documents.domain`, `procurement.domain`, `stakeholders.domain`
- [ ] **3.8** Extraer `AlertSeverity` a un módulo shared kernel si es necesario compartirlo

**Entregable:** Backend sin mock data en src/, bounded contexts respetados.

---

## Fase 4 — Refactor Frontend: Pages como orquestadores puros (Semana 7-8)

**Objetivo:** Cada page solo hace fetch + renderiza componentes.

- [ ] **4.1** `(app)/page.tsx` -> Server component que llama a `DashboardService.getSummary()`
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
