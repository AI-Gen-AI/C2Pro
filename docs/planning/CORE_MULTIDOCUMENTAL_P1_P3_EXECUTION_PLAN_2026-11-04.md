# C2Pro — CORE multidocumental | Plan de ejecución P1–P3

**Versión:** 1.0 · **Fecha:** 2026-11-04 · **Estado:** PLAN APROBADO PARA DOCUMENTACIÓN / IMPLEMENTACIÓN P1–P3 AÚN NO AUTORIZADA COMO DESPLIEGUE
**Repositorio:** AI-Gen-AI/C2Pro · **Candidato de integración:** [PR #1112](https://github.com/AI-Gen-AI/C2Pro/pull/1112) · **Base inspeccionada:** \`34f1f67d66f26c2e905570c39a0d693c605fca6e\`.
**Propósito:** una hoja de ruta ejecutable y actualizable, sin crear WORK redundantes ni rehacer auditorías. Este plan no acredita funcionalidad ni sustituye la UAT real.

## 0. Resumen ejecutivo y arquitectura

**Decisión:** arquitectura **B**: capa común de cobertura, integridad y procedencia **por revisión inmutable**, más extractores especializados por familia documental. RAG existente y LLM se reutilizan selectivamente para interpretación; **no** son autoridad de cobertura ni de aprobación humana. La arquitectura C (recuperación contextual adicional) solo se habilitará si un experimento diferencial acredita beneficio concreto.

Cuatro entradas: **Contrato** (obligaciones/riesgos); **Presupuesto** (filas, cantidades, divisas y totales); **Cronograma** (actividades, fechas, dependencias observadas); **Especificación técnica** (requisitos y parámetros). Salida: evidencia revisable vinculada a fuente + interpretación y contradicciones **confirmadas, provisionales o NOT_ASSESSED**, sin puntuación fabricada.

**Invariantes no negociables:**
- Tenant, proyecto, documento, \`revision_id\`, huella/hash y localizador de fuente acompañan cada dato usado para una decisión. La última carga/propuesta nunca sustituye implícitamente una revisión trusted-current.
- \`DocumentStatus.ANALYZED\` **no** es sinónimo de cobertura, comprensión semántica ni aprobación: mantener indicador independiente por revisión (\`COMPLETE | PARTIAL | UNSUPPORTED | UNVERIFIED\`, con motivos, contadores y unidades).
- No convertir citas verbatim en garantía de interpretación; no tratar «procesado el 100 % del texto» como «100 % de recall». Toda unidad de fuente debe estar contabilizada, incluida la excluida/incompatible.
- Una fila Excel o código WBS impreso **no** es una WBS canónica; los enlaces y decisiones siguen las autorizaciones humanas existentes. TECHNICAL solo puede puntuarse con evidencia y autoridad de cumplimiento reales.
- Sin datos ficticios como hechos de cliente; sin volcado de prompts, contratos o respuestas del modelo a LangSmith/logs no autorizados; no filtrar información entre tenants.
- Limitar los cambios a flujos actuales; no añadir otro RAG, nuevos LLM, Neo4j, gestor genérico de agentes, ruta crítica, calendarios o parsers MPP/XER en esta entrega.

## 1. Estado de partida / puerta de entrada P0

| Elemento | Estado a 2026-11-04 | Puerta de entrada |
|---|---|---|
| PR #1112 | OPEN / DRAFT, sin merge; HEAD base \`34f1f67d\` verificado para este plan | Claude mantiene **escritura exclusiva** de esa rama. |
| P0 Codex | **Reportado** local en \`codex/core-p0-20261104\`, commit \`232ef48375eb6672b2df6ea76bcaa49b7c3d6fe6\`; 16 pruebas focalizadas PASS reportadas | El commit **no se pudo recuperar en GitHub durante la redacción**; no asumir publicado ni integrado. Verificar push/HEAD remoto, revisión diferencial, integrarlo en #1112 sin sobreescrituras, y entonces fijar nuevo SHA. |
| P0 técnico | Fallback BC3 sintético, cobertura declarativa y trazas/logs sensibles según reporte de Codex | Acreditar que el código realmente elimina el mock BC3, expone cobertura veraz y no exporta payload sensible; no repetir auditoría general. |
| P1, P2, P3 | Planificados, **NO IMPLEMENTADOS / NO ACEPTADOS** | Cada fase requiere evidencia de los criterios de salida específicos. |

**Gate G0:** validar que P0 publicado e integrado en candidato de trabajo, sin perder cambios de Claude, y fijar un HEAD exacto. Si P0 sigue solo local, ejecutar P1 en base controlada pero **no declarar P0 integrado**. No modificar main ni desplegar producción.

## 2. Contrato técnico común: ledger de cobertura y evidencia

Para cada revisión inmutable, registrar al menos: \`tenant_id\`, \`project_id\`, \`document_id\`, \`revision_id\`, \`blob_sha256\`, familia, formato, algoritmo/versión de extracción, instante, estado, motivo, totales por tipo y unidades de origen. Cada unidad (\`clause/section/span\` o \`sheet!row\`) posee identidad y localizador, estado \`EXTRACTED | SKIPPED | UNSUPPORTED | UNVERIFIED\`, motivo, enlace a evidencia y, cuando corresponda, offset/página/columna. Evitar guardar texto contractual completo en telemetría.

**Cobertura documental:** \`COMPLETE\` solo si todas las unidades esperadas de la fuente aceptada están inventariadas/procesadas sin desconocidos; \`PARTIAL\` ante exclusiones/acortamientos; \`UNSUPPORTED\` para formato sin extractor válido; \`UNVERIFIED\` cuando no puede acreditarse integridad o resultado. **Cobertura semántica/interpretativa es un indicador separado:** un documento puede estar totalmente indexado y todavía no evaluado en riesgos, TIME o TECHNICAL.

Persistir con contratos y metadatos de revisión existentes, sin introducir una migración global si no resulta imprescindible; no almacenar estados nuevos en \`DocumentStatus\` por defecto. Los consumidores downstream deben usar **una sola revisión trusted-current** o declarar \`NOT_ASSESSED\`.

## 3. P1 — Extracción completa y evidencias de cuatro familias

**Dependencia:** G0, contrato de ledger estable. **Propietario propuesto:** Codex (escritor de su rama); Claude (integrador y guardián de #1112); ChatGPT (revisión de salidas y coordinación). Los bloques se integran **secuencialmente** y se prueban en aislamiento, sin dos escritores simultáneos en archivos comunes.

### P1-A — Presupuesto XLSX: libro de filas y totales

**Modificar/reutilizar:** 
- \`apps/api/src/documents/adapters/parsers/excel_file_parser.py\`
- \`apps/api/src/analysis/application/extract_budget_revision_evidence_use_case.py\`
- \`apps/api/src/analysis/domain/budget_row_evidence.py\`
- \`apps/api/src/documents/application/budget_stated_total.py\`
- \`apps/api/src/core/tasks/ingestion_tasks.py\`
- \`apps/api/src/documents/application/parse_document_use_case.py\`

**Implementación:**
1. Inventariar **todas las hojas** del XLSX; procesar las compatibles según política explícita y registrar hojas/filas sin procesar. Nunca confundir la hoja activa con todo el libro.
2. Conservar identidad de fila (\`Hoja!fila\`), tipo (partida, capítulo/subtotal, total declarado, vacío, inválido), cantidad, unidad, precio, importe, divisa y base fiscal cuando sean legibles. Evitar doble cómputo de capítulos.
3. Fórmulas: preservar expresión y estado de cálculo si es visible; el caché no acredita recalculado. Valores sin verificación **no producen hechos confirmados**. Un error en una fila no debe borrar silenciosamente el resto.
4. Enlazar \`ExtractBudgetRevisionEvidenceUseCase\` existente, que verifica bytes/revisión y previene filas duplicadas; no inventar WBS. Conservación por revisión y contabilización idempotente.
5. Conciliar total declarado, suma de partidas y subtotales con precisión adecuada (\`Decimal\`); ambigüedad sobre varias filas «TOTAL», impuestos, divisas o fórmulas = \`NOT_ASSESSED\` con motivo.

**Salida verificable:** inventario de hojas, \`N\` filas fuente, \`N\` evaluadas/\`N\` excluidas con causa, totales y sus localizadores exactos. Al menos una conciliación de partida↔total que no dependa de un mock/BOM ajeno. **No** implementar BC3 real salvo proyecto separado; P0 debe fallar cerrado.

**Pruebas dirigidas:** 2 hojas, subtotal etiquetado TOTAL, fórmula sin caché acreditado, varias divisas, partida duplicada, reupload y replay idempotente, tenant B negado.

### P1-B — Cronograma XLSX: actividad por fila y observación temporal

**Modificar/reutilizar:**
- \`apps/api/src/documents/adapters/parsers/excel_file_parser.py\`
- \`apps/api/src/analysis/application/extract_schedule_revision_evidence_use_case.py\`
- \`apps/api/src/analysis/domain/schedule_activity_evidence.py\`
- \`apps/api/src/documents/application/schedule_planned_finish.py\`
- \`apps/api/src/coherence/schedule_clause_builder.py\`
- \`apps/api/src/core/tasks/ingestion_tasks.py\`

**Implementación:**
1. Inventariar todas las hojas y actividades; guardar identidad \`sheet!row\`, nombre, ID de actividad/hito cuando exista, fechas literales, duración, WBS fuente y texto de predecesoras. Distinguir fechas observadas de calendario calculado.
2. Resolver duplicados e IDs ambiguos conservadoramente; fórmulas/fechas no acreditadas se etiquetan sin usarlas como baseline confirmada.
3. Conectar el caso de uso existente \`ExtractScheduleRevisionEvidenceUseCase\`; no interpretar texto WBS como enlace autorizado. Baseline aprobada es acto separado.
4. Conservar la última fecha fin **observada y sustentada** por revisión, con cobertura de actividades y limitaciones; múltiples cronogramas no se combinan por heurística.
5. Comparar con fecha contractual usando regla existente: **PROVISIONAL** cuando el fin es mera observación, **CONFIRMED** únicamente ante baseline válida y autoridad verificada.

**Salida verificable:** actividades inventariadas por revisión y hoja, contadores de fechas observadas/no evaluables, origen de cada fecha y razón explícita de no comparación. **Fuera de alcance:** CPM/ruta crítica, holguras, calendarios múltiples, replanificación predictiva y MPP/XER.

**Pruebas dirigidas:** 2 hojas, actividad con fórmula, predecesora textual, IDs duplicados, plazo posterior a contrato, baseline no aprobada, revisión propuesta, tenant B negado.

### P1-C — Contratos y especificaciones técnicas: cobertura de narrativa

**Modificar/reutilizar:**
- \`apps/api/src/core/tasks/ingestion_tasks.py\`
- \`apps/api/src/documents/application/technical_requirement_clauses.py\`
- \`apps/api/src/analysis/domain/risk_provenance.py\`
- \`apps/api/src/analysis/domain/citation_validation.py\`
- \`apps/api/src/analysis/adapters/graph/nodes.py\`

**Implementación:**
1. Conservar los rangos completos aunque una cláusula o sección supere 4.000 caracteres; fragmentar en **subspans unidos al mismo identificador fuente** si es necesario. Segmentos cortos/no clasificables se contabilizan, no desaparecen.
2. Para especificaciones reconocer encabezados estructurales reales (\`4.2 Transformadores\`, \`Section 5\`, etc.) y registrar **cada obligación**, no solo la primera por sección. Extracción de números/unidades/tolerancias como valores de fuente **unverified**, nunca como cumplimiento.
3. Tablas, anexos, OCR y texto no reconocible: inventariar limitación; no afirmar completa cobertura.
4. Alinear N4 y N15 en la identidad original/anonimizada de la cita y su verificación literal; \`source_quote\` debe estar vinculado a la misma revisión, no a texto libre de otra.
5. No alterar autoridad humana: una especificación indexada y un enlace WBS aprobado para revisión **no** acreditan conformidad técnica.

**Salida verificable:** toda sección/span contabilizada, obligaciones con offsets y revisión; ninguna cita atribuida a una revisión equivocada. Tests: encabezados numéricos, 2 obligaciones por sección, cláusula >4.000 caracteres, anexo al final y cita atravesando salto de línea.

### Gate P1 — aceptación

- En el proyecto sintético de referencia, **100 % de unidades fuente contabilizadas** como procesadas, excluidas con motivo o incompatibles; sin exclusiones conocidas invisibles. Esto **no** afirma recall semántico del 100 %.
- Cuatro familias con identidad \`tenant/document/revision/hash\` y evidencia localizada; reupload/replay no mezcla revisiones.
- Las rutas de ingestión actuales no empeoran el Complete Journey; formatos no soportados no presentan un análisis completo.
- Entrega 1 commit coherente por subfase, pruebas focalizadas, nota de riesgos y HEAD para integración. Solo Claude integra #1112.

## 4. P2 — Inteligencia y coherencia multidocumental

**Dependencia:** P1 aceptado en candidato; entrada única versionada por familia. No rediseñar las API existentes si hay un adaptador válido.

### P2-A — N4/N12: extracción y crítica con cobertura y evidencia

**Archivos clave:** \`analysis/adapters/ai/tools/risk_extraction_tool.py\`, \`analysis/adapters/graph/nodes.py\`, \`analysis/domain/ai_extraction.py\`, \`analysis/application/critique_extraction_use_case.py\`, \`analysis/domain/critique_evaluation.py\`, \`analysis/domain/risk_provenance.py\`.

- N4 consume cláusulas/subspans **por revisión**, en lotes completos con contexto de definiciones y referencias cuando sea necesario. El filtro léxico y los 40.000 caracteres pueden servir para priorizar, **no excluir** unidades sin declarar cobertura parcial.
- No truncar silenciosamente a 20 riesgos a nivel documento: límites por lote + consolidación trazable; deduplicar por evidencia y significado, preservar relaciones contradictorias y candidatos descartados con motivo.
- N12 valida riesgos contra las **cláusulas citadas y el ledger**, distingue consistencia de exhaustividad y marca omisiones/no evaluables. El fragmento actual de 16.000 caracteres no es prueba de ausencia documental.
- \`confidence=None\` permanece honesto cuando no existe medición, y el HITL mantiene su gate. Nunca interpretar un prompt «3–8» como número máximo de riesgos de un contrato grande.
- No enviar texto de clientes a trazas de evaluación. Experimento sintético sin datos reales.

**Aceptación:** riesgo con fuente completa, revisión y localizador; cobertura parcial visible al humano; riesgos de cláusulas situadas al principio/mitad/final alcanzan la evaluación; se preserva el manejo de fallos y \`None\`.

### P2-B — Coherencia determinista y WBS con autoridad

**Archivos clave:** \`coherence/cross_document/inputs.py\`, \`coherence/cross_document/assembly.py\`, \`coherence/cross_document/comparators.py\`, \`coherence/budget_clause_builder.py\`, \`coherence/schedule_clause_builder.py\`, \`analysis/application/canonical_structured_wbs_links.py\`, \`analysis/application/record_technical_wbs_review.py\`, \`coherence/graph/nodes.py\`.

- Conectar filas de presupuesto y actividades **trusted-current** a comparadores existentes; habilitar \`DET-BUD-INTERNAL\` y sumas por WBS solo con alcance y aprobaciones probados.
- Diferenciar: \`CONBUD/NEGMARGIN\` con importes, divisas, bases fiscales comparables; \`SCHDEAD\` provisional si el cronograma no tiene baseline aprobada; \`NOT_ASSESSED\` si falta verificación. No usar valores cacheados de fórmulas como importes aprobados.
- Requisitos técnicos/FAT sin enlace WBS: presentar como **«sin enlace demostrado»**, no «incumplimiento de especificación». Un requisito del contrato no convierte automáticamente un artefacto en canon.
- Revisiones propuestas, decisiones humanas pendientes y líneas de otro tenant nunca contaminan el estado trusted; recomputar tras cambio de revisión, sin duplicar alertas ni borrar decisiones.
- Contradicciones complejas especificación↔partida sin correspondencia estructurada: \`NOT_ASSESSED\` explícito antes que inventar matching semántico.

**Aceptación:** hallazgos con ambas fuentes, mismas revisiones/autorizaciones y tipo de certeza; sin promoción de \`PROPOSED\` a \`TRUSTED\`; idempotencia de alertas y enlace verificable en interfaz.

### Gate P2 — aceptación

- Los comparadores operativos están **conectados**, no solo presentes en código. Cada regla publica estado: \`CONFIRMED | PROVISIONAL | NOT_ASSESSED\`, con motivo cuando no se evalúa.
- Cobertura faltante bloquea declaraciones de coherencia completa y puntuaciones injustificadas; Score sigue \`NULL\` para TECHNICAL sin cumplimiento acreditado.
- N4/N12 identifican los riesgos sintéticos etiquetados dentro del alcance y muestran explícitamente qué relaciones no pueden evaluar.
- Validación específica de revisiones, A/B tenants, deduplicación, permisos y contradicciones conocidas; no suite general repetida sin motivo.

## 5. P3 — Un único Complete Journey real y UX de cliente

**Dependencia:** P1 + P2 integrados en candidato, despliegue aislado y controlado. El objetivo P3 es **producto visible**, no tests de código como sustituto de experiencia.

### P3-A — Proyecto sintético y verdades de referencia

Un solo proyecto persistido con **cuatro documentos**, datos inventados pero coherentes en identidad:
1. **Contrato DOCX/PDF:** precio 10 M EUR, entrega 30-06-2027, cláusula FAT, obligación sin keywords obvias y anexo/requisito al final; una sección >4.000 caracteres.
2. **Presupuesto XLSX:** pestañas Resumen + Partidas; importe conocido >10 M EUR para activar posible margen negativo cuando exista base verificada; falso subtotal rotulado TOTAL; fórmula sin resultado acreditado; partida deliberadamente ausente.
3. **Cronograma XLSX:** termina 30-09-2027, actividad con fórmula, dependencias fuente, un hito sin enlace aprobado; distinguir fin observado frente a baseline.
4. **Especificación DOCX:** «4.2 Transformadores — 50 MVA ±5 %» sin «Section» y otra sección FAT; revisión v2 propuesta cambia parámetro, no se incorpora como trusted hasta aprobación.

Publicar un **oráculo de evaluación** (tabla de hechos que se sabe que existen, su ubicación y respuesta esperada): confirmado, provisional, no evaluable con motivo; al menos una contradicción contractual/económica, una temporal y una ausencia de mapeo técnico explícita. No fijar arbitrariamente que *todas* las contradicciones deban ser detectadas si la capacidad no está implantada: la diferencia debe declararse como brecha.

### P3-B — Una prueba integral observable, sobre URL real aislada

Misma revisión de frontend/backend, servicio API, worker y base PostgreSQL. Una pasada E2E con:
- Clerk real A: login, crear proyecto y subir los cuatro documentos vía UI; UUID, revisión, hash y cobertura consultables.
- Ejecutar evaluación con **IA real** para N4/N12 donde corresponda; no confundir mock determinista con aceptación. Observar resultados, errores y costes.
- Abrir riesgos, alertas y comparadores; navegar a fuente y localizador originales. Estado \`PARTIAL/NOT_ASSESSED\` y motivos visibles.
- Realizar HITL donde sea exigible; probar decisión persistida; ninguna promoción automática.
- Salir y entrar de nuevo: persisten proyecto, documentos, decisiones y avisos. Identidad B de otro tenant no puede ver ni modificar recursos de A.
- Verificar una entrada no soportada (ej. BC3 sin parser) con error claro y **sin** datos sintéticos.
- Capturar evidencias mínimas: URL/snapshot, SHA de frontend/backend, pasos principales de navegador, IDs y respuestas/filas PostgreSQL *sin secretos*, coste/latencia, divergencias y primera causa de fallo.

**No programar rondas indefinidas.** Una prueba integral y correcciones focalizadas si falla; repetir únicamente el tramo afectado y, tras integración, una aceptación integral final. Los tests unitarios dirigidos son condición de calidad, no sustituyen esta prueba.

### Gate P3 — aceptación de usuario piloto

- Carga real de cuatro documentos e identidad persistida por revisión; resultados estables tras relogin.
- Se visualizan hechos/alertas correctos o una limitación explícita; **cero hallazgos confirmados sin fuentes verificables**, cero datos BC3 inventados, cero filtraciones entre tenants.
- Se prueba al menos una comparación económica y una temporal con semántica correcta; dimensión TECHNICAL no se inventa.
- Experiencia utilizable sin navegación engañosa: el usuario entiende «qué se revisó», «qué riesgo importa», «por qué» y «qué no se sabe».
- Se publica dictamen \`ACCEPTED | PARTIAL | NOT_ACCEPTED\` con primera brecha, no una etiqueta de éxito basada en CI verde. Si S1–S8 completo requiere funciones adicionales, **no** declararlo 8/8 por esta prueba CORE.

## 6. Ejecución, secuencia, dependencias y no duplicación

| Orden | Paquete | Responsable de escritura | Dependencia | Esfuerzo relativo | Evidencia de cierre |
|---|---|---|---|---|---|
| G0 | Verificar/absorber P0 \`232ef483\` | Claude integra; Codex prepara | Remoto disponible | Bajo–medio | SHA exacto #1112 y pruebas mínimas |
| P1-A | Libro de presupuesto | Codex, rama propia | G0/ledger | Medio–alto | Evidencia por fila + cobertura + reconciliación |
| P1-B | Libro de cronograma | Codex, rama propia | G0/ledger | Medio | Actividades + estados fecha + origen |
| P1-C | Contratos y especificaciones | Codex, rama propia | G0/ledger | Alto | Rango íntegro + obligaciones + localizadores |
| P2-A | N4/N12 por cobertura y lotes | Codex, rama propia | P1-C | Alto | Extracción/crítica sin corte silencioso |
| P2-B | Comparadores/WBS | Codex, rama propia | P1-A/B/C | Medio–alto | Regla conectada, estado y fuentes |
| P3-A/B | Dataset, UI, una E2E UAT | Claude integra/ejecuta; Codex corrige exclusivamente bloqueos asignados | P1/P2 | Medio–alto | Informe user journey con evidencias exact-SHA |

**Política de coordinación:** un solo escritor por rama y archivo; Codex en worktree + rama independiente, commits pequeños por paquete; Claude decide cherry-pick/rebase y conserva #1112 OPEN/DRAFT; no push/PR/despliegue/merge a producción por defecto. Revisar diferencias contra HEAD remoto antes de integrar. Mantener el mismo enlace de este plan y registrar en el checkpoint de #1112 los SHAs, PASS/FAIL, bloqueos y siguiente paquete. No multiplicar issues, planes o PR sin necesidad.

**Estado actualizado del plan (editar este documento, no duplicarlo):**
- G0 — P0 remoto/integración: **PENDING**
- P1-A / P1-B / P1-C: **PLANNED**
- P2-A / P2-B: **PLANNED**
- P3-A / P3-B: **PLANNED**

## 7. Riesgos y condiciones STOP

1. P0 no disponible en remoto o conflictos con Claude → detener integración, conservar commits y resolver solo diffs afectados.
2. Migración irreversible o cambio de contrato canónico \`RiskItem/WBS\` → exigir decisión técnica específica antes de escribir.
3. Excel fórmulas sin cálculo probado → no promover cantidades/fechas a verificadas; \`PARTIAL/NOT_ASSESSED\`.
4. Falta de revisión/hash/tenant o propuesta pendiente → no consumir en scoring/alerta confirmada.
5. Se requiere nuevo modelo, OCR masivo, parser BC3 o rutas críticas → fuera de alcance P1–P3; registrar propuesta posterior.
6. Sin infraestructura aislada apta para UAT (Clerk A/B, frontend/backend/PG coherentes) → P3 \`BLOCKED\`, no sustituir por tests mock.
7. Cualquier traza/log con texto real → STOP de evaluación con datos sensibles hasta contenida; trabajar solo con corpus sintético.

## 8. Referencias de implementación en el repositorio

- [PR #1112 — candidato integrado](https://github.com/AI-Gen-AI/C2Pro/pull/1112).
- [ACC-01 #1049 — recorrido del usuario](https://github.com/AI-Gen-AI/C2Pro/issues/1049).
- [MASTER PQ-HITL #936 — revisión granular y autoridad](https://github.com/AI-Gen-AI/C2Pro/issues/936).
- [N4 \`risk_extraction_tool.py\`](https://github.com/AI-Gen-AI/C2Pro/blob/34f1f67d66f26c2e905570c39a0d693c605fca6e/apps/api/src/analysis/adapters/ai/tools/risk_extraction_tool.py).
- [N12 \`ai_extraction.py\`](https://github.com/AI-Gen-AI/C2Pro/blob/34f1f67d66f26c2e905570c39a0d693c605fca6e/apps/api/src/analysis/domain/ai_extraction.py).
- [Ingesta \`ingestion_tasks.py\`](https://github.com/AI-Gen-AI/C2Pro/blob/34f1f67d66f26c2e905570c39a0d693c605fca6e/apps/api/src/core/tasks/ingestion_tasks.py).
- [Excel \`excel_file_parser.py\`](https://github.com/AI-Gen-AI/C2Pro/blob/34f1f67d66f26c2e905570c39a0d693c605fca6e/apps/api/src/documents/adapters/parsers/excel_file_parser.py).
- [Requisitos técnicos](https://github.com/AI-Gen-AI/C2Pro/blob/34f1f67d66f26c2e905570c39a0d693c605fca6e/apps/api/src/documents/application/technical_requirement_clauses.py).
- [Presupuesto: evidence use case](https://github.com/AI-Gen-AI/C2Pro/blob/34f1f67d66f26c2e905570c39a0d693c605fca6e/apps/api/src/analysis/application/extract_budget_revision_evidence_use_case.py).
- [Cronograma: evidence use case](https://github.com/AI-Gen-AI/C2Pro/blob/34f1f67d66f26c2e905570c39a0d693c605fca6e/apps/api/src/analysis/application/extract_schedule_revision_evidence_use_case.py).
- [Comparadores](https://github.com/AI-Gen-AI/C2Pro/blob/34f1f67d66f26c2e905570c39a0d693c605fca6e/apps/api/src/coherence/cross_document/comparators.py).

**Regla para futuras sesiones:** comenzar leyendo *esta versión del plan*, revalidar PR HEAD y estado del gate inmediatamente anterior; responder con \`fase | SHA | cambios | pruebas | bloqueo | siguiente paso\`. El plan es guía; ninguna declaración de PASS sin evidencia del HEAD integrado.
