# JV1 · Solicitud de LV independiente A3+A5 · 23-11-2026

**Estado: PENDIENTE DE EJECUCIÓN Y DICTAMEN POR UN AUDITOR DISTINTO DEL AUTOR L2.**

## Fuente exacta

- A3 / PR #1304: `49870fdb6567c9b53ed8886d1d006509a0861e33` (NO MERGED).
- A5 / PR #1301: `6dd63bb9aae540432e0d592025f82785f6769c07` (NO MERGED).
- Combinación: checkout nuevo de A3 detached + únicamente seis ficheros productivos/de pruebas de A5, verificados por blob; jamás usar un merge de PR como atajo ni cambiar sus ramas.
- Evidencia autora: [manifest.json](./manifest.json), [JUnit main 153](./junit/main-153-pass.xml), [JUnit aux 1](./junit/aux-1-pass.xml), [JUnit cross 3](./junit/cross-final-3-pass.xml), [test sintético](./tests/test_jv1_a3a5_synthetic_compat.py).

## Revisión independiente obligatoria

1. Reproducir en checkout controlado propio, PG16 aislado y migrado con Alembic `20261118_0001`; **sin datos privados ni tráfico LLM pagado**. Verificar tenant/RLS, no-bypass, SQL real, DB y rol descartables.
2. Confirmar identidad de `provider.prompt_version` y `config_sha`: v1 y v2 hash diferentes, versión ausente o mutada falla antes de reserva/call, primera llamada vs reintento `attempt`.
3. Confirmar exactamente un `tool_use record_window_findings`: nombres distintos, bloques extra o duplicados, payload discordante, respuesta vacía/truncada, JSON incorrecto → fail-closed. Confirmar que el runner contabiliza uso sintético y deja `BLOCKED` sin hallazgos validados.
4. Reproducir cita literal N2 con `analysis_span`, `source_kind=MODEL_SAFE_PROJECTION`, evidencia de cita falsa como `PROPOSED` no verificable, y no afirmar autenticidad del PDF original.
5. Reintentos/costos: `SETTLED` 0.02+0.02 sintéticos, distinta `idempotency_key`, `reserved=0`; `UNKNOWN/RESERVED` sin reenvío/segundo cargo; fencing de generación mientras proveedor está en vuelo.
6. Separar el test `test_n4_partial_ledger_sql_pg.py` con fixture `db` destructiva en **otra DB**: la ejecución unificada de la autora produjo 23 `UndefinedTableError: public.tenants` tras el reseteo de schema. Corroborar la causa únicamente en esa ejecución, **no extrapolar** a fallos Codex2 sobre A3; pedir su traceback, DSN y cronología.
7. Verificar JUnit/XML y log de ejecución autónoma; entregar SHA-256 y PASS/FAIL/SKIP sin eliminar pruebas fallidas; clasificar Sonar/Codecov y regresiones.
8. Emitir `LV_PASS`, `LV_PASS_WITH_FINDINGS`, `LV_FAIL` o `INFRA_BLOCKED` motivado. El resultado de autora `154 PASS` **no constituye LV independiente**, ni GO del producto.

**Permisos:** revisión/QA únicamente, cero APIs comerciales, sin credenciales nuevas, sin merge ni deploy, sin modificar L1. `A5_MERGE_HOLD · A6_HOLD · JV1_GLOBAL=NO_GO`.
