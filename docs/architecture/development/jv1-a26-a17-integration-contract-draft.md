# JV1 A26 ↔ A17 — Contrato de integración propuesto (NO WIRING)

**Estado:** DRAFT / DEPENDENCY_HOLD (23-11-2026). **Propietario de este documento y del
cálculo puro:** L5b. **Propietario del servicio, rutas, transacción y persistencia:** L5a/A17.
Este documento es una interfaz *propuesta*, no acredita implementación ni GO de producción.

## Contexto verificable

- A26 #1303: `src.coherence.application.validated_findings_evidence` publica
  `ExposureFact`, `ExposureBands`, `ScorePair`, `ExposureScore` y
  `calculate_exposure_score(facts, cfg)`. Es puro, sin I/O, sin base de datos,
  sin integración, sin carga de YAML y sin proveedor.
- A17 #1302: `evaluate_coherence_in_application` persiste los resultados V1 en
  `CoherenceResultORM` y `run_project_evaluation_after_approval` serializa por
  tenant/proyecto/revisión, con marcador `scoring_snapshot.a17_approval_id`.
  **No llama a A26**, y no debe modificarse desde L5b.
- `exposure_bands.yaml` contiene `calibrated: false`; severidades y escala de
  materialidad **sin valores productivos**. La prueba usa configuración sintética
  `SYNTHETIC-ONLY`, no una calibración aprobada.

## Interfaz de entrada: adaptador A17, aún NO implementado

El futuro adaptador, **fuera del PR A26**, resolverá información autoritativa de
la revisión y de evidencias aprobadas. No aceptará campos de identidad de un cliente
HTTP como fuente final. Por cada hecho enviará:

| Campo A26 | Contrato exigido |
| --- | --- |
| `canonical_key` | Identidad canónica *tipada* de hecho/cláusula; estable dentro del proyecto y revisión. No es el mero texto ni el ID de la fuente duplicada. |
| `dimension` | Una de `SCOPE/BUDGET/LEGAL/TIME/QUALITY/TECHNICAL`; alias se normalizan en adaptador, no se adivinan. |
| `severity` | `LOW/MEDIUM/HIGH/CRITICAL` asignada según política versionada; si no se puede validar, no emitir un hecho puntuable. |
| `state` | `PENDING`, `CONFIRMED`, `REJECTED` desde decisión HITL final y trazable; nunca inferir confirmado por mera aceptación del riesgo. |
| `evidence_id` | Identificador de evidencia real verificable, no vacío. Fuente, cláusula, revisión y, si es cita documental, página física validada se resuelven aguas arriba. Sin evidencia el hecho queda fuera de la puntuación. |
| `materiality` | Opcional; nulo significa desconocido, no cero confirmado. Unidades/moneda/fecha y escala dependen de calibración V2. |
| `accepted_risk` | Metadato de disposición, no mitigación. `true` **no puede elevar el Score**. |
| `mitigation_fraction/verified/evidence_id` | Descuento sólo si la mitigación es válida y su evidencia está verificada; intervalo cerrado [0,1]. |

**Ámbito de seguridad externo al motor puro:** `tenant_id`, `project_id`,
`evaluation_id`, `approval_id`, `source_revision`, `snapshot_schema_version`,
`score_algorithm_version` y `calibration_revision` deben viajar en un sobre
tenant-bound verificable. No introducir tenant como dimensión de deduplicación
dentro de A26: el motor puro recibe un lote ya filtrado por tenant/proyecto
y el adaptador deberá probar el aislamiento antes de llamarlo.

**Estado/precedencia:** un mismo par `(canonical_key,dimension)` se deduplica.
Si coexisten `CONFIRMED` y una copia `PENDING` obsoleta del mismo hecho,
prevalece confirmado. Dentro de un estado, exposición máxima verificada; el
orden y el número de fuentes no alteran el resultado. Un `REJECTED` no puntúa.
Transiciones nuevas sólo con decisión auditada; nunca reciclar una copia de
revisión anterior como hecho actual.

## Salida y semántica

`ExposureScore` contiene `global_score: ScorePair`,
`dimensions: dict[dimension, ScorePair]`, `validated_fact_count` y
`pending_fact_count`. Cada `ScorePair` tiene `validated` y `projected`
en [0,100], o `None` si no hay evidencia evaluable para esa vista.

- `validated`: sólo hechos confirmados; `projected`: confirmados y pendientes.
- Los seis nombres son fijos; ninguna dimensión sin hechos corroborados recibe
  un 0 ni un 100 ficticio.
- Pesos renormalizados sobre dimensiones con resultado evaluable; la proyección
  global no podrá superar el valor validado por una dimensión nueva pendiente.
- Aceptar el riesgo no es reducir impacto; mitigación sin verificación no descuenta.
- No confundir score ausente con `score=0` ni guardar el número de prueba como real.

**Brecha explícita para V2:** actualmente la interfaz pura recibe hechos, **no**
una prueba explícita de dimensión `assessed_clean` sin hallazgos. Por tanto una
dimensión sin hechos devuelve `None`, incluso si A17 tiene `coverage_map=True`.
La política para incorporar una dimensión limpia y corroborada como 100 requiere
acuerdo L0/L5a/V2 y nuevas pruebas, nunca completar con 100 por defecto.

## Integración segura / no habilitada

1. A17 debe estar fusionado y revalidado sobre el SHA final, incluida
   persistencia/relogin/replay e idempotencia PG real tenant-bound. Hasta entonces
   **no modificar A17 desde L5b**.
2. El adaptador futuro traduce `scoring_snapshot.findings` (schema v1,
   `finding_key`, `observation_key`, `signal`, `alert`) a hechos tipados;
   **este snapshot no aporta por sí solo** todos los campos A26 verificados.
   No equiparar `acknowledged`, `accepted_risk` o alertas a nuevas mitigaciones.
3. Verificar, antes del cálculo, que los datos pertenecen al mismo tenant,
   proyecto, revisión y base de decisión, sin duplicados de fuentes. Fallar
   cerrado ante versión de snapshot, citas, referencias o calibración desconocida.
4. Los coeficientes de bandas, materialidad y pesos deben tener revisión V2
   documentada, aprobada y probada; el YAML actual bloquea el cálculo. Ningún
   bypass de `ExposureBands.validate` o inyección de coeficientes sintéticos
   fuera de tests.
5. **NO escribir A26 en `CoherenceResultORM.global_score` V1**: ese campo es
   entero no nulo, no admite el `None` de un Score sin evidencia. Necesita
   decisión de contrato/persistencia versionado de L0 y L5a; no sobrescribir
   autoridad histórica del Score V1.
6. Se requiere UAT de `N4/N12 → evidencias → HITL → A17 → A26 → persistencia
   → logout/relogin`, con snapshot y reproducción, pruebas de cambio de revisión,
   determinismo por SHA, aislación tenant y política de no facturación.
7. Merge/deploy/feature flag de A26: exclusivamente decisión explícita L0 tras
   calibración V2, CI y LV exact-SHA, contrato aprobado y pruebas integradas.

**Dictamen actual:** A26 `PURE_MODULE_READY_FOR_REVIEW`, A26↔A17
`NOT_IMPLEMENTED / DEPENDENCY_HOLD`, producción **NO-GO**.


## Anexo v0.2 — Matriz verificable de bordes y transiciones (L5b)

**Referencias de revisión:** A26 PR #1303 SHA `3df30ea4f2f5db014f1687aa759e8cb1110cb63b`;
A17 PR #1302 SHA `2bdec6c5d2b5a6d3860c5b764e772d6f7cc4de33`.
`calibrated: false` se mantiene. Los números en pytest proceden exclusivamente de una
configuración `SYNTHETIC-ONLY`, **no calibrada para negocio**.

V = Score *validado*, P = Score *proyectado*. `null` expresa dimensión sin
evidencia evaluable: **no es 0, ni 100, ni un riesgo aceptado**.

| ID | Borde/entrada | V esperado | P esperado | Prueba o puerta |
| --- | --- | --- | --- | --- |
| B01 | Cero hechos, seis dimensiones | `null` todas | `null` todas | `test_assessable_only_weight_normalization_and_all_null` |
| B02 | Sólo hecho PENDING con evidencia | `null` | Valor en su dimensión | `test_pending_moves_projected_only` |
| B03 | PENDING → CONFIRMED exact-row | Validado sólo después de resolución final | Retiene hecho confirmado | `test_rejected_and_pending_to_confirmed_transition` |
| B04 | PENDING → REJECTED | No incorpora hecho | No incorpora hecho | Mismo test, nunca rescatar rechazo |
| B05 | CONFIRMED + PENDING obsoleto mismo hecho/dimensión | Una sola entrada confirmada | Confirmado prevalece | `test_confirmed_same_key_supersedes_stale_pending_replica` |
| B06 | Dos fuentes del mismo hecho/dimensión | Una entrada | Una entrada | `test_duplicate_fact_across_sources_counts_once` |
| B07 | Clave canónica igual en dos dimensiones | Dos entradas legítimas | Dos entradas legítimas | Nueva prueba `test_matrix_typed_key_is_dimension_scoped` |
| B08 | Misma clave/dimensión, severidades distintas dentro de estado | Exposición máxima | Exposición máxima | `test_duplicate_key_uses_largest_exposure_within_same_state` |
| B09 | Aceptar riesgo CONFIRMED | No mejora | No mejora | `test_accepted_risk_does_not_raise_score` |
| B10 | Aceptar riesgo PENDING | No promociona a V | No mejora P | Nueva prueba `test_matrix_pending_acceptance_is_not_confirmation` |
| B11 | Mitigación declarada, no verificada | No descuenta | No descuenta | `test_mitigation_only_with_verified_evidence` |
| B12 | Mitigación verificada + prueba, fracción 0/1 | Identidad / reducción máxima sintética | Idem | `test_verified_mitigation_at_zero_and_full_boundary` |
| B13 | Mitigación verificada sin evidencia | Error | Error | `test_verification_without_evidence_is_rejected` |
| B14 | Falta evidencia del hecho | `null` si único | `null` si único | `test_ungrounded_facts_not_promoted` |
| B15 | Evidencia en blanco, dimensión/estado desconocidos | Fail closed | Fail closed | `test_invalid_or_unlocated_fact_fails_closed` |
| B16 | Materialidad inválida, NaN o mitigación fuera [0,1] | Error | Error | Mismo test |
| B17 | Sólo BUDGET evaluable; otras cinco sin evidencia | Peso BUDGET renormalizado, otras `null` | Igual | `test_assessable_only_weight_normalization_and_all_null` |
| B18 | Nueva dimensión PENDING eleva la media renormalizada | Validado invariable | P global no mayor que V | `test_new_pending_dimension_cannot_improve_global_score` |
| B19 | Bandas sin calibración / sin revisión | No Score | No Score | `test_uncalibrated_bands_refused` |
| B20 | Pesos distintos de 1, severidades no ordenadas | Error | Error | `test_bad_configuration_fails_closed` |
| B21 | Rechazos en las seis dimensiones | `null` global y dimensiones | `null` global y dimensiones | Nueva prueba `test_matrix_all_rejected_stays_null` |
| B22 | Revisión/hash documental cambia durante evaluación | No reutilizar versión anterior | No reutilizar versión anterior | Adaptador tenant-bound futuro; NO IMPLEMENTADO |
| B23 | A17 `no_document_clauses` / `evaluation_withheld` | `null`, A26 no se llama | `null`, A26 no se llama | Mantener razón durable A17; NO INTEGRADO |
| B24 | HITL 409/rechazo/provisional/replay | Sin nueva evaluación | Sin nueva evaluación | Autoridad y lock A17, no invocar A26; NO INTEGRADO |
| B25 | Reinicio Beat; aprobación pendiente en PostgreSQL | Sólo cuando existan evidencias | Sólo cuando existan evidencias | Un efecto idempotente por revisión A17; NO INTEGRADO CON A26 |
| B26 | Identidad ajena de tenant/proyecto o revisión desconocida | Rechazo previo al motor puro | Rechazo previo al motor puro | RLS y sobre de autenticación A17; NO IMPLEMENTADO |

### Tabla de transiciones de autoridad

| Transición | Quién puede decidir | Resultado permisible | Invariante |
| --- | --- | --- | --- |
| No evaluado → PENDING | Extractor con evidencia vinculada y procedencia comprobada | Sólo P | Nunca mejora V |
| PENDING → CONFIRMED | Decisión HITL final, autorizada, exact-row | Pasa a V y P | Copias pendientes obsoletas descartadas |
| PENDING → REJECTED | HITL final | Se excluye de ambos | Rechazo no genera resultado |
| CONFIRMED → accepted_risk | HITL registra disposición | V/P sin cambios | Aceptación ≠ mitigación |
| CONFIRMED → mitigated | Prueba validada de mitigación | Descuento V/P calibrado | Una declaración sin prueba no descuenta |
| Revisión A → revisión B | Versionado documental, control de hash | Recalcular lote B si está autorizado | No mezclar evidencias/revisiones |
| A17 pending → done | CoherenceResult duradero o evento withheld | Exactamente un efecto por aprobación | No modificar decisión humana; nunca Score numérico inventado |

### Dependencias y condiciones de calibración V2

| Gate | Requisito para salir de `calibrated:false` | Responsable / estado |
| --- | --- | --- |
| C01 | Semántica documentada `assessed_clean` vs ausencia de hechos; nunca asignar 100 automáticamente | L0 + L5a / OPEN |
| C02 | Bandas LOW/MEDIUM/HIGH/CRITICAL con fuente, unidades, sensibilidad y revisión firmada | Negocio + QA / OPEN |
| C03 | Materialidad: moneda, período, escala, límites y dato desconocido vs 0 explícito | Negocio / OPEN |
| C04 | Justificación de pesos de seis dimensiones; suma=1 y política de nulos | L0 + QA / OPEN |
| C05 | Normalización sólo de dimensiones evaluables y cap conservador P≤V bajo nueva dimensión pendiente | L5b / PURE probado; calibración OPEN |
| C06 | `score_algorithm_version`, `calibration_revision`, digest inmutable de configuración y lotes | Arquitectura / OPEN |
| C07 | Sobre tenant-bound: tenant, project, approval, review, source revision, hash y provenance; pruebas RLS rol no propietario | L5a/QA / OPEN |
| C08 | Persistencia separada de V/P/`null`; no sobrescribir `CoherenceResultORM.global_score` V1 no nulo | L0/L5a / OPEN |
| C09 | Baseline de negocio, validación independiente held-out, deriva y protocolo de recalibración | Negocio + QA / OPEN |
| C10 | UAT N4/N12 → evidencia → HITL → A17 → A26 → logout/relogin, broker sintético y coste cero | DevOps/A23 / INFRA_HOLD |

**Interfaz de integración final propuesta, no activada:** futura operación de A17
`build_exposure_facts(authorized_snapshot, review_decision, evidence_graph)`
devuelve sólo hechos con dimensión/evidencia/revisión verificadas y un sobre de
`tenant_id, project_id, approval_id, source_revision, source_sha, algorithm_version,
calibration_revision`. A26 ejecuta únicamente la función pura y devuelve
`ScorePair(validated, projected)` por dimensión y global; A17 conserva la
autoridad de permisos, estado, 409, idempotencia, PostgreSQL y decisión de
persistencia versionada. **No se implementa el adaptador en #1303**.

Prohibido aprobar una calibración copiando coeficientes de pruebas
`SYNTHETIC-ONLY`. Mantener `exposure_bands.yaml: calibrated: false`.
A26 sigue `DEPENDENCY_HOLD / NO_WIRING / NO_DEPLOY` hasta nueva decisión L0.
