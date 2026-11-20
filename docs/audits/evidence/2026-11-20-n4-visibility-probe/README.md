# Evidencia observada: por qué un resultado N4 parcial no llega al usuario (2026-11-20)

**Estado de autoridad: `BLOCKED_WORK_AUTHORITY` para DEV-16/DEV-17.** A 2026-11-20 no existe ningún sobre `C2PRO-DEV-16` ni `C2PRO-DEV-17`: no están en `origin/main:.c2pro/work/` (que solo contiene DEV-01/02/03/14/15), ni en ninguna de las ramas remotas, ni en ningún PR. `.c2pro/control/current.yaml` en `main` sigue en `active_work: []`. Por eso esta evidencia **no es entrega de DEV-16 ni sustituye a REM-G0**.

Lo que se hizo es **observación ejecutada sobre código existente**:
- en un contenedor aislado;
- con PostgreSQL 16 desechable y local (`c2pro_test`, migrado hasta `20261118_0001` con el mismo bootstrap de roles que usa el CI);
- con un proveedor *stub* de coste 0;
- sin escribir en el producto, sin red de proveedor, sin datos privados y sin entornos compartidos.

La sonda no forma parte del código del producto.

## Qué se ejecutó

| Paso | Comando o artefacto | Resultado |
|---|---|---|
| Tests PG existentes de N4, sin modificar | `pytest tests/integration/analysis/test_n4_window_runner_pg.py test_n4_incremental_store_pg.py test_n4_governed_graph_bridge_pg.py` sobre `799ce531` | 13 passed. Confirman el mecanismo actual: una referencia abierta deja el run en `PARTIAL` y los candidatos en `PROPOSED`. |
| Sonda de visibilidad | `test_probe_n4_visibility.py` contra `799ce531` (runtime UAT) y contra `916808c5` (#1276) | `out_799ce531.json`, `out_916808c5.json` |

La sonda usa las funciones reales de cada SHA: `N4IncrementalRunner`, ledger, `run_governed_n4_in_graph`, `risk_extractor_node`, `route_after_risk_extraction`, `document_lifecycle_status`, `document_is_retryable`, `_document_status_detail` y `AlertGenerator._map_risk_severity`. Replica literalmente la lista blanca de `ingestion_tasks.py:1163-1170`. El texto y las referencias son **sintéticos**, así que no dice nada sobre la calidad del modelo.

## Observaciones

| # | Escenario | 799ce531 (UAT) | 916808c5 (#1276) |
|---|---|---|---|
| A1 | 2 ventanas, referencia abierta en la ventana 0 | Run `PARTIAL`; ventana 0 `BLOCKED/REFERENCES_UNRESOLVED`, ventana 1 `EXAMINED`; **4 candidatos y 2 recibos SETTLED persistidos** | Igual |
| A2 | Puente N4 → grafo | `N4GraphBridgeBlocked: … reason=PARTIAL`, sin leer los candidatos | Igual |
| A3 | `risk_extractor_node` | `extracted_risks=0`, `workflow_terminated=true`, `analysis_blocker_code=null`, `human_approval_required=false`; ruta `terminated`; la reejecución no llama otra vez al proveedor | Igual |
| A4 | **Lo que ve el usuario** | ciclo de vida `failed_retryable`, `retryable=true`, *"Automatic analysis did not complete after several attempts. Retry to try again."* Ninguna mención a los 4 candidatos ni a la causa | **Igual** |
| B | "Retry" = generación 2 del mismo documento y revisión (generación avanzada con `UPDATE` en la BD scratch; **no es la ruta HTTP real**) | **2 llamadas nuevas al proveedor, 4 recibos SETTLED en total: doble cobro** | **0 llamadas nuevas**: bloqueado por la guarda cross-generation (`N4BudgetError`), 2 recibos. Pero el bloqueo no se reconoce (no está en la lista blanca) y el usuario vuelve a ver "Retry" |
| C | Sin referencias: run `COMPLETE` | 4 riesgos (2 con cita verificada, 2 con cita no localizada); `severity=None` en todos; el `impact` del modelo **se descarta**; la alerta resultante sería `low` | Igual |

## Conclusiones
1. **CONFIRMADO (ejecutado):** un N4 parcial con candidatos persistidos se presenta al usuario como un fallo genérico, reintentable y sin causa. Ninguna pantalla ni endpoint de `799ce531` lee los candidatos (confirmado además por lectura: no hay referencias en `apps/web`).
2. **CONFIRMADO en el ledger (con stub y emulación de generación):** en `799ce531`, reintentar sobre el mismo documento y revisión vuelve a facturar todas las ventanas. **#1276 lo impide**, pero mantiene el mensaje y el Retry engañosos.
3. **CONFIRMADO (ejecutado):** la severidad desconocida termina como `low`, y la estimación de impacto del modelo se pierde.
4. **NO EJECUTADO:** el análisis de los 142 candidatos SEC (T0.5). El paquete privado está en el VPS de QA y esta sesión no tiene acceso. No se ha fingido.

## Reproducción
1. PostgreSQL 16 con pgvector y una base `c2pro_test`.
2. `bootstrap_admin_ops_role` (de `apps/api/scripts/admin_ops_bootstrap.py`), luego `alembic upgrade head`.
3. `C2PRO_N4_SCRATCH_DSN=postgresql://…/c2pro_test PYTHONPATH=. pytest <ruta>/test_probe_n4_visibility.py -o asyncio_mode=auto --rootdir=.`, desde `apps/api` del SHA que se quiera observar.

`PROBE_OUT` indica el fichero de salida. Variables de entorno de aplicación con valores ficticios; no se usa ninguna credencial real.
