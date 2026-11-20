# VS-1: resultados N4 parciales visibles y honestos (propuesta de intervención única)

| Campo | Valor |
|---|---|
| Estado | **PROPUESTA para gate CORE.** Diseño autorizado (`DESIGN_ONLY_GO`); el código necesita sobre y GO específicos. STOP vigentes: N4/N12 facturables, merge y despliegue UAT |
| Evidencia de partida | `docs/audits/evidence/2026-11-20-n4-visibility-probe/` (ejecución observada sobre `799ce531` y `916808c5`) |
| Base de código propuesta | **`916808c5` (cabeza de #1276, G4 PASS_LIMITED).** Contiene la guarda que evita el doble cobro y el GET de lectura que se reutiliza. Los ficheros que hay que tocar están congelados por #1276, así que VS-1 va en **una única PR DRAFT encima de #1276** o espera a su merge; la decisión es de CORE |
| Qué resuelve | El usuario ve los candidatos N4 que ya existen, con su causa y cobertura y sin poder aprobarlos, en vez de un "Retry needed" falso que en `799ce531` vuelve a cobrar |

## 1. Cambio (8 ficheros, sin tablas, migraciones, flags ni prompt nuevos)

| # | Fichero (en `916808c5`) | Cambio mínimo |
|---|---|---|
| 1 | `analysis/adapters/graph/n4_governed_bridge.py` | Cuando el run no es `COMPLETE`, lanzar `N4RunIncomplete(N4GraphBridgeBlocked)` con `run_id`, `status`, `examined`, `total`, `persisted_result_windows` y `stopped_reason`. Los candidatos **no** se cargan en el estado del grafo |
| 2 | `analysis/adapters/graph/nodes.py` (`risk_extractor_node`) | `analysis_blocker_code`: `N4_PARTIAL_RESULTS` si hay ventanas con resultado persistido; `N4_PRIOR_RUN_RECONCILIATION_REQUIRED` si la causa es la guarda cross-generation. Se conservan `workflow_terminated`, 0 riesgos en el grafo y ningún HITL. Se añade `n4_incremental_run_id` al estado |
| 3 | `core/tasks/ingestion_tasks.py` (lista blanca de `:1181-1188` y `:1566-1572`) | Admitir esos dos códigos y persistir `analysis_n4_run_id` en `document_metadata`. Ningún reintento automático (ya es terminal) |
| 4 | `documents/adapters/http/router.py` (`_document_status_detail` y lista de documentos) | Texto honesto: *"Análisis parcial: X de Y ventanas leídas; N bloqueadas (referencias no resueltas). N candidatos propuestos, no aprobables."*, o *"Ejecución anterior pendiente de conciliación; no se reintenta para evitar un doble cobro."* `retryable=false` para ambos códigos (amplía la condición `budget_blocked` existente) |
| 5 | Ídem, endpoint de lectura | `GET /projects/{p}/documents/{d}/n4-findings`. Reutiliza la serialización de `read_n4_only_pilot_findings`, extraída a una función común. El run se elige por `metadata.analysis_n4_run_id`, con tenant, proyecto, documento y revisión vigente. Añade la cobertura por ventana (`status`, `blocked_reason`, `unresolved_refs`), `approvable:false`, `severity:"UNASSESSED"`, `impact_model_proposed` (del `claim`, marcado "no verificado"), `n12_status:"UNASSESSED"` y `original_page:"ORIGINAL_PAGE_UNVERIFIED"`. Solo lectura. La ruta del piloto no cambia |
| 6 | `apps/web/schema/api.json` + cliente orval | Regenerar |
| 7 | `apps/web/components/features/review/` | Extraer de `ReviewFindingsPanel` la parte de presentación (título, cláusula, cita verificada o "cita no localizada") a `FindingEvidence`. Crear `N4PartialFindingsPanel`, de solo lectura y sin acciones |
| 8 | `apps/web/app/(app)/projects/[id]/documents/page.tsx` | Para esos dos códigos: mostrar el texto de causa y el enlace "Ver N candidatos propuestos (no aprobables)" que abre el panel. El botón Retry ya depende de `doc.retryable` |

**Fuera de alcance:** aprobación, HITL, N12, Score, alertas, ProjectGraph, prompt v2 (hechos tipados), página del PDF original, corrección LOW→`UNASSESSED` en `AlertGenerator` (ruta COMPLETE) y referencias no bloqueantes (ADR-033, opción B). Todo eso va en gates posteriores.

## 2. Pruebas RED→GREEN (convierten la sonda en tests; PG desechable y stub)

1. **Parcial visible.** Escenario A de la sonda (una ventana con una referencia abierta):
   - `analysis_blocker_code == "N4_PARTIAL_RESULTS"` y el metadata guarda el `run_id`.
   - La lista de documentos devuelve `retryable == false` y el texto honesto.
   - El GET devuelve 4 `PROPOSED`, `coverage = {read: 1, blocked: 1, total: 2}`, la referencia `Annex 0…` y `approvable == false`.
   - **Hoy es RED:** el código de bloqueo es `null`, `retryable` es `true` y el texto habla de "several attempts".
2. **Retry no cobra ni engaña.** Escenario B sobre `916808c5`: 0 llamadas nuevas al proveedor, `analysis_blocker_code == "N4_PRIOR_RUN_RECONCILIATION_REQUIRED"` y `retryable == false`.
3. **Aislamiento.**
   - Otro tenant recibe 404; otro proyecto, 404; una revisión no vigente, 404.
   - Cuatro llamadas al GET no hacen ninguna llamada al proveedor y no cambian ni ventanas, ni recibos, ni el saldo del tenant (snapshot byte a byte).
4. **No regresión:** la suite N4 PG existente (13 tests) y los focales G4 de #1276 pasan sin cambios.
5. **Web:** Vitest para `N4PartialFindingsPanel` (estados vacío, parcial y error) y para la desaparición del botón Retry; Playwright con MSW para documento bloqueado → enlace → panel.

## 3. Matriz de aceptación observable

| Etapa | Entrada | Salida esperada visible | Evidencia API, BD y UI | QA técnico | QA funcional |
|---|---|---|---|---|---|
| FG-1a, preview aislado con stub | Contrato de prueba; stub con una referencia abierta | Documento: "Análisis parcial: 1/2 ventanas…", sin Retry; panel con 4 candidatos, cita verificada en 2 y "cita no localizada" en 2; severidad "no evaluada"; sin botones de decisión | GET JSON; filas de `n4_*` sin cambios; captura y traza de navegador; se mantiene tras recargar y volver a iniciar sesión | Frente E o Auditor: tests §2, aislamiento, cero llamadas | Una persona usuaria recorre la pantalla y confirma que entiende qué se analizó, qué falta y que nada está aprobado |
| FG-1, contrato real (necesita GO económico aparte) | Contrato autorizado; una sola ejecución N4 | Lo mismo con datos reales: documentos y ventanas procesadas, candidatos, citas verificadas y no verificadas, causas | Igual, más recibos y coste real | Ídem | Experto independiente contrasta con el oráculo: falsos positivos y omisiones críticas, con numerador y denominador; sin oráculo designado, `NOT_MEASURED_NO_ORACLE` |

Un PASS técnico no se registra como PASS funcional. FG-1a no sustituye a FG-1.

## 4. Autorización que se pide
1. **Sobre único VS-1** (rol implementación; base `916808c5`; rama `fix/vs1-n4-partial-visibility`; principal Codex o Claude; revisor independiente de otro modelo; `forbidden_paths`: alembic, supabase, workflows, `analysis/application/n4_*runner*`, `n4_incremental_store.py`, prompt N4, N12, HITL de escritura y coherence). **PR DRAFT, sin merge ni despliegue.**
2. **Decisión** entre apilar VS-1 sobre #1276 en una única PR o esperar a su merge.
3. **Preview aislado** con stub para FG-1a, cuando la PR esté lista. Es un GO de despliegue no-UAT, distinto de `UAT_DEPLOY`.
