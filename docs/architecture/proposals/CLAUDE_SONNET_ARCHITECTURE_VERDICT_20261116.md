# Dictamen crítico: ARCHITECTURE_PLAN.md frente a la rama `feat/n4-multiprovider-gemini-openai-20261116`

**Alcance de la verificación.** Leí el plan completo y `workflow.py` líneas 200-379. De `nodes.py` leí 255-600 (N3, N4, N5, N9, N12). De `risk_extraction_tool.py` leí 196-240, 340-450 y 560-610, más un grep de firmas. De `n4_external_provider.py` leí 96-170, más un grep de firmas.

**No verifiqué** `schema.py`, ADR-014/017, la lógica interna de N6/N7/N8/N10/N11/N15, el almacén HITL/candidatos, `ClassifyDocumentUseCase`, el prompt N4 completo ni los tests. Lo que dependa de eso va marcado **[no verificado]**.

## (A) Veredicto: **GO condicionado**, solo para una primera fase estrecha

- **GO** para: (1) arreglar defectos reales del flujo actual, (2) N4 por ventanas con ledger y cobertura, (3) mover validación de citas antes del HITL.
- **NO-GO** para: N4 agéntico con tool-calling multiproveedor, router multi-etiqueta, los 3 modos de UI y el Tier-2 ProjectGraph, hasta que existan las métricas de la fase 1.
- **Por qué:** el diagnóstico del plan es en gran parte correcto. Pero la propuesta subestima dos costes que el código hace visibles: el reintento N12 reenvía el documento entero, y el provider actual no soporta herramientas.
- **Condiciones de GO:**
  1. Resolver las inconsistencias de (B).
  2. Fijar el presupuesto de reasoning en los providers antes de volver a comparar modelos.
  3. Acordar un gold set con experto antes de escribir código de F2.

## (B) Inconsistencias concretas entre plan y código

1. **Hueco de ruteo en N3 (probable bug vivo).**
   - `nodes.py:270` asigna `doc_type = "insufficient_extractable_text"`.
   - `workflow.py:279-291` no tiene esa clave en el `path_map` (solo contract, technical_spec, budget, schedule, specification, drawing, other).
   - Con `lambda state: state["doc_type"]`, un PDF escaneado sin texto debería provocar un error de ruteo en LangGraph en vez de un SKIPPED limpio.
   - **No verifiqué** si otro wrapper lo captura. Es verificable con un test de 10 líneas y encaja con el caso "PDF escaneado" del plan (§10).
2. **El plan escribe `N3->[N4,N5,N9]` como si fuera paralelo; el código es exclusivo.**
   - Es una conditional edge con un solo destino por `doc_type` (`workflow.py:279-291`).
   - Hacerlo multi-etiqueta exige fan-out más un join con lista (`add_edge([...], "critique")`).
   - Hoy hay tres `add_edge` separados hacia `critique` (`workflow.py:294-296`). Con fan-out, `critique` se dispararía varias veces. El comentario del propio archivo (`workflow.py:349-352`) describe ese mismo defecto para N10.
3. **El reintento N12 es el verdadero multiplicador de coste, y el plan no lo cuantifica.**
   - `workflow.py:306-309` devuelve a `risk_extractor`.
   - `risk_extraction_tool.py:430-431` re-añade `CRITIQUE:` y `FEEDBACK:` al texto y reenvía el documento completo.
   - Cada reintento es otra llamada N4 de contexto completo. Coste y latencia crecen linealmente con `retry_count`, y no hay recorte focal.
4. **N15 corre DESPUÉS del HITL; el plan exige citas literales antes.**
   - El comentario de `nodes.py:387-389` lo confirma: "N15 runs after HITL".
   - El plan (§1, §10) quiere "100% citas aceptadas literales" visibles en la revisión humana.
   - Solo `technical_spec` tiene validación previa (`nodes.py:394-418`). El humano revisa hoy riesgos de contrato sin validación literal.
   - Es un cambio barato, sin LLM, y de alto valor.
5. **"Vacío = fallo" está codificado, y la ambigüedad nace en la capa de abajo.**
   - `nodes.py:330-368` marca FAILED todo resultado sin riesgos.
   - Aguas abajo, la tool devuelve `[]` en `risk_extraction_tool.py:401`, y `_extract_items` devuelve `[]` en 576, 602 y 605.
   - Es el mismo valor para "documento sin riesgos", "payload con claves inesperadas" y "JSON roto". No existe ningún campo de cobertura.
6. **Heurística tolerante en el parser.**
   - `_extract_items` acepta seis claves alternativas (`risks`, `findings`, `items`…), más cualquier valor dict que "parezca" riesgo (`:595-601`).
   - Cuando el JSON no parsea y no hay continuaciones, hace salvage con regex (`:359`).
   - Esto contradice "eliminar heurísticas que sustituyan interpretación". Con `strict_completeness` (`:364`, `:395`) solo se cubre parte del camino.
7. **Código muerto o engañoso en N4.**
   - `_resolve_max_chars` (default 40.000, `:200-219`) no se usa en `extract_input_from_state` (`:410-441`), que envía todo el texto.
   - `max_risks` y `filter_relevant` están deprecados y no se aplican. `_keyword_match_text` (`:175`) sigue existiendo.
   - **No verifiqué** usos externos. Conviene confirmarlos antes de F2 para no mantener una API que miente.
8. **El provider NO soporta lo que el plan llama "evolucionable a tools".**
   - `AIRequest→AIResponse` es solo texto (`n4_external_provider.py:109-170`).
   - OpenAI usa `/v1/responses` con JSON schema estricto (`:145-159`). Gemini usa `generateContent` solo con `responseMimeType` (`:134-141`), sin schema.
   - Los dos caminos no son equivalentes, así que el benchmark del plan (§3: "no comparabilidad plena") no puede ser justo con este código.
9. **Posible causa raíz de los dos FAIL de GPT-6 Sol, no atribuida en el plan.**
   - Ni el payload de OpenAI (`:145-159`) ni el de Gemini (`:137-140`) fijan esfuerzo de razonamiento ni `thinkingConfig`.
   - El código ya lee `reasoning_tokens` y `thoughtsTokenCount` (`:178`, `:190`), así que sabe que existen. Pero `max_output_tokens` los incluye en el límite.
   - "0 riesgos" y "salida incompleta al límite 6.000" son compatibles con razonamiento invisible que consume el presupuesto, no necesariamente con incapacidad semántica.
   - **Es una hipótesis, no un hecho**: requiere la telemetría de esas ejecuciones, que no vi.
10. **Citas contra el texto anonimizado, no el original.**
    - El pre-HITL valida contra `anonymized_text` (`nodes.py:399`).
    - Además, el provider re-anonimiza `system+prompt` (`:117-122`).
    - Un span literal en la representación enviada no es automáticamente un span clicable en el original (§1 punto 6 del plan). Falta un mapa de offsets original↔enviado. **[no verificado si N2 lo produce]**
11. **N3 ya hace una llamada LLM por defecto.** `nodes.py:280-283` usa `ClassifyDocumentUseCase` con `get_ai_service`. El plan dice que N3 no debe hacerlo por defecto.
12. **Presupuesto solo por request.** El provider solo implementa precheck por request (`:127-129`). No vi límites por run, documento, proyecto o tenant; el plan los pide (§7). `core/ai/usage_analytics.py` existe según CLAUDE.md **[no verificado]**.
13. **HITL actual: una interrupción por run, y rechazo termina en END** (`workflow.py:326-333`). La revisión individual por hallazgo del plan (§1.7) es un cambio de modelo, no un ajuste. **[Módulo HITL no verificado.]**

## (C) Arquitectura mínima

**Nodos que mantener como están:**
- N1, N2 (determinista), N15, N17, N16.
- El fan-out/fan-in N6/N7/N8/N15 → N10 (`workflow.py:341-356`), que está bien resuelto con el join de lista.

**Cambios mínimos:**
- **N3:** primero determinista (extensión, MIME, hojas XLSX, estructura). LLM solo si no hay señal. Añadir la salida `insufficient_extractable_text` al `path_map`.
- **N4/N5/N9 con N12:** mantener el patrón extractor → crítica. Hacer que N12 sea consciente de cobertura (ver D) y que el reintento sea focal.
- **N15 determinista antes de N13/N14.** Después del HITL solo se re-ejecuta si el humano corrige una cita.
- **N10/N11:** diferir su rediseño hasta tener medición de lo que cuestan hoy. **[Su coste LLM actual no está verificado.]**

**Qué no hacer todavía:** nodos nuevos, un especialista "requisitos técnicos", agentes por documento, ni usar N8 como sustituto del ProjectGraph.

**Presupuesto de llamadas por documento, objetivo del modo completo:**

| Paso | Llamadas LLM |
|---|---|
| N3 | 0 (con fallback) |
| N4 | ventanas × 1 |
| N12 | 0 si cobertura completa y sin dudas; 1 focal si hay dudas |
| N5/N9 | 0 si la fuente es estructurada |

## (D) N4 incremental: sin tool-calling, con ventanas

Con el provider actual, **recomiendo ventanas sobre texto más ledger, no agente con herramientas**. Es portable entre Claude, OpenAI y Gemini, y evita construir tool-calling neutral antes de demostrar valor.

```python
async def n4_run(state, budget):
    inv = inventory(state)            # secciones/páginas/hojas, determinista (N1)
    ledger = load_or_create_ledger(run_id)   # CAS + idempotencia por (run_id, window_id)
    for w in plan_windows(inv, max_ctx=provider.window, overlap=OVERLAP):
        if ledger.window_done(w.id):          # reanudación
            continue
        budget.preflight(w)                   # reserva por ventana
        try:
            resp = await provider.generate(build_request(w, ledger.finding_headers()))
        except ProviderError as e:
            ledger.mark_window(w.id, "failed", e.kind); break
        out = parse_strict(resp)              # un único esquema; sin salvage
        if out.truncated or out.invalid:
            ledger.mark_window(w.id, "failed"); break
        for f in out.findings:
            span = locate_literal(f.quote, state.source_original)   # determinista
            ledger.upsert(stable_id(w, span), f, span, status="PROPOSED" if span else "UNVERIFIED")
        ledger.mark_window(w.id, "examined", sections=w.section_ids)
        budget.commit(resp.usage)
    cov = ledger.coverage()                    # examined/unreadable/pending/missing_external
    status = ("complete" if cov.all_examined and not ledger.has_failed
              else "partial" if ledger.findings else "blocked")
    return N4Result(findings=ledger.findings, coverage=cov, status=status)
```

**Reglas:**
- `risks=[]` solo es éxito si `status=complete` y la cobertura es total. Cualquier otra cosa es `partial` o `failed`, nunca éxito silencioso.
- Deduplicación por solape: `stable_id` basado en span normalizado más categoría. Equivalencia semántica solo si hay duda, y entonces una llamada pequeña, no en bloque.
- Checkpoint: el ledger es una tabla con el cursor de ventana. LangGraph sigue siendo el HITL; el ledger no sustituye al checkpointer.
- **Citas:** el modelo devuelve el literal; el adaptador lo localiza en el original y guarda `document_revision_id` más offsets. Si no se localiza, `UNVERIFIED` y a HITL, no se descarta.
- **HITL:** por hallazgo, con decisión persistida contra `finding_id`. El acto final queda separado y reutiliza el interrupt actual. **[Depende del módulo HITL, no verificado.]**
- **Migración mínima:** tabla nueva `n4_finding_ledger` más `n4_window_progress`, con RLS. No tocar `DocumentArtifact`; proyectar al contrato existente (`_risk_contract_payload`) solo al finalizar.

## (E) Router N3 multimodal y compatibilidad N5/N9/ProjectGraph

- **Fase 1 (barata):** clasificación determinista, y una salida por elemento (hojas, secciones), no por documento. Un XLSX con presupuesto y cronograma va a N9 y N5 por hoja.
- **Multi-etiqueta real** solo después de: join de lista hacia `critique`, claves de estado disjuntas por rama (el contrato de `workflow.py:211-224` ya lo documenta para el enrichment) y N12 que acepte varias salidas.
- **N5/N9** deben tomar entrada estructurada por parser (XER/MPP/XLSX), con cálculos exactos. N4 no recibe tareas de N5/N9; solo emite referencias cruzadas ("la cláusula X menciona hito Y") como candidatos que Tier-2 resuelve.
- **ProjectGraph:** conservar N10 como Tier-1 por documento (ADR-017 según el plan, **no verificado**). No escribir de N4 al grafo del proyecto, solo al ledger. Tier-2 consume el ledger tras HITL.

## (F) Límites de gasto y latencia

- **Hoy:** precheck por request (`n4_external_provider.py:127-129`), con estimación de input conservadora `chars//2` (`:107`) y output = `max_output_tokens`. No hay reintento (`:161`). Solo cubre la capa más baja.
- **Falta:** acumulado por run, documento, proyecto y tenant, y reserva atómica compartida entre ventanas concurrentes. Propongo un `BudgetLedger` en Redis o PG con reserva y liquidación por ventana.
- **Reasoning:** fijar `reasoning.effort` (OpenAI) y `thinkingConfig.thinkingBudget` (Gemini) y contabilizarlos explícitamente dentro de `max_output_tokens`. Sin esto, cualquier benchmark es ruido.
- **Latencia:** las ventanas secuenciales suman. Paralelizarlas solo cuando el ledger sea idempotente y el presupuesto reserve por ventana. Medir p50/p95 por documento antes de decidir.
- **Agotamiento:** pausa con checkpoint, estado `partial/blocked`, y mensaje al usuario con lo cubierto. Nunca "completo".

## (G) Tres modos y riesgos de cobertura

| Modo | Definición | Riesgo principal |
|---|---|---|
| **Rápido** | Ventanas con modelo barato o una sola pasada, sin N12. Etiqueta "preliminar" fija | Se lee como "sin riesgos" cuando solo es "sin hallazgos en lo examinado" |
| **Completo** (default) | Cobertura íntegra de ventanas, N12 focal | Coste alto si el documento es grande; necesita tope por tenant |
| **Auditoría** | Segunda opinión selectiva (otro proveedor) solo en secciones críticas o discrepantes | El desacuerdo entre modelos no prueba error; necesita criterio de desempate humano |

- **Riesgo de cobertura de las ventanas:** una obligación y su excepción en ventanas distintas. Mitigación: solape más `resolve_cross_reference` determinista (búsqueda literal de "artículo X"), no un LLM.
- **No implementar los 3 modos antes de tener el gold set.** Sin métricas, "rápido" y "completo" son etiquetas sin respaldo.
- **UI:** el modo viaja en el run y en cada hallazgo (`produced_by_mode`), para que un resultado rápido nunca sustituya silenciosamente a uno completo.

## (H) Secuencia mínima de PRs, QA y criterios de salida

| PR | Contenido | Salida |
|---|---|---|
| **0** | Test del hueco `insufficient_extractable_text`; fix del `path_map` | Test rojo→verde |
| **1** | Telemetría de reasoning en providers; fijar effort/budget; mismo esquema para Gemini y OpenAI | Rerun del extracto SolarMax con cifras comparables |
| **2** | N15 determinista previo a N13 (contratos) | Citas validadas visibles en HITL |
| **3** | `NodeResult` de N4 con cobertura y estados `complete/partial/blocked`; separar "vacío" de "fallo" en el parser | `[]` ya no es ambiguo |
| **4** | Ledger + ventanas + reanudación (flag off por defecto) | 3 runs repetibles sin duplicados |
| **5** | BudgetLedger multinivel | Corte forzado produce `partial`, no éxito |
| **6** | N12 focal y gold set con experto | Recall/precisión medidos |

**QA obligatorio:**
- Los fallos del plan §10: corte de proveedor, 0 riesgos real, JSON truncado, anexo ausente, PDF escaneado, race/fence.
- Tests de idempotencia del ledger.
- Aislamiento por tenant con RLS.
- Caso adversarial: excepción en otra ventana.

**Criterios de salida de la fase 1 (PR 0-3):**
- Cero resultados vacíos reportados como éxito.
- 100% de hallazgos con estado de cita.
- Cero regresiones en el flujo Claude por defecto.
- **No tocar el piloto ni #1229**, como exige el plan §9.

## (I) Cinco objeciones al autor

1. **"¿Por qué agente con herramientas si el provider solo habla texto?"** Seis herramientas neutrales a tres proveedores es un proyecto en sí mismo. Las ventanas más el ledger consiguen el 80% del valor con una fracción del riesgo. Demuestre primero que las ventanas fallan.
2. **"Los FAIL de GPT-6 Sol se atribuyen implícitamente al modelo y se resuelven con arquitectura."** El código no controla el razonamiento (`:137-159`). Antes de rediseñar N4, descarte que la causa sea presupuesto de reasoning. Si lo es, buena parte del §5 es una solución a un problema distinto.
3. **"Seis etapas y 'sin 17 llamadas' no son un presupuesto."** Falta una tabla de llamadas LLM por nodo con coste p50/p95 medido hoy. No verifiqué cuántas hacen N6/N7/N10/N11; el plan tampoco lo demuestra, y sin eso "minimiza coste" (pregunta 1) no es contestable.
4. **"Los criterios de §10 (≥90% recall y precisión, 100% de críticos) no tienen línea base."** No hay gold set, ni calibración, ni definición de "crítico". Fijar umbrales antes de medir es teatro. Y 4 cláusulas de SolarMax (12 candidatos) no sostienen ninguna estadística.
5. **"El ProjectGraph, los 3 modos y la multi-vertical entran en el mismo plan que cerrar #1229."** El plan se declara prioritariamente de Complete Journey EPC, pero F4-F8 amplían el alcance mucho más allá. Recomiendo recortar el plan a F0-F2 más los PR 0-3 de arriba, y reabrir el resto con datos.

**Incertidumbres finales.** No verifiqué `schema.py`, los ADR, el módulo HITL, los costes de N6-N11 ni el prompt N4 completo. Mi hipótesis sobre el reasoning (B.9) y sobre el hueco de ruteo (B.1) son inferencias del código, no ejecuciones.
