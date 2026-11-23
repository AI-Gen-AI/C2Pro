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
