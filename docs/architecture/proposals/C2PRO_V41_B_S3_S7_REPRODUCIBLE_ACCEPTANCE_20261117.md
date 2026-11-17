# Frente B V4.1 — B1, S3 y S7: matriz de validación 17/11/2026

**Coordinación y autoridad:** CORE #1049; PR propietaria #1258. Código B
de partida: `c1f9fa22e120c140f2d08f23345aec359fce94eb`.
Frente A para integración: `17898c364b8baf05739614ae36ef2c8f6b0e5a6c`.
Las pruebas aquí indicadas son evidencia QA delimitada, nunca una
autorización de producción. Sin proveedor real nuevo, SQL productivo,
reprocesamiento del contrato original o actos HITL.

## B1 — auditoría financiera

- Artefacto real GHA #44007355327, SHA256
  `549ca20b14549e7d74aee1452a33e43f8aa526036fb57a5d07cc83be55f61cad`:
  N3 1 SETTLED; N4 24/24 SETTLED; gobernador 25 reserve + 25 done;
  24 N4 enlazados por request ID/tokens/coste. 0.394394 USD **estimados**,
  factura del proveedor NO verificada. N3 no conserva provider_request_id
  en ledger legacy: identidad cruzada/inter-run no probada.
- PostgreSQL 16 en clúster **local y desechable** con migraciones Alembic
  head y roles de bootstrap solo del clúster: 37/37 PASS de manifiesto,
  Coherence escrow, auditoría N4+legacy y latch N12 (cuatro suites).
- Segundo bloque 21/21 PostgreSQL PASS: concurrencia tenant, reserva
  compartida, idempotencia, N4 incremental y reconciliación.
- A+B aislada sobre A `17898c36` + B `c1f9fa22`: cero conflictos,
  85/85 PASS focales (37 PostgreSQL + 48 auditoría offline/unidades).
  A añadió 7/7 pruebas PG de recuperación N4 y N12/checkpoint en su
  entorno de integración con proveedor simulado.
- Los conteos de pruebas corresponden a ejecuciones concretas; algunos
  tests se ejecutaron más de una vez para verificar A+B. Ningún PASS
  valida una factura externa ni reconstituye la DB del piloto destruida.

## B2 — matriz S3 Health / Coherence Score / alertas

| Entrada o estado | Esperado | Observado / prueba | Veredicto |
|---|---|---|---|
| N4/riesgo sin ejecución | score null, banda UNKNOWN | `test_risk_assessment_not_run_is_unknown_not_green` | PASS unidad |
| Sin riesgos constatados, crítica N12 no evaluada | nunca declarar saludable | **Defecto reproducido RED:** valor 90/HEALTHY. Corregido en `risk_scorer.py`: null/UNKNOWN, evidencia limpia vacía. `test_no_trusted_risks_with_unassessed_critique_is_unknown_not_clean` | FIX + PASS |
| Riesgo fuente verificada, N12 pendiente | conservar puntuación de lo validado; confianza <=0.3 y cobertura pendiente | `test_verified_risk_is_retained_when_critique_pending`, `test_b_unassessed_critique_qualifies_risk_health` | PASS unidad |
| Riesgos propuestos sin cita | no asignar VERIFIED ni source_clause_id | `test_a_unverified_or_missing_quote_status_is_not_verified` | PASS unidad |
| Ausencia de pruebas para dimensión | NULL/UNKNOWN; no inferir 100 | `test_single_document_coverage.py`, `test_coherence_subscore.py`, Health node | PASS unidades acotadas |
| PROPOSED de otra revisión | Score confiable intacto; provisional separado | `test_trusted_projection.py` y reglas anti-gaming | PASS unidad; UAT pendiente |
| Recalculación con Score no evaluable | alertas durables no duplicadas ni auto-resueltas, decisiones humanas conservadas, sin fuga tenant | `test_scoreless_alert_ledger_flow.py` en PostgreSQL 16 | 6/6 PASS PG |
| Aceptación real de riesgo sin subir Score | mantener semántica independiente de aceptación | Reglas/proyecciones unitarias; **no existe UAT real de decisión con el piloto** | NO-GO UAT |
| Alerta de riesgo con evidencia | documento/revisión/cláusula/quote/severidad coherentes | `test_evidence_status_alerts_health_20261110.py`; evidencia no verificada queda sin vínculo verificable | PASS contrato; E2E pendiente |

La corrección es intencionadamente acotada: conserva Health evaluado
cuando existen riesgos sustentados; únicamente prohíbe **certificar
ausencia de riesgos** mientras la crítica obligatoria no terminó.

## B3 — matriz S7 WBS / Coherence multifuente

| Contrato | Esperado / observado | Veredicto |
|---|---|---|
| Tenant/proyecto/UUID revisión real | manifiesto verificado desde `document_revisions`, sin identidad fabricada | PASS PG |
| Dos documentos independientes | SHA/manifiesto estable, request keys diferentes, revisión/source binding exactos | PASS PG |
| Revisión obsoleta o duplicada | fail closed, no identidad falsa | PASS PG |
| Un documento subido sin revisión | inventario incompleto no puede afirmar cobertura completa | PASS PG |
| Selección parcial de documentos | inventario completo exige REPEATABLE READ y todos los docs/revisiones | PASS PG |
| Cláusula de varias fuentes | no convertirla en una única revisión para cobrar o evaluar | PASS PG (rechazo) |
| Contrato + Budget + Schedule + Technical reales | enlaces semánticos independientes hasta WBS, alertas y ProjectGraph | **NOT VERIFIED**: falta corpus multifuente íntegro y pruebas verticales |
| pending/projected sin HITL | score provisional separado del Score validado, no promoción automática | PASS contrato unitario; integración de persistencia/UAT NO-GO |

Los tests PG del manifiesto prueban **inventario y binding de revisión**,
no discrepancias financieras/temporales semánticamente correctas entre
cuatro documentos ni WBS aprobado. No declarar S7 concluido.

## B4 — integración y gates

- A se consulta por HEAD exacta inmediatamente antes de la superposición
  (sin tocar su PR); no merge ni deploy productivo.
- Proveedores N4/N12 de pruebas son stubs, **no** equivalentes al ensayo
  IA real. N4 del artefacto real sigue `PARTIAL` con 0/24 `EXAMINED`,
  142 candidatos propuestos, 50 citas verificadas/92 no verificadas;
  N12 real no ejecutado; ninguna aceptación HITL.
- B1 financiero/PG: **GO técnico delimitado**, no factura.
- S3: **GO técnico condicionado** a integración/UI, UAT y cierre N4/N12.
- S7: **NO-GO funcional multifuente**, contratos de fuente PASS PG.
- S8/Complete Journey: **NO-GO**, decide CORE.

**Dependencias:** A = completar análisis real y evidencias N4/N12;
Ops = despliegues/Clerk y binding UAT; UX/HITL = decisiones individuales
y visualización de valores validado/provisional; Backend WBS/ProjectGraph =
partidas, actividades, requisitos y discrepancias persistidas.
