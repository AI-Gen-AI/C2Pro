# C2Pro — WBS v2: reparación E2E (orquestación, modelo de datos, integración)

| Campo | Valor |
|---|---|
| Fecha | 2026-11-19 |
| Estado | **PROPUESTA v2. APPROVAL_WITHHELD.** No da autoridad para ejecutar nada. No autoriza sobres `.c2pro/work`, ADR, código, merges, despliegues, flags, SQL ni llamadas facturables. Todo lo que contiene es una propuesta condicionada a los gates REM-G\*. |
| Invariantes vigentes | `N4_BILLABLE=STOP` · `N12_BILLABLE=STOP` · `MERGE=STOP` · `UAT_DEPLOY=STOP` |
| Dictamen al que responde | Issue #1259, comentarios CORE **7020970699** y **7021223373** (estado `PLAN_USEFUL / APPROVAL_WITHHELD`) |
| Sustituye a | `docs/architecture/proposals/C2PRO_E2E_REMEDIATION_WBS_2026-11-19.md` (v1). La v1 queda como histórico. |
| Origen | `docs/audits/C2PRO_E2E_FUNCTIONAL_AUDIT_2026-11-19.md` (RC-01…RC-14, N4-D1…D8, N4-H1…H4) |
| Código de referencia | Runtime UAT `origin/fix/uat-n4-inherit-budget-scopes-20261118` = `799ce5315c01cdf6ec83f5716a02a509a6be1785`. Toda ruta y línea citada se ha verificado con `git show` sobre ese SHA, salvo las marcadas `NO_VERIFICADO`. |
| PRs en QA de seguridad (no se tocan) | #1276 `pr/1276` = `916808c5`, y #1277 `pr/1277` = `95fd1c06`. Las dos parten de `799ce531`. El G4 de seguridad de #1276 sigue **abierto y es prioritario**, con QA independiente del Frente E. |
| Objetivo de esta versión | Llegar al **primer resultado funcional visible** sin gastar en inferencia: cobertura honesta de los 142 candidatos SEC y referencias abiertas que no bloquean. No es un cronograma cosmético. |

---

## 1. Cambios de v1 a v2

| # | Corrección CORE | Qué decía la v1 | Qué dice la v2 |
|---|---|---|---|
| 1 | Recuento y calendario | No daba el número de WP, sumaba 166 dp como "≈4 personas × 10 semanas" y estimaba "~10 semanas" | La v1 tiene **40 WP** (4+8+7+9+4+5+3). Los 166 dp son una **estimación, no capacidad**. Su camino crítico de 58 dp equivale a ≈11,6 semanas con un ejecutor a 5 d/sem. La v2 tiene **45 WP / 175 dp**, sumas verificadas en §4. El calendario de §7 se recalcula con capacidad real: 4 d/sem, revisión 1 d por PR, latencia de gate, bloqueo externo y contingencia del 20 %. Se dan rangos y no fechas. |
| 2 | Corpus | 5 documentos | **6 documentos de 4 familias**: contrato + 2 anexos + especificación (PDF), cronograma XLSX y presupuesto XLSX. Los XLSX se leen con `ExcelFileParser` (`apps/api/src/documents/adapters/parsers/excel_file_parser.py`). También existe `BC3FileParser` (`bc3_file_parser.py`). La subida rechaza DOCX para presupuesto y cronograma (`STRUCTURED_DOCX_ERROR = "budget/schedule require .xlsx/.bc3"` en `upload_document_use_case.py:39`). `schedule_planned_finish.py:102` solo admite `.xlsx`. |
| 3 | WP1.1 | "PR de 799ce531 → main", fusión de PRs DRAFT y congelación | **Solo inventario**: SHAs, compatibilidad web/API/worker/migraciones/flags, manifiesto y una **propuesta** de baseline integrada. Unificar `main` pasa a ser WP1.2, bajo un gate independiente posterior (REM-G-BL). Sin fusión masiva ni force push. **No es requisito del replay.** |
| 4 | Nombres de gates | G0…G5 (chocaban con el G4 de seguridad de #1276) | **REM-G0…REM-G7 y REM-G-BL**. El G4 de seguridad de #1276 es otra cosa, sigue abierto y tiene prioridad. |
| 5 | WP1.4 | Arnés nuevo `apps/api/tests/replay/`, reproducir el grafo N1→N16 y el SEC "reconstruido" | **Reutiliza** `apps/api/scripts/reconcile_v41_n4_real_artifact.py`, `v41_private_cli_paths.py`, los fixtures PG de `tests/integration/analysis/test_n4_window_runner_pg.py` y el harness PG/Redis/Celery de #1277 (`qa/g3_1276/`). Las referencias inyectadas se declaran **SINTÉTICAS**. No se afirma reproducir las 24 respuestas. Se miden 50/142 citas y el recall contra un oráculo. Ningún resultado de replay se promueve a HITL real. |
| 6 | WP2.1 | La ventana pasaba a `EXAMINED` y el flag quedaba a 1 por defecto en piloto | Se separan **ventana leída / referencia resuelta / cobertura del PDF original**. `unresolved_refs` se conserva con procedencia, clase y causa. No se reetiqueta historial `SETTLED/BLOCKED` ni se tocan recibos. `EXAMINED_WITH_OPEN_REFERENCES` es **semántica derivada** y no un status SQL: las columnas son `varchar(16)` con CHECK y el literal tiene 29 caracteres. **Flag OFF por defecto también en piloto** hasta REM-G1. Ninguna referencia se marca como resuelta sin enlazar su fuente original. |
| 7 | WP2.4 | "142 candidatos llegan a N12/N13 con estado parcial; checkpoint HITL creado" | Los candidatos PARTIAL se ven en el read-model con cobertura honesta, **sin** aprobación final, TRUSTED, Score, N12 facturable ni autopromoción mientras no exista un contrato HITL independiente de revisabilidad. "0 examinadas" no se presenta nunca como "0 riesgos". Se reutiliza el `GET …/n4-only-pilot/findings` de #1276 (§6). |
| 8 | WP2.3 / WP2.8 | Un reintento automático por ventana (`…:retry1`) y una "nueva revisión" para pasar ANY-RUN | **Prohibido reintentar automáticamente** tras una respuesta inválida si antes no se ha clasificado y reconciliado su coste. `UNKNOWN = STOP`. Fencing activo y ningún efecto duplicado. En 2.8, una revisión nueva **no** es vía de escape de ANY-RUN. Solo valen una revisión genuina o una continuación diseñada y demostrada bajo autoridad. |
| 9 | WP2.7 N12 | Comparar hash de `parsed_text` + registro de redacciones, `C2PRO_N12_MODE=off` en contratos | `UNASSESSED` puede ser la respuesta correcta. No se compara hash original + marcadores para saltarse la PII. Hace falta una **atestación separada** de parser original, proyección N2 y localizadores. No se usa "N12 off" en rutas que aspiren a S1–S8/HITL. N4-only sí puede terminar sin N12/HITL, de forma explícita. Verificar por hallazgo (2.9) y analizar omisiones (2.10) son WP distintos. Que haya encabezados sin hallazgos **no prueba** una omisión jurídica. |
| 10 | WP3–4 | Tablas nuevas `contract_facts`, `cross_doc_discrepancies`, `severity_assessment` y confianza por hallazgo | Se añade el **WP3.0 de inventario**, previo a todo lo demás. `SPEC-MILESTONE-VS-SCHEDULE` **ya existe** (`structured_source_comparison.py:313`). La tarea es alimentarlo con fuentes originales y convertir `PROVISIONAL / provisional_only_not_scored` en una alerta honesta más un ítem revisable, sin duplicar el motor. El TRUSTED canónico no se degrada. Un ProjectGraph sobre PROPOSED vive en un plano PROVISIONAL sin Score aprobado. Las tablas nuevas pasan a **"condicionales al resultado de 3.0"**. |
| 11 | Coste | "$2–4" | Es una **hipótesis, no un presupuesto**. El tope del tenant es $5 según el último snapshot del 18/11 (`NO_VERIFICADO` hoy). Antes de cualquier GO (REM-G6) se verifican headroom, modelo, tokens y las llamadas no-N4 (N3, N5, N9, N12). |
| 12 | Sobres | Tabla REM-01…REM-10 con modelos asignados | Son **borradores, no permisos**. Usan el formato `c2pro-work-envelope-v1` (`work_id` debe cumplir `^C2PRO-DEV-[0-9]{2}$` y `additionalProperties: false`), los owners A–E y la separación autor/QA. WP1.4 y WP2.1 **no tocan ficheros de #1276/#1277** mientras dure su QA. |
| — | Recomendaciones que CORE rechaza | WP7.1 ("perfil único", retirar flags), RC-14 y P2-3 ("simplificar gobernanza, eliminar latches/escrows") y WP1.1 (fusionar en `main`) | **Se retiran.** WP7.1 queda en inventario y documentación de flags, **sin quitar controles** de reservas, escrow, fencing ni atestaciones. Unificar `main` solo ocurre como WP1.2 bajo REM-G-BL, con dictamen independiente. |

---

## 2. Principios de ejecución

1. **Diagnosticar sin coste antes que cualquier código de producción.** La Fase 0 no modifica `apps/api/src/**`.
2. **Reutilizar, no reescribir.** El inventario de §6 es obligatorio. Ningún WP crea un harness, motor de comparación o flujo HITL paralelo a uno que ya existe.
3. **Un único dueño por fichero caliente.** Mientras dure la QA de #1276/#1277, ningún WP toca sus ficheros (§5).
4. **Flags OFF por defecto en todos los entornos, piloto incluido.** Activar un flag es una decisión de gate y no la toma el autor.
5. **Honestidad de estado.** Leída ≠ resuelta ≠ cubierta en el original. Desconocido ≠ bajo. Parcial ≠ cero. `UNASSESSED` es un resultado legítimo.
6. **Historial inmutable.** No se reescriben filas `SETTLED`, `BLOCKED`, recibos ni `findings_sha256`.
7. **Autor ≠ revisor ≠ QA.** El Frente E está reservado al G4 de #1276. Los demás WP se revisan con el Verification Auditor (solo lectura) y con un frente distinto del autor.
8. **Toda PR es propuesta.** `MERGE=STOP` sigue vigente hasta que CORE lo levante.

---

## 3. Fases y gates

### 3.0 Vista general

| Fase | Contenido (WP) | Gate de salida | Condición de activación |
|---|---|---|---|
| **0 — Diagnóstico sin coste** | 1.6, 1.4, 1.1, 6.3-A, 5.1-T0.8 | **REM-G0** | Ya posible como propuesta. Requiere autorización CORE de los sobres §10. |
| **1 — Semántica de cobertura** | 1.3-A (ADR-033), 2.1 (flag OFF), 3.0, 1.5 | **REM-G1** | REM-G0 superado, ADR-033 aceptado por CORE y **QA-E de #1276/#1277 cerrada** (solo para tocar `n4_incremental_store.py`) |
| **2 — Primer resultado visible** | 2.4, 3.7, 5.1, 5.2-A, 2.3, 2.8, 7.2 | **REM-G2** | REM-G1 superado y #1276 resuelto (merge autorizado o cierre) |
| 3 — N12 honesto | 2.7, 2.9, 2.10, 3.1 | REM-G3 | REM-G2 y ADR-035 aceptado |
| 4 — Hechos tipados | 1.3-B, 2.5, 2.2, 2.6, 3.3, 3.6, 3.2 (cond.), 4.1, 4.2 | REM-G4 | REM-G2, 3.0 concluido y ADR-034 aceptado |
| 5 — S7 provisional | 4.3, 4.4, 3.5 (cond.), 4.5, 3.4 (cond.), 4.6, 4.8, 4.7, 5.2-B, 5.3, 5.4, 6.1, 6.2, 7.3 | REM-G5 | REM-G4 y ADR-036/037 aceptados |
| 6 — Ensayo real y UAT | 6.4, 6.5 | REM-G6 (GO de coste) → REM-G7 (UAT) | REM-G5 y CORE levanta `N4_BILLABLE`, `N12_BILLABLE` y `UAT_DEPLOY` |
| Paralelo independiente | 1.2 (unificar `main`), 7.1, 4.9 | **REM-G-BL** | Dictamen independiente, desacoplado del replay |

> REM-G4 se refiere solo a este WBS. **No es** el G4 de seguridad de #1276.

### 3.1 Fase 0: diagnóstico sin coste (ningún cambio en `apps/api/src/**`)

Rama aislada propuesta: `test/rem-p0-n4-coverage-red-20261123`, desde `799ce5315c01cdf6ec83f5716a02a509a6be1785`. **No se fusiona.** Su único fin es demostrar RED y archivar evidencia.

| Tarea | WP | dp | Responsable | Revisor independiente |
|---|---|---|---|---|
| T0.1 Salvaguarda G4 y congelación de ficheros | 1.6 | 1 | Orchestrator | Verification Auditor; el Frente E solo recibe aviso |
| T0.2 Especificación reducida del replay SEC | 1.4 | 1 | Frente A (Test/QA, DeepSeek) | Verification Auditor (Gemini) |
| T0.3 RED de `outstanding_references` (unitario + PG) | 1.4 | 2 | Frente A (Test/QA) | Frente B (ledger) + Auditor |
| T0.4 Prueba negativa e inmutabilidad de contabilidad e historial | 1.4 | 1 | Frente A (Test/QA) | Frente B |
| T0.5 Medición offline SEC: 50/142, duplicados, recall contra oráculo | 6.3-A | 2 | Frente A, en el VPS QA | Verification Auditor |
| T0.6 Inventario de SHAs, compatibilidad, migraciones y flags | 1.1 | 2 | Frente B (DevOps/Infra, Codex) | Orchestrator + Auditor |
| T0.7 Manifiesto y propuesta de baseline candidata | 1.1 | 1 | Frente B | Auditor |
| T0.8 Visibilidad parcial de los 142 (paquete offline + análisis de huecos del GET de #1276) | 5.1 | 1 | Frente A | Frente C + Auditor |

**Total Fase 0: 11 dp.** Camino crítico de la fase: T0.2 → T0.3 → T0.4 → T0.5 → T0.8 (7 dp, Frente A).

#### T0.1 — Salvaguarda G4 (1 dp)
- **Lee:** `git diff origin/fix/uat-n4-inherit-budget-scopes-20261118...pr/1276 --name-only` y el mismo diff contra `pr/1277`.
- **Entrega:** la lista congelada de §5 y la regla de verificación que se aplica a cada rama REM: `git diff --name-only 799ce531...HEAD`, cuya intersección con la lista congelada debe ser vacía.
- **Aceptación:** lista publicada en el issue coordinador (lo publica el Orchestrator, no el worker). La intersección es 0 en todas las ramas de Fase 0 y 1. El Frente E confirma por escrito que su QA no se ve afectada.

#### T0.2 — Especificación reducida del replay SEC (1 dp)
- **Lee:** `apps/api/scripts/reconcile_v41_n4_real_artifact.py` (`inspect_real_n4`, `prepare_offline_hitl_packet`, `attest_original_sec_filing_pages`), `apps/api/scripts/v41_private_cli_paths.py`, `apps/api/src/analysis/domain/n4_source_windows.py` y `docs/architecture/proposals/C2PRO_V41_FRONT_A_REAL_N4_RECOVERY_20261117.md`.
- **Entrega:** `docs/qa/REM_P0_SEC_REPLAY_SPEC.md` (ruta propuesta). Debe fijar:
  - **Entradas privadas** que no se mueven del VPS: el artefacto de evidencia con su SHA pinneado, la proyección N2 `cf8f4b7d…`, el paquete privado `7bf753a4…` y el filing SEC `23708121…`.
  - **Plan de ventanas:** `max_context_chars=12_000`, `overlap_chars=400` (los parámetros con los que el recuperador reproduce 24 ventanas).
  - **Stub de replay:** reemite por ordinal los `claim` recuperados (título, categoría, `risk_reason`, `impact`, `clause_ref` y `source_quote` **solo** en las 50 verificadas) y añade `outstanding_references = ["SYNTHETIC-REF-<ordinal>"]` con la etiqueta `synthetic=true` en el informe.
  - **Coste del stub:** `"0.000000"`, para que no se confunda con coste real.
  - **Límites declarados (no negociables):**
    - El JSON crudo del modelo y las `outstanding_references` originales **no se conservaron**. Las 24 respuestas **no se reproducen**; solo se reproduce la *clase* de resultado.
    - Las 92 citas no verificadas tienen `source_quote = None` en el artefacto (el recuperador lo exige: `N4_UNVERIFIED_QUOTE_FALSIFIED`). En el replay saldrán como `MISSING_SOURCE_QUOTE` y no como `NOT_FOUND_IN_MODEL_SAFE_SOURCE`. Por eso **N4-H2 (paráfrasis frente a normalización) no se puede discriminar** con este artefacto.
    - Las filas originales de `n4_extraction_windows` se destruyeron (`historical_window_states_reconstructible: False`).
- **Aceptación:** la especificación nombra cada límite anterior, no usa los verbos "reproduce exactamente" ni "valida riesgos" y la aprueba el Auditor.

#### T0.3 — RED de `outstanding_references` (2 dp)
- **Lee:**
  - `apps/api/src/analysis/adapters/persistence/n4_incremental_store.py`: `commit_window` en 711-829. La regla `blocked = bool(unresolved_refs or incomplete_reason)` está en 791 y el estado del run (`PARTIAL` si hay algún `BLOCKED`) en 806-818.
  - `apps/api/src/analysis/domain/n4_compact_window_response.py`: `N4WindowParsed.can_commit_as_examined` en 55-59.
  - `apps/api/src/analysis/application/n4_incremental_runner.py`: `run` en 196-421, con la llamada a `commit_window` en 410-421.
  - `apps/api/alembic/versions/20261116_0001_n4_incremental_ledger.py`: `ck_n4_windows_status IN ('PENDING','CLAIMED','EXAMINED','FAILED','BLOCKED')`, `status varchar(16)` y `ck_n4_candidate_proposed CHECK (candidate_state = 'PROPOSED')`.
  - `20261116_0002_n4_window_blocked_provenance.py`: `unresolved_refs jsonb` con CHECK de array y `blocked_reason varchar(80)`.
- **Toca (solo tests nuevos):** `apps/api/tests/integration/analysis/test_rem_p0_n4_open_references_pg.py`. Importa `_prepare`, `_runner`, `_source` y `StubProvider` de `tests/integration/analysis/test_n4_window_runner_pg.py` sin modificarlo. Se activa con `C2PRO_N4_SCRATCH_DSN`; sin DSN el módulo se salta.
- **Tests RED** (fallan hoy por la razón correcta). El flag propuesto `C2PRO_N4_OPEN_REFS_NON_BLOCKING=1` **no existe** hoy: los tests lo fijan con `monkeypatch.setenv`.
  1. `test_rem_red_open_reference_window_is_read_with_refs_preserved`
     - **Setup:** `StubProvider(missing_at=0)`.
     - **Aserciones:** fila ordinal 0 con `status == 'EXAMINED'`, `json.loads(unresolved_refs) == ["Annex 21 not uploaded"]`, `blocked_reason IS NULL`, y `outcome.examined_windows == outcome.total_windows`.
     - **RED hoy:** `status == 'BLOCKED'`.
  2. `test_rem_red_run_with_open_refs_reports_derived_coverage`
     - **Aserciones:** el run llega al estado que fije ADR-033 §3 (la opción recomendada es la A, ver §11). La consulta `count(*) WHERE status='EXAMINED' AND unresolved_refs <> '[]'::jsonb` devuelve 1 y el resultado expone `open_reference_windows == 1`.
     - **RED hoy:** run `PARTIAL` y el atributo no existe. La aserción del atributo va después de la de status, para que el RED falle por semántica y no por un `AttributeError`.
- **Contraste con tests existentes:** `test_n4_window_runner_pg.py::test_unresolved_reference_keeps_candidates_proposed_and_run_partial` y `tests/unit/analysis/test_v4_n4_compact_response.py` (aserción `not parsed.can_commit_as_examined` con referencias) **fijan el comportamiento actual**. Con el flag OFF por defecto siguen siendo válidos y **no se modifican**.
- **Aceptación:** `pytest apps/api/tests/integration/analysis/test_rem_p0_n4_open_references_pg.py -q` contra el PG desechable da exactamente 2 fallos, con el mensaje de aserción de status archivado. La salida se archiva con el SHA de la rama.

#### T0.4 — Prueba negativa e inmutabilidad (1 dp)
- **Toca:** el mismo fichero de T0.3.
- **Guardas** (VERDES hoy y deben seguir VERDES después de WP2.1):
  1. `test_rem_guard_flag_off_preserves_reference_blocking`: sin flag, ventana 0 en `BLOCKED` con `blocked_reason == 'REFERENCES_UNRESOLVED'` y run `PARTIAL`.
  2. `test_rem_guard_model_not_examined_stays_blocked[flag_on|flag_off]`: subclase `NotExaminedStub` que devuelve `"window_examined": false` en el ordinal 0. Se espera `status == 'BLOCKED'`, `blocked_reason == 'MODEL_DID_NOT_EXAMINE_WINDOW'` (el runner lo fija en `n4_incremental_runner.py:415-418`) y run distinto de `COMPLETE`.
  3. `test_rem_guard_history_and_receipts_immutable`:
     - Ejecuta con el flag OFF y toma un snapshot de `n4_extraction_windows(status, findings_sha256, blocked_reason, unresolved_refs, committed_at)` y de `n4_usage_reservations(status, spent_usd, input_tokens, output_tokens)`.
     - Activa el flag y vuelve a llamar a `commit_window` sobre la ventana `BLOCKED` con los mismos `findings`. Debe devolver `"ALREADY_BLOCKED"`.
     - Los dos snapshots deben ser idénticos byte a byte y `provider.calls` no debe crecer.
- **Aceptación:** 3 guardas (4 casos parametrizados) en verde hoy. El Frente B, como revisor, confirma que ninguna aserción depende de un estado mutable.

#### T0.5 — Medición offline SEC (2 dp, VPS QA, solo lectura)
- **Ejecuta:** `reconcile_v41_n4_real_artifact.py` con rutas autorizadas por `v41_private_cli_paths.authorize_private_input` y `authorize_private_output`, salida `0600` y nada sale del VPS.
- **Mide:**
  - (a) candidatos, claves, recibos y citas: se espera 142, 142, 24 y 50 `EXACT_N2_SOURCE` / 92 no verificadas;
  - (b) distribución de `unverified_reasons`;
  - (c) duplicados N4-H3: solape de `analysis_span` ≥ 50 % entre las 50 con span, y título normalizado entre las 142;
  - (d) recall N4-H1 contra un **oráculo humano de 20 cláusulas**. El protocolo lo redacta el Frente A y la selección de cláusulas la hace una persona revisora que no es autora de N4;
  - (e) el replay de T0.2 con flag OFF, que debe reproducir la clase "24 `BLOCKED` / 0 `EXAMINED` / run `PARTIAL` / 142 `PROPOSED`" y medir cuántas `finding_key` coinciden con las originales. Se mide; no se presupone. El PG desechable sale de `qa/g3_1276/run_g3_rootless_pg.sh` en una checkout de `pr/1277`, usado en solo lectura y sin modificarlo (interfaz `NO_VERIFICADO`).
- **Aceptación:** informe privado con las 5 métricas y su SHA. Si no hay persona revisora disponible, (d) se reporta como `NOT_MEASURED_NO_ORACLE` y no se estima. Declara N4-H2 `NOT_TESTABLE_WITH_ARTIFACT`. **Ningún candidato se promueve.**

#### T0.6–T0.7 — Inventario de baseline (WP1.1, 3 dp)
- **Lee:**
  - el ahead/behind de `main`, de `799ce531`, `feat/c2pro-core-pilot-20261104` y `release/core-candidate-20261108`;
  - las cabezas Alembic (la última en el runtime es `20261118_0001_n4_actual_provider_provenance.py`) y los espejos Supabase;
  - los flags con `git grep -ohE "C2PRO_[A-Z0-9_]+" 799ce531 -- apps/ | sort -u`;
  - las PR DRAFT #1253–#1258, #1270, #1271, #1273, #1276 y #1277.
- **Entrega:** `docs/audits/REM_P0_BASELINE_INVENTORY.md` (ruta propuesta), con una matriz de compatibilidad entre web, API, worker, scheduler, migraciones y flags, y un **manifiesto propuesto** en el mismo documento (no en CI). Termina con una **propuesta** de baseline candidata y su orden de integración, que se decidirá en REM-G-BL.
- **Aceptación:** cada SHA desplegado viene con su fuente. Lo que no se pueda leer de Railway o Vercel queda `NO_VERIFICADO`. No hay ninguna acción de git sobre `main`.

#### T0.8 — Visibilidad parcial de los 142 (1 dp)
- **Lee:** `pr/1276:apps/api/src/documents/adapters/http/router.py:1543-1680` (`read_n4_only_pilot_findings`) y `pr/1276:apps/api/tests/unit/analysis/test_g2_n4_partial_read_p1.py`.
- **Entrega 1 (privada, sin código):** una vista de cobertura generada con `prepare_offline_hitl_packet`, encabezada por este banner: *"24/24 ventanas leídas y liquidadas · 0 `EXAMINED` en el ledger · referencias abiertas: no conservadas · 50 citas en N2 (50/50 localizadas en página SEC) · 92 sin literal · 0 decisiones humanas · NO es HITL"*.
- **Entrega 2:** análisis de huecos del GET de #1276. Ya ofrece `status = PARTIAL_UNASSESSED`, `ledger_status`, `total_windows`, `total_findings`, `review_state = PROPOSED`, `n2_quote_status`, `pdf_quote_status = UNVERIFIED`, `n12_status = UNASSESSED`, `original_pdf_coverage = UNVERIFIED`, `trusted = False`, paginación y solo lectura. **Le falta** `examined_windows`, `blocked_reason` y `unresolved_refs` por ventana, la distinción leída/resuelta/original y el uso fuera del marcador `n4_only_pilot`.
- **Aceptación:** la vista no contiene la palabra "riesgos" sin el calificativo "candidatos propuestos". El análisis queda adjunto como insumo de WP5.1 y WP2.4.

**Evidencia que exige REM-G0:** salida RED de T0.3 (2 fallos con su motivo), guardas de T0.4 en verde, informe de T0.5, inventario de T0.6–T0.7, vista y huecos de T0.8, intersección vacía de T0.1 y revisión del Auditor. Todo con SHA.

### 3.2 Fase 1: semántica de cobertura y WP2.1 con flag OFF

| Tarea | WP | dp | Responsable | Revisor | Ficheros |
|---|---|---|---|---|---|
| T1.1 ADR-033 acotado (borrador) | 1.3-A | 2 | Frente A | Auditor + Frente B; **dictamina CORE** | `docs/architecture/decisions/ADR-033-n4-coverage-semantics.md` (nuevo, propuesto) |
| T1.2 Runner: flag y resultado | 2.1 | 1 | Frente A (Backend) | Frente B | `apps/api/src/analysis/application/n4_incremental_runner.py` (no tocado por #1276/#1277) |
| T1.3 Store: regla de bloqueo parametrizada | 2.1 | 1 | Frente A (Backend) | Frente B + Auditor | `apps/api/src/analysis/adapters/persistence/n4_incremental_store.py`. **Bloqueado** hasta el cierre de la QA de #1276/#1277 y el rebase (§5). |
| T1.4 GREEN de los RED de Fase 0 | 2.1 | 1 | Frente A (Test/QA) | Frente B | tests de T0.3/T0.4 |
| T1.5 Replay SEC con flag ON (scratch) | 2.1 | 1 | Frente A (VPS) | Auditor | ninguno en el repo |
| T1.6 Inventario 3.0-a: contratos tipados, eventos, reglas | 3.0 | 2 | Frente B | Frente C | solo lectura |
| T1.7 Inventario 3.0-b: entradas S7/ProjectGraph y alertas | 3.0 | 2 | Frente C | Frente B | solo lectura |
| T1.8 Corpus-a: contrato, 2 anexos y especificación sintéticos | 1.5 | 2 | Frente C (Test/QA) | Auditor | `apps/api/tests/fixtures/rem_corpus/**` (propuesto) |
| T1.9 Corpus-b: cronograma y presupuesto XLSX + `oracle.yaml` | 1.5 | 2 | Frente C (Test/QA) | Frente B | ídem |

**Total Fase 1: 14 dp.** Camino crítico de la fase: T1.1 → aceptación CORE → (bloqueo externo) → T1.3 → T1.4 → T1.5.

**T1.1 — ADR-033** (2 dp). El esquema está en §11. Aceptación: ocupa una página o menos, no introduce status SQL, deja el flag OFF por defecto, deja explícito que no hay aprobación y CORE lo acepta. **Sin ADR aceptado no empieza T1.2.**

**T1.2 — Runner** (1 dp).
- El flag `C2PRO_N4_OPEN_REFS_NON_BLOCKING` se lee **una vez** en el constructor como parámetro explícito `open_refs_non_blocking: bool = False`, nunca dentro del store.
- `N4RunOutcome` (líneas 64-73) se amplía con `open_reference_windows: int = 0` y `open_references_total: int = 0`, calculados en `_outcome` (124-173) con una SELECT adicional sobre `unresolved_refs`.
- Test: `tests/unit/analysis/test_rem_n4_runner_outcome_fields.py::test_outcome_counts_open_reference_windows_without_changing_status`.

**T1.3 — Store** (1 dp).
- `commit_window(..., refs_block_window: bool = True)`. La regla pasa a ser `blocked = bool(incomplete_reason) or (bool(unresolved_refs) and refs_block_window)`.
- `blocked_reason` vale `REFERENCES_UNRESOLVED` solo si las referencias bloquean.
- `unresolved_refs` se persiste **siempre**. Los strings existentes no cambian de forma: la clase y la causa se derivan en WP2.2 y no se escriben aquí.
- La rama de idempotencia (`ALREADY_EXAMINED` / `ALREADY_BLOCKED`, 745-748) queda intacta, así que **no se reetiqueta historial**.
- `reserve_call`, recibos y presupuesto no se tocan.

**T1.4 — GREEN** (1 dp). Aceptación: los 2 RED de T0.3 pasan con el flag ON. Las 3 guardas de T0.4 siguen verdes. Pasan sin cambios `test_n4_window_runner_pg.py`, `test_n4_incremental_store_pg.py`, `test_n4_governed_graph_bridge_pg.py`, `test_v4_n4_compact_response.py`, `test_n4_partial_ledger_p0.py`, `test_n4_n12_partial_cost_and_nonblocking.py`, `test_v41_n4_billed_artifact_recovery.py` y el resto de `tests/unit/analysis/test_*n4*`.

**T1.5 — Replay SEC con flag ON** (1 dp). Aceptación en el PG scratch: 24/24 con semántica `EXAMINED_WITH_OPEN_REFERENCES`, con las referencias **SINTÉTICAS** declaradas. 0 recibos reales y 0 llamadas de red (el stub cuenta llamadas). La métrica de `finding_key` reproducidas sale de T0.5. El informe dice literalmente: *"no demuestra comportamiento con referencias reales del modelo"*.

**T1.6 / T1.7 — Inventario WP3.0** (4 dp). Produce `docs/audits/REM_WP30_TYPED_CONTRACT_INVENTORY.md` (ruta propuesta), con una tabla de decisión *existe → reutilizar / extender / falta* para cada uno de estos componentes (verificados en `799ce531`):
- `apps/api/src/coherence/cross_document/`:
  - `comparators.py`: reglas `DET-CRS-CONBUD`, `DET-CRS-WBSBUD`, `DET-CRS-BOMBUD`, `DET-CRS-NEGMARGIN`, `DET-CRS-RISKCONT` y `RULE_SCHEDULE_OVERRUNS_DEADLINE`;
  - `findings.py`: `CrossDocFinding`, `CrossDocNotAssessed` y `CrossDocProvisional` (`reason="SCHEDULE_NOT_APPROVED_BASELINE"`);
  - `inputs.py`: `DatedSource`, `ProjectCrossDocInputs`, `BASIS_SOURCE_OBSERVED` y `BASIS_APPROVED_BASELINE`;
  - `identity.py`, `assembly.py` y `signal_adapter.py`.
- `apps/api/src/analysis/adapters/graph/structured_source_comparison.py`: `compare_original_source_rows` (217-324) y `SPEC-MILESTONE-VS-SCHEDULE` (313).
- `apps/api/src/core/tasks/project_graph_tasks.py`: `persist_provisional_source_discrepancies` (100+), que emite el evento `project_graph.source_discrepancies_observed`, y `run_project_graph_once` (182). El lector es `reporting/adapters/sources/sqlalchemy_current_state_sources.py:271`.
- `apps/api/src/change_intelligence/` (`semantic_diff.py`, `structural_diff.py`, `anchor_resolver.py`, `change_impact_report.py`).
- `apps/api/src/wbs/intelligence/` (`contracts/proposal.py`, `contracts/qualification.py`, `application/service.py`).
- `apps/api/src/project_state/` (`trusted_artifact_projector.py`, `materialize_trusted_state.py`, `domain/lifecycle.py`).
- `apps/api/src/temporal/` (`project_event_repository.py`, `snapshot_writer.py`, `revision_change_orchestrator.py`, `impact_assessment.py`).
- `apps/api/src/alerts/domain/enums.py`: `AlertSeverity` solo tiene `low/medium/high/critical` y hay una migración de conformidad de enum, `20260824_0001_alerts_severity_enum_conformance.py`.
- `apps/api/src/coherence/alert_generator.py`: `_map_risk_severity`, que hace fallback a `LOW` en las líneas ~330-352.
- `apps/api/src/modules/hitl/`: `FindingDecisionKind{RISK, CRITIQUE}` y `FindingDecisionAction{CONFIRMED, CORRECTION_PROPOSED, DISMISSED, NEEDS_INFO}`, además de `review_findings_view.py` y `finding_decision_router.py`.
- `apps/api/src/analysis/adapters/persistence/risk_source_clause_binding.py::load_trusted_risk_source_clause_ids`.
- Las restricciones de ADR-026, ADR-030, ADR-031 y ADR-032.

Aceptación: cada tabla nueva propuesta en la v1 (`contract_facts`, `cross_doc_discrepancies`, `severity_assessment` y confianza por hallazgo) recibe el veredicto `NECESARIA` / `CUBIERTA_POR <componente>` / `EXTENSIÓN_DE <componente>`, con su justificación.

**T1.8 / T1.9 — Corpus de 6 documentos** (4 dp).
- Contrato, Anexo A (programa de hitos), Anexo B (pruebas de aceptación) y especificación técnica, en PDF sintético. Cronograma y presupuesto en XLSX con cabeceras que `ExcelFileParser` reconozca: `task/actividad/tarea/activity`, fecha de fin y una fila de total declarado.
- Tres conflictos sembrados y documentados en `oracle.yaml`:
  - FAT del Anexo A en D frente a FAT del cronograma en D+21 (debe disparar `SPEC-MILESTONE-VS-SCHEDULE`);
  - terminación del contrato frente a fin del cronograma, con +92 días;
  - total del presupuesto igual al precio + 300.000 €.
- Que BC3 produzca filas `declared_total` utilizables por los comparadores está `NO_VERIFICADO` y queda fuera del corpus mínimo.
- Aceptación: los 6 ficheros parsean en un test unitario sin red, y `oracle.yaml` enumera riesgos, hechos y discrepancias esperados, cada uno con su localizador.

**Evidencia que exige REM-G1:** ADR-033 aceptado. RED → GREEN con flag ON y sin cambios con flag OFF. Guardas en verde. Replay SEC 24/24 declarado sintético. Inventario 3.0 entregado. Corpus parseado. Intersección vacía con #1276/#1277 hasta su cierre. Autor ≠ revisor demostrado en cada PR.

### 3.3 Fases posteriores (nivel WP)

| WP | dp | Dueño | Depende de | Contenido corregido | Activación |
|---|---|---|---|---|---|
| **2.4** Propagación parcial al read-model | 4 | A | 2.1, ADR-033 | `n4_governed_bridge.py:192-200` deja de lanzar si hay ≥1 ventana con resultado persistido. Devuelve candidatos y cobertura (`examined`, `read_with_open_refs`, `blocked_ordinals`, `total`) con `risk_extraction_outcome="PARTIAL_UNASSESSED"`. Se mantiene `human_approval_required=True`. **Ni TRUSTED, ni Score, ni N12 facturable, ni autopromoción.** El fallo honesto (`nodes.py:99-129`, `340-359`) queda solo para "0 ventanas con resultado". Si 2.4 añade campos a `graph/schema.py`, espera al cierre de #1276. | REM-G1 + #1276 resuelto |
| **3.7** Severidad no evaluada | 2 | B | 3.0 | Opción mínima sin migración: un riesgo sin severidad no genera alerta canónica `LOW` y queda como ítem revisable "Sin evaluar". La opción con enum o columna nueva depende de 3.0 y necesita su ADR. | REM-G1 |
| **5.1** Read-models | 3 (1 ya en T0.8) | A + FE | 2.4, #1276 | Extender el GET de #1276, sin duplicarlo, con cobertura por ventana. Pasa a ser tenant-scoped y no exclusivo del piloto. | #1276 resuelto |
| **5.2** Panel de revisión (A: cobertura; B: severidad y página) | 5 | FE (asociado a A) | 5.1 | Banner "leídas X/Y · referencias abiertas N · cobertura del PDF original: no verificada". "0 examinadas" nunca se muestra como "0 riesgos". Sin aprobación en bloque. | REM-G1 |
| **2.3** Resiliencia por ventana | 4 | A | 2.1 | Solo continúa tras fallos **clasificados con coste reconciliado** (p. ej. `INVALID_PROVIDER_ENVELOPE` con `account_call` liquidado). `PROVIDER_RESULT_UNCERTAIN`, `USAGE_UNAVAILABLE`, `UNVERIFIED_PROVIDER_IDENTITY`, la réplica en vuelo y el presupuesto siguen siendo **STOP** (`UNKNOWN=STOP`). **Sin reintento automático.** | REM-G1 |
| **2.8** Reproceso legítimo | 3 | B | 2.3, #1276 | Runbook. La guarda ANY-RUN de #1276 (`_CROSS_GENERATION_RECEIPT_SQL` en `reserve_call`) filtra por `document_revision_id` + `source_sha256`, así que una revisión nueva *técnica* la esquivaría. **Esa vía queda prohibida.** Solo se admite una revisión genuina, o una continuación diseñada (reutilizar ventanas `SETTLED`, sin volver a facturarlas) que se demuestre bajo autoridad. Test: `critique → risk_extractor` no crea un run nuevo (N4-H4). | #1276 resuelto |
| 7.2 Causas explícitas | 2 | B | — | Todo `UNASSESSED`, `BLOCKED` o `SKIPPED` lleva un `reason_code`. Se quita `except Exception: pass` en `ai_extraction.py:~194` y se sustituye por un log estructurado, **sin** cambiar el veredicto. | REM-G1 |
| **2.7** Atestación N12 separada | 3 | A | ADR-035 | Atestaciones independientes de parser original, proyección N2 y localizadores. **No** se compara hash original + marcadores para saltarse la PII (`n12_source_attestation.py`). `UNASSESSED` sigue siendo válido. | REM-G2 |
| **2.9** N12 verificador por hallazgo | 5 | A | 2.7, 2.4 | Lotes acotados por `finding_key`, con veredicto `SUPPORTED / NOT_SUPPORTED / SEVERITY_DISPUTED / NEEDS_CONTEXT / UNASSESSED`. No aprueba nunca. Facturable solo después de REM-G6. | REM-G2 |
| **2.10** Análisis de omisiones | 3 | A | 2.7 | Separado de 2.9. Un encabezado N2 sin hallazgo genera un "hueco de cobertura a revisar" y **no** una "omisión jurídica". | REM-G2 |
| 3.1 RiskItem v2 (campos aditivos) | 3 | B | 3.0 | Campos opcionales sin migración JSONB, validados contra el contrato v1. | REM-G2 |
| 1.3-B ADR-034…037 | 3 | A/B/C | 3.0 | Solo para lo que 3.0 declare `NECESARIA`. | REM-G2 |
| 2.5 Severidad propuesta | 5 | A | 3.1 | Cambia el prompt (`N4_WINDOW_SYSTEM_PROMPT`) y `config_sha256` (`n4_incremental_runner.py:219-227`). Los runs antiguos no se mezclan con los nuevos. | REM-G3 |
| 2.2 Resolver determinista de referencias | 5 | A (delegable a C) | 3.3 | Clases `RESOLVED_IN_DOCUMENT / RESOLVED_IN_FAMILY / NOT_IN_PROJECT / AMBIGUOUS`. **Solo se marca resuelta con un enlace a la fuente original.** | REM-G3 |
| 2.6 Consolidación entre ventanas | 3 | C | T0.5 (c) | Agrupa sin borrar evidencia. | REM-G3 |
| 3.3 Familia documental | 4 | B | 3.0 | RLS y FK dentro del mismo proyecto. | REM-G3 |
| 3.6 Offset → página | 4 | B | 3.0 | Reutiliza la atestación de páginas de `attest_original_sec_filing_pages`. | REM-G3 |
| 3.2 Hechos tipados (**condicional**) | 6 | B | 3.0, ADR-034 | Solo si 3.0 concluye que `ProjectCrossDocInputs` / `DatedSource` no bastan. | REM-G3 |
| 4.1 Hechos en la llamada N4 | 5 | A | 2.5, 3.2 o equivalente | Sin coste de entrada adicional; la salida crece. | REM-G3 |
| 4.2 Enrutado de especificaciones y anexos | 3 | A | 3.3 | `workflow.py:336-350`. | REM-G3 |
| **4.3** Alimentar los comparadores existentes | 5 | C | 4.1, 3.0 | `compare_original_source_rows` y `SPEC-MILESTONE-VS-SCHEDULE` reciben fuentes originales. Sin motor nuevo; las regex quedan como respaldo marcado. | REM-G4 |
| **4.4** Discrepancia → alerta honesta + ítem revisable | 5 | C | 4.3, 3.7 | Convierte `PROVISIONAL / provisional_only_not_scored` en una alerta con dos fuentes y un ítem HITL que reutiliza `finding_decision_router`. | REM-G4 |
| 3.5 Persistencia de discrepancias (**condicional**) | 4 | B | 3.0 | Solo si `project_event` y `persist_provisional_source_discrepancies` no bastan. | REM-G4 |
| **4.5** ProjectGraph en plano PROVISIONAL | 6 | C | 4.4 | `run_project_graph_once` con `trust_scope=PROVISIONAL`. **No escribe** Coherence/Health canónicos ni TRUSTED. ADR-026 intacto. | REM-G4 |
| 3.4 Confianza por hallazgo (**condicional**) | 5 | B | 3.0, ADR-036 | Derivada de las decisiones HITL existentes. | REM-G4 |
| 4.6 Anclaje riesgo → cláusula | 3 | C | 3.6 | `load_trusted_risk_source_clause_ids`. | REM-G4 |
| 4.8 Score validado vs pendiente | 4 | C | 4.5 | Que se reconozca un riesgo no sube el Score. | REM-G4 |
| 4.7 Propuestas WBS (ADR-030) | 5 | C | 4.4 | Solo propuestas. | REM-G4 |
| 5.3 / 5.4 Vistas de discrepancias y Coherence | 5 / 3 | FE (asociado a C) | 4.4 / 4.8 | — | REM-G4 |
| 6.1 Suite de replay en CI | 4 | E (tras G4) | T0.3–T0.4 | Sintéticos en CI; SEC solo en el VPS. | REM-G4 |
| 6.2 E2E del corpus con PG/Redis/Celery reales y stub | 5 | D (tras G4) | 4.8, 1.5 | Reutiliza el harness `qa/g3_1276/`. | REM-G4 |
| 7.3 Panel por etapa | 4 | B + FE | 7.2 | — | REM-G4 |
| 6.3 (resto: B, corpus) | 3 | E + Auditor | 6.2 | Recall y precisión por categoría; el umbral lo fija CORE. | REM-G5 |
| 6.4 Ensayo real acotado | 3 | ORC + B | REM-G6 | Gasto autorizado de forma explícita. | REM-G6 |
| 6.5 UAT en navegador S1–S8 | 3 | E + persona HITL | 6.4 | — | REM-G7 |
| 1.2 Unificar `main` | 3 | ORC + B | T0.6–T0.7 | Integración ordenada, CI verde, **sin force push ni fusión masiva**. | REM-G-BL |
| 7.1 Inventario de flags | 2 | B | T0.6 | Documenta flags y su dueño. **No elimina controles.** | REM-G-BL |
| 4.9 Impacto de revisión | 5 | C | 4.4 | Reutiliza `change_intelligence`. | Posterior a REM-G7 |

---

## 4. Árbol WBS v2

```
C2PRO-REM v2
├── 1 Base y diagnóstico ................................. 6 WP · 20 dp
│   ├── 1.1 Inventario SHAs/compat./migr./flags + manifiesto + propuesta baseline (3)
│   ├── 1.2 Unificación main bajo REM-G-BL (3, condicional)
│   ├── 1.3 ADR: 1.3-A ADR-033 acotado (2) + 1.3-B ADR-034..037 condicionales (3) = 5
│   ├── 1.4 Replay SEC reducido + RED + inmutabilidad (4)
│   ├── 1.5 Corpus 6 docs / 4 familias + oráculo (4)
│   └── 1.6 Salvaguarda G4 #1276/#1277 y congelación de ficheros (1)
├── 2 Orquestación N4/N12 ................................ 10 WP · 38 dp
│   ├── 2.1 Referencias abiertas no bloqueantes, flag OFF (3)
│   ├── 2.2 Resolver determinista con enlace a fuente (5)
│   ├── 2.3 Resiliencia sin reintento automático; UNKNOWN=STOP (4)
│   ├── 2.4 Parcial → read-model con cobertura honesta, sin aprobación (4)
│   ├── 2.5 Severidad propuesta (5)
│   ├── 2.6 Consolidación entre ventanas (3)
│   ├── 2.7 N12: atestación separada parser/N2/localizadores (3)
│   ├── 2.8 Reproceso legítimo (no escape de ANY-RUN) (3)
│   ├── 2.9 N12: verificador por hallazgo (5)
│   └── 2.10 Análisis de omisiones (3)
├── 3 Modelo de datos .................................... 8 WP · 32 dp
│   ├── 3.0 Inventario de contratos tipados/eventos/reglas (4)
│   ├── 3.1 RiskItem v2 aditivo (3)
│   ├── 3.2 Hechos tipados (6, CONDICIONAL a 3.0)
│   ├── 3.3 Familia documental (4)
│   ├── 3.4 Confianza por hallazgo (5, CONDICIONAL a 3.0)
│   ├── 3.5 Persistencia de discrepancias (4, CONDICIONAL a 3.0)
│   ├── 3.6 Offset → página (4)
│   └── 3.7 Severidad no evaluada sin LOW por defecto (2; columna/enum CONDICIONAL)
├── 4 Integración ........................................ 9 WP · 41 dp
│   ├── 4.1 Hechos en llamada N4 (5)   4.2 Enrutado spec/anexos (3)
│   ├── 4.3 Alimentar comparadores existentes (5)   4.4 Discrepancia → alerta + ítem (5)
│   ├── 4.5 ProjectGraph PROVISIONAL (6)   4.6 Anclaje cláusula (3)
│   ├── 4.7 Propuestas WBS (5)   4.8 Score validado/pendiente (4)
│   └── 4.9 Impacto de revisión (5)
├── 5 API y UI ........................................... 4 WP · 16 dp
│   └── 5.1 Read-models sobre GET #1276 (3) · 5.2 Panel revisión (5) · 5.3 Discrepancias (5) · 5.4 Coherence (3)
├── 6 Verificación ....................................... 5 WP · 20 dp
│   └── 6.1 Suite replay (4) · 6.2 E2E corpus (5) · 6.3 Recall/precisión A+B (5) · 6.4 Ensayo real (3) · 6.5 UAT S1–S8 (3)
└── 7 Observabilidad (sin retirar controles) ............. 3 WP · 8 dp
    └── 7.1 Inventario de flags (2) · 7.2 Causas explícitas (2) · 7.3 Panel por etapa (4)
```

| Bloque | WP | dp | Comprobación |
|---|---|---|---|
| 1 | 6 | 20 | 3+3+5+4+4+1 |
| 2 | 10 | 38 | 3+5+4+4+5+3+3+3+5+3 |
| 3 | 8 | 32 | 4+3+6+4+5+4+4+2 |
| 4 | 9 | 41 | 5+3+5+5+6+3+5+4+5 |
| 5 | 4 | 16 | 3+5+5+3 |
| 6 | 5 | 20 | 4+5+5+3+3 |
| 7 | 3 | 8 | 2+2+4 |
| **Total** | **45** | **175** | 20+38+32+41+16+20+8 |

Los 175 dp son una **estimación de esfuerzo, no de capacidad**. Los WP condicionales (3.2, 3.4, 3.5 y 1.2; 19 dp) pueden reducirse a 0 si 3.0 los declara cubiertos.

---

## 5. Conflictos de ficheros con #1276 y #1277

Ficheros congelados (unión de los dos diffs contra `799ce531`):
- **Código:** `analysis/adapters/graph/schema.py`, `analysis/adapters/persistence/n4_incremental_store.py`, `analysis/application/n4_only_pilot.py`, `analysis/application/n4_only_pilot_policy.py`, `core/tasks/document_recovery.py`, `core/tasks/ingestion_tasks.py`, `documents/adapters/http/router.py`, `documents/application/trigger_document_analysis_use_case.py`, y solo en #1276 `documents/application/n4_only_enqueue_recovery.py` y `documents/application/n4_only_ingestion_effects_guard.py`.
- **Tests y QA:** `tests/unit/analysis/test_g2_n4_*.py`, `test_g3_n4_*.py`, `docs/qa/G2_N4_ONLY_PILOT_QA.md` y `qa/g3_1276/**` (#1277).

| WP | Fichero congelado afectado | Ventana en que puede tocarse |
|---|---|---|
| 1.4 / T0.3–T0.4 | ninguno (tests nuevos; uso de `qa/g3_1276/` en solo lectura) | Inmediata |
| 1.5, 1.1, 3.0, 6.3-A | ninguno | Inmediata |
| 2.1 T1.2 (runner) | ninguno | Tras ADR-033 |
| **2.1 T1.3** | `n4_incremental_store.py`. #1276 toca `_locked_run` y `reserve_call`; 2.1 toca `commit_window`. No se solapan las líneas, pero sí el fichero. | **Tras el dictamen QA-E del G4 de #1276/#1277 y su merge autorizado o cierre**, con rebase sobre el resultado |
| 2.4 | `graph/schema.py` (si añade campos de estado) | Tras resolver #1276 |
| 5.1 | `documents/adapters/http/router.py`, `n4_only_pilot_policy.py` | Tras resolver #1276; se **extiende** su GET |
| 2.8 | `n4_incremental_store.py` (ANY-RUN), `ingestion_tasks.py`, `document_recovery.py`, `trigger_document_analysis_use_case.py`, `n4_only_enqueue_recovery.py` | Tras resolver #1276 |
| 2.3 | ninguno (solo el runner) | Tras REM-G1 |
| 4.2 | `trigger_document_analysis_use_case.py` (si el enrutado pasa por ahí, `NO_VERIFICADO`) y `workflow.py` (libre) | Tras resolver #1276 |
| 6.1 / 6.2 | `qa/g3_1276/**` (solo se reutiliza; los cambios van en una copia nueva o con autorización de D/E) | Tras cerrar el G4 de #1276 |
| Resto (bloques 3, 4 salvo 4.2, 5.3, 5.4 y 7) | ninguno | Según su fase |

---

## 6. Inventario de reutilización

| Componente existente (en `799ce531` salvo que se indique) | Lo reutiliza |
|---|---|
| `apps/api/scripts/reconcile_v41_n4_real_artifact.py` (`inspect_real_n4`, `prepare_offline_hitl_packet`, `attest_original_sec_filing_pages`) | 1.4, 6.3-A, T0.8, 3.6 |
| `apps/api/scripts/v41_private_cli_paths.py` | 1.4, 6.3-A |
| `tests/integration/analysis/test_n4_window_runner_pg.py` (`StubProvider`, `_prepare`, `_runner`, `_source`) y `test_n4_incremental_store_pg.py` (`_new_authority`, `_seed_identity`, `_seed_caps`) | 1.4, 2.1, 2.3 |
| Harness `qa/g3_1276/**` (solo en `pr/1277`) | 1.4 (PG desechable), 6.2 |
| `GET /projects/{project_id}/documents/{document_id}/n4-only-pilot/findings` (`pr/1276`, `router.py:1543`) | 5.1, 2.4, 5.2 |
| Guarda cross-generation `_CROSS_GENERATION_RECEIPT_SQL` (`pr/1276`) | 2.8 (se respeta y no se esquiva) |
| `analysis/domain/n4_source_windows.py::plan_n4_source_windows` | 1.4, 2.2 |
| `analysis/domain/risk_provenance.py::classify_quote` | 2.4, 6.3 |
| `N4RunOutcome.blocked_result_windows` (runner, ya distingue "BLOCKED con resultado persistido") | 2.1, 2.4 |
| `coherence/cross_document/*` (`comparators`, `findings`, `inputs`, `signal_adapter`) | 3.0, 4.3, 4.4 |
| `analysis/adapters/graph/structured_source_comparison.py` (`SPEC-MILESTONE-VS-SCHEDULE`, la regla de terminación y la de precio) | 4.3 |
| `core/tasks/project_graph_tasks.py::persist_provisional_source_discrepancies` / `run_project_graph_once` | 3.5 (puede evitarlo), 4.4, 4.5 |
| `coherence/alert_generator.py` | 3.7, 4.4 |
| `modules/hitl/` (`finding_decision.py`, `finding_decision_router.py`, `review_findings_view.py`) | 3.4, 4.4, 5.2 |
| `apps/web/components/features/review/ReviewFindingsPanel.tsx` | 5.2 |
| `change_intelligence/application/*` | 4.9 |
| `wbs/intelligence/*` (ADR-030) | 4.7 |
| `temporal/*` (eventos, snapshots), ADR-031 | 4.5, 4.9 |
| `analysis/adapters/persistence/risk_source_clause_binding.py::load_trusted_risk_source_clause_ids` | 4.6 |
| `documents/adapters/parsers/excel_file_parser.py` (actividades, `declared_total_rows`) y `bc3_file_parser.py` | 1.5, 4.3 |
| `structured_source_trust` (ADR-032) | 4.3, 4.5 |

---

## 7. Calendario realista

**Supuestos** (los fijó CORE):
- un dueño por frente, de A a E;
- 4 días efectivos por semana;
- 1 día de revisión independiente por PR;
- 20 % de contingencia en el escenario esperado;
- inicio el 23/11/2026.

**Supuestos añadidos** (para que CORE los ajuste):
- latencia de decisión de cada gate: 1 día en el optimista, 3 en el esperado;
- bloqueo externo por la QA del G4 de #1276/#1277: 0 días en el optimista, 5 en el esperado;
- **festivos de fin de año no incluidos** (añadirían entre 1 y 2 semanas);
- los Frentes D y E no tienen capacidad hasta que cierre el G4 de #1276.

**Camino crítico recalculado.** El recurso cuello de botella es el **Frente A**, que es dueño de N4 y N12.

| Tramo | Esfuerzo CP (dp) | PR | Gates |
|---|---|---|---|
| Fase 0 (T0.2 → T0.3 → T0.4 → T0.5 → T0.8) | 7 | 1 | REM-G0 |
| Fase 1 (1.3-A → T1.2 → T1.3 → T1.4 → T1.5) | 2 + 3 + 1 = 6 | 2 | REM-G1 (incluye la aceptación de ADR-033) |
| Fase 2 (2.4 → cola UI 5.2-A) | 4 + 1 | 1 | REM-G2 |
| Fases 3–4, Frente A en serie (2.3, 2.7, 2.9, 2.10, 2.5, 4.1, 4.2) | 4 + 3 + 5 + 3 + 5 + 5 + 3 = 28 | 7 | REM-G3, REM-G4 |
| Cola de integración (4.3-final 2 → 6.2 5 → 6.4 3 → 6.5 3) | 13 | 2 | REM-G5, REM-G6, REM-G7 |
| **Total** | **59 dp** | **13 PR** | **8 gates** |

**Cálculo:**

| Hito | Optimista (sin contingencia) | Esperado (con 20 %) |
|---|---|---|
| REM-G0 (diagnóstico demostrado) | 7 + 1 + 1 = 9 d → **≈2,5 semanas** | (7 + 1 + 3) × 1,2 = 13,2 d → **≈3,5 semanas** |
| REM-G1 (WP2.1 en verde, flag OFF) | +6 + 2 + 1 = 18 d → **≈4,5 semanas** | +(6 + 2 + 3 + 5) × 1,2 → 32,4 d → **≈8 semanas** |
| **REM-G2 (primer resultado funcional visible en producto)** | +5 + 1 + 1 = 25 d → **≈6,5 semanas** | +(5 + 1 + 3) × 1,2 → 43,2 d → **≈11 semanas** |
| REM-G7 (UAT S1–S8) | +28 + 7 + 13 + 2 + 5 = 80 d → **≈20 semanas** | +(28 + 7 + 13 + 2 + 15) × 1,2 → 121,2 d → **≈30–31 semanas** |

**Lectura del calendario:**
- La v1 prometía unas 10 semanas. Con las mismas cifras a 5 d/sem salían 11,6 semanas, y con supuestos realistas la v2 da entre **20 y 31 semanas** hasta el UAT.
- El primer resultado *visible* sin coste llega en Fase 0: la vista de cobertura honesta de los 142, en unas 2,5–3,5 semanas.
- El primer resultado visible *en producto* (REM-G2) queda en unas 6,5–11 semanas.
- **Ruta casi crítica:** el Frente C (3.0, 4.3, 4.4, 4.5, 4.6, 4.8 y 4.7, más el UI asociado) suma unos 48 dp. Empieza en Fase 1 y termina cerca del Frente A. Si 3.0 declara `NECESARIA` alguna tabla condicional, el Frente B (unos 41 dp) puede pasar a ser crítico.
- **Revisión:** son unas 30 PR en total. Con E y D bloqueados por el G4, el Auditor y la revisión cruzada entre frentes absorben la carga, y la latencia de revisión es el riesgo de calendario más probable.

---

## 8. Gates

| Gate | Evidencia exigida | Dictamina | STOP si… |
|---|---|---|---|
| **REM-G0** | RED de T0.3 (2 fallos con motivo), guardas de T0.4 en verde, informe de T0.5 con límites declarados, inventario de baseline, vista de los 142 con banner honesto, intersección vacía con #1276/#1277 | Auditor (Gemini) + Orchestrator; CORE informado | algún RED falla por un motivo ajeno a la semántica; alguna guarda falla hoy; el informe afirma reproducción exacta o validación; algún fichero congelado aparece tocado |
| **REM-G1** | ADR-033 aceptado; RED → GREEN con flag ON y suite N4 existente sin cambios con flag OFF; `window_examined=false` sigue en `BLOCKED`; historial y recibos idénticos; replay SEC 24/24 declarado sintético; inventario 3.0; corpus parseado | Auditor + Frente B; **CORE acepta el ADR** | cambio de semántica con flag OFF; cualquier cambio en filas o recibos históricos; un status SQL nuevo; el flag ON por defecto; un fichero congelado tocado antes de que cierre la QA-E |
| **REM-G2** | Read-model con cobertura (`leídas/total`, referencias abiertas, `BLOCKED` por causa, `original_pdf_coverage = UNVERIFIED`); los 142 visibles en UI de preview **sin** aprobación, TRUSTED ni Score; test de que "0 examinadas" ≠ "0 riesgos"; 3.7 sin `LOW` por defecto; 2.3 sin reintento automático | Auditor + E (si está libre); CORE | aparece un estado TRUSTED, un Score o una autopromoción; se crea una revisión HITL implícita; hay un reintento sin coste reconciliado |
| REM-G3 | N12 con atestaciones separadas; veredicto por hallazgo o `UNASSESSED` con causa (stub); omisiones como "hueco a revisar" | Auditor + CORE | se usa "N12 off" en una ruta S1–S8; un hash original + marcadores sustituye a la atestación |
| REM-G4 | Corpus: hechos con cita; resolver con enlace a la fuente; ADR condicionales solo donde 3.0 lo justificó | Auditor + CORE | una tabla nueva sin veredicto `NECESARIA` en 3.0 |
| REM-G5 | E2E del corpus con worker real y stub: los 3 conflictos llegan como alerta con dos fuentes y como ítem revisable; ProjectGraph PROVISIONAL sin Score aprobado; TRUSTED intacto | E + Auditor + CORE | se degrada el TRUSTED canónico; aparece un motor de comparación duplicado |
| **REM-G6** (GO de coste) | Headroom del tenant verificado hoy (no el snapshot del 18/11), modelo, tokens estimados por nodo (N3, N4, N5, N9, N12) y presupuesto máximo explícito | **CORE** | headroom insuficiente o no verificable; cualquier `UNKNOWN` sin reconciliar en el ledger |
| REM-G7 | Ensayo real autorizado y UAT en navegador S1–S8 con persona HITL real y readback | CORE | falta evidencia en cualquier fila del Entregable 7 de la auditoría |
| **REM-G-BL** | Propuesta de baseline (T0.7), CI verde en la candidata, sin force push, con dictamen independiente | Auditor + CORE | fusión masiva, gates de CI debilitados o el G4 de #1276 sin cerrar |

---

## 9. Riesgos y supuestos

| Riesgo o supuesto | Prob. | Impacto | Mitigación |
|---|---|---|---|
| **Límites del replay:** referencias sintéticas, JSON crudo no conservado, 92 citas sin texto y filas de ventana destruidas | Cierta | Alto | Se declara en la especificación T0.2. El replay demuestra la *mecánica* del ledger, no el comportamiento del modelo. N4-H2 queda `NOT_TESTABLE`. Ningún resultado de replay llega a HITL. |
| Las `finding_key` del replay no coinciden con las originales | Media | Medio | Se mide y se informa (T0.5 e). Nunca se presupone. |
| La QA-E de #1276/#1277 se alarga | Media | Alto (bloquea T1.3, 2.4, 2.8, 5.1) | T1.2, 3.0 y 1.5 avanzan en paralelo. T1.3 lleva un parche mínimo listo para rebase. |
| No hay persona disponible para el oráculo de 20 cláusulas | Media | Medio | `NOT_MEASURED_NO_ORACLE`; el recall no se estima. |
| La semántica "run COMPLETE con referencias abiertas" se lee como completitud total | Media | Alto | ADR-033 obliga a mostrar la cobertura derivada junto al status. La alternativa B mantiene `PARTIAL` (§11). |
| El inventario 3.0 descubre que hacen falta tablas | Media | Medio (+19 dp) | Ya están contadas como condicionales. |
| La guarda ANY-RUN impide el UAT real | Alta | Alto | WP2.8 solo con una continuación diseñada y demostrada. Sin atajos. |
| Coste real mayor que la hipótesis de $2–4 (N3, N5, N9 y N12 además de N4; el XLSX pasa por N9 vía LLM, `NO_VERIFICADO` en el entorno) | Media | Alto | REM-G6 con medición por nodo. El tope de $5 no se da por vigente. |
| Revisión independiente saturada (E y D en G4) | Alta | Medio | Revisión cruzada entre frentes más Auditor; autor ≠ revisor sigue siendo obligatorio. |
| Los datos del SEC salen del VPS | Baja | Alto | Las rutas de `v41_private_cli_paths`, la salida `0600` y la regla de no subir nada al repo. |
| Despliegue real (Railway/Vercel) | — | — | `NO_VERIFICADO`; T0.6 lo registra con su fuente. |

---

## 10. Borradores de sobres (Fase 0 y Fase 1)

> **BORRADOR — no crear hasta autorización CORE.** Notas sobre los borradores:
> - `work_id` sigue el patrón obligatorio `^C2PRO-DEV-[0-9]{2}$`. Los números 16 a 21 son **propuestos** y los confirma el Orchestrator; podrían colisionar.
> - El esquema tiene `additionalProperties: false`, así que la marca de borrador va solo en comentario.
> - `campaign_id` es propuesto.

```yaml
# BORRADOR — no crear hasta autorización CORE (WBS v2, Fase 0, WP1.4 + 6.3-A + T0.8)
schema: c2pro-work-envelope-v1
schema_version: 1
work_id: C2PRO-DEV-16            # PROPUESTO
campaign_id: CORE-REM-E2E-V2-P0-20261123   # PROPUESTO
role: qa
base_sha: 799ce5315c01cdf6ec83f5716a02a509a6be1785
branch: test/rem-p0-n4-coverage-red-20261123
risk_class: material
scope:
  - write the reduced SEC replay specification docs/qa/REM_P0_SEC_REPLAY_SPEC.md declaring synthetic references and non-reproducible raw outputs
  - add RED tests apps/api/tests/integration/analysis/test_rem_p0_n4_open_references_pg.py for open references and derived coverage
  - add guard tests for flag-off blocking, window_examined=false and immutable window/receipt history
  - run reconcile_v41_n4_real_artifact.py read-only on the private QA VPS and report 50/142 citations, duplicates and oracle recall
  - produce the private coverage-honest view of the 142 proposed candidates and the gap analysis of the PR 1276 partial GET
out_of_scope:
  - any change under apps/api/src
  - any billable provider call, deploy, merge, flag activation or SQL against shared environments
  - promoting any candidate to HITL, TRUSTED, Score or ProjectGraph
  - claiming exact reproduction of the 24 historical model responses
  - modifying files under review in PR 1276 or PR 1277
allowed_tools:
  - github_repository_read
  - code_reference_search
  - focused_local_tests_with_synthetic_data
  - disposable_postgres_scratch_database
  - private_vps_read_only_recovery
  - scoped_repository_write_for_tests_and_qa_docs_only
forbidden_paths:
  - apps/api/src/**
  - apps/api/alembic/**
  - supabase/migrations/**
  - .github/workflows/**
  - qa/g3_1276/**
  - apps/api/tests/unit/analysis/test_g2_n4_*.py
  - apps/api/tests/unit/analysis/test_g3_n4_*.py
  - apps/api/tests/integration/analysis/test_n4_window_runner_pg.py
  - apps/api/tests/unit/analysis/test_v4_n4_compact_response.py
  - .c2pro/control/**
acceptance_criteria:
  - two RED tests fail against 799ce531 on the window status assertion and archived output carries the branch SHA
  - guard tests pass today for flag off, window_examined false (flag on and off) and immutable history and receipts
  - private report states 142 candidates, 24 settled receipts, 50 verified N2 quotes, 92 unverified, N4-H2 not testable, recall measured or NOT_MEASURED_NO_ORACLE
  - no SEC private content leaves the QA VPS
  - intersection of changed files with PR 1276 and PR 1277 files is empty
required_tests:
  - C2PRO_N4_SCRATCH_DSN=<disposable> pytest apps/api/tests/integration/analysis/test_rem_p0_n4_open_references_pg.py -q
  - C2PRO_N4_SCRATCH_DSN=<disposable> pytest apps/api/tests/integration/analysis/test_n4_window_runner_pg.py -q
  - pytest apps/api/tests/unit/analysis/test_v41_n4_billed_artifact_recovery.py -q
  - python scripts/development/validate_c2pro_control.py
evidence_required:
  - red_output_with_failure_reason
  - green_guard_output
  - private_sec_measurement_report_sha256
  - frozen_file_intersection_empty
  - independent_review_by_non_author
review_policy: independent_principal
worker_selection:
  preferred: null
  eligible_principals: [claude_code, codex]
  eligible_subordinates: []
  selected: null
timeout_resource_policy: zero_cost_diagnostic_only_no_provider_no_deploy_no_merge
```

```yaml
# BORRADOR — no crear hasta autorización CORE (WBS v2, Fase 0, WP1.1)
schema: c2pro-work-envelope-v1
schema_version: 1
work_id: C2PRO-DEV-17            # PROPUESTO
campaign_id: CORE-REM-E2E-V2-P0-20261123
role: specialist
base_sha: 799ce5315c01cdf6ec83f5716a02a509a6be1785
branch: docs/rem-p0-baseline-inventory-20261123
risk_class: normal
scope:
  - inventory web API worker scheduler SHAs, Alembic and Supabase heads and C2PRO flags with their source
  - record compatibility matrix and a proposed release manifest inside docs/audits/REM_P0_BASELINE_INVENTORY.md
  - propose (not execute) a candidate integrated baseline and ordering for later REM-G-BL decision
out_of_scope:
  - any git operation on main, merge, rebase of other PRs or force push
  - CI or deployment configuration changes
  - closing or relabelling draft PRs
allowed_tools: [github_repository_read, github_ci_read, code_reference_search, scoped_repository_write_for_audit_evidence_only]
forbidden_paths: [apps/**, .github/workflows/**, apps/api/alembic/**, supabase/migrations/**, qa/**, .c2pro/control/**]
acceptance_criteria:
  - every SHA has a cited source or NO_VERIFICADO
  - manifest is a proposal and not wired to CI
  - baseline proposal explicitly not a prerequisite of replay
required_tests: [python scripts/development/validate_c2pro_control.py]
evidence_required: [exact_sha_inventory, independent_review_by_non_author]
review_policy: independent_principal
worker_selection: {preferred: codex, eligible_principals: [claude_code, codex], eligible_subordinates: [], selected: null}
timeout_resource_policy: read_only_inventory_no_runtime_access_mutation
```

```yaml
# BORRADOR — no crear hasta autorización CORE (WBS v2, Fase 1, WP1.3-A ADR-033)
schema: c2pro-work-envelope-v1
schema_version: 1
work_id: C2PRO-DEV-18            # PROPUESTO
campaign_id: CORE-REM-E2E-V2-P1      # PROPUESTO
role: specialist
base_sha: 799ce5315c01cdf6ec83f5716a02a509a6be1785
branch: docs/rem-p1-adr033-n4-coverage-semantics
risk_class: architecture
scope:
  - draft ADR-033 (one page) distinguishing window read, reference resolved and original document coverage, PARTIAL_WITH_COVERAGE and no approval
out_of_scope: [code, migrations, flags, new SQL status values, HITL contract definition]
allowed_tools: [github_repository_read, code_reference_search, scoped_repository_write_for_adr_only]
forbidden_paths: [apps/**, qa/**, .github/**, .c2pro/control/**]
acceptance_criteria:
  - no new varchar(16) status value; semantics derived from existing columns
  - flag default OFF in every environment including pilot
  - explicit statement that coverage never implies approval, TRUSTED or Score
  - accepted by CORE
required_tests: [python scripts/development/validate_c2pro_control.py]
evidence_required: [core_acceptance_comment, independent_review_by_non_author]
review_policy: principal_and_challenger
worker_selection: {preferred: claude_code, eligible_principals: [claude_code, codex], eligible_subordinates: [], selected: null}
timeout_resource_policy: docs_only
```

```yaml
# BORRADOR — no crear hasta autorización CORE (WBS v2, Fase 1, WP2.1; T1.3 bloqueada hasta cierre QA-E #1276/#1277)
schema: c2pro-work-envelope-v1
schema_version: 1
work_id: C2PRO-DEV-19            # PROPUESTO
campaign_id: CORE-REM-E2E-V2-P1
role: implementation_lead
base_sha: 799ce5315c01cdf6ec83f5716a02a509a6be1785   # se re-fija al SHA resultante tras resolver #1276
branch: fix/rem-p1-n4-open-refs-nonblocking-flag-off
risk_class: material
scope:
  - add explicit open_refs_non_blocking constructor parameter (default False) to N4IncrementalRunner reading C2PRO_N4_OPEN_REFS_NON_BLOCKING once
  - add open_reference_windows and open_references_total to N4RunOutcome
  - add refs_block_window parameter (default True) to commit_window; persist unresolved_refs always; no history relabel
  - turn REM-P0 RED tests GREEN with flag on; keep all existing N4 tests unchanged with flag off
out_of_scope:
  - reserve_call, budget, receipts, fencing, ANY-RUN guard, idempotency
  - bridge, nodes, workflow, schema.py, routers, N12, HITL, alerts
  - enabling the flag in any environment
  - marking any reference as resolved
allowed_tools: [github_repository_read, code_reference_search, focused_local_tests_with_synthetic_data, disposable_postgres_scratch_database, scoped_repository_write]
forbidden_paths:
  - apps/api/alembic/**
  - supabase/migrations/**
  - apps/api/src/analysis/adapters/graph/**
  - apps/api/src/documents/**
  - apps/api/src/core/tasks/**
  - apps/api/src/analysis/application/n4_only_pilot*.py
  - qa/**
  - .github/workflows/**
acceptance_criteria:
  - with flag off every pre-existing N4 unit and PG test passes unmodified
  - with flag on an open-reference window is EXAMINED with unresolved_refs preserved and blocked_reason NULL
  - window_examined false remains BLOCKED with MODEL_DID_NOT_EXAMINE_WINDOW
  - historical BLOCKED/SETTLED rows and reservations byte-identical
  - n4_incremental_store.py touched only after QA-E verdict and resolution of PR 1276/1277 and rebase
required_tests:
  - C2PRO_N4_SCRATCH_DSN=<disposable> pytest apps/api/tests/integration/analysis -k "n4 or rem_p0" -q
  - pytest apps/api/tests/unit/analysis -k "n4" -q
  - canonical GitHub CI required gates
evidence_required: [red_to_green_transcript, flag_off_regression_suite, immutable_history_diff, sec_synthetic_replay_report, independent_review_by_non_author]
review_policy: principal_and_challenger
worker_selection: {preferred: codex, eligible_principals: [claude_code, codex], eligible_subordinates: [], selected: null}
timeout_resource_policy: no_provider_no_deploy_no_merge_flag_default_off
```

```yaml
# BORRADOR — no crear hasta autorización CORE (WBS v2, Fase 1, WP3.0 + WP1.5)
schema: c2pro-work-envelope-v1
schema_version: 1
work_id: C2PRO-DEV-20            # PROPUESTO
campaign_id: CORE-REM-E2E-V2-P1
role: specialist
base_sha: 799ce5315c01cdf6ec83f5716a02a509a6be1785
branch: docs/rem-p1-typed-contract-inventory-and-corpus
risk_class: normal
scope:
  - inventory coherence/cross_document, structured_source_comparison, project_graph_tasks events, change_intelligence, wbs/intelligence, project_state, temporal, alerts domain, hitl finding decisions and ADR-026/030/031/032 constraints
  - give a NECESARIA / CUBIERTA_POR / EXTENSION_DE verdict for contract_facts, cross_doc_discrepancies, severity_assessment and per-finding trust
  - build synthetic 6-document 4-family corpus (contract, 2 annexes, specification PDF; schedule and budget XLSX) with oracle.yaml and three seeded conflicts
out_of_scope: [schema or code changes, real customer documents, new comparator engine]
allowed_tools: [github_repository_read, code_reference_search, focused_local_tests_with_synthetic_data, scoped_repository_write_for_audit_and_fixtures_only]
forbidden_paths: [apps/api/src/**, apps/api/alembic/**, supabase/migrations/**, qa/**, .github/workflows/**, .c2pro/control/**]
acceptance_criteria:
  - every v1 proposed table has an evidence-cited verdict
  - SPEC-MILESTONE-VS-SCHEDULE reuse path documented
  - all six corpus files parse offline; oracle lists expected findings with locators
required_tests: [pytest apps/api/tests/unit/analysis/graph/test_structured_source_comparison.py -q]
evidence_required: [inventory_document, corpus_parse_transcript, independent_review_by_non_author]
review_policy: independent_principal
worker_selection: {preferred: null, eligible_principals: [claude_code, codex], eligible_subordinates: [], selected: null}
timeout_resource_policy: read_only_inventory_and_synthetic_fixtures
```

---

## 11. Esquema de ADR-033 acotado (una página como máximo)

**ADR-033 — Semántica de cobertura N4: ventana leída, referencia resuelta y cobertura original** (Estado: *Propuesto*)

1. **Contexto.** Hoy `commit_window` bloquea la ventana si `unresolved_refs` no está vacío (`n4_incremental_store.py:791`). Por eso el SEC dio 24 ventanas liquidadas, 0 `EXAMINED`, run `PARTIAL` y 142 candidatos inalcanzables. Las columnas de status son `varchar(16)` con CHECK: no admiten valores nuevos sin migración, y no se propone ninguna.
2. **Tres ejes independientes:**
   - **Leída** (`window_read`): hay recibo `SETTLED`, resultado persistido (`findings_sha256`) y `window_examined=true`.
   - **Referencias:** para cada entrada de `unresolved_refs`, una clase (`OPEN`, `RESOLVED_IN_DOCUMENT`, `RESOLVED_IN_FAMILY`, `DOCUMENT_ABSENT`, `AMBIGUOUS`), una procedencia (ventana, cita del modelo, `synthetic` sí/no) y una causa. **Se marca `RESOLVED_*` solo con un enlace a la fuente original** (documento, revisión, localizador). Hasta WP2.2 todas son `OPEN`.
   - **Cobertura original:** la cobertura del PDF original y sus páginas es independiente. Vale `UNVERIFIED` mientras no exista la atestación de WP2.7 y WP3.6.
3. **Representación sin status nuevo.**
   - `EXAMINED_WITH_OPEN_REFERENCES` es una etiqueta **derivada**: `status='EXAMINED'` con `unresolved_refs <> '[]'`.
   - Con el flag ON, el run puede llegar a `COMPLETE`, que significa "todas las ventanas leídas" (como ya dice el docstring de `N4IncrementalRunner.run`). **Toda lectura** de ese run expone a la vez `open_reference_windows` y `open_references_total`.
   - **Alternativa B** (para que CORE elija): conservar `PARTIAL` y exponer `examined == total`.
   - `window_examined=false` sigue en `BLOCKED/MODEL_DID_NOT_EXAMINE_WINDOW`.
4. **`PARTIAL_WITH_COVERAGE`.** Es la etiqueta del read-model cuando hay al menos una ventana sin resultado leído. Muestra los candidatos de las ventanas leídas junto a `{leídas, total, bloqueadas por causa, referencias abiertas, original=UNVERIFIED}`. "0 leídas" se presenta como "no analizado", **nunca** como "0 riesgos".
5. **No aprobación.** Ninguna de estas etiquetas implica aprobación, TRUSTED, Score, N12 facturable, alerta canónica ni promoción. Los candidatos siguen en `PROPOSED` (`ck_n4_candidate_proposed`). La revisabilidad HITL la definirá un contrato independiente posterior.
6. **Historial.** No se reetiquetan filas `SETTLED`, `BLOCKED` ni recibos, y no se recalculan `findings_sha256`. Los runs anteriores al flag conservan su semántica.
7. **Activación.** `C2PRO_N4_OPEN_REFS_NON_BLOCKING` queda **OFF por defecto en todos los entornos**. Activarlo es una decisión de gate (posterior a REM-G1) y la toma CORE.
8. **Consecuencias.** Desbloquea WP2.4 y WP5.1 sin migraciones. Obliga a que los consumidores del status del run lean también la cobertura derivada. No resuelve RC-02 por sí solo.
9. **Fuera de alcance.** El resolver (2.2), N12 (2.7, 2.9, 2.10), la severidad (2.5) y la persistencia de discrepancias (3.5).

---

---

*Elaborado por el rol Planner (solo lectura) a partir de la auditoría y los dictámenes CORE; revisado por el auditor contra `.c2pro/schemas/work-envelope.schema.yaml` y el código `799ce531`/`pr/1276`.*
