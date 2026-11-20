# I-01 — Plan de integración ejecutable (prioridad vigente)

**Decisión 20/11/2026:** detener en esta rama el inventario/análisis de documentos históricos. El corpus y el OCR quedan en Drive privado y no son dependencias del objetivo de integración. Este plan sustituye la priorización anterior WP0–WP5, que se conserva solo como referencia de opciones.

## Objetivo
Conectar software externo reutilizable a **puertos específicos de C2Pro**, sin duplicar su autoridad de evidencia, ProjectGraph ni HITL y sin introducir regresiones en el flujo actual. Cada hito entrega código reversible, prueba reproducible y evaluación funcional. No se habilita despliegue ni merge en esta autorización.

## Diagnóstico del código (base de rama 299aaf19…, reconciliar con UAT actual)
- `CompositeFileParser` delega la planificación a `ExcelFileParser.parse_schedule`; `upload_policy.py` permite `.xlsx` y `.bc3`, NO MPP/XER.
- `ExtractScheduleRevisionEvidenceUseCase` y `schedule_planned_finish` verifican SHA de fuente y sólo aceptan `.xlsx` como fuente de fechas; los source WBS codes no son autoridad de nodos.
- `ScheduleActivityEvidence` distingue fechas observadas de estados `NOT_ASSESSED`; planificador externo puede devolver fechas con hora/calendario desconocido. No inventar zona horaria ni baseline.
- Los pilotos de MPXJ 16.10 demostraron importación de MPP y XER; los informes previos NO significan que el adaptador ya estuviera integrado.

## Prioridades técnicas

### I-01 MPXJ → Schedule Candidate Adapter — P0 · EJECUTAR AQUÍ
**Implementación en rama aislada:** `apps/api/src/documents/adapters/parsers/mpxj_schedule_candidate_adapter.py` y tests unitarios independientes, sin `mcp` ni despliegues. MPXJ/JPype1 son dependencias opcionales, **lazy import**; aún no instalar en API productiva.
- API read-only: `source_bytes` inmutables + `expected_sha256` + scope `tenant_id/project_id/document_id/revision_id` + formato `mpp/xer`, con límite de tamaño y tareas.
- Resultado: `candidate schedule observations` con locator único derivado del ID nativo MPXJ, relaciones de precedencia, fechas *locales sin autoridad*, hitos y limitaciones. Ninguna fila puede adquirir `wbs_node_id` ni `trusted` por parsing.
- Pruebas: checksum incorrecto → abortar antes de parsear; tipo no permitido; duplicación de IDs; duraciones y relaciones legibles; ausencia de fechas; no efectos secundarios. Smoke integrado en entorno aislado real MPXJ sobre fixture sintético existente.
- **Gate I-01:** import real + tests PASS + QA de schema, con `NOT_ASSESSED` para autoridad contractual/fecha/WBS. **No se activa endpoint de subida, conversión a `ScheduleActivityEvidence` ni reemplazo de parser XLSX todavía**.
- **Conexión I-01b (posterior a QA):** adapter bridge contra la rama API funcional actual (verificar SHA de las rutas `DocumentRevision` y file parser), *feature flag off*, source immutable, mapeo sin mutar `ProjectGraph`.

### I-02 Docling → Structured Evidence Adapter — P1
Conservar PDFFileParser actual; desarrollar adaptador *opt-in* `DocumentParseAdapter` que devuelve `pages, tables, source location`, hash y coverage, sin llamar a N4/N12 ni convertir texto a hechos trusted. Probar sobre fixture digital y escaneado **sintéticos**; comparar con parser actual, registrar dónde se pierden tabla, página o span. **No crear un segundo almacén DocumentGraph**.

### I-03 Cross-domain evidence mapper — P1 (después de I-01/I-02)
Contratos canónicos `EvidenceRef/SourceRevision/ScheduleCandidate/CostCandidate/RequirementCandidate/RelationshipCandidate`, con `unresolved` explícito y multiplicidad. Consumir `schedule` y `document` desde adaptadores, enlazar únicamente IDs explícitos de fixtures sintéticos; prohibir matching automático por palabra. Tests de versión, mismatch y zero trusted promotions.

### I-04 MCP/API — P2
Sólo tras una ruta I-01/I-03 funcional: exposición read-only de evidence bundles/coverage/discrepancies en API/MCP, con auth tenant, rate limits y output `candidate vs trusted`. No delegar autoridad al cliente LLM.

## Fronteras y exclusiones
- No investigación de nuevos corpus de usuario, clasificación de Drive ni OCR histórico en esta línea.
- No introducir ERPNext/OpenContracts/CLM/LangExtract sin un problema concreto y una mejora medible sobre el stack.
- No tocar UAT N4-only, HITL, Coherence Score, MASTER, servicios ni releases. No cambiar `upload_policy`, schemas HTTP, migraciones o depósitos de datos productivos mientras no exista QA y decisión de integración.
- El repo es **público**; código y fixtures sólo sintéticos. Conservar repositorio de trabajo sin nombres, PO, OCR y hashes privados.

## Criterio de avance
Un hito sólo es **IMPLEMENTADO** si hay código invocable y pruebas efectivamente ejecutadas. El documento por sí solo se marca como **DISEÑADO**. Probar en runtime local es distinto de integración end-to-end en C2Pro y distinto de despliegue. Mantener las tres etiquetas.

## Evidencias requeridas en la entrega de I-01
Commit de rama + ruta del adaptador + tests ejecutados con resultado y entorno + evidencia de hash/IDs/predecesoras/cobertura + riesgos explícitos + siguiente patch mínimo sobre el código actual.
