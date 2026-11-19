# C2Pro — Dictamen crítico: ruta funcional mínima y primer gate funcional

| Campo | Valor |
|---|---|
| Fecha | 2026-11-19 |
| Responde a | Instrucción CORE "Prioridad absoluta: funcionamiento real del producto" (19/11/2026) |
| Autores | Claude Code (auditor) y rol Planner (solo lectura). Las afirmaciones de código se han comprobado en `799ce5315c01cdf6ec83f5716a02a509a6be1785` y `pr/1276` |
| Naturaleza | Dictamen y propuesta. **No autoriza ni ejecuta** correcciones de producto. Siguen vigentes `N4_BILLABLE=STOP`, `N12_BILLABLE=STOP`, `MERGE=STOP` y `UAT_DEPLOY=STOP`. La autorización vigente es solo la de Fase 0 (DEV-16, DEV-17). |
| Relación con la WBS v2 | La WBS v2 queda como catálogo técnico de referencia. **Este documento la sustituye como criterio de priorización**: se avanza por gates funcionales, no por paquetes. |

---

## 0. Respuesta directa a la pregunta de CORE

**¿Qué dejar de hacer?**
1. Medir el avance por PRs, tests verdes, PASS técnicos o número de documentos de propuesta. Hay 1.161 ficheros de test backend, 19 propuestas de arquitectura en noviembre y ~10 PRs DRAFT apiladas, y ningún contrato real analizado y visible.
2. Añadir capas de control (escrow, atestaciones, latches, guardas) **sin un caso funcional que las exija**. Los controles existentes se mantienen. Lo que se detiene es el crecimiento de controles por delante de la función.
3. Tratar los fixtures sintéticos o con *mocks* como evidencia de producto. Solo sirven como evidencia técnica.
4. Mantener caminos paralelos de producto. La ruta N4-only de #1276 sirve como **instrumento de ensayo**, no como segundo flujo de usuario.
5. Ofrecer al usuario un "Retry" que vuelve a cobrar N4 sin arreglar la causa (`router.py:1155-1170`, `retryable=True`).
6. Planificar en semanas-esfuerzo antes de haber medido la productividad real.

**¿Qué reutilizar?** Parsing + N2, el planificador de ventanas y el ledger N4 con recibos, el recuperador SEC (`reconcile_v41_n4_real_artifact.py`) y su paquete de 142 candidatos con página, los arneses de evaluación `n4_n12_real_ai_eval.py` (omisiones esperadas) y `n4_n12_representative_eval.py`/`_gate.py` (N12 como oráculo adversarial y gate independiente), el módulo `golden/`, el GET de lectura parcial de #1276, `ReviewFindingsPanel` y las decisiones HITL por hallazgo, los comparadores existentes (`SPEC-MILESTONE-VS-SCHEDULE`, terminación, precio, `coherence/cross_document/*`), `structured_source_trust` (ADR-032), ProjectGraph TRUSTED, `AlertGenerator`, y las pruebas G4 y el harness de #1277.

**¿Qué corregir primero?** Que **el resultado de N4 llegue al usuario, completo o parcial, con su causa y sin poder aprobarse por accidente**, y que **N4 pida lo que el producto necesita**. Hoy solo pide riesgos; obligaciones, hitos, garantías, penalizaciones y condiciones económicas no forman parte del prompt. Son las correcciones C1–C5 del §3.

**¿Qué evidencia demostrará que esta vez construimos el producto correcto?** Un contrato real autorizado, analizado **dentro de C2Pro** y comparado con un **oráculo humano independiente hecho a ciegas**. Se mide recall de elementos críticos, precisión, fidelidad de cita a página del PDF original y cobertura. Se repite con un **segundo contrato no visto durante el desarrollo**. El dictamen funcional lo emite alguien distinto del equipo técnico (§5).

---

## 1. Cadena mínima y dónde se rompe hoy

La cadena mínima para que un usuario vea el análisis de un contrato real es esta (lectura de código de `799ce531`, sin ejecución):

| # | Eslabón | Componente | Estado | Qué ve el usuario |
|---|---|---|---|---|
| 1 | Subida | `documents/adapters/http/router.py:629` → `_enqueue_document_processing` | Implementado; subida real verificada en UAT (#1259) | "Upload accepted" |
| 2 | Parsing → disparo automático del análisis | `core/tasks/ingestion_tasks.py:2043-2080` → `trigger_document_analysis_use_case.py:111` | Implementado; N2 verificado (46/46 hashes) | Pendiente de análisis |
| 3 | Grafo: N1 → N2 → N3 → N4 gobernado | `ingestion_tasks.py:1015-1146` → `orchestrator_factory.py:52`; `nodes.py:315-337` | Implementado; UAT se ejecuta pero se bloqueó por presupuesto (gen1/gen2) | — |
| 4 | **Run N4 PARTIAL → candidatos** | `n4_governed_bridge.py:192-200` lanza la excepción **antes** de leer los candidatos (`:202-219`) | **ROTO (confirmado)** | Nada |
| 5 | **Causa del bloqueo** | `nodes.py:343-347` y lista blanca `ingestion_tasks.py:1525-1528`: solo admite códigos de presupuesto; `termination_reason` no se persiste en `documents` | **ROTO (confirmado)** | Causa invisible |
| 6 | **Texto y acción en la UI** | `router.py:425-426`: "did not complete after several attempts. Retry to try again." y `retryable=True` | **ROTO (confirmado)**: texto falso (hubo un solo intento) y un Retry que vuelve a cobrar sin arreglar | "Retry needed" |
| 7 | Artefacto, revisión, alertas | `document_artifact_completion.py:41,92`; `nodes.py:931`; `trusted_materialization.py:763` | No se alcanzan con PARTIAL (confirmado) | Vacío / 0 riesgos |
| 8 | **Web ↔ candidatos N4** | Ninguna referencia en `apps/web` a candidatos N4; el GET de #1276 (`pr/1276 router.py:1543`) exige el marcador de piloto (404 en otro caso) y no lo usa la web | **AUSENTE (confirmado)** | — |
| 9 | Caso COMPLETE → N12 → HITL → panel | `nodes.py:672, 931, 1026-1117`; `document_artifact_repository.py:482-509`; `ReviewFindingsPanel.tsx:110-138` | Implementado; **nunca ejecutado con un contrato real** | Hallazgos con cláusula y cita (si VERIFIED) |
| 10 | **Severidad** | `n4_governed_bridge.py:138` `severity=None`; `alert_generator.py:330-352` → LOW | **ROTO (confirmado)** | Sin severidad; alerta LOW tras aprobar |
| 11 | **Página del PDF original** | No existe en `RiskItem` ni en el read-model; `analysis_span` es un offset N2 | **AUSENTE (confirmado)** | Sin página |
| 12 | **Alcance del análisis** | Prompt `n4-compact-window-v1` (`n4_compact_window_response.py:16-41`): solo `findings` de riesgo | **AUSENTE (confirmado)**: no pide obligaciones, hitos, garantías, penalizaciones, pagos ni exclusiones | Solo riesgos |
| 13 | N12 sobre un contrato real | `ai_extraction.py:100-200`, `n12_source_attestation.py` | Nunca ejecutado en real; con PII redactada la atestación no valida → `UNASSESSED` (confirmado) | Nota genérica |

**Hipótesis no verificadas:**
- **H-a.** En el caso COMPLETE, un `RETRY` de N12 podría volver a N4 y crear un run nuevo con su coste.
- **H-b.** Los eventos `processing_error` no se muestran en la pantalla Evidence.
- **H-c.** Existe un mapeo de offsets N2 → `parsed_text` → página reutilizable. `_build_text_block_index` de `ingestion_tasks.py:170-206` sí conoce la página.

**Por qué el usuario no ve nada:**
1. Un bloqueo parcial (por referencias abiertas o por presupuesto) se convierte en "sin artefacto" y la UI lo presenta como un fallo genérico reintentable.
2. Aunque N4 completara, el usuario vería riesgos sin severidad ni página, y ni una sola obligación, hito o garantía, porque nunca se pidieron.

---

## 2. Qué se puede demostrar hoy sin coste y qué no

- **El contrato UAT (88 págs.) nunca ha tenido inferencia N4**: 0 recibos. Sobre él no existe ningún resultado que mostrar.
- **Los 142 candidatos SEC existen solo offline.** La base de datos *scratch* se destruyó. Viven en un paquete privado con trazabilidad de página (`7bf753a4…`). Importarlos a UAT sería introducir datos fuera de su procedencia, y #1259 lo prohíbe.
- **Consecuencia:** una demostración **dentro de C2Pro** exige **una ejecución N4 facturable autorizada**. Por referencia, el SEC de 24 ventanas costó $0,39; el coste para el contrato UAT es una hipótesis que hay que verificar en el gate económico. Lo que sí puede hacerse ya, sin coste, es **medir la calidad de N4 sobre el SEC contra un oráculo humano** (FG-0). Es el primer GO/STOP, y el más barato: si N4 no extrae bien, integrarlo no aporta valor.

---

## 3. Conjunto mínimo de correcciones para la primera demostración útil de N4

Propuestas, **no autorizadas**. Ninguna crea tablas, motores ni flujos nuevos.

| ID | Corrección | Dónde | Por qué es mínima | Choca con #1276/#1277 |
|---|---|---|---|---|
| **C1** | El parcial deja de ser invisible: excepción tipada `N4RunIncomplete` (`run_id`, ventanas examinadas/total, causa) → `analysis_blocker_code="N4_RUN_PARTIAL"`; sigue sin artefacto ni nada aprobable | `n4_governed_bridge.py:192-200`; `nodes.py:339-358` | Reutiliza la ruta de fallo honesto existente | No |
| **C1b** | Persistir código y `run_id`; texto honesto ("analizadas X/Y ventanas; causa: referencias abiertas; N candidatos propuestos, no aprobables"); `retryable=False` para esta causa | `ingestion_tasks.py:1167, 1525-1528`; `router.py:396-429, 1155-1170` | Amplía la lista blanca existente | **Sí** (congelados): después de resolver #1276 |
| **C2** | Lectura de candidatos parciales para cualquier documento del tenant, con cobertura por ventana (`status`, `blocked_reason`, `unresolved_refs`), `approvable=false`, `n12_status=UNASSESSED`, `original_pdf_coverage=UNVERIFIED` | Extraer la consulta del GET de #1276 a una función compartida | Reutiliza el GET de #1276 | Sí, si se toca `router.py`; alternativa: router nuevo de solo lectura que reutiliza su consulta |
| **C3** | Panel de solo lectura en la web que reutiliza la presentación de `ReviewFindingsPanel` (cláusula, cita verificada) sin acciones; enlace desde el documento bloqueado | `apps/web/.../documents/page.tsx:804-815`; extraer componente de `ReviewFindingsPanel.tsx:110-138` | Reutiliza el componente | No |
| **C4** | Referencias abiertas no bloqueantes, detrás de flag OFF por defecto: la ventana leída conserva `unresolved_refs` y la causa; no se reescribe el historial ni los recibos | `n4_incremental_store.commit_window:791`; `n4_incremental_runner.py` | Ya diseñada (ADR-033 esbozado, tests RED en DEV-16) | **Sí** (`n4_incremental_store.py`): después de resolver #1276 |
| **C5** | **N4 pide lo que el producto necesita**: prompt v2 en la misma llamada por ventana, con `kind ∈ {risk, obligation, milestone, guarantee, penalty, payment_term, exclusion, responsibility}`, `severity_proposed` (o `UNASSESSED`), consecuencia y cita literal. Se guarda en el `claim` JSONB existente de `n4_candidate_findings`; sin tabla nueva. El panel muestra "severidad no evaluada" y `AlertGenerator` deja de convertir lo desconocido en LOW | `n4_compact_window_response.py`; `n4_governed_bridge._candidate_payload`; `alert_generator.py:330-352` | Una sola llamada facturable cubre riesgos y obligaciones. **Se hace antes del ensayo pagado para no pagar dos veces** | No |
| **C6** | Página del PDF original para cada cita: mapear offset N2 → `parsed_text` → página con el índice de bloques existente | `ingestion_tasks.py:170-206` + read-model | Reutiliza el índice de páginas (H-c, a confirmar en DEV-16) | Puede tocar `ingestion_tasks.py` (congelado) |

**Fuera de la primera demostración (y por qué):** N12 por hallazgo, que va en FG-1b con presupuesto separado; multidocumento; ProjectGraph; Score.

---

## 4. Cómo demostraremos la calidad de N4 y de N12

### 4.1 Oráculo independiente (para N4)
- **Quién lo hace:** una persona experta en contratos EPC **ajena al equipo de desarrollo**, que anota **a ciegas** (sin ver la salida de C2Pro) el contrato autorizado y sus anexos.
- **Qué anota:** por cada elemento material, tipo (riesgo, obligación, hito, garantía, penalización, pago, exclusión, responsabilidad), cláusula, página, materialidad (crítico / alto / otro) y una breve justificación.
- **Formato:** se reutiliza el esquema de casos de `golden/` y el patrón `EXPECTED_OMISSIONS` de `n4_n12_real_ai_eval.py`. No se crea otro.

### 4.2 Métricas y umbrales

Los umbrales son una propuesta para que CORE los fije.

| Métrica | Definición | Umbral propuesto |
|---|---|---|
| Recall crítico | Elementos críticos del oráculo encontrados por C2Pro | ≥ 90 %, y **cada omisión crítica listada individualmente** |
| Recall alto | Ídem, materialidad alta | ≥ 75 % |
| Precisión | Muestra de salidas juzgadas: soportada / no soportada / errónea | ≤ 15 % no soportadas o erróneas |
| Fidelidad de cita | Citas mostradas que aparecen literalmente en la página indicada del PDF original | ≥ 95 % |
| Cobertura | Páginas y ventanas procesadas sobre el total, con lo no cubierto explicado | 100 % leído, o hueco explicado |
| Severidad | Acuerdo con el oráculo (mismo nivel o ±1) | ≥ 80 % |

### 4.3 N12 como revisor independiente
1. **Defectos sembrados:** a una copia de la salida N4 se le inyectan 10 errores conocidos (fecha alterada, parte equivocada, cláusula inventada, obligación crítica eliminada, severidad rebajada, cita que no corresponde). Se mide cuántos detecta N12 y con qué cita.
2. **Errores reales:** veredictos de N12 frente a los falsos positivos y omisiones reales que haya encontrado el oráculo.
3. **Abstención explícita:** N12 debe listar lo que no pudo evaluar y por qué. `UNASSESSED` sin causa cuenta como fallo.
4. **Reutilización:** `n4_n12_representative_eval.py` ya implementa "N12 como oráculo adversarial" con tope de llamadas y de coste. Se adapta; no se reescribe.

### 4.4 Generalización
Se repite el protocolo completo con un **segundo contrato** no usado durante el desarrollo (*held-out*). Se reportan los dos resultados por separado. Un buen resultado solo en el primer contrato es `PASS_LIMITED`.

### 4.5 Separación de dictámenes
- **QA técnico** (Frente E / Verification Auditor): código, seguridad, idempotencia, coste, persistencia.
- **QA funcional**: la persona experta del oráculo, más una persona usuaria que recorre la UI real con traza de navegador.
- Cada uno emite `PASS / PASS_LIMITED / FAIL / NOT_VERIFIED`. **Un PASS técnico nunca se registra como PASS funcional.**

---

## 5. Gates funcionales GO/STOP

Cada gate tiene un *time-box*. Si al vencer no hay un **avance funcional observable**, la línea se detiene y se revisa la causa antes de abrir otros frentes.

| Gate | Entregable observable | Coste | Time-box | GO si… | STOP si… |
|---|---|---|---|---|---|
| **FG-0 — Calidad N4 sin coste** | Informe del oráculo sobre el SEC (142 candidatos frente a anotación humana); análisis de las 92 citas no localizadas; lista de omisiones críticas | 0 (offline, VPS QA) | 5 días hábiles desde que el experto esté disponible | Recall crítico y precisión dentro de umbral, o fallos atribuibles a causas corregibles (prompt, ventana, alcance) | Recall crítico muy bajo sin causa identificable → **no integrar**; rediseñar prompt y ventanas primero |
| **FG-1a — Visibilidad honesta** (preview aislado, stub) | Con un run parcial simulado, la UI real muestra: ventanas X/Y, causa, candidatos propuestos no aprobables, sin "Retry" engañoso; con un run completo simulado, el panel de revisión muestra cita, página y "severidad no evaluada" o propuesta | 0 | 7 días hábiles tras autorizar C1–C3, C5 y C6 | Recorrido visible y persistido tras recargar | Se necesitan tablas o motores nuevos, o se debilitan controles para lograrlo |
| **FG-1 — Primera demostración real** | Contrato real autorizado analizado en C2Pro: documentos y páginas procesados; riesgos **y obligaciones**; citas con página original; omisiones frente al oráculo; qué puede revisar el usuario; qué llega aguas abajo (hoy: revisión HITL; nada más) | 1 ejecución N4 facturable, **autorización económica separada** | 1 ejecución, sin repeticiones | Métricas de §4.2 informadas honestamente y bloqueos visibles | `UNKNOWN` en el ledger, cobro duplicado, resultado vacío presentado como éxito |
| **FG-1b — N12 revisor** | Veredictos por hallazgo, detección de defectos sembrados, lista de lo no evaluado | Facturable, autorización separada | 1 ejecución | Detección de defectos sembrados ≥ umbral fijado por CORE | N12 sin aportar nada útil → replantear su diseño antes de seguir |
| **FG-1c — Generalización** | FG-1 repetido con el contrato *held-out* | Facturable | 1 ejecución | Métricas comparables | Calidad degradada → problema de prompt o modelo, no de integración |
| FG-2 — Contrato + anexos | Referencias resueltas contra anexos subidos; anexos ausentes señalados | Facturable | — | — | — |
| FG-3 — Discrepancias multidocumento | Cronograma y presupuesto XLSX + especificación; comparadores existentes alimentados con los hitos, plazos y precio de C5 → alerta con dos fuentes + ítem HITL | Facturable | — | — | — |
| FG-4 — Decisiones y estado | Aprobar, rechazar o corregir cada elemento; ProjectGraph TRUSTED tras aprobar; Current State, Health y Coherence distinguen validado de pendiente; persistencia tras relogin | — | — | — | — |
| FG-5 — Complete Journey | S1–S8 con traza de navegador y segundo proyecto | Facturable | — | — | — |

Los FG-2 a FG-5 se detallarán solo cuando el gate anterior pase. No se abren a la vez.

---

## 6. Del núcleo contractual al multidocumento

Todo se hace reutilizando lo que existe:

1. **Hechos del contrato (C5):** hitos, plazos, precio y garantías salen del mismo N4 con cita. Alimentan los tipos de entrada que ya existen en `coherence/cross_document/inputs.py` (`DatedSource`, `ProjectCrossDocInputs`), en lugar de la regex sobre citas de riesgos.
2. **Familia documental:** el vínculo entre anexo y contrato se guarda en `document_metadata` (JSONB existente). Solo se propondrá una columna si eso no basta.
3. **Cronograma y presupuesto:** XLSX con confianza humana mediante `structured_source_trust` (ADR-032).
4. **Comparadores existentes:** `SPEC-MILESTONE-VS-SCHEDULE`, terminación vs fin de cronograma y precio vs presupuesto, ampliados para aceptar hitos del contrato y de los anexos.
5. **Visibilidad:** cada resultado `PROVISIONAL` genera una alerta con dos fuentes (`AlertGenerator`) y un ítem revisable (`finding_decision_router`). No se crea un motor nuevo.
6. **ProjectGraph:** se alimenta por la ruta TRUSTED existente tras la aprobación humana. Una vista provisional sin Score solo se plantea si FG-3 demuestra que hace falta.

---

## 7. Estrategia multiagente realmente paralela

Cinco carriles con **ficheros disjuntos**, un responsable por carril y un revisor fijo de otro carril. Nadie revisa su propio trabajo.

| Carril | Responsable (rol) | Ficheros exclusivos | Entregable | Revisor fijo |
|---|---|---|---|---|
| **L1 Núcleo N4** | Frente A (Backend) | `n4_governed_bridge.py`, `nodes.py` (solo N4), `n4_compact_window_response.py`, `n4_incremental_runner.py`; `n4_incremental_store.py` **tras #1276** | C1, C4, C5 | Frente B |
| **L2 Lectura y UX** | Frontend + Backend de lectura | Router nuevo de solo lectura (o extracción tras #1276), `apps/web/**` del documento y del panel | C2, C3, C6 en el read-model | Frente C |
| **L3 Evaluación** | Test/QA + **experto humano** | `docs/qa/**`, scripts de evaluación, fixtures privados (VPS) | FG-0, protocolo §4, métricas | Verification Auditor |
| **L4 Preparación multidocumento** | Frente C | Solo lectura hasta FG-1; corpus de 6 documentos; mapeo C5 → `ProjectCrossDocInputs` | Diseño listo para FG-3 | Frente A |
| **L5 Release y economía** | Frente B / DevOps | Inventario DEV-17, preview aislado, verificación de saldo y modelo | Entorno y gate económico listos para FG-1 | Orchestrator + Auditor |

El **Frente E** sigue dedicado en exclusiva al G4 de #1276/#1277.

**Medición real del avance:**
- Cada tarea registra en su bloque `c2pro-implementation-result-v1` las marcas de inicio, PR abierta, revisión y cierre.
- Al quinto día hábil se calcula el *throughput* real por carril. **El calendario se planifica a partir de ese dato**, no de estimaciones.
- No se compromete ninguna fecha antes de esa medición.

**Dependencias reales:**
- L1-C4 y C1b esperan a que se resuelva #1276. Hasta entonces, L1 hace C1 y C5, y L2 hace C2 (router nuevo) y C3.
- L3 no depende de nadie, salvo del experto humano.

---

## 8. Primer gate funcional propuesto y decisiones que necesita CORE

**Primer gate: FG-0** (coste cero, puede empezar ya dentro de DEV-16). Ningún otro trabajo de producto tiene sentido si FG-0 revela que N4 no extrae bien.

**Decisiones de CORE:**
1. Designar a la **persona experta del oráculo** (ajena al equipo) y elegir el **contrato *held-out***.
2. Fijar los **umbrales** de §4.2 y de detección de defectos de N12.
3. Autorizar el **diseño** de C1, C2, C3, C5 y C6 (y C4 y C1b tras resolver #1276). No es autorización de despliegue.
4. Preparar, sin aprobarla todavía, la **autorización económica** de FG-1 (una ejecución N4) y, por separado, la de FG-1b (N12).
5. Confirmar que FG-1 se hace en un **preview aislado**, sin tocar UAT ni producción.

**Lo que este dictamen no hace:** no modifica código, no crea sobres, no despliega, no hace llamadas facturables ni convierte la WBS v2 en programa de trabajo.
