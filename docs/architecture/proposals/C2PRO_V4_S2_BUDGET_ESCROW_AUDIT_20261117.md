# C2Pro V4 — Auditoría de reservas IA (Frente B, S2)

**Fecha:** 17/11/2026. **Dependencias:** PR #1250 → #1249 → #1248 → #1246 → #1245 → #1242 → #1239. **Estado:** nueva utilidad de lectura; no activación de proveedores ni despliegue.

## Riesgo y objetivo

N4 y las nuevas llamadas IA heredadas comparten `tenants.ai_spend_reserved_usd`. Si un worker falla después de enviar una petición al proveedor, el importe debe quedar como `RESERVED` o `UNKNOWN` hasta tener el recibo real. Un operador necesita detectar reservas antiguas, divergencias entre el contador global y los dos ledgers, y diferencias del bucket TENANT de N4. **No se deben liberar fondos automáticamente por antigüedad**.

## Implementación

`apps/api/src/core/ai/budget_escrow_audit.py` expone `audit_tenant_escrow(session, tenant_id, stale_after_hours=24)`. Devuelve un informe tipado que distingue:

- Saldo reservado en el registro de tenant frente a la suma de reservas pendientes de `n4_usage_reservations` y `legacy_ai_usage_reservations`; diferencia → `GLOBAL_ESCROW_MISMATCH`.
- Importe reservado en buckets `N4 / TENANT` frente a recibos N4 pendientes; diferencia → `N4_TENANT_BUCKET_MISMATCH`.
- Recuento separado de `RESERVED`, `UNKNOWN` y operaciones antiguas en cada ledger; `UNRECONCILED_PROVIDER_USAGE`, `STALE_INFLIGHT_RESERVATIONS`, `STALE_UNKNOWN_PROVIDER_USAGE`.
- Gasto confirmado y cupo mensual; si el proveedor ha facturado por encima de la estimación, se informa como `CAP_EXCEEDED_REQUIRES_REVIEW` sin borrar el importe ni clasificar automáticamente el exceso como corrupción.

**Aislamiento:** exige `app.current_tenant` explícito y coincide con el `tenant_id` autorizado; consulta el registro tenant con `FOR SHARE`, que serializa el informe contra los locks `FOR UPDATE` utilizados al reservar y conciliar. No lee otros clientes ni muestra contenido contractual, facturas o claves. El llamador controla la transacción. No hay mutaciones SQL.

## Ejemplo para operador autorizado, bajo una sesión tenant-scoped

```python
async with get_session_with_tenant(tenant_id) as session:
    report = await audit_tenant_escrow(
        session, tenant_id=tenant_id, stale_after_hours=24,
    )
    if not report.financial_reconciliation_passed:
        # Abrir incidencia QA/Finanzas, no activar nuevas rutas facturables.
        ...
    if report.needs_provider_followup:
        # Solicitar recibo, id del proveedor, tokens y coste verificables.
        ...
```

**No es un monitor automático:** la utilidad debe ejecutarse explícitamente por un servicio de Ops con identidad autorizada. Ni `UNKNOWN` ni una reserva caducada pueden convertirse automáticamente en gasto cero, `CANCELED` o aprobación de resultados. Un informe sin diferencias no demuestra la exactitud de la tarifa ni que las fuentes hayan sido analizadas; solo verifica consistencia contable interna.

## Alcance de QA

Pruebas PostgreSQL aisladas `*_test`: cero reservas, N4+legacy concurrentes, conciliación real de columnas, descuadres inyectados en fixture, UNKNOWN antiguo desde su inserción, sobregasto, aislamiento de tenant y concurrencia entre auditoría `FOR SHARE` y una nueva reserva `FOR UPDATE`. Se ejecuta regresión del Frente B y validación de linters.

## Pendientes / control de producción

- **Seguridad y Finanzas:** auditoría independiente sobre la SHA exacta; revisar uso del informe antes de habilitar nuevos gastos.
- **Integración:** la ruta Coherence LLM Gate usa el control previo pero todavía no reserva y no conserva información de coste suficiente para migrarla sin rehacer su adaptador de proveedor. No declarar cobertura universal.
- **Proveedor:** contrastar los recibos reales y precios vigentes con consumos registrados. Resolver con autorización humana las operaciones `UNKNOWN`, sin liberación automática.
- **CORE/Frente A:** integrar el puerto N12 solo cuando exista checkpoint persistido y fuente N2 validada; no tocar los nodos A desde este frente.
