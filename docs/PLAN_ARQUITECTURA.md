# Plan de Saneamiento y Evolucion Arquitectonica de C2Pro (v2.0)

## Filosofia

Este plan representa la hoja de ruta para transformar C2Pro en un monolito modular con arquitectura hexagonal por modulo. Se prioriza claridad, estabilidad y evolucion controlada.

## Roadmap por fases

- Fase 1 (Fundacion): puntos 1-4. No se inicia trabajo nuevo sin fundacion estable.
- Fase 2 (Capacidades criticas): puntos 5-8. IA, observabilidad y negocio con base solida.
- Fase 3 (Escalado y madurez): puntos 9-11. Contratos, pruebas y documentacion.

---

## Estado actual (resumen ejecutivo)

- Estructura modular activa en `apps/api/src/*`.
- Infraestructura transversal consolidada en `apps/api/src/core/*`.
- Routers HTTP principales delegan a application/use cases.
- Regla de dependencia cross-modulo aplicada en application/ports y adapters HTTP.

---

## Checklist de Consolidacion Cross-Modulo (Fase 1)

- [x] Eliminar imports ORM cruzados en adapters HTTP.
- [x] Crear puertos de consulta minimos entre modulos (existencia/lectura) y exponerlos en application.
- [x] Migrar servicios application que usan ORM de otros modulos a puertos/DTOs.
- [x] Aislar adapters transicionales con TODO y plan de eliminacion.
- [x] Reducir relaciones ORM cross-modulo a FKs simples o capa de integracion.
- [x] Documentar contratos publicos por modulo (exports + puertos permitidos).
- [x] Verificar cumplimiento con rg (sin `adapters.persistence.models` en application/adapters HTTP).

---

## Plan de ejecucion detallado (Fase 1 - Cross-Modulo)

**Objetivo:** cerrar la regla de dependencia y dejar contratos publicos claros por modulo.

### Secuencia recomendada (orden estricto)

1) Definir contratos publicos por modulo (bloqueante).
2) Eliminar dependencias ORM en ports/application.
3) Crear puertos de consulta minimos entre modulos y adaptar use cases.
4) Aislar adapters transicionales con TODO y plan de eliminacion.
5) Reducir relaciones ORM cross-modulo a FKs simples.
6) Verificacion final con `rg` + actualizacion de docs.

### Tareas con owners y esfuerzo estimado

#### T1. Contratos publicos por modulo

- Owner: Arquitecto + Tech Lead  
- Alcance: definir `__init__.py` export publicos y lista de puertos permitidos por modulo.  
- Salida: tabla en docs + convenciones de import.  
- Documento fuente: `docs/specifications/CONTRATOS_PUBLICOS.md`  
- Estado: DONE (2026-01-29)  
- Esfuerzo: S (0.5-1d)

#### T2. Enums/DTOs de Analysis fuera de ORM

- Owner: Backend Lead (Analysis)  
- Alcance: mover `AlertStatus/AlertSeverity` a domain/DTO; ajustar HTTP/adapters.  
- Dependencias: T1  
- Estado: DONE (2026-01-29)  
- Esfuerzo: S (0.5d)

#### T3. Ports/Application sin ORM en Analysis

- Owner: Backend Lead (Analysis)  
- Alcance: refactor `analysis/ports/*` y `analysis/application/*` para usar DTOs y repositorios propios.  
- Dependencias: T1, T2  
- Estado: DONE (2026-01-29)  
- Esfuerzo: M (1-2d)

#### T4. Ports minimos entre modulos (consulta/exists)

- Owner: Backend Lead (Documents/Procurement/Projects/Stakeholders)  
- Alcance: puertos de lectura/exists + adaptadores; uso desde application.  
- Dependencias: T1  
- Estado: DONE (2026-01-29)  
- Esfuerzo: M (1-2d)

#### T5. Refactor services application con ORM cruzado

- Owner: Backend Lead  
- Alcance: `documents/application/services/source_locator.py`, `stakeholders/application/services/raci_generation_service.py`.  
- Dependencias: T4  
- Estado: DONE (2026-01-29)  
- Esfuerzo: M (1-2d)

#### T6. Aislar adapters transicionales

- Owner: Tech Lead  
- Alcance: encapsular `legacy_entity_extraction_service` y `legacy_rag_ingestion_service` con TODO, contrato y fecha objetivo.  
- Dependencias: T1  
- Estado: DONE (2026-01-29)  
- Esfuerzo: S (0.5-1d)

#### T7. Reducir relaciones ORM cross-modulo

- Owner: Arquitecto + Backend Lead  
- Alcance: eliminar relaciones ORM directas y dejar FKs simples (o capa de integracion).  
- Dependencias: T1, T3, T4  
- Estado: DONE (2026-01-29)
- Esfuerzo: L (2-3d)

#### T8. Verificacion final y cierre

- Owner: Tech Lead + QA  
- Alcance: `rg` sin violaciones + actualizar docs y checklist.  
- Dependencias: T1-T7  
- Estado: DONE (2026-01-29)
- Esfuerzo: S (0.5d)
- Dependencias: T1-T7  
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
## 1. Fundacion: Monolito Modular y DDD

- Responsable: Arquitecto Principal + Tech Lead
- Logros esperados: estructura unica, sin duplicidad, comunicacion via puertos.
- Tareas:
  - 1.1 ADR monolito modular. [DONE]
  - 1.2 Definir bounded contexts y estructura de directorios. [DONE]
  - 1.3 Regla de comunicacion inter-modulo (solo puertos). [DONE]
  - 1.4 Consolidar codigo duplicado. [DONE]
  - 1.5 Separar dominio vs infraestructura (core vs modulos). [DONE]
  - 1.6 Eliminar ambiguedad de ubicacion. [DONE]
  - 1.7 Definir contratos publicos por modulo. [DONE]

## 2. Patrones de Diseno: Arquitectura Limpia/Hexagonal

- Responsable: Backend Lead + Arquitecto
- Tareas:
  - 2.1 Dominio puro (entidades, value objects, domain services). [DONE]
  - 2.2 Puertos (interfaces) por modulo. [DONE] (2026-01-30)
  - 2.3 Adaptadores (HTTP, persistence, externos). [DONE]
  - 2.4 Routers delgados delegan a use cases. [DONE]
  - 2.5 Core simple salvo reglas de negocio complejas. [DONE]

## 3. Seguridad Multitenant

- Responsable: Security Lead + Backend Lead
- Tareas:
  - 3.1 Middleware obligatorio de tenant. [DONE] (2026-01-30)
  - 3.2 Repositorios con filtro tenant obligatorio. [PENDIENTE]
  - 3.3 RLS en DB alineado a logica app. [PENDIENTE]

## 4. Orquestacion y Agentes IA

- Responsable: AI Lead + Arquitecto Principal
- Tareas:
  - 4.1 LangGraph como orquestacion. [DONE]
  - 4.2 Interfaces de tool/agente. [EN PROGRESO]
  - 4.3 Nodos de validacion deterministas. [PENDIENTE]
  - 4.4 Versionado centralizado de prompts. [EN PROGRESO]

## 5. Control de Costos y Resiliencia IA

- Responsable: Platform Lead + AI Lead
- Tareas:
  - 5.1 Trazabilidad de costos. [PENDIENTE]
  - 5.2 Budget circuit breaker. [PENDIENTE]
  - 5.3 Retry/circuit breaker por tool. [PENDIENTE]

## 6. Componentes de Dominio Clave

- Responsable: Product + Backend Lead
- Tareas:
  - 6.1 Coherence en domain service. [EN PROGRESO]
  - 6.2 Abstraer Graph RAG con `IGraphRepository`. [PENDIENTE]

## 7. Contrato API y Front-Back

- Responsable: Frontend Lead + API Lead + DevOps
- Tareas:
  - 7.1 Generacion automatica OpenAPI. [PENDIENTE]
  - 7.2 Tests de contrato en CI. [PENDIENTE]

## 8. Estrategia de Pruebas

- Responsable: QA Lead + Tech Leads
- Tareas:
  - 8.1 Unit tests dominio y use cases. [PENDIENTE]
  - 8.2 Integracion adaptadores. [PENDIENTE]
  - 8.3 Contratos APIs externas. [PENDIENTE]
  - 8.4 E2E flujos criticos. [PENDIENTE]

## 9. Observabilidad

- Responsable: Platform Lead
- Tareas:
  - 9.1 trace_id end-to-end. [PENDIENTE]
  - 9.2 logging JSON. [EN PROGRESO]
  - 9.3 visualizacion de grafos IA. [PENDIENTE]

## 10. Documentacion Viva

- Responsable: Arquitecto Principal + Tech Leads
- Tareas:
  - 10.1 Mantener ADRs. [EN PROGRESO]
  - 10.2 Diagramas C4. [PENDIENTE]

## 11. Roadmap de Despliegue y Riesgos

- Responsable: Arquitecto Principal + Product
- Tareas:
  - 11.1 Mapear fases a hitos de negocio. [PENDIENTE]
  - 11.2 Identificar riesgos por fase y mitigacion. [PENDIENTE]
