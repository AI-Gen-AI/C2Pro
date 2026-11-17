# C2Pro V4 — Frente A: arquitectura, contratos y decisión G0 (WBS 0.2 / 0.5)

**Checkpoint canónico:** [#1049 comentario 6930932354](https://github.com/AI-Gen-AI/C2Pro/issues/1049#issuecomment-6930932354)  
**Plan:** C2Pro V4 WBS FAST-TRACK V4.1; objetivo G0 17/11/2026, G1 18/11/2026.  
**CORE de inspección:** `release/core-candidate-20261108` @ `5af16eed1d3087f8e081cdc5caa567f726ca6a9e`.  
**Candidato S1 integrado, NO en CORE:** PR [#1241](https://github.com/AI-Gen-AI/C2Pro/pull/1241) @ `971b60ce81d97e8c6c7f33d6a5155a887a71f267` (N3+N4+N15-preHITL+N12 focal).  
**Estado:** SDD de contraste para el gate, **no acta de promoción**. Ni aprobación jurídica de gold, ni UAT real; no tocar piloto [#1229](https://github.com/AI-Gen-AI/C2Pro/issues/1229), migraciones, DB ledger o WBS 2.2/2.5/2.6.

## 0. Autoridad de cambios y no solapamiento
- **Frente A:** `workflow.py`, `nodes.py`, `schema.py`, `critique_extraction_use_case.py`, `ai_extraction.py`, adaptadores de proveedores y tests correspondientes; S0/S1, G0/G1, QA independiente. *NO MERGE/DEPLOY automático* según #1049.
- **Frente B:** ventanas/ledger PostgreSQL, RLS, CAS, checkpoints y presupuesto transaccional; sólo contratos, sin edición desde A.
- **Tándem CORE:** Railway, #1229, candidatos y validación humana genuina. Frente A se abstiene de realizar su ingestión o de aprobar en su nombre.
- Revisión independiente: el autor nunca es su propio árbitro; un modelo opinando sin ejecutar tests/integración no certifica G1.

## 1. Grafo actual y puntos de responsabilidad
`apps/api/src/analysis/adapters/graph/workflow.py:202` define N1→N2→N3→(N4|N5|N9)→N12→(retry|N13/N14|enrichment), N6→N7 / N8 / N15→N10→N11→N17→N16. No todos los nodos llaman IA; el grafo de documento **no equivale** al ProjectGraph Tier-2.

| Nodo/frontera | Punto de código inspeccionado (ruta bajo `apps/api/`) | Contrato y pendiente |
|---|---|---|
| N1 ingestión | `src/analysis/adapters/graph/nodes_extended.py:216` + worker upstream | La ausencia de texto es precondición fallida, no extracción vacía; OCR/status upstream **no cerrados** por #1235 |
| N2 PII | `src/analysis/adapters/graph/nodes_extended.py:256` | Envío IA debe usar proyección segura; map original↔sanitizado aún requiere evidencia comprobable |
| N3 router | `src/analysis/adapters/graph/nodes.py:259`, `workflow.py:202` | #1235 agrega ruta terminal `insufficient_extractable_text` evitando KeyError, sin llamar N4/HITL |
| N4 riesgos | `src/analysis/adapters/graph/nodes.py:296`, `src/analysis/adapters/ai/tools/risk_extraction_tool.py:238` | #1237: JSON inválido=FAILED; `risks=[]` válido pero NO_FINDINGS_UNASSESSED, confidence null. No declarar cobertura global sin ledger |
| N5 WBS | `src/analysis/adapters/graph/nodes.py:514` | Referencias WBS técnicas no sustituyen materialidad ni citas originales |
| N9 budget | `src/analysis/adapters/graph/nodes_extended.py:757` | Diferenciar lectura XLSX estructurada de evaluación semántica IA |
| N12 crítica | `src/analysis/adapters/graph/nodes.py:605`; `src/analysis/application/critique_extraction_use_case.py:117,192`; `src/analysis/domain/ai_extraction.py:89` | #1240: primera pasada conserva fuente N2 completa; repeticiones sólo excerpt local con quote rastreable o abstenerse. Resultado focal siempre UNASSESSED+HITL. Coste real sin medir |
| N13/N14 HITL | `src/analysis/adapters/graph/nodes.py:842` | La revisión humana exige vínculo al candidato exacto; NO-GO para aprobaciones simuladas |
| N15 citas | `src/analysis/adapters/graph/nodes_extended.py:907` y #1238 `nodes.py:409` | Pre-HITL verifica literal **en proyección N2**, nunca es autenticidad PDF original; posterior N15 mantiene función propia |
| N6/N7/N8 | `src/analysis/adapters/graph/nodes_extended.py:297,355,407` | Enriquecimiento y Coherence provisional/validada; no agregar confianza por falta de datos |
| N10/N11/N17/N16 | `nodes_extended.py:796,866,963`; `nodes.py:1130` | Tier-1 produce/guarda artefactos; Tier-2 ProjectGraph separado asíncrono, sin equivaler a integración validada |

## 2. Contratos innegociables S0→S1→Frente B

1. **Entrada / fuente**: `tenant_id`, `project_id`, `document_id`, `revision_id`, fuente original por hash, proyección segura N2 y distinción explícita de unidades ilegibles/faltantes. Una longitud de texto >0 no acredita cobertura.
2. **Extracción N4**: estados independientes `FAILED` (proveedor/parse), `NO_FINDINGS_UNASSESSED` (JSON válido vacío), `FINDINGS_PROPOSED` (candidatos), y futuros `PARTIAL/COMPLETE` anclados a cobertura de cada SourceUnit, NO a respuesta JSON sola. Nunca reinterpretar excepción como 0 riesgos.
3. **Evidencia**: conservar `source_quote`, `clause_ref`, alcance N2 vs original, estado VERIFICADO_SANITIZADO/NO_VERIFICADO; cita literal ≠ interpretación legal demostrada; no pasar automáticamente a TRUSTED.
4. **Crítica**: N12 primera pasada sobre N2 completa mientras haya capacidad y presupuesto; una segunda revisión focal no certifica omisiones fuera del fragmento; `UNASSESSED` obliga humana. Finite retries, coste billable no cero ante timeout desconocido.
5. **HITL**: `PROPOSED ≠ TRUSTED`, decisión vinculada a candidato/revisión/identidad, rechazo no puede entrar en persistencia canónica. No anular revisión por confidence agregada. `citation_validation_passed` basado en N2 debe presentarse únicamente como tal y revisarse en integraciones de N15/N17.
6. **Frontera B / SDD**: contratos propuestos SourceUnit/ExtractionRun/Window/Finding/Coverage; ledger transaccional, CAS+fencing reutilizando `processing_authority`, tenant RLS, idempotencia, reconciliación de tokens/razonamiento. El diseño no habilita modificaciones a tablas/migraciones por Frente A.
7. **Rollback**: mantener flags alternativos OFF, cambios de código aislados, revertir funcionalidad sin degradar lineage; desplegar y fusionar requiere revisión CORE y gates. No utilizar el piloto para probar hipótesis.

**Compatibilidad arquitectónica:** [ADR-014](https://github.com/AI-Gen-AI/C2Pro/blob/release/core-candidate-20261108/docs/architecture/decisions/ADR-014-project-state-model.md) fija ProjectState como raíz y la revisión como evidencia; ADR-017 define el corte Tier-1/Tier-2. No forzar WBS/BOQ como núcleo universal en vertical software.

## 3. Registro de cambios y controles auditables
| WBS | Cambio en PR / SHA | Evidencia conocida | Limitación para DONE |
|---|---|---|---|
| 1.1 | #1235 / `ac4257c147c750b40c2b9e3197220490e36df74c` | Python 3.11 + PG aislado: 45 PASS, job `1b49a5e200c740d9b79f504b` | OCR/estado upstream, revisión adversarial exact-head |
| 1.2 | #1237 / `9e37174ec928eedbaf8c7fc4b402081df19a1cdf` | Python 3.11 + PG aislado: 18 PASS, job `de519b1d4c0d4d5cb34834a7` | Paridad completa API, branch integrado |
| 1.3 | #1238 / `2d24f809012536920466f2fb2d6ec7202235c243` | Python 3.11 + PG aislado: 21 PASS, job `66ecbb50d23247a6be7ef912` | Gold contra original; revisión independiente Gemini sólo de código |
| 1.4 | #1240 / `a9deaca1ab10d12a1bf0fbe646a6e2d4cd645389` | Python 3.11 + PG aislado: 33 PASS, job `66315f0c51bc47b2b05c44e9`; Ruff PASS | Medición de coste/tokens reales, review antagonista y branch integrado |
| 1.5 | #1234 / `f04b1b2ab49c9613af11f4a5d46bbb969182f333` | Adaptadores opt-in, trabajo parcial anterior | Drift Guard FALLA (3 UNKNOWN_BLOCK), revisión de proveedor y benchmark pendientes |
| G1 candidato | #1241 / `971b60ce81d97e8c6c7f33d6a5155a887a71f267` | HEAD combinada en QA aislada, **no CORE** | QA de integración exact SHA, revisión independiente y no fusionado |

## 4. Decisión G0 en términos del WBS
- **0.2 mapa/contratos**: entregado como inventario con puntos reales, requiere challenger independiente.
- **0.3 observabilidad**: instrumentación existente identificada (`src/core/ai/llm_client.py`, `src/core/ai/usage_logger.py`, `src/core/ai/cost_controller.py`); **NO HAY** base real y comparable de p50/p95, tokens reasoning, coste por nodo/proveedor. No inventar.
- **0.4 evaluación abierta («gold» no determinista)**: protocolo y casos ilustrativos de regresión en fichero independiente, **NO motor de reglas ni taxonomía de negocio**. G0 exige metodología de evaluación y diseño de held-out multivertical, **no certificación experta previa de catálogo**. Materialidad y capacidad de generalización aún NO CERTIFICADAS; full SolarMax 94 páginas vs SEC 8 KB no son equivalentes.
- **0.5 SDD**: contrato firmado en coordinación en términos de autoridad, diseño de datos aún sujeto a Frente B y QA de RLS/CAS. No implica migraciones.
- **0.6 piloto**: propietario único Tándem CORE #1229.
- **Criterio de emisión revisado (decisión owner 17/11/2026)**: G0 puede ser `PASS_CONDICIONADO` con procedimiento de evaluación versionado, casos de regresión ilustrativos, diseño de pruebas held-out y responsables, **sin un gold exhaustivo certificado**. El diferimiento de mediciones no críticas requiere constancia expresa; los controles de seguridad, trazabilidad, contratos y fallos reales siguen siendo obligatorios. **No confundir G0 diseño aprobado con capacidad N4 validada**. G1 nunca PASS con PR DRAFT sin HEAD CORE, pruebas de integración y revisión fiable; desempeño semántico y generalización necesitan benchmark posterior.


## 5. Decisión de arquitectura de evaluación, aprobada 17/11/2026

- **Prohibido** usar listas «gold» de cláusulas, palabras clave, importes, tipos de proyecto, severidades esperadas o ejemplos de SolarMax como reglas de generación de riesgos en N4/N12/N15; ninguna categoría futura se debe filtrar por pertenecer o no al benchmark. Tampoco entrenar prompts para superar casos conocidos.
- **Permitido** usar aserciones deterministas **técnicas**: seguridad y aislamiento tenant/PII, control de costes, idempotencia, cobertura de fuente medible, validación de cita literal, estados de error/parcialidad, trazabilidad y HITL. Una cita correcta es condición técnica de evidencia; **no** adjudica por sí sola materialidad.
- **Evaluación diferenciada**: (a) regresión de ejemplos ya conocidos; (b) held-out nuevo, heterogéneo por EPC/ETO y otras verticales; (c) adversarial técnico de errores y evidencia. El juicio experto se aplica a **anotaciones de evaluación**, no a decisiones productivas a codificar.
- **Gate G0**: aprobar metodología, dueños, alcance, separación de muestras y contrato, no «12 de 12 riesgos localizados». **Gate G1 y posteriores**: comprobar fiabilidad operacional y resultados reales, sin inventar recall universal ni bloquear diseño hasta disponer de expertos para todos los contratos.
- **Compatibilidad**: no hay modificación en esta decisión de modelos PG, ledger, migraciones, SourceUnit del Frente B ni UAT de #1229. Las revisiones a WBS 0.4/1.7 deben citar este checkpoint como cambio de criterio, no suplantar autoridad de coordinadores sobre otras ramas.

Este documento especifica fronteras y condiciones comprobables; no autoaprueba el sprint.

## 6. Auditoría de ejecución de política «sin semántica determinista» (17/11/2026)

Se detectó que la política aprobada en #1049 **no estaba plenamente reflejada en la HEAD candidata G1**:
- **N12 `src/analysis/application/critique_extraction_use_case.py`** contenía `_source_consistency_issues`, con expresiones regulares de `Defective work/5.2`, cure period, Client payment y un `RETRY` impuesto por interpretación **contractual**. No es mero cotejo de cita o seguridad. **Corrección propuesta:** PR [#1247](https://github.com/AI-Gen-AI/C2Pro/pull/1247), SHA `4974f2101975a4a48c01ff5e6f2a0d2604769259`, elimina esas reglas semánticas y exige HITL para cada ejecución con riesgos contractuales propuestos, aunque N12 devuelva OK; fuentes/citas y abstención siguen protegidas.
- **N3 `src/analysis/domain/ai_extraction.py`** `_fallback_doc_type` escogía por keywords `contract/budget/schedule/technical_spec` cuando fallaba la clasificación por IA; podía mandar contratos mixtos al especialista equivocado. #1247 sustituye ese acierto presunto por `classification_unassessed`; el grafo conduce a ruta terminal diferenciada, sin N4/N5/N9, riesgos falsos, aprobación simulada o DONE.
- **N4 `src/analysis/adapters/ai/tools/risk_extraction_tool.py`**: las listas `_INCLUDE_KEYWORDS`/`_EXCLUDE_KEYWORDS` son legado de compatibilidad pero **`extract_input_from_state` preserva el texto N2 íntegro**, `filter_relevant=False`, y no aplica top-20 (hint deprecated). Se verificó con texto contractual fuera del léxico EPC. La taxonomía enum rígidos del prompt todavía puede sesgar clasificación: revisar experimentalmente sin convertirlo en hardcode de descubrimiento de riesgos.
- **Pendiente fuera de Frente A**: `src/analysis/domain/document_classification.py` `DocumentCategoryClassifier` asigna categorías de coherencia N1 por palabras clave; **no interviene en N3 clasificador de extracción**, pero puede sesgar N8/score. El equipo del score/Coherence (S4) debe analizar eliminar/aislar este *fallback*, con pruebas de distintos tipos de proyecto y sin inferir materialidad de las etiquetas.
- **Sin cambio a S2/Frente B ni piloto**: N4 ledger/migraciones siguen propiedad B y #1229 propiedad Tándem CORE.

**Evidencia de calidad de PR #1247:**
- RED antes de corrección: cinco pruebas de regresión contra conjeturas por palabras clave y `RETRY` de cláusula específica.
- GREEN local Python3.11: **385/385** en regresión amplia de N3, N4, N12, grafo y HITL, con un único test `test_cross_doc_coherence_aggregates_signals_and_returns_typed_summary` deseleccionado **porque falla idénticamente en SHA base #1241**, sin modificar su criterio de procedencia.
- GREEN en infraestructura AI-GEN Ops, PR #1247 SHA exacto: **180/180** pruebas, PostgreSQL aislado, job `94475154bbde457b919b1c9b`, log SHA256 `a0c3bbd733e1639c21940cca6ce80cc9723e6b9180a8f6b70bd60d4be7ea8f77`. CI Install Drift Guard/Secret Scan SUCCESS.
- **Calidad probada sólo para código/suites mencionadas**: no hay nuevo contrato completo de proveedor vivo ni revisión experta independiente. #1247 es una PR DRAFT apilada sobre #1241, no está en CORE; **G1 permanece sin cerrar**.

**Consecuencia del contrato G0:** la auditoría materializa la regla ya aprobada: seguridad y origen de datos sí tienen validación determinista; semántica del contrato y familias de documentos no. La evidencia de código anterior a la fusión es una propuesta verificable, no una promoción o UAT.


## 7. Checkpoint diferencial de implementación 17/11/2026 — N4 multivertical, N3/N12 y artefactos terminales

**PR:** [#1247](https://github.com/AI-Gen-AI/C2Pro/pull/1247) DRAFT, apilada sobre #1241, HEAD exacta **`e6866afa4183c96f3b2c84036e495d08e1ee7a8f`**. No merge/deploy.

**Correcciones adicionales a lo ya descrito en §6:**
- **N4** `apps/api/src/analysis/adapters/ai/tools/risk_extraction_tool.py`: prompt previo exclusivamente EPC/infraestructura y clasificación prescriptiva de force majeure/termination/LD; ahora inferencia contextual de riesgos en ingeniería, fabricación, servicios, software y proyectos no anticipados. Los códigos `LEGAL/SCHEDULE/QUALITY/SCOPE/TECHNICAL/BUDGET` son **etiquetas de API**, no motor de descubrimiento ni taxonomía exhaustiva de oportunidades de riesgo. No se codifican patrones del Gold. Eliminada restricción **≥80 caracteres** del prompt que podía hacer omitir cláusulas operativas cortas; el cotejo técnico de cita literal real permanece en el verificador de procedencia (`MIN_QUOTE_CHARS=12` como defensa de citas triviales). Identificadores de cita **pueden ser expresos alfanuméricos** como `SLA-A`/`Annex B`, además de numéricos; prohibido inventarlos.
- **N3**: no llamar a N4 por palabras clave ante respuesta desconocida del clasificador; ruta terminal `classification_unassessed` con distinta identidad del caso OCR ilegible.
- **N12**: sin regex de interpretación contractual; no consume retries automáticos con afirmaciones semánticas no probadas y presenta riesgos contractuales propuestos a HITL, incluso si el modelo afirma OK.
- **Frontera de persistencia ADR-017:** se descubrió que el hook `persist_artifact_and_enqueue_project_graph` podría tratar un grafo `workflow_terminated=True` y `human_approval_required=False` como artefacto `TRUSTED`. **Tres tests adversariales RED** antes de parche (clasificación no evaluada, fuente ilegible, rechazo). Corrección en `apps/api/src/analysis/application/document_artifact_completion.py`: tanto hook público como persistencia privada rechazan guardar/encolar estados terminales; validación positiva de candidato no terminal conservada. **31 pruebas focales GREEN**.

**Evidencia exacta:**
- N4 prompt y localizador, 45/45 pytest focales PASS, Ruff y `git diff --check` PASS antes del commit terminal.
- **244/244 pytest PASS** en Python 3.11.16, PostgreSQL privado, **HEAD exacta `e6866afa4183c96f3b2c84036e495d08e1ee7a8f`**, job AI-GEN Ops `0e3fa5a36faa4949aa6576c0`, log SHA256 **`5018447f0e7d7ba59380494842b7868ef91b29392e8875ebf59090b4a671634e`**. Suite N3/N4/N12/prompts/HITL/citas/artifact/ProjectGraph, sin proveedor de pago.
- CI same HEAD: **Secret Scan `43984676758` PASS**, **Install Drift Guard `43984676607` PASS**, **SonarCloud Quality Gate OK** (consulta real).
- Una regresión de `cross_doc_coherence` de **SHA base #1241** permanece fallando también sin el parche: espera ≥4 señales, sólo 2 con evidencia prudente. No modificar Coherence en Frente A.

**Dependencias que deben permanecer visibles en #1049 sin ampliar el alcance:**
1. El sistema N1 `src/analysis/domain/document_classification.py` conserva clasificador por frecuencias de palabras clave para **categorías de Coherence**. Revisión corresponde a S4/N8, no N3; prevenir materialidad basada en etiquetas sin prueba.
2. La ingesta heredada `src/core/tasks/ingestion_tasks.py::_extract_contract_clauses` salta segmentos menores de 40 caracteres y recorta los mayores a 4.000 al crear **Clause** para persistencia, y les asigna `extraction_model=deterministic-contract-ingestion`. Aunque N4 sobre N2-safe conserva su texto fuente y esto **no demuestra truncamiento del prompt N4**, podría limitar relaciones/cobertura de ProjectGraph y merece evaluación por S2/S4 sin cambiar ese módulo desde Frente A.
3. `_run_document_analysis` dispone ya de estado `PARSED_PENDING_ANALYSIS` si falta `analysis_id`, pero nunca sustituye el bloqueo de persistencia de artefactos terminales, corregido aquí.
4. Revisión independiente externa de #1247 sigue **sin dictamen PASS**: Gemini lectura-only acabó por timeout en SHA anterior `4974f210...`; no repetir indefinidamente sin sesión operativa.
5. **No existe benchmark exitoso con proveedor real en esta HEAD**, ni UAT del documento piloto #1229. G0 diseño de evaluación puede considerarse candidatado para aceptación condicionada conforme owner, pero **no aprobado automáticamente**; G1 **NO-GO** para promoción de código hasta QA y evidencia de proveedor/Complete Journey.

**Límites:** nada de modelos/migraciones/ledger WBS2.2/2.5/2.6, ni trabajos del piloto #1229. El presente checkpoint documenta avances del Frente A; no cambia autorizaciones de merge.
