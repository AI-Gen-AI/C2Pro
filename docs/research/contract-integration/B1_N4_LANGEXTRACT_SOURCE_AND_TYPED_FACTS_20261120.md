# B1 — N4 actual vs LangExtract: alineación de evidencias + preparación de hechos EPC tipados

**Fecha:** 20/11/2026. **Dictamen:** PASS_LIMITED para alineación de citas **sin LLM**. NO-GO para afirmar mejora de análisis contractual, activar LangExtract o reemplazar N4.

> **Actualización posterior, 20/11/2026:** se completó un **único smoke generativo Gemini** sobre la §2.5.5 pública y su JSON se validó con N4 v2: **5 candidatos, 5/5 citas exactas, 1 referencia a anexo pendiente y ninguna obligación emitida con tipo individual `obligation`**. No fue un ensayo directo N4 vs LangExtract ni una evaluación semántica exhaustiva. Ver [B1B_REAL_GEMINI_TYPED_EPC_CLAUSE_20261120.md](B1B_REAL_GEMINI_TYPED_EPC_CLAUSE_20261120.md). El apartado B1b inferior sigue describiendo el benchmark comparativo completo pendiente.

## Fuente y versiones

- Mismo texto emitido por `PDFFileParser` de C2Pro en SHA `916808c5212e3dbc652407f35f3a17557623c06c` sobre PDF público SEC de Longfellow generado localmente a partir del HTML SEC: **227.313 caracteres**, 22 ventanas planificadas por `n4_source_windows.py` (12.000 caracteres de contexto/400 de solapamiento). No es el PDF original firmado ni la UAT.
- Validador N4 de esa SHA: `parse_n4_window_output` y su coincidencia literal `EXACT_MODEL_SAFE_MATCH`.
- LangExtract **v1.7.1**, función real `resolver.Resolver().align`, modo estricto y modo con alineación flexible. Instalado en nuevo entorno `.venv-langextract` del PC; no se usaron claves, inferencia ni facturación.
- Harness: `apps/api/tests/integration/b1_langextract_n4_offline_grounding.py`.
- Evidencia JSON (sin reproducir contrato): `docs/research/contract-integration/evidence/B1_LANGEXTRACT_N4_OFFLINE_GROUNDING.json`.

## Experimento ejecutado

Cuatro citas semilla asociadas a los patrones textuales 2.5.5, 9.6, 4.3.1 y 13 del PDF público. **Esas coincidencias no garantizan por sí solas que la cita corresponda al cuerpo operativo de una cláusula: pueden provenir de índice, referencias cruzadas u otros apartados.** Este ensayo es exclusivamente de posicionamiento literal, no de contenido jurídico. Cada cita es **literal completa con límites de palabra y aparición única en todo el texto de 74 páginas**. Se inyectaron tres variantes por muestra (12 salidas controladas), **no generadas por modelo**.

| Candidato | N4 actual (literal) | LangExtract estricto | LangExtract flexible |
|---|---:|---:|---:|
| Literal exacta (4) | 4/4 con span esperado | 4/4 con span esperado | 4/4 exactas |
| Texto deliberadamente alterado (4) | 0 spans certificados | 0 spans exactos | 4/4 alineados como MATCH_LESSER, **0/4 verbatim** |
| Texto inventado (4) | 0 spans certificados | 0 spans exactos | 0 spans |

**Conclusión acotada:** no se ha demostrado valor añadido de LangExtract para **coincidencia literal**, porque la función presente en N4 ya lo hace; sí se evidencia que el modo aproximado puede devolver un span cuyo texto **no es idéntico** al declarado. Nunca traducir un `MATCH_LESSER` a `EXACT_MODEL_SAFE_MATCH` o cita de PDF certificada.

**Corrección de método importante:** el primer intento cortaba citas artificialmente tras 95 caracteres, partiendo palabras; eso producía diferencias espurias contra el alineador basado en tokens. Se corrigió antes de publicar el resultado final; también se corrigieron los límites regex de numeración y se exigió unicidad documental global, según hallazgos QA de Gemini job `a09f9a0a75dfba7caff9d06fa3971116` (dictamen PASS_LIMITED sobre la versión previa). La ejecución final se repitió y mantuvo sus métricas. Ese dictamen anterior **no equivale a QA independiente del último commit**.

## Avance de contrato N4 v2 (experimental y separado de la UAT)

Nuevo código: `apps/api/src/analysis/domain/n4_typed_fact_v2_candidate.py`.
- Naturaleza del hecho (`entity_type`) es ortogonal a `dimensions`. Valores: obligación, derecho, condición, evento, hito, importe, referencia e hipótesis de riesgo; dimensiones `LEGAL, SCOPE, TIME, BUDGET, QUALITY, TECHNICAL`.
- Citas de fuente contra **proyección N2 del texto**, con estado `EXACT_MODEL_SAFE_MATCH`, ausente, no localizado o repetido/ambiguo. Nunca declarar original PDF verificado por coincidencia textual.
- Conserva un candidato sin literalidad verificable como `PROPOSED_UNVALIDATED`; factos verificables no se borran si faltan anexos. La razón de riesgo es interpretación separada de un hecho extraído.
- **8/8 pruebas unitarias PASS** en entorno aislado, usando respuestas sintéticas. **No se ha invocado N4 v2 como modelo**, tampoco N12, ProjectGraph, Score, HITL ni alertas. No se ha cambiado la PR #1276.

## Qué queda bloqueado / siguiente experimento de alto valor

**B1b/B2 no completado:** se precisa una ejecución de inferencia real bajo **mismo modelo, corpus, presupuesto, ventanas, límite de salida y oráculo held-out** para medir:
- cobertura de obligaciones, derechos, condiciones, hitos, importes y riesgos de cláusulas críticas;
- falsos positivos, citas/verbatim, comprobación de página física y referencias a anexos `REFERENCED_MISSING`;
- JSON inválido, riesgos truncados, coste por 100 páginas y decisión de revisión N12 independiente.

El esquema tipado **NO** será un segundo motor. A lo sumo es una respuesta propuesta para N4 existente; debe reconciliarse con los tipos y el contrato de gasto/autoridad de #1276 antes de cualquier llamada facturable o despliegue. El oráculo del contrato SEC público no equivale a certificación jurídico-contratual sin revisión humana. No atribuir calidad o bajo coste a ningún modelo sin una ejecución.

**Decisión:** mantener N4 y el parser actual como baseline; Docling sidecar `ADVISORY_UNVERIFIED`; LangExtract en evaluación solo como estrategia de extracción futura si **demuestra mayor recall semántico** manteniendo fidelidad y coste. OpenContracts/ERPNext/IfcOpenShell/MCP permanecen pausados.
