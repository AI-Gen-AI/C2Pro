# CORE: bootstrap de ProjectState con evidencia revisada (09/11/2026)

Estado: implementación candidata AISLADA, NO conectada a producción; CORE NOT_UAT/NO_RELEASE.

## Causa y objetivo

Para EPC-SYN-2026-11-05, PostgreSQL contiene 4 documentos, 6 cláusulas de contrato y 3 riesgos en análisis, pero no ProjectState canónico. El SnapshotWriter consume ProjectState; sin materialización emite Health honesto NULL y Coherence no calculado.

## Solución candidata

- TrustedRevisionBundle agrupa un artefacto TRUSTED + ACTIVE obtenido exclusivamente de un lector autenticado por tenant/proyecto y sus cláusulas físicas de la misma revisión.
- Projector rechaza revisiones duplicadas, referencias de otro documento/proyecto/tenant, citas inexistentes y riesgos sin VERIFIED + pasaje literal único en una única cláusula física.
- Mantiene la identidad física de la cláusula y un identificador de riesgo determinista por revisión+índice+hash.
- EvidenceTier.WEAK es deliberado: localización de texto no equivale a validación contractual del significado.
- Materialización idempotente solo en ausencia de ProjectState; si ya existe otro estado, retorna reconciliation_required y NO sobrescribe, evitando borrar correcciones humanas.
- No escribe ni siquiera un estado vacío cuando faltan cláusulas de alguna revisión, riesgos con citas válidas o hay riesgos descartados. Especialmente: no interpretar cero riesgos verificados como clean assessment 90.
- Repositorio del ProjectState sigue siendo el único escritor y conserva la semántica transaccional no-commit.

## Límites, pendientes antes de wiring runtime

1. El consumidor debe consultar list_trusted_for_project() en la misma transacción tenant-scoped y leer cláusulas físicas ligadas a (tenant, documento, revisión). Un booleano supplied por cualquier cliente jamás acredita TRUSTED.
2. Cablear tras punto de confianza real y antes del snapshot, con bloqueo por proyecto y reconciliación de nuevos artefactos; no permitir que mark_loaded_projected confirme un estado canónico pendiente.
3. Verificar prueba de PostgreSQL aislado con el mapeador puro y SnapshotWriter, además de rechazo A/B y propuesta pendiente.
4. Health y Coherence son distintos. El bootstrap puede habilitar una dimensión Health con evidencia confiable, pero nunca eleva N8 Coherence global por la puerta trasera, ni aprueba HITL ni justifica UAT.

No deployment, no backfill de usuario, sin IA pagada, sin cambios de umbrales.
