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
- **0.4 gold**: semilla y protocolo en fichero independiente; cobertura y materialidad experta NO CERTIFICADAS; full SolarMax 94 páginas vs SEC 8 KB no son equivalentes.
- **0.5 SDD**: contrato firmado en coordinación en términos de autoridad, diseño de datos aún sujeto a Frente B y QA de RLS/CAS. No implica migraciones.
- **0.6 piloto**: propietario único Tándem CORE #1229.
- **Criterio de emisión**: G0 `PASS_CONDICIONADO` sólo si equipo/propietario acepta explícitamente diferir métricas no bloqueantes; si baseline, gold o garantía de original se consideran esenciales, **NO-GO**. G1 nunca PASS con PR DRAFT sin HEAD CORE ni evidencias de integración+revisión.

Este documento especifica fronteras y condiciones comprobables; no autoaprueba el sprint.