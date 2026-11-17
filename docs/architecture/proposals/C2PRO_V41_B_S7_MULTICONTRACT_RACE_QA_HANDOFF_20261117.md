# C2Pro V4.1 / Frente B — P0 multicontrato y P1 concurrencia

**Coordinación:** GitHub #1049. **PR:** #1258, DRAFT. **Corpus de
producción sometido a prueba:** cuatro archivos oficiales sintéticos triplet
con contrato único. **Adversario C1/C2:** señales y revisiones de laboratorio
identificadas como sintéticas, nunca reconstrucción de contratos reales.
**Proveedores N4/N12:** no utilizados.

## A. Falsabilidad y alcanzabilidad del escenario C1/C2

La versión anterior de `economic_signal_dedup._key` usaba
`(contract_total,budget_total,budget_document_id,budget_revision_id,budget_locator)`,
sin el contrato independiente. Se conservan **pruebas RED** que
demostraron cuatro errores de la **función pura**, no una UAT del producto:

| Escenario adversarial | Resultado RED | Resultado GREEN después de fix |
|---|---|---|
| A: C1 y C2 de 1 M€, presupuesto común 1,5 M€, 4 señales (2 reglas por contrato) | 2 impactos, pero **una misma clave** para ambos contratos | 2 impactos y **2 claves de discrepancia distintas** |
| B: solo CONBUD C1 y NEGMARGIN C2 | Falsa fusión: **2→1** | **2 impactos independientes** |
| C: mismo contrato, distinto número de revisión, mismas cifras | Falsa fusión: **2→1** | **2 impactos independientes** |
| Sin identidad del contrato | Fusión no verificable | **Sin clave / sin deduplicación** |
| Un contrato y revisión auténticos, 2 reglas | 2 alertas y un impacto | Se conserva: **2 alertas, un impacto** |

**Alcanzabilidad productiva comprobada:** el módulo actual
`assemble_cross_doc_inputs` selecciona **el máximo agregado de
contract_total por proyecto**, y `assess_numeric_comparators` emite
**un solo par de reglas por comparación**. El caso B (cada contrato
emite una regla distinta) **no sale de ese ensamblador normal**: requiere
señales fabricadas o un futuro/otro camino de múltiples evaluaciones.
La colisión de la función pura está demostrada; **una infrapenalización
de ese tipo en el flujo productivo corriente NO está demostrada**.

La consulta actual de contratos `load_contract_total` también selecciona
un importe máximo (a igualdad de precio no distingue contratos). Por
tanto el proyecto multicontrato **no está semánticamente evaluado
por contrato**: no confundir "no colisiona el agrupador" con
"se han analizado ambos contratos por separado". Residual y owner
**Backend ProjectGraph/CORE** para diseño futuro del alcance.

## B. Corrección mínima de identidad

`load_contract_total_source` consulta
`clauses + documents + document_revisions` bajo
`current_revision_lateral`, `canonical_clause_in_current_scope`,
`valid_to IS NULL` y tenant/proyecto. Solo devuelve la
identidad contractual si hay **una única pareja documento/revisión/SHA**
para el importe seleccionado; más de una, o más de 64 filas candidatas,
=> `None`. El origen incluye cláusula UUID auténtica.

`ProjectCrossDocInputs.contract_total_source` preserva esa procedencia;
los dos comparadores económicos la transmiten en
`evidence.contract_source`, **independiente** de la referencia
`evidence.sources[0]` presupuestaria. El detector retiene documento,
revisión, SHA y locator en el alert persistido. La nueva
`economic_discrepancy_key` exige ambos lados completos:

`(contract_total,budget_total,
 budget_doc_id,budget_revision,budget_SHA,budget_locator,
 contract_doc_id,contract_revision,contract_SHA)`.

Sin dato contractual fiable **no se deduplican** impactos; no se genera
una clave aparentemente autenticada. La ausencia de procedencia
**no se convierte en VERIFIED**. Un único contrato original del
triplet mantiene el comportamiento probado de **2 alertas/1 impacto**.
Si dos contratos compartiesen el importe canónico, su origen no puede
elegirse arbitrariamente y la deduplicación queda inhabilitada.

**Nota QA:** la procedencia contractual se adquiere del SQL canónico
durante ingesta/Coherence en proyecto real; un `FindingSignal`
construido directamente en pruebas puede simular identidades, lo que
no constituye prueba de seguridad de un dato procedente de API pública.

## C. Prueba real PostgreSQL de carrera revisión/alerta

Test nuevo `test_s7_concurrent_revision_insert_pg.py`:

1. Ingiere exclusivamente el presupuesto XLSX sintético existente,
   enlazado a `documents/document_revisions/document_source_units`.
2. T1 toma un origen verificado con `FOR SHARE OF r,u`.
3. **T2, transacción concurrente real**, intenta cerrar el intervalo
   único `valid_to=NULL` y ejecutar `INSERT INTO document_revisions`
   de rev. 2 (datos exclusivamente temporales de DB de test).
4. T2 **no puede completar la inserción antes del COMMIT de T1**.
   Después del COMMIT de T1, T2 cierra la rev. 1 e inserta la rev. 2.
5. Una lectura posterior rechaza la revisión original como actual
   (`NOT_VERIFIED`). La misma alerta histórica conserva la
   referencia a la rev. 1, pero los endpoints de listado
   `/alerts/projects/{id}`, `/projects/{id}/alerts` y
   `/alerts/tenant` revalidan su estado de fuente y presentan
   `STALE_SOURCE`; la lectura no altera el ledger ni crea una
   revisión/HITL artificial.
6. El SQL de binding añade `cur.resolved AND cur.revision_id=r.revision_id`
   para no tratar como actual una revisión que perdió la autoridad
   efectiva sin que su hash hubiera cambiado.

**Alcance de esta prueba:** cierre de revisión + inserción real de
la siguiente bajo la constraint `uq_docrev_open_revision`, mismo
documento/tenant. No cubre toda carrera de promoción de
`document_artifacts` ni toda transacción bajo niveles de aislamiento
alternativos; QA Ops/Backend debe verificar lo último antes de
reclamar garantía universal de concurrencia.

## D. Estado QA independiente — AIGAA-130

Recuperados **3/3 comentarios persistidos** de Elena (tarea
Paperclip `AIGAA-130`, issue
`a7733a32-6672-4ed6-9de1-e541eb87d388`):
- `a8b81812-348d-4ffe-87c3-3bb10353ecd1`: alcance solo
  estático sobre SHA antigua, sin shell ni pruebas ejecutadas.
- `87b04766-95fa-400c-878f-030ef80c50db`: detecta explícitamente
  falta de identidad contractual y el adversario asimétrico B.
- `69ee055e-a9b2-4392-b6f3-bef47659b8c2`: revisión estática
  parcial de v1/v2/canary/severidad, sin emitir aprobación funcional.

Ejecución Paperclip `9edd0a5b-fa3c-4a48-b337-03a4b68b81b8`:
`adapter_failed`, código 26 comunicado por CORE;
recovery `abb52d95-89d2-4301-aa80-32c1d5efeda2` con
`adapterRecovery=unsupported_or_unknown`,
`policy=preserve_without_replay_v1`, `replay=blocked`,
`legacy_execution_requires_reconciliation`.
**No reintentos, modelo pagado ni aprobación Elena**. Los tres comentarios
siguen archivados en Paperclip; no se adjudican a nuevas pruebas
ejecutadas. **Owner Ops/CORE:** identificar causa del exit 26 y
conciliar los efectos de esa sesión ANTES de autorizar nueva revisión
independiente exclusivamente del diferencial posterior a la SHA
`690caffc`. Exigir dictamen individual para B1/S3/S7,
`PASS/PASS_LIMITED/CHANGES_REQUIRED`, con alcance probado.

## E. Bloqueos y aceptación

- **B1:** GO técnico previo intacto; QA definitivo pendiente.
- **S3:** GO técnico previo intacto; QA/UX UAT pendiente.
- **S7 identidad y concurrencia:** GO técnico focal sujeto a QA
  independiente y limitaciones de corpus multicontrato.
- **S7 funcional:** **NO-GO**: Backend WBS + UX/HITL aún no han
  aportado baseline WBS vigente, link documento/revisión/fuente→nodo,
  evento humano auténtico y posterior readback ProjectGraph.
- **S8 Complete Journey:** NO-GO.
- Mantener **Score null/UNKNOWN**, TECHNICAL NOT_ASSESSED,
  riesgos PROPOSED sin promoción por mero ACK.
- SEC 73p de A, SolarMax 94p y triplet cuatro fuentes B
  **permanecen aislados**; ningún handoff sin identidad/revisión/run
  del original y HITL real atraviesa estas fronteras.

CI PASS y cualquier test del autor **no** reemplazan QA
independiente. No merges, despliegue productivo, SQL productivo,
N4/N12 real ni gasto de IA adicional.
