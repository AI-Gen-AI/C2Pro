# C2Pro V4 — Frente A: gold semilla y línea base de coste/latencia (WBS 0.3 / 0.4 / 1.7)

**Fecha:** 2026-11-16. **Estado:** protocolo y semilla reproducible **PENDIENTE de certificación experta**. Ninguna cifra sintética es factura ni resultado de benchmark real. **Coordinación:** #1049; fuera del piloto #1229.

## 1. Corpus y control de procedencia

| Conjunto | Fuente real | Integridad | Utilidad / límite |
|---|---|---|---|
| G-SEC-EXCERPT-v1 | `apps/api/tests/fixtures/n4_solarmax_critical_excerpt.txt` en PR #1234 @ `f04b1b2ab49c9613af11f4a5d46bbb969182f333` | SHA256 bytes **`5386e0518b932813e25e29484d69095e502942167fd83e8218f5fac6b06190ee`**, tamaño **8.040 bytes** verificados en VPS | Ensayo focal 4+ cláusulas; **NO ES** PDF original completo ni corpus de 94 páginas |
| G-SEC-ORIGINAL | Fuente referenciada SEC: https://www.sec.gov/Archives/edgar/data/1519472/000164033426000032/solarmax_ex991.htm | **PENDIENTE** hash de original autenticado + mapeo byte/página/spans | Solo tras validar y fijar revisión, alinear citas originales y excepción cross-clause |
| G-SOLARMAX-94P | Contrato piloto 94 páginas citado en #1049 | Hash original/revisión **NO OBTENIDOS en este frente** | Pertenece exclusivamente a Tándem CORE; NO REINGESTAR ni mezclar resultados |

La muestra EXCERPT no permite medir recuperación real en contrato completo. Un resultado 4/4 en la semilla no se debe presentar como 100% de recall general.

## 2. Casos gold anotables — expectativas objetivas, no juicio de materialidad

Los textos se contrastaron contra la **fixture** de 8 KB, no contra el documento original. Las clases `CLAUSE_PRESENT`, `TEXTUAL_CONTRADICTION`, `CONDITIONAL_OBLIGATION` son expectativas deterministas verificables; severidad, probabilidad, deducción jurídica y materialidad: `EXPERT_UNASSESSED` hasta revisión humana. La marca de «riesgo» es **candidato**, no referencia de verdad universal.

| ID | Región / patrón fuente | Expectativa de evaluación | Estado de anotación |
|---|---|---|---|
| GC01 | §2.5.5: LD mecánica $5k/día, sustancial $10k/día, final $20k/día; tope `[5] percent ([5] %)` | Extraer obligaciones condicionadas, tasas y tope con cita literal y excepciones; rechazo a «penalidad diaria sin límite» | Texto localizado en fixture; interpretación **pendiente** |
| GC02 | §2.5.5: excepción por retrasos atribuibles a Substation/Owner/Utility, y devolución LD si Final Completion puntual | Vincular condiciones/excepciones, evitar falso positivo de obligación absoluta | Texto localizado; experto pendiente |
| GC03 | §4.3.1 Outside NTP: plazo `[ten (10)] Days`, terminación y LD a cargo de Owner | Respetar rol Owner vs Contractor y condiciones, no reasignar penalización | Texto localizado; experto pendiente |
| GC04 | §9.6 indemnización de conveniencia `ten percent (5%)` | Identificar **inconsistencia literal numérico-palabra** y mantener ambos tokens en evidencia; no inventar porcentaje resuelto | Contradicción textual verificable; materialidad pendiente |
| GC05 | §9.6 pagos trabajo completado, demovilización con cap y materiales no reutilizables | Registrar excepciones y límites acumulativos; no interpretar pago parcial como pago total indiscriminado | Texto localizado; experto pendiente |
| GC06 | §14.14.2 y referencia potencial a §14.15 | Revisar proximidad y existencia real del destino; **NO** etiquetar referencia errónea sin comprobar contrato íntegro | Pendiente contrastar original |
| GN01 | Texto sin cláusula de riesgo contractualmente material, bien formado | `risks: []` válido ≠ hallazgo «sin riesgos»: `NO_FINDINGS_UNASSESSED` hasta cobertura independiente | Fixture sintética negativa, no benchmark semántico |
| GN02 | Proveedor devuelve `{"message":"no risks"}` sin array explícito | `FAILED/SCHEMA_INVALID`, jamás cero hallazgos | Regresión técnica automatizada #1237 |
| GN03 | Texto vacío/espacios, PDF sólo imagen sin OCR | Ruta terminal N3 sin N4/HITL ni falso análisis COMPLETED; OCR pendiente | Regresión técnica #1235 |
| GN04 | Cita «cosida» de dos cláusulas, o texto previo a anonimización no presente en N2 | Pre-HITL no presenta `source_quote` inventada como evidencia, revisión humana | Regresión técnica #1238 |
| GN05 | Excepción o anexo fuera de excerpt; cita solo en otra revisión | `MISSING_EXTERNAL/UNASSESSED` y no `COMPLETE`, lineage revisión | Diseño, todavía sin test E2E real |
| GN06 | N12 repetida, cita no localizable | No nueva llamada full-source y `UNASSESSED` con HITL | Regresión técnica #1240 |

**Protocolo de anotación:** dos revisores independientes marcan para cada obligación: `document_id/revision_id/source_sha256/locator/start/end/quote_exact/semantic_claim/materiality/label/reviewer/time`. Acuerdos y disensos explícitos, reviewer experto de contratos distinto del evaluador/modelo; positivos y negativos, incluyendo excepciones. Las discrepancias no se «resuelven» mediante mayoría de LLM sin evidencia.

**Métricas separadas:** cobertura literal = unidades efectivamente examinadas / unidades disponibles (con estados para ilegibles); citation_precision = citas correctas/emitidas; hallazgos obligatorios extraídos y recall/precision sólo frente a gold experto acordado; FPs con cláusula citada pero significado erróneo; variantes de coste y tiempo. No penalizar como 0 lo que está UNASSESSED.

## 3. Baseline coste/latencia (NO MEDIDA AÚN)
Los componentes de observabilidad detectados son `apps/api/src/core/ai/llm_client.py` (tokens, coste, continuaciones), `src/core/ai/usage_logger.py` / `models.py` (AIUsageLogORM), `src/core/ai/cost_controller.py` (estimación de tarifa) y N4 `src/analysis/adapters/ai/tools/risk_extraction_tool.py`. Una tabla de precio o una medición de latencia de un test mock **no** demuestra factura del proveedor.

### Registro obligatorio por invocación real
`run_id, tenant, revision/source_hash, node, model/provider, prompt/schema_version, mode, attempt_id, calls, status/error_kind, input_tokens, output_tokens, reasoning_tokens (si API informa), cache_tokens, billed_usd, estimated_usd, time_to_first_token_ms, elapsed_ms, completion/finish_reason, retries, source_length_chars, billed_unknown`. Nunca persistir texto fuente, API keys ni contenido de PII en logs exportados. No consultar datos del piloto #1229 sin autorización de su dueño.

### Método para fijar baseline reproducible
1. Seleccionar fuente única versionada (hash de fixture o original autorizado), modelo y endpoint realmente disponibles, flags y parámetros declarados; ejecutar ensayos con el **mismo input**, sin habilitar nuevas rutas productivas.
2. Registrar recibos auténticos del proveedor, incluida diferencia entre estimado/reservado/facturado. Si no hay recibo: `BILLED_UNKNOWN`, nunca «0 €».
3. De al menos tres corridas comparables (y más si se pretende p95 estadísticamente útil), publicar `calls/attempts`, `€ / documento`, `€ / hallazgo validado` cuando haya gold, p50/p95 **con n y método**; sin muestras suficientes p95 = NO_ESTIMABLE.
4. Probar N12 primer paso full vs segundo focal con los mismos spans, medir ahorro de input tokens y consecuencias de omisiones; el ratio de caracteres no es equivalente a coste de tokens.
5. Evaluar Anthropic default contra Gemini/OpenAI sólo tras resolver [#1234](https://github.com/AI-Gen-AI/C2Pro/pull/1234) Install Drift Guard y equivalencia de formatos/finish_reason/reasoning, sin activar en Railway.

### Tabla de baseline actual — declaración honesta
| Indicador | Valor verificable 16/11 | Cobertura |
|---|---|---|
| Coste real € por run/nodo/modelo | **NO MEDIDO** | Requiere recibos auténticos |
| Input/output/reasoning tokens N4+N12 | **NO MEDIDO en un run equivalente** | No sustituir por 8.040 bytes |
| LLM calls por expediente completo | **NO MEDIDO** | N3/N4/N5/N9/N12 condicionales |
| N12 focal: límite construido | **8.000 caracteres**, si hay cita válida | Límite de código, **no p95 de tokens** |
| p50/p95 latencia modelo | **NO MEDIDO** | n y recibo no disponibles |
| Recall/precision Gold original | **EXPERT_UNASSESSED** | Solo fixture semilla |
| Ensayos PG aislados de PR individuales | Sí, evidencia por job en #1049 | No sustituyen proveedor real |

## 4. Gate y siguiente evidencia exigible
- **0.3 WBS:** `REVIEW/BLOCKED_MEASUREMENT`, no DONE. Para un G0 condicional, aceptación expresa de deferir baseline real no bloqueante; G1 y cambio de proveedor no aceptados sin medición.
- **0.4 WBS:** `REVIEW/EXPERT_UNASSESSED`. Puede considerarse gold **mínimo anotable** (entregable de diseño), pero no corpus certificado.
- **1.7 WBS:** `BLOCKED` hasta benchmark de la **misma fuente/hash** con proveedor real, gold experto y recibos; 12 propuestas Gemini en cuatro cláusulas no equivalen a recall global.
- No manipular #1229 ni reproducir aprobación humana. El owner del gate decide PASS/NO-GO con pruebas adjuntas.

**Trazabilidad:** SHA de fuente EXCERPT confirmado localmente en VPS, sin convertir el resultado en declaración de fidelidad del PDF SEC ni del piloto 94p.