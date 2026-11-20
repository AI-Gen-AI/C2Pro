# Plan inicial del Planner (Codex) — 2026-11-20

**Origen:** AI-GEN Ops / Codex con rol Planner, job `4c2217758df1681190972e6acb5feaad`.  
**Resultado:** succeeded (exit 0); evaluación read-only de la rama, pin `6701e422805f9935a9494cc29c6c8c39ef5b9358`.  
**Estado:** PROPUESTA de planificación, no aprobación de arquitectura ni ejecución de spikes.  
**Nota:** esta es la salida de la revisión focal repetida después de que la ejecución original de Codex fallara con exit -25. El informe proviene de documentos ya existentes, no de benchmarks ejecutados.

---

## Plan inicial auditado

Conclusión: conviene validar primero un borde de integración trazable y reversible. ProjectGraph seguirá siendo el único modelo canónico; cualquier salida externa nace como `pending`, nunca como `trusted`. Health/evaluabilidad, Coherence/consistencia y Alerts/atención operativa permanecen separados. Este plan no altera N4-only, UAT ni sus ramas.

### 1. Dos arquitecturas alternativas

#### A. Adaptadores lightweight

Flujo: archivos o APIs → adaptadores especializados (`DocumentParseAdapter`, `ScheduleSourceAdapter`, etc.) → contratos normalizados → staging `pending` → validación humana → ProjectGraph.

Componentes candidatos: Docling para estructura documental, MPXJ como proceso JVM aislado y LangExtract opcional para candidatos contractuales. BOQ/BOM/RFQ pueden comenzar mediante CSV/XLSX exportados.

Pros:

- Menor coste operativo y superficie de seguridad.
- Evita un segundo grafo, HITL o repositorio documental.
- Sustitución sencilla de proveedores y parsers.
- Adecuada para una demo reproducible sin ERP ni SaaS.
- Conserva UUID, tenant, revisión y promoción en C2Pro.

Contras:

- C2Pro debe resolver normalización, reintentos, versionado y observabilidad.
- UX de anotación y revisión más limitada.
- MPXJ introduce interoperabilidad Python/JVM.
- La extracción documental compleja puede exigir más desarrollo propio.

Recomendación: arquitectura inicial para los spikes.

#### B. Servicio documental especializado

Flujo: fuentes → OpenContracts u otro servicio documental → anotaciones, spans y grafo documental propio → `EvidenceServiceAdapter` → staging `pending` → ProjectGraph.

El servicio sería autoridad de artefactos documentales, no del estado del proyecto. Sus IDs se conservarían como `native_id`; las relaciones de negocio canónicas seguirían perteneciendo a ProjectGraph.

Pros:

- Anotación, revisión, corpus y APIs documentales ya integrados.
- Mejor colaboración sobre cláusulas y evidencia.
- Puede acelerar datasets etiquetados y evaluación humana.
- Aísla procesamiento documental pesado.

Contras:

- Riesgo alto de duplicar DocumentGraph, HITL y control de versiones.
- Mayor TCO, despliegue, migración, tenant isolation y operación.
- Sincronización e identidad más complejas.
- Sus estados podrían confundirse indebidamente con `trusted`.
- No resuelve por sí mismo coherencia EPC transversal.

Condición de elección: solo si demuestra una ventaja material en revisión/evidencia que compense operar una segunda plataforma.

### 2. Spikes priorizados

#### Spike 1 — Preservación de cronograma con MPXJ

- **Rol:** Backend/Domain, con QA independiente.
- **Precondiciones:** corpus sintético autorizado con XER/PMXML y, si es legalmente posible, MPP/Asta; dos revisiones; oráculo de WBS, actividades, hitos, calendarios, baselines, relaciones y holguras.
- **Archivos futuros:** `spikes/schedule-mpxj/README.md`, `fixtures/manifest.json`, `results/preservation-report.json`, `schemas/schedule-activity.schema.json`.
- **DoD:** importar sin escritura externa; preservar IDs nativos, revisión, calendario, dependencias y evidencia; declarar toda pérdida; cero matches ambiguos promocionados.
- **Evidencia:** diff estructural contra el oráculo, fixtures con hash, versiones de MPXJ/JVM, logs de ejecución y tabla de pérdidas.
- **Coste relativo:** bajo–medio.
- **NO-GO:** pérdida silenciosa de calendarios/baselines/relaciones, IDs inestables, licencia o empaquetado JVM incompatibles, o imposibilidad de reproducir resultados.

#### Spike 2 — Docling frente a ingesta existente

- **Rol:** AI/Backend, con QA documental.
- **Precondiciones:** mismo corpus autorizado de contrato, anexos, pliegos y tablas; baseline de ingesta fijada por SHA, sin tocar N4/N12; criterios de página, tabla, celda y span.
- **Archivos futuros:** `spikes/document-parsing/README.md`, `eval/corpus-manifest.json`, `eval/parser-comparison.json`, `schemas/evidence-ref.schema.json`.
- **DoD:** comparación ciega y reproducible; medir preservación de estructura, referencias, revisiones, tablas, coste y tiempo; ninguna afirmación de cobertura completa sin medición.
- **Evidencia:** precision/recall estructural, anclajes verificables, ejemplos de pérdida, hashes de entrada y configuración/versiones.
- **Coste relativo:** bajo.
- **NO-GO:** citas no recuperables en el original, pérdida material de tablas/referencias, coste desproporcionado o ausencia de mejora complementaria sobre la ingesta actual.

#### Spike 3 — Extracción contractual intercambiable

- **Rol:** AI/Legal-domain, con evaluador independiente.
- **Precondiciones:** autorización separada de inferencia; oráculo de obligaciones críticas; mismo corpus, taxonomía, presupuesto y cobertura para N4/N12 y LangExtract. OpenContracts se evalúa solo como backend opcional de anotación.
- **Archivos futuros:** `spikes/contract-extraction/README.md`, `eval/oracle.json`, `eval/extraction-matrix.json`, `schemas/requirement.schema.json`, `schemas/discrepancy.schema.json`.
- **DoD:** medir recall crítico, precisión, citas, contradicciones, omisiones y coste; todas las salidas permanecen `pending`; documentar fallback al motor actual.
- **Evidencia:** resultados por severidad, bundle de citas, cobertura examinada, falsos positivos/negativos y revisión humana firmada.
- **Coste relativo:** medio–alto.
- **NO-GO:** omisiones críticas no declaradas, spans correctos con interpretación material errónea, promoción automática a `trusted`, o necesidad de convertir OpenContracts en grafo canónico.

### 3. Contratos mínimos

```text
EvidenceRef {
  tenant_id, project_id, source_id, native_id?,
  source_revision, source_hash, location {page?, span?, sheet?, row?, cell?},
  excerpt_hash, observed_at, run_id, coverage
}

Requirement {
  id, tenant_id, project_id, kind, statement,
  evidence_refs[], validity {from?, to?},
  assertion: extracted|inferred|human,
  confidence?, review_state: pending|trusted|rejected,
  unresolved_links[]
}

ScheduleActivity {
  id, tenant_id, project_id, native_id, source_revision,
  wbs_id?, name, start?, finish?, milestone,
  calendar_id?, baseline?, predecessors[],
  evidence_refs[], review_state
}

Discrepancy {
  id, tenant_id, project_id, dimension,
  subject_refs[], claim, evidence_refs[],
  severity, confidence, coverage,
  status: candidate|confirmed|dismissed,
  owner?, review_decision?, run_id, detected_at
}
```

Reglas: `pending != trusted`; confianza no sustituye revisión. `Discrepancy` no es `Alert`: una política posterior decide si merece atención. Tampoco calcula Health ni Coherence; Health expresa evaluabilidad/cobertura y Coherence consistencia entre estados.

### 4. Dependencias y decisión del propietario

Secuencia: congelar corpus, permisos, oráculo, SHAs y umbrales → ejecutar Spikes 1 y 2 → autorizar gasto y ejecutar Spike 3 → comparar TCO y evidencia → decidir arquitectura. El cruce contractual–cronograma depende de 1 y 3; la arquitectura de servicio documental depende de que el Spike 3 justifique su operación.

El propietario debe aprobar:

1. Arquitectura base A o autorización condicionada para explorar B.
2. Corpus y derechos de uso.
3. Presupuesto de inferencia del Spike 3.
4. Umbrales de recall crítico y tolerancia de falsos positivos.
5. Revisión de licencias, especialmente MPXJ LGPL y modelos/datos separados.
6. Autorización posterior e independiente antes de escribir archivos, abrir backlog, integrar, fusionar o desplegar.

Auditoría basada exclusivamente en los cinco documentos indicados; no se modificó ningún archivo ni estado operativo.
