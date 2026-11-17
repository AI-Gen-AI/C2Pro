# C2Pro V4.1 — Frente B: auditoría de sobrecostes y procedencia Coherence

Date 2026-11-17. Owner Frente B. Parent PR #1256, based on SHA
`1db5f739f95e0f1f34b3102a22d93e6de59ef1d2`.
**Draft, not merged, not deployed.**

## 1. Defecto financiero corregido

En #1256 un resultado Coherence con **coste verificable superior al
importe reservado** se convertía en UNKNOWN y retenía el importe de la
reserva, aun cuando la información necesaria para facturar existía.
La situación impedía distinguir dinero realmente facturado de gasto
incertidumbre.

Nueva regla:

- **Coste conocido finito y no negativo, incluso > reserva**:
  primero `SETTLED` por el coste de proveedor completo mediante el
  ledger PostgreSQL compartido (N4/N12/Coherence); se libera la reserva
  y el gasto real puede superar lo previsto. **Después** de contabilizar,
  se rechaza el resultado semántico cuando supera el cap por llamada o
  el límite de continuaciones. No se borra el recibo ni se presenta como
  evaluación aprobada.
- **Coste ausente, NaN, infinito, negativo o cero no justificable con
  tokens**: `UNKNOWN` con el importe reservado retenido; se necesita
  conciliación con proveedor. No se inventa $0.
- **Contenido JSON inválido con coste conocido**: gasto facturado
  `SETTLED` pero resultado `UNASSESSED`; no hay ascenso de confianza.

Nueva auditoría no destructiva de ambos ledgers:
`PendingLedger.settled_overage_count`,
`PendingLedger.settled_overage_usd` y hallazgo
`PROVIDER_CHARGE_EXCEEDED_RESERVATION`. Se detecta el exceso aunque el
presupuesto mensual total siga teniendo saldo. La conciliación interna
contable puede ser correcta aun si existe sobrecoste; el seguimiento
financiero permanece obligatorio.

## 2. Coherence multifuente: sin inventar una revisión

`verify_coherence_project_manifest` consulta por **revisión real** la
tabla `document_revisions` con `tenant_id,project_id,document_id,
revision_id,blob_hash,valid_to`, dentro de transacción que impone
`app.current_tenant`. Conserva la revisión exacta, su contenido-addressed
SHA-256 original y el run_id de la orquestación. Valida el conjunto
*seleccionado* de documentos, rechaza duplicados, tenant/proyecto falsos,
revisiones inexistentes y revisiones no actuales.

La salida es un manifiesto tipado y ordenado determinísticamente. Una
evaluación cuyo origen es **exactamente un documento** puede obtener su
`CoherenceCallIdentity` mediante `bind_clause_source(document_id,
revision_id)`; la clave de facturación se mantiene estable e incluye
la identidad original. Una cláusula que combina **varios documentos**
se rechaza: no se le asigna artificialmente una única revisión. Requiere
una interfaz de escrow distinta para agregados multifuente y un
ProjectState/versionado de origen validado.

**Límites de esta verificación**: no acredita que el conjunto de
revisiones seleccionado incluya todos los documentos relevantes, ni
valida por sí sola la correspondencia literal de una cláusula o la
autenticidad de un PDF a través de OCR. El dueño de la ingesta y
orquestación debe proporcionar los IDs seleccionados, demostrar
cobertura/correspondencia de fuente y persistir el run_id antes de
utilizar el adaptador. La verificación SQL sola no autoriza activar
Coherence en el grafo productivo.

## 3. Evidencia y prueba conjunta

Pruebas en PostgreSQL 16 **real aislado** (BD `*_test`):
- Coherence con costo proveedor medido 0,48 USD sobre reserva 0,30 USD;
  se comprueba `SETTLED` 0,48, 0 reserva, alerta de sobrecoste, rechazo
  semántico y no duplicación del proveedor por replay.
- Respuesta sin costo demostrado `UNKNOWN`, hold intacto.
- Concurrencia de N4 reserva 0,25, N12 reserva 0,20 y Coherence intenta
  0,20 bajo cap global 0,55: primera Coherence DENIED, 0 requests;
  tras conciliación N12 a 0,08, una Coherence autorizada 0,12,
  mismo contador global y auditoría consistente.
- Documento A y documento B del mismo proyecto tienen revisiones
  verificadas y claves diferentes; asociación equivocada o agregado
  sin identidad rechazada, aislamiento tenant y revisión obsoleta.

Los valores monetarios son **fixtures**, no cargos reales. Las llamadas
al modelo son STUBS. No hay gastos de proveedor ni validación contractual
con PDF auténtico.

## 4. Plan de conciliación con el piloto CORE

1. Antes del piloto autorizado, CORE debe aportar tenant/proyecto/run
   auténticos, la fuente y revisiones verificadas, versión exacta de
   grafo y del módulo de finanzas, permisos de modelo y tarifas.
2. Guardar por llamada `tenant`, `source`, `reservation_id`,
   `idempotency_key`, `model`, límite estimado, estado, tokens,
   coste medido y, cuando exista, referencia de recibo del proveedor.
3. Comparar con gasto medido por el proveedor (no equiparar una
   estimación de wrapper a la factura externa); marcar discrepancias.
4. No repetir operaciones UNKNOWN ni liberar reservas antiguas
   automáticamente. Resolver mediante procedimiento autorizable con
   evidencia del proveedor; registrar autorización/decisión y saldo.
5. Mantener bandera `C2PRO_COHERENCE_ESCROW` **OFF** por defecto
   hasta identidad multifuente completa y QA independiente exitosa.

## 5. Gates

- G2 financiero **NO-GO productivo** mientras falten piloto real y
  revisión independiente del ledger/cobros; regresiones aisladas PASS
  no equivalen a validación de factura.
- S4 Coherence **NO-GO** para agregados multifuente y activación
  del grafo, aunque el enlace de un documento validado esté listo.
- Frente A conserva #1255 (N12 LangGraph/escrow) y CORE controla
  journey/autoridad de proveedor. No fusionar fuera de orden.
