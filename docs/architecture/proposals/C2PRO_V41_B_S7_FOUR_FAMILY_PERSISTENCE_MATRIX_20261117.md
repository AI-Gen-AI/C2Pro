# C2Pro V4.1 / Frente B — matriz S7 de cuatro fuentes EPC (17/11/2026)

**Scope exacto:** cuatro ficheros sintéticos **ya existentes**, no
un contrato real ni nuevos documentos generados. Test reproducible:
`apps/api/tests/integration/document_flow/test_s7_triplet_four_family_wbs_evidence_pg.py`.
Proveedor IA: **no invocado**. El test usa PostgreSQL 16 en la DB
deséchable `c2pro_front_b_s7_triplet_20261117_test`,
el mismo `UploadDocumentUseCase`, worker de ingesta y
`evaluate_project_coherence` que el producto. Persistencia contrastada
en **nueva sesión de base de datos**, no solamente objetos de Python.

## 1. Inventario y procedencia realmente verificadas

| Familia | Archivo fijado en el repo | SHA256 | Localización comprobada |
|---|---|---|---|
| Contrato DOCX | `triplet-contract.docx` | `5d85acdfc54601e174383361acbb5ef4126a9d1a0b181d3bebeeb82371ff7c4a` | Párrafos 3 y 4: precio y fecha final; `clauses` con documento original |
| Presupuesto XLSX | `triplet-budget.xlsx` | `aabcbf422887f5eaae0a4846019403d6f90cdf451e0fdc649487f9cba08847ac` | Hoja `Presupuesto`: partidas 2–4 y total fila 5; `document_source_units` por revisión |
| Cronograma XLSX | `triplet-schedule.xlsx` | `7b05eb8c4c86e040ffea4010ffa8bfbdab7a43d011b04aaea6dc815d0ce37fee` | `Plan!4`: entrega 30/09/2027; `document_source_units` y metadato `schedule_planned_finish` |
| Especificación DOCX | `triplet-specification.docx` | `41120f87b1e7e1710396f1388e6ecff78f0eb64582de802077ccb27196dc11a0` | `Section 4.1.2` hormigón >35 MPa a 28 días, `Section 4.2` acero B500S; `clauses` con revisión, offsets y `verification_status=unverified` |

Los IDs de tenant, project, document y revision se crean **solo en la
DB aislada**, son UUID estables durante la ejecución, se contrastan con
sus filas durables de `documents` + `document_revisions` desde
otra conexión y se verifican contra los hashes de los cuatro bytes
originales. No deben citarse esos UUID efímeros como IDs de producción.

## 2. Matriz fuente → discrepancia → WBS → resultado persistido

| Fuente comparada | Hecho determinista | Resultado de aplicación y persistencia | Relación WBS / autoridad |
|---|---|---|---|
| Contrato precio 1.000.000 € ↔ presupuesto 1.500.000 € | **+500.000 €**: 50% del contrato, 33,3% del presupuesto | `DET-CRS-CONBUD` y `DET-CRS-NEGMARGIN`, alertas **CRITICAL en el ledger observado** (la severidad es propiedad del mirror y debe revisarse por QA) persistidas en `alerts`; `detection_evidence.structured_sources[]` contiene documento, revisión y fila origen del presupuesto | Existe WBS canónica (raíz y nodo humano), **sin vinculación aprobada partida→nodo**, no atribuir la diferencia a paquetes WBS |
| Fin de contrato 30/06/2027 ↔ `Plan!4` 30/09/2027 | **92 días naturales** posteriores | `ADV-SCHDEAD-PROVISIONAL`, alerta MEDIUM persistida con revisión y localizador del cronograma; la cláusula contractual es comprobable en la fuente, pero **source_clause_id=null** mientras el contrato no esté aprobado; **no** `DET-CRS-SCHDEAD` confirmado | Cronograma **no** es baseline aprobado ni fecha WBS; no crear alerta de incumplimiento firme |
| Obligación contractual ↔ especificación 4.1.2 / 4.2 | Requisitos técnicos extraídos: 35 MPa y B500S; **no hay contradicción comparable** | `clauses` conservan sección, offset y revisión, pero `manually_verified=false` y `technical_requirement.verification_status=unverified`; dimensión TECHNICAL **no evaluada** | No existe vínculo humano aprobado requisito→WBS; no promover a VERIFIED |
| Las cuatro fuentes ↔ WBS canónica | Mismo `project_id` para cuatro revisiones; árbol WBS de prueba independiente | La ingesta y la evaluación dejan **idénticos** nodos, RACI, BOM y fechas; nada convierte una fila XLSX en WBS | **Solo asociación de proyecto**, no autorización de baseline ni referencia aprobada fila→nodo; S7 funcional sigue NO-GO |

**Evidencia estructurada del PostgreSQL:** `docs/architecture/proposals/C2PRO_V41_B_S7_FOUR_FAMILY_PG_EVIDENCE_20261117.json`, SHA256 `759194828246cfb12fcd5297ab295fe57f98707152f46acb4c6c0e6a4b1772f6`. Contiene IDs UUID exclusivamente sintéticos, SHA originales, revisiones, `source_row_locators`, severidades y `alert_evidence_bindings`. El alert advisory conserva la fila `Plan!4`, y ahora también conserva el `blob_sha256` tras su verificación contra `document_revisions` y `document_source_units`; `source_clause_id` permanece `null` por ausencia de aprobación del contrato. `AUDIT_INCOMPLETE` es una cuarta alerta persistida para cobertura insuficiente; la fuente no está declarada completa.

**Corrección diferencial:** las dos reglas económicas comparten ahora una misma clave de discrepancia, los mismos importes y la misma revisión/fila: **dos alertas, un único impacto**. La prueba RED dio una penalización 1,83 frente a 1,00; tras el cambio, 1,00 con ambas alertas conservadas. La severidad `CRITICAL` deriva del umbral numérico >20% del motor (`CONBUD` 33,3% sobre el mayor valor y `NEGMARGIN` 50% sobre contrato) y se transmite con `severity_qualification=NUMERIC_MATERIALITY_NOT_VERIFIED_CONTRACTUAL_LOSS`: **no acredita pérdida ejecutada ni incumplimiento confirmado**. El `overall_score` actual continúa `null` por cobertura insuficiente. Se exige revisión independiente del criterio de severidad.

**Precisión:** en la fila económica, la diferencia absoluta es
500.000 € y la magnitud relativa debe expresar su denominador:
50% *del precio del contrato*; 33,3% *del presupuesto*. No existe
dato de margen objetivo, base fiscal ni cambio aprobado en los
ficheros; la alarma es una discrepancia nominal, no una factura de
sobrecoste ejecutado.

## 3. Invariantes y resultado del test diferencial

El ensayo de PostgreSQL consulta `document_revisions`, `clauses`,
`document_source_units`, `alerts`, `coherence_results` y
`wbs_nodes` (más RACI/BOM) en transacciones reales.

- 4/4 SHA256 y revisiones originales verificadas.
- Las alertas por importe y plazo permanecen durables y con referencias.
- La especificación se persiste como fuente **no verificada**.
- `coherence_results` sigue vacío, `overall_score=null` y
  TECHNICAL figura entre las dimensiones no evaluadas.
- No aparece una alerta confirmada de incumplimiento de plazo
  simplemente porque la fecha planificada del XLSX sea posterior.
- No se altera la WBS ni se autogeneran vínculos aprobados.
- Un repositorio tenant-scoped no entrega revisiones a tenant ajeno.

## 4. Qué NO ha quedado demostrado y quién lo tiene

**Backend WBS/ProjectGraph + UX/HITL (principal):** la WBS de este
fixture es de origen legacy/humano y no proporciona un acto de
aprobación moderno para las **cuatro fuentes**. El sistema dispone de
servicios de aprobación explícita de vínculos y tests separados con
otros datos sintéticos (`test_s7_structured_wbs_three_source_pg.py`,
`test_adr032_s7_pg_evidence.py`), pero mezclarlos con los
cuatro ficheros autorizados o afirmar que estos últimos ya fueron
aprobados sería fabricar evidencia. Requiere flujo legítimo de revisión
humana de cada source-row/requisito y baseline única.

**Frente A (dependencia):** entrega de la cadena de procedencia
N2→documento original→revision; N4/N12 reales y candidatos solo
cuando su evaluación está completa y la cita es verificable.

**Ops/QA (dependencia):** ejecución S7 en entorno desplegado con Clerk
y un revisor independiente, persistencia duradera multiusuario,
validación cross-tenant y navegación real a la fuente.

**CORE:** acepta o rechaza el alcance funcional S7; **este ensayo no
promueve Product Control, ProjectGraph ni el Complete Journey.**

**Veredicto:** `GO` en persistencia S7 de cuatro fuentes y detección
de incoherencias acotadas; `NO-GO` en vinculación gobernada completa
a WBS, autoridad de fuente técnica y Coherence global.
