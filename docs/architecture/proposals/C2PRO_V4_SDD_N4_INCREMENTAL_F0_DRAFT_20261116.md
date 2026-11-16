# C2Pro V4 — SDD-F0: N4 incremental con evidencia persistente y presupuesto gobernado
**Versión:** DRAFT 0.1 · 16/11/2026 · **Ámbito:** S0 WBS 0.5. **Estado:** especificación para revisión; NO implementación autorizada por este documento, aunque el plan general S0–S5 sí tiene GO del propietario.
**Baseline:** `release/core-candidate-20261108` SHA `5af16eed1d3087f8e081cdc5caa567f726ca6a9e`, PR #1234 (draft) y #1235 (draft).
**Contexto:** ADR-014 ProjectState, ADR-017 ProjectGraph, ADR-013 NodeResult, #1229 HITL, contratos de `risk_extraction_tool.py` y `nodes.py`.

## 1. Decisiones arquitectónicas
1. **Mantener el nodo público N4 `risk_extractor` y no reescribir N1–N17.** N4 invoca un servicio incremental interno, retorna `NodeResult` y estado de cobertura; N12, N15, N17 y ProjectGraph consumen adaptadores compatibles.
2. **Fase MVP: ventanas consecutivas + ledger con un esquema de hallazgos compacto.** No exigir tool-calling agéntico universal en la primera versión. Agregar herramientas de búsqueda/lectura focal solo al medir falsos negativos por separaciones del contexto o referencias cruzadas.
3. **Control semántico por IA, integridad por código.** Cita literal, hash, rev, cálculos, permisos, costes e idempotencia son verificaciones programáticas, no heurísticas que suprimen material.
4. **No pasar nunca de un `extraction complete` a `trusted/approved` sin fuente/usuario y requisitos existentes.** Compleción de la lectura ≠ calidad de hallazgos ≠ aprobación humana.
5. **No abrir ruta de impacto automático en piloto mientras #1229 tenga G1/G4 sin demostrar**; datos extraídos pueden mostrarse PROVISIONALMENTE y con fuente sin incorporarlos al estado validado ni score validado.

## 2. Fronteras
- El BLOB original y su `DocumentRevision` son inmutables y tenant-scoped; extractor N4 no lee otros tenants ni genera enlaces a secretos.
- N1 entrega texto, páginas/filas y tabla de origen. Dejar registro de OCR pendiente y secciones ilegibles, NO inventar OCR ni procesar fragmentos faltantes como «examinados».
- N2 produce representación segura para modelo; registrar traducción de spans `original ↔ sanitized`. No tratar un substring literal en texto anonimizad como prueba de cita en original.
- N3 sigue entregando `doc_type=contract` hasta implementar routing multietiqueta con fanout/fanin correcto.
- N4 entrega candidatos y `CoverageReport`. N12 evalúa omisiones, no vuelve a lanzar un intento completo sobre el mismo archivo salvo razones expresas. N15 verifica localización literal; HITL hace revisión humana; ProjectGraph enlaza relaciones de proyecto después.
- ProjectGraph (Tier-2) continúa separado/asíncrono del DocumentGraph. No generar un segundo grafo paralelo improvisado.

## 3. Contratos de datos propuestos
**Documento/sección**
`SourceUnit(id, tenant_id, project_id, document_id, revision_id, parser_version, ordinal, type, original_span_or_cell, sanitized_span, hash, status)` con `status: READY|UNREADABLE|MISSING_EXTERNAL|PENDING`.
La fuente completa es el conjunto de unidades `READY` + unidades explícitamente indisponibles. Las tablas/hojas conservan estructura/celdas; no convertir fórmula/cantidad en relato IA si son computables.

**Run**
`ExtractionRun(run_id, tenant_id, project_id, document_id, revision_id, source_hash, model_family, provider, prompt_version, schema_version, mode, status, claim_token, budget_cap_usd, reserved_usd, spent_usd, started_at, finished_at)`.
`status = PREPARING|RUNNING|PARTIAL|BLOCKED|FAILED|COMPLETE`. Un run no puede ser `COMPLETE` si falta una unidad `READY` sin cubrir.

**Ventana**
`ExtractionWindow(window_id, run_id, source_unit_ids, context_hash, ordinal_start, ordinal_end, coverage_status, attempt_id, claim_token, last_error_kind)`.
`coverage_status = PENDING|IN_PROGRESS|EXAMINED|FAILED|UNREADABLE|MISSING_EXTERNAL`.
Ventanas solapadas son permitidas pero se enlazan al mismo `SourceUnit`; `EXAMINED` no demuestra recordar riesgos críticos.

**Hallazgo**
`RiskFindingCandidate(finding_id, run_id, document_revision_id, category, title, claim, interpretation, source_refs[], source_quote_ref, literal_status, risk_reason, impact, probability_basis, mitigation, confidence_notes, review_status, created_at, supersedes_id)`.
`literal_status = VERIFIED_ORIGINAL|VERIFIED_SANITIZED_ONLY|NOT_FOUND|MISSING_QUOTE|SOURCE_UNAVAILABLE`.
`review_status = PROPOSED|REVIEW_PENDING|ACCEPTED|REJECTED|CORRECTED|SUPERSEDED`; no exportar como TRUSTED solo porque `literal_status=VERIFIED_ORIGINAL`.
El ID estable se basa en run/revision + span original + claim normalizado; un hallazgo con dos spans preserva dos fuentes. Solape de ventanas idempotente mediante upsert `(run_id, finding_id)` o unique equivalente; no hacer dedup semántico destructivo por descripción vagamente similar.

**Cobertura**
`CoverageReport(run_id, source_unit_count, examined_unit_ids, unavailable_unit_ids, pending_unit_ids, failed_unit_ids, unresolved_references, warnings)`.
Declarar tanto `source_coverage` (qué se intentó leer) como `semantic_recall` (estimado sobre gold) por separado. Sin gold, `semantic_recall=UNASSESSED`. Un run con `risks=[]` solo puede expresar «no se encontraron riesgos en lo examinado» hasta que N12 y la cobertura permitan una conclusión más amplia, nunca «sin riesgos» por omisión.

## 4. Persistencia, concurrencia y autoridad
PostgreSQL, esquemas aditivos propuestos: `n4_extraction_runs`, `n4_source_units`, `n4_window_progress`, `n4_findings`, `n4_usage_ledger`. Confirmar primero si hay tablas generales reutilizables; **no duplicar** `EvidenceExtractionEventORM`, `ProjectEvent` o cost controller si ya cubren el contrato.
Todas las tablas: `tenant_id`, RLS, FK revision, índices por `run_id`, UUID ids y auditoría. Un worker actualiza ventanas solo si `processing_authority`/fencing y `claim_token` siguen vigentes; una ejecución desplazada no puede mutar run actual.
Persistir por ventana **después** de parseo y verificación tipados, mediante única transacción: estados+candidatos+usage reservation reconciliation; si el commit falla, reintento debe reconsultar idempotencia antes de repetir llamada pagada.
No persistir fuente íntegra ni credenciales en logs/eventos, solo referencias/hashes y error_type acotado. Mantener versiones de prompt, proveedor, parser y modelo para reproducibilidad.

## 5. Política económica
Preflight por ventana: límite por request y reserva acumulativa por run/documento/proyecto/tenant. Reserva atómica en PG o reutilización de CostController existente, no Redis volátil como único origen contable.
**Reserved** incluye máximo estimado por respuesta y reasoning; **spent** se liquida con uso reportado, con `PARTIAL_BILLABLE` y `UNSETTLED` cuando hay timeout sin recibo final. Desconocido NO equivale a cero. Se puede pausar run en `PARTIAL/BLOCKED` al alcanzar cuota, conservando candidatos sin marcar COMPLETE. No reintento ilimitado ni continuación monolítica.
Instrumentar `run_id, window_id, provider, model, prompt/schema version, input/output/reasoning tokens, billed/estimated usd, p50/p95, attempt_count, result_kind` sin exponer PII/secretos.

## 6. Algoritmo MVP
```python
async def extract_n4_incremental(ctx):
    run = await acquire_run(ctx.document_revision_id, ctx.policy, ctx.fence)
    units = await get_or_create_source_inventory(ctx.document_revision_id)
    for window in windows_in_order(units, ctx.provider_context_limit):
        if await run.window_done(window.id):
            continue
        reservation = await budget.reserve(ctx.tenant, run.id, window.estimated_max)
        if not reservation.allowed:
            return await run.pause_with_coverage("budget_exhausted")
        try:
            response = await provider.generate(
                prompt=compact_evidence_contract,
                source_window=window.sanitized_text,
                context_refs=await lookup_declared_crossrefs(window, units),
                max_output_tokens=window.policy_cap,
            )
            findings = parse_strict_and_verify_response(response)
            await run.commit_window(
                window.id, findings, response.usage, ctx.fence, reservation
            )
        except ProviderTruncatedOrInvalid as e:
            await run.record_partial_and_failure(window.id, e, reservation)
            return await run.pause_with_coverage(e.kind)
    return await run.finish_with_coverage()
```
No significa que el modelo tenga que generar un JSON por cada pequeña frase; optimizar ventana/longitud/solapes con p95, y usar referencias en lugar de repetir citas largas. Contraste cruzado se ejecuta **solo en ventanas con referencias/ambigüedad**, no en todos los segmentos.

## 7. Adaptadores multi-provider
Contrato externo actual de PR #1234 es texto `AIRequest→AIResponse`. MVP de ventanas puede funcionar con ese transporte antes de universalizar tool calls, manteniendo Anthropic predeterminado y OpenAI/Gemini opt-in. Comparar con exacto contrato de evidencia compacto, misma fuente/hash y límites de output/reasoning documentados. No asumir que `thinking budget=0` sea posible o recomendado en todos los modelos. Leer `finish_reason`, truncamiento y tokens ocultos; no colapsar error a `risks=[]`.
Más adelante: interfaz `read_source_span/ref` agéntica si gold adversarial de referencias cruzadas no mejora con el MVP.

## 8. Compatibilidad y despliegue
Fase A: tablas y interfaces nuevas sin alterar legado, flags OFF en PILOT.
Fase B: N4 legacy adapter lee `N4Result` en ejecución aislada; cuando `COMPLETE`, proyecta candidatos compatibles con `_risk_contract_payload`; cuando `PARTIAL/BLOCKED/FAILED`, retorna `NodeResult` y evita sello de éxito, no incorpora resultados incompletos como confiables.
Fase C: N12/N15 evalúan evidencia antes de HITL, sin suplantar `HumanInTheLoopService`; la aprobación final sigue separada.
Fase D: ProjectGraph consume `DocumentArtifact` tipado; lecturas provisionales segregadas por estado. No elevar score validado por aprobación de riesgo.
Rollback = desactivar flag, preservar ledger como evidencia no confiable/histórico y volver a ruta N4 anterior sin eliminar revisiones ni cambiar tablas base. Gates CI, RLS, latencia, Quality benchmark, UAT real humano.

## 9. Pruebas obligatorias
- 0 riesgos real vs llamada provider fallida, JSON inválido, truncamiento, 0 output tokens, sin cobertura.
- Excepción normativa en ventana posterior; dos hallazgos semánticamente relacionados con distintos spans; anexo faltante; PDF con OCR pendiente.
- PII re-anonimizada dos veces y spans desplazados; cita presente solo en texto sanitizado => NOT VERIFIED ORIGINAL.
- Timeout después de consumir tokens, antes de recibo: NO marcar coste 0; reconciliar pago/deduplicar intento si proveedor lo soporta.
- Abortar y reiniciar en cada seam (pre-reserva, post-llamada, pre-commit, post-commit), mismo run y mismo fence; comparar hashes.
- Rev cambia durante procesamiento, alquiler worker expira, RLS cross tenant, ventana duplicada en paralelo.
- N12 critica focal, no vuelta a fuente completa salvo decisión medida; HITL queda en revisión humana con origen real y estado coherente.
- Bench 4 cláusulas (regresión), contrato completo y expediente contrato/XLSX/cronograma/spec real con gold experto. Probar 3 modos solo tras medir.

## 10. Preguntas abiertas antes de migrar
- ¿Qué almacén actual de evidencia/ventanas/uso es canónico y cuál merece reutilización?
- ¿La fuente original original conserva offsets para PDF Word y XLSX, o solo texto plano?
- ¿Qué semántica exacta de `no findings but complete coverage` aceptará el reviewer de N12?
- ¿Cómo se expone evidencia provisional en UI sin parecer aprobación validada?
- ¿Qué caps por run/tenant/documento se fijan tras medir consumo real?
- ¿Dónde se retiene el candidato exacto y qué transiciones en #1229 dependen de `analysis_id`/artifact?
- ¿Cómo versionar el gold por document hash/método y resolver desacuerdo experto?

**Gate F0:** cerrar estas decisiones, comprobar interfaces con código real y validar QA/arquitectura antes de Alembic/PR de ejecución. Mantener plan de 3 modos y multivertical como objetivo sin ampliar la ontología de EPC a software.
