# C2Pro V4 — S0 baseline técnico y acta de arranque
**Fecha:** 2026-11-16, Europa/Madrid. **Versión de referencia:** CORE `5af16eed1d3087f8e081cdc5caa567f726ca6a9e`. **Estado:** evidencia parcial; no equivalencia con mediciones de proveedor/piloto.
**Autorización:** GO del propietario para plan WBS S0–S5, modelos y recursos disponibles, ejecución por PR aisladas con QA antes de merge/deploy.
**Coordinación:** #1049; #1229 sigue siendo autoridad única del piloto; PR #1234 multiproveedor permanece DRAFT y fuera de piloto.

## A. Inventario del grafo y posibles llamadas a IA
Fuente: `apps/api/src/analysis/adapters/graph/workflow.py`, `nodes.py`, `nodes_extended.py`; lectura 16/11 de CORE.
| Nodo | Código/servicio | Proveedor/LLM posible | Primera decisión |
|---|---|---|---|
| N1 ingesta | `document_ingestion_node` + parsing upstream | No obligatorio | medir cobertura y OCR |
| N2 PII | `pii_anonymizer_node` | No obligatorio; detector | preservar mapa fuente/sanitizado |
| N3 clasificación | `ClassifyDocumentUseCase(ai=get_ai_service)` si tipo desconocido | Sí condicional | evitar invocación innecesaria, ruta sin texto |
| N4 riesgos | `get_tool("risk_extraction")` | Sí; posible continuación y retry | principal cuello de coste/JSON |
| N5 WBS | `get_tool("wbs_extraction")` | Sí no-mock | habilitar parser estructurado |
| N9 presupuesto | `ParseBudgetUseCase(ai=get_ai_service)` | Sí en graph, incluso fuente estructurada | parser/cálculo sin LLM primero |
| N12 crítica | `CritiqueExtractionUseCase(ai=get_ai_service)` | Sí no-mock | reintentos focales, evitar reenvío global |
| N13/14 HITL | `human_interrupt_node` | No obligatorio | vinculación candidate/revisión/usuario |
| N6 stakeholders | `ExtractStakeholdersUseCase(ai_provider=get_anthropic_wrapper())` | Sí si tenant | condicionar a utilidad |
| N7 RACI | `GenerateRaciUseCase(ai=get_ai_service)` | Sí si hay WBS/stakeholders | condicionar y medir |
| N8 Coherence | `evaluate_coherence_async` con feature flag `feature_v3_coherence_llm` | Condicional, verificar subgrafo | distinguir score y cobertura |
| N15 citas | `CitationValidatorService` | No obligatorio | mover verificación segura antes de HITL |
| N10 relaciones | `BuildProjectKnowledgeGraphUseCase` | No LLM visible en nodo, verificar módulos | no duplicar ProjectGraph |
| N11 decisiones | `DecisionPackageAssemblyService` | No LLM directo visible | no inventar impactos |
| N17 guardar | `save_to_db_node` | No obligatorio | lineage/fence |
| N16 ensamblar | `final_assembler_node` | No obligatorio | lecturas sin nueva generación |

**Recuento real:** NO MEDIDO todavía: ninguna afirmación de «X llamadas por documento», p50/p95 o €/expediente. Requiere ambiente autorizado, mismo SHA y métricas reales de uso incluyendo reasoning y continuaciones. El recuento de nodos no equivale al de invocaciones.

## B. Topología verificada
N1→N2→N3→[N4 | N5 | N9, elección exclusiva]→N12→[retry | N13/14 | dispatch]→fanout concurrente N6→N7, N8, N15→fan-in N10→N11→N17→N16.
ADR-014 exige ProjectState agregado por proyecto y ADR-017 separa DocumentGraph por fuente de ProjectGraph asíncrono; no declarar que el grafo actual de documento ya cumpla inteligencia cross-doc real.

## C. Primer test RED→GREEN: WBS 1.1
- Base de rama: `5af16eed...`; worktree independiente `/home/aigenadmin/c2pro-v4-s1-n3-route-20261116`.
- Evidencia RED: test async para documento vacío produjo `KeyError: 'insufficient_extractable_text'` desde LangGraph: `router_node` sí emite ese `doc_type`, pero su `path_map` no tenía destino.
- Corrección `ac4257c147c750b40c2b9e3197220490e36df74c`: nodo terminal con `workflow_terminated=True`, `termination_reason=insufficient_extractable_text`, `confidence_score=None`, `NodeResult.SKIPPED`, sin N4/N12/HITL/LLM, y ruta explícita a END.
- Pruebas focales después: **94/94 PASS** (2 nuevos escenarios: cadena vacía y whitespace, y 92 existentes) con Python3.11 venv; `ruff check` y `git diff --check` PASS.
- GitHub PR [#1235](https://github.com/AI-Gen-AI/C2Pro/pull/1235) DRAFT, mergeable; Secret Scan y Install Drift Guard SUCCESS (GHA #43957075502 y #43957075507). NO MERGE/DEPLOY a fecha de este registro.
- Límite explícito: `_analyze_owned` normalmente evita el grafo si `requires_text_analysis` resulta falso por ausencia de texto, por lo que la PR protege otras entradas legítimas al grafo pero **no** soluciona OCR ni acredita estado de ingesta de PDF escaneado. Si se ejecuta el grafo sin `analysis_id`, `decide_document_status` conserva PENDING para las entradas que requieren análisis. Necesario ampliar test de integración ingestión antes del merge.
- Review auxiliar Gemini CLI no ejecutado: sesión VPS carece `GOOGLE_CLOUD_PROJECT(_ID)`, error de autenticación previo a toda revisión. NO contabilizar como QA.
- La plataforma de dispatch Ops read-only no aceptó el `ref` propuesto de PR/sha, así que no produjo revisión ni cambios.

## D. Gold-set de referencia: conjunto de diseño, NO anotación experta aún
Definir identificador fuente+sha+versión, dominio, span exacto, interpretación, obligaciones/excepciones, severidad justificada, etiquetas `risk`, `non-risk`, `ambiguous`, `unassessed`, y reviewer. No fabricar anotaciones de certeza.
Casos semilla a revisar: SolarMax SEC §9.6 «ten percent» frente a «(5%)» (contradicción literal verificable); §14.14.2→§14.15 (enlace cuestionable a verificar); excepción de responsabilidad en ventana posterior; contrato sin riesgos materiales; PDF escaneado o ilegible; anexos faltantes; cronograma contractual vs baseline; presupuesto sin cobertura de requisito FAT. Los cuatro primeros de SolarMax NO demuestran recall general; el corpus 94 páginas es distinto del SEC y no debe mezclarse.
Calibrar gold con Elena y revisión experta real antes de fijar precision/recall o tasas de riesgo «crítico». Separar cobertura de fuente de recuperación semántica de riesgos.

## E. Estado WBS inmediato y bloqueos
| Tarea | Estado evidenciado | Próximo control |
|---|---|---|
| 0.1 alcance/autoridad | DONE | #1049 registrado, plan aprobado |
| 0.2 mapa de N/ProjectGraph | IN PROGRESS | revisar contratos `schema.py` y módulos Tier-2 |
| 0.3 observabilidad/coste | BLOCKED ON BASELINE | configurar corrida de medición autorizada, no atribuir datos inventados |
| 0.4 gold set | IN PROGRESS | anotación experta y muestras completas |
| 0.5 SDD/ADR | PENDING | cierre tras 0.2 y 0.4 |
| 0.6 coordinación #1229 | DONE for planning | piloto sigue NO-GO hasta HITL auténtico |
| 1.1 N3 sin texto | CODE IMPLEMENTED; QA PARTIAL | revisión independiente + ingestión / CI; no merge todavía |
| 1.2 N4 resultados vacíos | PENDING | diseñar estado/ledger sin mutar toda API |
| 1.3 citas antes HITL | PENDING | diseño y tests sobre candidato real |
| 1.4 N12 retry total | PENDING | baseline coste y focalización |
| 1.5 multiproveedor | IN OTHER LANE #1234 | coordinar y no duplicar |

## F. Riesgos y decisiones pendientes
1. La corrección WBS 1.1 termina antes de N17; validar observabilidad y tratamiento status/errores por el worker con test E2E no-mock (sin invocación real del modelo).
2. Posibilidad de daño por introducir N3 fan-out multidisciplinar sin join/reducers y duplicar N12; diferido a S4.
3. Coste acumulado del retry N12 y schema N4: no fusionar #1234 ni activar providers nuevos sin control financiero.
4. Proveedor de QA Gemini en la sesión requiere configuración de proyecto; evitar leer o imprimir secrets y no modificar cuentas.
5. Cualquier rollback y promoción deben respetar HEAD de CORE, candidate binding, aislamiento multitenant y HITL humano real.

**Próxima evidencia:** PR #1235 QA independiente; S0 mapa contratos y gold; S1 N4 estados y citas. No se ha efectuado merge ni deploy de código.
