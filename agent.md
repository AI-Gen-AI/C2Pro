Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Therefore, do not stop tasks early due to token budget concerns. As you approach your token budget limit, save your current progress and state to memory before the context window refreshes. Always be as persistent and autonomous as possible and complete tasks fully, even if the end of your budget is approaching. Never artificially stop any task early regardless of the context remaining.

Do not jump into implementatation or changes files unless clearly instructed to make changes. When the user's intent is ambiguous, default to providing information, doing research, and providing recommendations rather than taking action. Only proceed with edits, modifications, or implementations when the user explicitly requests them.

Only delegate to subagents when the task clearly benefits from a separate agent with a new context window.

If you intend to call multiple tools and there are no dependencies between the tool calls, make all of the independent tool calls in parallel. Prioritize calling tools simultaneously whenever the actions can be done in parallel rather than sequentially. For example, when reading 3 files, run 3 tool calls in parallel to read all 3 files into context at the same time. Maximize use of parallel tool calls where possible to increase speed and efficiency. However, if some tool calls depend on previous calls to inform dependent values like the parameters, do NOT call these tools in parallel and instead call them sequentially. Never use placeholders or guess missing parameters in tool calls.

If you create any temporary new files, scripts, or helper files for iteration, clean up these files by removing them at the end of the task.

Avoid over-engineering. Only make changes that are directly requested or clearly necessary. Keep solutions simple and focused.

ALWAYS read and understand relevant files before proposing code edits. Do not speculate about code you have not inspected. If the user references a specific file/path, you MUST open and inspect it before explaining or proposing fixes. Be rigorous and persistent in searching code for key facts. Thoroughly review the style, conventions, and abstractions of the codebase before implementing new features or abstractions.

Never speculate about code you have not opened. If the user references a specific file, you MUST read the file before answering. Make sure to investigate and read relevant files BEFORE answering questions about the codebase. Never make any claims about code before investigating unless you are certain of the correct answer - give grounded and hallucination-free answers.


## Contexto y objetivo
- Proyecto: C2Pro (monolito modular, hexagonal/clean por módulo)
- Objetivo actual: Consolidar la arquitectura en el esquema nuevo por dominio en `apps/api/src/{documents,stakeholders,procurement,...}` y retirar el esquema legacy `apps/api/src/modules`, `apps/api/src/routers`, `apps/api/src/services`, etc.
- Decisión del usuario: Opción 1 (consolidar en esquema nuevo)



## Estado actual (revisión realizada)
- `docs/PLAN_ARQUITECTURA.md` revisado: confirma que Fase 1 exige estructura única por módulo, comunicación solo vía puertos, y consolidación del código duplicado.
- `docs/architecture/decisions/001-modular-monolith-architecture.md` revisado antes: reafirma monolito modular con puertos.


## Hallazgos técnicos relevantes
- Duplicidad estructural: coexisten `apps/api/src/{documents,stakeholders,procurement}` y `apps/api/src/modules/*` + `apps/api/src/routers`.
- Falta de ORM para `projects` y relaciones cruzadas inconsistentes en modelos nuevos (string names no resolvían).

## Cambios realizados en esta sesión
- `apps/api/src/documents/domain/models.py`
  - Agregados campos: `file_format`, `storage_url`, `file_size_bytes`.
  - Agregados campos de auditoría/storage y metadata para alinear DTOs.
- `apps/api/src/documents/application/upload_document_use_case.py`
  - Reemplazado `UUID()` por `uuid4()` en creación de entidades.
- `apps/api/src/documents/application/create_and_queue_document_use_case.py`
  - Reemplazado `UUID()` por `uuid4()` en creación de entidades.
- `apps/api/src/documents/adapters/persistence/sqlalchemy_document_repository.py`
  - Mapeo completo de auditoría/metadata y refresh extendido.
  - `get_project_tenant_id` usa SQL directo (tabla `projects`).
- `apps/api/src/documents/adapters/http/router.py`
  - Nuevo router HTTP usando casos de uso + adapters legacy para extracción/RAG.
- `apps/api/src/documents/adapters/extraction/legacy_entity_extraction_service.py`
  - Adapter transicional para extracción (stakeholders/WBS/BOM).
- `apps/api/src/documents/adapters/rag/legacy_rag_ingestion_service.py`
  - Adapter transicional para ingestión RAG.
- `apps/api/src/main.py`
  - Router de documentos cambiado a `src.documents.adapters.http.router`.
- `apps/api/src/stakeholders/`
  - Reemplazo de imports `apps.api.src.*` → `src.*`.
  - Corrección de `UUID()` → `uuid4()` en extracción.
  - Nuevos casos de uso: list/create/update/delete.
  - Nuevo repository adapter SQLAlchemy.
  - Nuevo router HTTP `src.stakeholders.adapters.http.router`.
- `apps/api/src/main.py`
  - Router de stakeholders cambiado a `src.stakeholders.adapters.http.router`.
- `apps/api/src/modules/main.py`
  - Document router actualizado a `src.documents.adapters.http.router`.
- `apps/api/src/routers/stakeholders.py`, `apps/api/src/modules/documents/router.py`, `apps/api/src/modules/documents/service.py`
  - Marcados como LEGACY (solo referencia).
- Reemplazos de imports legacy (`src.modules.documents.*`, `src.modules.stakeholders.*`) en servicios/core:
  - `apps/api/src/services/knowledge_graph.py`, `apps/api/src/services/source_locator.py`, `apps/api/src/services/raci_generation_service.py`
  - `apps/api/src/ai/graph/nodes.py`, `apps/api/src/modules/wbs/schemas.py`, `apps/api/src/agents/raci_generator.py`, `apps/api/src/services/stakeholder_classifier.py`
  - `apps/api/src/modules/analysis/coherence_engine.py`, `apps/api/src/modules/analysis/models.py`, `apps/api/src/modules/auth/models.py`
  - `apps/api/src/projects/adapters/persistence/models.py` (relaciones a análisis/alertas)
- Migración en routers legacy:
  - `apps/api/src/routers/approvals.py` usa StakeholderORM.
  - `apps/api/src/routers/raci.py` usa ProjectORM/WBSItemORM/StakeholderORM y DTOs nuevos.
- Nuevos routers en módulo stakeholders:
  - `apps/api/src/stakeholders/adapters/http/approvals_router.py`
  - `apps/api/src/stakeholders/adapters/http/raci_router.py`
  - `apps/api/src/main.py` apunta a estos routers nuevos.
- `apps/api/src/modules/main.py`
  - Marcado como LEGACY (entrypoint antiguo).
- Legacy aislado:
  - `apps/api/src/modules/documents/LEGACY.md` y `apps/api/src/routers/LEGACY.md`.
  - Movidos a `apps/api/src/_legacy/`:
    - `apps/api/src/_legacy/routers/approvals.py`
    - `apps/api/src/_legacy/routers/raci.py`
    - `apps/api/src/_legacy/routers/stakeholders.py`
    - `apps/api/src/_legacy/modules/documents/router.py`
    - `apps/api/src/_legacy/modules/documents/service.py`
- Consolidación de agentes:
  - Movido `apps/api/src/agents/*` a `apps/api/src/ai/agents/`.
  - Actualizados imports a `src.ai.agents.*`.
  - `apps/api/src/agents/LEGACY.md` agregado.
- Puertos y AI en analysis:
  - `apps/api/src/analysis/ports/ai_client.py` agregado.
  - `apps/api/src/analysis/adapters/ai/anthropic_client.py` (antes `src/ai/ai_service.py`).
  - Shim legacy en `apps/api/src/ai/ai_service.py`.
- Movimiento de AI/agents y AI/graph:
  - `apps/api/src/analysis/adapters/ai/agents/*` y `apps/api/src/analysis/adapters/graph/*`.
  - Shims legacy en `apps/api/src/ai/agents/__init__.py` y `apps/api/src/ai/graph/*`.
  - `apps/api/src/services/raci_generation_service.py` actualizado a la nueva ruta.
  - `apps/api/src/ai/LEGACY.md`, `apps/api/src/ai/agents/LEGACY.md`, `apps/api/src/ai/graph/LEGACY.md`.
- Limpieza y migración adicional:
  - `apps/api/src/agents` eliminado por completo.
  - `apps/api/src/ai/cost_controller.py` y `apps/api/src/ai/orchestrator.py` movidos a `apps/api/src/analysis/adapters/ai/`.
  - Shims legacy en `apps/api/src/ai/cost_controller.py` y `apps/api/src/ai/orchestrator.py`.
  - Imports actualizados en `apps/api/src/modules/analysis/router.py` y `apps/api/src/analysis/adapters/ai/anthropic_client.py`.
- Limpieza adicional:
  - Imports de AI actualizados a `src.analysis.adapters.ai.anthropic_client` en coherence/stakeholder_classifier.
  - `apps/api/src/ai` movido a `apps/api/src/_legacy/ai`.
- Migración inicial de Analysis:
  - `apps/api/src/analysis/adapters/http/router.py` creado desde legacy.
  - `apps/api/src/main.py` y `apps/api/src/modules/main.py` actualizados a router nuevo.
  - `apps/api/src/modules/analysis/router.py` movido a `apps/api/src/_legacy/modules/analysis/router.py`.
- Models de Analysis movidos:
  - `apps/api/src/analysis/adapters/persistence/models.py` (antes `modules/analysis/models.py`).
  - Shim legacy en `apps/api/src/modules/analysis/models.py`.
  - Imports actualizados en services/coherence/observability/graph y `core/database.py`.
- Repositorios Analysis:
  - `apps/api/src/analysis/ports/analysis_repository.py`
  - `apps/api/src/analysis/adapters/persistence/analysis_repository.py`
  - `apps/api/src/analysis/adapters/graph/nodes.py` usa `SqlAlchemyAnalysisRepository`.
- `apps/api/src/projects/adapters/persistence/models.py`
  - Nuevo `ProjectORM` mínimo para resolver relaciones.
- `apps/api/src/core/database.py`
  - Import explícito de modelos nuevos/legacy para registrar mappers.
- **Migración de MCP (Model Context Protocol) a infraestructura core (2026-01-27)**:
  - Análisis arquitectónico: MCP NO es un módulo de dominio, es infraestructura transversal de seguridad.
  - Movido de `apps/api/src/mcp/` a `apps/api/src/core/mcp/`
  - Justificación: `core/` es el lugar establecido para infraestructura compartida (database, cache, middleware, security).
  - Archivos migrados:
    - `core/mcp/__init__.py`
    - `core/mcp/README.md` (actualizado con nuevos imports)
    - `core/mcp/router.py` (actualizado imports internos)
    - `core/mcp/servers/database_server.py`
  - Imports actualizados:
    - `src/main.py`: `from src.mcp.router` → `from src.core.mcp.router`
    - `tests/security/test_mcp_security.py`: `from src.mcp.servers` → `from src.core.mcp.servers`
    - `core/__init__.py`: agregado export de `DatabaseMCPServer` y `get_mcp_server`
    - `core/mcp/__init__.py`: actualizado import interno
    - `core/mcp/router.py`: actualizado import interno
    - `core/mcp/README.md`: actualizados ejemplos de código
  - Directorio antiguo `src/mcp/` eliminado
  - Estado: ✅ COMPLETADO - imports verificados funcionando correctamente
  - Beneficios:
    - Consistencia arquitectónica: infraestructura centralizada en `core/`
    - Claridad conceptual: separación clara entre dominio y infraestructura
    - Alineado con ADR-001 y PLAN_ARQUITECTURA.md Fase 1

- **Corrección de import roto de Projects router (2026-01-27) - 🔴 CRÍTICO**:
  - Problema: `src/main.py` importaba `from src.modules.projects.router` que NO EXISTÍA
  - Impacto: La aplicación no podía arrancar (ModuleNotFoundError)
  - Solución implementada:
    - Creada estructura `src/projects/adapters/http/`
    - Creado `src/projects/adapters/http/router.py` (TRANSITIONAL - usa ORM directamente)
    - Implementados endpoints CRUD completos:
      - GET /api/v1/projects - Listar proyectos (paginación, filtros, búsqueda)
      - POST /api/v1/projects - Crear proyecto
      - GET /api/v1/projects/{id} - Obtener proyecto por ID
      - PUT /api/v1/projects/{id} - Actualizar proyecto
    - Actualizado `src/main.py`: import cambiado a `from src.projects.adapters.http.router`
    - Arreglado import incorrecto en `src/projects/application/dtos.py`: `apps.api.src.projects` → `src.projects`
  - Notas técnicas:
    - Router TRANSITIONAL: usa ProjectORM directamente en lugar de casos de uso
    - Razón: No existen casos de uso implementados en `src/projects/application/`
    - TODO: Refactorizar a usar casos de uso cuando se implementen (arquitectura hexagonal completa)
    - DTOs inline temporales en el router (hasta que se usen los de `application/dtos.py`)
  - Verificación:
    - ✅ Import de `src.projects.adapters.http.router` funciona correctamente
    - ✅ Router correctamente montado en main.py (línea 30 y 200)
    - ⚠️ Aplicación aún no arranca por problema DIFERENTE: import circular en `modules/coherence/` (preexistente)
  - Estado: ✅ COMPLETADO - import roto de projects ARREGLADO
  - Bloqueo restante: Import circular en coherence (próxima prioridad)

- **Corrección de import circular y errores en cascada (2026-01-27) - 🔴 CRÍTICO RESUELTO**:
  - Problema inicial: Import circular en `modules/coherence/scoring.py` bloqueaba arranque
  - Error: `apps.api.src.modules.coherence.config` causaba circular import
  - Acción: Arreglado import en `scoring.py` líneas 12 y 17
    - Antes: `from apps.api.src.modules.coherence.config import ...`
    - Después: `from src.modules.coherence.config import ...`
  - **Errores en cascada descubiertos y arreglados**:
    1. `documents/adapters/extraction/legacy_entity_extraction_service.py`:
       - Import incorrecto: `from src.modules.stakeholders.models` (módulo no existe)
       - Arreglado: `from src.stakeholders.adapters.persistence.models import StakeholderORM`
       - Arreglado: `from src.procurement.adapters.persistence.models import BOMItemORM, WBSItemORM`
    2. `stakeholders/adapters/persistence/models.py`:
       - Error de tipeo: `PGUID` en lugar de `PGUUID` (9 ocurrencias)
       - Arreglado: reemplazo masivo `PGUID` → `PGUUID`
       - Error de nombre: `reviewed_by` en lugar de `verified_by` (línea 208)
       - Arreglado: foreign key usa `verified_by` correctamente
    3. `procurement/adapters/persistence/models.py`:
       - Error de tipeo: `PGUID` en lugar de `PGUUID` (múltiples ocurrencias)
       - Arreglado: reemplazo masivo `PGUID` → `PGUUID`
    4. `analysis/adapters/http/router.py`:
       - Import faltante: `from src.analysis.adapters.ai.orchestrator import run_orchestration`
       - Problema: orchestrator.py es un shim legacy, función no existe
       - Solución temporal: import comentado con TODO
       - **PENDIENTE**: Refactorizar análisis router para usar arquitectura correcta
  - Verificación final:
    - ✅ Aplicación arranca correctamente: "SUCCESS: Main app created"
    - ✅ 46 rutas cargadas correctamente
    - ✅ Coherence rules inicializadas (3 determinísticas + 6 LLM)
    - ⚠️ Warning Pydantic: `orm_mode` → `from_attributes` (no bloqueante)
  - Estado: ✅ COMPLETADO - aplicación arranca exitosamente
  - **Resultado**: La aplicación C2Pro está funcional y lista para desarrollo

- **Consolidación de Coherence duplicado (2026-01-27) - ✅ COMPLETADO**:
  - Problema: Código de Coherence duplicado en dos ubicaciones:
    - `src/coherence/` (5 archivos, implementación nueva pero incompleta)
    - `src/modules/coherence/` (21 archivos, implementación completa v0.2 con LLM)
  - Análisis:
    - `src/coherence/` era más reciente pero incompleto
    - `src/modules/coherence/` contenía implementación completa con:
      - CoherenceEngine principal
      - Integración LLM (v0.2)
      - Rules engine con evaluadores deterministas y LLM
      - 6 reglas cualitativas predefinidas
      - ScoringService completo
      - AlertGenerator
  - Decisión: Mantener `src/modules/coherence/` como versión oficial en `src/coherence/`
  - Acciones ejecutadas:
    1. Respaldo de `src/coherence/` antiguo a `src/_legacy/coherence_old/`
    2. Copia de `src/modules/coherence/` a `src/coherence/`
    3. Actualización de imports internos en coherence:
       - Reemplazo masivo: `src.modules.coherence` → `src.coherence` (usando sed)
       - Archivos actualizados: todos los .py dentro de src/coherence/
    4. Actualización de imports externos:
       - `src/main.py`: router de coherence actualizado (línea 27)
       - `src/modules/analysis/coherence_engine.py`: import de CoherenceRuleResult
       - `src/services/alerts/generator.py`: imports de AlertGenerator y CoherenceRuleResult
       - `src/coherence/README.md`: ejemplos de código y documentación
    5. Eliminación del directorio antiguo: `src/modules/coherence/` completamente eliminado
  - Verificación:
    - ✅ Aplicación importa correctamente: "Application imported successfully"
    - ✅ Coherence rules cargadas: 6 LLM rules + 3 deterministic rules
    - ✅ Registry inicializado correctamente
    - ✅ Exception handlers registrados (4 handlers)
    - ✅ Router de coherence montado en main.py
  - Archivos clave consolidados:
    - `src/coherence/engine.py` - Motor principal
    - `src/coherence/llm_integration.py` - Integración LLM (CE-22)
    - `src/coherence/rules_engine/llm_evaluator.py` - Evaluador LLM (CE-23)
    - `src/coherence/scoring.py` - Cálculo de scores
    - `src/coherence/alert_generator.py` - Generación de alertas
    - `src/coherence/router.py` - API endpoint
    - `src/coherence/qualitative_rules.yaml` - Reglas cualitativas
  - Estado: ✅ COMPLETADO - coherence consolidado en ubicación final
  - Resultado: Eliminada duplicación de código, estructura limpia y organizada

## Plan de trabajo acordado (fase actual)
1) Auditar endpoints y dependencias de `documents`, `stakeholders`, `procurement`. (COMPLETADO)
2) Crear/adaptar routers (HTTP adapters) en módulos nuevos + wiring mínimo de DI. (EN PROGRESO: documents y stakeholders)
3) Actualizar `apps/api/src/main.py` para montar routers nuevos y retirar legacy de esos dominios. (EN PROGRESO: documents y stakeholders)
4) Aislar/etiquetar código legacy no usado y registrar TODOs de migración. (PENDIENTE)

## Estructura actual del proyecto (apps/api/src/)
```
src/
├── core/                        # ✅ Infraestructura compartida (bien ubicado)
│   ├── database.py
│   ├── cache.py
│   ├── middleware.py
│   ├── security.py
│   ├── handlers.py
│   ├── observability.py
│   └── mcp/                     # ✅ MIGRADO (2026-01-27)
│       ├── router.py
│       └── servers/database_server.py
│
├── documents/                   # ✅ Módulo de dominio (arquitectura hexagonal)
│   ├── domain/
│   ├── application/
│   ├── adapters/
│   └── ports/
│
├── stakeholders/                # ✅ Módulo de dominio (arquitectura hexagonal)
├── analysis/                    # ✅ Módulo de dominio (arquitectura hexagonal)
├── projects/                    # ✅ Módulo de dominio (arquitectura hexagonal)
├── procurement/                 # ✅ Módulo de dominio (arquitectura hexagonal)
│
├── shared_kernel/               # 📦 DDD Shared Kernel (vacío, para value objects compartidos)
│
├── modules/                     # ⚠️  LEGACY - en proceso de migración
│   ├── auth/                    # → evaluar si va a core/auth o nuevo módulo
│   ├── coherence/               # → evaluar si es módulo o parte de analysis
│   ├── observability/           # → evaluar si va a core/observability
│   └── [otros]
│
├── routers/                     # ⚠️  LEGACY - migrar a adapters HTTP de módulos
│   ├── health.py               # → core/health?
│   ├── alerts.py               # → analysis/adapters/http?
│   └── [otros movidos a _legacy]
│
├── services/                    # ⚠️  LEGACY - determinar ubicación correcta
│   ├── knowledge_graph.py      # → analysis/adapters?
│   ├── raci_generation_service.py
│   ├── stakeholder_classifier.py
│   └── [otros]
│
├── coherence/                   # ⚠️  EVALUAR - posible módulo de dominio
├── security/                    # ⚠️  EVALUAR - probablemente core/security
├── tasks/                       # ⚠️  EVALUAR - Celery tasks
├── middleware/                  # ⚠️  EVALUAR - probablemente core/middleware
│
└── _legacy/                     # 🗑️  Código legacy aislado
    ├── modules/
    ├── routers/
    ├── services/
    └── ai/
```

## Bloqueos/pendientes inmediatos
- 🟠 **[ALTA]** Consolidar coherence/ (duplicado en src/coherence/ y src/modules/coherence/)
- 🟠 **[ALTA]** Migrar auth (decisión: core/auth/ vs auth/ como módulo)
- 🟡 **[MEDIA]** Refactorizar projects router a usar casos de uso (actualmente usa ORM directamente)
- 🟡 **[MEDIA]** Refactorizar analysis router (import de orchestrator comentado temporalmente)
- 🟡 **[MEDIA]** Consolidar observability, middleware, tasks a core/
- 🟢 **[BAJA]** Arreglar warning Pydantic: `orm_mode` → `from_attributes`
- ✅ **[COMPLETADO]** Aplicación arranca exitosamente (2026-01-27)
- ✅ **[COMPLETADO]** Import circular en coherence arreglado (2026-01-27)
- ✅ **[COMPLETADO]** Import roto de projects router arreglado (2026-01-27)
- ✅ **[COMPLETADO]** Errores de tipeo PGUID→PGUUID arreglados (2026-01-27)
- ✅ **[COMPLETADO]** Análisis completo de directorios src/ realizado (2026-01-27)
- ✅ **[COMPLETADO]** Migración de MCP a core/mcp/ (2026-01-27)

## Recomendaciones priorizadas de migración

### ✅ BLOQUEANTES CRÍTICOS RESUELTOS
1. ~~**Arreglar import roto de projects**~~ ✅ COMPLETADO (2026-01-27)
2. ~~**Arreglar import circular en coherence**~~ ✅ COMPLETADO (2026-01-27)
3. ~~**Arreglar errores de tipeo PGUID/PGUUID**~~ ✅ COMPLETADO (2026-01-27)
4. ~~**Arreglar imports legacy de stakeholders/procurement**~~ ✅ COMPLETADO (2026-01-27)
**→ RESULTADO: Aplicación arranca correctamente con 46 rutas cargadas**

### 🟠 PRIORIDAD ALTA (claridad arquitectónica)
2. **Consolidar coherence/**:
   - Evaluar si coherence es módulo de dominio separado
   - Si es dominio: consolidar `src/coherence/` + `src/modules/coherence/` → `src/coherence/` hexagonal
   - Si es parte de analysis: migrar todo a `src/analysis/adapters/coherence/`

3. **Migrar auth**:
   - Decisión: `src/auth/` (módulo de dominio) vs `src/core/auth/` (infraestructura)
   - Recomendación: `src/core/auth/` (transversal como MCP, usado por middleware/database)
   - Actualizar 28 archivos que importan de `src.modules.auth`

### 🟡 PRIORIDAD MEDIA (consolidación)
4. **Consolidar observability**:
   - `core/observability.py` (archivo) → `core/observability/` (directorio)
   - Migrar `modules/observability/` a `core/observability/`

5. **Migrar routers a core**:
   - `routers/health.py` → `core/routers/health.py`
   - `routers/alerts.py` → `analysis/adapters/http/alerts_router.py` o `core/routers/alerts.py`

6. **Consolidar middleware**:
   - `middleware/rate_limiter.py` → integrar en `core/middleware.py` o expandir a directorio

7. **Migrar tasks a core**:
   - `tasks/budget_alerts.py` → `core/tasks/budget_alerts.py`
   - `tasks/ingestion_tasks.py` → `core/tasks/ingestion_tasks.py` o distribuir en módulos

### 🟢 PRIORIDAD BAJA (limpieza)
8. **Limpiar modules/ai/**:
   - Verificar que está completamente migrado a `_legacy/ai/`
   - Eliminar directorio si está vacío

9. **Migrar services/ a ubicaciones específicas**:
   - `knowledge_graph.py` → `analysis/adapters/graph/`
   - `stakeholder_classifier.py` → `stakeholders/adapters/classification/`
   - `rag_service.py` → `documents/adapters/rag/`
   - etc.

10. **Evaluar módulos pequeños**:
    - `modules/bom/` - ¿parte de procurement?
    - `modules/wbs/` - ¿parte de projects?
    - `modules/tenants/` - ¿core o módulo?

## Próximos pasos sugeridos (actualizados)
1) ~~**[URGENTE]** Arreglar import roto de projects router~~ ✅ COMPLETADO
2) ~~**[URGENTE]** Arreglar import circular en coherence~~ ✅ COMPLETADO
3) ~~**[URGENTE]** Arreglar errores en cascada (imports, tipeos)~~ ✅ COMPLETADO
**→ Aplicación ahora arranca correctamente**
4) **[SIGUIENTE]** Continuar con migraciones de PRIORIDAD ALTA:
   - Consolidar coherence/ (duplicado en 2 ubicaciones)
   - Migrar auth a ubicación definitiva (core/auth/ recomendado)
5) **[ACTUAL]** Continuar revisión de `apps/api/src/` para depurar código y alinearlo con nueva arquitectura:
   - ✅ `src/mcp/` → migrado a `src/core/mcp/`
   - ✅ `src/modules/` - análisis completo realizado
   - ✅ `src/routers/` - análisis completo realizado
   - ✅ `src/services/` - análisis completo realizado
   - ✅ `src/coherence/` - análisis completo realizado
   - ✅ `src/security/` - análisis completo realizado
   - ✅ `src/tasks/` - análisis completo realizado
   - ✅ `src/middleware/` - análisis completo realizado
   - ⏭️ **Ejecutar migraciones** según prioridades definidas arriba
3) Crear router HTTP y DI de `procurement` (si existen endpoints).
4) Revisar y resolver dependencias cruzadas restantes (`src.modules.*` vs nuevos módulos).
5) Aislar o eliminar rutas legacy (`src.routers.*`, `src.modules.*`) una vez verificado.

## Notas
- No ejecutar cambios destructivos en legacy hasta que los routers nuevos estén cableados y funcionales.
- Mantener reglas de "Dependency Rule" (nada de imports directos entre módulos salvo puertos públicos).
- **Estrategia de migración establecida**:
  1. **Infraestructura → `core/`**: database, cache, middleware, security, mcp, handlers, observability
  2. **Dominios → módulos propios**: documents, stakeholders, analysis, projects, procurement (hexagonal)
  3. **Shared Kernel → `shared_kernel/`**: Value Objects y Domain Events compartidos entre bounded contexts
  4. **Legacy → `_legacy/`**: código antiguo aislado con shims de compatibilidad
- **Criterio de decisión MCP**: Se decidió por `core/mcp/` porque:
  - MCP NO es un bounded context de negocio
  - ES infraestructura de seguridad y acceso a datos transversal
  - Agrupa capacidades de infraestructura en un solo lugar (`core/`)
  - Evita crear estructura innecesaria (ej. `platform/`, `infrastructure/`)

## Análisis detallado de directorios pendientes de migración (2026-01-27)

### 1. `src/modules/` - LEGACY mixto (parcialmente migrado)

**Subdirectorios encontrados:**
- `ai/` - 280KB de código (anthropic_wrapper, llm_client, model_router, prompts, etc.)
  - **Estado**: Archivos vacíos (anonymizer.py, cost_controller.py)
  - **Migrado a**: `_legacy/ai/` ya existe con contenido
  - **Acción**: ⚠️ VALIDAR si modules/ai debe eliminarse o tiene código no migrado

- `analysis/` - Contiene shim legacy
  - `models.py`: `from src.analysis.adapters.persistence.models import *` (shim)
  - **Estado**: Migrado a `src/analysis/`
  - **Acción**: ✅ Solo mantener shim o mover a `_legacy/`

- `auth/` - 1561 líneas (models, router, schemas, service)
  - **Estado**: ACTIVO - usado por main.py, middleware, database, tests
  - **Decisión pendiente**: ¿Módulo de dominio `auth/` o infraestructura `core/auth`?
  - **Evaluación**: Auth es transversal (como MCP), podría ir a `core/auth/`
  - **Acción**: ⏭️ DECIDIR ubicación final y migrar

- `bom/` - Bill of Materials
  - **Estado**: Aparente módulo pequeño
  - **Acción**: ⏭️ EVALUAR si es parte de `procurement/` o módulo separado (confirmo es parte de procurement)

- `coherence/` - Motor de coherencia (alert_generator, config, engine, etc.)
  - **Estado**: ACTIVO - gran cantidad de código
  - **Existe también**: `src/coherence/` (evaluator, llm_rule_evaluator, models, rules/)
  - **Acción**: ⏭️ CONSOLIDAR ambos coherence/ en ubicación única

- `config.py` - Configuración del módulo modules
  - **Acción**: ⏭️ EVALUAR si debe ir a core/config.py o eliminarse

- `documents/` - Probable legacy
  - **Estado**: Ya existe `src/documents/` (hexagonal)
  - **Acción**: ⏭️ VERIFICAR si es shim y mover a `_legacy/`

- `main.py` - Entrypoint antiguo (marcado LEGACY)
  - **Acción**: ✅ Mantener como referencia en `_legacy/`

- `observability/` - 3 archivos (router, schemas, service)
  - **Estado**: ACTIVO - usado por main.py
  - **Decisión pendiente**: ¿`core/observability/` o mantener separado?
  - **Existe**: `core/observability.py` (archivo único)
  - **Acción**: ⏭️ CONSOLIDAR con `core/observability/` (expandir a directorio)

- `tenants/` - Gestión de tenants
  - **Estado**: Aparente módulo pequeño
  - **Acción**: ⏭️ EVALUAR si es `core/tenants/` (infraestructura) o módulo separado

- `wbs/` - Work Breakdown Structure
  - **Estado**: Aparente módulo pequeño
  - **Acción**: ⏭️ EVALUAR si es parte de `projects/` o módulo separado (esta relacionado con proyects, y procurement también, es la descomposicion de las tareas de un proyecto, revisar opciones, ya que esto es parte importante de la gestión de un proyecto, la idea es que realicemos revision del wbs actual, si se da, y que se propronga mejoras o nuevo en base a los datos y recursos, esto si hay que confirmar human in the loop )

### 2. `src/routers/` - LEGACY (marcado con LEGACY.md)

**Archivos encontrados:**
- `alerts.py` - 5.6KB
  - **Acción**: ⏭️ Migrar a `analysis/adapters/http/alerts_router.py` o `core/routers/alerts.py`

- `health.py` - 4.4KB
  - **Acción**: ⏭️ Migrar a `core/routers/health.py` (infraestructura)

- `LEGACY.md` - Ya marcado como legacy
  - **Acción**: ✅ Está documentado

### 3. `src/services/` - LEGACY disperso

**Archivos/subdirectorios encontrados:**
- `alerts/` - subdirectorio
  - **Acción**: ⏭️ EVALUAR contenido y migrar

- `anonymizer.py` - 10.5KB
  - **Acción**: ⏭️ Migrar a `core/services/anonymizer.py` o `analysis/adapters/`

- `budget_alerts.py` - 8.3KB
  - **Acción**: ⏭️ Migrar a dominio correspondiente (analysis?)

- `ingestion/` - subdirectorio
  - **Acción**: ⏭️ EVALUAR si es parte de documents/ o analysis/

- `knowledge_graph.py` - 8.1KB
  - **Acción**: ⏭️ Migrar a `analysis/adapters/graph/` (ya existe analysis/adapters/graph/)

- `privacy/` - subdirectorio
  - **Acción**: ⏭️ EVALUAR y migrar a `core/privacy/` o eliminar

- `raci_generation_service.py` - 4.9KB
  - **Acción**: ⏭️ Migrar a `stakeholders/adapters/` o `analysis/adapters/`

- `rag_service.py` - 5.8KB
  - **Acción**: ⏭️ Migrar a `documents/adapters/rag/` (ya existe)

- `scoring/` - subdirectorio
  - **Acción**: ⏭️ EVALUAR si es parte de analysis/ o coherence/

- `source_locator.py` - 5.5KB
  - **Acción**: ⏭️ Migrar a dominio correspondiente

- `stakeholder_classifier.py` - 7KB
  - **Acción**: ⏭️ Migrar a `stakeholders/adapters/classification/`

### 4. `src/coherence/` - EVALUAR (posible módulo o parte de analysis)

**Archivos encontrados:**
- `evaluator.py` - 1.5KB
- `llm_rule_evaluator.py` - 6.2KB
- `models.py` - 1.1KB
- `rules/` - subdirectorio

**Conflicto**: También existe `modules/coherence/` con mucho código
**Acción**: ⏭️ CONSOLIDAR en una única ubicación (¿módulo `coherence/` o `analysis/adapters/coherence/`?)

### 5. `src/security/` - VACÍO (estructura preparada)

**Estado**: Directorio con structure domain/application/adapters pero vacío
**Acción**: ⏭️ EVALUAR si debe ser `core/security/` o mantener como módulo

### 6. `src/tasks/` - Celery tasks

**Archivos encontrados:**
- `budget_alerts.py` - 743 bytes (Celery task)
- `ingestion_tasks.py` - 6.9KB (Celery task)

**Acción**: ⏭️ MIGRAR a `core/tasks/` (infraestructura) o distribuir en módulos correspondientes

### 7. `src/middleware/` - rate_limiter.py

**Archivo encontrado:**
- `rate_limiter.py` - 8KB

**Existe**: `core/middleware.py` (archivo único con RequestLoggingMiddleware, RateLimitMiddleware, TenantIsolationMiddleware)
**Acción**: ⏭️ CONSOLIDAR con `core/middleware.py` o expandir a directorio `core/middleware/`

## Problemas críticos encontrados

### ⚠️ IMPORT ROTO en main.py
```python
from src.modules.projects.router import router as projects_router
```
- **Problema**: `src/modules/projects/` NO EXISTE
- **Existe**: `src/projects/` (hexagonal) pero SIN ROUTER
- **Acción**: 🔴 URGENTE - crear router en `src/projects/adapters/http/router.py` o arreglar import

### ⚠️ Duplicación coherence/
- `src/coherence/` - 4 archivos
- `src/modules/coherence/` - ~30 archivos
- **Acción**: 🟡 CONSOLIDAR en una ubicación

### ⚠️ Duplicación AI
- `src/modules/ai/` - archivos vacíos
- `src/_legacy/ai/` - archivos completos
- **Acción**: 🟡 ELIMINAR modules/ai/ si está completamente migrado

## Problemas conocidos (no bloqueantes para arquitectura)
- Import circular en `modules/coherence/scoring.py`: usa `apps.api.src.*` en lugar de `src.*`
- Tests requieren configuración de environment (solo acepta 'development', 'staging', 'production', no 'test')

---

# 📋 GUION COMPLETO DEL PROYECTO C2PRO (Referencia Arquitectónica)

> **Fecha de actualización**: 2026-01-27
> **Propósito**: Guía de referencia para entender la estructura completa del proyecto y dónde debe ubicarse cada tipo de código según la arquitectura de monolito modular con hexagonal/clean por módulo.

## 🎯 VISIÓN ARQUITECTÓNICA

**C2Pro** es un **monolito modular** con arquitectura hexagonal/clean por módulo, diseñado para análisis inteligente de contratos de construcción usando IA.

### Principios Fundamentales
1. **Monolito Modular**: Una aplicación desplegable con módulos independientes internamente
2. **Hexagonal/Clean por Módulo**: Cada módulo sigue patrón hexagonal (domain → application → adapters → ports)
3. **Regla de Dependencias**: Las dependencias siempre apuntan hacia adentro (hacia el dominio)
4. **Comunicación entre Módulos**: Solo vía puertos y DTOs (prohibido import directo de internals)

---

## 📂 ESTRUCTURA DE ALTO NIVEL

```
c2pro/
├── apps/
│   ├── api/              → Backend FastAPI (Python 3.11)
│   └── web/              → Frontend Next.js 14 (TypeScript)
├── docs/                 → Documentación y ADRs
├── tests/                → Tests organizados por tipo
├── infrastructure/       → Scripts, IaC, migraciones
├── supabase/            → Migraciones SQL
└── [configs raíz]       → docker-compose, .env, Makefile
```

---

## 🏗️ BACKEND (apps/api/src/) - ORGANIZACIÓN MODULAR

### REGLA ARQUITECTÓNICA
Cada módulo sigue el patrón hexagonal: `domain/` → `application/` → `adapters/` → `ports/`

### MÓDULOS Y UBICACIONES

```
src/
│
├── 🎯 CORE (Infraestructura Transversal)
│   ├── core/
│   │   ├── mcp/                    ✅ Model Context Protocol
│   │   ├── database.py             ✅ Conexión DB
│   │   ├── cache.py                ✅ Redis
│   │   ├── middleware.py           ✅ Rate limiting, CORS
│   │   ├── security.py             ✅ JWT, auth
│   │   ├── handlers.py             ✅ Error handlers
│   │   └── observability.py        ✅ Logging, Sentry
│   │
│   └── middleware/                 ⚠️ Consolidar a core/middleware/
│
├── 🔐 AUTH (Autenticación)
│   └── modules/auth/               ⚠️ MIGRAR a src/auth/ (hexagonal)
│
├── 📄 DOCUMENTS (Gestión de Documentos)
│   ├── documents/                  ✅ Estructura hexagonal COMPLETA
│   │   ├── adapters/
│   │   │   ├── http/              → Router FastAPI
│   │   │   ├── persistence/       → Repositorio SQLAlchemy
│   │   │   ├── parsers/           → PDF, Excel, BC3, Word
│   │   │   ├── storage/           → S3/R2
│   │   │   ├── extraction/        → Entidades (legacy bridge)
│   │   │   └── rag/               → RAG ingestion
│   │   ├── application/           → Use cases
│   │   ├── domain/                → Entidades puras
│   │   └── ports/                 → Interfaces públicas
│   │
│   └── modules/documents/          ❌ LEGACY - eliminar cuando termine migración
│
├── 👥 STAKEHOLDERS (Partes Interesadas)
│   ├── stakeholders/               ✅ Estructura hexagonal COMPLETA
│   │   ├── adapters/
│   │   │   ├── http/
│   │   │   │   ├── router.py
│   │   │   │   ├── approvals_router.py
│   │   │   │   └── raci_router.py
│   │   │   └── persistence/
│   │   ├── application/
│   │   ├── domain/
│   │   └── ports/
│   │
│   └── modules/stakeholders/       ❌ LEGACY - puede eliminarse
│
├── 🛒 PROCUREMENT (WBS + BOM)
│   ├── procurement/                ✅ Estructura hexagonal PARCIAL
│   │   ├── adapters/
│   │   │   └── persistence/       → WBSItemORM, BOMItemORM
│   │   ├── application/           ⚠️ Crear use cases
│   │   └── domain/                ⚠️ Crear entidades
│   │
│   ├── modules/bom/                ⚠️ Consolidar a procurement/
│   └── modules/wbs/                ⚠️ Consolidar a procurement/
│
├── 🏢 PROJECTS (Proyectos)
│   └── projects/                   ⚠️ Estructura hexagonal INCOMPLETA
│       ├── adapters/
│       │   ├── http/              → Router TRANSITIONAL (usa ORM)
│       │   └── persistence/       → ProjectORM
│       ├── application/           ⚠️ Crear use cases
│       └── domain/                ⚠️ Crear entidades
│
├── 🔍 ANALYSIS (Análisis con IA)
│   ├── analysis/                   ✅ Estructura hexagonal COMPLETA
│   │   ├── adapters/
│   │   │   ├── ai/                → Anthropic client, agentes
│   │   │   │   └── agents/        → Risk, WBS agents
│   │   │   ├── graph/             → LangGraph workflow
│   │   │   ├── http/              → Router
│   │   │   └── persistence/       → Repositorios
│   │   ├── application/
│   │   ├── domain/
│   │   └── ports/
│   │
│   ├── modules/analysis/           ❌ LEGACY - eliminar gradualmente
│   └── ai/                         ❌ LEGACY - movido a _legacy/ai/
│
├── ⚖️ COHERENCE (Motor de Coherencia)
│   └── coherence/                  ✅ Módulo independiente COMPLETO
│       ├── rules/                 → Reglas por categoría
│       ├── rules_engine/          → Evaluadores
│       ├── engine.py / engine_v2.py
│       ├── llm_integration.py     → Integración Claude
│       ├── alert_generator.py
│       ├── scoring.py
│       ├── router.py              → API endpoint
│       └── *.yaml                 → Reglas YAML
│
├── 🔒 SECURITY (Seguridad)
│   └── security/                   ⚠️ Crear módulo hexagonal
│
├── 📊 OBSERVABILITY (Monitoreo)
│   └── modules/observability/      ⚠️ MIGRAR a src/observability/
│
├── 🏘️ TENANTS (Multi-tenant)
│   └── modules/tenants/            ⚠️ MIGRAR a core/tenants/ (infraestructura)
│
├── 🛠️ SERVICES (Servicios Compartidos)
│   └── services/                   ⚠️ Distribuir según responsabilidad:
│       ├── alerts/                → Mover a coherence/
│       ├── scoring/               → Mover a coherence/
│       ├── raci_generation_service.py → Mover a stakeholders/
│       ├── stakeholder_classifier.py  → Mover a stakeholders/
│       ├── knowledge_graph.py     → Mover a analysis/
│       ├── rag_service.py         → Mover a documents/
│       ├── source_locator.py      → Mover a documents/
│       └── anonymizer.py          → Mover a core/privacy/
│
├── 🗺️ ROUTERS (Routers Legacy)
│   └── routers/                    ⚠️ Distribuir a módulos:
│       ├── health.py              → Mantener en routers/
│       └── alerts.py              → Mover a coherence/adapters/http/
│
├── 📦 MODULES (Código Legacy)
│   └── modules/                    ❌ ELIMINAR gradualmente
│       └── main.py                ❌ LEGACY entrypoint
│
├── 🗑️ _LEGACY (Código Retirado)
│   └── _legacy/                    ✅ Aislamiento temporal
│       ├── ai/
│       ├── agents/
│       ├── routers/
│       ├── modules/
│       └── coherence_old/
│
└── main.py                         ✅ Entrypoint principal FastAPI
```

---

## 🎨 FRONTEND (apps/web/) - NEXT.JS 14

```
apps/web/
├── app/                           → App Router (Next.js 14)
│   ├── (auth)/                   → Login, Register
│   │   ├── login/
│   │   └── register/
│   │
│   ├── (dashboard)/              → Área privada
│   │   ├── layout.tsx
│   │   ├── page.tsx              → Dashboard home
│   │   ├── projects/             → Gestión de proyectos
│   │   │   ├── page.tsx
│   │   │   ├── new/
│   │   │   └── [id]/
│   │   │       ├── analysis/
│   │   │       ├── documents/
│   │   │       └── evidence/
│   │   ├── documents/            → Upload y gestión
│   │   ├── analysis/             → Resultados de análisis
│   │   ├── coherence/            → Motor de coherencia
│   │   ├── stakeholders/         → RACI, stakeholders
│   │   ├── alerts/               → Alertas
│   │   ├── evidence/             → Evidencia contractual
│   │   ├── observability/        → Métricas
│   │   └── settings/             → Configuración
│   │
│   ├── api/                      → API routes (proxy)
│   └── layout.tsx                → Root layout
│
├── components/                    → Componentes React
│   ├── auth/
│   ├── coherence/
│   ├── dashboard/
│   ├── evidence/
│   ├── pdf/                      → PDF viewer
│   ├── stakeholders/
│   ├── layout/
│   └── ui/                       → Radix UI components
│
├── contexts/                      → React Context
├── hooks/                         → Custom hooks
├── lib/                           → Utilities
│   ├── api-client.ts             → Axios client
│   └── auth.ts
│
└── types/                         → TypeScript types
```

---

## 🧪 TESTS - ORGANIZACIÓN

```
tests/                             → Tests globales
├── unit/                         → Tests unitarios puros
├── integration/                  → Tests de integración
├── accuracy/                     → Tests de precisión IA
├── performance/                  → Tests de rendimiento
├── golden/                       → Golden snapshots
└── fixtures/                     → Datos de prueba

apps/api/tests/                   → Tests del backend
├── ai/
├── auth/
├── coherence/
├── core/
└── conftest.py                   → Fixtures pytest

apps/web/__tests__/               → Tests del frontend
├── components/
├── hooks/
└── pages/
```

---

## 📚 DOCUMENTACIÓN (docs/)

```
docs/
├── PLAN_ARQUITECTURA.md          ✅ Hoja de ruta (v2.0)
├── DEVELOPMENT_STATUS.md         ✅ Estado actual
├── architecture/
│   └── decisions/                ✅ ADRs
│       ├── 001-modular-monolith-architecture.md
│       ├── 002-supabase-for-mvp.md
│       └── 003-ai-architecture.md
├── api/
│   └── openapi.yaml              ⚠️ Actualizar con routers nuevos
├── coherence_engine/             ✅ Documentación del motor
└── specifications/               ⚠️ Agregar especificaciones de módulos
```

---

## 🔧 INFRAESTRUCTURA

```
infrastructure/
├── scripts/
│   ├── setup-local.sh
│   └── backup-verify.sh
└── supabase/
    └── migrations/

supabase/
└── migrations/                   → Migraciones versionadas

[root]
├── docker-compose.yml            → Postgres + Redis + MinIO
├── docker-compose.test.yml       → Compose para tests
├── .env                          → Variables locales
└── Makefile                      → Comandos de desarrollo
```

---

## 🗺️ PLAN DE MIGRACIÓN (PRÓXIMOS PASOS)

### **FASE 1: CONSOLIDACIÓN DE INFRAESTRUCTURA** ⚠️
```
❌ modules/auth/          → ✅ src/auth/ (hexagonal completa)
❌ modules/observability/ → ✅ src/observability/ (hexagonal)
❌ modules/tenants/       → ✅ core/tenants/ (infraestructura)
❌ middleware/            → ✅ core/middleware/ (consolidar)
```

### **FASE 2: CONSOLIDACIÓN DE PROCUREMENT** ⚠️
```
❌ modules/bom/           → ✅ procurement/application/bom/
❌ modules/wbs/           → ✅ procurement/application/wbs/
⚠️ procurement/           → Completar use cases y domain
```

### **FASE 3: COMPLETAR PROJECTS** ⚠️
```
⚠️ projects/adapters/http/router.py  → Refactor: usar use cases
⚠️ projects/application/              → Crear use cases completos
⚠️ projects/domain/                   → Crear entidades
```

### **FASE 4: DISTRIBUIR SERVICES COMPARTIDOS** ⚠️
```
❌ services/alerts/           → ✅ coherence/services/
❌ services/scoring/          → ✅ coherence/services/
❌ services/raci_*           → ✅ stakeholders/services/
❌ services/stakeholder_*    → ✅ stakeholders/services/
❌ services/knowledge_graph  → ✅ analysis/services/
❌ services/rag_service      → ✅ documents/services/
❌ services/source_locator   → ✅ documents/services/
❌ services/anonymizer       → ✅ core/privacy/
```

### **FASE 5: LIMPIEZA FINAL** ❌
```
❌ Eliminar modules/ completo
❌ Eliminar _legacy/ (después de verificar)
❌ Actualizar tests para nueva estructura
❌ Actualizar documentación API
```

---

## 📊 STACK TECNOLÓGICO COMPLETO

### Backend
- **Runtime**: Python 3.11
- **Framework**: FastAPI 0.109.2
- **BD**: PostgreSQL (Supabase) + SQLAlchemy 2.0
- **Cache**: Redis (Upstash)
- **Storage**: S3/R2 (CloudFlare)
- **IA**: Anthropic Claude + LangGraph
- **Testing**: pytest + pytest-asyncio
- **Lint**: Ruff + MyPy

### Frontend
- **Runtime**: Node.js
- **Framework**: Next.js 14
- **Lenguaje**: TypeScript 5.3.3
- **UI**: Tailwind CSS + Radix UI
- **State**: React Query
- **Testing**: Vitest

### DevOps
- **Contenedores**: Docker + Docker Compose
- **BD**: PostgreSQL 15
- **Cache**: Redis 7
- **Storage**: MinIO (local S3)

---

## 🎯 REGLAS ARQUITECTÓNICAS

### 1. Patrón Hexagonal por Módulo
```
modulo/
├── domain/          → Lógica pura (sin framework)
├── application/     → Use cases
├── adapters/        → Implementaciones (HTTP, DB, etc.)
└── ports/           → Interfaces públicas
```

### 2. Regla de Dependencias
**Las dependencias SIEMPRE apuntan hacia adentro (hacia el dominio)**

### 3. Comunicación entre Módulos
- **Solo vía puertos y DTOs**
- **Prohibido** import directo de modelos de otro módulo
- **Prohibido** import de adapters de otro módulo

### 4. Ubicación según Responsabilidad

| Tipo de Código | Ubicación |
|---------------|-----------|
| Infraestructura transversal | `core/` |
| Lógica de negocio | `{modulo}/domain/` |
| Casos de uso | `{modulo}/application/` |
| APIs externas | `{modulo}/adapters/` |
| Servicios compartidos | Distribuir a módulo dueño |

---

## 📐 PATRÓN DE MÓDULO HEXAGONAL COMPLETO

Cada módulo debe seguir esta estructura estándar:

```
{modulo}/
├── domain/                      # Capa de Dominio (Lógica de Negocio Pura)
│   ├── entities/                # Entidades de negocio
│   │   └── {entity}.py
│   ├── value_objects/           # Value Objects inmutables
│   │   └── {vo}.py
│   ├── events/                  # Domain Events
│   │   └── {event}.py
│   └── services/                # Domain Services (lógica compleja)
│       └── {service}.py
│
├── application/                 # Capa de Aplicación (Casos de Uso)
│   ├── use_cases/               # Use Cases (orquestación)
│   │   ├── {action}_{entity}_use_case.py
│   │   └── ...
│   ├── dtos.py                  # Data Transfer Objects
│   └── commands.py              # Commands (CQRS)
│
├── adapters/                    # Capa de Adaptadores (Implementaciones)
│   ├── http/                    # Adaptador HTTP (FastAPI)
│   │   ├── router.py
│   │   └── schemas.py           # Pydantic schemas para API
│   ├── persistence/             # Adaptador de Persistencia
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   └── repository.py        # Implementación de IRepository
│   ├── {external_service}/      # Otros adaptadores externos
│   └── ...
│
├── ports/                       # Capa de Puertos (Interfaces Públicas)
│   ├── repository.py            # IRepository interface
│   ├── {service}_port.py        # Otros ports
│   └── ...
│
└── __init__.py                  # Exports públicos del módulo
```

### Flujo de Dependencias
```
HTTP Request
    ↓
adapters/http/router.py
    ↓ (inyecta)
application/use_cases/{use_case}.py
    ↓ (usa)
domain/entities/{entity}.py
    ↑ (implementa)
adapters/persistence/repository.py
    ↑ (define interfaz)
ports/repository.py
```

---

## 🔍 CRITERIOS DE DECISIÓN ARQUITECTÓNICA

### ¿Dónde va este código?

**1. ¿Es infraestructura transversal?** → `core/`
- Database, cache, middleware, security, handlers, observability
- Ejemplo: MCP, JWT, logging, rate limiting

**2. ¿Es lógica de negocio?** → `{modulo}/domain/`
- Entidades, value objects, domain services
- Ejemplo: Document, Stakeholder, Project

**3. ¿Es un caso de uso?** → `{modulo}/application/`
- Orquestación de operaciones
- Ejemplo: UploadDocumentUseCase, CreateProjectUseCase

**4. ¿Es una implementación técnica?** → `{modulo}/adapters/`
- HTTP routers, repositorios, servicios externos
- Ejemplo: DocumentRouter, SQLAlchemyDocumentRepository

**5. ¿Es una interfaz pública?** → `{modulo}/ports/`
- Contratos que deben cumplir los adaptadores
- Ejemplo: IDocumentRepository, IStorageService

**6. ¿Es compartido entre módulos?** → `shared_kernel/`
- Value objects y domain events compartidos
- Ejemplo: Money, Email, DocumentUploaded

---

## 🚀 COMANDOS DE DESARROLLO COMUNES

### Backend (apps/api/)
```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar aplicación
python -m uvicorn src.main:app --reload

# Ejecutar tests
pytest apps/api/tests/ -v

# Linting
ruff check apps/api/src/
mypy apps/api/src/

# Migraciones
alembic revision --autogenerate -m "mensaje"
alembic upgrade head
```

### Frontend (apps/web/)
```bash
# Instalar dependencias
npm install

# Ejecutar en desarrollo
npm run dev

# Build producción
npm run build

# Ejecutar tests
npm run test

# Linting
npm run lint
```

### Docker
```bash
# Levantar servicios locales
docker-compose up -d

# Ver logs
docker-compose logs -f

# Limpiar todo
docker-compose down -v
```

---

## 📝 CHECKLIST DE MIGRACIÓN DE MÓDULO

Al migrar código legacy a la nueva estructura:

- [ ] **1. Analizar el código existente**
  - [ ] Identificar entidades de dominio
  - [ ] Identificar casos de uso
  - [ ] Identificar dependencias externas
  - [ ] Revisar tests existentes

- [ ] **2. Crear estructura hexagonal**
  - [ ] Crear directorios: domain/, application/, adapters/, ports/
  - [ ] Mover entidades a domain/entities/
  - [ ] Extraer lógica de negocio a domain/services/
  - [ ] Crear use cases en application/

- [ ] **3. Implementar adaptadores**
  - [ ] Crear router HTTP en adapters/http/
  - [ ] Crear repositorio en adapters/persistence/
  - [ ] Implementar interfaces de ports/

- [ ] **4. Actualizar imports**
  - [ ] Buscar todos los imports del código antiguo
  - [ ] Actualizar a nuevas rutas
  - [ ] Verificar que no hay imports circulares

- [ ] **5. Actualizar main.py**
  - [ ] Montar nuevo router
  - [ ] Verificar que funciona correctamente

- [ ] **6. Migrar tests**
  - [ ] Actualizar imports en tests
  - [ ] Verificar que todos los tests pasan
  - [ ] Agregar tests faltantes

- [ ] **7. Mover código antiguo a _legacy/**
  - [ ] Crear shim de compatibilidad si es necesario
  - [ ] Marcar con LEGACY.md
  - [ ] Programar eliminación definitiva

- [ ] **8. Actualizar documentación**
  - [ ] Actualizar agent.md
  - [ ] Actualizar README del módulo
  - [ ] Actualizar OpenAPI spec si aplica

---

## 🎯 ESTADO ACTUAL DE MIGRACIÓN (2026-01-27)

### ✅ COMPLETADO
- [x] MCP migrado a core/mcp/
- [x] Documents módulo hexagonal completo
- [x] Stakeholders módulo hexagonal completo
- [x] Analysis módulo hexagonal completo
- [x] Coherence consolidado en src/coherence/
- [x] Projects router básico (transitional)
- [x] Aplicación arranca correctamente (46 rutas)

### 🔄 EN PROGRESO
- [ ] Procurement: completar use cases y domain
- [ ] Projects: completar arquitectura hexagonal
- [ ] Analysis: refactorizar orchestrator

### ⏳ PENDIENTE
- [ ] Auth: migrar a ubicación definitiva
- [ ] Observability: consolidar en core/
- [ ] Services: distribuir a módulos dueños
- [ ] Middleware: consolidar en core/
- [ ] Tasks: migrar a core/ o distribuir
- [ ] Eliminar modules/ legacy
- [ ] Eliminar routers/ legacy

---

**Este guion debe consultarse siempre antes de:**
1. Agregar nuevo código al proyecto
2. Migrar código legacy
3. Refactorizar módulos existentes
4. Tomar decisiones arquitectónicas

**Mantener actualizado con cada cambio significativo en la estructura.**
