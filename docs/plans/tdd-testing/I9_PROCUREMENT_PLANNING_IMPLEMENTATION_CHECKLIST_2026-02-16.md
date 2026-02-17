# I9 Procurement Planning Intelligence

## Alcance

Documento de estado de implementación y plan de pruebas para I9:

- `TS-I9-PROC-DOM-001`
- `TS-I9-PROC-APP-001`
- `TS-I9-PROC-APP-002`
- `TS-I9-PROC-ADP-001`
- `TS-I9-PROC-HTTP-001`
- `TS-I9-PROC-INT-001`
- `TS-SEC-I9-001`
- `TS-I9-PROC-TXN-001` (pendiente)
- `TS-I9-PROC-ADP-002` (pendiente)
- `TS-I9-PROC-INT-002` (pendiente)
- `TS-SEC-I9-002` (pendiente)
- `TS-SEC-S4-001` (cobertura transversal de seguridad I7-I9)

## Checklist Done

- [x] Existe implementación de dominio I9:
  - `apps/api/src/modules/procurement/domain/entities.py`
  - `apps/api/src/modules/procurement/domain/services.py`
- [x] Existe implementación de aplicación I9:
  - `apps/api/src/modules/procurement/application/ports.py`
- [x] Existen tests I9 en dominio y aplicación:
  - `apps/api/tests/modules/procurement/domain/test_i9_procurement_intelligence.py`
  - `apps/api/tests/modules/procurement/application/test_i9_procurement_planning_service.py`
- [x] Existen pruebas de seguridad S4 que cubren el gate de revisión humana en I9:
  - `apps/api/tests/security/test_s4_scoring_wbs_procurement_security.py`
- [x] Existe suite de seguridad dedicada I9:
  - `apps/api/tests/security/test_i9_procurement_security_red.py`
- [x] Existe suite de contratos app/repositorio I9:
  - `apps/api/tests/modules/procurement/application/test_i9_repository_contracts.py`
- [x] Existe suite de adapter persistence I9:
  - `apps/api/tests/modules/procurement/adapters/test_i9_persistence_tenant_filters.py`
- [x] Existe suite de adapter HTTP I9:
  - `apps/api/tests/modules/procurement/adapters/http/test_i9_planning_router.py`
- [x] Existe suite de integración de pipeline I9:
  - `apps/api/tests/modules/integration/test_i9_procurement_pipeline_integration.py`
- [x] Implementación `src/modules/procurement` expandida a capas adapter/integration:
  - `apps/api/src/modules/procurement/adapters/persistence/snapshot_repository.py`
  - `apps/api/src/modules/procurement/adapters/http/router.py`
  - `apps/api/src/modules/procurement/application/integration.py`
- [x] Verificación de ejecución realizada:
  - Comando:
    - `pytest apps/api/tests/modules/procurement/domain/test_i9_procurement_intelligence.py apps/api/tests/modules/procurement/application/test_i9_procurement_planning_service.py apps/api/tests/modules/procurement/application/test_i9_repository_contracts.py apps/api/tests/modules/procurement/adapters/test_i9_persistence_tenant_filters.py apps/api/tests/modules/procurement/adapters/http/test_i9_planning_router.py apps/api/tests/modules/integration/test_i9_procurement_pipeline_integration.py apps/api/tests/security/test_i9_procurement_security_red.py apps/api/tests/security/test_s4_scoring_wbs_procurement_security.py -q`
  - Resultado:
    - `18 passed`

## Checklist Pending

- [x] Remover fallback por `ImportError` en tests I9 para señal RED/GREEN estricta.
- [x] Definir y probar puertos/repositorio para I9 con filtro obligatorio por `tenant_id` (contract tests).
- [x] Implementar y probar adapters de persistencia en `src/modules/procurement/adapters/persistence` para I9.
- [x] Implementar y probar adapter HTTP para I9 en `src/modules/procurement/adapters/http`.
- [x] Añadir suite de integración I9 (`WBS/BOM -> procurement plan -> conflicts`) con verificación de trazabilidad.
- [x] Añadir hardening de seguridad I9:
  - No bypass de `requires_human_review` cuando hay conflictos `HIGH/CRITICAL`.
  - No leakage cross-tenant.
- [ ] `TS-I9-PROC-TXN-001`: atomicidad en capa aplicación (sin estado parcial en fallos `save/commit`).
- [ ] `TS-I9-PROC-ADP-002`: frontera transaccional en adapter de persistencia.
- [ ] `TS-I9-PROC-INT-002`: atomicidad de pipeline integrado y consistencia tras retry.
- [ ] `TS-SEC-I9-002`: hardening de seguridad sobre atomicidad y no exposición de estado parcial.

## Plan de Pruebas para Cierre de I9

- [x] `TS-I9-PROC-APP-002` (nuevo): contratos de puertos/repositorios y `tenant_id` obligatorio.
- [x] `TS-I9-PROC-ADP-001` (nuevo): aislamiento multi-tenant en persistence adapters.
- [x] `TS-I9-PROC-HTTP-001` (nuevo): contrato HTTP, errores y auth/tenant context.
- [x] `TS-I9-PROC-INT-001` (nuevo): flujo integrado y consistencia de salida.
- [x] `TS-SEC-I9-001` (nuevo/expansión): hardening de bypass y manipulación de impacto.
- [ ] `TS-I9-PROC-TXN-001` (nuevo): atomicidad transaccional en application service.
- [ ] `TS-I9-PROC-ADP-002` (nuevo): rollback transaccional en persistence adapter.
- [ ] `TS-I9-PROC-INT-002` (nuevo): integración con rollback/no partial-write.
- [ ] `TS-SEC-I9-002` (nuevo): seguridad de atomicidad y sanitización de error en fallos transaccionales.

## Criterio de Cierre (Definition of Done)

- [x] Todas las suites I9 (dominio, app, adapters, integración, seguridad) en verde.
- [x] Sin fallback de imports en tests I9.
- [x] Todas las rutas de lectura/escritura I9 con `tenant_id` aplicado (scope de contratos I9 actuales).
- [x] Evidencia de ejecución de pruebas anexada en este documento.
- [x] Estado actualizado en:
  - `context/C2PRO_TDD_BACKLOG_v1.0.md`
  - `context/PLAN_ARQUITECTURA_v2.1.md`

---

Last Updated: 2026-02-17

Changelog:

- 2026-02-16: Creado checklist de implementación I9 con estado `done/pending` y plan de pruebas de cierre.
- 2026-02-16: Actualizado estado a cierre de suites I9 (`APP-002`, `ADP-001`, `HTTP-001`, `INT-001`, `SEC-I9-001`) con evidencia de ejecución (`18 passed`).
- 2026-02-17: Añadido plan pendiente de pruebas transaccionales (`TS-I9-PROC-TXN-001`, `TS-I9-PROC-ADP-002`, `TS-I9-PROC-INT-002`, `TS-SEC-I9-002`).
