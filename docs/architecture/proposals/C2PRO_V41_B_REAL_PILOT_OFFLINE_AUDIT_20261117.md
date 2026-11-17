# C2Pro V4.1 — Frente B / primer piloto real: auditoría offline y bloqueo N4

17/11/2026. Run canónico [44007355327](https://github.com/AI-Gen-AI/C2Pro/actions/runs/44007355327);
código Frente A `61df7648715085112ad41dacf61565e57725b710`. Inspección
con lectura única del artefacto `c2pro-v41-real-evidence-61df7648715085112ad41dacf61565e57725b710`.
SHA256 `real_analysis_evidence.json`:
`549ca20b14549e7d74aee1452a33e43f8aa526036fb57a5d07cc83be55f61cad`.
No llamadas nuevas a modelos, bases compartidas ni cuentas.

## Evidencia financiera efectivamente observada

- Gobernador: 25 eventos `reserve` y 25 `done/completed`, con 25 claves
  de llamada únicas y 25 IDs de solicitud del proveedor únicos.
- N3: `CLASSIFIED`, recibo legacy `SETTLED`, costo estimado USD
  **0.003808**. El ledger N3 **no** expone `provider_request_id`; el
  gobernador conserva el ID de esa llamada, pero la CLI financiera
  JSON-only no certifica por sí sola deduplicación inter-lane.
- N4: 24 recibos `SETTLED`, ordinales 0..23 sin huecos ni repeticiones;
  sus 24 IDs de proveedor aparecen en los 25 `done` del gobernador.
  Costo estimado N4 **0.390586 USD**.
- Total ledger N3 + N4 = **0.394394 USD**, idéntico al total de eventos
  completados. Balance de tenant serializado como float:
  `0.39439399999999997` USD, diferencia residual de precisión IEEE-754;
  `ai_spend_reserved_usd=0.000000`.
- Presupuesto mensual del tenant de prueba: **5.00 USD**. No se observa
  reserva pendiente **en ese snapshot**; el coste es estimado a partir
  de tokens, **no factura ni cargo externo verificado**.
- N4 cuenta 142 candidatos, pero reporta `status=PARTIAL` y
  `examined_windows=0` de 24. N12 `NOT_STARTED`, HITL
  `PENDING_REVIEW`, N8/ProjectGraph `UNASSESSED_NOT_PROMOTED`.
  Los 142 candidatos NO son riesgos validados.

## Resultado de la CLI y corrección aislada

En la SHA B previa `8bca22a13`, la CLI existente devolvía:
`INTERNAL_LEDGER_INCONSISTENT` con
`N4_ANALYSIS_NOT_COMPLETE` + `TENANT_CONFIRMED_SPEND_MISMATCH`,
causado por comparación exacta de Decimal(receipts) frente a un float
serializado en JSON. No era una diferencia real de gasto.

La corrección compara estrictamente, excepto ruido inferior o igual a
`1e-12` USD **solo** si el balance fue expuesto como `float`. Strings
y registros de recibos no obtienen tolerancia; diferencias de
`0.000001` USD siguen fallando; reserva UNKNOWN, duplicados,
sobrecostes y cap permanecen protegidos.

CLI sobre el mismo archivo real, después de la corrección:
`PARTIAL_PILOT_NO_GO`;
`internal_ledger_consistent=true`;
`findings=[N4_ANALYSIS_NOT_COMPLETE]`;
`invoice_verified=false`.
El **exit code sigue siendo 1** de forma intencionada: N4 no es
funcionalmente completo y la ejecución no certifica UAT.

## Límite de aceptación y handoff

La conciliación del snapshot es **interna, offline y de un único run**.
No demuestra facturación externa, ni idempotencia entre ejecuciones
diferentes, ni que todos los documentos EPC estén cargados. La fuente
real analizada es el filing SEC de 73 páginas, distinto del PDF Library
de 94 páginas. Los enlaces contractuales deben validarse contra la
fuente literal correcta; no aprobar automáticamente las citas.

Frente A debe investigar contador de ventanas, persistencia y asociación
de hallazgos antes de cualquier repetición: las 24 llamadas N4 están
documentadas como completadas en el gobernador. Frente B verifica
ledger e inventario y puede reutilizar el artefacto offline sin pagar
otra llamada. G1/G2/G4 y despliegue/merge **NO-GO** hasta evidencia
semántica real, N12, HITL, ProjectGraph, revisión independiente
de la SHA final y factura cuando proceda.

Pruebas focales locales ejecutadas con `pytest --noconftest` para
evitar dependencias globales de un entorno VPS no aislado; el resultado
no sustituye el job CI ni la regresión PostgreSQL en DB desechable.


## Endurecimiento posterior de la CLI (SonarCloud S8707)

La auditoría offline lee exclusivamente un
`real_analysis_evidence.json` localizado dentro del directorio de
extracción elegido como **directorio actual** del operador. Rechaza
rutas absolutas, `..`, enlaces simbólicos que escapen de la raíz y
nombres de fichero no coincidentes. El cambio exige invocar desde la
carpeta de extracción en lugar de suministrar una ruta absoluta.

Ejemplo (el código puede estar fuera de la carpeta de evidencias):

```bash
cd /ruta/segura/extraida
PYTHONPATH=/ruta/repo/apps/api python /ruta/repo/apps/api/scripts/audit_v41_finance_evidence.py \
  _temp/c2pro-v41-real/real_analysis_evidence.json
```
