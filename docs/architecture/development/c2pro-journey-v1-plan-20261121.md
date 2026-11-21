# C2Pro — Plan de implementación Journey V1 (línea productiva + línea experimental)

**Fecha:** sáb 21/11/2026 · **Estado:** PROPUESTO — pendiente de OK del fundador (C0) · **Autor:** Claude (planner/integrador), con desglose del agente Plan y verificación independiente
**Base de código:** `integration/journey-v1` = #1283 (929fbda) + hojas #1280, #1271, #1273, #1282, #1277 + `ci.yml` ampliado a `integration/**` (head 34b4180)
**Fuentes:** revisión Pass E de Claude, ChatGPT y Gemini (21/11); benchmark T0–T9; auditoría FG-1; lectura de código en 929fbda; despliegues de Railway (solo lectura)

> Confidencialidad: este documento está en un repositorio **público**. No contiene nombres de contratos privados, IDs de Drive, citas ni salidas de modelos sobre contratos reales. El manifiesto del corpus y los oráculos viven solo en el Drive privado del fundador.

---

## 0. Resumen para el fundador

- **Objetivo:** que un usuario real complete el recorrido *subir contrato (+ cronograma y presupuesto) → análisis sin pérdidas silenciosas → hallazgos con cita literal y página → revisión uno a uno → Score global + 6 subscores → Excel/PDF → sigue ahí al volver a entrar*, con calidad medida sobre **6 contratos** y no sobre uno.
- **Fechas:** V1 **mar 24/11 12:00** · V2 **jue 26/11 10:00** · aceptación **lun 30/11 17:00** · margen mar 1/12 (tope 3/12). El umbral de calidad no se rebaja.
- **Umbral (por contrato):** C2Pro ≥ análisis directo (Claude/ChatGPT con el contrato completo) **y** ≥ 90 % de controles críticos del oráculo; **100 % de citas literales con página**; **0 ventanas perdidas en silencio**.
- **Qué arregla:** N4 deja de pararse en la primera ventana que falla y deja de bloquearse por remisiones; reintenta con salida estructurada y más tokens; consolida y resuelve remisiones; las filas de cláusulas dejan de perder el 70 % del texto (alimentan el Score); los hallazgos llegan a la revisión aunque haya huecos (visibles y cerrables); **los hallazgos que confirmas alimentan los 6 subscores** (hoy el Score los ignora); el Score se calcula solo; hay Excel y PDF.
- **Red de seguridad:** si en V1 el N4 mejorado no alcanza el umbral, se activa el motor "extracción directa" (`C2PRO_N4_ENGINE=direct`) sobre el mismo ledger, revisión, página y exportación. No se rehace nada.
- **Coste:** ≤ 100 USD de API con topes duros; la línea experimental se para al 85 %.
- **Equipo:** hasta 9 carriles de escritura sin conflictos de archivos (Claude Code, Codex, Gemini CLI/Antigravity, ChatGPT, OpenCode, OpenClaw, Hermes) + auditor de solo lectura. **Integra y fusiona Claude; suplente ChatGPT GPT-6.** Despliegues al piloto preautorizados con CI verde.

---

## 1. Revisión unificada (Claude × ChatGPT × Gemini)

Los tres modelos: **ACCEPT_WITH_CONDITIONS**, sin objeciones bloqueantes. Las condiciones son el trabajo de este plan.

### 1.1 Hechos verificados (código o evidencia, ≥ 2 fuentes)

| # | Hecho | Evidencia |
|---|---|---|
| H1 | Una ventana N4 fallida detiene el run; el bridge exige el 100 % de ventanas para pasar a revisión | `analysis/application/n4_incremental_runner.py`, `analysis/adapters/graph/n4_governed_bridge.py:216-230` |
| H2 | **Una ventana con remisiones pendientes queda BLOCKED y el run en PARTIAL aunque nada falle** (en T5 los 9 JSON válidos traían remisiones) | `analysis/adapters/persistence/n4_incremental_store.py:829-857` |
| H3 | Un corte por `max_tokens` se registra sin coste como UNKNOWN y la ventana ya no se puede reintentar | `core/ai/llm_client.py:689-691`; runner 286-327; store 459-471 |
| H4 | El parser exige coincidencia literal exacta (pierde citas con saltos de línea del PDF); la búsqueda tolerante de VS-2 existe sin conectar | `analysis/domain/n4_compact_window_response.py:94-106`; `n4_typed_evidence_v2.py:163-174` |
| H5 | Salida 2048 tokens; el proveedor no admite más de 4096 | bridge 186/193/196; `analysis/adapters/ai/n4_anthropic_window_provider.py:36` |
| H6 | Filas de cláusulas truncadas a 4000 car. y segmentos <40 descartados; alimentan coherencia/Score, alertas, grafo y endpoint de cláusulas. Reproducción ChatGPT: 29,9 % del texto retenido, 5/14 controles fuera | `core/tasks/ingestion_tasks.py:845-849`; `coherence/router.py:372-457` |
| H7 | El regex de encabezados no reconoce portugués (Artigo, Secção, Anexo) | `core/tasks/ingestion_tasks.py:815-819` |
| H8 | Modelo N4 efectivo = `claude-sonnet-4-6` (YAML); el benchmark usó Sonnet 5.5; dos fuentes de verdad | `core/ai/model_routing.yaml:31-32`; `config.py:284` |
| H9 | El Score no se calcula solo; N8 usa solo cláusulas del documento; TIME/BUDGET solo vía `POST /coherence/evaluate` (DET-CRS-SCHDEAD, DET-CRS-CONBUD…) | `coherence/router.py:1175-1479`; `coherence/graph/nodes.py:994` |
| H10 | Exportación = solo `window.print()` | `AuditReportMode.tsx:109` |
| H11 | N2 solo anonimiza DNI, email, teléfono e IBAN (nombres e importes pasan) — **aceptado por el fundador** para Anthropic/OpenAI | `anonymizer/domain/pii_detector_service.py:51-57` |
| H12 | El piloto Railway ejecuta **799ce53**; `main` está parado desde el 28/10; hay **120 PR abiertos (99 borradores)** apilados; `ci.yml` **no corría** en PR contra ramas de feature. Primer CI real de la integración: ruff 80, mypy +91, 19 unit + 3 web en rojo (A0b) | Railway (solo lectura); GitHub REST; run 44917370712 |
| H13 | Benchmark T5: 22 ventanas → 9 JSON válidos, 6 por límite de tokens, 7 formato inválido. FG-1: SM-03/05/08 sin hallazgo directo; citas sin cifras | CSV T5; `docs/audits/C2PRO_FG1_SOLARMAX_REAL_CONTRACT_OFFLINE_REPLAY_2026-11-20.md` |

### 1.2 Correcciones aceptadas de ChatGPT
T9 no demuestra superioridad del híbrido; T0 no fue ciego; Docling y LangExtract siguen siendo hipótesis; OpenContracts es opcional; N1 no es el parser; no se ejecuta una campaña E1–E11; faltaba la truncación de cláusulas (H6).

### 1.3 Discrepancias y cómo se resuelven
| Tema | Resolución |
|---|---|
| Puerta de materialidad (Gemini sí, ChatGPT aún no) | Implementada tras flag (A18); decide el fundador en V2 con datos |
| Resultados parciales | `COMPLETE_WITH_GAPS`: hallazgos revisables uno a uno; aprobación final y Score bloqueados hasta cerrar huecos (A15, A18) |
| OpenContracts / Docling | Fuera de la ruta crítica (X6, X4) |
| Gobernanza G2–G4 | Congelada; control de gasto con topes de consola + `RUN_USD` + gobernador |

---

## 2. Decisiones cerradas

| Id | Decisión | Origen |
|---|---|---|
| D1 | Fechas: V1 24/11 12:00 · V2 26/11 10:00 · Aceptación 30/11 17:00 · margen 1/12 (tope 3/12) | Fundador ("más agresividad") |
| D2 | Presupuesto API total 100 USD, tope duro; N4 facturable solo en el piloto | Fundador |
| D3 | Corpus 6 contratos: C1 SolarMax + 5 privados; 3 desarrollo / 3 aceptación nunca vistos; cronogramas/presupuestos que falten se generan **SINTÉTICOS** con OpenAI | Fundador |
| D4 | Umbral por contrato: ≥ directo **y** ≥ 90 % críticos; 100 % citas literales con página; 0 ventanas perdidas en silencio | Fundador |
| D5 | Contratos privados solo a Anthropic y OpenAI (tras N2 tal cual, nombres incluidos); nunca en el repo. Agentes con modelos gratuitos/otros (OpenCode, OpenClaw, Hermes, DeepSeek, Gemini) solo código y datos sintéticos | Fundador |
| D6 | Oráculo validado por el fundador (~1 h/contrato) sobre plantilla prerrellenada por OpenAI; los de aceptación se validan y se fijan con hash antes de ver salidas de C2Pro | Fundador |
| D7 | Un Score global + 6 subscores; "No evaluada" (null, nunca 0); aceptar un riesgo no sube el Score; con huecos el Score queda "Pendiente"; materialidad tras flag | Fundador / ADR-018 |
| D8 | HITL individual; nada provisional pasa a TRUSTED solo; un usuario funcional (Clerk admin) | Fundador |
| D9 | Integración en `integration/journey-v1` (creada). **Fusiona Claude; suplente ChatGPT GPT-6.** Condición: CI verde + auditor en WPs de riesgo alto. Nada va a `main` en esta campaña | Fundador |
| D10 | Despliegues al piloto **preautorizados con CI verde** (todos). Vuelta atrás a 799ce53 documentada | Fundador |
| D11 | N12 fuera de la ruta crítica (`C2PRO_N12_MODE=off`): N1→N2→N4→HITL→Score. N12 se mide aparte (B8) | DR-07 aceptado |
| D12 | Interfaz en inglés (sin i18n) con lenguaje de negocio; informe Excel + PDF | Supuesto S8 no corregido |
| D13 | El MASTER lo actualiza ChatGPT (Document Steward) con este plan | Supuesto S11 |

---

## 3. Calendario y checkpoints (hora de Madrid)

| Hito | Cuándo | Qué se demuestra con uso real | Decide |
|---|---|---|---|
| **C0 Arranque** | dom 22/11 09:00 | Plan aprobado; topes de consola Anthropic/OpenAI puestos; corpus confirmado; arranca A0b | Fundador |
| CI en verde | dom 22/11 20:00 | `integration/journey-v1` con `ci-status` verde (A0b) | — |
| Despliegue 1 | lun 23/11 ~21:30 | `integration/journey-v1` con A2–A12 en el piloto (automático con CI verde) | — |
| Despliegue 1b | mar 24/11 ~10:30 | Motor alternativo A8 disponible tras flag | — |
| **V1** | **mar 24/11 12:00** | SolarMax + C2 en el piloto: N4 sin ventanas perdidas, hallazgos con cita y página, revisables uno a uno; métricas D4 frente a oráculo y análisis directo | Fundador: modelo N4 (B7) y **motor por ventanas vs directo** |
| Despliegue 2 | mié 25/11 ~19:00 | A15–A23 y A26 en el piloto | — |
| **V2** | **jue 26/11 10:00** | Journey completo en C1–C3: revisión → Score + 6 subscores (TIME/BUDGET con cronograma/presupuesto) → Excel/PDF → re-login sin re-gasto | Fundador: materialidad; **congelación de prompts** |
| Oráculos de aceptación | vie 27/11 20:00 | C4–C6 validados y fijados con hash, a ciegas | Fundador |
| Ejecución de aceptación | sáb 28 – dom 29/11 | C4–C6 por el journey; análisis directo de referencia | — |
| **Aceptación** | **lun 30/11 17:00** | Umbral D4 en C4–C6 + revisión del fundador en la interfaz | Fundador: GO/NO-GO demo |
| Margen | mar 1/12 (tope 3/12) | Solo corrección de defectos; prohibido ajustar prompts con datos de aceptación | — |

Tiempo del fundador: ~3 h dom 22–lun 23 (oráculos de desarrollo), ~3 h vie 27 (aceptación), ~45 min por checkpoint.

---

## 4. Carriles, roles y propiedad de archivos

Rutas relativas a `apps/api/src` salvo indicación. Regla: **un archivo, un carril**; los stubs que crea A1 (`n4_clause_inventory.py`, `quote_page_locator.py`, firma `generate(..., attempt)`) pasan a ser del carril que los implementa en cuanto A1 se fusiona (dom 11:00), antes de que nadie más edite esos archivos; L0 regenera `openapi.yaml` tras fusionar A16, A19 y A20; los tests existentes los actualiza el dueño del archivo de código; L8 solo crea tests nuevos; solo L0 regenera `docs/api/openapi.yaml`; el frontend no regenera `lib/api/generated` (servicios manuales).

| Carril | Rol · agente | WPs | Archivos de propiedad exclusiva | Datos |
|---|---|---|---|---|
| L0 | Orchestrator/DevOps · **Claude** (suplente ChatGPT GPT-6) + Codex para Railway | A0, A13, A14, fusiones | rama de integración; variables Railway; `docs/runbooks/journey-v1-pilot.md`; `openapi.yaml` | metadatos |
| L1 | Backend · Claude Code (Opus) | A1, A2, A3, A16 | `analysis/adapters/persistence/n4_incremental_store.py`, `analysis/application/n4_incremental_runner.py`, `analysis/domain/n4_failure_kinds.py` (nuevo), `documents/adapters/http/router.py` | sintéticos |
| L2 | Backend · Codex | A4, A5, A6 | `core/ai/llm_client.py`, `core/ai/anthropic_wrapper.py`, `core/ai/model_router.py`, `core/ai/model_routing.yaml`, `config.py`, `analysis/adapters/ai/n4_anthropic_window_provider.py`, `analysis/domain/n4_compact_window_response.py`, `analysis/domain/n4_clause_inventory.py` (nuevo) | sintéticos + SolarMax (público) |
| L3 | Backend · Claude Code (Sonnet) | A7, A8 | `analysis/adapters/graph/n4_governed_bridge.py`, `analysis/adapters/graph/nodes.py`, `analysis/adapters/graph/schema.py`, `analysis/domain/contracts.py`, `analysis/domain/n4_consolidation.py` (nuevo), `analysis/domain/n4_reference_register.py` (nuevo), `analysis/adapters/ai/n4_direct_openai_window_provider.py` | sintéticos |
| L4 | Backend · Codex (2.ª sesión); A9 con OpenCode | A9, A10, A11, A12 | `core/tasks/ingestion_tasks.py`, `documents/adapters/parsers/pdf_file_parser.py`, `documents/domain/quote_page_locator.py` (nuevo) | sintéticos |
| L5 | Backend · Claude Code (Sonnet, 2.ª y 3.ª sesión) | A15, A17, A18 (L5a); A26 (L5b) | L5a: `modules/hitl/application/resume_workflow_use_case.py`, `modules/hitl/adapters/http/router.py`, `coherence/router.py` · L5b: `coherence/application/project_evaluation.py` (nuevo, creado en A17), `coherence/application/validated_findings_evidence.py` (nuevo) | sintéticos |
| L6 | Backend · Gemini CLI / Antigravity | A19, A20 | `reporting/application/build_journey_export.py` (nuevo), `reporting/adapters/http/router.py` | **solo sintéticos** |
| L7 | Frontend · Claude Code (Sonnet) o Antigravity | A21, A22 | `apps/web/app/(app)/projects/[id]/documents/[documentId]/n4-findings/page.tsx`, `apps/web/components/features/review/*`, `apps/web/components/coherence/*`, `apps/web/components/features/report/*`, `apps/web/lib/api/services/journey*.ts` | sintéticos |
| L8 | Test/QA · OpenClaw / OpenCode-DeepSeek | A23 | solo archivos de test nuevos | **solo sintéticos**; usuario Clerk de prueba en entorno desechable, nunca credenciales del piloto |
| LB1 | Test/QA · OpenCode / Hermes | B0, B4, B5 | `apps/api/scripts/journey_v1_*.py`, `apps/api/tests/unit/scripts/test_journey_v1_*.py`, `evals/journey_v1/synthetic/` | **solo sintéticos**: escriben código con fixtures; B0, B4 y B5 sobre datos reales los ejecuta solo Claude Code o el fundador en local |
| LB2 | Evaluación · ChatGPT (API OpenAI) + Claude Code | B1, B2, B3, B6, B7 | `evals/journey_v1/` (plantillas); datos reales solo en Drive privado | contratos reales (Anthropic/OpenAI) |
| LV | Verification Auditor · Gemini CLI (solo lectura) + Claude (este chat) | revisa A2, A3, A7, A15, A16 antes de fusionar; auditoría final | ninguno | código y métricas agregadas; **nunca** salidas, citas u oráculos de contratos privados |

Paralelismo: 9 carriles de escritura simultáneos sin solapamiento de archivos; **recomendado 6 de código a la vez** (L1–L5, L7) + LB1/LB2 + LV. El cuello de botella real es la puerta CI + integración (L0), no los agentes.

Cada WP: rama `jv1/<id>-<slug>` desde `integration/journey-v1`, PR contra `integration/journey-v1`, bloque `c2pro-implementation-result-v1` en el cuerpo del PR, `.c2pro/work/JV1-<id>.yaml` mínimo creado por L0.

---

## 5. Línea productiva (A)

Formato: **objetivo** · rol/agente · tamaño · bloqueado por · franja. Aceptación ≤ 3 criterios medibles. Verificación = comando real.

### Fase 0 — Arranque (dom 22/11)

**A0 · Rama de integración y línea base** · L0 Claude · S · — · dom 09:00–12:00
- Hecho: rama creada (34b4180) con las 5 hojas y `ci.yml` ampliado a `integration/**`.
- Pendiente: clasificar cada test en rojo como "preexistente" o asignado a un WP; registrar en el PR de seguimiento.
- Verificación: CI `ci-status` en `integration/journey-v1`; `make test-api && make test-web`; `cd apps/api && C2PRO_N4_SCRATCH_DSN=$DSN pytest tests/integration/analysis -q`.

**A0b · CI a verde en la rama de integración (condición de todos los despliegues)** · L0 + 4 agentes en paralelo · M · A0 · dom 22 09:00–20:00
- Primer CI real de la pila (run 44917370712, 21/11): los PR apilados nunca habían ejecutado `ci.yml`. Resultado: ruff **80 errores** (casi todos de orden de imports, autocorregibles); mypy ratchet **91 errores nuevos** (baseline 0); unit backend **19 fallos + 1 error** de ~6.200; web **3 fallos** de 1.613; Docker build, E2E smoke y P0b journey en rojo; seguridad, coherencia, core, build web y migraciones en verde.
- Reparto: Codex → ruff (`ruff check --fix`) + mypy; Claude Code → 19 unit + 1 error backend (corregir o marcar con motivo si el test es obsoleto, nunca borrar en silencio); Sonnet → 3 tests web + E2E smoke; Codex DevOps → Docker build y P0b.
- Aceptación: `ci-status` verde en `integration/journey-v1`; cada test cambiado justificado en el PR; ningún gate debilitado.
- Verificación: CI `ci-status` (required).

**A1 · Contrato de interfaces N4 (sin lógica)** · L1 Claude Code · XS · — · dom 09:00–11:00
- `N4RunOutcome` gana `coverage_status` (`COMPLETE` / `COMPLETE_WITH_GAPS` / `INCOMPLETE`, calculado en aplicación, **sin migración**: la columna `status varchar(16)` tiene CHECK cerrado) y `gap_windows`; `generate(..., attempt)`; `n4_failure_kinds.py` (OUTPUT_TRUNCATED, INVALID_ENVELOPE, PROVIDER_REJECTED_UNBILLED, PROVIDER_RESULT_UNCERTAIN, BUDGET_UNAVAILABLE); stubs `quote_page_locator`, `n4_clause_inventory`; forma de `item_data.n4_coverage` y `metadata.analysis_n4_coverage`; esquema de hallazgo compartido con el motor directo (A8) y el brazo directo (B3).
- Aceptación: mypy + ruff limpios; firmas congeladas; ningún rojo nuevo.
- Verificación: `make typecheck && cd apps/api && pytest tests/unit/analysis -q`.

### Fase 1 — Robustez y fidelidad (dom 22 – lun 23) → V1

**A2 · Ledger: reintentos, remisiones no bloqueantes, adopción del run, liquidación pesimista** · L1 Claude Code (Opus) + LV · M · A0, A1 · dom 11:00 → lun 10:00
- `create_run` (store 170-287) adopta un run RUNNING/PARTIAL con igual tenant, revisión, fuente y config (actualiza generación y fencing); `commit_window` (749-866) guarda remisiones **sin bloquear**; nuevas `retryable_windows()` y `settle_unknown_pessimistically()`.
- Aceptación: (1) al reintentar, `spent` suma ambos intentos y `reserved`/`tenants.ai_spend_reserved_usd` vuelven a 0; (2) nueva generación con misma config adopta el run sin reservar ventanas EXAMINED; con config distinta sigue bloqueada; (3) UNKNOWN solo se libera con liquidación pesimista explícita.
- Verificación: `cd apps/api && C2PRO_N4_SCRATCH_DSN=$DSN pytest tests/integration/analysis/test_n4_incremental_store_pg.py tests/unit/analysis/test_g2_n4_crossgen_pg.py tests/integration/analysis/test_n4_shared_tenant_budget_pg.py -q`.

**A3 · Runner: continuar tras fallo y reintentos acotados** · L1 Claude Code (Opus) + LV · S · A2 · lun 10:00–16:00
- Los `return` (runner 260-395) pasan a "bloquear ventana y seguir"; presupuesto agotado = bloquear restantes y parar; segunda pasada sobre `retryable_windows` con el intento en la clave de idempotencia (247-250); `C2PRO_N4_MAX_ATTEMPTS=3`; rechazo explícito no facturado (429/529/402, reutiliza `direct_provider_fallback.py:93-113`) = SETTLED a 0; truncado = coste real.
- Aceptación: (1) ventanas 3 (truncada) y 7 (JSON inválido) aciertan al 2.º intento → COMPLETE, 0 huecos; (2) si la 7 falla siempre → COMPLETE_WITH_GAPS `gap_windows=[7]`, resto EXAMINED; (3) un timeout sin coste nunca provoca 2.ª llamada.
- Verificación: `cd apps/api && C2PRO_N4_SCRATCH_DSN=$DSN pytest tests/integration/analysis/test_n4_window_runner_pg.py tests/integration/analysis/test_n4_direct_provider_settlement_pg.py -q`.
- Interruptores: `C2PRO_N4_MAX_ATTEMPTS=1` + `C2PRO_N4_CONTINUE_ON_FAILURE=0` = comportamiento actual.

**A4 · Transporte: `max_tokens` con coste y tool-use forzado** · L2 Codex · S · A0 · dom 11:00–17:00
- `llm_client.py`: `tool_choice` en `LLMRequest` (145) y `api_kwargs` (424-425); 689-691 lanzan `_partial_generation_error` con coste; `_extract_content` (791-793) serializa `tool_use.input`. `anthropic_wrapper.py`: `AIRequest` admite `tools`/`tool_choice` (64-104 → 424-435).
- Aceptación: (1) `max_tokens` → `LLMPartialGenerationError` con coste y tokens; (2) con tool_use el contenido es el JSON del input; (3) ruta de texto sin cambios.
- Verificación: `cd apps/api && C2PRO_AI_MOCK=1 pytest tests/unit/core/ai -q` (+ nuevo `tests/unit/core/ai/test_llm_client_tool_output.py`).

**A5 · Proveedor, contrato de ventana v2 e inventario de cláusulas** · L2 Codex · M · A1, A4 · dom 17:00 → lun 12:00
- Tool `record_window_findings` forzado; salida **8192** (intento 1) y **16384** (intentos ≥ 2; guarda de la línea 36 → ≤ 16384); timeout 75 → 300 s. Prompt `n4-compact-window-v2`: cita = frase completa **con cifras y porcentajes** (≤ 1200 car.) + ≤ 2 `supporting_quotes`; `_evidence` usa el regex `\s+` de VS-2; flag `quote_omits_figures`; categorías de la taxonomía EPC (§6.2) mapeadas a las 6 dimensiones; `severity_proposed` (CRITICAL/HIGH/MEDIUM/LOW) que el revisor confirma o corrige. Inventario determinista de cláusulas sobre la proyección N2 (encabezados **EN/ES/PT**), ≤ 3000 car. por mensaje, y obligación de declarar cada cláusula del inventario como `examined` (con o sin riesgo).
- Aceptación: (1) cita con salto de línea → `EXACT_MODEL_SAFE_MATCH` con offsets exactos; (2) explicación con "10 %" y cita sin él → flag activo; (3) versión del prompt incluida en `config_sha` (runner 219-227).
- Verificación: `cd apps/api && pytest tests/unit/analysis/test_v4_n4_compact_response.py tests/unit/analysis/test_v4_n4_anthropic_adapter.py tests/unit/analysis/test_n4_typed_evidence_v2.py -q`.

**A6 · Fuente única del modelo N4** · L2 Codex · S · A0 · lun 12:00–16:00
- `config.py` (raíz de `apps/api/src`): `n4_model_id` desde `C2PRO_N4_MODEL` (por defecto `claude-sonnet-4-6` hasta B7); alinea `ai_model_default` (284); override solo para N4 en `model_router.py`; precio del modelo del A/B en `model_routing.yaml`.
- Aceptación: (1) N4 usa exactamente ese modelo; el resto STANDARD no cambia; (2) modelo en `reservations.model_name` y en la respuesta de n4-findings; (3) sin caída silenciosa a `claude-sonnet-4-20250514`.
- Verificación: `cd apps/api && pytest tests/ai/test_model_router.py tests/unit/core/ai/test_anthropic_wrapper_config.py -q`.

**A7 · Bridge y grafo: huecos a revisión, consolidación, remisiones, página, N12 fuera** · L3 Claude Code (Sonnet) + LV · M · A1 (inicio); A3 y A9 (integración) · dom 14:00 → lun 18:00
- Bridge (172-272): si todas las ventanas terminaron y hay ≥ 1 resultado → update con `n4_coverage` (estado, huecos con ordinal, motivo, páginas aproximadas), `run_id`, `source_sha`; `N4RunIncomplete` solo con reservas en vuelo o 0 resultados. `nodes.py`: `risk_extractor_node` (315-340) DEGRADED con `coverage_gaps`; `critique_node` (697) con `C2PRO_N12_MODE=off` no llama al LLM y fija `human_approval_required=True`; `_contract_risk_review_summary` (545) añade cobertura y registro de remisiones. `contracts.py`: `RiskItem.page_number` y `source_locator`. `n4_consolidation.py`: fusiona spans solapados ≥ 50 % de igual categoría o misma cláusula (con trazabilidad). `n4_reference_register.py`: remisiones IN_DOCUMENT (resueltas contra la proyección/filas de cláusula), MISSING_EXTERNAL (genera hallazgo "Referenced document not provided" con cita literal) o UNRESOLVED.
- Aceptación: (1) run con huecos llega a `human_interrupt` como COMPLETE_WITH_GAPS y crea artefacto PROPOSED; (2) duplicado por solape = 1 hallazgo con traza; (3) toda cita VERIFIED lleva `page_number`.
- Verificación: `cd apps/api && pytest tests/unit/analysis/graph/test_n4_governed_graph_bridge.py -q && C2PRO_N4_SCRATCH_DSN=$DSN pytest tests/integration/analysis/test_n4_governed_graph_bridge_pg.py -q`.

**A8 · Motor alternativo "extracción directa" (red de seguridad)** · L3 Claude Code (Sonnet) · S · A7 · lun 18:00 → mar 09:00 · **despliegue 1b mar ~10:30** para que V1 pueda conmutar de motor
- `C2PRO_N4_ENGINE=direct`: una ventana con toda la proyección; salida hasta 32k por streaming (`llm_client.py:625-628`); tope 2 USD/llamada; proveedor `openai` ya existe (bridge 180-187).
- Aceptación: mismo ledger, revisión, página y exportación; el modo por ventanas no cambia; coste ≤ tope.
- Verificación: la de A7 (parte unitaria) + caso nuevo `engine=direct`.

**A9 · Localizador de cita → página** · L4 OpenCode (solo sintéticos) · XS · A1 · dom 11:00–14:00
- Aceptación: (1) encuentra la página aunque la cita tenga `[REDACTED]` o espacios distintos; (2) con cita repetida elige la más cercana al span N2; (3) si cruza páginas devuelve "pp. a–b".
- Verificación: `cd apps/api && pytest tests/unit/documents/domain/test_quote_page_locator.py -q`.

**A10 · Filas de cláusula sin pérdida de texto (+ encabezados PT)** · L4 Codex · S · A0 · dom 14:00–20:00
- Quita el truncado (845-848); parte tramos > 4000 car. por párrafo/frase con offsets exactos (continuaciones `x.y~n`); segmentos < 40 car. se unen al siguiente; regex de encabezados con Artigo/Secção/Anexo/Cláusula; `_contract_clause_coverage_omissions` deja de informar omisiones.
- Aceptación: (1) los spans cubren el 100 % del texto no blanco; (2) ninguna fila > 4000 car.; (3) importe total y fechas contractuales se siguen extrayendo.
- Verificación: `cd apps/api && pytest tests/unit/core/tasks/test_ingestion_contract_clause_reading.py tests/unit/core/tasks/test_ingestion_contract_totals.py tests/unit/analysis/test_real_splitter_boundary.py tests/unit/core/tasks/test_evidence_provenance.py tests/unit/change_intelligence/test_clause_identity_regressions.py -q`.

**A11 · Mapa de páginas y OCR de páginas sin texto** · L4 Codex · S · A10 · lun 08:00–13:00
- Persiste `parsed_text_page_spans` por revisión (`_build_text_block_index` 170-205) y lo pasa al estado del grafo; `pdf_file_parser.py` (166-198): motivo `sparse_native_text`, OCR si la página tiene < 200 car. e imágenes (añade, no reemplaza).
- Aceptación: mapa en el estado; página solo imagen → texto OCR o diagnóstico visible; págs. 9/21/55 de SolarMax recuperadas o señaladas en la interfaz.
- Verificación: `cd apps/api && pytest tests/unit/documents/application/test_document_parser_observations.py tests/unit/application/documents/test_parse_document_use_case.py tests/unit/core/tasks/test_c3a_revision_scoped_ingestion.py -q`.

**A12 · Run y cobertura fijados en el documento** · L4 Codex · XS · A7 · lun 18:00–20:30
- `ingestion_tasks.py` 1191-1196 devuelve run, SHA y cobertura N4 cuando el grafo no termina en error; 1576-1594 fija siempre `analysis_n4_*` y `analysis_n4_coverage`.
- Aceptación: documento en "waiting_for_review" con huecos tiene cobertura en metadata; n4-findings devuelve el run; la pausa HITL no reintenta sola.
- Verificación: `cd apps/api && pytest tests/unit/core/tasks/test_ingestion_analysis_retry_flag.py tests/core/test_ingestion_task_contract.py -q`.

**A13 · Entorno del piloto, topes y runbook** · L0 + Codex · S · A2–A7, A12 · preparación lun 14:00–19:00; aplicación tras fusionar A12 (~20:30)
- Variables: `C2PRO_N4_GRAPH_LEDGER_ENABLED=1`, `C2PRO_N4_GRAPH_RUN_USD=6`, `C2PRO_N4_GRAPH_WINDOW_USD=0.30`, `C2PRO_N4_GRAPH_WINDOW_CHARS=12000`, `C2PRO_N12_MODE=off`, `C2PRO_N4_MODEL`, `C2PRO_N4_ENGINE=windowed`, `C2PRO_N4_MAX_ATTEMPTS=3`, `C2PRO_SCORE_MATERIALITY_GATE=0`; presupuesto mensual del tenant; gobernador `apps/api/scripts/real_ai_governor/` con `MAX_USD=60` en el worker; Tesseract en la imagen del worker. Runbook con vuelta atrás a 799ce53.
- Aceptación: preflight verde; diff de variables registrado en el PR; topes de consola Anthropic/OpenAI confirmados por el fundador (C0).
- Verificación: `python scripts/validate_runtime_env.py`.

**A14 · Despliegues al piloto (automáticos con CI verde)** · L0 · XS c/u · CI verde en `integration/journey-v1` · lun ~21:30 (A2–A12), mar ~10:30 (A8) y mié ~19:00 (A15–A23), y los que siga habiendo
- Aceptación: SHA desplegado = HEAD con CI verde; smoke de n4-findings, revisión y Score; aviso al fundador con SHA y enlace.

### Fase 2 — Revisión, Score, exportación (lun 23 – mié 25) → V2

**A15 · Aprobación final bloqueada con huecos** · L5 Claude Code (Sonnet) + LV · S · A1 · lun 09:00–14:00
- Comprobación tras `_require_trust_ready` (`resume_workflow_use_case.py` 948-955); router HITL approve (420-470) y resume (719-795) → 409 `n4_coverage_gaps`.
- Aceptación: aprobar con huecos abiertos → 409 sin operación de resume (los cerrados manualmente en A16 no bloquean); decisiones por hallazgo → 201; rechazar sigue permitido.
- Verificación: `cd apps/api && pytest tests/unit/modules/hitl/test_final_decision_authorization_and_http_guard.py tests/unit/modules/hitl/test_review_findings_view_and_routes.py tests/unit/modules/hitl/test_resume_lineage_safety_matrix.py -q`.

**A16 · "Reintentar secciones fallidas" + campos nuevos en n4-findings** · L1 Claude Code (Opus) + LV · S · A3, A12 · mar 13:00 → mié 12:00
- `POST …/n4-retry-gaps` (nueva generación + reanálisis solo del run fijado; la ventana que vuelve a fallar se reintenta **partida en 2 subllamadas** con salida de 16k, sin cambiar los límites de ventana ni `config_sha`; si aun así falla, el revisor puede **cerrar el hueco manualmente** con motivo y revisión humana de esas páginas, registrado en auditoría y en el Excel; salta la negativa genérica 1334-1359 solo para ese run; liquidar UNKNOWN exige `settle_unknown=true`); n4-findings (1599-1760) añade página, `model_id` y textos de negocio.
- Aceptación: (1) solo se reservan ventanas hueco (y sus subllamadas); (2) 409 si cambió el SHA de la fuente o hay reserva en vuelo; (3) la revisión pendiente muestra el nuevo candidato sin duplicar revisión; un hueco cerrado manualmente cuenta como cubierto por revisión humana.
- Verificación: `cd apps/api && C2PRO_N4_SCRATCH_DSN=$DSN pytest tests/unit/analysis/test_vs1_n4_http_pg.py tests/integration/analysis/test_n4_journey_v1_gaps_pg.py -q`.

**A17 · Score automático tras la aprobación** · L5 Claude Code (Sonnet) · S · A15 · lun 14:00 → mar 12:00
- Mueve `coherence/router.py:1215-1453` a `coherence/application/project_evaluation.py` (el router delega); el router HITL lanza la evaluación con BackgroundTasks tras APPROVE correcto (approve 420, resume 719).
- Aceptación: (1) tras aprobar se persiste un CoherenceResult sin pulsar "Evaluate"; (2) `POST /coherence/evaluate` sin cambios; (3) decisiones provisionales no disparan evaluación.
- Verificación: `cd apps/api && pytest tests/core/test_coherence_dashboard_derivation.py tests/unit/coherence -q`.

**A18 · Score "Pendiente", "No evaluada" y materialidad tras flag** · L5 · S · A17 · mar 12:00 → mié 12:00
- Dashboard (1724-1848): contrato con huecos → Score global null, motivo `n4_coverage_gaps`, `pending_windows=N`; `C2PRO_SCORE_MATERIALITY_GATE=1` limita el global a ≤ 59 si hay alerta CRITICAL abierta validada.
- Aceptación: (1) subscore sin evidencia = null, nunca 0; (2) flag apagado = sin cambios; (3) aceptar un riesgo no sube el Score.
- Verificación: la de A17.

**A26 · Hallazgos validados → subscores (y enmienda de ADR-018)** · L5b Claude Code (Sonnet) · S · A17 · mar 12:00 → mié 10:00
- Hoy el Score solo lee cláusulas, cronograma y presupuesto: **no consume los hallazgos N4 revisados**. Nuevo `coherence/application/validated_findings_evidence.py` que convierte cada hallazgo **confirmado** por el revisor en evidencia de su dimensión, y `project_evaluation.py` la combina. Regla propuesta (configurable, el fundador la confirma en V2): subscore = mín(subscore por reglas existente, 100 − Σ penalización) con penalización CRITICAL 40 / HIGH 20 / MEDIUM 10 / LOW 5, suelo 0; una dimensión es "evaluada" si tiene evidencia de reglas **o** ≥ 1 hallazgo confirmado; los hallazgos rechazados no penalizan; "riesgo aceptado" **mantiene** la penalización; global = media ponderada por confianza de ADR-018 (+ puerta de materialidad A18 si se activa). Enmienda de ADR-018 en `docs/architecture/decisions/` (vía Reconciler).
- Aceptación: (1) confirmar un hallazgo HIGH de LEGAL baja el subscore LEGAL según la regla y queda trazado; (2) marcarlo como riesgo aceptado no sube el Score; (3) sin evidencia ni hallazgos la dimensión sigue en null.
- Verificación: `cd apps/api && pytest tests/unit/coherence -q` (+ nuevo `tests/unit/coherence/test_validated_findings_evidence.py`).

**A19 · Exportación Excel** · L6 Gemini CLI (sintéticos) · S · A1 (forma); A7 (datos) · lun 09:00 → mar 18:00
- `GET /projects/{id}/reports/journey.xlsx` (openpyxl): hojas Summary (Score, 6 subscores, cobertura), Findings (título, interpretación IA etiquetada, cita exacta, página, cláusula, decisión, revisor, fecha), Gaps & References.
- Aceptación: proyecto de otro tenant → 404; valores = read models; abre en Excel sin avisos.
- Verificación: `cd apps/api && pytest tests/unit/reporting -q`.

**A20 · Exportación PDF** · L6 · S · A19 · mar 18:00 → mié 14:00
- `journey.pdf` con PyMuPDF Story (sin dependencias nuevas).
- Aceptación: todas las citas con página; acentos ES/PT correctos; ≤ 5 s con 100 hallazgos.
- Verificación: la de A19.

**A21 · Interfaz de hallazgos y revisión en lenguaje de negocio** · L7 Sonnet · S · A1 · lun 09:00 → mar 18:00
- Sin jerga (N12, N2, window, "NOT APPROVABLE") → "Section k of N (pp. a–b)", "Exact quote found, page X"; hallazgos agrupados por dimensión; banner de huecos + "Retry failed sections"; aprobación final deshabilitada con motivo; página visible en cada hallazgo; al confirmar un hallazgo el revisor ve y puede corregir **severidad y dimensión** (un clic); acción "Close gap manually" con motivo.
- Verificación: `cd apps/web && pnpm vitest run "app/(app)/projects/[id]/documents/[documentId]/n4-findings/page.test.tsx" components/features/review/ReviewFindingsPanel.test.tsx components/features/review/ReviewItemCard.test.tsx`.

**A22 · Interfaz del Score y botones de exportación** · L7 · S · A18, A19, A26 · mié 12:00–16:00 (maquetación con datos simulados desde mar 18:00)
- "Not evaluated" y "Pending: N sections not analyzed"; botones Excel/PDF; al cargar, re-evalúa si la última evaluación es anterior a la última aprobación (respaldo de A17).
- Verificación: `cd apps/web && pnpm vitest run components/coherence components/features/report "app/(app)/projects/[id]/coherence"`.

**A23 · Recorrido completo sintético (e2e)** · L8 OpenClaw/OpenCode · S · A1 (rojo); A15–A22, A26 (verde) · rojo lun 12:00; verde mié 16:00–18:00
- Subir contrato → cita y página → decisiones individuales → aprobación bloqueada con huecos → Score → exportación → persistencia tras re-login sin llamadas nuevas al LLM.
- Verificación: `cd apps/web && pnpm exec playwright test src/tests/e2e/journey-v1-contract-to-export.spec.ts src/tests/e2e/s7-clerk-relogin.spec.ts`.

### Fase 3 — Aceptación (jue 26 – lun 30)

**A24 · Congelación y ejecución de aceptación** · L0 + LB2 · S · V2 · jue 26 → dom 29
- Prompts y configuración congelados con hash tras V2; C4–C6 se ejecutan una vez por el journey en el piloto; análisis directo de referencia sobre C4–C6; puntuación con B4.
- Aceptación: umbral D4 en C4–C6; ningún cambio de prompt tras ver datos de aceptación; evidencia agregada (sin datos privados) en `docs/audits/C2PRO_JOURNEY_V1_ACCEPTANCE_20261130.md`.

**A25 · Guion de demo y runbook de uso** · L0 · XS · A24 · lun 30
- `docs/runbooks/journey-v1-pilot.md` ampliado con el recorrido de demo (SolarMax público) y la vuelta atrás.

---

## 6. Línea experimental y de validación (B)

### 6.1 Corpus
6 contratos: C1 SolarMax (EN, EPC principal, 94 págs., público) y C2–C6 privados (manifiesto con nombres e IDs solo en Drive privado). Reglas: ≥ 4 proyectos distintos, ≥ 2 idiomas (EN/ES/PT), ≥ 1 escaneado; C2–C3 de desarrollo, C4–C6 de aceptación, de proyectos distintos entre sí; los carriles que ajustan prompts (L2, L3) **nunca** ven C4–C6. Cronogramas y presupuestos que falten: SINTÉTICOS (.xlsx que el parser acepta; total declarado y fecha de fin inequívocos; 2–3 incoherencias sembradas y anotadas en el oráculo).

### 6.2 Taxonomía EPC del oráculo (20 controles; C = crítico, cuenta para el 90 %)
| # | Control | Dimensión | C |
|---|---|---|---|
| 1 | Precio y moneda | BUDGET | C |
| 2 | Hitos/calendario de pagos y condiciones | BUDGET | C |
| 3 | Retenciones, avales y garantías financieras | BUDGET | C |
| 4 | Plazo / fechas de terminación garantizadas | TIME | C |
| 5 | Penalizaciones por retraso: tasa y tope | TIME | C |
| 6 | Garantías y penalizaciones de rendimiento | TECHNICAL | C |
| 7 | Limitación de responsabilidad, daño consecuencial y excepciones | LEGAL | C |
| 8 | Indemnidades | LEGAL | C |
| 9 | Resolución (causas, consecuencias, plazos) | LEGAL | C |
| 10 | Suspensión | LEGAL | — |
| 11 | Fuerza mayor | LEGAL | C |
| 12 | Variaciones / órdenes de cambio y su valoración | SCOPE | C |
| 13 | Alcance, exclusiones e interfaces | SCOPE | C |
| 14 | Pruebas y recepción (provisional/definitiva) | QUALITY | C |
| 15 | Garantía y periodo de defectos | QUALITY | C |
| 16 | Seguros y límites | LEGAL | — |
| 17 | Confidencialidad y propiedad intelectual | LEGAL | — |
| 18 | Ley aplicable y disputas | LEGAL | — |
| 19 | Impuestos, aranceles, permisos y cambio de ley | BUDGET | — |
| 20 | Remisiones a anexos y orden de prelación | SCOPE | C |

Campos por control: id, tipo, crítico, presente/ausente, cláusula, página, cita ancla, cifras esperadas, dimensión.

### 6.3 Paquetes B

**B0 · Exportador N2 offline** · LB1 OpenCode (código) / fundador (ejecución) · XS · dom 09:00–12:00 — mismo SHA de proyección que el pipeline; rechaza rutas de salida dentro del repo; sin red. `cd apps/api && pytest tests/unit/scripts/test_journey_v1_n2_export.py -q`.

**B1 · Plantilla de oráculo y taxonomía** · LB2 ChatGPT (sin datos reales) · XS · dom 09:00–12:00 — `evals/journey_v1/oracle_template.csv`, `epc_control_taxonomy.yaml` (§6.2); OK del fundador (~15 min).

**B2 · Prerrelleno con las dos familias (OpenAI + Anthropic, unión) + validación del fundador** · LB2 · S · (la unión evita sesgar el oráculo hacia uno de los brazos directos; el fundador añade lo que falte con la taxonomía) · desarrollo dom 12:00 → lun 12:00; aceptación mié 25 09:00 → vie 27 20:00 — cada oráculo validado (≤ 1 h) y fijado con hash; aceptación validada y bloqueada antes de cualquier ejecución de C2Pro sobre C4–C6.

**B3 · Brazo de análisis directo (referencia de D4)** · LB2 Claude Code · S · código dom 12:00–18:00; desarrollo lun 09:00–14:00; aceptación dom 29 — Claude y OpenAI con el contrato completo (SolarMax como PDF; privados como proyección N2), salida en el esquema del oráculo con cita y página; coste al registro de gasto. Mismo esquema que A1/A8.

**B4 · Puntuación D4** · LB1 OpenCode · S · dom 12:00 → lun 18:00 — por contrato: % críticos detectados, C2Pro − máx(directos), % citas literales con página correcta, ventanas perdidas en silencio (desde el ledger), ruido (rechazos en revisión), coste y tiempo; veredicto PASS/FAIL; coincidencias ambiguas → decide el fundador; salida determinista. `cd apps/api && pytest tests/unit/scripts/test_journey_v1_score_d4.py -q`.

**B5 · Control de gasto** · LB1 OpenCode · XS · dom 12:00–18:00 — ledger del gobernador + SQL de solo lectura sobre reservas N4 (UNKNOWN/RESERVED por importe reservado) + uso OpenAI; avisos al 70/85/100 %; **al 85 % se para la línea B**.

**B6 · Cronogramas y presupuestos SINTÉTICOS** · LB2 ChatGPT (API OpenAI) · S · desarrollo lun 12:00 → mar 18:00; aceptación mié 25 (preparado por quien no ajusta prompts) — "SINTÉTICO" en nombre y fila 1; ≥ 1 incoherencia sembrada anotada; C2Pro parsea fecha de fin y total.

**B7 · A/B de modelo N4 (Sonnet 4.6 vs 5.5)** · LB2 Claude Code (en el piloto) · S · A6, A14, B4 · mar 14:00 → mié 14:00 — métricas D4, coste y latencia en C1–C3; recomendación para V2.

**B8 · Aporte marginal de N12 (opcional)** · vie 27 – sáb 28.

### 6.4 Experimentos diferidos o condicionados (abiertos, no descartados)
| Id | Qué | Condición |
|---|---|---|
| X3 | Sidecar LangExtract (#1284) solo con Anthropic/OpenAI | si tras A5 las citas literales < 100 % |
| X4 | Docling para páginas sin texto | si A11 (Tesseract) no las recupera |
| X5 | C2Pro como MCP de solo lectura dentro de Claude/ChatGPT frente a esos modelos solos | tras la aceptación (diciembre) |
| X6 | OpenContracts (licencia MIT vs GPL-3.0) como mesa de anotación | si el oráculo pasa a ser el cuello de botella |
| X7 | Licencia PyMuPDF (AGPL/comercial) para SaaS | revisión legal del fundador en paralelo |

---

## 7. Ruta crítica, puertas y red de seguridad

Ruta crítica: **A0 → A0b → A2 → A3 → A7 → A12 → A13 → A14 → V1 (B4) → A16/A17/A26/A18/A21 → A14 → V2 → A24 → Aceptación.** Críticas también para V1: A5 (calidad de cita), A10–A11 (filas de cláusula y páginas, alimentan el Score) y la red de seguridad A8 + B3. En paralelo: A4, A9, B0–B2.

| Riesgo | Detección | Respuesta |
|---|---|---|
| R1 Regresión del ledger (doble cobro, reservas colgadas) | tests PG obligatorios + LV | `C2PRO_N4_MAX_ATTEMPTS=1` y `C2PRO_N4_CONTINUE_ON_FAILURE=0` = comportamiento actual |
| R2 El N4 mejorado no alcanza D4 en V1 | B4 sobre C1–C2 | `C2PRO_N4_ENGINE=direct` (A8) con el proveedor que mejor mida B3; si ninguno alcanza: unión ventanas + directo con la consolidación de A7. **El umbral no baja** |
| R3 Truncado incluso con 16k | ledger | `WINDOW_CHARS=8000` (cambia `config_sha`: solo documentos/revisiones nuevos) |
| R4 La guarda entre generaciones bloquea repeticiones | A2 | en pruebas, subir revisión o documento nuevo |
| R5 Ejecuciones largas (10–30 min/contrato) | piloto | heartbeat + progreso visible |
| R6 Gasto | B5 | topes de consola, `RUN_USD=6`, gobernador 60 USD, parada de B al 85 % |
| R7 Revinculación de la revisión tras reintento | A16 | cierre explícito de la revisión anterior |
| R8 Disparo del Score perdido por reinicio | A22 | re-evaluación al cargar la página |
| R9 Sin OCR en el worker | A11 | hueco visible por página, nunca silencioso |
| R10 Rojos semánticos tras la integración | A0 | se clasifican; el que bloquee la ruta crítica va primero |
| R11 Una ventana falla siempre | ledger | A16: reintento partido en 2 subllamadas; si persiste, cierre manual con motivo y revisión humana de esas páginas |
| R12 La regla de subscores no refleja el criterio experto | V2 | regla configurable (A26); el fundador la ajusta en V2 antes de congelar |

Puertas de fusión: CI `ci-status` verde + revisión del integrador; **LV obligatorio** en A2, A3, A7, A15, A16. Puerta de despliegue: CI verde (preautorizado, D10).

---

## 8. Presupuesto (100 USD)

| Partida | USD |
|---|---:|
| Runs N4 desarrollo hasta V1 | 15 |
| Runs piloto hasta V2 | 10 |
| Runs de aceptación | 10 |
| Brazos de análisis directo (B3) | 15 |
| Prerrelleno de oráculos con dos familias y sintéticos (B2, B6) | 14 |
| A/B de modelo (B7) | 12 |
| Reserva (solo con aviso al fundador) | 24 |
| **Total** | **100** |

Referencia: SolarMax por ventanas ≈ 22 ventanas → ~1,2–2 USD/run con salida ampliada (a confirmar con el primer run real).

---

## 9. Prompts de despacho por carril (para pegar)

Plantilla común (añadir al inicio de cada prompt): *"Repo AI-Gen-AI/C2Pro, base `integration/journey-v1`. Lee `docs/architecture/development/c2pro-journey-v1-plan-20261121.md` §5–§7 y ejecuta SOLO el WP indicado. Rama `jv1/<id>-<slug>`, PR contra `integration/journey-v1`, sin tocar archivos de otros carriles (§4), TDD (rojo → verde), sin trailers de atribución, bloque `c2pro-implementation-result-v1` en el PR. Prohibido: datos de contratos reales (salvo LB2), cambiar `main`, desplegar, editar backlogs."*

| Carril | Instrucción específica |
|---|---|
| L1 (Claude Code Opus) | "Ejecuta A1, luego A2 y A3 (y después A16). Prioridad máxima: es la ruta crítica. Pide revisión LV antes de fusionar." |
| L2 (Codex) | "Ejecuta A4, después A5, después A6. Respeta el esquema congelado de A1." |
| L3 (Claude Code Sonnet) | "Ejecuta A7 con stubs de A1; integra A3/A9 cuando estén en la rama; después A8." |
| L4 (Codex 2.ª) | "Ejecuta A10, A11 y A12 en ese orden. A9 lo hace OpenCode." |
| L5a (Claude Code Sonnet 2.ª) | "Ejecuta A15, A17 y A18." |
| L5b (Claude Code Sonnet 3.ª) | "Ejecuta A26 cuando A17 esté fusionado; deja la regla de penalización configurable." |
| L6 (Gemini CLI) | "Ejecuta A19 y A20 solo con datos sintéticos." |
| L7 (Sonnet/Antigravity) | "Ejecuta A21 y A22; textos de negocio, sin jerga interna." |
| L8 (OpenClaw/OpenCode) | "Ejecuta A23: primero rojo con A1, verde cuando A15–A22 estén integrados. Solo sintéticos." |
| LB1 (OpenCode/Hermes) | "Ejecuta B0, B4 y B5. Solo código y fixtures sintéticos." |
| LB2 (ChatGPT/Claude Code) | "Ejecuta B1, B2 (prerrelleno), B3, B6 y B7. Datos reales solo en el Drive privado, nunca en el repo." |
| LV (Gemini CLI) | "Auditor de solo lectura: revisa A2, A3, A7, A15, A16 contra sus criterios y este plan; informe con hallazgos; no edites nada." |

---

## 10. Siempre / Nunca

- **Siempre:** medir contra oráculo y análisis directo; citas literales con página; huecos visibles; topes de gasto activos; un archivo por carril; CI verde antes de fusionar y desplegar.
- **Nunca:** contratos privados en el repo o en modelos no autorizados; rebajar el umbral D4; ajustar prompts con datos de aceptación; promover hallazgos a TRUSTED sin decisión humana; ampliar G2–G4; nuevas campañas fuera de este plan; tocar `main`; i18n, multiusuario, roles, MCP, Docling, OpenContracts o LangExtract en la ruta crítica.

## 11. Pendiente / niebla
- Valores actuales de variables, buckets y herencia UAT del piloto (A13 los descubre).
- Comportamiento real de `route_for_review` y del rebind del candidato tras reintento (se demuestra en A16).
- Disponibilidad de salida estructurada nativa por JSON-schema con el SDK fijado (se usa tool_choice forzado, que sí está soportado).
- Regla exacta de materialidad (V2).
- Consolidación posterior de los 120 PR abiertos y actualización de `main`: después de la aceptación, como decisión aparte.
- Registro de "Integrador: Claude (primario), ChatGPT GPT-6 (suplente)" en `.claude/rules/agents.md` vía Reconciler.

## 12. Progreso
| Fase / WP | Estado |
|---|---|
| A0 rama de integración | CREADA (34b4180) |
| A0b CI a verde | PENDIENTE — primer CI: ruff 80, mypy +91, 19 unit + 1 error, 3 web, Docker/E2E/P0b en rojo |
| Plan | PROPUESTO (este PR) |
| Fase 1 (A1–A14) | PENDIENTE |
| Fase 2 (A15–A23, A26) | PENDIENTE |
| Fase 3 (A24–A25) | PENDIENTE |
| Línea B (B0–B8) | PENDIENTE |
