# Revisión técnica independiente en paralelo — 2026-11-20

**Estado:** revisión documental propia, sin ejecución de software, benchmark, despliegue ni gasto de inferencia. **No es resultado del Planner.**  
**Rama de estudio:** `research/c2pro-integration-open-source-20261120` (base de creación 299aaf19...).  
**Flujo funcional observado independiente:** PR #1276, HEAD `916808c5212e3dbc652407f35f3a17557623c06c`, base `799ce5315c01cdf6ec83f5716a02a509a6be1785`; draft abierto al consultarlo. **No fusionar estas ramas por efecto de la investigación.**

## Resumen ejecutivo / diagnóstico

La oportunidad inicial de más valor no parece ser implantar una nueva suite ni un runtime más, sino **probar un borde de datos externo y trazable** entre: (1) contrato/anexos/pliegos y (2) cronograma/BOQ/BOM, conservando la semántica ya diseñada en C2Pro (ProjectGraph, trusted/pending, Health vs Coherence, evidence, HITL).

La integración comercial debe ser opcional y por API/adaptadores. La alternativa OSS merece prueba focal, no adopción inmediata. Los repositorios son reales y activos, pero **ninguno demuestra por sí mismo la coherencia EPC de extremo a extremo**.

## Hechos técnicos comprobados en repositorio C2Pro

1. **La rama de research está basada en un `main` anterior a las ramas de piloto actuales.** El HEAD de `main` expuesto el 20-11 era `299aaf19...` (commit 28-10). El piloto N4-only está en PR #1276 (HEAD `916808c5...`, no fusionada). Toda afirmación de "ya funciona" debe comprobarse en la SHA relevante, no inferirse de la rama de investigación.
   - https://github.com/AI-Gen-AI/C2Pro/pull/1276
2. **El servicio de integración WBS/BOM de `main` y del HEAD de #1276 aún es un stub en este archivo específico**, no un circuito de compras completo: `_load_snapshot_rows()` devuelve fixtures, mientras `build_and_persist_from_wbs_bom_snapshot()` llama `save_plan_items(items=[])` y `save_conflicts(conflicts=[])`. Esto es **un hallazgo de un archivo concreto**, no prueba de inexistencia de otras funciones.
   - https://github.com/AI-Gen-AI/C2Pro/blob/916808c5212e3dbc652407f35f3a17557623c06c/apps/api/src/procurement/application/integration_service.py
3. **ADR-018 ya separa tres conceptos:** evidencia/Health (¿se puede evaluar?), Coherence Score (¿son consistentes los estados?), Alerts (¿qué requiere atención?). Canon de seis dimensiones `SCOPE/BUDGET/TIME/TECHNICAL/LEGAL/QUALITY`. Una consistencia alta puede coexistir con alerta CRITICAL, p. ej. retraso reconocido en todas las fuentes. Preservar **honest nulls**, score y confianza por separado. No crear un nuevo Coherence Score como proxy de salud del proyecto.
   - https://github.com/AI-Gen-AI/C2Pro/blob/299aaf19f5025a2162c6a2c626542f6dd472c3c6/docs/architecture/decisions/ADR-018-project-health-engine.md
4. **ADR-017** plantea DocumentGraph/Tier1 y ProjectGraph/Tier2 asíncrono. Por tanto OpenContracts, Google GraphRAG o nuevas herramientas no deben convertirse inadvertidamente en otro grafo canónico de estado.
   - https://github.com/AI-Gen-AI/C2Pro/blob/299aaf19f5025a2162c6a2c626542f6dd472c3c6/docs/architecture/decisions/ADR-017-projectgraph-two-tier-orchestration.md
5. **ADR-026** define la frontera de confianza en promociones de estado. Un candidato externo a N4/N12 **no** es automáticamente `TRUSTED`, ni válido para Coherence Score canónico, por el hecho de venir de un motor especializado.
   - https://github.com/AI-Gen-AI/C2Pro/blob/299aaf19f5025a2162c6a2c626542f6dd472c3c6/docs/architecture/decisions/ADR-026-trusted-state-commit-boundary.md

## Candidatos OSS: comparación inicial no-benchmark

| Herramienta | Encaje propuesto | Frontera | Riesgo principal | Veredicto |
|---|---|---|---|---|
| **MPXJ** | Importador externo XER/PMXML/MPP/Asta con paquete Python + JVM | `ScheduleSourceAdapter`→actividades/hitos/baselines/evidencia de versión | Fidelidad de calendarios, zonas horarias, offsets, critical path y licencia LGPL 2.1 | **SPIKE P0** de lectura/normalización sin inferencia |
| **Docling** | Parsing de PDF/DOCX/XLSX; estructura y fuentes visuales | `DocumentParseAdapter`→páginas/tablas/source-map | Solapamiento con ingesta actual, coste/OCR, pérdida de referencias a original | **SPIKE P0** frente a parser existente |
| **LangExtract** | Extracción tipada y anclada a spans con LLM | `ExtractionCandidateAdapter`→candidatos NO trusted | Prompts/evidencia ≠ exactitud jurídica; inferencia y licencias de modelos | **SPIKE P1** solo con mismo oráculo |
| **OpenContracts** | Corpus, anotaciones revisables, citation graph y MCP | `EvidenceServiceAdapter`, opcional | Duplicación de DocumentGraph/HITL/ProjectGraph, coste de operar segunda plataforma | **Comparar, no implantar por defecto** |
| **InvenTree** | Estructura BOM/producto/proveedor como sistema externo | `BOMSourceAdapter` o importación CSV | Los términos BOM discreta no siempre corresponden a BOQ/WBS EPC | **Referencia P1** |
| **ERPNext** | Requisición/RFQ/PO/recepción/factura vía API | `ProcurementSystemAdapter` | GPL-3.0, mantenimiento ERP y coupling transaccional | **Referencia P1, no incrustar** |
| **IfcOpenShell** | IFC/IDS y comprobación de propiedades | `EngineeringSourceAdapter` | Solo casos con información BIM/IFC; LGPL 3.0 | P2 condicionado |
| **MCP Python SDK** | Exposición read-only a Claude/ChatGPT | Herramientas con scoping usuario/tenant | Autorización, OAuth, no atribuir autoridad al LLM host | P1 diseño |

Fuentes originales: https://github.com/joniles/mpxj ; https://github.com/docling-project/docling ; https://github.com/google/langextract ; https://github.com/Open-Source-Legal/OpenContracts ; https://github.com/inventree/InvenTree ; https://github.com/frappe/erpnext ; https://github.com/IfcOpenShell/IfcOpenShell ; https://github.com/modelcontextprotocol/python-sdk.

### Cadena contractual que realmente importa
No inferir equivalencias por matching de strings:
`Clause/SourceSpan` → `Obligation[scope, time, cost, technical, legal, quality]` → `Requirement` → `WBSWorkPackage` → `ScheduleActivity` → `CostLine/BOQ` → `BOMItem` → `RFQLine/OfferLine/PO` → `RACI responsibility` → `Alert/ReviewDecision`.

Cada relación exige `project_id, tenant_id, source_id, source_revision/hash, source_span/cell/row, asserted_or_inferred, matching_basis, confidence, coverage, human_review_state, observed_at`. Los identificadores no coincidentes deben permanecer explícitamente sin resolver, nunca emparejarse forzosamente. La existencia del dato no equivale a evidencia de conformidad.

## Experimentos propuestos en paralelo — sin ejecución aún

### F0 — Comprobar preservación estructural (sin LLM, bajo coste)
**Corpus:** contrato sintético con anexo y cronograma XER/PMXML/MPP; BOQ y BOM con IDs semánticos, dos versiones con cambio de plazo/coste y dos fuentes contradictorias.
**Comparativa:** parser actual vs Docling para fuentes documentales; MPXJ para estructura schedule. Extraer y registrar `source spans` y `native ids`; 0 falsos emparejamientos autovalidados.
**Criterio:** la salida debe preservar hitos, calendarios/baselines, identificadores y origen, o describir pérdidas. Rechazar prueba si solo produce texto plano o no mantiene source references.

### F1 — Extracción contractual con oráculo independiente (gasto de IA solo si autorizado separadamente)
Comparar N4/N12 y LangExtract sobre mismo contrato/anexos, budget/model/config/version y cobertura. Oráculo evaluado por expertos: materialidad de las cláusulas, omisiones, false positives, citas exactas y contradicciones. No promover a trusted.
**Criterio:** todo hallazgo CRITICAL debe ser verificable y las omisiones críticas deben informarse por separado. No usar estrellas de GitHub ni tests unitarios como medida de calidad de análisis.

### F2 — Coherencia transversal sin ERP transaccional
Importación de cronograma + BOQ/BOM/3 ofertas en archivos exportados; comprobar requerimiento contractual de fecha, suministro ofertado y coste aprobado, más RACI asignado. El motor puede producir discrepancia candidata y evidencia; no adjudica ni envía emails.
**Criterio:** conflicto de plazo y exclusión técnica explicados; ninguna relación sin evidencia queda validada.

## Riesgos que deben estar en el informe Planner
- **C2Pro research branch desactualizada respecto al piloto:** auditar deltas por SHA, nunca rebase/merge por inercia.
- **Dos grafos/tres scores:** evitar OpenContracts/GraphRAG como segundo estado de proyecto y no colapsar Health/Coherence/Alerts.
- **Múltiples modelos sin certificación:** source span correcto puede acompañar interpretación errónea.
- **Licencias OSS ≠ licencia de modelos:** MPXJ LGPL, ERPNext/OpenProject GPL, pesos en Hugging Face bajo licencias propias.
- **Diferencia de sistemas:** BOM de manufactura discreta vs BOQ/WBS de construcción EPC.
- **Trazabilidad transaccional:** RFQ/PO/invoice puede requerir cuentas/servicios; no contaminar demo funcional con dependencias comerciales.
- **Recuperación y autoridad:** datos de proveedor no pueden pasar a trusted por una respuesta MCP.

## Recomendación táctica
1. Elegir **MPXJ + contrato/BOQ/BOM exportados** como primer cruce de datos **sin facturación IA**, verificando preservación y mappings.
2. En paralelo hacer comparación de **Docling vs ingesta propia**, limitada a formato y evidencia, no impacto comercial.
3. Diseñar la semántica de integración para que **el motor contractual siga siendo intercambiable** hasta superar el oráculo N4/N12; no comenzar por implantar OpenContracts, ERPNext ni un nuevo runtime.

**Resultado:** esta revisión aporta hipótesis y hallazgos de código, **no** acredita viabilidad económica, eficacia sobre contratos reales o compatibilidad ejecutada.
