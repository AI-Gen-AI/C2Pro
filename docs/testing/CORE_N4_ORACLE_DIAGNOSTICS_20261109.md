# CORE N4 — desglose de fallos del oráculo (09/11/2026)

Estado: diagnóstico instrumental, NO aceptación funcional.

## Problema identificado

El ensayo Sonnet 4.6 [Actions #42514971086](https://github.com/AI-Gen-AI/C2Pro/actions/runs/42514971086) emitió nueve registros. El oráculo emparejó cuatro, validó cinco citas literales y rechazó cuatro. El nombre histórico del campo false_positives puede inducir a error: su fórmula es el número total de registros emitidos menos los emparejados. Un riesgo respaldado por fuente, pero con una categoría distinta, también cuenta como no emparejado. No equivale necesariamente a cinco afirmaciones inventadas.

El campo nuevo unmatched_emitted_risks aclara esa distinción sin romper el contrato previo. El score N4 y la prueba de aceptación siguen intactos.

## Diagnóstico estrictamente sin aprobación semántica

La función diagnose_n4_unmatched clasifica las correspondencias que no superaron el oráculo mediante cinco contadores:

- valid_marker_different_category: el pasaje fuente exigido aparece, pero la categoría difiere.
- same_category_clause_quote_missing_marker: fuente verificable de la cláusula con categoría esperada, pero sin el pasaje decisivo exigido.
- valid_clause_different_category_and_marker: cita verificable de la cláusula, otra categoría y sin el pasaje exigido.
- unrelated_valid_quotes: citas verificadas de otros elementos sin conexión probada con el caso.
- globally_unverified_quotes: citas no verificadas por el sistema (recuento global, no causa específica por cláusula).

No almacena texto de respuesta del proveedor. El gate independiente exige que dichos diagnósticos coincidan con las posiciones y hashes de citas del documento EPC sintético.

## Plan de cierre de este bloqueo

P0: determinar categoría, cita y semántica por cláusula EPC-01/05/06/07/09, con datos que permitan ver los textos bajo un procedimiento de evidencia autorizado; el artefacto viejo solo tiene resultados agregados, así que no permite diagnosticar un caso exacto retrospectivamente.

P1: corregir primera causa demostrada y cruzar revisión Codex/Claude. No relajar trazabilidad, no exigir categorías editoriales rígidas sin respaldo jurídico.

P1 Health/Score: seguir nulidades por documento, revisión y tenant, identificar persistencia/propagación o insuficiencia real antes de modificar ninguna ponderación.

P2: una vez superada la calidad, UAT vertical EPC completo con dos fuentes, HITL y Coherence Score real; hasta entonces CORE NOT_UAT / NO_RELEASE.

Sin nuevas llamadas pagadas, despliegue o aprobación HITL en esta PR.
