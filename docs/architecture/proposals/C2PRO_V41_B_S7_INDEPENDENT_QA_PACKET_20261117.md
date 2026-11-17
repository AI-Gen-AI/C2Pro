# C2Pro / Frente B — paquete de revisión QA independiente S7

**Solicitante:** CORE #1049 · **PR propietaria:** #1258 (DRAFT)
**Revisor solicitado:** Elena o persona expresamente designada por CORE.
**Dictamen independiente:** **PENDING**; ningún agente de IA de pago ha sido ejecutado.

## Qué revisar exactamente

El anterior GO técnico S7 sobre B `5935297ec2ab6a65e14a64ff14b917dfb6e6b0d3`
era correcto **solo** para el cálculo v1 focal y la procedencia del
fixture. La revisión diferencial posterior ha detectado dos rutas más
que **no** consumían ese deduplicado:

1. **Coherence v2**: `calculate_v2_from_signals` y
   `build_conflict_candidates` consideraban `DET-CRS-CONBUD` +
   `DET-CRS-NEGMARGIN` como **dos conflictos independientes**, con
   `independent_count=2` en el modelo canónico de conflictos.
   **Prueba RED reproducida**; cambio: una señal independiente por
   mismo valor y misma revisión/fila original, sin cambiar las dos
   alertas del ledger. Una revisión de presupuesto diferente permanece
   como conflicto independiente.
2. **Canary / breakdown**: el desglose de BUDGET informaba
   `alert_count=2` y `critical=2` cuando había un solo impacto
   económico. **Prueba RED reproducida**; cambio: desglose de
   **impactos independientes** para alimentar canary, mientras la lista
   detallada mantiene dos reglas explicables.
3. **Persistencia de fuente**: el SQL de vinculación de filas originales
   se protege con `FOR SHARE OF r,u` dentro de la **misma transacción**
   que la reconciliación del ledger de alertas, para que un retiro
   concurrente de la revisión no pueda invalidar la fuente antes del
   COMMIT. Prueba PG con revisión realmente retirada bajo SAVEPOINT
   debe devolver `NOT_VERIFIED`, junto a pruebas anteriores de tenant
   ajeno, localizador incorrecto y hash manipulado.

No hay cambios en B1 finanzas, en proveedores N4/N12 ni en HITL.

## Checklist de dictamen independiente

| Componente | Evidencia que debe verificar QA | Riesgo residual |
|---|---|---|
| Clave económica | Dos importes+identidad del original Budget document/revision/locator; colapsa solo reglas CONBUD+NEGMARGIN; cambio de revision, importes o fila no colapsa | **Identidad original del contrato** no forma parte del hash de grupo, porque el agregador v1 actual solo expone `contract_total` y la referencia de fila de presupuesto. Se necesita handoff fiable de origen contractual para demostrar que dos contratos distintos con mismo valor no convergen dentro de una misma evaluación. No elevar a certificación multicontrato |
| Scorer v1 | `calculate_detailed` y `calculate_from_signals` usan un solo impacto; unidades con cobertura completa y UNKNOWN | Scoring de fuentes ajenas a este par no agrupado |
| v2/conflicts | `calculate_v2_from_signals` y `build_conflict_candidates`: una sola `detected_conflict` para el par; dos para distinta revisión | Shadow sólo se enciende por flags; falta UAT de tenant real |
| Canary | `_build_category_breakdown` un impacto crítico, aunque hay dos alertas originales | No equivale a revisión de materialidad jurídica |
| Severidad | `CRITICAL` describe prioridad **numérica >20%**, `severity_qualification` niega pérdida contractual confirmada | Materialidad EPC final requiere responsable funcional/QA |
| Fuente original | SHA revision-bound de `Presupuesto!5`, `Plan!4`; contrato `source_clause_id=null` mientras no hay aprobación | Test no equivale a revisión HITL del contrato |
| Atomicidad | Misma transacción Alert + `FOR SHARE` de revisión/fila en lectura; savepoint muestra rechazo a revisión retirada | No hay prueba de concurrencia revision-INSERT vs link read; requiere QA PostgreSQL dirigido antes de garantía plena |
| WBS | `require_linkable_wbs_nodes` falla sin baseline aprobada; no eventos humanos fabricados; WBS existente no se altera | No hay relación fuente→nodo con acto HITL del mismo corpus autorizado |
| Score incompleto | `overall_score=null`, TECHNICAL=NOT_ASSESSED y alerta AUDIT_INCOMPLETE | Complete Journey NO-GO |

**Archivos principales para revisar:**
`apps/api/src/coherence/economic_signal_dedup.py`,
`scoring.py`, `services/v2/conflict_service.py`,
`graph/nodes.py`, `structured_source_binding.py`,
`router.py`,
`tests/unit/coherence/test_s7_economic_impact_grouping.py`,
`tests/integration/document_flow/test_s7_triplet_four_family_wbs_evidence_pg.py`.

**Separación de corpus:** cuatro archivos DOCX/XLSX `triplet-v1` de S7
no son el contrato real SEC 73 páginas de A ni SolarMax 94 páginas.
No reutilizar resultados entre ellos ni levantar estados VERIFIED sin
fuente/HITL real.

## Resultado que QA debe emitir a CORE (sin presupuestar IA)

Uno de `PASS`, `PASS_LIMITED` o `CHANGES_REQUIRED` por
**B1, S3 y S7**, con SHA comprobada, pruebas efectivamente ejecutadas
y limitaciones. Si no se puede demostrar la identidad de un contrato
distinto, emitir `PASS_LIMITED` o `CHANGES_REQUIRED` para ese
supuesto, nunca `PASS` multicontrato.

**Entrega S7 funcional:** `NO-GO` hasta que Backend WBS + UX/HITL
demuestren el evento humano `source revision → approval → canonical
WBS node` en las mismas cuatro fuentes con baseline aprobada. Ninguna
prueba automatizada suplanta esa aprobación.
