# AGENTS

## Principios operativos
- No implementar cambios sin instruccion explicita.
- Leer archivos relevantes antes de opinar o modificar.
- Evitar sobre-ingenieria; soluciones simples y enfocadas.
- Si el objetivo es ambiguo: investigar y recomendar, no ejecutar.


## Referencias clave
- `docs/PLAN_ARQUITECTURA.md`
- `docs/ROADMAP_v2.4.0.md` (revisar vigencia)
- `docs/DEVELOPMENT_STATUS.md`
- `docs/specifications/especificacion_tecnica.md`
- `docs/specifications/CONTRATOS_PUBLICOS.md`
- `context/README.md` (indice de contexto)

## Estructura del repo (resumen)
- `apps/`: productos ejecutables (API FastAPI / web Next.js).
- `context/`: indice de contexto de arquitectura/estado.
- `infrastructure/`: infraestructura y operaciones.
- `supabase/`: workspace Supabase CLI.
- `docs/`: documentacion viva (estado, ADRs, runbooks).
- `tests/`: suites globales.
- `evidence/`: evidencia/artefactos.
- `backups/`: backups locales/manuales.
- `apps/api/src/core/ai/prompts/`: prompts versionados.
- `apps/api/storage/`: storage local estandarizado.

---
## Inventario de estructura (actualizar con cambios)
### Raiz del repositorio
- `.git/`: metadata git.
- `apps/`: productos ejecutables (API, web).
- `backups/`: backups locales/manuales.
- `context/`: indice de contexto de arquitectura/estado.
- `docs/`: documentacion y planes.
- `evidence/`: evidencia/artefactos.
- `infrastructure/`: scripts y operaciones.
- `logs/`: logs locales.
- `node_modules/`: dependencias JS (generado).
- `Skills/`: recursos locales (no productivo).
- `supabase/`: workspace Supabase CLI.
- `tests/`: tests globales.
- `vision-matched-repo/`: draft frontend (mantener).
- `zzz- capturas/`: capturas y evidencia visual.
- `.env.example`: plantilla de variables.
- `.env.staging`: variables staging (sensible).
- `.gitignore`: reglas de git.
- `.python-version`: version Python.
- `agents.md`: guia operativa y estado.
- `calibration_dataset.example.json`: dataset ejemplo.
- `codex resumen ultimo trabajo.txt`: notas internas.
- `Critical arquitecture.md`: notas arquitectura (legacy).
- `diseño arquitectura.md`: notas arquitectura (legacy).
- `docker-compose.test.yml`: compose para tests.
- `docker-compose.yml`: compose principal.
- `FRONTEND_TESTING_PLAN.md`: plan de pruebas frontend.
- `Makefile`: comandos de automatizacion.
- `package-lock.json`: lock npm.
- `package.json`: raiz JS (scripts/tooling).
- `QUICK_START.md`: guia de inicio rapido.
- `README.md`: overview del repo.
- `SECRETS.md`: guia de secretos (no incluir valores).
- `test.db`: sqlite local (temporal).

### apps/
- `apps/.claude/`: config local (no productivo).
- `apps/.venv/`: entorno virtual (generado).
- `apps/api/`: backend FastAPI.
  - `apps/api/alembic/`: migraciones DB.
  - `apps/api/examples/`: ejemplos.
  - `apps/api/htmlcov/`: cobertura (generado).
  - `apps/api/scripts/`: scripts locales del backend.
  - `apps/api/src/`: codigo productivo (API).
    - `apps/api/src/main.py`: entrypoint FastAPI.
    - `apps/api/src/config.py`: configuracion principal.
    - `apps/api/src/core/`: infraestructura transversal.
    - `apps/api/src/documents/`: modulo documents.
    - `apps/api/src/stakeholders/`: modulo stakeholders.
    - `apps/api/src/analysis/`: modulo analysis (IA).
    - `apps/api/src/projects/`: modulo projects.
    - `apps/api/src/procurement/`: modulo procurement (WBS/BOM).
    - `apps/api/src/coherence/`: motor coherence.
    - `apps/api/src/shared_kernel/`: shared kernel (VOs/eventos).
  - `apps/api/tests/`: tests backend.
  - `apps/api/storage/`: storage local estandarizado.
  - `apps/api/.env`: variables locales (sensible).
  - `apps/api/.env.test`: variables tests (sensible).
  - `apps/api/alembic.ini`: config alembic.
  - `apps/api/Dockerfile`: build backend.
  - `apps/api/pyproject.toml`: config tooling python.
  - `apps/api/requirements*.txt`: deps backend.
- `apps/web/`: frontend Next.js.
  - `apps/web/app/`: app router.
  - `apps/web/components/`: componentes UI.
  - `apps/web/contexts/`, `apps/web/hooks/`, `apps/web/lib/`, `apps/web/types/`.
  - `apps/web/scripts/`: scripts frontend.
  - `apps/web/__tests__/`: tests frontend.
  - `apps/web/.next/`: build (generado).
  - `apps/web/node_modules/`: deps (generado).
  - `apps/web/README_SETUP.md`: setup frontend.
  - `apps/web/next.config.js`, `tailwind.config.ts`, `tsconfig.json`: config.
- `apps/web-lovable/`: draft frontend (mantener).
- `apps/pytest_output.txt`: salida tests (temporal).

### context/
- `context/README.md`: indice de contexto.
- `context/experimental/mi-gemini/`: experimento Node/Google GenAI.

### infrastructure/
- `infrastructure/scripts/`: scripts operativos (migraciones, setup, verificaciones).
- `infrastructure/supabase/`: soporte adicional supabase (si aplica).

### docs/
- `docs/PLAN_ARQUITECTURA.md`: plan arquitectonico (fuente principal).
- `docs/ROADMAP_v2.4.0.md`: roadmap actual (revisar vigencia).
- `docs/DEVELOPMENT_STATUS.md`: estado global.
- `docs/specifications/especificacion_tecnica.md`: especificacion tecnica.
- `docs/architecture/`: ADRs y decisiones.
- `docs/runbooks/`: runbooks operativos.
- `docs/archive/`: historico (roadmaps, sprints, tasks).
- `docs/coherence_engine/`: documentacion coherence.

### supabase/
- `supabase/migrations/`: migraciones CLI.

### tests/
- `tests/unit/`, `tests/integration/`, `tests/performance/`, `tests/fixtures/`: suites globales.

### Nota sobre generados
- Directorios como `node_modules/`, `.venv/`, `.next/`, `__pycache__/`, `htmlcov/` son generados y no se documentan en detalle.

---
## Estado actual (alto nivel)
- Arquitectura objetivo: monolito modular con arquitectura hexagonal por modulo.
- `apps/api/src/modules` y `apps/api/src/routers` eliminados.
- Infraestructura transversal consolidada en `apps/api/src/core`.
- Routers HTTP principales delegan a application/use cases.

---
## Checklist Cross-Modulo Fase 1 (estado real)
- [x] Eliminar imports ORM cruzados en adapters HTTP.
- [x] Crear puertos de consulta minimos entre modulos (existencia/lectura) desde application.
- [x] Migrar servicios application que usan ORM de otros modulos a puertos/DTOs.
- [x] Aislar adapters transicionales con TODO y plan de eliminacion.
- [x] Reducir relaciones ORM cross-modulo (FKs simples o capa de integracion).
- [x] Documentar contratos publicos por modulo (exports + puertos permitidos).
- [x] Verificar cumplimiento con rg (sin `adapters.persistence.models` en application/adapters HTTP).

---
## Estado del plan (resumen ejecutivo)
**Fase 1 - Fundacion**
- DONE: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7

**Fase 2 - Arquitectura hexagonal**
- DONE: 2.3, 2.4, 2.5
- EN PROGRESO: 2.1, 2.2

**Fase 3 - Seguridad multitenant**
- EN REVISION: 3.1
- PENDIENTE: 3.2, 3.3

**Fase 4 - Orquestacion IA**
- DONE: 4.1
- EN PROGRESO: 4.2, 4.4
- PENDIENTE: 4.3

**Fase 5 - Costos y resiliencia IA**
- PENDIENTE: 5.1, 5.2, 5.3

**Fase 6 - Componentes de dominio**
- EN PROGRESO: 6.1
- PENDIENTE: 6.2

**Fase 7 - Contrato API**
- PENDIENTE: 7.1, 7.2

**Fase 8 - Pruebas**
- PENDIENTE: 8.1, 8.2, 8.3, 8.4

**Fase 9 - Observabilidad**
- EN PROGRESO: 9.2
- PENDIENTE: 9.1, 9.3

**Fase 10 - Documentacion viva**
- EN PROGRESO: 10.1
- PENDIENTE: 10.2

**Fase 11 - Roadmap y riesgos**
- PENDIENTE: 11.1, 11.2

---
## Hallazgos del barrido (2026-01-29)
### Routers HTTP
- Sin ORM cross-modulo en adapters HTTP.
- Enums de Analysis movidos a domain/DTOs (sin ORM en HTTP).

### Violaciones actuales (application/ports)
- Sin dependencias ORM en application/ports (verificacion `rg`).

### Adapters transicionales a aislar
- `apps/api/src/documents/adapters/extraction/legacy_entity_extraction_service.py`
- `apps/api/src/documents/adapters/rag/legacy_rag_ingestion_service.py`
  - TODO(arch): eliminar al cerrar Fase 1 (ver docstrings de cada adapter)

---
## Tareas pendientes (priorizadas)
### P0 - Regla de dependencia
- P0 completado (Fase 1 Cross-Modulo cerrada).

---
## Plan de ejecucion detallado (Fase 1 - Cross-Modulo)
**Objetivo:** cerrar completamente la regla de dependencia y dejar contratos publicos claros por modulo.

### Secuencia recomendada (orden estricto)
1) Definir contratos publicos por modulo (bloqueante).
2) Eliminar dependencias ORM en ports/application.
3) Crear puertos de consulta minimos entre modulos y adaptar use cases.
4) Aislar adapters transicionales con TODO y plan de eliminacion.
5) Reducir relaciones ORM cross-modulo a FKs simples.
6) Verificacion final con `rg` + actualizacion de docs.

### Tareas con owners y esfuerzo estimado

**T1. Contratos publicos por modulo**

- Owner: Arquitecto + Tech Lead
- Alcance: definir `__init__.py` export publicos y lista de puertos permitidos por modulo.
- Salida: tabla en docs + convenciones de import.
- Esfuerzo: S (0.5-1d)
- Estado: DONE (2026-01-29)

**T2. Enums/DTOs de Analysis fuera de ORM**


- Owner: Backend Lead (Analysis)
- Alcance: mover `AlertStatus/AlertSeverity` a domain/DTO; ajustar HTTP/adapters.
- Dependencias: T1
- Estado: DONE (2026-01-29)
- Esfuerzo: S (0.5d)

**T3. Ports/Application sin ORM en Analysis**
- Owner: Backend Lead (Analysis)
- Alcance: refactor `analysis/ports/*` y `analysis/application/*` para usar DTOs y repositorios propios.
- Dependencias: T1, T2
- Estado: DONE (2026-01-29)
- Esfuerzo: M (1-2d)

**T4. Ports minimos entre modulos (consulta/exists)**
- Owner: Backend Lead (Documents/Procurement/Projects/Stakeholders)
- Alcance: puertos de lectura/exists + adaptadores; uso desde application.
- Dependencias: T1
- Estado: DONE (2026-01-29)
- Esfuerzo: M (1-2d)

**T5. Refactor services application con ORM cruzado**
- Owner: Backend Lead
- Alcance: `documents/application/services/source_locator.py`, `stakeholders/application/services/raci_generation_service.py`.
- Dependencias: T4
- Estado: DONE (2026-01-29)
- Esfuerzo: M (1-2d)

**T6. Aislar adapters transicionales**
- Owner: Tech Lead
- Alcance: encapsular `legacy_entity_extraction_service` y `legacy_rag_ingestion_service` con TODO, contrato y fecha objetivo.
- Dependencias: T1
- Estado: DONE (2026-01-29)
- Esfuerzo: S (0.5-1d)

**T7. Reducir relaciones ORM cross-modulo**
- Owner: Arquitecto + Backend Lead
- Alcance: eliminar relaciones ORM directas y dejar FKs simples (o capa de integracion).
- Dependencias: T1, T3, T4
- Estado: DONE (2026-01-29)
- Esfuerzo: L (2-3d)

**T8. Verificacion final y cierre**
- Owner: Tech Lead + QA
- Alcance: `rg` sin violaciones + actualizar docs y checklist.
- Dependencias: T1-T7
- Estado: DONE (2026-01-29)
- Esfuerzo: S (0.5d)

---
## Definition of Done (DoD) + Criterios de aceptacion
### DoD global (Fase 1 Cross-Modulo)
- `rg` sin imports `adapters.persistence.models` en `application/` ni `adapters/http/`.
- Todos los puertos son interfaces puras (sin ORM ni adapters).
- Routers HTTP solo orquestan y delegan a application/use cases.
- Contratos publicos por modulo documentados y consistentes con `__init__.py`.
- Adapters transicionales aislados con TODO + fecha objetivo.
- Docs actualizadas (`agents.md`, `docs/PLAN_ARQUITECTURA.md`).

### Criterios de aceptacion por tarea
**T1. Contratos publicos por modulo**
- Existe tabla de contratos por modulo en docs.
- `__init__.py` exporta solo APIs publicas declaradas.
- No hay imports externos hacia internos no publicos.

**T2. Enums/DTOs de Analysis fuera de ORM**
- `AlertStatus/AlertSeverity` viven en domain/DTOs (no en ORM).
- `analysis/adapters/http/alerts_router.py` no importa ORM.
- Tests/imports existentes actualizados.

**T3. Ports/Application sin ORM en Analysis**
- `analysis/ports/*` sin dependencias ORM.
- `analysis/application/*` usa DTOs/ports, no ORM.
- Compila y arranca sin errores de import.

**T4. Ports minimos entre modulos**
- Existe puerto por consulta/exists en cada modulo requerido.
- Application usa esos puertos para lecturas cruzadas.
- No hay imports de adapters de otros modulos.

**T5. Refactor services application con ORM cruzado**
- `source_locator.py` y `raci_generation_service.py` sin ORM cross-modulo.
- Uso de DTOs o puertos minimos.
- Tests/flows funcionales.

**T6. Aislar adapters transicionales**
- TODOs explicitos + plan de eliminacion.
- Contrato documentado (inputs/outputs) y owner.
- Ubicacion marcada como transicional en docs.

**T7. Reducir relaciones ORM cross-modulo**
- Relaciones directas ORM removidas o encapsuladas.
- FKs simples o capa de integracion definida.
- Migraciones documentadas si aplica.

**T8. Verificacion final y cierre**
- `rg` sin violaciones.
- Checklist Fase 1 actualizado a estado final.
- Resumen ejecutivo en `agents.md`.

---
## Comandos utiles
- Barrido cross-modulo:
  - `rg -n "adapters\\.persistence\\.models" apps\\api\\src`
  - `rg -n -g "**/adapters/http/*.py" "adapters\\.persistence\\.models" apps\\api\\src`

---
## Politicas
- Adapters HTTP: solo orquestacion, sin ORM directo.
- Application: usa puertos y DTOs; nunca ORM de otros modulos.
- Ports: interfaces puras, sin dependencias de ORM.
