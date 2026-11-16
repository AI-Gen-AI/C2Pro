# C2Pro V4 — Diseño propuesto de inteligencia adaptativa y ejecución eficiente
**Fecha:** 2026-11-16
**Estado:** propuesta aprobada conceptualmente por el propietario; revisión crítica Claude solicitada **ANTES DEL GO de implementación**.
**Referencias:** ADR-014 Project State, ADR-017 Two-Tier ProjectGraph, ADR-009 Coherence, workflow N1-N17, PR #1234 N4 multiproveedor, issue #1229 y CORE #1049.
**Ámbito:** arquitectura de inteligencia de proyectos multivertical (EPC/ETO hoy; software, I+D, inversiones y otros dominios posteriormente).

## 0. Decisión ejecutiva y restricciones
C2Pro no es un generador de informes por documento. Debe construir, mantener y explicar un estado verificable, temporal, de un **proyecto** a partir de contratos, cronogramas, presupuestos, especificaciones, planos, anexos, requisitos, cambios, incidencias y futuras fuentes.
- Prioridad presente: demostrar Complete Journey REAL de expediente EPC y cerrar #1229; futuras verticales deben resultar posibles sin rediseño fundamental.
- Se mantiene LangGraph cuando aporta orquestación, persistencia y HITL; no se crean 17 agentes ni se impone un LLM por nodo.
- Se eliminan heurísticas deterministas que sustituyan interpretación jurídica/semántica. Se conservan cálculos exactos, comparaciones numéricas, validación de fuente, autorización, seguridad, integridad, costes, concurrencia e idempotencia.
- RAG puede ayudar a localizar contexto adicional pero no debe ocultar contenido durante extracción, ni convertirse en condición de iniciación N4/N12.
- Un resultado parcial no pasa por análisis completo. Ninguna aprobación simulada sustituye al humano. No se cambia el piloto ni se fusiona #1234 sin UAT y GO expreso.

## 1. Experiencia objetivo (prioridad producto)
Pantalla de proyecto: (1) Coherence validada y provisional separadas; (2) Health, cobertura y confianza; (3) riesgos, contradicciones y requisitos sin resolver; (4) impacto en tiempo, presupuesto, alcance, calidad; (5) acciones recomendadas con responsable y estado; (6) fuente exacta clicable por hallazgo (cláusula, celda, actividad, página, revisión); (7) HITL individual aprobar/rechazar/corregir y acto de aprobación final separado; (8) histórico y cambios entre versiones.
Cada hallazgo: hechos/evidencia, interpretación, materialidad, confianza, dependencia afectada, fuente original/versionada, estado de revisión y limitaciones. Evitar scores falsos o que suban al aceptar un riesgo.
Muestra progreso real y permite consultar hallazgos parciales claramente marcados, sin bloquear la subida a la espera de análisis.

## 2. Arquitectura conceptual de seis etapas (NO seis llamadas a modelo)
1) Preparar: N1/N2/N3 — upload autorizado, versionado, análisis de formato, parsing, OCR si necesario, inventario de cobertura, protección PII, clasificación multi-etiqueta.
2) Comprender: N4/N5/N9 y especialistas — parse estructurado cuando es fuente estructurada; IA incremental para semántica, ambigüedad, relaciones y riesgos.
3) Verificar: N12/N15 — evaluación de cobertura, exactitud literal, pertinencia y omisiones; nuevas consultas SOLO focales.
4) Relacionar: Project State/ProjectGraph, N8/N10 — enlazar hechos y entidades multi-documento, baseline aprobado vs observado vs propuesto; comparar y proyectar consecuencias.
5) Decidir: N11/N13/N14 — recomendaciones y decisiones HITL autorizadas con auditoría. No usurpar aprobación humana.
6) Presentar y seguir: N16/N17 + servicios — estado y versiones, dashboard, alertas, informe, seguimiento y reanálisis incremental por eventos.
La persistencia es transversal a todas las etapas; no una única llamada final a N17.

## 3. Realidad actual verificada en release/core-candidate-20261108
`apps/api/src/analysis/adapters/graph/workflow.py` registra nodos N1->N2->N3->[N4 risk, N5 wbs, N9 budget]->N12; la crítica deriva a retry/HITL/dispatch; dispatch paraleliza N6->N7, N8 y N15; fan-in N10->N11->N17->N16.
N3 actual: contract->N4, budget->N9, schedule/specification/technical_spec/drawing->N5, other->N4. No es verdadero análisis multi-disciplinar: un único documento puede contener obligaciones, hitos, presupuesto y requisitos.
`apps/api/src/analysis/adapters/ai/tools/risk_extraction_tool.py` N4 llama proveedor con prompt largo y JSON monolítico; strict_completeness y normalización; tiene retorno [] que exige desambiguar «sin riesgos» de extracción fallida y evidencia de cobertura.
`apps/api/src/analysis/adapters/graph/schema.py` conserva estado de documento dentro de ProjectState; ADR-014 plantea agregado de proyecto con entidades tipadas y eventos. ADR-017 plantea Tier-1 DocumentGraph por documento y Tier-2 ProjectGraph asíncrono por proyecto. Evitar duplicar grafo o confundir N8 con Tier-2.
PR #1234 (draft) implementa provider externo opt-in OpenAI/Gemini transport AIRequest->AIResponse, reservado por solicitud, sin reintento, strict JSON largo. Anthropic predeterminado. No fusionado al piloto.
Evidencia 16/11: Gemini CLI OAuth sobre 4 cláusulas auténticas de SolarMax: 12 candidatos, 12/12 snippets literales, no benchmark de todo contrato. GPT-6 Sol con N4 original: 0 riesgos (FAIL semántico); con prompt conciso y mismo esquema N4: salida incompleta al límite 6.000 (FAIL). No comparabilidad plena por esquemas distintos.
El Complete Journey de Railway sigue pendiente de candidato genuino legible por HITL, acto humano real y pending->projected (#1229), aunque otros tests/proveedor Sonnet hayan pasado en entornos aislados. Nunca confundir test, desarrollo, staging y piloto.

## 4. Funciones N1–N17 objetivo (no necesariamente ejecución serial)
- N1: ingesta binaria, MIME, hashing, páginas/hojas, metadatos, revisiones, preservación exacta original, OCR y marcas de segmentos ilegibles; nada de truncar silenciosamente.
- N2: privacidad/PII y políticas de exposición por proveedor; correspondencia segura fuente original/representación enviada; fail closed en seguridad.
- N3: planificador de análisis multidisciplinar; selección de herramientas y especializaciones por contenido/elemento, no exclusivamente por tipo documental ni una llamada LLM obligatoria.
- N4: investigador agéntico de obligaciones, contradicciones, riesgos y oportunidades; ver §5.
- N5: WBS/actividades/hitos/dependencias/baselines; cálculos de fechas/CPM ejecutados por utilidades exactas y no por generación libre. WBS es útil en EPC pero NO obligatoria en cualquier metodología/proyecto.
- N6: stakeholders/entidades identificables y su fuente.
- N7: RACI y autorizaciones; no inventar responsabilidad ausente; ejecución condicional.
- N8: Coherence Score evidence-backed, separado para datos validados vs pendientes; no evaluarse como sustituto del cross-doc ProjectGraph.
- N9: BOQ/budget cost items, hojas/celdas/totales/unidades/monedas/baseline, cálculos exactos; IA solo para desambiguar correspondencia y anomalías semánticas.
- N10: vínculos semánticos y knowledge graph; evitar duplicación con entidad canónica ProjectState y ProjectGraph.
- N11: paquetes de decisión con alternativas, pros/contras, impacto/limitaciones, no ejecutar cambios sin autoridad.
- N12: crítica de omisiones/pertinencia/falsos negativos con cobertura e inventario; inspección focalizada en vez de repetir todo siempre.
- N13/N14: interrupción, revisión per-finding y final; persistencia/continuación ligadas a candidato/revisión/identidad, atomicidad y tenant.
- N15: localización literal de evidencia/citas con revisión, página/spans/celdas, anclaje original; validación de números/unidades/fechas cuando sea posible.
- N16: ensamblado de vistas y reportes desde artefactos existentes; sin regenerar LLM por defecto.
- N17: persistencia (además de checkpoints transversales) con transacciones, idempotencia, lineage y versionado.
No introducir nuevos N numéricos sin necesidad: requisitos técnicos puede ser especialista registrado bajo interfaz común.

## 5. N4 V2 — máquina de investigación incremental dentro del nodo público N4
Mantener el nombre/contrato externo `risk_extractor` (adaptador compatible) inicialmente. Suboperaciones NO implican seis nodos ni seis llamadas:
A) PLAN: leer inventario de secciones, nivel de cobertura, referencias, presupuesto restante, preguntas abiertas; si documento simple, plan y extracción pueden compartir llamada.
B) INVESTIGATE: el modelo lee unidades de contexto completas, incluye carve-outs/excepciones, consulta texto y referencias cruzadas con herramientas específicas. Nunca descarta material por palabras clave, ranking o top-20. Si el contexto rebasa ventana del proveedor, recorrer ventanas exhaustivas consecutivas con solapes controlados y registro de cobertura.
C) EMIT: registrar hallazgos compactos con id estable, `document_revision_id`, provenance span/ref, categoría/propuesta, título e hipótesis; citas largas y contexto permanecen en almacén de evidencia, no repetidos en cada respuesta. Emitir mediante evento/herramienta o lote pequeño validable; no esperar JSON gigante.
D) CROSSCHECK: contrastar cláusula, excepción, contradicción, anexos y hallazgos previos; deduplicar con relación de equivalencia y procedencia intacta; marcar cuestiones no resueltas.
E) EVALUATE: distinguir fuente literal (hecho) vs interpretación vs probabilidad/impacto vs mitigación vs incertidumbre. No estimar probabilidades cuantitativas sin base. Vincular con actividades, costes y requisitos si hay evidencia; nunca fabricar.
F) CONSOLIDATE: cobertura de cada sección (`examined`, `unreadable`, `pending`, `missing_external`, `not_applicable`), hallazgos y estado `complete|partial|blocked|failed|pending_review`; integración con candidatos tipados y N12/HITL.
Checkpoints consistentes por trabajo/call: `tenant_id, project_id, document_id, revision_id, analysis_run_id, provider, model, prompt_version, source_hash, coverage_cursor, budget_spent, seen_finding_ids, pending_refs, errors, fencing_token`. Persistencia CAS/idempotente: retries no generan hallazgos duplicados ni reejecutan efectos. Un checkpoint no equivale a confianza ni aprobación.
Herramientas inicialmente mínimas: `get_document_sections`, `read_source_span`, `resolve_cross_reference`, `list_current_findings`, `propose_finding`, `mark_coverage`. Definir controles fuente/tenant/permisos. Adiciones posteriores deben justificarse.
No permitir que un LLM redacte manualmente toda la evidencia para producir respuesta monolítica. La IA decide investigación/semántica; un adaptador guarda artefactos parciales con referencias verificables. Datos parciales quedan en store provisional; proyección a ProjectState final solo después de integridad, calidad y controles HITL.
Nunca usar `risks=[]` como `success` sin prueba de cobertura y crítica independiente; un documento puede genuinamente carecer de riesgos, y ello no debe etiquetarse FAIL sin evidencia.
No invocar modelos para tareas deterministas (sumas, plazos calendarios, hash, búsqueda literal, permisos).

## 6. Adapters multiproveedor
N4 llama abstracción de proveedor `AIRequest->AIResponse` (evolucionable a contrato de tools y respuesta incremental). Claude baseline; OpenAI/Gemini opt-in y misma calidad/evidencia/cobertura, con serialización particular de tool calls/JSON si procede.
Per provider se gobierna tokens y coste incluyendo razonamiento invisible, llamadas incompletas, tokens facturables, preflight y límites transaccionales por ejecución/documento/proyecto/tenant. Compatibilidad con privacidad y errores tipados, no reintentos automáticos ilimitados.
Benchmark justo: mismo extracto+hash, misma ontología de hallazgos, iguales herramientas, tiempo y presupuesto comparables, varios seeds/ejecuciones; proveedor diferente no garantiza misma respuesta ni factura por CLI OAuth.

## 7. Control de coste, latencia, autonomía
- Arquitectura 6 etapas no significa 6 llamadas IA; N1/N2/N15/N17 suelen funcionar sin LLM.
- Bypass de LLM si fuente estructurada puede parsearse exactamente; N3 no debe hacer una consulta LLM por defecto.
- Reutilizar análisis cuando hash+versión+alcance+prompt/política son compatibles; evaluación diferencial al cambiar solo un documento.
- Ejecutar especialistas de fuentes distintas en paralelo solo si evita colisiones, manteniendo límites de concurrencia y coste por tenant.
- N12 inspección focal en dudas; escalado de modelos de calidad solo ante incertidumbre real; contraejemplos complejos se revisan más a fondo.
- 3 modos UI: RÁPIDO=triage explícitamente preliminar y no declara ausencia global de riesgo; COMPLETO=default, cobertura íntegra del material disponible, análisis incremental y proyecto; AUDITORÍA=verificación reforzada / segunda opinión selectiva y aprobación de gasto cuando proceda.
- Límite por request, ejecución, documento, proyecto y tenant; cuando se agota pausa con checkpoint y estado PARTIAL/BLOCKED, nunca vacía en éxito. Trazas proveedor/modelo/prompt/tokens razonamiento/coste/latencia/errores/cobertura, sin exponer PII/secrets.
- No insertar etapas nuevas sin necesidad de valor o prueba; revisar latencia p50/p95, coste por documento y hallazgo correcto, calidad de omisiones, CPU y tool calls.

## 8. Proyecto unificado, fuentes y seguridad
ADR-014 ProjectState agregado temporal, no inmóvil: versiones/Events/Snapshots y entidades Obligation, Requirement, Activity, BudgetItem, Risk, Evidence, Change, Review, Alert/Action. No forzar semántica EPC (BOQ/FAT/WBS) sobre desarrollo software: usar núcleo tipado mínimo, plugins/especializaciones posteriores.
ADR-017 Tier-1 DocumentGraph procesa por fuente; Tier-2 ProjectGraph corre asíncronamente tras cambios genuinos, alinea entidades cross-doc, evalúa conflictos y deltas/Health/Score/Alert, mantiene versiones, notifica progreso. HITL final en principal autoridad humana, no por test automatizado.
Estados: OBSERVED (fuente), PROPOSED (IA), VERIFIED_EVIDENCE (cita), REVIEW_PENDING, TRUSTED/HUMAN_APPROVED según semántica canónica. Aceptar riesgo no implica que disminuya severidad; Coherence Score validada/provisional distintas. No bypass por «aprobado» de documento sin línea base aplicable.
Ejemplo: obligación de entrega contractual X; fecha plan Y; BOQ sin FAT; requisito FAT en especificación. ProjectGraph vincula objetos, verifica si fechas/baselines son comparables, señala discrepancia o NOT_ASSESSED, no inventa relación ni coste.

## 9. WBS de ejecución propuesto (secuencial por puertas, desarrollo acotado)
F0 diagnóstico con mapa exacto de nodos existentes y contratos de estado; identificar duplicaciones, consumidores y compatibilidad N12/HITL, ProjectGraph, #1229.
F1 inventario de entrada/cobertura y ledger de hallazgos provisional, idempotencia/lineage/fencing y privacidad (migraciones mínimas).
F2 orquestador N4 interno: lectura, tools, emisión incremental, checkpoint/reanudación, presupuestos multinivel. Mantener N4 API.
F3 adapters Claude/OpenAI/Gemini + benchmark comparable sobre extracto real SolarMax de cuatro cláusulas (cita verdadera ≠ interpretación correcta).
F4 ampliar patrón común a N5/N9 y requisitos técnicos, con parsers estructurados y aristas cross-doc.
F5 N12/N15 de calidad y referencia gold con experto, falsos negativos, FPR, precisión/recall, cobertura, confidencialidad, coste, 3 modos.
F6 Tier-2 ProjectGraph / Coherence / Health / alertas y perspectiva temporal, actualizar solo entidades afectadas.
F7 HITL UX, análisis y decisiones con evidencia navegable; no suplantar aprobación humana.
F8 UAT integral con contrato, cronograma, presupuesto, especificaciones reales y journeys S1-S8; repetibilidad 3 runs, evidencia y GO.
Evitar desarrollar todas las fases en paralelo; PR pequeñas, feature flags, rollout gradual con rollback y diagnóstico de coste/latencia.
**Bloqueo concurrente:** #1229 Complete Journey pilot, NO-GO y responsabilidad del Tándem CORE; NO reupload ni SQL seed; no interferir durante revisión.

## 10. Pruebas mínimas y aceptación
Criterios objetivos propuestos para consensuar con QA: 100% de citas aceptadas literales y localizables por revisión; 100% de secciones de fuente disponible con estado de cobertura explícito; 100% de riesgos críticos del gold set detectados, >=90% recall de riesgos materiales y >=90% precision (sujetos a calibración con expertos), variación/repetibilidad medida, 0 silencios ante error parcial, coste correctamente atribuido de 100% de llamadas, 0 accesos cross-tenant, reanudación sin duplicados, contrato multifuente real y decisión humana HITL.
Pruebas de fallo: corte de proveedor en mitad de llamada, 0 riesgos, respuesta incompleta, referencia a anexo ausente, PDF escaneado, reupload misma revisión, cambio de versión durante procesamiento, race/fence, model swap, budget exhausted, permisos, extracción sin cláusula de excepción, normalizador inválido.
No confundir unit tests, synthetics, OAuth CLI con UAT en Railway. Requerir logs de llamadas reales, hashes/versiones, contrato, métricas quality+cost, ledger PG, fuentes clicables, walkthrough UX.

## 11. Preguntas para revisión crítica de Claude
1. ¿Esta arquitectura minimiza realmente llamadas/coste y latencia, o añade redundancias? Detectar nodos a fusionar/preservar, con razones y coste.
2. ¿Es consistente con `workflow.py`, `nodes.py`, `schema.py`, N4 real, ADR-014 y ADR-017? Señalar conflictos concretos con fichero/línea y cambios mínimos.
3. ¿Cómo introducir `finding-ledger` incremental preservando CAS, HITL y compatibilidad de `DocumentArtifact` sin migración riesgosa?
4. ¿Qué contraejemplos demuestran que N4 no será exhaustivo? Diseño eficiente de medición de cobertura, omisión y false-negative.
5. ¿Cómo se resuelve proveedor-neutral tool calling y N12 critique sin aumento exponencial de prompts/tokens?
6. ¿Qué es lo más pequeño que hay que implementar para demostrar valor real primero? Qué NO hacer todavía.
7. ¿Cómo garantizar integridad de parsing PDF/XLSX/cronograma y cross-doc, sin trasladar a N4 tareas de N5/N9?
8. ¿Cómo implementaría los 3 modos de análisis manteniendo coste, seguridad, semántica de resultados y operatividad?
9. Proponer ADR/SDD/PR plan concreto con dependencias, riesgos, migraciones, endpoints, estado, rollback y aceptación.
10. Veredicto GO/GO-CON-CONDICIONES/NO-GO para implementar; diferenciar pruebas disponibles de inferencias.

**Instrucción al revisor:** hacer análisis independiente y crítico, con referencias al código real. NO modificar archivos del repositorio, NO commits, NO PR, NO despliegues, NO llamadas pagadas a modelos desde el propio C2Pro y NO tocar el piloto. Entregar dictamen legible y lista priorizada de cambios, identificando incertidumbres.
