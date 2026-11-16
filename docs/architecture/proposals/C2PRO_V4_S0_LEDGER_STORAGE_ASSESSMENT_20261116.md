# C2Pro V4 — S0 checkpoint: ledger, contabilidad y coste de N4
Fecha: 16/11/2026. **Diseño / análisis de reutilización** (todavía NO esquema PostgreSQL ejecutado).
Referencia de código: CORE SHA `5af16eed1d3087f8e081cdc5caa567f726ca6a9e`.

## Hechos comprobados
1. `apps/api/src/evidence/adapters/persistence/models.py:EvidenceExtractionEventORM` permite únicamente `event_type in ('processing_error','out_of_scope')` por CHECK; **no es un ledger de ventanas de extracción N4** ni debe reutilizarse insertando eventos de hallazgo sin migración.
2. `apps/api/src/analysis/adapters/persistence/models.py:ExtractionORM` guarda `document_id`, `extraction_type`, `data_json`, `confidence_score`, `model_version`, tokens y coste, pero no ofrece explícitamente `tenant_id`, `document_revision_id`, `source_span`, ventana, `claim_token` o `coverage_state`; no es adecuado como única fuente de la nueva persistencia incremental sin cambios.
3. `apps/api/src/core/ai/models.py:AIUsageLogORM` registra tenant, project, provider/model, tokens, estimación, status y metadata. Es útil como log observable y conciliación, pero carece de reserva atómica por run/document/revision y unicidad de una llamada.
4. `apps/api/src/core/ai/cost_controller.py:CostControllerService` comprueba el gasto mensual y suma el coste observado; la comprobación y el cargo no aparecen como una transacción reservada con SELECT FOR UPDATE ni como una función de presupuesto por documento/run. Las constantes tarifarias están vinculadas a modelos anteriores y existen tarifas de fallback.
5. `apps/api/src/core/processing_authority.py` ya aporta `attempt_id`, `owner_token`, `fencing_token`, revisión y verificación transaccional de ownership. Debe **reutilizarse**, no diseñarse una autoridad paralela para N4.

## Decisión propuesta y próxima implementación
- WBS 2.1: [PR #1239](https://github.com/AI-Gen-AI/C2Pro/pull/1239), ventana lossless + overlap + SHA, 14/14 test PASS; todavía no llama al proveedor ni persiste en PG.
- WBS 2.2: migración **aditiva mínima** para `n4_extraction_runs`, `n4_window_progress`, `n4_findings` con claves `tenant_id, project_id, document_id, document_revision_id, extraction_run_id`, indexes y RLS. Evaluar si `ProjectEvent` existente puede recibir hallazgos validados sin duplicar la fuente de verdad.
- WBS 2.5: las escrituras de estados/hallazgos y control de `window_state` deben comprobar `fence_current` EN la misma transacción; CAS/unicidad por run y ventana.
- WBS 2.6: presupuesto por ejecución mediante reserva/conciliación atómica; reutilizar `AIUsageLogORM` como recibo, no como única reserva. Facturación desconocida por timeouts no debe contabilizarse como 0. Cualquier cambio debe integrar costes, concurrency y tests PG aislados.
- WBS 1.4: N12 actual sí devuelve `UNASSESSED` y solicita HITL para críticas no fundamentadas, lo que evita algunas reiteraciones. Sin embargo, puede enviar nuevamente el documento completo a un modelo; **no es correcto afirmar que ya está optimizado en coste**. Medir y diseñar crítica focal/ventanas sin esconder material crítico.

## Gate antes de aplicar migración
Confirmar modelos/tablas RLS y política de migración, test aislado con tenant A/B, migración downgrade sin pérdida de información existente, idempotencia de ventanas y efecto en el #1229, estabilidad de contratos N4/N12/HITL. NO desplegar hasta gate.

## Estado verificado
- [PR #1238](https://github.com/AI-Gen-AI/C2Pro/pull/1238) WBS1.3 pre-HITL citas: tests específicos PASS; QA merge local con #1235 y #1237, 145 tests focales PASS; merge QA `cb60b02d9e3207cf296087a8090fb6e01f771944` (no desplegado).
- [PR #1239](https://github.com/AI-Gen-AI/C2Pro/pull/1239) WBS2.1 source-window: 14 tests PASS. CI de #1235/#1237/#1238/#1239: Secret Scan y Install Drift Guard SUCCESS en respectivas HEADs.
- Son cuatro PRs DRAFT; no hay análisis end-to-end del contrato completo bajo el nuevo motor, ni ledger PG activo ni cambios al piloto.
