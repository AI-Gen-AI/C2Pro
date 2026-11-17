# C2Pro V4.1 — Frente A / N4, QA de originales y preautorización N12 (17/11/2026)

**Decisión CORE:** GO técnico limitado de recuperación y seguridad. PR propietaria #1255; coordinación canónica #1049. NO merge/deploy, NO proveedores, NO cambios a ledger/Coherence B, NO approvals simulados. Calidad N4 **PARTIAL**; N12 real/HITL/S8 **NO-GO**.

## 1. Separación de expedientes y evidencia inmutable

**Piloto real:** GHA [#44007355327](https://github.com/AI-Gen-AI/C2Pro/actions/runs/44007355327); artifact `14295261912`, archivo `real_analysis_evidence.json` SHA256 `549ca20b14549e7d74aee1452a33e43f8aa526036fb57a5d07cc83be55f61cad` (**223806 bytes**). El ZIP original conserva 25 reservas y 25 operaciones `done` (N3 una y N4 24). Las 24 ventanas N4 (0–23) presentan 142 `finding_key` únicos con `review_status=PROPOSED`; 50 `EXACT_MODEL_SAFE_MATCH` y **92 sin `source_quote` aportada**. No cambiar el status, fingerprints, recibos ni históricos.

**Fuente:** filing público SEC original 224 páginas SHA256 `2370812124b5f42713153122fc45f1e5716dd85385d881bdd339bd87b9dced06`; contrato EX-99.1 de **73 páginas**, distinta de la fuente Library SolarMax de **94 páginas** SHA256 `e58a128e01348aa3c77e4a101861a6ebcdc0e303e599314c85bde3aa2ec7d63d`. Conservar este último expediente y oráculo P01–P14 **separados**, sin trasvasar omisiones o medidas de recall.

**N2 esperado del piloto:** SHA256 `cf8f4b7d5341b04b7aacd5532b45cf130dd689037412a08ed1e9f7e59bf555c4`, 229329 caracteres, 4 redacciones, 24 ventanas CORE (histórico). No confundir SHA N2 con `document_revisions.blob_hash` del original.

## 2. Cuatro hallazgos: juicio de QA distinto de propuesta IA

| Nº | Cláusula | Contexto contractual público y juicio independiente | Severidad de revisión, NO decisión HITL |
|---|---|---|---|
| 108 | 9.5.1 | El límite de una suspensión individual es 60 días consecutivos; el agregado contiene la contradicción literal `one hundred (180) Days`. La IA adoptó 180 sin justificar; el propio contrato reconoce, sujeto a condiciones, determinados costes de suspensión y remite el exceso a terminación por conveniencia. No determinar 100 o 180 automáticamente. | ALTA: umbral de plazo y terminación material, con costos condicionados |
| 109 | 9.6 | Derecho de Owner a terminar con aviso de 15 días y liquidación condicionada. Texto externo contiene `ten percent (5%)` en un supuesto concreto; también un techo `[3]% ` para partidas (iii)/(iv). La cita original que N4 aportó para este hallazgo solo cubre el techo [3]%; no acredita por sí sola la contradicción 10/5. | ALTA: cuantía y base ambiguas; aclaración contractual/documentos Exhibit D |
| 111 | 9.9 | Owner `may` pagar lo no discutido y colocar importe disputado en escrow mediante tercero mutuamente convenido, con resolución de diferencias conforme al art. 11. La IA lo describió como depósito automático, lo cual no se sigue del texto. | MEDIA: liquidez condicional y cuantía incierta |
| 118 | 9.9 | Misma disposición; intervalo N2 `187272–187390` contenido íntegramente en el de #111 `187252–187390`, ventanas 19 y 18. ÚNICO par entre las 50 citas localizado que comparte cláusula y solapa ≥75 % del menor intervalo (cribado automatizado). No borrar ninguna propuesta. | MEDIA AGRUPADA: probable repetición; no duplicar penalización/impacto |

**Fuente externa de contexto:** [SEC filing PDF completo](https://s3.amazonaws.com/sec.irpass.cc/2934/0001640334-26-000032.pdf), páginas físicas 60 y 62 (Exhibit 99.1 páginas impresas 56 y 58). La inspección externa ayuda al revisor pero **no reescribe ni verifica retroactivamente las 92 citas ausentes de N4**. La clasificación es consultiva y no reconocimiento jurídico de validez.

**Pendientes de humano:** texto final firmado, anexos y valores entre corchetes, aviso real y situación comercial, cuantificación de daños/impacto, custodia legal de revisión, eventual agrupación #111/#118. 142 siguen PROPOSED, 0 CONFIRMED.

## 3. 19 pruebas bloqueadas por originales no montados

| Suite del commit | Cantidad anterior | Fixture de integridad requerida | Estado de este checkpoint |
|---|---:|---|---|
| `tests/unit/analysis/test_v41_n4_billed_artifact_recovery.py` | 10 SKIPPED | ZIP real JSON SHA `549ca...` + **N2 original** SHA `cf8f4b...`; algunas requieren filing original | NO COMPLETADAS; JSON recuperado, N2 no localizado |
| `tests/unit/analysis/test_v41_s2_s4_real_handoff.py` | 9 SKIPPED | Paquete privado `n4_offline_review_packet_sec_verified.json` SHA256 `7bf753a485a92b7fc096763f7fbf623a9a1c3de878c8efa0df84030041931b43` | NO COMPLETADAS; paquete no localizado |

**Recuperación ejecutada:** consulta de archivos de Library y búsqueda de los nombres originales en las raíces privadas habituales del VPS en modo solo lectura y con autorización Ops, sin localizar N2 ni paquete privado. El ZIP facturable original sí se ha descargado y su SHA exacto sí se ha acreditado. El ZIP no contiene el N2 ni el paquete privado; solo JSON del resultado, preflight sanitizado y governor JSONL. Se prohíbe generar N2 sustituto, reemitir citas, saltarse el `pytest.skip` o contar pruebas antiguas como PASS de este checkpoint.

Última regresión ya acreditada en HEAD de código `cfaf570a...`: job `b95cce0fb3ab4a67a382a5f1`, **44 PASS / 19 SKIPPED**; HEAD final previa `6e12611476...`: job `a6c7b9d54b73425dad56b1b4`, **3 PASS** rutas de seguridad. No repetir suites sin fixture. N4 fuente real no será llamada otra vez. La continuación exige que Ops localice un **original conservado**, compruebe SHA y prepare montaje `read-only` en runner; si se perdió, registrar irreproducibilidad de esas 19 pruebas, no reconstruir.

## 4. Expediente N12 — propuesta presupuestaria NO autorizada

| Campo | Condición para GO |
|---|---|
| Documento objetivo | Filing SEC SHA `237081...` / EX-99.1 73p; N2 `cf8f4b...` de 229329 chars, no el original Library de 94p |
| Autoridad QA histórica | Revision `862714ba-9b4a-4091-874c-1b03e9e2204a`; N4 run `b18ce1bd-de99-417c-a47a-8ca29a5d43c9`. **IDs de scratch desechable, NO utilizables como autoridad vigente** |
| Identidad válida futura | Tenant/proyecto/documento/revision blob SHA actual, generation/fencing, N4 run e hilo `ProjectState` verificables en PostgreSQL persistido. **AUSENTES** hoy |
| Checkpoint | AsyncPostgresSaver parent snapshot duradero ligado a la llamada; **NO EXISTE de N12 real** |
| Cobertura | N2 íntegro SHA-verificado, 24 ventanas y lista completa 142 propuestas; mantener N4 `PARTIAL` y `UNASSESSED`, no cambiar a COMPLETE sin evidencia |
| Entrada / salida | ~80k–183k tokens input orientativos para ~366k chars N2+propuestas; salida máxima 4096. Exigir conteo y tamaño real del prompt final antes de reservar |
| Modelo / tarifa interna | GPT-4.1; 2 USD/1M input +10 USD/1M output (estimador interno, no factura) |
| Coste / reserva | ~0,17–0,41 USD estimados según tokens; **reservar como máximo USD 1,20** para UNA llamada, tras comprobar presupuesto *del tenant vigente*, no del scratch antiguo |
| Latencia | No medida; `OpenAIBudgetedTransport` usa timeout 120 segundos. No estimar SLA basado en silencio del proveedor |
| Idempotencia | Solicitud con binding estable, escrow COMMIT antes del POST, sin retry de operación incierta, `UNKNOWN` mantiene liability |
| Conciliación | B compara reserva/recibo real/IDs, tokens y costos, con governor, ledger actual y factura externa cuando exista; coste no verificado ≠ cero |
| Stop | SHA inválido/ausente; usuario/proyecto/revisión no autenticados; N4 PARTIAL sin política autorizada; checkpoint/escrow insuficientes; budget no verificado; request incierto; provider drift |
| Continuidad | N12 nunca promociona automáticamente N4: si fuente incompleta, `UNASSESSED` + HITL auténtico. Solo candidato inmutable revisado y versión actual pueden continuar hacia N8/Graph |

**Control crítico que falta resolver antes del GO de dinero:** `v41_contract_real_ai_pilot.py` aborta deliberadamente cuando `outcome.status != COMPLETE` o `examined_windows != total_windows`. No eludir esa condición bajo el nuevo presupuesto. CORE y Backend deben aprobar explícitamente tratamiento honesto de cobertura `PARTIAL` antes de cualquier run N12.

El workflow facturable sigue `if: false`. **Esta propuesta de USD 1,20 no constituye autorización de cargo.**

## 5. Handoff A→B y Backend HITL

Frente B PR #1258 es único dueño de ledger, Coherence y S7; A no modifica esos archivos. El paquete A→B mantiene únicamente procedencia segura `finding_key`, ventana, revisión histórica, SHA original PDF/N2 y estado PROPOSED. Hasta disponer de revisión actual PostgreSQL, manifest B completo, snapshot consistente `REPEATABLE READ/SERIALIZABLE`, candidato inmutable y decisión auténtica individual, `projectgraph_promotion_authorized=false` y `coherence_result=UNASSESSED_NOT_CALLED`.

Ops: recuperar fuente privada N2 y packet original o acreditar su pérdida irreversible, sin generar sustitutos. B: validar identidad original blob/revisión y conciliación financiera futura, sin tocar A. Backend HITL/Atlas/UX: una única interfaz S5 con decisión individual verificada, `Aprobar todo` al final, no duplicar implementación; CORE conserva la aceptación S8.

**Veredicto:** inventario real N4 recuperado GO técnico / semántica PARTIAL; original QA 19 **BLOCKED**; N12 **NO-GO**; HITL **NO-GO**; N8/Graph **NONPROMOTABLE**; S8 **NO-GO**.
